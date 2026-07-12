import pyvista as p_v
from pathlib import Path
import trimesh
import numpy as np
import load_scan
import vtk

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
 

def load_scan_as_pyvista(obj_pfad: str) -> p_v.PolyData:
    #Wird grade nicht verwendet, pyVista ist ein wenig buggy beim Laden mit jpgs
    
    tmesh = load_scan.load_whole_folder(obj_pfad.parent)

    if isinstance(tmesh, trimesh.Scene):
        tmesh = trimesh.util.concatenate(tmesh.dump())
    
    pv_mesh = p_v.wrap(tmesh, )

    if hasattr(tmesh.visual, "uv") and tmesh.visual.material.image is not None:
        texture = p_v.from_trimesh(tmesh.visual.material.image)

    return pv_mesh, texture


def make_surface_on_hand(points, hand_mesh):

    # geschlossene Kontur
    contour = np.vstack([points, points[0]])

    contour_mesh = p_v.PolyData(contour)

    # Fläche innerhalb der Kontur erzeugen
    surface = contour_mesh.delaunay_2d()

    # Punkte auf die Handoberfläche zurückprojizieren
    new_points = np.array([
    hand_mesh.points[hand_mesh.find_closest_point(p)] for p in surface.points])

    surface.points = new_points

    return surface

def get_hand_region(hand_mesh, circle_points):

    circle = np.vstack([
        circle_points,
        circle_points[0]
    ])

    vtk_points = vtk.vtkPoints()

    for point in circle:
        vtk_points.InsertNextPoint(point)

    selector = vtk.vtkSelectPolyData()

    selector.SetInputData(hand_mesh)
    selector.SetLoop(vtk_points)
    selector.GenerateSelectionScalarsOn()
    selector.Update()

    result = p_v.wrap(selector.GetOutput())

    return result["Selection"] < 0

def extract_faces_of_hand(hand_mesh, mask):

    faces = hand_mesh.faces.reshape(-1,4)

    neue_faces = []

    for face in faces:

        ids = face[1:]

        # Mindestens eine Ecke im vom Polygon in der Selection, wird dazu gepackt.
        if np.any(mask[ids]):
            neue_faces.append(ids)

    faces_array = np.array(neue_faces)

    vtk_faces = np.hstack([
        np.full((len(faces_array),1),3),
        faces_array
    ])

    return p_v.PolyData(
        hand_mesh.points,
        vtk_faces
    )

def draw_circle_on_scan(mesh):
    
    my_p_v_plotter = p_v.Plotter()

    hand_mesh = p_v.merge([teil for teil, textur in mesh])

    def line_done(scan):
        print(f"Fertig gemalt, du hast gesamt {scan.n_points} Punkte.")

        punkte = scan.points

        if len(punkte) < 3:
            return

        # Abstand zwischen letztem und erstem Punkt
        abstand = np.linalg.norm(punkte[0] - punkte[-1])

        # Schließen, wenn nah genug am Anfang geklickt wurde
        if abstand < 5:  # Wert an deine Scan-Größe anpassen
            geschlossene_punkte = np.vstack([punkte, punkte[0]])

            linien = np.arange(len(geschlossene_punkte))

            faces = np.hstack([
                [len(linien)],
                linien
            ])

            kontur = p_v.PolyData(
                geschlossene_punkte,
                faces=faces
            )

            # Fläche erzeugen
            mask = get_hand_region(hand_mesh,scan.points)

            flaeche = extract_faces_of_hand(hand_mesh, mask)
            #flaeche.save("markierung.obj")
            
            my_p_v_plotter.add_mesh(
                flaeche,
                color="red",
                opacity=1
            )

            print("Kreis geschlossen!")

    for teil, textur in mesh:
        my_p_v_plotter.add_mesh(teil, texture = textur, smooth_shading = True)

    my_p_v_plotter.enable_path_picking(
        callback = line_done,
        color = "blue",
        line_width = 5,
        show_path = True)

    my_p_v_plotter.show()


path_to_directory = Path(input("Pfad: "))
obj_files = list(path_to_directory.glob("*.obj"))

texture_teile = load_teilmeshe_mit_textur(obj_files)

draw_circle_on_scan(texture_teile)