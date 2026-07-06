"""
Freihand-Zeichnen einer Linie (z.B. Kreis-Markierung) direkt auf dem
3D-Mesh, im selben trimesh-Viewer wie das Schnitt-Werkzeug:

1. Fenster oeffnet sich, Mesh wie gewohnt drehbar/zoombar.
2. SHIFT gedrueckt halten + Maus ziehen: eine rote Linie folgt exakt der
   Mausbewegung, waehrend im Hintergrund fuer jeden Punkt per Ray-Casting
   die passende 3D-Position auf der Mesh-Oberflaeche gesucht wird.
3. Maus loslassen: die Linie ist fertig.
4. Im Terminal wird gefragt, ob die Linie gespeichert werden soll.
5. Falls ja: wird als JSON-Datei IMMER im Ordner des Original-Scans
   abgelegt (niemals im Code-Ordner), damit Rohdaten und Code sauber
   getrennt bleiben.

Nutzt pixel_to_ray() und ray_mesh_hit() aus cut_finger.py wieder -
identische Ray-Casting-Logik, kein Grund das doppelt zu schreiben.
"""

import json
from pathlib import Path

import numpy as np
import pyglet
from pyglet import gl
import trimesh
from trimesh.viewer.windowed import SceneViewer

from cut_finger import pixel_to_ray, ray_mesh_hit


class DrawCircleViewer(SceneViewer):
    """trimesh-Viewer, erweitert um eine Freihand-Zeichenfunktion.

    SHIFT + Maus-Ziehen zeichnet eine rote Linie auf dem Bildschirm und
    sammelt dabei gleichzeitig die entsprechenden 3D-Punkte auf der
    Mesh-Oberflaeche. Nach dem Loslassen kann die Linie gespeichert
    werden (immer im Ordner des Original-Scans, nie im Code-Ordner).
    """

    def __init__(self, mesh, original_folder, **kwargs):
        self.mesh = mesh
        self.original_folder = Path(original_folder)

        self.is_drawing = False
        self.pixel_trail = []   # Bildschirm-Pixel: fuer die rote Live-Anzeige
        self.mesh_points = []   # 3D-Punkte auf dem Mesh: fuer die Speicherung

        # SceneViewer.__init__() oeffnet das Fenster und blockiert, bis
        # es wieder geschlossen wird (wie schon beim Schnitt-Werkzeug)
        super().__init__(trimesh.Scene(mesh), **kwargs)

    # ---------- Maus-Events ----------

    def on_mouse_press(self, x, y, buttons, modifiers):
        if modifiers & pyglet.window.key.MOD_SHIFT:
            self.is_drawing = True
            self.pixel_trail = []
            self.mesh_points = []
            self._add_point(x, y)
        else:
            super().on_mouse_press(x, y, buttons, modifiers)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.is_drawing:
            self._add_point(x, y)
        else:
            super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)

    def on_mouse_release(self, x, y, button, modifiers):
        # SceneViewer definiert on_mouse_release selbst nicht, daher hier
        # kein super()-Aufruf noetig (siehe cut_mesh.py, gleiches Prinzip)
        if self.is_drawing:
            self.is_drawing = False
            self._finish_drawing()

    def _add_point(self, x, y):
        """Merkt sich den Bildschirm-Pixel fuer die rote Anzeige und
        versucht zusaetzlich, den zugehoerigen 3D-Punkt auf dem Mesh
        per Ray-Casting zu finden."""
        self.pixel_trail.append((x, y))

        camera = self.scene.camera
        camera.resolution = (self.width, self.height)
        origin, direction = pixel_to_ray(camera, self.scene.camera_transform, x, y)

        hit = ray_mesh_hit(self.mesh, origin, direction)
        if hit is not None:
            self.mesh_points.append(hit)
        # falls die Maus kurz neben das Mesh rutscht (hit=None), wird der
        # Pixel trotzdem fuer die rote Linie gespeichert - nur eben ohne
        # zugehoerigen 3D-Punkt

    # ---------- Nach dem Loslassen ----------

    def _finish_drawing(self):
        print(f"\nLinie fertig gezeichnet: {len(self.mesh_points)} Punkte auf dem Mesh erfasst.")

        if len(self.mesh_points) < 3:
            print("Zu wenige Punkte auf dem Mesh getroffen, nichts zu speichern.")
            return

        antwort = input("Diese Linie speichern? (j/n): ").strip().lower()
        if antwort != "j":
            print("Nicht gespeichert.")
            return

        self._save_points()

    def _save_points(self):
        """Speichert die gesammelten 3D-Punkte als JSON-Datei.

        Wird IMMER im Ordner des Original-Scans abgelegt, niemals im
        Code-Ordner - Rohdaten und Code sollen sauber getrennt bleiben.
        """
        save_path = self.original_folder / "gezeichneter_kreis.json"

        # Falls der Dateiname schon existiert (z.B. zweiter Versuch),
        # nicht ueberschreiben, sondern durchnummerieren
        zaehler = 1
        while save_path.exists():
            save_path = self.original_folder / f"gezeichneter_kreis_{zaehler}.json"
            zaehler += 1

        daten = {"punkte": [list(p) for p in self.mesh_points]}
        with open(save_path, "w") as f:
            json.dump(daten, f, indent=2)

        print(f"Gespeichert unter: {save_path}")

    # ---------- Zeichnen ----------

    def on_draw(self):
        # erst die normale 3D-Szene zeichnen lassen (Original-Verhalten
        # von SceneViewer), danach unsere rote Linie oben drueber legen
        super().on_draw()
        self._draw_red_line_overlay()

    def _draw_red_line_overlay(self):
        """Zeichnet die aktuell gezogene Linie als rote 2D-Linie ueber
        der 3D-Szene, direkt in Bildschirm-Pixel-Koordinaten (nicht in
        3D-Weltkoordinaten - die Linie soll ja exakt an der
        Mausposition kleben, unabhaengig von Kamera-Drehung/Zoom)."""
        if len(self.pixel_trail) < 2:
            return

        # kurzzeitig in einen einfachen 2D-Bildschirm-Modus wechseln:
        # Ursprung unten links, 1 Einheit = 1 Pixel
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glOrtho(0, self.width, 0, self.height, -1, 1)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()

        gl.glDisable(gl.GL_DEPTH_TEST)  # Linie soll immer sichtbar sein, auch "vor" dem Mesh
        gl.glColor3f(1.0, 0.0, 0.0)     # rot
        gl.glLineWidth(3.0)

        gl.glBegin(gl.GL_LINE_STRIP)
        for px, py in self.pixel_trail:
            gl.glVertex2f(px, py)
        gl.glEnd()

        gl.glEnable(gl.GL_DEPTH_TEST)

        # zurueck in den normalen 3D-Modus wechseln, damit die naechste
        # Aktualisierung der 3D-Szene wieder korrekt funktioniert
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)


    def draw_circle_on_mesh(mesh: trimesh.Trimesh, original_folder: str) -> None:
        """Oeffnet den Viewer mit Freihand-Zeichenfunktion.

        SHIFT gedrueckt halten + Maus ziehen zum Zeichnen, danach im
        Terminal per (j/n) speichern. Die Datei landet immer im
        Original-Scan-Ordner, nie im Code-Ordner.
        """
        print("Fenster oeffnet sich. Normal Drehen/Zoomen wie gewohnt.")
        print("Zum Zeichnen: SHIFT gedrueckt halten, auf dem Mesh klicken,")
        print("Linie/Kreis nachzeichnen, loslassen. Danach im Terminal speichern (j/n).\n")

        DrawCircleViewer(mesh, original_folder)


# if __name__ == "__main__":
#     import sys
#     import load_scan

#     if len(sys.argv) != 2:
#         print("Nutzung: python draw_circle.py <scan_ordner>")
#         sys.exit(1)

#     scan_folder = sys.argv[1]
#     mesh = load_scan.load_whole_folder(scan_folder, bake_vertex_colors=False)
#     draw_circle_on_mesh(mesh, scan_folder)