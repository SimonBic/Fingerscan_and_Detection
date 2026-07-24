import pyvista as p_v
from pathlib import Path
import trimesh
import numpy as np
#import finger_marked_area_detection.prototyp.load_scan as load_scan
import vtk
from PIL import Image 
import heatmap

HEATMAPFARBEN = {
    "rot" : (220, 20, 20),
    "orange" : (255, 140, 0),
    "gelb" : (240, 220, 0),
    "grün" : (30, 180, 30),
}

LANDMARK_NAMEN = {
    "1" : "linke_rille",
    "2" : "fingerspitze",
    "3" : "rechte_rille"
}

LANDMARK_FARBE = (30, 30, 220) #blau
LANDMARK_RADIUS = 2


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
 

def p_v_flaeche_zu_farbigem_obj(flaeche, farbe_rgb, landmarken, save_path):
    # VTK-Face-Format [3, i0,i1,i2, 3, i0,i1,i2, ...] -> (n,3) fuer trimesh
    faces = flaeche.faces.reshape(-1, 4)[:, 1:]
    tmesh = trimesh.Trimesh(vertices=flaeche.points, faces=faces, process=False)
    tmesh.remove_unreferenced_vertices() 

    farb_bild = Image.new("RGB", (64, 64), farbe_rgb)
 
    uv = np.full((len(tmesh.vertices), 2), 0.5)
 
    tmesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=farb_bild)

    geometrien = {"markierung": tmesh}
    geometrien.update(landmarken_als_kugeln(landmarken))   

    scene = trimesh.Scene(geometrien)                       
    scene.export(str(save_path))



def save_drawn_area(area, original_folder, farbenname, landmarken):
    if farbenname not in HEATMAPFARBEN:
        raise ValueError(f"Bitte korrekte Heatmapfarbe wählen: (rot, orange, gelb, grün)") 

    farbe = HEATMAPFARBEN[farbenname]

    output_ordner = original_folder.parent / "Markierungen"

    output_ordner.mkdir(exist_ok = True)

    save_name = original_folder.name
    save_path = output_ordner / (save_name + "_marked.obj")

    zaehler = 1
    while save_path.exists():
        save_path = output_ordner / f"{save_name}_marked_{zaehler}.obj"
        zaehler += 1

    p_v_flaeche_zu_farbigem_obj(area, farbe, landmarken, save_path)
    
    print(f"Erfolgreich gespeichert unter dem Pfad: {save_path}")

    return save_path.parent


def landmarken_picking_einrichten(plotter: p_v.Plotter, pfad_zeichnen_neu_starten):
    # Registriert die Tasten 1/2/3 fuer Landmarken-Picking auf dem
    # uebergebenen Plotter. 'pfad_zeichnen_neu_starten' ist eine
    # Funktion ohne Argumente, die enable_path_picking() erneut
    # aufruft (um nach dem Landmark-Setzen wiederr ins normale
    # Zeichnen zurueckzuschalten).
 
    # Gibt ein dict {name: 3d_punkt oder None} zurueck, das waehrend
    # der Sitzung befuellt wird.

    landmarken = {name: None for name in LANDMARK_NAMEN.values()} #Erstmal das leere dict aufstzen
 
    def landmark_setzen(name):
        def callback(point, picker):
            landmarken[name] = np.array(point)
            print(f"Landmark '{name}' gesetzt: {point.round(1)}")
 
            # nur EIN Klick fuer diesen Landmark - danach Picking
            # wieder deaktivieren und zurueck zum normalen Zeichnen
            plotter.disable_picking()
            pfad_zeichnen_neu_starten()
 
        return callback
 
    def taste_gedrueckt(name):
        def taste_callback():
            print(f"Landmark-Modus: naechster Linksklick setzt '{name}'")
            plotter.disable_picking()  # Pfad-Zeichnen kurz pausieren
            plotter.enable_point_picking(
                callback=landmark_setzen(name),
                left_clicking=True,
                use_picker=True,
                show_message=False,
                show_point=True,
                point_size=12,
                color="blue",
            )
        return taste_callback
 
    for taste, name in LANDMARK_NAMEN.items():
        plotter.add_key_event(taste, taste_gedrueckt(name))
 
    return landmarken


def landmarken_als_kugeln(landmarken: dict) -> dict:
    """Baut fuer jeden gesetzten Landmark eine kleine, einheitlich
    gefaerbte Kugel-Geometrie (trimesh), fuer den gemeinsamen Export
    mit der Markierungs-Flaeche."""
    bild = Image.new("RGB", (8, 8), LANDMARK_FARBE)
 
    kugeln = {}
    for name, position in landmarken.items():
        if position is None:
            continue
        kugel = trimesh.creation.icosphere(radius=LANDMARK_RADIUS, subdivisions=1)
        kugel.apply_translation(position)
        kugel.visual = trimesh.visual.texture.TextureVisuals(
            uv=np.full((len(kugel.vertices), 2), 0.5), image=bild
        )
        kugeln[f"landmark_{name}"] = kugel
 
    return kugeln


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
    drawn_flaeche = {"flaeche": None}

    my_p_v_plotter = p_v.Plotter()

    hand_mesh = p_v.merge([teil for teil, textur in mesh])

    def line_done(scan):
        print(f"Fertig gemalt, du hast gesamt {scan.n_points} Punkte.")

        punkte = scan.points

        if len(punkte) < 3:
            return

        abstand = np.linalg.norm(punkte[0] - punkte[-1])

        if abstand < 5:
            geschlossene_punkte = np.vstack([punkte, punkte[0]])
            linien = np.arange(len(geschlossene_punkte))
            faces = np.hstack([[len(linien)], linien])

            mask = get_hand_region(hand_mesh, scan.points)
            flaeche = extract_faces_of_hand(hand_mesh, mask)
            drawn_flaeche["flaeche"] = flaeche

            my_p_v_plotter.add_mesh(flaeche, color="red", opacity=1)
            print("Kreis geschlossen!")

    
    def path_picking_starten():
        my_p_v_plotter.enable_path_picking(
            callback=line_done,
            color="blue",
            line_width=5,
            show_path=True)

    for teil, textur in mesh:
        my_p_v_plotter.add_mesh(teil, texture=textur, smooth_shading=True)

    # NEU: Landmarken-Picking einrichten (Tasten 1/2/3)
    landmarken = landmarken_picking_einrichten(my_p_v_plotter, path_picking_starten)

    path_picking_starten()

    my_p_v_plotter.show()

    return drawn_flaeche["flaeche"], landmarken

    

def draw_main(path_to_directory: str):
    path_to_directory = Path(path_to_directory)
    obj_files = list(path_to_directory.glob("*.obj"))

    texture_teile = load_teilmeshe_mit_textur(obj_files)

    drawn_flaeche, landmarken = draw_circle_on_scan(texture_teile)

    if drawn_flaeche is not None:
        speichern_frage = input("Markierung speichern? (y / n)")
        farben_frage = input("Welche Fabre soll für die Heatmap gewählt werden? (rot / orange / gelb / grün)")
        if speichern_frage == "y":
            path_marked_area = save_drawn_area(drawn_flaeche, path_to_directory, farben_frage, landmarken)
        # heatmap_frage = input("zu 2D transformieren? (y / n)")
        # if heatmap_frage == "y":
    #     heatmap2D_to_3D(drawn_flaeche, landmarken, path_marked_area)