import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb") 
import PySide6
qt_lib_pfad = os.path.join(os.path.dirname(PySide6.__file__), "Qt", "lib")
os.environ["LD_LIBRARY_PATH"] = qt_lib_pfad + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
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

def isolate_finger_parameter_datei_pfad(scan_ordner: Path) -> Path:
        #Pfad zur Parameterdatei, siehe Ordnerstruktur.pdf (Update ich bald)
        patienten_ordner = scan_ordner.parent.parent
        return patienten_ordner / "pat_parameter" / "isolate_finger_parameter.txt"
    
 
def lade_isolate_finger_parameter(scan_ordner: Path) -> dict | None:
    pfad = isolate_finger_parameter_datei_pfad(scan_ordner)
    if not pfad.exists():
        return None
                
    werte = {}
    for zeile in pfad.read_text().splitlines():
        if "=" not in zeile:
            continue
        name, wert = zeile.split("=")
        werte[name.strip()] = float(wert.strip())

    return werte           
         
    
def speichere_isolate_finger_parameter(
            scan_ordner: Path, 
            radius_faktor: float,
            laengen_faktor: float, 
            unterschreitung: float) -> Path:
    
    pfad = isolate_finger_parameter_datei_pfad(scan_ordner)
    pfad.write_text(
        f"radius_faktor={radius_faktor}\n"
        f"laengen_faktor={laengen_faktor}\n"
        f"unterschreitung={unterschreitung}\n"
    )
    return pfad

def generator_bis_ende(generator):
    try:
        while True:
            next(generator)
    except StopIteration as e:
        return e.value

class HauptFenster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fingerscan-Viewer")
        self.resize(1920, 1080)
        self.setAcceptDrops(True)

        self.aktueller_ordner = None
        self.isolieren_ablauf = None

        zentral_widget = QWidget()
        self.setCentralWidget(zentral_widget)
        haupt_layout = QHBoxLayout(zentral_widget)

        self.knopf_spalte = QWidget()
        self.knopf_layout = QVBoxLayout(self.knopf_spalte)

        
        self.haupt_buttons_container = QWidget()
        haupt_buttons_layout = QVBoxLayout(self.haupt_buttons_container)

        self.button_isolieren = QPushButton("Finger isolieren")
        self.button_isolieren.setFixedSize(192, 108)
        self.button_isolieren.clicked.connect(self.isolieren_klick)
        haupt_buttons_layout.addWidget(self.button_isolieren)         

        self.button_zeichnen = QPushButton("Bereich einzeichnen")
        self.button_zeichnen.setFixedSize(192, 108)
        self.button_zeichnen.clicked.connect(self.zeichnen_klick)
        haupt_buttons_layout.addWidget(self.button_zeichnen)

        self.button_heatmap = QPushButton("Heatmap erzeugen")
        self.button_heatmap.setFixedSize(192, 108)
        self.button_heatmap.clicked.connect(self.heatmap_klick)
        haupt_buttons_layout.addWidget(self.button_heatmap)

        self.knopf_layout.addWidget(self.haupt_buttons_container)       
        
        self.isolieren_wahl_container = QWidget()
        wahl_layout = QVBoxLayout(self.isolieren_wahl_container)

        self.button_automatisch = QPushButton("Automatische\nEinstellungen\nverwenden")
        self.button_automatisch.setFixedSize(192, 108)
        self.button_automatisch.clicked.connect(self.automatisch_klick)
        wahl_layout.addWidget(self.button_automatisch)

        self.button_manuell = QPushButton("Selbst justieren")
        self.button_manuell.setFixedSize(192, 108)
        wahl_layout.addWidget(self.button_manuell)

        self.button_weiter = QPushButton("Weiter")
        self.button_weiter.setFixedSize(192, 108)
        self.button_weiter.clicked.connect(self.weiter_klick)
        wahl_layout.addWidget(self.button_weiter)
        self.button_weiter.setVisible(False)

        self.knopf_layout.addWidget(self.isolieren_wahl_container)
        self.isolieren_wahl_container.setVisible(False)                 

        haupt_layout.addWidget(self.knopf_spalte, stretch=1)     

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
        self.isolieren_wahl_container.setVisible(True)
        self.haupt_buttons_container.setVisible(False)

    def automatisch_klick(self):
        ordner = Path(self.aktueller_ordner)
        gespeichert = lade_isolate_finger_parameter(ordner)

        if gespeichert:
            gen = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=False, **gespeichert)
        else:
            gen = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=False)

        gespeicherter_obj_pfad = generator_bis_ende(gen)   

        self.isolieren_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(True)

        self.lade_und_zeige(Path(gespeicherter_obj_pfad))   

    def manuell_klick(self):
        ordner = Path(self.aktueller_ordner)
        self.isolieren_ablauf = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=True)
        self.button_weiter.setVisible(True)
        next(self.isolieren_ablauf)

    def weiter_klick(self):
        try:
            next(self.isolieren_ablauf)
        except StopIteration:
            self.button_weiter.setVisible(False)
            self.isolieren_wahl_container.setVisible(False)
            self.haupt_buttons_container.setVisible(True)

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