import pyvista as p_v
from pathlib import Path
import trimesh
import numpy as np

def load_scan_as_pyvista(obj_pfad: str) -> p_v.PolyData:
    
    tmesh = trimesh.load(str(obj_pfad), process=False, force="mesh")
 
    if isinstance(tmesh.visual, trimesh.visual.texture.TextureVisuals):
        tmesh.visual = tmesh.visual.to_color()
 
    faces_vtk = np.hstack(
        [np.full((len(tmesh.faces), 1), 3), tmesh.faces]
    ).astype(np.int64)
 
    pv_mesh = p_v.PolyData(tmesh.vertices, faces_vtk)
    pv_mesh.point_data["RGBA"] = tmesh.visual.vertex_colors
    pv_mesh = pv_mesh.compute_normals(point_normals=True, auto_orient_normals=True)
 
    return pv_mesh

def line_done(scan):
    print(f"Fertig gemalt, du hast {scan.n_points} gezeichnet.")

def draw_circle_on_scan(mesh):
    
    my_p_v_plotter = p_v.Plotter()
    my_p_v_plotter.add_mesh(mesh, scalars = "RGBA", rgba = True)

    my_p_v_plotter.enable_path_picking(
        callback = line_done,
        color = "blue",
        line_width = 5,
        show_path = True)

    my_p_v_plotter.show()


path_to_directory = Path(input("Pfad: "))
obj_files = list(path_to_directory.glob("*.obj"))
mesh = load_scan_as_pyvista(obj_files[0])

draw_circle_on_scan(mesh)