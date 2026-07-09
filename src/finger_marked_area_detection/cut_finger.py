
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

    #normalisierte Geraetekoordinaten el.  -1 bis +1
    x_ndc = (px / width_cam) * 2.0 - 1.0
    y_ndc = (py / height_cam) * 2.0 - 1.0

    aspect = width_cam / height_cam
    half_fov_y = np.radians(camera.fov[1]) / 2.0
    tan_half_fov_y = np.tan(half_fov_y)
    tan_half_fov_x = tan_half_fov_y * aspect

    x_cam = x_ndc * tan_half_fov_x
    y_cam = y_ndc * tan_half_fov_y

    direction_cam = np.array([x_cam, y_cam, -1.0])
    direction_cam /= np.linalg.norm(direction_cam)

    direction_world = camera_transform[:3, :3] @ direction_cam
    origin_world = camera_transform[:3, 3]

    return origin_world, direction_world


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
        self._drag_current_px = None
        self._preview_plane = None

        super().__init__(trimesh.Scene(mesh), **kwargs)

    def _compute_preview_plane(self):
        camera = self.scene.camera
        camera.resolution = (self.width, self.height)
        cam_transform = self.scene.camera_transform

        o0, d0 = pixel_to_ray(camera, cam_transform, *self._drag_start_px)
        o1, d1 = pixel_to_ray(camera, cam_transform, *self._drag_current_px)

        p0 = ray_mesh_hit(self.mesh, o0, d0)
        p1 = ray_mesh_hit(self.mesh, o1, d1)

        depth = 2.0

        if p0 is None:
            p0 = o0 + d0 * depth

        if p1 is None:
            p1 = o1 + d1 * depth

        view_dir = cam_transform[:3, :3] @ np.array([0, 0, -1])

        try:
            return plane_from_line_and_view(p0, p1, view_dir)
        except:
            return None

    def on_mouse_press(self, x, y, buttons, modifiers):
        if modifiers & pyglet.window.key.MOD_SHIFT:
            self._drag_start_px = (x, y)
        else:
            super().on_mouse_press(x, y, buttons, modifiers)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._preview_plane = None
        if self._drag_start_px is not None:
            self._drag_current_px = (x, y)
            self._preview_plane = self._compute_preview_plane()
        else:
            super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)
        # waehrend SHIFT-Drag: Kamera nicht mitdrehen, einfach nichts tun

    def on_mouse_release(self, x, y, button, modifiers):
        if self._drag_start_px is not None:
            start_px = self._drag_start_px
            end_px = (x, y)

            self._drag_start_px = None
            self._drag_current_px = None   
            self._preview_plane = None

            self._try_cut(start_px, end_px)

    def _try_cut(self, start_px, end_px):
        camera = self.scene.camera
        camera.resolution = (self.width, self.height)
        cam_transform = self.scene.camera_transform

        o0, d0 = pixel_to_ray(camera, cam_transform, *start_px)
        o1, d1 = pixel_to_ray(camera, cam_transform, *end_px)

        p0 = ray_mesh_hit(self.mesh, o0, d0)
        p1 = ray_mesh_hit(self.mesh, o1, d1)

        depth = 2.0

        if p0 is None:
            p0 = o0 + d0 * depth

        if p1 is None:
            p1 = o1 + d1 * depth

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
    
    def on_draw(self):
        super().on_draw()

       
        if self._preview_plane is None:
            self.mesh.visual.vertex_colors = None

        if self._preview_plane is not None:
            origin, normal = self._preview_plane

            signed = np.dot(self.mesh.vertices - origin, normal)

            colors = np.zeros((len(self.mesh.vertices), 4), dtype=np.uint8)

            colors[signed > 0] = [255, 0, 0, 80]
            colors[signed <= 0] = [0, 0, 255, 80]

            self.mesh.visual.vertex_colors = colors

        if self._drag_start_px is None or self._drag_current_px is None:
            return

        import pyglet.gl as gl

        x0, y0 = self._drag_start_px
        x1, y1 = self._drag_current_px

        # in OpenGL Screen Space zeichnen
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glOrtho(0, self.width, 0, self.height, -1, 1)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()

        gl.glLineWidth(2)
        gl.glColor3f(1.0, 0.0, 0.0)

        pyglet.graphics.draw(2, gl.GL_LINES,
            ('v2f', (x0, y0, x1, y1))
        )

        # restore state
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)

        gl.glEnable(gl.GL_DEPTH_TEST)

        gl.glColor3f(1.0, 1.0, 1.0)


def interactive_cut(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    print("Fenster öffnet sich. Normal Drehen/Zoomen wie gewohnt.")
    print("Zum Schneiden: SHIFT gedrueckt halten, auf dem Mesh klicken,")
    print("Linie ziehen, loslassen. Dann im Terminal Seite waehlen (a/b).\n")

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
        input_user = input("nochmal schneiden? (y / n)")
        
    cut.show()