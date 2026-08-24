import colorsys
import numpy as np
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix

def erzeuge_farbpalette(anzahl = 81):
    farben = []
    for i in range(anzahl):
        h = i / anzahl
        s = 0.85 if i % 2 == 0 else 0.55
        v = 0.9 if i % 3 != 0 else 0.65
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        farben.append('#{:02X}{:02X}{:02X}'.format(int(r*255), int(g*255), int(b*255)))
    return farben


def finde_markierungs_punkte(teile: list, hex_code: str, toleranz: float = 40.0) -> np.ndarray:
    ziel_rgb = np.array([int(hex_code.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)])

    alle_markierten_punkte = []
    for pv_mesh, tex in teile:
        if pv_mesh.active_texture_coordinates is None:
            continue
        uv = pv_mesh.active_texture_coordinates
        bild_array = tex.to_array()
        hoehe, breite = bild_array.shape[:2]

        x_pixel = np.clip((uv[:, 0] * (breite - 1)).astype(int), 0, breite - 1)
        y_pixel = np.clip(((1 - uv[:, 1]) * (hoehe - 1)).astype(int), 0, hoehe - 1)

        vertex_farben = bild_array[y_pixel, x_pixel]
        distanzen = np.linalg.norm(vertex_farben.astype(float) - ziel_rgb, axis=1)
        maske = distanzen < toleranz

        if maske.any():
            alle_markierten_punkte.append(pv_mesh.points[maske])

    if not alle_markierten_punkte:
        return np.empty((0, 3))
    return np.vstack(alle_markierten_punkte)


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

def _baue_nachbarschafts_matrix(mesh):
    faces = mesh.faces.reshape(-1, 4)[:, 1:]
    kanten_liste = []
    for f in faces:
        kanten_liste += [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])]
    kanten_arr = np.array(kanten_liste)
    n = mesh.n_points
    daten = np.ones(len(kanten_arr))
    matrix = csr_matrix((daten, (kanten_arr[:, 0], kanten_arr[:, 1])), shape=(n, n))
    return matrix + matrix.T
 
 
def schliesse_maske(mesh, maske: np.ndarray, schritte: int = 2) -> np.ndarray:
    #entfernt kleine trails, also Linien aus kleinen, erkannten Flächen, damit am Ende nur noch eine existiert
    #mit Dilation und Closing, alte Technik
    nachbar_matrix = _baue_nachbarschafts_matrix(mesh)
 
    aktuelle = maske.copy()
    for _ in range(schritte):
        aktuelle = aktuelle | (nachbar_matrix.dot(aktuelle.astype(int)) > 0)
 
    grad = np.array(nachbar_matrix.sum(axis=1)).flatten()
    for _ in range(schritte):
        nachbarn_markiert = nachbar_matrix.dot(aktuelle.astype(int))
        aktuelle = aktuelle & (nachbarn_markiert >= grad)
 
    return aktuelle
 