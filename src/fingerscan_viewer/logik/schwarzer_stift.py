#Erkennt einen schwarzen Stift auf heller Haut
#Dreht im Viewer den Finger von allen Seiten
#Erstellt screenshots, wendet folgendes Filter an:
#1. leicht entsaettigen
#2. Helligkeit und Kontrast anheben
#3. harter Schwellwert
#Alles was dann noch schwarz ist wird markiert. 

#noch unfinshed, da bisher nur der Strich markiert wird, füllen und Fehler aussortieren kommt 



import numpy as np
import pyvista as p_v
from scipy import ndimage
from scipy.spatial import cKDTree

import konstanten as k


# ---------- Filterkette  ----------

LUMINANZ = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def _srgb_zu_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def _linear_zu_srgb(c):
    c = np.clip(c, 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)

def gimp_kette(rgb: np.ndarray) -> np.ndarray:
    # Bildet die GIMP-Kette nach, mit der sich ein schwarzer Stift auf
    # heller Haut herausloest: leicht entsaettigen, Helligkeit und
    # Kontrast anheben, dann harter Schwellwert.
    #
    # Rueckgabe: Wert 0..255 nach der Kette. Klein = dunkel = Stift.
    wert = _srgb_zu_linear(np.asarray(rgb, dtype=np.float32)[..., :3] / 255.0)

    # Teilweise entsaettigen: Richtung Grauwert interpolieren
    grau = wert @ LUMINANZ
    wert = grau[..., None] + (wert - grau[..., None]) * k.STIFT_SAETTIGUNG

    # Helligkeit (GIMP: positiver Wert zieht Richtung Weiss)
    wert = wert + (1.0 - wert) * k.STIFT_HELLIGKEIT

    # Kontrast: Spreizung um die Bildmitte
    steigung = np.tan((k.STIFT_KONTRAST + 1.0) * np.pi / 4.0)
    wert = (wert - 0.5) * steigung + 0.5

    wert = _linear_zu_srgb(np.clip(wert, 0.0, 1.0))
    return np.clip(wert.max(axis=-1), 0.0, 1.0) * 255.0


# ---------- Ansichten aufnehmen ----------

def _kamera_richtungen():
    # Nach dem Isolieren liegt der Finger entlang Z. Rundherum ein Kranz
    # von Kameras, dazu je ein Ring von schraeg oben und schraeg unten -
    # sonst treffen Kuppe und Basis nur streifend, und genau dort laeuft
    # der Strich oft entlang.
    richtungen = []
    for hoehe_grad in (0.0, k.ANSICHT_SCHRAEG_GRAD, -k.ANSICHT_SCHRAEG_GRAD):
        anzahl = k.ANSICHTEN_RUNDUM if hoehe_grad == 0.0 else k.ANSICHTEN_SCHRAEG
        hoehe = np.radians(hoehe_grad)
        for i in range(anzahl):
            winkel = 2 * np.pi * i / anzahl
            richtungen.append(np.array([
                np.cos(winkel) * np.cos(hoehe),
                np.sin(winkel) * np.cos(hoehe),
                np.sin(hoehe),
            ]))
    return richtungen


def _id_farben(anzahl: int) -> np.ndarray:
    # Face i bekommt die Farbe i+1, auf drei Bytes verteilt. Die Null
    # bleibt fuer den Hintergrund frei, damit "kein Face" eindeutig ist.
    nummer = np.arange(1, anzahl + 1, dtype=np.int64)
    return np.column_stack([
        nummer & 0xFF,
        (nummer >> 8) & 0xFF,
        (nummer >> 16) & 0xFF,
    ]).astype(np.uint8)


def _farben_zu_ids(bild: np.ndarray) -> np.ndarray:
    # Umkehrung von _id_farben: Bild -> Face-Index (-1 = Hintergrund)
    b = bild[..., :3].astype(np.int64)
    return (b[..., 0] | (b[..., 1] << 8) | (b[..., 2] << 16)) - 1


def _kamera_setzen(plotter, mittelpunkt, richtung):
    # Blickrichtung "oben" ist die Fingerachse - ausser die Kamera schaut
    # fast von oben, dann waere sie parallel zur Blickrichtung.
    oben = (0.0, 1.0, 0.0) if abs(float(richtung[2])) > 0.9 else (0.0, 0.0, 1.0)
    plotter.camera_position = [
        tuple(mittelpunkt + richtung),    # nur die Richtung
        tuple(mittelpunkt),
        oben,
    ]
    # reset_camera behaelt die Blickrichtung und rueckt so weit weg, dass
    # der Finger ganz ins Bild passt - wie beim Drehen in der App.
    plotter.reset_camera()
    plotter.render()


def _eingabe_sperren(plotter, gesperrt: bool):
    # Waehrend der Aufnahme wandert die Kamera durch 20 Stellungen. Ein
    # Mausklick dazwischen wuerde die Bilder unbrauchbar machen.
    fenster = getattr(plotter, "interactor", None)
    if fenster is not None and hasattr(fenster, "setEnabled"):
        fenster.setEnabled(not gesperrt)


def _pixel_je_mm(id_bild, sichtbar, fein) -> float:
    # Massstab der Ansicht, aus dem ID-Puffer abgelesen: wie viele Pixel
    # entspricht ein Millimeter? Muss je Ansicht neu bestimmt werden, weil
    # das Viewer-Fenster jede Groesse haben kann.
    zeilen, spalten = np.nonzero(sichtbar)
    if len(zeilen) < 2:
        return 0.0
    quer_px = float(np.hypot(np.ptp(zeilen), np.ptp(spalten)))

    ids = np.unique(id_bild[sichtbar])
    ecken = fein.faces.reshape(-1, 4)[:, 1:][ids]
    punkte = fein.points[np.unique(ecken)]
    quer_mm = float(np.linalg.norm(np.ptp(punkte, axis=0)))
    return quer_px / quer_mm if quer_mm > 0 else 0.0


def _luecken_im_bild_schliessen(dunkel, spanne_px: int, dicke_px: int):
    # Schliesst Unterbrechungen im Strich im Bild, nicht in der Textur PNG, indem die naechsten
    # Enden zweier Stuecke direkt verbunden werden.
    #
    # Die Luecken entstehen durch Glanzlichter und helle Stellen im Scan.
    # der Stift ist dort vorhanden, im Foto aber weiss.
    #

    # Hier wird  eine gerade Strecke zwischen den beiden
    # naechsten Punkten gezogen, in der Dicke des Strichs. Bei einer
    # Luecke in einer Linie liegt diese Strecke genau auf der Linie.
    if spanne_px < 1:
        return dunkel

    ergebnis = dunkel.copy()
    acht = np.ones((3, 3), dtype=bool)

    for _ in range(k.MAX_LUECKEN):
        stuecke, anzahl = ndimage.label(ergebnis, structure=acht)
        if anzahl < 2:
            break

        # Nur Stuecke ab einer Mindestgroesse: einzelne Fehlpixel sollen
        # keine Bruecken nach sich ziehen.
        groesse = np.bincount(stuecke.ravel())
        gross = [i for i in range(1, anzahl + 1) if groesse[i] >= k.MIN_STUECK_PIXEL]
        if len(gross) < 2:
            break

        koordinaten = {i: np.column_stack(np.nonzero(stuecke == i)) for i in gross}
        bestes = None
        for nummer, i in enumerate(gross):
            andere = np.vstack([koordinaten[j] for j in gross if j != i])
            abstand, ziel = cKDTree(andere).query(koordinaten[i], k=1)
            t = int(np.argmin(abstand))
            if bestes is None or abstand[t] < bestes[0]:
                bestes = (float(abstand[t]), koordinaten[i][t], andere[ziel[t]])

        if bestes is None or bestes[0] > spanne_px:
            break

        _strecke_zeichnen(ergebnis, bestes[1], bestes[2], dicke_px)

    return ergebnis


def _strecke_zeichnen(bild, von, nach, dicke_px: int):
    schritte = int(max(abs(nach[0] - von[0]), abs(nach[1] - von[1]))) + 1
    zeilen = np.round(np.linspace(von[0], nach[0], schritte)).astype(int)
    spalten = np.round(np.linspace(von[1], nach[1], schritte)).astype(int)

    rand = max(dicke_px // 2, 0)
    versatz = np.arange(-rand, rand + 1)
    for dy in versatz:
        for dx in versatz:
            if dy * dy + dx * dx > rand * rand:
                continue
            bild[np.clip(zeilen + dy, 0, bild.shape[0] - 1),
                 np.clip(spalten + dx, 0, bild.shape[1] - 1)] = True


def _aufnehmen( plotter, 
                mittelpunkt, 
                richtung,
                scan_schauspieler,
                id_schauspieler, 
                ist_id: bool, 
                hintergrund):
    # Umschalten statt neu aufbauen: dieselbe Kamera, dasselbe Fenster,
    # nur andere Sichtbarkeiten. So passen Farbbild und ID-Puffer Pixel
    # fuer Pixel aufeinander.
    for schauspieler in scan_schauspieler:
        schauspieler.SetVisibility(not ist_id)
    id_schauspieler.SetVisibility(ist_id)
    plotter.set_background(hintergrund)
    if ist_id:
        plotter.disable_anti_aliasing()
    else:
        plotter.enable_anti_aliasing()

    _kamera_setzen(plotter, mittelpunkt, richtung)
    return plotter.screenshot(return_img=True)


def _diagnose_schreiben(ordner, nummer, farbbild, dunkel):
    from PIL import Image
    from pathlib import Path
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    Image.fromarray(farbbild[..., :3]).save(ordner / f"ansicht_{nummer:02d}_farbe.png")
    Image.fromarray((~dunkel * 255).astype(np.uint8)).save(
        ordner / f"ansicht_{nummer:02d}_maske.png")


def _direkt(funktion):
    #Ohne Hintergrund-Thread laeuft alles schon im Hauptthread, also einfach direkt aufrufen
    return funktion()


def strich_maske_aus_ansichten(plotter, fein, diagnose_ordner=None, hauptthread=_direkt):
    # Nimmt den Finger im laufenden Viewer von allen Seiten auf und
    # markiert jedes Face, das im gefilterten Bild schwarz ist.
    #
    #hauptthread fuehrt eine Funktion im Hauptthread aus. Laeuft die Suche
    #im Hintergrund, darf nur der Hauptthread den Plotter anfassen.
    mittelpunkt = np.array(fein.center)

    normalen = np.asarray(
        fein.compute_normals(cell_normals=True, point_normals=False,
                             auto_orient_normals=True).cell_data["Normals"])

    id_mesh = fein.copy(deep=True)
    id_mesh.cell_data["ID"] = _id_farben(fein.n_cells)

    #Alles, was den Plotter anfasst, gebuendelt, damit es im Hauptthread laufen kann
    def vorbereiten():
        kamera_vorher = plotter.camera_position
        hintergrund_vorher = plotter.background_color
        scan_schauspieler = [a for a in plotter.renderer.actors.values()]

        # lighting=False und spaeter kein Kantenglaetten: sonst mischt der
        # Renderer benachbarte IDs zu einer dritten, gar nicht existierenden
        # Zahl.
        id_schauspieler = plotter.add_mesh(id_mesh, scalars="ID", rgb=True,
                                           lighting=False, show_scalar_bar=False,
                                           reset_camera=False)
        _eingabe_sperren(plotter, True)
        #Die vier Werte braucht spaeter die Schleife und das Aufraeumen
        return kamera_vorher, hintergrund_vorher, scan_schauspieler, id_schauspieler

    #Vorbereitung im Hauptthread ausfuehren und die Werte zurueckholen
    kamera_vorher, hintergrund_vorher, scan_schauspieler, id_schauspieler = hauptthread(vorbereiten)

    strich = np.zeros(fein.n_cells, dtype=bool)
    gesehen = np.zeros(fein.n_cells, dtype=bool)

    #Viewer wieder so hinterlassen, wie er war, ebenfalls im Hauptthread
    def aufraeumen():
        plotter.remove_actor(id_schauspieler)
        for schauspieler in scan_schauspieler:
            schauspieler.SetVisibility(True)
        plotter.set_background(hintergrund_vorher)
        plotter.enable_anti_aliasing()
        plotter.camera_position = kamera_vorher
        plotter.render()
        _eingabe_sperren(plotter, False)

    try:
        for nummer, richtung in enumerate(_kamera_richtungen()):
            #Beide Bilder einer Ansicht in einem Rutsch im Hauptthread aufnehmen,
            #der Rest der Schleife rechnet dann im Hintergrund
            farbbild, id_bild = hauptthread(lambda: (
                _aufnehmen(plotter, mittelpunkt, richtung,
                           scan_schauspieler, id_schauspieler,
                           ist_id=False, hintergrund=hintergrund_vorher),
                _aufnehmen(plotter, mittelpunkt, richtung,
                           scan_schauspieler, id_schauspieler,
                           ist_id=True, hintergrund="black")))

            ids = _farben_zu_ids(id_bild)
            # Nur gueltige Nummern: Farbrundung kann trotz aller
            # Vorkehrungen Werte ausserhalb des Bereichs erzeugen.
            sichtbar = (ids >= 0) & (ids < fein.n_cells)
            gesehen[np.unique(ids[sichtbar])] = True

            #Erst mal ist nichts dunkel, auch der ganze Hintergrund nicht
            dunkel = np.zeros(sichtbar.shape, dtype=bool)
            #Filterkette nur auf die Finger-Pixel, der Finger ist nur rund 9 % des Bildes, spart 60 % Rechenzeit
            dunkel[sichtbar] = gimp_kette(farbbild[sichtbar]) < k.STIFT_SCHWELLE_ANSICHT
            massstab = _pixel_je_mm(ids, sichtbar, fein)
            dunkel = _luecken_im_bild_schliessen(
                dunkel,
                int(round(massstab * k.MAX_LUECKE_MM)),
                max(int(round(massstab * k.STRICH_DICKE_MM)), 1))
            getroffen = np.unique(ids[dunkel])

            if len(getroffen):
                frontal = np.abs(normalen[getroffen] @ richtung) > k.MIN_BLICKWINKEL_COS
                strich[getroffen[frontal]] = True

            if diagnose_ordner is not None:
                _diagnose_schreiben(diagnose_ordner, nummer, farbbild, dunkel)
    finally:
        #Auch bei einem Fehler den Viewer zuruecksetzen, im Hauptthread
        hauptthread(aufraeumen)

    return strich, {"gesehen": int(gesehen.sum()), "faces": int(fein.n_cells),
                    "strich": int(strich.sum())}


def _flaeche_aus_faces(fein, strich):
    dreiecke = fein.faces.reshape(-1, 4)[:, 1:][strich]
    vtk_faces = np.hstack([np.full((len(dreiecke), 1), 3), dreiecke])
    return p_v.PolyData(fein.points, vtk_faces).clean()

def _split_finger_teile(fein_ganz, strich):
    #Trennt den Finger an den Strichen. Das aeussere Teil hat die meisten
    #Randfaces, alles andere liegt innerhalb einer Markierung und wird in
    #zusammenhaengende Gebiete zerlegt. Jedes Gebiet ist ein eingezeichneter
    #Bereich mit Strich, Taschen im Strich werden so mit aufgefuellt.
    #
    #clean() ist Wichtig, weil das OBJ hat an jeder UV-Naht doppelte Punkte,
    #ohne das Zusammenlegen findet connectivity 262 Gebiete statt einem.
    fein_ganz = fein_ganz.clean()
    #Jedes Face kriegt ne Nummer, einzigartig im kompletten MEsh
    fein_ganz.cell_data["FaceNr"] = np.arange(fein_ganz.n_cells)

    #Nimmt alle aus dem MEsh, was nicht der Strich ist.
    #connectivity all gibt zusammenhaengende Gebiete, die nicht durch den Strich getrennt sind die gleiche nummer (Also wenn es eine Kantenverbindung dazwischen gibt)
    finger_ohne_striche = fein_ganz.extract_cells(~strich).connectivity("all")

    #Macht aus den Gebitsnummern ein Array
    kennung_finger = np.asarray(finger_ohne_striche.cell_data["RegionId"])
    #Berechnet die Groesse jedes Gebiets und zählt die Anzahl der FAces pro Gebiet.
    groessen_finger = np.bincount(kennung_finger)

    if len(groessen_finger) < 2:
        return []

    #Winzige Gebiete gar nicht erst betrachten, das sind Taschen zwischen
    #zwei dicht beieinander liegenden Strichteilen
    #Schreibt jeden möglichen Kandidaten mit > 200 Faces in ein Dictionary, mit der Nummer als Key und dem Teilmesh als Value
    kandidaten = {}
    for nummer in np.flatnonzero(groessen_finger >= k.MIN_FLAECHE_FACES):
        kandidaten[int(nummer)] = finger_ohne_striche.extract_cells(
            kennung_finger == nummer).extract_surface(algorithm="dataset_surface")

    #Aussenteil ist das Gebiet mit den meisten Randfaces
    max_edge_faces = -1
    aussenteil = None
    for nummer, teil in kandidaten.items():
        anzahl_edge_faces = teil.extract_feature_edges(boundary_edges=True,
                                                       feature_edges=False,
                                                       non_manifold_edges=False,
                                                       manifold_edges=False).n_cells
        if anzahl_edge_faces > max_edge_faces:
            max_edge_faces = anzahl_edge_faces
            aussenteil = nummer

    #FaceNr der Aussenteil-Faces, also ihre Nummer im ganzen Mesh statt im Teilmesh
    face_nr = np.asarray(finger_ohne_striche.cell_data["FaceNr"])
    #Maske ueber das ganze Mesh, erst mal ist kein Face aussen
    ist_aussen = np.zeros(fein_ganz.n_cells, dtype=bool)
    #Faces des Aussenteils ueber ihre FaceNr im ganzen Mesh markieren
    ist_aussen[face_nr[kennung_finger == aussenteil]] = True

    #Alles ausser dem Aussenteil, also Strich, Innenflaeche, Taschen und Kruemel, in zusammenhaengende Gebiete zerlegen
    rest = fein_ganz.extract_cells(~ist_aussen).connectivity("all")
    #Gebietsnummer je Face im Rest
    kennung_rest = np.asarray(rest.cell_data["RegionId"])
    #Nummer im ganzen Mesh je Face im Rest, damit die Strichmaske passt
    rest_nr = np.asarray(rest.cell_data["FaceNr"])

    eingekreiste_teile = []
    #Jedes Gebiet ist eine moegliche Markierung
    for nummer in range(int(kennung_rest.max()) + 1):
        #Welche Faces im Rest gehoeren zu diesem Gebiet
        im_gebiet = kennung_rest == nummer
        #Zu wenig Haut im Gebiet heisst loser Strichkruemel aussen auf dem Finger, keine Markierung
        if (~strich[rest_nr[im_gebiet]]).sum() < k.MIN_FLAECHE_FACES:
            continue
        #Gebiet als eigene Flaeche herausloesen, mit Strich und ohne Luecken
        eingekreiste_teile.append(
            rest.extract_cells(im_gebiet).extract_surface(algorithm="dataset_surface"))

    #Nach Groesse sortiert, damit die Nummerierung in der Excel-Liste und
    #in der Anzeige immer dieselbe Reihenfolge hat
    eingekreiste_teile.sort(key=lambda t: t.area, reverse=True)
    return [teil.clean() for teil in eingekreiste_teile]


# ---------- Hauptfunktion ----------

def markiere_strich(plotter, teile, diagnose_ordner=None, hauptthread=_direkt):
    # Der ganze Ablauf 
    mit_bild = [(mesh, tex) for mesh, tex in teile if mesh.n_points]
    if not mit_bild:
        return [], {}

    ganz = p_v.merge([mesh for mesh, _ in mit_bild]) if len(mit_bild) > 1 else mit_bild[0][0]

    # Unterteilen, damit ein Dreieck nur wenige Pixel gross ist 
    fein = ganz.subdivide(k.STIFT_UNTERTEILUNGEN, subfilter="linear")

    #hauptthread nur durchreichen, gebraucht wird er erst bei den Aufnahmen
    strich, bericht = strich_maske_aus_ansichten(plotter, fein, diagnose_ordner, hauptthread)

    if not strich.any():
        return [], bericht

    #Gibt eine Liste zurueck, ein Eintrag je eingekreistem Bereich, nach
    #Groesse sortiert. Bei nur einem Kreis ist die Liste einelementig.
    eingekreiste_teile = _split_finger_teile(fein, strich)
    bericht["bereiche"] = len(eingekreiste_teile)
    return eingekreiste_teile, bericht
  

    


