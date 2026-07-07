
"""Freihand-Zeichnen einer Linie (z.B. Kreis-Markierung) direkt auf dem
3D-Mesh, im selben trimesh-Viewer wie das Schnitt-Werkzeug:
 
1. Fenster oeffnet sich, Mesh wie gewohnt drehbar/zoombar.
2. SHIFT gedrueckt halten + Maus ziehen: eine rote Linie folgt der
   Mausbewegung UND ist direkt auf der Mesh-Oberflaeche gezeichnet
   (echte 3D-Punkte, keine Bildschirm-Koordinaten) - dreht man die
   Kamera, bleibt die Linie also am Mesh "kleben".
3. Maus loslassen: die Linie ist fertig, bleibt sichtbar auf dem Mesh.
4. Im Terminal wird gefragt, ob die Linie gespeichert werden soll.
5. Falls ja: die rote Linie wird direkt in eine KOPIE der Original-
   Textur eingemalt (nicht in Vertex-Colors - das wuerde Aufloesung
   kosten), und als neues OBJ + MTL + Textur-Bild exportiert - also
   im selben Format wie der Original-Scan. Landet IMMER im Ordner des
   Original-Scans, niemals im Code-Ordner.
 
Nutzt pixel_to_ray() aus cut_mesh.py wieder (identische Kamera-Strahl-
Berechnung, kein Grund das doppelt zu schreiben).
"""
 
from pathlib import Path
 
import numpy as np
import pyglet
import time
from pyglet import gl
import trimesh
from PIL import ImageDraw
from trimesh.viewer.windowed import SceneViewer
 
from cut_finger import pixel_to_ray
  
 
class DrawCircleViewer(SceneViewer):
    """trimesh-Viewer, erweitert um eine Freihand-Zeichenfunktion.
 
    SHIFT + Maus-Ziehen zeichnet eine rote Linie direkt auf der
    Mesh-Oberflaeche. Nach dem Loslassen kann ein neuer Scan (OBJ+MTL+
    Textur) mit eingemalter roter Markierung gespeichert werden.
    """
 
    # Radius des "Pinsels" beim Einmalen in die Textur, in Pixeln der
    # Textur-Bildgroesse
    BRUSH_RADIUS_PX = 6
 
    def __init__(self, mesh, original_folder, **kwargs):
        self.mesh = mesh
        self.original_folder = Path(original_folder)
 
        self.is_drawing = False
        self.lines = []
        self.current_line = []  # 3D-Punkte, fuer die Live-Anzeige der Linie
        
        self.uv_points = []    # zugehoerige UV-Koordinaten, fuer das Speichern
        self.current_uv_points = []

        self._last_draw_time = 0
        self._draw_interval = (1 / 5) #Nur alle 5tel Sekudnen wird aktualisiert, sonst hängt ser Pc hinterher.

        super().__init__(trimesh.Scene(mesh), **kwargs)
        self.scene.camera.resolution = (self.width, self.height)
    
    @staticmethod
    def ray_hit_point_and_uv(mesh, origin, direction):
        """Findet den naehesten Schnittpunkt eines Strahls mit dem Mesh und
        berechnet zusaetzlich die UV-Textur-Koordinate an genau dieser
        Stelle (per baryzentrischer Interpolation innerhalb des
        getroffenen Dreiecks).
    
        Gibt (punkt_3d, uv) zurueck, oder (None, None) falls kein Treffer.
        uv ist None, falls das Mesh gar keine UV-Koordinaten hat.
        """
        locations, _, index_tri = mesh.ray.intersects_location(
            ray_origins=[origin], ray_directions=[direction]
        )
        if len(locations) == 0:
            return None, None
    
        # bei mehreren Treffern (z.B. Vorder- und Rueckseite) den
        # naehesten zur Kamera nehmen
        dists = np.linalg.norm(locations - origin, axis=1)
        closest = np.argmin(dists)
        point = locations[closest]
    
        if mesh.visual.uv is None:
            return point, None
    
        tri_index = index_tri[closest]
        face = mesh.faces[tri_index]
        tri_vertices = mesh.vertices[face]
    
        # baryzentrische Koordinaten: beschreiben den Treffpunkt als
        # gewichtete Mischung der 3 Dreiecks-Eckpunkte (Gewichte summieren
        # sich zu 1) - dieselben Gewichte gelten dann auch fuer die UVs
        bary = trimesh.triangles.points_to_barycentric(
            triangles=[tri_vertices], points=[point]
        )[0]
        tri_uv = mesh.visual.uv[face]
        uv = (bary[:, None] * tri_uv).sum(axis=0)
    
        return point, uv
    # ---------- Maus-Events ----------
 
    def on_mouse_press(self, x, y, buttons, modifiers):
        if modifiers & pyglet.window.key.MOD_SHIFT:
            self.is_drawing = True
            self._add_point(x, y)
        else:
            super().on_mouse_press(x, y, buttons, modifiers)
 
    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.is_drawing:
            self._add_point(x, y)
        else:
            super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)
 
    def on_mouse_release(self, x, y, button, modifiers):
        if self.is_drawing:
            self._add_point(x, y)  # exakte Loslass-Position noch mit aufnehmen
            self.is_drawing = False
            self.lines.append(self.current_line)
            self.uv_points.append(self.current_uv_points)
        self.current_line = []
        self.current_uv_points = []

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.F and modifiers & pyglet.window.key.MOD_CTRL:
            self._finish_drawing()
    
    def _add_point(self, x, y):
        self.scene.camera.resolution = (self.width, self.height)
        origin, direction = pixel_to_ray(self.scene.camera, self.scene.camera_transform, x, y)

        now = time.time()

        point, uv = self.ray_hit_point_and_uv(self.mesh, origin, direction)
        if point is not None:
            self.current_line.append(point)
            self.current_uv_points.append(uv)

        if now - self._last_draw_time >= self._draw_interval:
            self.dispatch_event("on_draw")
            self.flip()
            self._last_draw_time = now
 
    def _finish_drawing(self):
        self.dispatch_event("on_draw")
        self.flip()
 
        print(f"\nLinie fertig gezeichnet: {len(self.current_line)} Punkte auf dem Mesh erfasst.")
    
        num_points_drawn = sum(len(line) for line in self.lines)
        if num_points_drawn < 3:
            print("Zu wenige Punkte auf dem Mesh getroffen, nichts zu speichern.")
            return
 
        antwort = input("Linien als neuen Scan speichern (OBJ+MTL)? (j/n): ").strip().lower()
        if antwort != "j":
            print("Nicht gespeichert.")
            return
 
        self._save_marked_mesh()
 
    def _save_marked_mesh(self):
        """Erstellt eine Kopie des Meshes mit der roten Linie direkt in
        die Textur eingemalt (nicht in Vertex-Colors - das wuerde
        Aufloesung kosten) und exportiert sie als neues OBJ+MTL+Textur.
 
        Wird IMMER im Ordner des Original-Scans abgelegt, niemals im
        Code-Ordner - Rohdaten und Code sollen sauber getrennt bleiben.
        """
        marked_mesh = self.mesh.copy()
 
        has_texture = (
            isinstance(marked_mesh.visual, trimesh.visual.texture.TextureVisuals)
            and marked_mesh.visual.material.image is not None
        )
 
        if has_texture:
            self._paint_line_on_texture(marked_mesh)
        else:
            # Fallback fuer Meshes ohne Textur: Vertex-Colors einfaerben
            print("Kein Textur-Bild gefunden, faerbe stattdessen Vertex-Colors ein.")
            self._paint_line_on_vertex_colors(marked_mesh)

        output_folder = self.original_folder / "scan_mit_markierung"
        output_folder.mkdir(exist_ok=True)
        save_path = self.original_folder / "scan_mit_markierung" /"scan_mit_kreis.obj"
    
        # Falls der Dateiname schon existiert (z.B. zweiter Versuch),
        # nicht ueberschreiben, sondern durchnummerieren
        zaehler = 1
        while save_path.exists():
            save_path = self.original_folder / f"scan_mit_kreis_{zaehler}.obj"
            zaehler += 1
 
        marked_mesh.export(save_path)
        print(f"Neuer Scan (OBJ+MTL+Textur) gespeichert unter: {save_path}")
 
    def _paint_line_on_texture(self, marked_mesh):
        original_image = marked_mesh.visual.material.image
        painted_image = original_image.copy()
        draw = ImageDraw.Draw(painted_image)
        img_w, img_h = painted_image.size
 
        gemalt = 0

        for uv_lines in self.uv_points:
            for cur_uv in self.current_uv_points:
                if cur_uv is None:
                    continue
                # U/V sind normiert (0 bis 1) - auf echte Bild-Pixel umrechnen.
                # V zeigt in Textur-Koordinaten meist von unten nach oben,
                # Bild-Pixel-Y aber von oben nach unten - deshalb (1 - v)
                px = cur_uv[0] * img_w
                py = (1 - cur_uv[1]) * img_h
    
                draw.ellipse(
                    [px - self.BRUSH_RADIUS_PX, py - self.BRUSH_RADIUS_PX,
                    px + self.BRUSH_RADIUS_PX, py + self.BRUSH_RADIUS_PX],
                    fill=(0, 0, 255),
                )
                gemalt += 1
 
        marked_mesh.visual.material.image = painted_image
        print(f"{gemalt} Punkte in die Textur eingemalt (Original-Aufloesung bleibt erhalten).")
 
    def _paint_line_on_vertex_colors(self, marked_mesh):
        from scipy.spatial import cKDTree
 
        if isinstance(marked_mesh.visual, trimesh.visual.texture.TextureVisuals):
            marked_mesh.visual = marked_mesh.visual.to_color()
 
        tree = cKDTree(marked_mesh.vertices)
        all_points = []
        for line in self.lines:
            all_points.extend(line)
        all_points = np.array(all_points)
        nearby_lists = tree.query_ball_point(all_points, r=1.5)
 
        marked_indices = set()
        for indices in nearby_lists:
            marked_indices.update(indices)
 
        marked_mesh.visual.vertex_colors[list(marked_indices)] = [255, 0, 0, 255]
        print(f"{len(marked_indices)} Vertices rot eingefaerbt.")
 
    # ---------- Zeichnen ----------
 
    def on_draw(self):
        # erst die normale 3D-Szene zeichnen lassen (Original-Verhalten
        # von SceneViewer)
        super().on_draw()
        # SceneViewer.on_draw() setzt die Kamera-Transformation direkt in
        # die aktive Matrix und stellt sie NICHT zurueck - wir befinden
        # uns hier also bereits im korrekten 3D-Weltkoordinatensystem und
        # koennen unsere gesammelten Mesh-Punkte direkt zeichnen, ohne
        # selbst irgendeine Matrix umzuschalten
        self._draw_line_on_mesh()
 
    def _draw_line_on_mesh(self):
        """Zeichnet die aktuell gezogene bzw. fertige Linie als rote
        3D-Linie direkt auf der Mesh-Oberfläche."""
        # Prüfen ob es überhaupt was zu zeichnen gibt
        has_lines = False
        for line in self.lines:
            if len(line) >= 2:
                has_lines = True
                break
        if not has_lines and len(self.current_line) < 2:
            return  # Nichts zu zeichnen

        gl.glDisable(gl.GL_LIGHTING)
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glColor3f(1.0, 0.0, 0.0)  # Rot
        gl.glLineWidth(4.0)

        # ALLE gespeicherten Linien zeichnen
        for line in self.lines:
            if len(line) >= 2:
                gl.glBegin(gl.GL_LINE_STRIP)
                for point in line:
                    gl.glVertex3f(*point)
                gl.glEnd()

        # AKTUELLE Linie zeichnen (während dem Zeichnen)
        if len(self.current_line) >= 2:
            gl.glBegin(gl.GL_LINE_STRIP)
            for point in self.current_line:
                gl.glVertex3f(*point)
            gl.glEnd()

        gl.glColor3f(1.0, 1.0, 1.0)

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glEnable(gl.GL_LIGHTING)
    
 
    def draw_circle_on_mesh(mesh: trimesh.Trimesh, original_folder: str) -> None:
        """Oeffnet den Viewer mit Freihand-Zeichenfunktion.
    
        SHIFT gedrueckt halten + Maus ziehen zum Zeichnen, danach im
        Terminal per (j/n) speichern. Die neue Datei landet immer im
        Original-Scan-Ordner, nie im Code-Ordner.
        """
        print("Fenster oeffnet sich. Normal Drehen/Zoomen wie gewohnt.")
        print("Zum Zeichnen: SHIFT gedrueckt halten, auf dem Mesh klicken,")
        print("Linie/Kreis nachzeichnen, loslassen. Danach im Terminal speichern (j/n).\n")
    
        DrawCircleViewer(mesh, original_folder)
    
