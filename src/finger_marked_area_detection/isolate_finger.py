import pyvista as p_v
import numpy as np
from pathlib import Path
import trimesh
from scipy.spatial import cKDTree

def load_teilmeshe_mit_textur(obj_pfad: str):
    geladen = trimesh.load(str(obj_pfad[0]), process=False)
 
    if isinstance(geladen, trimesh.Scene):
        teile = list(geladen.geometry.values())
    else:
        teile = [geladen]
 
    count_vertices = 0
    ergebnis = []
    for tmesh in teile:
        if tmesh.visual.uv is None:
            print(f"Teilmesh ohne UV-Koordinaten gefunden.")
            continue

        faces_vtk = np.hstack(
            [np.full((len(tmesh.faces), 1), 3), tmesh.faces]
        ).astype(np.int64)

        count_vertices += len(tmesh.vertices)
        pv_mesh = p_v.PolyData(tmesh.vertices, faces_vtk)
        pv_mesh.active_texture_coordinates = tmesh.visual.uv
        pv_mesh = pv_mesh.compute_normals(point_normals=True, auto_orient_normals=True)
 
        bild_array = np.array(tmesh.visual.material.image.convert("RGB"))
        tex = p_v.Texture(bild_array)
 
        ergebnis.append((pv_mesh, tex))
 
    print(f"Erfolgreich geladen, {count_vertices} Vertices gesamt.")
    return ergebnis
 

def pick_finger_point(plotter, mesh):
    punkte = []
    print("Bitte Wählen Sie den Fingernagel des verlezten Fingers")

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
 
    return ausgerichtetes_mesh, seed_neu, second_finger_neu

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


def finger_normale(mesh: p_v.PolyData, verletzter_finger: np.ndarray, anzahl_punkte: int = 2000) -> np.ndarray:

    if anzahl_punkte > mesh.n_points:
        raise ValueError(
            f"anzahl_punkte ({anzahl_punkte}) ist größer als die Gesamtzahl "
            f"der Vertices im Mesh ({mesh.n_points})."
        )
 
    baum = cKDTree(mesh.points)
    _, indices = baum.query(verletzter_finger, k = anzahl_punkte)
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
 
    return normale, nahe_punkte


def isolate_finger(path: str):
    path = Path(path)
    obj_file = list(path.glob("*.obj"))

    texture_teile = load_teilmeshe_mit_textur(obj_file)
    hand_mesh = p_v.merge([teil for teil, tex in texture_teile])

    my_p_v_plotter = p_v.Plotter()
    my_p_v_plotter.add_mesh(hand_mesh, color="lightgray")

    hurt_finger, second_finger = pick_finger_point(my_p_v_plotter, hand_mesh)
    if (hurt_finger is None) or (second_finger is None):
        raise ValueError("Ungenügend Fingerspitzen gewählt")
    
    print("Finger korrekt gewählt.")
    print(f"Koordinaten des verlzten Fingers: {hurt_finger}")
    print(f"Finger des benachbarten Fingers: {second_finger}")

    
    #Handausrichten
    hand_ausgerichtet, hurt_finger, second_finger = richte_hand_aus(hand_mesh, hurt_finger, second_finger)
    #Hand zeigen (für Testzwecke)
    plotter_ausgerichtete_hand = p_v.Plotter()
    achsen_actor = plotter_ausgerichtete_hand.add_axes_at_origin(x_color="red", y_color="green", z_color="blue")
    achsen_actor.SetTotalLength(300, 300, 300)
    plotter_ausgerichtete_hand.add_mesh(hand_ausgerichtet, color = "light_gray")
    plotter_ausgerichtete_hand.show()
    
    #Djikstra & gleichzeitig tiefster Punkt
    tiefster_punkt, pfad_mesh, kugel = djikstra_und_tiefster_punkt(hand_ausgerichtet, hurt_finger, second_finger)
    #Handzeigen (für Testzwecke wieder):
    djikstra_plotter = p_v.Plotter()
    djikstra_plotter.add_mesh(hand_ausgerichtet, color = "light_gray")
    djikstra_plotter.add_mesh(pfad_mesh, color="yellow", line_width=20)   # der Pfad selbst
    djikstra_plotter.add_mesh(kugel, color="red")  
    djikstra_plotter.show()
   
    #Normale mit PCA (Principal Comonent Analysis bestimmen)
    normale, verwendete_vertices = finger_normale(hand_ausgerichtet, hurt_finger)
    #Hand wieder zeigen zum debuggen:
    normalen_plotter = p_v.Plotter()
    normalen_plotter.add_mesh(hand_ausgerichtet, color="lightgray")
    normalen_plotter.add_points(verwendete_vertices, color="orange", point_size=6)
    pfeil_normale = p_v.Arrow(start=hurt_finger, direction=normale, scale=50)  # scale = Laenge in mm, anpassen
    normalen_plotter.add_mesh(pfeil_normale, color="red")
    normalen_plotter.show()

    #Rotationsellipsoid bestimmen

    #Cutten

    #Finger speichern


path_string = input("Pfad eingeben:")
isolate_finger(path_string)



#finger = extract_finger(hand_mesh, seed)






