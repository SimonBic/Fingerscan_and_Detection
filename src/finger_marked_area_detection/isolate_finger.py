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
    picked = {"point": None}

    def callback(point, picker):
        picked["point"] = np.array(point)
        print("Finger gewählt bei:", point)

    plotter.enable_point_picking(
        callback=callback,
        use_picker=True,
        show_point=True,
        color="red",
        point_size=15
    )

    plotter.show()

    return picked["point"]


path_string = input("Pfad eingeben:")
path = Path(path_string)
obj_file = list(path.glob("*.obj"))
texture_teile = load_teilmeshe_mit_textur(obj_file)
hand_mesh = p_v.merge([teil for teil, tex in texture_teile])

my_p_v_plotter = p_v.Plotter()
my_p_v_plotter.add_mesh(hand_mesh, color="lightgray")

seed = pick_finger_point(my_p_v_plotter, hand_mesh)
if seed is None:
    raise ValueError("Kein Punkt gewählt!")

finger = extract_finger(hand_mesh, seed)

my_finger_shower = p_v.Plotter()
my_finger_shower.add_mesh(finger, color = "blue")
my_finger_shower.show()



