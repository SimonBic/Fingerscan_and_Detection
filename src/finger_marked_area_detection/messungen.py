import numpy as np
import pyvista as p_v
import vtk
from farberkennung import finde_markierungs_punkte 

def berechne_flaeche_und_umfang(flaeche: p_v.PolyData, punkte: np.ndarray) -> tuple[float, float]:
    flaecheninhalt = flaeche.area

    geschlossen = np.vstack([punkte, punkte[0]])
    umfang = np.linalg.norm(np.diff(geschlossen, axis=0), axis=1).sum()

    return flaecheninhalt, umfang

def schneide_und_deckle(mesh: p_v.PolyData, normal: np.ndarray, origin: np.ndarray) -> p_v.PolyData:
    #Schneidet und deckelt, da sonst .volume eine falsche Ebene bei der Volumenberechnug von einem nicht wasserdichten 
    #Objekt berechnet

    ebene = vtk.vtkPlane()
    ebene.SetNormal(*normal)
    ebene.SetOrigin(*origin)
 
    ebenen_sammlung = vtk.vtkPlaneCollection()
    ebenen_sammlung.AddItem(ebene)
 
    clipper = vtk.vtkClipClosedSurface()
    clipper.SetInputData(mesh)
    clipper.SetClippingPlanes(ebenen_sammlung)
    clipper.SetGenerateFaces(True)
    clipper.Update()
 
    return p_v.wrap(clipper.GetOutput())

def volumen_ab_markierung(hand_mesh: p_v.PolyData, teile: list, hex_code: str, toleranz: float = 40.0):
    markierte_punkte = finde_markierungs_punkte(teile, hex_code, toleranz)
    if len(markierte_punkte) == 0:
        raise ValueError(f"Keine Markierung mit Farbe {hex_code} gefunden.")
 
    schnitt_hoehe = markierte_punkte[:, 2].mean()
    geschnitten = schneide_und_deckle(hand_mesh, normal=(0, 0, 1), origin=(0, 0, schnitt_hoehe))
 
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
    geschnitten = schneide_und_deckle(hand_mesh, normal=normale, origin=schwerpunkt)
 
    return geschnitten.volume, schwerpunkt, normale, len(markierte_punkte)

def volumen_ab_fingerzwischenfalte(hand_mesh: p_v.PolyData) -> float:
    bounds = hand_mesh.bounds
    if bounds[4] > 0 or bounds[5] < 0:
        raise ValueError(
            "Das Mesh scheint bei Z = 0 nicht die Fingerzwischenfalte zu haben"
            "ist das ein isolierter, final ausgerichteter Finger?"
        )
 
    geschnitten = schneide_und_deckle(hand_mesh, normal=(0, 0, 1), origin=(0, 0, 0))
    return geschnitten.volume


def schliesse_offenes_ende(mesh: p_v.PolyData) -> p_v.PolyData:
    """Findet den (einzigen) offenen Rand eines Meshes - z.B. dort,
    wo der Finger von der Hand abgetrennt wurde - legt eine Ebene
    hindurch (PCA) und verschliesst ihn mit einem faecherfoermigen
    Deckel. Ist das Mesh bereits geschlossen, wird es unveraendert
    zurueckgegeben.
 
    Anders als schneide_und_deckle() wird hier NICHTS Neues
    abgeschnitten - nur ein BEREITS bestehendes Loch verschlossen."""
    #Erkennt alle punkte am Rand des Schnittes
    #und legt eine Ebene mit PCA rein
    rand = mesh.extract_feature_edges(
        boundary_edges=True, feature_edges=False, non_manifold_edges=False, manifold_edges=False
    )
    if rand.n_points == 0:
        return mesh
 
    rand_punkte = np.unique(rand.points, axis=0)
    schwerpunkt, normale = baue_pca_ebene(rand_punkte)
 
    referenz = rand_punkte[0] - schwerpunkt
    referenz = referenz - np.dot(referenz, normale) * normale
    referenz = referenz / np.linalg.norm(referenz)
    quer = np.cross(normale, referenz)
 
    relativ = rand_punkte - schwerpunkt
    winkel = np.arctan2(relativ @ quer, relativ @ referenz)
    geordnete_punkte = rand_punkte[np.argsort(winkel)]
 
    # Ausrichtungs-Pruefung: Deckel-Normale soll vom Mesh-Schwerpunkt
    # weg zeigen (nach aussen), sonst wuerde die Volumen-Formel durch
    # die falsch orientierten Deckel-Dreiecke verfaelscht
    mesh_schwerpunkt = mesh.points.mean(axis=0)
    nach_aussen_erwartet = schwerpunkt - mesh_schwerpunkt
    test_normale = np.cross(geordnete_punkte[1] - geordnete_punkte[0], geordnete_punkte[2] - geordnete_punkte[0])
    if np.dot(test_normale, nach_aussen_erwartet) < 0:
        geordnete_punkte = geordnete_punkte[::-1]
 
    deckel_punkte = np.vstack([geordnete_punkte, schwerpunkt])
    n = len(geordnete_punkte)
    deckel_faces = []
    for i in range(n):
        deckel_faces += [3, i, (i + 1) % n, n]
    deckel = p_v.PolyData(deckel_punkte, np.array(deckel_faces))
 
    return mesh.merge(deckel).triangulate()
 
 
def volumen_gesamtes_mesh(hand_mesh: p_v.PolyData) -> float:
    geschlossen = schliesse_offenes_ende(hand_mesh)
    return geschlossen.volume