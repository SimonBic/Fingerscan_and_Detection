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