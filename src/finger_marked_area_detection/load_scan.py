from pathlib import Path
import trimesh

def load_whole_folder(folder_path: str) -> trimesh.Trimesh:
    if not Path(folder_path).is_dir():
        raise NotADirectoryError(f"Ordner nicht gefunden{folder}, bitte den Pfad uberpruefen")
    
    folder = Path(folder_path)

    obj_files_list = list(folder.glob("*.obj"))
    mtl_files_list = list(folder.glob("*.mtl"))
    textur_files_list = list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")) + list(folder.glob("*.png"))
    
    if not obj_files_list:
        raise FileNotFoundError(f"Im Ordner {folder} wurde keine .obj file gefunden.")
    
    if len(obj_files_list) > 1:
        raise ValueError(f"Im Ordner sind mehr als eine .obj file, soll exakt eine existieren")
    
    if len(mtl_files_list) == 0:
        raise ValueError(f"Es wurden keine noetigen .mtl files gefunden.")
    
    if len(textur_files_list) == 0:
        raise ValueError(f"Es wurden keine Textur-files (.jpg, .jpeg, .png) gefunden.")

    obj_file = obj_files_list[0]

    handscan_mesh = trimesh.load(obj_file, process = False, force = "mesh")

    if not isinstance(handscan_mesh, trimesh.Trimesh):
        raise TypeError("Scan ist kein einzelnes mesh, sondern mehrere Objekte oder Gruppen.")
    
    color_of_hand_scan = handscan_mesh.visual

    if isinstance(color_of_hand_scan, trimesh.visual.color.ColorVisuals):
        print(f"Erfolgreich geladen: {len(handscan_mesh.vertices)} Vertices gefunden, {len(handscan_mesh.faces)} Faces gefunden.")
        return handscan_mesh
    
    if isinstance(color_of_hand_scan, trimesh.visual.texture.TextureVisuals):
        if color_of_hand_scan.material.image is None:
            raise ValueError("Es wurde keine Textur gefunden, obwohl eine .mtl file existiert.")
        else:
            filled_handscan = color_of_hand_scan.to_color()
            handscan_mesh.visual = filled_handscan
            print(f"Erfolgreich geladen: {len(handscan_mesh.vertices)} Vertices gefunden, {len(handscan_mesh.faces)} Faces gefunden.")
            return handscan_mesh

        
    raise TypeError("Scan hat keine Textur oder Farbe, bitte die .mtl file und die Textur uberprufen.")


#Beispielaufruf:
#handscan_mesh = load_whole_folder(".../.../...")
