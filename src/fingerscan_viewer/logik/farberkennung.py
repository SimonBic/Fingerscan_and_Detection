import colorsys
import numpy as np
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix

import konstanten as k

def erzeuge_farbpalette(anzahl = 81):
    farben = []
    for i in range(anzahl):
        h = i / anzahl
        s = 0.85 if i % 2 == 0 else 0.55
        v = 0.9 if i % 3 != 0 else 0.65
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        farben.append('#{:02X}{:02X}{:02X}'.format(int(r*255), int(g*255), int(b*255)))
    return farben


def hex_zu_rgb(hex_code: str) -> np.ndarray:
    return np.array([int(hex_code.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def texel_koordinaten(uv: np.ndarray, breite: int, hoehe: int) -> tuple:
    # UV zeigt von unten nach oben, Bildzeilen von oben nach unten deswgen 1-v
    x = np.clip((uv[:, 0] * (breite - 1)).astype(np.int32), 0, breite - 1)
    y = np.clip(((1 - uv[:, 1]) * (hoehe - 1)).astype(np.int32), 0, hoehe - 1)
    return x, y


def medianer_texelabstand(x: np.ndarray, y: np.ndarray) -> float:
    # Wie weit benachbarte Vertices in der Textur auseinanderliegen. Daraus
    # ergibt sich, wie weit das Abtastraster gespreizt werden muss, damit
    # keine Luecken zwischen den Vertices bleiben. Pro Scan verschieden,
    # deshalb gemessen statt als Konstante angenommen.
    if len(x) < 2:
        return 1.0
    pixel = np.column_stack([x, y]).astype(np.float32)
    abstaende, _ = cKDTree(pixel).query(pixel, k=2)
    return float(max(np.median(abstaende[:, 1]), 1.0))


def kleinster_farbabstand(bild: np.ndarray, x: np.ndarray, y: np.ndarray,
                          ziel_rgb: np.ndarray, spreizung: float) -> np.ndarray:
    # Pro Vertex ein kleines Texelraster lesen und den besten Treffer darin
    # behalten. Es wird ueber die Rasterpositionen iteriert statt alle
    # Farben auf einmal zu holen, so liegen nie mehr als n_vertices Werte
    # gleichzeitig im Speicher, nicht n_vertices * raster^2.
    hoehe, breite = bild.shape[:2]
    versatz = np.unique(np.linspace(-spreizung, spreizung, k.RASTER_GROESSE).round().astype(int))

    bester_abstand = np.full(len(x), np.inf, dtype=np.float32)
    for dy in versatz:
        zeile = np.clip(y + dy, 0, hoehe - 1)
        for dx in versatz:
            spalte = np.clip(x + dx, 0, breite - 1)
            farben = bild[zeile, spalte].astype(np.float32)
            abstand = np.linalg.norm(farben - ziel_rgb, axis=1)
            np.minimum(bester_abstand, abstand, out=bester_abstand)
    return bester_abstand


def markierungsfarbe_um_texel(bild: np.ndarray, xi: int, yi: int) -> np.ndarray:
    # Die reinste Markierungsfarbe in der Umgebung des angeklickten Texels.
    #
    # Das angeklickte Texel selbst taugt nicht als Referenz: die Stiftlinie
    # ist nur ~25 Texel breit, die Vertices liegen ~14 Texel auseinander -
    # ein Vertex trifft den Linienkern selten mittig, seine Farbe ist meist
    # eine Mischung aus Linie und Haut. Gemessen ist das dunkelste Texel an
    # einem Vertex #231C15, der Linienkern in der Textur aber #443638.
    #
    # Ein blosser Median der Umgebung hilft nicht (die Haut ueberwiegt
    # flaechenmaessig), und "am weitesten vom Median entfernt" faengt die
    # hellen Glanzlichter mit ein, beides gemessen und verworfen.
    #
    # Was traegt: das angeklickte Texel gibt die RICHTUNG vor, in der sich
    # die Markierung vom Untergrund unterscheidet. Entlang dieser Richtung
    # werden die extremsten Texel der Umgebung gemittelt. Damit ist nichts
    # ueber die Farbe angenommen - dunkler Stift, heller oder bunter
    # Marker funktionieren gleichermassen.
    hoehe, breite = bild.shape[:2]
    versatz = np.arange(-k.PIPETTE_RADIUS_TEXEL, k.PIPETTE_RADIUS_TEXEL + 1)
    zeilen = np.clip(yi + versatz, 0, hoehe - 1)
    spalten = np.clip(xi + versatz, 0, breite - 1)
    umgebung = bild[np.ix_(zeilen, spalten)].reshape(-1, bild.shape[2])[:, :3].astype(np.float32)

    untergrund = np.median(umgebung, axis=0)
    richtung = bild[yi, xi][:3].astype(np.float32) - untergrund
    laenge = float(np.linalg.norm(richtung))

    # Hebt sich das geklickte Texel gar nicht ab, war der Klick auf
    # gleichmaessiger Flaeche - dann ist der Untergrund die ehrliche Antwort.
    if laenge < k.PIPETTE_MIN_ABHEBUNG:
        return untergrund

    projektion = (umgebung - untergrund) @ (richtung / laenge)
    grenze = np.percentile(projektion, 100 - k.PIPETTE_AUFFAELLIG_PROZENT)
    return np.median(umgebung[projektion >= grenze], axis=0)


def textur_farbe_an_punkt(teile: list, punkt: np.ndarray) -> str:
    # Farbe an der Stelle, die dem angeklickten 3D-Punkt am naechsten liegt -
    # aus der textur, nicht aus dem Bildschirm.
    #
    # Gelesen wird nicht ein einzelnes Texel, sondern der Median einer
    # kleinen Umgebung: gegen Rauschen und gegen leichtes Danebenklicken.
    bestes = None
    for pv_mesh, tex in teile:
        if pv_mesh.n_points == 0:
            continue
        index = int(pv_mesh.find_closest_point(punkt))
        abstand = float(np.linalg.norm(pv_mesh.points[index] - punkt))
        if bestes is None or abstand < bestes[0]:
            bestes = (abstand, pv_mesh, tex, index)

    if bestes is None:
        return None
    _, pv_mesh, tex, index = bestes

    if pv_mesh.active_texture_coordinates is not None and tex is not None:
        bild = tex.to_array()
        hoehe, breite = bild.shape[:2]
        uv = np.asarray(pv_mesh.active_texture_coordinates)
        x, y = texel_koordinaten(uv, breite, hoehe)

        farbe = markierungsfarbe_um_texel(bild, int(x[index]), int(y[index]))
    elif "RGB" in pv_mesh.point_data:
        farbe = np.asarray(pv_mesh.point_data["RGB"])[index][:3]
    else:
        return None

    return "#%02X%02X%02X" % tuple(int(np.clip(c, 0, 255)) for c in farbe)


def schwelle_aus_verteilung(abstaende: np.ndarray) -> float:
    
    endlich = abstaende[np.isfinite(abstaende)]
    if len(endlich) < 10:
        return k.FALLBACK_TOLERANZ

    median = float(np.median(endlich))
    mad = float(np.median(np.abs(endlich - median))) * 1.4826
    if mad <= 0:
        return k.FALLBACK_TOLERANZ

    schwelle = median - k.SCHWELLE_MAD_FAKTOR * mad

    # Plausibilitaet: eine Markierung ist immer ein kleiner Teil der
    # Oberflaeche. Rutscht die Schwelle daneben, lieber den Rueckfallwert.
    anteil = float((endlich < schwelle).mean())
    if schwelle <= 0 or anteil > k.MAX_MARKIERUNGS_ANTEIL or anteil < k.MIN_MARKIERUNGS_ANTEIL:
        return k.FALLBACK_TOLERANZ

    return schwelle


def _teil_abstaende(pv_mesh, tex, ziel_rgb: np.ndarray, nur_ein_texel: bool = False) -> np.ndarray:
    # Farbabstand jedes Vertex zur Zielfarbe - egal ob die Farbe aus einer
    # Textur oder aus Vertex-Farben kommt. Gibt None zurueck, wenn das Teil
    # ueberhaupt keine Farbinformation hat.
    if pv_mesh.active_texture_coordinates is not None and tex is not None:
        bild = tex.to_array()
        hoehe, breite = bild.shape[:2]
        x, y = texel_koordinaten(np.asarray(pv_mesh.active_texture_coordinates), breite, hoehe)
        if nur_ein_texel:
            return np.linalg.norm(bild[y, x].astype(np.float32) - ziel_rgb, axis=1)
        spreizung = medianer_texelabstand(x, y) * k.RASTER_SPREIZUNG
        return kleinster_farbabstand(bild, x, y, ziel_rgb, spreizung)

    # Vertex-Farben: der Loader fuellt point_data["RGB"], wenn das OBJ keine
    # Textur mitbringt (isolate_finger.py). Frueher wurden solche Teile
    # stumm uebersprungen - isolierte Finger lieferten dadurch immer
    # "keine Markierung gefunden".
    if "RGB" in pv_mesh.point_data:
        farben = np.asarray(pv_mesh.point_data["RGB"]).astype(np.float32)[:, :3]
        return np.linalg.norm(farben - ziel_rgb, axis=1)

    return None


def finde_markierungs_punkte(teile: list, hex_code: str, toleranz: float = None,
                             gib_masken: bool = False, nur_ein_texel: bool = None):
   
    if nur_ein_texel is None:
        nur_ein_texel = toleranz is not None

    ziel_rgb = hex_zu_rgb(hex_code)

    abstaende_je_teil = []
    for pv_mesh, tex in teile:
        abstaende_je_teil.append((pv_mesh, _teil_abstaende(pv_mesh, tex, ziel_rgb, nur_ein_texel)))

    brauchbar = [a for _, a in abstaende_je_teil if a is not None]
    if not brauchbar:
        return ([], np.empty((0, 3))) if gib_masken else np.empty((0, 3))

    schwelle_automatisch = toleranz is None
    if schwelle_automatisch:
        toleranz = schwelle_aus_verteilung(np.concatenate(brauchbar))

    masken, punkte = [], []
    for pv_mesh, abstaende in abstaende_je_teil:
        if abstaende is None:
            maske = np.zeros(pv_mesh.n_points, dtype=bool)
        else:
            maske = abstaende < toleranz
        masken.append((pv_mesh, maske))
        if maske.any():
            punkte.append(pv_mesh.points[maske])

    alle_punkte = np.vstack(punkte) if punkte else np.empty((0, 3))

    # Sicherung gegen "halbe Hand markiert": lieber nichts liefern als eine
    # Flaeche, die offensichtlich keine Markierung mehr ist. Nur bei
    # automatischer Schwelle - wer eine Toleranz vorgibt (Volumenmessung in
    # messungen.py), bekommt genau das, wonach er gefragt hat.
    gesamt = sum(len(a) for a in brauchbar)
    if schwelle_automatisch and len(alle_punkte) > gesamt * k.MAX_MARKIERUNGS_ANTEIL:
        leer = [(m, np.zeros(m.n_points, dtype=bool)) for m, _ in abstaende_je_teil]
        return (leer, np.empty((0, 3))) if gib_masken else np.empty((0, 3))

    return (masken, alle_punkte) if gib_masken else alle_punkte


def entferne_ausreisser_punkte(punkte: np.ndarray, verbindungs_faktor: float = 15.0) -> np.ndarray:
    if len(punkte) < 2:
        return punkte
 
    baum = cKDTree(punkte)
    distanzen, _ = baum.query(punkte, k=2)
    typischer_abstand = np.median(distanzen[:, 1])
    max_nachbar_distanz = typischer_abstand * verbindungs_faktor
 
    paare = baum.query_pairs(r=max_nachbar_distanz, output_type='ndarray')
    n = len(punkte)
    daten = np.ones(len(paare))
    matrix = csr_matrix((daten, (paare[:, 0], paare[:, 1])), shape=(n, n))
    matrix = matrix + matrix.T
 
    anzahl, labels = connected_components(matrix, directed=False)
    groessen = np.bincount(labels)
    groesstes_label = np.argmax(groessen)
    return punkte[labels == groesstes_label]


def baue_geschlossenen_pfad(punkte: np.ndarray) -> np.ndarray:
    verbleibend = punkte.copy()
    besucht = [verbleibend[0]]
    verbleibend = np.delete(verbleibend, 0, axis=0)

    while len(verbleibend) > 0:
        letzter = besucht[-1]
        distanzen = np.linalg.norm(verbleibend - letzter, axis=1)
        naechster_index = np.argmin(distanzen)
        besucht.append(verbleibend[naechster_index])
        verbleibend = np.delete(verbleibend, naechster_index, axis=0)

    return np.array(besucht)
