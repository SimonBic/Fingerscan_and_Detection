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
from draw_area_on_scan_experimental import draw_main, save_drawn_area
from heatmap import heatmap_main
import numpy as np
from PySide6.QtWidgets import QMainWindow, QApplication, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
from pyvistaqt import QtInteractor
from pathlib import Path
from theme import QSS

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
            ordner = next(generator)
    except StopIteration as e:
        return e.value
    return ordner

class HauptFenster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fingerscan-Viewer")
        self.resize(1920, 1080)
        self.setAcceptDrops(True)

        self.aktueller_ordner = None
        self.isolieren_ablauf = None
        self.automatisch_modus_aktiv = False
        self.zeichnungs_status = {
            "flaeche": None,
            "landmarken": None,
            "punkte_eingezeichnet": None
            }
        self.path_zeichnung = None
        self.aktuelle_teile = None
        self.vermessen_modus_aktiv = False

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

        self.button_vermessen = QPushButton("Bereich / Strecke \nvermessen")
        self.button_vermessen.setFixedSize(192, 108)
        self.button_vermessen.clicked.connect(self.vermessen_klick)
        haupt_buttons_layout.addWidget(self.button_vermessen)

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

        self.malen_wahl_container = QWidget()
        malen_wahl_layout = QVBoxLayout(self.malen_wahl_container)
        self.button_weiter_malen = QPushButton("Fertig gemalt")
        self.button_weiter_malen.setFixedSize(192, 108)
        self.button_weiter_malen.clicked.connect(self.weiter_klick_malen)
        malen_wahl_layout.addWidget(self.button_weiter_malen)
        self.button_weiter_malen.setVisible(False)

        self.knopf_layout.addWidget(self.malen_wahl_container)
        self.malen_wahl_container.setVisible(False)        

        self.farbe_wahl_container = QWidget()
        farbe_wahl_layout = QVBoxLayout(self.farbe_wahl_container)

        self.button_rot= QPushButton("Untersuchung 1 \nrot")
        self.button_orange= QPushButton("Untersuchung 2 \norange")
        self.button_gelb= QPushButton("Untersuchung 1 \ngelb")
        self.button_gruen= QPushButton("Untersuchung 1 \ngrün")
        self.button_blau= QPushButton("Untersuchung 1 \nblau")

        self.button_rot.setFixedSize(192, 108)
        self.button_orange.setFixedSize(192, 108)
        self.button_gelb.setFixedSize(192, 108)
        self.button_gruen.setFixedSize(192, 108)
        self.button_blau.setFixedSize(192, 108)

        farbe_wahl_layout.addWidget(self.button_rot)
        farbe_wahl_layout.addWidget(self.button_orange)
        farbe_wahl_layout.addWidget(self.button_gelb)
        farbe_wahl_layout.addWidget(self.button_gruen)
        farbe_wahl_layout.addWidget(self.button_blau)

        self.button_rot.clicked.connect(lambda:self.farbenwahl("rot"))
        self.button_orange.clicked.connect(lambda:self.farbenwahl("orange"))
        self.button_gelb.clicked.connect(lambda:self.farbenwahl("gelb"))
        self.button_gruen.clicked.connect(lambda:self.farbenwahl("grün"))
        self.button_blau.clicked.connect(lambda:self.farbenwahl("blau"))

        self.knopf_layout.addWidget(self.farbe_wahl_container)
        self.farbe_wahl_container.setVisible(False)


        self.vermessung_wahl_container = QWidget()
        vermessung_wahl_layout = QVBoxLayout(self.vermessung_wahl_container)

        self.button_vermessen_weiter = QPushButton("Eingezeichneten \nBereich / Umfang \nvermessen")
        self.button_Strecke_vermessen = QPushButton("Eingezeichnete \nStrecke vermessen")

        self.button_vermessen_weiter.setFixedSize(192, 108)
        self.button_Strecke_vermessen.setFixedSize(192, 108)

        self.button_vermessen_weiter.clicked.connect(self.bereich_vermessen_start)
        self.button_Strecke_vermessen.clicked.connect(self.strecke_messen_klick)

        vermessung_wahl_layout.addWidget(self.button_vermessen_weiter)
        vermessung_wahl_layout.addWidget(self.button_Strecke_vermessen)

        self.knopf_layout.addWidget(self.vermessung_wahl_container)
        self.vermessung_wahl_container.setVisible(False)

        self.navigatecontainer = QWidget()
        navigate_layout = QVBoxLayout(self.navigatecontainer)
        self.button_main_menu = QPushButton("Zurück zum Hauptmenü")
        self.button_main_menu.setFixedSize(192, 108)
        self.button_main_menu.clicked.connect(self.lade_main_menu)
        navigate_layout.addWidget(self.button_main_menu)
        self.knopf_layout.addWidget(self.navigatecontainer)
        self.navigatecontainer.setVisible(False)

        haupt_layout.addWidget(self.knopf_spalte, stretch=1)     

        self.viewer_spalte = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_spalte)

        self.hinweis_label = QLabel("Scan-Ordner per Drag-and-Drop hierher ziehen")
        self.hinweis_label.setAlignment(Qt.AlignCenter)
        viewer_layout.addWidget(self.hinweis_label)

        self.plotter = QtInteractor(self.viewer_spalte)
        self.plotter.set_background("F5F7FA")                  
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


    def zeige_koordinatensystem(self):
        achsen_actor = self.plotter.add_axes_at_origin(x_color="red", y_color="green", z_color="blue")
        achsen_actor.SetTotalLength(1000, 1000, 1000)
        self.plotter.reset_camera()
        print("Mesh-Bounds:", self.plotter.bounds)

 
    def lade_und_zeige(self, ordner: Path):
        print("DEBUG - lade_und_zeige bekommt Ordner:", ordner, "| ist Ordner?", ordner.is_dir())
        try:
            obj_file = list(ordner.glob("*.obj"))
            print("DEBUG - gefundene .obj-Dateien:", obj_file)
            teile = load_teilmeshe_mit_textur(obj_file)
        except Exception as e:
            self.hinweis_label.setText(f"Fehler beim Laden (ui, lade_und_zeige): {e}")
            return

        self.aktuelle_teile = teile
        self.aktuelles_hand_mesh = p_v.merge([teil for teil, tex in teile])
        self.plotter.clear()

        for pv_mesh, tex in teile:          
            self.plotter.add_mesh(pv_mesh, texture=tex)

        #self.zeige_koordinatensystem()
        self.plotter.reset_camera()
        self.hinweis_label.setText(f"Geladen: {ordner.name}")


    def zeige_basis_mesh_neu(self):
        self.plotter.clear()
        for pv_mesh, tex in self.aktuelle_teile:
            self.plotter.add_mesh(pv_mesh, texture=tex)


    def lade_main_menu(self):
        self.haupt_buttons_container.setVisible(True)
        self.isolieren_wahl_container.setVisible(False)
        self.malen_wahl_container.setVisible(False)
        self.farbe_wahl_container.setVisible(False)
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(False)
        self.plotter.clear()
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.zeige_basis_mesh_neu()
        self.plotter.disable_picking()

    def isolieren_klick(self):
        if self.aktueller_ordner is None:
                    self.hinweis_label.setText("Erst einen Scan laden")
                    return
        self.zeige_basis_mesh_neu()
        self.button_automatisch.setVisible(True)   
        self.button_manuell.setVisible(True)   
        self.isolieren_wahl_container.setVisible(True)
        self.haupt_buttons_container.setVisible(False)
        self.navigatecontainer.setVisible(True)

    def automatisch_klick(self):
        self.zeige_basis_mesh_neu()
        self.button_automatisch.setVisible(False)   
        self.button_manuell.setVisible(False)    
        self.navigatecontainer.setVisible(True)     
        ordner = Path(self.aktueller_ordner)
        gespeichert = lade_isolate_finger_parameter(ordner)

        if gespeichert:
            self.isolieren_ablauf = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=False, **gespeichert)
        else:
            self.isolieren_ablauf = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=False)

        self.automatisch_modus_aktiv = True

        self.button_weiter.setText("Fertig markiert")
        self.button_weiter.setVisible(True)
        next(self.isolieren_ablauf) 

    def manuell_klick(self):
        ordner = Path(self.aktueller_ordner)
        self.isolieren_ablauf = isolate_finger(str(ordner), plotter = self.plotter, zeige_zwischenschritte=True)
        self.button_weiter.setVisible(True)
        self.navigatecontainer.setVisible(True)
        next(self.isolieren_ablauf)

    def weiter_klick(self):
        self.navigatecontainer.setVisible(False)
        if getattr(self, "automatisch_modus_aktiv", False):
            # Nutzer hat gerade 2 Punkte geklickt und "Fertig markiert" gedrueckt
            self.automatisch_modus_aktiv = False
            self.button_weiter.setText("Weiter")
            self.button_weiter.setVisible(False)

            try:
                gespeicherter_obj_pfad = generator_bis_ende(self.isolieren_ablauf)  # Rest jetzt automatisch
                self.aktueller_ordner = Path(gespeicherter_obj_pfad)
            except Exception as e:
                self.hinweis_label.setText(f"Fehler: {e}")
                self.isolieren_wahl_container.setVisible(False)
                self.haupt_buttons_container.setVisible(True)
                return

            self.isolieren_wahl_container.setVisible(False)
            self.haupt_buttons_container.setVisible(True)
            self.lade_und_zeige(Path(gespeicherter_obj_pfad))   
            return

        # bisheriger "manuell"-Ablauf bleibt unveraendert
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
        
        self.navigatecontainer.setVisible(True)
        self.haupt_buttons_container.setVisible(False)
        self.malen_wahl_container.setVisible(True)
        self.button_weiter_malen.setVisible(True)

        self.gezeichnete_flaeche = draw_main(str(self.aktueller_ordner), self.plotter, self.zeichnungs_status)


    def berechne_flaeche_und_umfang(self, flaeche: p_v.PolyData, punkte: np.ndarray) -> tuple[float, float]:
        flaecheninhalt = flaeche.area

        geschlossen = np.vstack([punkte, punkte[0]])
        umfang = np.linalg.norm(np.diff(geschlossen, axis=0), axis=1).sum()

        return flaecheninhalt, umfang
        

    def weiter_klick_malen(self):
        if self.zeichnungs_status["flaeche"] is None:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet!")
            return

        flaecheninhalt, umfang = self.berechne_flaeche_und_umfang(
            self.zeichnungs_status["flaeche"],
            self.zeichnungs_status["punkte_eingezeichnet"]
        )
        self.hinweis_label.setText(f"Fläche: {flaecheninhalt:.1f} mm² | Umfang: {umfang:.1f} mm")
        self.malen_wahl_container.setVisible(False)

        if self.vermessen_modus_aktiv:
            self.vermessen_modus_aktiv = False
            self.haupt_buttons_container.setVisible(True)   
            self.navigatecontainer.setVisible(False)
        else:
            self.haupt_buttons_container.setVisible(False)
            self.farbe_wahl_container.setVisible(True) 
            self.navigatecontainer.setVisible(True)


    def farbenwahl(self, farbe: str):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Kein Scan geladen.")
            return
        elif self.zeichnungs_status["flaeche"] is None:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet")
            return
        
        save_drawn_area(
            self.zeichnungs_status["flaeche"],
            Path(self.aktueller_ordner),
            farbe,
            self.zeichnungs_status["landmarken"]
        )

        self.plotter.clear()
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.farbe_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(True)
        self.navigatecontainer.setVisible(False)

    def bereich_vermessen_start(self):
        if self.aktueller_ordner is None:
                    self.hinweis_label.setText("Erst einen Scan laden!")
                    return
        self.zeige_basis_mesh_neu()
        self.vermessung_wahl_container.setVisible(False)
        self.malen_wahl_container.setVisible(True)
        self.vermessen_modus_aktiv = True
        self.button_weiter_malen.setVisible(True)
        self.gezeichnete_flaeche = draw_main(str(self.aktueller_ordner), self.plotter, self.zeichnungs_status) 
        self.navigatecontainer.setVisible(True)


    def vermessen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        self.haupt_buttons_container.setVisible(False)
        self.vermessung_wahl_container.setVisible(True)
        self.navigatecontainer.setVisible(True)
        
    def strecke_messen_klick(self):
        self.zeige_basis_mesh_neu()
        self.plotter.disable_picking()
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(True)
        self.hinweis_label.setText("2x rechtsklicken: Start- und Endpunkt der Strecke.")

        hand_mesh = self.aktuelles_hand_mesh   
        punkte_indices = []

        def punkt_geklickt(punkt, picker):
            punkte_indices.append(hand_mesh.find_closest_point(punkt))
            if len(punkte_indices) == 2:
                self.plotter.disable_picking()
                pfad = hand_mesh.geodesic(punkte_indices[0], punkte_indices[1])
                distanz = np.linalg.norm(np.diff(pfad.points, axis=0), axis=1).sum()
                self.hinweis_label.setText(f"Strecke auf der Oberfläche: {distanz:.1f} mm")
                self.navigatecontainer.setVisible(False)
                self.haupt_buttons_container.setVisible(True)

        self.plotter.enable_point_picking(
            callback=punkt_geklickt, 
            use_picker=True, 
            show_point=True, 
            color="red", 
            point_size=20
        )

    def heatmap_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        heatmap_main(str(self.aktueller_ordner))   # Parameter an deine echte Signatur anpassen


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    fenster = HauptFenster()
    fenster.show()
    sys.exit(app.exec())