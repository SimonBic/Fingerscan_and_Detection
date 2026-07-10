import pyvista as p_v
from pathlib import Path
import trimesh
import numpy as np
import load_scan

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

def draw_circle_on_scan(mesh):
    
    my_p_v_plotter = p_v.Plotter()

    def line_done(scan):
        print(f"Fertig gemalt, du hast {scan.n_points} gezeichnet.")

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