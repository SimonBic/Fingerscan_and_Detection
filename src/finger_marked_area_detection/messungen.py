import numpy as np
import pyvista as p_v
from farberkennung import finde_markierungs_punkte 

def berechne_flaeche_und_umfang(flaeche: p_v.PolyData, punkte: np.ndarray) -> tuple[float, float]:
    flaecheninhalt = flaeche.area

    geschlossen = np.vstack([punkte, punkte[0]])
    umfang = np.linalg.norm(np.diff(geschlossen, axis=0), axis=1).sum()

    return flaecheninhalt, umfang
    
def volumen_ab_markierung(hand_mesh: p_v.PolyData, teile: list, hex_code: str, toleranz: float = 40.0):
    markierte_punkte = finde_markierungs_punkte(teile, hex_code, toleranz)
    if len(markierte_punkte) == 0:
        raise ValueError(f"Keine Markierung mit Farbe {hex_code} gefunden.")
 
    schnitt_hoehe = markierte_punkte[:, 2].mean()
    geschnitten = hand_mesh.clip(normal=(0, 0, 1), origin=(0, 0, schnitt_hoehe), invert=False)
 
    return geschnitten.volume, schnitt_hoehe, len(markierte_punkte)

def baue_pca_ebene(punkte: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    schwerpunkt = punkte.mean(axis=0)
    zentriert = punkte - schwerpunkt
    _, _, vt = np.linalg.svd(zentriert, full_matrices=False)
    normale = vt[2]
    if normale[2] < 0:
        normale = -normale
    return schwerpunkt, normale
 
 
def volumen_ab_ring(hand_mesh: p_v.PolyData, teile: list, hex_code: str, toleranz: float = 40.0):
    markierte_punkte = finde_markierungs_punkte(teile, hex_code, toleranz)
    if len(markierte_punkte) < 3:
        raise ValueError(f"Keine ausreichende Ring-Markierung mit Farbe {hex_code} gefunden.")
 
    schwerpunkt, normale = baue_pca_ebene(markierte_punkte)
    geschnitten = hand_mesh.clip(normal=normale, origin=schwerpunkt, invert=False)
 
    return geschnitten.volume, schwerpunkt, normale, len(markierte_punkte)

def volumen_ab_fingerzwischenfalte(hand_mesh: p_v.PolyData) -> float:
    bounds = hand_mesh.bounds
    if bounds[4] > 0 or bounds[5] < 0:
        raise ValueError(
            "Das Mesh scheint bei Z = 0 nicht die Fingerzwischenfalte zu haben"
            "ist das ein isolierter, final ausgerichteter Finger?"
        )
 
    geschnitten = hand_mesh.clip(normal=(0, 0, 1), origin=(0, 0, 0), invert=False)
    return geschnitten.volume
 