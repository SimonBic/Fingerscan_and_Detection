from pathlib import Path
import numpy as np
import trimesh
import pyvista as p_v
import matplotlib.pyplot as plt
from PIL import Image
from scipy.spatial import cKDTree
import re

from draw_area_on_scan import (
    lese_markierungsfarbe, 
    extract_faces_of_hand, 
    HEATMAPFARBEN)

FARB_REIHENFOLGE = ["rot", "orange", "gelb", "grün", "blau"]
FARB_PRIORITAET = {HEATMAPFARBEN[name]: index for index, name in enumerate(FARB_REIHENFOLGE)}


def farb_prioritaet(farbe_rgb: tuple) -> int:
    return FARB_PRIORITAET.get(farbe_rgb, -1)


def finde_nagel_normale(mesh: p_v.PolyData, geklickter_punkt: np.ndarray, k: int = 400) -> np.ndarray:
    #PCA auf die lokale Nachbarschaft um den geklickten Fingernagel-
    #Punkt - gibt die lokale Oberflaechen-Normale zurueck (Richtung
    #der KLEINSTEN Streuung, da eine Nagel-Oberflaeche lokal recht
    
    baum = cKDTree(mesh.points)
    _, indices = baum.query(geklickter_punkt, k=k)
    nahe_punkte = mesh.points[indices]
    zentriert = nahe_punkte - nahe_punkte.mean(axis=0)
    kovarianz = np.cov(zentriert.T)
    eigenwerte, eigenvektoren = np.linalg.eigh(kovarianz)
    normale = eigenvektoren[:, np.argmin(eigenwerte)]
 
    fusspunkt_auf_achse = np.array([0, 0, geklickter_punkt[2]])
    nach_aussen = geklickter_punkt - fusspunkt_auf_achse
    if np.dot(normale, nach_aussen) < 0:
        normale = -normale
    return normale


def rotationsmatrix_um_z_fuer_nagel_ausrichtung(normale: np.ndarray) -> np.ndarray:
    # Rotationsmatrix um die Z-Achse, die die (XY-Projektion der)
    # Nagel-Normale exakt auf die positive Y-Achse dreht

    winkel_aktuell = np.arctan2(normale[1], normale[0])
    winkel_korrektur = np.pi / 2 - winkel_aktuell
    c, s = np.cos(winkel_korrektur), np.sin(winkel_korrektur)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def isolierte_scan_name_aus_markierung(markierungs_ordner_name: str) -> str:
    #Leitet aus zb 'U1_isoliert_marked' den zugehoerigen isolierte_scans-Ordnernamen 'U1_isoliert' ab
    return re.sub(r"_marked(_\d+)?$", "", markierungs_ordner_name)


def lade_markierung(obj_pfad: Path) -> np.ndarray:
    geladen = trimesh.load(str(obj_pfad), process=False, split_objects=True)

    if isinstance(geladen, trimesh.Scene):
        alle_punkte = [
            geom.vertices for name, geom in geladen.geometry.items()
            if not name.startswith("landmark_")
        ]
        if not alle_punkte:
            raise ValueError(f"{obj_pfad} enthaelt keine Flaechen-Geometrie.")
        return np.vstack(alle_punkte)

    return geladen.vertices


def finde_markierte_scans(patienten_ordner: Path) -> list:
    markierte_scans_ordner = patienten_ordner / "markierte_scans"
    if not markierte_scans_ordner.is_dir():
        return []
    return sorted(markierte_scans_ordner.glob("*/*.obj"))



def baue_farbgruppen_aus_gewinner(aktueller_scan_mesh: p_v.PolyData, gewinner_pro_vertex: dict) -> list:
    punkte_pro_farbe = {}
    for vertex_index, farbe_rgb in gewinner_pro_vertex.items():
        punkte_pro_farbe.setdefault(farbe_rgb, []).append(aktueller_scan_mesh.points[vertex_index])
 
    return [(np.array(punkte), farbe) for farbe, punkte in punkte_pro_farbe.items()]


def baue_3d_genesungsverlauf(aktueller_scan_mesh: p_v.PolyData, path: str) -> list:
    scan_ordner = Path(path)
    patienten_ordner = scan_ordner.parent.parent
 
    gewinner_pro_vertex = {}
    for obj_pfad in finde_markierte_scans(patienten_ordner):
        try:
            punkte = lade_markierung(obj_pfad)
            farbe_rgb = lese_markierungsfarbe(obj_pfad)
        except ValueError as e:
            print(f"Ueberspringe {obj_pfad.name}: {e}")
            continue
 
        for p in punkte:
            vertex_index = aktueller_scan_mesh.find_closest_point(p)
            # 'finde_markierte_scans' liefert die Dateien sortiert
            # (chronologisch, da U1/U2/... alphabetisch gleich sortiert) -
            # ein spaeterer Eintrag ueberschreibt hier also IMMER einen
            # frueheren fuer denselben Vertex
            gewinner_pro_vertex[vertex_index] = farbe_rgb
 
    punkte_pro_farbe = {}
    for vertex_index, farbe_rgb in gewinner_pro_vertex.items():
        punkte_pro_farbe.setdefault(farbe_rgb, []).append(aktueller_scan_mesh.points[vertex_index])
 
    return [(np.array(punkte), farbe) for farbe, punkte in punkte_pro_farbe.items()]
 
 
def speichere_genesungsverlauf(aktueller_scan_mesh: p_v.PolyData, aktuelle_teile: list, gewinner_pro_vertex: dict, path: str) -> Path:
    scan_ordner = Path(path)
    patienten_ordner = scan_ordner.parent.parent
 
    farben_gruppen = {}
    for vertex_index, farbe in gewinner_pro_vertex.items():
        farben_gruppen.setdefault(farbe, []).append(vertex_index)
 
    geometrien = {}
 
    # Pro Farbe eine eigene, eingefaerbte Flaeche bauen
    for i, (farbe, indices) in enumerate(farben_gruppen.items()):
        maske = np.zeros(aktueller_scan_mesh.n_points, dtype=bool)
        maske[indices] = True
        flaeche = extract_faces_of_hand(aktueller_scan_mesh, maske)
        if flaeche.n_points == 0:
            continue
 
        faces = flaeche.faces.reshape(-1, 4)[:, 1:]
        tmesh = trimesh.Trimesh(vertices=flaeche.points, faces=faces, process=False)
        tmesh.remove_unreferenced_vertices()
 
        farb_bild = Image.new("RGB", (64, 64), farbe)
        uv = np.full((len(tmesh.vertices), 2), 0.5)
        tmesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=farb_bild)
        geometrien[f"genesungsverlauf_{i}"] = tmesh
 
    # Original-Scan-Teile MIT ihrer echten Textur dazupacken
    for i, (pv_mesh, tex) in enumerate(aktuelle_teile):
        faces = pv_mesh.faces.reshape(-1, 4)[:, 1:]
        tmesh = trimesh.Trimesh(vertices=pv_mesh.points, faces=faces, process=False)
        uv = pv_mesh.active_texture_coordinates
        bild = Image.fromarray(tex.to_array())
        tmesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=bild)
        geometrien[f"scan_teil_{i}"] = tmesh
 
    scene = trimesh.Scene(geometrien)
 
    save_name = scan_ordner.name + "_genesungsverlauf"
    ziel_ordner = patienten_ordner / "genesungsverlauf" / save_name
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    save_path = ziel_ordner / f"{save_name}.obj"
    scene.export(str(save_path))
 
    print(f"Genesungsverlauf gespeichert unter: {save_path}")
    return save_path
 
 