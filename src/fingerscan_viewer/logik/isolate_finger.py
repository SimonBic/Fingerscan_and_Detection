import pyvista as p_v
import numpy as np
from pathlib import Path

import trimesh
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from PIL import Image

import konstanten as k


def berechne_normalen(pv_mesh: p_v.PolyData) -> p_v.PolyData:
    return pv_mesh.compute_normals(
        point_normals=True,
        auto_orient_normals=True,
    )


def hole_textur_bild(material):
    if material.image is not None:
        return material.image.convert("RGB")

    farbe = getattr(material, "diffuse", None)
    if farbe is None:
        farbe = getattr(material, "main_color", [200, 200, 200, 255])
    farbe_rgb = tuple(int(c) for c in farbe[:3])
    return Image.new("RGB", (8, 8), farbe_rgb)



def load_teilmeshe_mit_textur(obj_pfad: str):
    # obj_pfad ist der Ordner
    obj_dateien = list(obj_pfad.glob("*.obj"))

    if not obj_dateien:
        print(f"Keine OBJ-Datei gefunden in: {obj_pfad}")
        return []

    if len(obj_dateien) > 1:
        print(f"Mehrere OBJ-Dateien gefunden: {obj_dateien}")

    obj_datei = obj_dateien[0]

    geladen = trimesh.load(str(obj_datei), process=False)

    print("OBJ:", obj_pfad)
    print("Typ:", type(geladen))

    if isinstance(geladen, trimesh.Scene):
        teile = list(geladen.geometry.values())
    else:
        teile = [geladen]

    count_vertices = 0
    ergebnis = []

    for tmesh in teile:

        print(
            "Teilmesh:",
            "Vertices:", len(tmesh.vertices),
            "Faces:", len(tmesh.faces),
            "Visual:", type(tmesh.visual),
            "Vertex colors:",
            getattr(tmesh.visual, "vertex_colors", None) is not None,
            "UV:",
            getattr(tmesh.visual, "uv", None) is not None,
        )

        # ==========================================================
        # FALL 1: Vertex-Farben vorhanden
        # ==========================================================
        vertex_farben = getattr(tmesh.visual, "vertex_colors", None)

        if vertex_farben is not None and len(vertex_farben) == len(tmesh.vertices):
            print("→ Mesh mit Vertex-Farben gefunden.")

            vertex_farben = np.asarray(vertex_farben)[:, :3]

            faces_vtk = np.hstack(
                [
                    np.full((len(tmesh.faces), 1), 3),
                    tmesh.faces
                ]
            ).astype(np.int64)

            count_vertices += len(tmesh.vertices)

            pv_mesh = p_v.PolyData(
                tmesh.vertices,
                faces_vtk
            )

            pv_mesh.point_data["RGB"] = vertex_farben

            pv_mesh = berechne_normalen(pv_mesh)

            # Bei Vertex-Farben bleibt tex None
            ergebnis.append((pv_mesh, None))

            continue

        # ==========================================================
        # FALL 2: Textur vorhanden (PNG/JPG)
        # ==========================================================
        uv = getattr(tmesh.visual, "uv", None)
        material = getattr(tmesh.visual, "material", None)

        if uv is not None and material is not None:
            print("→ Texturiertes Mesh gefunden.")

            faces_vtk = np.hstack(
                [
                    np.full((len(tmesh.faces), 1), 3),
                    tmesh.faces
                ]
            ).astype(np.int64)

            count_vertices += len(tmesh.vertices)

            pv_mesh = p_v.PolyData(
                tmesh.vertices,
                faces_vtk
            )

            # UV-Koordinaten übernehmen
            pv_mesh.active_texture_coordinates = np.asarray(uv)

            # ------------------------------------------------------
            # Texturbild aus dem Trimesh-Material holen
            # ------------------------------------------------------
            try:
                bild_array = np.array(
                    hole_textur_bild(material)
                )

                print(
                    "Textur geladen:",
                    bild_array.shape,
                    "Datentyp:",
                    bild_array.dtype
                )

                # --------------------------------------------------
                # Prüfen, ob es sich um PNG/JPG handelt
                #
                # Das Bild selbst enthält diese Information nicht
                # zuverlässig. Deshalb prüfen wir zusätzlich das
                # Material bzw. den ursprünglichen Pfad.
                # --------------------------------------------------

                textur_pfad = getattr(
                    material,
                    "image_path",
                    None
                )

                if textur_pfad is not None:
                    suffix = Path(str(textur_pfad)).suffix.lower()

                    if suffix in [".jpg", ".jpeg"]:
                        print("→ JPG/JPEG-Textur erkannt.")

                    elif suffix == ".png":
                        print("→ PNG-Textur erkannt.")

                    else:
                        print(
                            f"→ Unbekanntes Texturformat: {suffix}"
                        )

                else:
                    print(
                        "→ Texturformat konnte nicht über den "
                        "Dateipfad bestimmt werden."
                    )

                # PyVista-Textur erzeugen
                tex = p_v.Texture(bild_array)

                pv_mesh = berechne_normalen(pv_mesh)

                ergebnis.append((pv_mesh, tex))

            except Exception as e:
                print(
                    "Fehler beim Laden der Textur:",
                    repr(e)
                )
                continue

            continue

        # ==========================================================
        # FALL 3: Weder Vertex-Farben noch Textur
        # ==========================================================
        print(
            "Teilmesh ohne Vertex-Farben und ohne UV/Textur "
            "gefunden. Wird übersprungen."
        )

    print(
        f"Erfolgreich geladen, "
        f"{count_vertices} Vertices gesamt."
    )

    return ergebnis


 

def rendere_teile(plotter, teile: list) -> None:
    # EINE Stelle fuer die Darstellung - die Oberflaeche und die
    # Screenshots der Markierungserkennung muessen exakt gleich aussehen,
    # sonst gilt der dort eingemessene Schwellwert nicht mehr.
    for pv_mesh, tex in teile:
        #Eindeutiger Name je Mesh, daran erkennt die Stifterkennung die Fingermeshes
        name = f"{k.SCAN_TEIL_NAME}_{pv_mesh.memory_address}"
        if tex is not None:
            plotter.add_mesh(pv_mesh, texture=tex, smooth_shading=False, name=name)
        elif "RGB" in pv_mesh.point_data:
            plotter.add_mesh(pv_mesh, scalars="RGB", rgb=True, smooth_shading=True, name=name)
        else:
            plotter.add_mesh(pv_mesh, name=name)


def zeige_mit_texturen(plotter: p_v.Plotter, teile: list) -> None:
    rendere_teile(plotter, teile)
 
 
def transformiere_teile(teile: list, transform_matrix) -> list:
    return [(teil.transform(transform_matrix, inplace=False), farben) for teil, farben in teile]
 
 
def waehle_ganze_dreiecke(mesh: p_v.PolyData, flaeche: p_v.PolyData, invert: bool = False) -> p_v.PolyData:
    # Behaelt ganze Dreiecke, statt sie an der Schnittflaeche zu zerschneiden.
    #
    # Warum nicht clip_surface(): Beim echten Schneiden erzeugt VTK neue Punkte
    # auf der Schnittkante und verschmilzt dabei deckungsgleiche Punkte. An
    # einer UV-Naht liegen aber absichtlich zwei Punkte auf derselben
    # 3D-Position - einer je Inselseite, mit unterschiedlicher UV-Koordinate.
    # Werden die verschmolzen, ueberlebt nur eine der beiden UVs, und die
    # Dreiecke der anderen Seite zeigen anschliessend auf die falsche Insel.
    # Ihr Inneres tastet dann quer durch den Atlas ab - das sind die
    # gezackten Regenbogen-Streifen. Messung am echten Scan: 1555 von 13450
    # Dreiecken betroffen, groesste UV-Kante 1.04 statt 0.03.
    #
    # Ohne neue Punkte gibt es nichts zu verschmelzen, die UVs bleiben heil.
    # Preis: Der Rand verlaeuft entlang der Dreieckskanten statt exakt auf der
    # Ellipsoidflaeche - bei einem Vertexabstand von rund 0,5 mm unkritisch.
    mit_abstand = mesh.compute_implicit_distance(flaeche)
    abstand = np.asarray(mit_abstand["implicit_distance"])
    dreiecke = mit_abstand.faces.reshape(-1, 4)[:, 1:]

    if invert:
        behalten = (abstand[dreiecke] <= 0).all(axis=1)
    else:
        behalten = (abstand[dreiecke] >= 0).all(axis=1)

    if not behalten.any():
        return p_v.PolyData()

    ausgewaehlt = mit_abstand.extract_cells(behalten).extract_surface()

    # extract_surface() verliert die Kennzeichnung als aktive Texturkoordinaten
    if "Texture Coordinates" in ausgewaehlt.point_data:
        ausgewaehlt.active_texture_coordinates = np.asarray(
            ausgewaehlt.point_data["Texture Coordinates"]
        )

    return ausgewaehlt


def clippe_teile(teile: list, zylinder: p_v.PolyData) -> list:
    ergebnis = []
    for teil, farben in teile:
        geschnitten = waehle_ganze_dreiecke(teil, zylinder, invert=False)
        if geschnitten.n_points > 0:
            ergebnis.append((geschnitten, farben))
    return ergebnis


def pick_finger_point(plotter, mesh):
    punkte = []
    print("Bitte Wählen Sie den Fingernagel des verletzten Fingers")

    def callback(point, picker):
        punkte.append(np.array(point))
        print(f"Punkt {len(punkte)} gewählt bei: {point}")

        if len(punkte) < 2:
            print("Bitte jetzt den Fingernagel des Nachbar-Fingers anklicken")
        else:
            plotter.disable_picking()
            plotter.close()

    plotter.enable_point_picking(
        callback=callback,
        use_picker=True,
        show_point=True,
        color="red",
        point_size=15,
    )

    plotter.show()

    return punkte[0], punkte[1]


def rotationsmatrix(seed: np.ndarray, second_finger: np.ndarray, centroid: np.ndarray) -> np.ndarray:
    
    v = second_finger - seed
    v_hat = v / np.linalg.norm(v)
 
    m = (seed + second_finger) / 2 - centroid
 
    m_parallel = np.dot(m, v_hat) * v_hat
    m_perp = m - m_parallel
    m_perp_norm = np.linalg.norm(m_perp)
 
    if m_perp_norm < 1e-8:
        beliebige = np.array([0, 0, 1.0]) if abs(v_hat[2]) < 0.9 else np.array([1.0, 0, 0])
        m_perp_hat = beliebige - np.dot(beliebige, v_hat) * v_hat
        m_perp_hat /= np.linalg.norm(m_perp_hat)
    else:
        m_perp_hat = m_perp / m_perp_norm
 
    lokale_basis = np.column_stack([v_hat, m_perp_hat, np.cross(v_hat, m_perp_hat)])
    ziel_basis = np.column_stack([[1, 0, 0], [0, 0, 1], np.cross([1, 0, 0], [0, 0, 1])])
 
    return ziel_basis @ lokale_basis.T
 
 
def richte_hand_aus(mesh, verlezter_finger: np.ndarray, second_finger: np.ndarray):
    ist_pyvista = isinstance(mesh, p_v.PolyData)
    centroid = np.asarray(mesh.points if ist_pyvista else mesh.centroid, dtype=float)

    if ist_pyvista:
        centroid = mesh.points.mean(axis=0)
    else:
        centroid = mesh.centroid
 
    R = rotationsmatrix(verlezter_finger, second_finger, centroid)
 
    transform = np.eye(4)
    transform[:3, :3] = R
    transform[:3, 3] = -R @ centroid
 
    if ist_pyvista:
        ausgerichtetes_mesh = mesh.transform(transform, inplace=False)
    else:
        ausgerichtetes_mesh = mesh.copy()
        ausgerichtetes_mesh.apply_transform(transform)
 
    seed_neu = R @ (verlezter_finger - centroid)
    second_finger_neu = R @ (second_finger - centroid)
 
    return ausgerichtetes_mesh, seed_neu, second_finger_neu, transform

def djikstra_und_tiefster_punkt(mesh: p_v.PolyData, verlezter_finger: np.ndarray, second_finger: np.ndarray):
    idx_a = mesh.find_closest_point(verlezter_finger)
    idx_b = mesh.find_closest_point(second_finger)
 
    pfad_mesh = mesh.geodesic(idx_a, idx_b)
    pfad_punkte = pfad_mesh.points
 
    tiefster_index = np.argmin(pfad_punkte[:, 2])
    tiefster_punkt = np.array(pfad_punkte[tiefster_index])
 
    kugel_radius = mesh.length * 0.01  # relativ zur Mesh-Groesse, damit sie immer sichtbar passt
    kugel = p_v.Sphere(radius=kugel_radius, center=tiefster_punkt)
 
    return tiefster_punkt, pfad_mesh, kugel


def rotationsmatrix_a_nach_b(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    #Verwendete Rodriques Rotationsformel.
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    achse = np.cross(a, b)
    sin_winkel = np.linalg.norm(achse)
    cos_winkel = np.dot(a, b)
 
    if sin_winkel < 1e-8:
        if cos_winkel > 0:
            return np.eye(3)
        beliebig = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
        achse2 = np.cross(a, beliebig)
        achse2 /= np.linalg.norm(achse2)
        K = np.array([[0, -achse2[2], achse2[1]], [achse2[2], 0, -achse2[0]], [-achse2[1], achse2[0], 0]])
        return np.eye(3) + 2 * K @ K
 
    achse = achse / sin_winkel
    K = np.array([[0, -achse[2], achse[1]], [achse[2], 0, -achse[0]], [-achse[1], achse[0], 0]])
    return np.eye(3) + K * sin_winkel + K @ K * (1 - cos_winkel)


def baue_kantengraph(mesh: p_v.PolyData, max_kantenlaenge: float = k.MAX_KANTENLAENGE) -> csr_matrix:
    #Kantengerüst des Meshes als gewichteter Graph, damit sich Abstaende
    #entlang der Oberfläche messen lassen statt quer durch die Luft. Nach Djikstra vom Saatpunkt aus
    
    dreiecke = mesh.faces.reshape(-1, 4)[:, 1:]
    kanten = np.vstack([dreiecke[:, [0, 1]], dreiecke[:, [1, 2]], dreiecke[:, [2, 0]]])
    kanten = np.unique(np.sort(kanten, axis=1), axis=0)

    laengen = np.linalg.norm(mesh.points[kanten[:, 0]] - mesh.points[kanten[:, 1]], axis=1)
    brauchbar = laengen <= max_kantenlaenge
    kanten, laengen = kanten[brauchbar], laengen[brauchbar]

    n = mesh.n_points
    return csr_matrix(
        (np.concatenate([laengen, laengen]),
         (np.concatenate([kanten[:, 0], kanten[:, 1]]),
          np.concatenate([kanten[:, 1], kanten[:, 0]]))),
        shape=(n, n),
    )


def geodaetische_nachbarschaft(
        mesh: p_v.PolyData,
        saat_punkt: np.ndarray,
        radius: float,
        graph: csr_matrix | None = None) -> np.ndarray:
    #Statt wie davor eine Kugel, jetzt die geodätische Nachbarschaft
    #Also basically wie weit man auf dem Finger gehen muss, bis der Punkt erreicht ist vom Saatpunkt aus
    #Nach djiktra

    if graph is None:
        graph = baue_kantengraph(mesh)

    saat_index = int(mesh.find_closest_point(saat_punkt))
    abstaende = dijkstra(graph, directed=False, indices=saat_index, limit=radius)
    indices = np.flatnonzero(np.isfinite(abstaende))

    #Fallback: sitzt der Saatpunkt auf einem Scan-Artefakt (duenner Auswuchs,
    #der in einer geschlossenen Blase endet), ist die Nachbarschaft winzig.
    #Dann lieber den Radius aufziehen als eine entartete PCA rechnen.
    radius_versuch = radius
    while len(indices) < k.MIN_PCA_PUNKTE and radius_versuch < radius * k.RADIUS_MAX_FAKTOR:
        radius_versuch *= 1.5
        abstaende = dijkstra(graph, directed=False, indices=saat_index, limit=radius_versuch)
        indices = np.flatnonzero(np.isfinite(abstaende))

    if radius_versuch != radius:
        print(f"Achtung: bei {radius:.0f} mm um den gewaehlten Punkt lagen zu wenige "
              f"Vertices, Radius auf {radius_versuch:.0f} mm aufgezogen ({len(indices)} Punkte). "
              f"Die Fingerachse bitte in der Vorschau pruefen.")

    if len(indices) < k.MIN_PCA_PUNKTE:
        raise ValueError(
            f"Nur {len(indices)} Punkte im Umkreis von {radius_versuch:.0f} mm um den "
            f"gewaehlten Punkt gefunden (mindestens {k.MIN_PCA_PUNKTE} noetig). Der Punkt "
            f"liegt vermutlich auf einem Scan-Artefakt - bitte erneut auf die Fingerkuppe klicken."
        )

    return indices

#Dann weiter wie gehabt: 

def finger_normale(mesh: p_v.PolyData,
                   verletzter_finger: np.ndarray,
                   radius: float = k.PCA_RADIUS,
                   graph: csr_matrix | None = None) -> np.ndarray:

    indices = geodaetische_nachbarschaft(mesh, verletzter_finger, radius, graph)
    nahe_punkte = mesh.points[indices]

    zentriert = nahe_punkte - nahe_punkte.mean(axis=0)
    kovarianz = np.cov(zentriert.T)
    eigenwerte, eigenvektoren = np.linalg.eigh(kovarianz)
 
    normale = eigenvektoren[:, np.argmax(eigenwerte)]
 
    # Vorzeichen festlegen: Achse soll vom Hand-Schwerpunkt WEG zeigen
    # (Finger zeigen anatomisch immer nach aussen, unabhaengig von der Pose)
    hand_schwerpunkt = mesh.points.mean(axis=0)
    richtung_vom_zentrum = verletzter_finger - hand_schwerpunkt

    if np.dot(normale, richtung_vom_zentrum) < 0:
        normale = -normale
 
    return normale, nahe_punkte, nahe_punkte.mean(axis = 0)


def ellipsoid_geometrie(
        lokales_zentrum: np.ndarray,
        normale: np.ndarray,
        verwendete_punkte: np.ndarray,
        tiefster_punkt: np.ndarray,
        radius_faktor = 2.0,
        laengen_faktor = 0.8,
        unterschreitung: float = 0.6,
        dicken_faktor: float | None = None,
        versatz_breite: float = 0.0,
        versatz_dicke: float = 0.0) -> dict:
    # Lage, Achsen und Halbachsen des Schnittellipsoids, ohne das Mesh. Die
    # Oberflaeche braucht das fuer die Ziehpfeile und um gezogene mm wieder
    # in Faktoren umzurechnen.
    # dicken_faktor None: quer zur Fingerachse rund, so wie frueher nur mit
    # radius_faktor. Der Versatz schiebt die Mitte seitlich von der
    # Fingerachse weg, in Vielfachen von radius_original, damit er auch beim
    # naechsten Scan desselben Patienten ungefaehr passt.
    if dicken_faktor is None:
        dicken_faktor = radius_faktor

    if abs(normale[2]) < 1e-8:
        raise ValueError(
            "Fingerachse verläuft horizontal zur Ellipsoid-Ausrichtung kann nicht eindeutig auf eine Höhe z bezogen werden."
        )
 
    t_boden = (tiefster_punkt[2] - lokales_zentrum[2]) / normale[2]
 
    relative_punkte = verwendete_punkte - lokales_zentrum
    axiale_projektionen = relative_punkte @ normale
    radiale_komponenten = relative_punkte - np.outer(axiale_projektionen, normale)
    radius_original = np.linalg.norm(radiale_komponenten, axis=1).max()
 
    t_oben = axiale_projektionen.max()
    if t_oben <= t_boden:
        raise ValueError(
            "Der Wurzel-Punkt liegt auf oder ueber der obersten PCA-Nachbarschaft - "
            "pruefe tiefster_punkt/lokales_zentrum auf Plausibilitaet."
        )
 
    original_laenge = t_oben - t_boden
    halbe_hauptachse = laengen_faktor * original_laenge
    unten_spitze_t = t_boden - unterschreitung * original_laenge
    zentrum_t = unten_spitze_t + halbe_hauptachse

    # Querachsen: Breite zeigt Richtung Nachbarfinger. Nach richte_hand_aus
    # liegt der auf +x, also x senkrecht zur Fingerachse projizieren. Dicke
    # steht senkrecht auf beiden (Handruecken/Handflaeche).
    # Die Basis MUSS rechtshaendig sein: gespiegelt zeigen die Flaechennormalen
    # nach innen, und compute_implicit_distance in waehle_ganze_dreiecke
    # vertauscht dann innen und aussen.
    achse_laenge = normale / np.linalg.norm(normale)
    achse_breite = np.array([1.0, 0, 0]) - achse_laenge[0] * achse_laenge
    if np.linalg.norm(achse_breite) < 1e-8:
        #Fingerachse laeuft genau entlang x, dann ist die Richtung egal
        achse_breite = np.array([0, 1.0, 0]) - achse_laenge[1] * achse_laenge
    achse_breite /= np.linalg.norm(achse_breite)
    achse_dicke = np.cross(achse_laenge, achse_breite)

    ellipsoid_mitte = (lokales_zentrum + normale * zentrum_t
                       + (versatz_breite * achse_breite + versatz_dicke * achse_dicke) * radius_original)

    return {
        "mitte": ellipsoid_mitte,
        "achsen": {"laenge": achse_laenge, "breite": achse_breite, "dicke": achse_dicke},
        "halbachsen": {
            "laenge": halbe_hauptachse,
            "breite": radius_faktor * radius_original,
            "dicke": dicken_faktor * radius_original,
        },
        "radius_original": radius_original,
        "original_laenge": original_laenge,
    }


def ellipsoid_mesh(geometrie: dict) -> p_v.PolyData:
    # Ellipsoid entlang X bauen (Standard-Ausrichtung von
    # ParametricEllipsoid), dann auf die Achsen drehen + verschieben
    halbachsen = geometrie["halbachsen"]
    achsen = geometrie["achsen"]
    basis_ellipsoid = p_v.ParametricEllipsoid(
        xradius=halbachsen["laenge"], yradius=halbachsen["breite"], zradius=halbachsen["dicke"]
    )
    transform = np.eye(4)
    transform[:3, :3] = np.column_stack([achsen["laenge"], achsen["breite"], achsen["dicke"]])
    transform[:3, 3] = geometrie["mitte"]

    return basis_ellipsoid.transform(transform, inplace = False)


def erstelle_schnitt_ellipsoid(
        lokales_zentrum: np.ndarray,
        normale: np.ndarray,
        verwendete_punkte: np.ndarray,
        tiefster_punkt: np.ndarray,
        radius_faktor = 2.0,
        laengen_faktor = 0.8,
        unterschreitung: float = 0.6,
        dicken_faktor: float | None = None,
        versatz_breite: float = 0.0,
        versatz_dicke: float = 0.0) -> p_v.PolyData:

    return ellipsoid_mesh(ellipsoid_geometrie(
        lokales_zentrum, normale, verwendete_punkte, tiefster_punkt,
        radius_faktor=radius_faktor, laengen_faktor=laengen_faktor, unterschreitung=unterschreitung,
        dicken_faktor=dicken_faktor, versatz_breite=versatz_breite, versatz_dicke=versatz_dicke))


def berechne_finale_ausrichtung(normale: np.ndarray, achsen_punkt: np.ndarray, kerben_punkt: np.ndarray) -> np.ndarray:
    R1 = rotationsmatrix_a_nach_b(normale, np.array([0, 0, 1.0]))
    achsen_punkt_rot = R1 @ achsen_punkt
    kerben_punkt_rot = R1 @ kerben_punkt

    naechster_punkt = np.array([achsen_punkt_rot[0], achsen_punkt_rot[1], kerben_punkt_rot[2]])
    kerben_verschoben = kerben_punkt_rot - naechster_punkt

    theta = np.arctan2(kerben_verschoben[1], kerben_verschoben[0])
    c, s = np.cos(-theta), np.sin(-theta)
    R3 = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    R_gesamt = R3 @ R1
    verschiebung = -R3 @ naechster_punkt

    transform = np.eye(4)
    transform[:3, :3] = R_gesamt
    transform[:3, 3] = verschiebung
    return transform


def speichere_isolierten_finger(scan_ordner_pfad: str, texture_teile_isoliert: list,
                                ersetzen_erlaubt=None) -> Path | None:
    # Je Scan gibt es hoechstens einen isolierten Finger. Liegt schon einer da,
    # entscheidet ersetzen_erlaubt(ziel_ordner): True = der Aufrufer hat den
    # alten weggeraeumt, neu speichern. False = alten behalten, dann wird hier
    # nichts geschrieben und None zurueckgegeben.
    scan_ordner = Path(scan_ordner_pfad)
    originale_scans_ordner = scan_ordner.parent
    patienten_ordner = originale_scans_ordner.parent
 
    isolierte_scans_ordner = patienten_ordner / "isolierte_scans"
    isolierte_scans_ordner.mkdir(exist_ok=True)
 
    ziel_name = scan_ordner.name + "_isoliert"
    ziel_ordner = isolierte_scans_ordner / ziel_name
    return_ordner = ziel_ordner
    if ziel_ordner.exists() and ersetzen_erlaubt is not None and not ersetzen_erlaubt(ziel_ordner):
        print(f"Isolated finger {ziel_name} already exists and is kept, the new one is not saved")
        return None
    ziel_ordner.mkdir(exist_ok=True)
 
    save_path = ziel_ordner / f"{ziel_name}.obj"
 
    geometrien = {}
    for i, (pv_mesh, tex) in enumerate(texture_teile_isoliert):
        dreiecks_mesh = pv_mesh.triangulate()
        faces = dreiecks_mesh.faces.reshape(-1, 4)[:, 1:]
 
        if tex is not None:
            # Texturiertes Teil (JPG/PNG): echte Textur exportieren,
            # damit die volle Bildaufloesung erhalten bleibt (statt
            # nur ein Farbwert pro Vertex).
            uv = np.asarray(dreiecks_mesh.active_texture_coordinates)
            bild = Image.fromarray(tex.to_array())

            tmesh = trimesh.Trimesh(
                vertices=dreiecks_mesh.points, faces=faces, process=False)
            tmesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=bild)

        elif "RGB" in dreiecks_mesh.point_data:
            # Teil hat bereits Vertex-Farben, keine Textur.
            farben = np.asarray(dreiecks_mesh.point_data["RGB"])
            tmesh = trimesh.Trimesh(
                vertices=dreiecks_mesh.points, faces=faces,
                vertex_colors=farben, process=False)

        else:
            print(f"Warnung: Teil {i} hat weder Textur noch Vertex-Farben, wird uebersprungen.")
            continue

        geometrien[f"teil_{i}"] = tmesh

    if not geometrien:
        raise ValueError("Keine gueltigen texturierten Teile zum Speichern gefunden.")
 
    scene = trimesh.Scene(geometrien)
    scene.export(str(save_path))
 
    print(f"Isolierter Finger ({len(geometrien)} Materialien) gespeichert unter: {save_path}")
    return return_ordner


def isolate_finger_parameter_datei_pfad(scan_ordner: Path) -> Path:
        #Pfad zur Parameterdatei, siehe Ordnerstruktur.pdf (Update ich bald)
        patienten_ordner = scan_ordner.parent.parent
        return patienten_ordner / "pat_parameter" / "isolate_finger_parameter.txt"


def lade_isolate_finger_parameter(scan_ordner: Path) -> dict | None:
    pfad = isolate_finger_parameter_datei_pfad(scan_ordner)
    if not pfad.exists():
        return None
                
    werte = {}
    for zeile in pfad.read_text().splitlines():
        if "=" not in zeile:
            continue
        name, wert = zeile.split("=")
        werte[name.strip()] = float(wert.strip())

    #Aeltere Dateien haben noch anzahl_punkte_pca (Punktzahl einer
    #euklidischen Kugel). Das laesst sich nicht in einen Radius entlang der
    #Oberflaeche umrechnen, weil die alte Kugel je nach Scan bis auf den
    #Nachbarfinger uebergriff. Darum wird der Wert verworfen und der
    #eingemessene Default gesetzt.
    if "pca_radius" not in werte:
        werte.pop("anzahl_punkte_pca", None)
        werte["pca_radius"] = k.PCA_RADIUS

    #Aeltere Dateien kennen nur einen runden Querschnitt. Dicke = Breite
    #schneidet genau wie damals, sonst wuerde die Automatik bei diesen
    #Patienten ploetzlich mit der Standard-Dicke schneiden.
    if "dicken_faktor" not in werte and "radius_faktor" in werte:
        werte["dicken_faktor"] = werte["radius_faktor"]

    return werte

def speichere_isolate_finger_parameter(
            scan_ordner: Path,
            radius_faktor: float,
            laengen_faktor: float,
            unterschreitung: float,
            pca_radius: float = k.PCA_RADIUS,
            dicken_faktor: float | None = None,
            versatz_breite: float = 0.0,
            versatz_dicke: float = 0.0) -> Path:

    if dicken_faktor is None:
        dicken_faktor = radius_faktor
    pfad = isolate_finger_parameter_datei_pfad(scan_ordner)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        f"radius_faktor={radius_faktor}\n"
        f"dicken_faktor={dicken_faktor}\n"
        f"laengen_faktor={laengen_faktor}\n"
        f"unterschreitung={unterschreitung}\n"
        f"pca_radius={pca_radius}\n"
        f"versatz_breite={versatz_breite}\n"
        f"versatz_dicke={versatz_dicke}\n"
    )
    return pfad

###!!! Der Spaß ist jetzt n Generator, also mit "for _ in isoltae_finer(...): \n\tab pass" aufrufen!!!

def isolate_finger(path: str,
                plotter = None,
                radius_faktor = k.ISOLIEREN_STANDARD_WERTE["radius_faktor"],
                laengen_faktor = k.ISOLIEREN_STANDARD_WERTE["laengen_faktor"],
                unterschreitung = k.ISOLIEREN_STANDARD_WERTE["unterschreitung"],
                pca_radius = k.ISOLIEREN_STANDARD_WERTE["pca_radius"],
                dicken_faktor = k.ISOLIEREN_STANDARD_WERTE["dicken_faktor"],
                versatz_breite = k.ISOLIEREN_STANDARD_WERTE["versatz_breite"],
                versatz_dicke = k.ISOLIEREN_STANDARD_WERTE["versatz_dicke"],
                zeige_zwischenschritte = True,
                bei_punkt_gesetzt = None,
                bei_punkt_abgelehnt = None,
                ersetzen_erlaubt = None):
    # bei_punkt_gesetzt(anzahl): wird nach jedem Klick auf eine Fingerspitze
    # aufgerufen, damit die Oberflaeche ihren Hinweis anpassen kann.
    # bei_punkt_abgelehnt(abstand): der zweite Punkt lag zu nah am ersten
    # und wurde nicht gesetzt.
    # ersetzen_erlaubt(ziel_ordner): siehe speichere_isolierten_finger. Gibt
    # sie False zurueck, endet der Ablauf mit None statt mit dem Ordner.
    path = Path(path)

    texture_teile = load_teilmeshe_mit_textur(path)
    hand_mesh = p_v.merge([teil for teil, tex in texture_teile])

    if plotter is not None:
        plotter.clear()
        zeige_mit_texturen(plotter, texture_teile)
        plotter.reset_camera()

        punkte = []
        kugel_radius = hand_mesh.length * k.ISOLIEREN_KUGEL_ANTEIL
        def punkt_callback(point, picker):
            # Zweiter Punkt (fast) auf dem ersten: die Richtung zwischen den
            # Fingerspitzen waere nicht bestimmbar, also gar nicht erst setzen
            if len(punkte) == 1:
                abstand = float(np.linalg.norm(np.array(point) - punkte[0]))
                if abstand <= k.ISOLIEREN_MIN_ABSTAND_MM:
                    print(f"Second point only {abstand:.1f} mm away from the first, not set")
                    if bei_punkt_abgelehnt is not None:
                        bei_punkt_abgelehnt(abstand)
                    return
            punkte.append(np.array(point))
            print(f"Punkt {len(punkte)} gewählt bei: {point}")
            # Kugel statt flachem Punkt, der war je nach Blickwinkel kaum zu
            # sehen. Ab dem dritten Klick grau, es zaehlen nur die ersten zwei.
            if len(punkte) <= len(k.ISOLIEREN_KUGEL_FARBEN):
                farbe = k.ISOLIEREN_KUGEL_FARBEN[len(punkte) - 1]
            else:
                farbe = k.ISOLIEREN_KUGEL_UEBERZAEHLIG
                print(f"Point {len(punkte)} is not used, only the first two points count")
            # pickable=False: sonst trifft der naechste Klick die Kugel statt den Finger
            plotter.add_mesh(p_v.Sphere(radius=kugel_radius, center=point), color=farbe,
                             smooth_shading=True, pickable=False, name=f"isolieren_kugel_{len(punkte)}", opacity=0.5)
            if bei_punkt_gesetzt is not None:
                bei_punkt_gesetzt(len(punkte))

        #Falls vorher noch ein Picking aktiv war (z.B. vom Zeichnen), wirft
        #pyvista sonst einen PyVistaPickingError
        plotter.disable_picking()
        print("disabled picking in plotter, meaning cleanup")
        plotter.enable_point_picking(
            callback=punkt_callback, use_picker=True, show_point=False
        )
        print("enabled picking in plotter, now new and clean")

        def letzten_punkt_entfernen():
            # Fuer "Letzte Markierung zuruecknehmen": letzten Klick samt Kugel
            # weg. Gibt zurueck, wie viele Punkte noch da sind, None wenn
            # keiner mehr da war.
            if not punkte:
                return None
            nummer = len(punkte)
            punkte.pop()
            plotter.remove_actor(f"isolieren_kugel_{nummer}", reset_camera=False, render=True)
            print(f"Point {nummer} taken back, {len(punkte)} left")
            return len(punkte)

        # Nutzer klickt jetzt 2 Punkte, dann "Fertig markiert"/"Weiter".
        # Die Oberflaeche bekommt dafuer die Funktion zum Zuruecknehmen.
        yield letzten_punkt_entfernen

        plotter.disable_picking()

        if len(punkte) < 2:
            raise ValueError("Nicht genug Punkte gewählt - bitte 2 Punkte anklicken, bevor weitergemacht wird.")

        hurt_finger, second_finger = punkte[0], punkte[1]
    else:
        my_p_v_plotter = p_v.Plotter()
        zeige_mit_texturen(my_p_v_plotter, texture_teile)
        hurt_finger, second_finger = pick_finger_point(my_p_v_plotter, hand_mesh)
    if (hurt_finger is None) or (second_finger is None):
        raise ValueError("Ungenügend Fingerspitzen gewählt")
    # Auch hier pruefen, falls jemand ohne die Oberflaeche aufruft
    if np.linalg.norm(second_finger - hurt_finger) <= k.ISOLIEREN_MIN_ABSTAND_MM:
        raise ValueError(f"Die beiden Fingerspitzen liegen nicht mehr als "
                         f"{k.ISOLIEREN_MIN_ABSTAND_MM:.0f} mm auseinander.")
    
    print("Finger korrekt gewählt.")
    print(f"Koordinaten des verlzten Fingers: {hurt_finger}")
    print(f"Finger des benachbarten Fingers: {second_finger}")

    
    
    #Handausrichten
    hand_ausgerichtet, hurt_finger, second_finger, transformierungsmatrix = richte_hand_aus(hand_mesh, hurt_finger, second_finger)
    texture_teile = transformiere_teile(texture_teile, transformierungsmatrix) 

    #Djikstra & gleichzeitig tiefster Punkt (still, kein Zwischenschritt mehr)
    tiefster_punkt, pfad_mesh, kugel = djikstra_und_tiefster_punkt(hand_ausgerichtet, hurt_finger, second_finger)

    #Normale mit PCA (still, kein Zwischenschritt mehr).
    
    kantengraph = baue_kantengraph(hand_ausgerichtet)
    normale, verwendete_vertices, avg_point_of_hurt_finger = finger_normale(
        hand_ausgerichtet, hurt_finger, pca_radius, kantengraph
    )

    #Einziger verbleibender Zwischenschritt: Ellipsoid live einstellbar.
    if zeige_zwischenschritte and plotter is not None:
        plotter.clear()
        zeige_mit_texturen(plotter, texture_teile)
        plotter.reset_camera()


        empfangene_werte = yield {
            "avg_point_of_hurt_finger": avg_point_of_hurt_finger,
            "normale": normale,
            "verwendete_vertices": verwendete_vertices,
            "tiefster_punkt": tiefster_punkt,
            "hand_ausgerichtet": hand_ausgerichtet,
            "hurt_finger": hurt_finger,
            "pca_radius": pca_radius,
            "kantengraph": kantengraph,
        }
        if empfangene_werte is not None:
            radius_faktor = empfangene_werte.get("radius_faktor", radius_faktor)
            laengen_faktor = empfangene_werte.get("laengen_faktor", laengen_faktor)
            unterschreitung = empfangene_werte.get("unterschreitung", unterschreitung)
            dicken_faktor = empfangene_werte.get("dicken_faktor", dicken_faktor)
            versatz_breite = empfangene_werte.get("versatz_breite", versatz_breite)
            versatz_dicke = empfangene_werte.get("versatz_dicke", versatz_dicke)

            neuer_pca_radius = empfangene_werte.get("pca_radius", pca_radius)
            if neuer_pca_radius != pca_radius:
                pca_radius = neuer_pca_radius
                normale, verwendete_vertices, avg_point_of_hurt_finger = finger_normale(
                    hand_ausgerichtet, hurt_finger, pca_radius, kantengraph
                )

    elif zeige_zwischenschritte:
        ellipsoid_vorschau = erstelle_schnitt_ellipsoid(
            avg_point_of_hurt_finger, normale, verwendete_vertices, tiefster_punkt,
            radius_faktor=radius_faktor, laengen_faktor=laengen_faktor, unterschreitung=unterschreitung,
            dicken_faktor=dicken_faktor, versatz_breite=versatz_breite, versatz_dicke=versatz_dicke
        )
        ellipsoid_plotter = p_v.Plotter()
        zeige_mit_texturen(ellipsoid_plotter, texture_teile)
        ellipsoid_plotter.add_mesh(ellipsoid_vorschau, color="cyan", opacity=0.3)
        ellipsoid_plotter.show()

    #Schnittellipsoid bestimmen (mit den finalen, evtl. per Slider angepassten Parametern)
    ellipsoid = erstelle_schnitt_ellipsoid(
        avg_point_of_hurt_finger, 
        normale, 
        verwendete_vertices, 
        tiefster_punkt,
        radius_faktor = radius_faktor,
        laengen_faktor = laengen_faktor,
        unterschreitung = unterschreitung,
        dicken_faktor = dicken_faktor,
        versatz_breite = versatz_breite,
        versatz_dicke = versatz_dicke)

    #Cutten
    texture_teile_isoliert = clippe_teile(texture_teile, ellipsoid)

    #Finale Ausrichtung: Fingerachse -> Z-Achse, Kerbenpunkt -> +X-Achse
    finale_transform = berechne_finale_ausrichtung(normale, avg_point_of_hurt_finger, tiefster_punkt)
    texture_teile_isoliert = transformiere_teile(texture_teile_isoliert, finale_transform)

    if plotter is not None:
        plotter.clear()
        zeige_mit_texturen(plotter, texture_teile_isoliert)
        plotter.reset_camera()
    else:
        iso_finger_plotter = p_v.Plotter()
        zeige_mit_texturen(iso_finger_plotter, texture_teile_isoliert)
        iso_finger_plotter.show()

    #Finger speichern
    markierungsordner = speichere_isolierten_finger(path, texture_teile_isoliert, ersetzen_erlaubt)

    return markierungsordner

# path_string = input("Pfad eingeben:")
# isolate_finger(path_string, plotter = p_v.Plotter(), 
#                 radius_faktor = 2.0, 
#                 laengen_faktor = 0.8, 
#                 unterschreitung = 0.45, 
#                 zeige_zwischenschritte = True)










