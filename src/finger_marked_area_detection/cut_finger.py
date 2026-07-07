
# Interaktives Schneiden eines Meshes direkt im trimesh-Viewer:
# Shift + linke Maustase halten, dann auf dem mesh schneiden.
# 
# Im Terminal wird gefragt, welche Seite gezeigt behalten werden soll (a / b), einfach eingeben, fertig.


import numpy as np  
import pyglet   #um SHIFT zu erkennen.
import trimesh
from trimesh.viewer.windowed import SceneViewer


def pixel_to_ray(camera, camera_transform, px, py):
    """Wandelt Bildschirm-Pixelkoordinate in einen 3D-Sichtstrahl um"""

    width_cam = int(camera.resolution[0])
    height_cam = int(camera.resolution[1])

    # NDC (normalisierte Geraetekoordinaten): -1 bis +1
    x_ndc = (px / width_cam) * 2.0 - 1.0
    y_ndc = (py / height_cam) * 2.0 - 1.0

    # camera.fov ist ein Array mit 2 Werten: [fov_x, fov_y] - getrennt
    # behandeln, NICHT zusammen mit einem zusaetzlichen aspect-Faktor
    # verrechnen (das FOV beruecksichtigt das Seitenverhaeltnis schon)
    half_fov = np.radians(camera.fov) / 2.0   # Array mit 2 Werten
    tan_half_fov = np.tan(half_fov)           # Array mit 2 Werten

    x_cam = x_ndc * tan_half_fov[0]   # nur den X-Anteil nehmen
    y_cam = y_ndc * tan_half_fov[1]   # nur den Y-Anteil nehmen

    direction_cam = np.array([x_cam, y_cam, -1.0])
    direction_cam /= np.linalg.norm(direction_cam)

    direction_world = camera_transform[:3, :3] @ direction_cam
    origin_world = camera_transform[:3, 3]

    return origin_world, direction_world

# def pixel_to_ray(camera, camera_transform, px, py):
#     ''' Wandelt Bildschirm-Pixelkoordinate in einen 3D-Sichtstrahl
#         (Ursprung + Richtung) im Weltkoordinatensystem um'''

#     widht_of_cam, height_of_cam = camera.resolution

#     half_fov = np.radians(camera.fov) / 2.0 #Öffnungswinkel von Bildmitte bis Rand, von winkel zu Radianten
#     right_top = np.tan(half_fov) * (1 - 1.0 / np.array([widht_of_cam, height_of_cam])) #Berechnung obere Rechte Ecke, Multiplikator um Pixelmitte zu treffen

#     x_cam = np.interp(px, [0, widht_of_cam - 1], [-right_top[0], right_top[0]])     #Umrechnung des Kamerapixels von numerischen Werten
#     y_cam = np.interp(py, [0, height_of_cam - 1], [-right_top[1], right_top[1]])    #in lineare Interpolation, also Element von [-right top, right top]
    
#     #Annahme, z Richtung der Kamera = -1; Ebene ist immer genau -1 in der z Koordinatre entfernt
#     direction_cam = np.array([x_cam, y_cam, -1.0])      #Vektor = Ziel - Beginn = (x, y -1) - (0, 0, 0)
#     direction_cam /= np.linalg.norm(direction_cam)      #normieren

#     #Ergibt Vektor, der x, y, z relativ zu mir selbst betrachtet.

#     #camera_transform = 4 mal 4 Matrix, 3 mal 3 Block oben links isr rotation, rechte Spalte ist Änderung der Koordinaten, letzte zeile  = (0,0,0,1)
#     direction_world = camera_transform[:3, :3] @ direction_cam  #Matrixmultiplikation mit richtungsvektor von oben 
#     #ergibt Vektor mit Berücksichtigung der Rotationen davor

#     origin_world = camera_transform[:3, 3] #wo startet der blickstrahl
#     return origin_world, direction_world


def ray_mesh_hit(mesh, origin, direction):
    """Findet den naehesten Schnittpunkt eines Rays mit dem Mesh (Hände sind ja 3-Dimensional)"""

    locations, _, _ = mesh.ray.intersects_location(
        ray_origins=[origin], ray_directions=[direction]
    )

    if len(locations) == 0:
        return None
    
    dists = np.linalg.norm(locations - origin, axis=1) #Berechnen des Abstand jedes Treffpunkts

    return locations[np.argmin(dists)] #Zurückgabe des Treffpunktes mit kleinstem Abstand


def plane_from_line_and_view(p0: np.ndarray, p1: np.ndarray, view_dir: np.ndarray):
    """ Berechnet die Schnittebene, die durch die gezogene Linie (p0->p1)
        und die Kamera-Blickrichtung aufgespannt wird   """

    line_dir = p1 - p0 

    if np.linalg.norm(line_dir) < 1e-8:
        raise ValueError("Linie zu kurz - bitte deutlicher ziehen.")
    
    normal = np.cross(line_dir, view_dir) 
    norm_len = np.linalg.norm(normal)

    if norm_len < 1e-8:
        raise ValueError("Linie zeigt in Blickrichtung - keine eindeutige Ebene.")
    normal = normal / norm_len
    origin = (p0 + p1) / 2
    return origin, normal


class CutSceneViewer(SceneViewer):
    """trimesh-Viewer, erweitert um SHIFT+Ziehen zum Definieren einer
    Schnittebene. Ergebnis wird nach Fenster-Schliessen in self.result_mesh
    abgelegt (None, falls kein Schnitt gemacht wurde)."""

    def __init__(self, mesh, **kwargs):
        self.mesh = mesh
        self.result_mesh = None
        self._drag_start_px = None
        super().__init__(trimesh.Scene(mesh), **kwargs)

    def on_mouse_press(self, x, y, buttons, modifiers):
        if modifiers & pyglet.window.key.MOD_SHIFT:
            self._drag_start_px = (x, y)
        else:
            super().on_mouse_press(x, y, buttons, modifiers)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self._drag_start_px is None:
            super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)
        # waehrend SHIFT-Drag: Kamera nicht mitdrehen, einfach nichts tun

    def on_mouse_release(self, x, y, button, modifiers):
        # SceneViewer definiert selbst kein on_mouse_release, daher hier
        # kein super()-Aufruf noetig (es gibt nichts zu delegieren).
        if self._drag_start_px is not None:
            start_px = self._drag_start_px
            end_px = (x, y)
            self._drag_start_px = None
            self._try_cut(start_px, end_px)

    def _try_cut(self, start_px, end_px):
        camera = self.scene.camera
        camera.resolution = (self.width, self.height)
        cam_transform = self.scene.camera_transform

        o0, d0 = pixel_to_ray(camera, cam_transform, *start_px)
        o1, d1 = pixel_to_ray(camera, cam_transform, *end_px)

        p0 = ray_mesh_hit(self.mesh, o0, d0)
        p1 = ray_mesh_hit(self.mesh, o1, d1)

        if p0 is None or p1 is None:
            print("Linie muss auf dem Mesh beginnen UND enden - bitte erneut ziehen.")
            return

        view_dir = cam_transform[:3, :3] @ np.array([0.0, 0.0, -1.0])

        try:
            origin, normal = plane_from_line_and_view(p0, p1, view_dir)
        except ValueError as e:
            print(f"Ebene konnte nicht berechnet werden: {e}")
            return

        signed = np.dot(self.mesh.vertices - origin, normal)
        count_a = int((signed > 0).sum())
        count_b = int((signed <= 0).sum())
        print(f"\nSeite A (Normalenrichtung):     {count_a} Vertices")
        print(f"Seite B (Gegenrichtung):         {count_b} Vertices")

        choice = input("Welche Seite behalten? (a/b, oder Enter zum Abbrechen): ").strip().lower()
        if choice not in ("a", "b"):
            print("Abgebrochen, keine Aenderung.")
            return

        cut_normal = normal if choice == "a" else -normal
        self.result_mesh = self.mesh.slice_plane(plane_origin=origin, plane_normal=cut_normal)
        print(f"Geschnitten: {len(self.result_mesh.vertices)} Vertices, "
              f"{len(self.result_mesh.faces)} Faces uebrig. Fenster schliesst sich.")
        self.close()


def interactive_cut(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    print("Fenster öffnet sich. Normal Drehen/Zoomen wie gewohnt.")
    print("Zum Schneiden: SHIFT gedrueckt halten, auf dem Mesh klicken,")
    print("Linie ziehen, loslassen. Dann im Terminal Seite waehlen (a/b).\n")

    # SceneViewer.__init__() ruft intern bereits pyglet.app.run() auf und
    # kehrt erst zurueck, wenn das Fenster geschlossen wird - kein
    # zusaetzlicher pyglet.app.run()-Aufruf noetig (fuehrte sonst zu einer
    # haengenden zweiten Event-Loop nach dem Schliessen).
    viewer = CutSceneViewer(mesh)

    if viewer.result_mesh is not None:
        return viewer.result_mesh
    return mesh


def cut_finger_main(mesh):
    cut = mesh

    input_user = "y"
    while input_user == "y":
        cut = interactive_cut(mesh)
        mesh = cut
        input_user = input("nochmal schneiden?")
        
    cut.show()