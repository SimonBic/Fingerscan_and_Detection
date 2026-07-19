import pyvista as p_v
import numpy as np
from pathlib import Path
import trimesh

def load_teilmeshe_mit_textur(obj_pfad: str):
    geladen = trimesh.load(str(obj_pfad[0]), process=False)
 
    if isinstance(geladen, trimesh.Scene):
        teile = list(geladen.geometry.values())
    else:
        teile = [geladen]
 
    ergebnis = []
    for tmesh in teile:
        if tmesh.visual.uv is None:
            print(f"Teilmesh ohne UV-Koordinaten gefunden.")
            continue

        faces_vtk = np.hstack(
            [np.full((len(tmesh.faces), 1), 3), tmesh.faces]
        ).astype(np.int64)
 
        pv_mesh = p_v.PolyData(tmesh.vertices, faces_vtk)
        pv_mesh.active_texture_coordinates = tmesh.visual.uv
        pv_mesh = pv_mesh.compute_normals(point_normals=True, auto_orient_normals=True)
 
        bild_array = np.array(tmesh.visual.material.image.convert("RGB"))
        tex = p_v.Texture(bild_array)
 
        ergebnis.append((pv_mesh, tex))
 
    return ergebnis
 

def extract_ungefaehr_finger(mesh, seed_point, max_geodesic_dist=40):
    # nächster Vertex zum Klick
    seed_id = mesh.find_closest_point(seed_point)

    # Geodätische Distanz (entlang Oberfläche)
    dists = mesh.compute_geodesic_distance(seed_id)

    # Finger grob isolieren
    mask = dists < max_geodesic_dist

    return mask

def find_cut_position(mesh, mask, seed_point):
    points = mesh.points[mask]

    # PCA → Hauptachse des Fingers
    mean = points.mean(axis=0)
    centered = points - mean

    U, S, Vt = np.linalg.svd(centered)
    axis = Vt[0]  # Finger-Richtung

    # Projektion aller Punkte auf Achse
    t = np.dot(points - mean, axis)

    # entlang Achse samplen
    bins = np.linspace(t.min(), t.max(), 50)

    areas = []

    for i in range(len(bins)-1):
        slice_mask = (t >= bins[i]) & (t < bins[i+1])
        slice_pts = points[slice_mask]

        if len(slice_pts) < 10:
            areas.append(np.inf)
            continue

        # Fläche approximieren (Convex Hull)
        from scipy.spatial import ConvexHull
        try:
            hull = ConvexHull(slice_pts[:, :2])
            areas.append(hull.area)
        except:
            areas.append(np.inf)

    cut_idx = np.argmin(areas)
    cut_value = (bins[cut_idx] + bins[cut_idx+1]) / 2

    return axis, mean, cut_value

def cut_finger(mesh, axis, origin, cut_value):
    # Punkt auf Schnittebene
    plane_origin = origin + axis * cut_value

    # Ebene
    clipped = mesh.clip(
        origin=plane_origin,
        normal=axis,
        invert=False  # je nach Richtung evtl. True
    )

    return clipped

def extract_finger(mesh, seed_point):
    #entrpciht der main Funktion, bzw die ganze pipelien
    mask = extract_ungefaehr_finger(mesh, seed_point)

    axis, origin, cut_value = find_cut_position(mesh, mask, seed_point)

    finger = cut_finger(mesh, axis, origin, cut_value)

    return finger

def pick_finger_point(plotter, mesh):
    punkte = []
    print("Bitte Wählen Sie den Fingernagel des verlezten Fingers")

    def callback(point, picker):
        punkte.append(np.array(point))
        print(f"Punkt {len(punkte)} gewaehlt bei: {point}")

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


def rotationsmatrix_zu_z_achse(richtung: np.ndarray) -> np.ndarray:
    # Baut eine Rotationsmatrix, die 'richtung' exakt auf die
    # Welt-Z-Achse [0,0,1] dreht (Rodrigues-Rotationsformel).

    #normalisieren
    richtung = richtung / np.linalg.norm(richtung)
    ziel = np.array([0, 0, 1.0])
    

    rotationsachse = np.cross(richtung, ziel)
    sin_winkel = np.linalg.norm(rotationsachse)
    cos_winkel = np.dot(richtung, ziel)
    
    #Fehlerbehandlung, falls ziel und richtung fast gleich sind bzw paralell
    if sin_winkel < 1e-8:
        if cos_winkel > 0:
            #falls es schon passt
            return np.eye(3)
        #falls basically falschrum, dann ist die Rotationsachse ja wurscht
        beliebige_achse = np.array([1.0, 0, 0]) if abs(richtung[0]) < 0.9 else np.array([0, 1.0, 0])
        achse = np.cross(richtung, beliebige_achse)
        achse /= np.linalg.norm(achse)
        K = np.array([[0, -achse[2], achse[1]], [achse[2], 0, -achse[0]], [-achse[1], achse[0], 0]])
        return np.eye(3) + 2 * K @ K  # 180-Grad-Rotation
 
    #normalfall: normieren
    achse = rotationsachse / sin_winkel
    #Rodrigues Formel:
    K = np.array([[0, -achse[2], achse[1]], [achse[2], 0, -achse[0]], [-achse[1], achse[0], 0]])
    return np.eye(3) + K * sin_winkel + K @ K * (1 - cos_winkel)

def richte_hand_aus(mesh: trimesh.Trimesh, seed: np.ndarray, second_finger: np.ndarray):
    
    mitte = (seed + second_finger) / 2
    hoch_richtung = mitte - mesh.centroid
    hoch_richtung = hoch_richtung / np.linalg.norm(hoch_richtung)
    
    #hoch_richtung entspricht jetzt der Vektor vom Mesh Centroid zum mittelpunkt der beiden Fingerspitzen
    R = rotationsmatrix_zu_z_achse(hoch_richtung)
 
    #trimesh will wieder eine 4 * mal 4 Matrix, tranformierungsmatrix wird einfach oben links abgelegt, rest bleibt Einheitsmatrix
    transform = np.eye(4)
    transform[:3, :3] = R
    transform[:3, 3] = -R @ mesh.centroid
 
    #Drehmatrix wird angewendet
    ausgerichtetes_mesh = mesh.copy()
    ausgerichtetes_mesh.apply_transform(transform)
 
    #Drehmatrix auch auf die Fingerpunkte, dass diese wieder passen
    hurt_finger_neu = R @ (seed - mesh.centroid)
    second_finger_neu = R @ (second_finger - mesh.centroid)
 
    return ausgerichtetes_mesh, hurt_finger_neu, second_finger_neu


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

    #von pyvista mesh tu trimesh mesh (pyvista hat nicht alle Funktionen, dass die Hand gscheid ausgerichtet werden kann)
    faces = hand_mesh.faces.reshape(-1, 4)[:, 1:]
    hand_mesh_trimesh =  trimesh.Trimesh(vertices = hand_mesh.points, faces=faces, process=False)
    #Handausrichten
    hand_ausgerichtet, hurt_finger, second_finger = richte_hand_aus(hand_mesh_trimesh, hurt_finger, second_finger)
    achsen = trimesh.creation.axis(origin_size = 0.02, axis_length = 20)
    achsen.apply_scale(6.0) 
    szene = trimesh.Scene([hand_ausgerichtet, achsen]) 
    szene.show()
    #Djikstra
    #tiefster Punkt
    #normale
    #Cutten

    finger = None
    my_finger_shower = p_v.Plotter()
    my_finger_shower.add_mesh(finger, color = "blue")
    my_finger_shower.show()

    #Finger speichern


path_string = input("Pfad eingeben:")
isolate_finger(path_string)



#finger = extract_finger(hand_mesh, seed)






