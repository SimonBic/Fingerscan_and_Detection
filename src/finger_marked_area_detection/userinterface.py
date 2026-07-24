import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
import sys
import trimesh
import pyvistaqt
import pyvista as p_v
from isolate_finger import load_teilmeshe_mit_textur, isolate_finger
from draw_area_on_scan_experimental import draw_main
from heatmap import heatmap_main
import numpy as np
from PySide6.QtWidgets import QMainWindow, QApplication, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
from pyvistaqt import QtInteractor
from pathlib import Path



class HauptFenster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fingerscan-Viewer")
        self.resize(1920, 1080)
        self.setAcceptDrops(True)

        self.aktueller_ordner = None

        zentral_widget = QWidget()
        self.setCentralWidget(zentral_widget)
        haupt_layout = QHBoxLayout(zentral_widget)

        self.knopf_spalte = QWidget()
        self.knopf_layout = QVBoxLayout(self.knopf_spalte)
        self.button_isolieren = QPushButton("Finger isolieren")
        self.button_isolieren.setFixedSize(192, 108)
        self.button_isolieren.clicked.connect(self.isolieren_klick)
        self.knopf_layout.addWidget(self.button_isolieren)

        self.button_zeichnen = QPushButton("Bereich einzeichnen")
        self.button_zeichnen.setFixedSize(192, 108)
        self.button_zeichnen.clicked.connect(self.zeichnen_klick)
        self.knopf_layout.addWidget(self.button_zeichnen)

        self.button_heatmap = QPushButton("Heatmap erzeugen")
        self.button_heatmap.setFixedSize(192, 108)
        self.button_heatmap.clicked.connect(self.heatmap_klick)
        self.knopf_layout.addWidget(self.button_heatmap)
        haupt_layout.addWidget(self.knopf_spalte, stretch = 1)         

        self.viewer_spalte = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_spalte)

        self.hinweis_label = QLabel("Scan-Ordner per Drag-and-Drop hierher ziehen")
        self.hinweis_label.setAlignment(Qt.AlignCenter)
        viewer_layout.addWidget(self.hinweis_label)

        self.plotter = QtInteractor(self.viewer_spalte)                     
        viewer_layout.addWidget(self.plotter.interactor)               

        haupt_layout.addWidget(self.viewer_spalte, stretch = 4)   
 
    def dragEnterEvent(self, event):
        #wird aufgerufen, wenn die Daten oder der Ordner über dem Fenster hovert
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
 
    def dropEvent(self, event):
        #Wir aufgerufen, wenn der ORdner losgelassen wird
        urls = event.mimeData().urls()
        if not urls:
            return

        self.aktueller_ordner = urls[0].toLocalFile()
        pfad = Path(urls[0].toLocalFile())
 
        # Falls direkt eine .obj-Datei gezogen wurde, den Ordner
        # drumherum nehmen
        ordner = pfad.parent if pfad.is_file() else pfad

        self.lade_und_zeige(ordner)
 
    def lade_und_zeige(self, ordner: Path):
        try:
            obj_file = list(ordner.glob("*.obj"))
            teile = load_teilmeshe_mit_textur(obj_file)
        except Exception as e:
            self.hinweis_label.setText(f"Fehler beim Laden: {e}")
            return
 
        self.plotter.clear()

        for pv_mesh, tex in teile:          
            self.plotter.add_mesh(pv_mesh, texture=tex)

        self.plotter.reset_camera()
 
        self.hinweis_label.setText(f"Geladen: {ordner.name}")

    def isolieren_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        isolate_finger(str(self.aktueller_ordner))

    def zeichnen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        draw_main(str(self.aktueller_ordner))   # Parameter an deine echte Signatur anpassen

    def heatmap_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        heatmap_main(str(self.aktueller_ordner))   # Parameter an deine echte Signatur anpassen
 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenster = HauptFenster()
    fenster.show()
    sys.exit(app.exec())