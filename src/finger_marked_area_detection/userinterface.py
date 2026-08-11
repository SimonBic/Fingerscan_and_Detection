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
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QMainWindow, 
    QApplication, 
    QLabel, 
    QVBoxLayout, 
    QWidget, 
    QHBoxLayout, 
    QPushButton, 
    QSlider, 
    QTreeView, 
    QFileSystemModel, 
    QLineEdit,
    QColorDialog, 
    QGridLayout)
from PySide6.QtCore import QDir, Qt, QEvent
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
    pfad.parent.mkdir(parents=True, exist_ok=True)
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
        self.ellipsoid_kontext = None
        self.aktueller_ellipsoid_actor = None
        self.isolieren_phase = None
        self.markierungsfarbe = "#DD11ED"  

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
        self.button_manuell.clicked.connect(self.manuell_klick)
        wahl_layout.addWidget(self.button_manuell)

        self.ellipsoid_einstellen_container = QWidget()
        ellipsoid_layout = QVBoxLayout(self.ellipsoid_einstellen_container)

        self.label_radius = QLabel("Breite: 2.00")
        self.slider_radius = QSlider(Qt.Horizontal)
        self.slider_radius.setRange(100, 400)   
        self.slider_radius.setValue(200)     
        ellipsoid_layout.addWidget(self.label_radius)
        ellipsoid_layout.addWidget(self.slider_radius)

        self.label_laenge = QLabel("Länge: 0.80")
        self.slider_laenge = QSlider(Qt.Horizontal)
        self.slider_laenge.setRange(30, 150)   
        self.slider_laenge.setValue(80)
        ellipsoid_layout.addWidget(self.label_laenge)
        ellipsoid_layout.addWidget(self.slider_laenge)

        self.label_unterschreitung = QLabel("Unterschreitung: 0.45")
        self.slider_unterschreitung = QSlider(Qt.Horizontal)
        self.slider_unterschreitung.setRange(0, 100)   
        self.slider_unterschreitung.setValue(45)
        ellipsoid_layout.addWidget(self.label_unterschreitung)
        ellipsoid_layout.addWidget(self.slider_unterschreitung)

        self.slider_radius.valueChanged.connect(self.aktualisiere_ellipsoid_vorschau)
        self.slider_laenge.valueChanged.connect(self.aktualisiere_ellipsoid_vorschau)
        self.slider_unterschreitung.valueChanged.connect(self.aktualisiere_ellipsoid_vorschau)

        self.button_ellipsoid_bestaetigen = QPushButton("Bestätigen")
        self.button_ellipsoid_bestaetigen.setFixedSize(192, 108)
        self.button_ellipsoid_bestaetigen.clicked.connect(self.ellipsoid_bestaetigen_klick)
        ellipsoid_layout.addWidget(self.button_ellipsoid_bestaetigen)

        self.knopf_layout.addWidget(self.ellipsoid_einstellen_container)
        self.ellipsoid_einstellen_container.setVisible(False)

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
        self.button_Volumen_vermessen = QPushButton("Volumen \nvermessen")

        self.button_vermessen_weiter.setFixedSize(192, 108)
        self.button_Strecke_vermessen.setFixedSize(192, 108)
        self.button_Volumen_vermessen.setFixedSize(192, 108)

        self.button_vermessen_weiter.clicked.connect(self.bereich_vermessen_start)
        self.button_Strecke_vermessen.clicked.connect(self.strecke_messen_klick)
        self.button_Volumen_vermessen.clicked.connect(self.volumen_messen_klick)

        vermessung_wahl_layout.addWidget(self.button_vermessen_weiter)
        vermessung_wahl_layout.addWidget(self.button_Strecke_vermessen)
        vermessung_wahl_layout.addWidget(self.button_Volumen_vermessen)

        self.knopf_layout.addWidget(self.vermessung_wahl_container)
        self.vermessung_wahl_container.setVisible(False)

        self.volumen_container = QWidget()  
        volumen_layout = QVBoxLayout(self.volumen_container)

        self.button_gesamtes_volumen_berechnen = QPushButton("Gesamtes Volumen\nberechnen")
        self.button_Finger_spitze_volumen_berechnen = QPushButton("Volumen über\nmarkierter Fläche\nberechnen")

        self.button_gesamtes_volumen_berechnen.setFixedSize(192, 108)
        self.button_gesamtes_volumen_berechnen.clicked.connect(self.volumen_ganzes_mesh_messen_klick)
        self.button_Finger_spitze_volumen_berechnen.setFixedSize(192, 108)
        self.button_Finger_spitze_volumen_berechnen.clicked.connect(self.volumen_Finger_spitze_messen_klick)
        


        volumen_layout.addWidget(self.button_gesamtes_volumen_berechnen)
        volumen_layout.addWidget(self.button_Finger_spitze_volumen_berechnen)

        self.farbvorschau = QLabel()
        self.farbvorschau.setFixedSize(192, 40)
        self.farbvorschau.setStyleSheet(f"background-color: {self.markierungsfarbe}; border: 2px solid #4A90D9; border-radius: 6px;")
        volumen_layout.addWidget(self.farbvorschau)

        self.slider_farbe_r = QSlider(Qt.Horizontal)
        self.slider_farbe_r.setRange(0, 255)
        self.slider_farbe_r.setValue(0xDD)          
        volumen_layout.addWidget(self.slider_farbe_r)

        self.slider_farbe_g = QSlider(Qt.Horizontal)
        self.slider_farbe_g.setRange(0, 255)
        self.slider_farbe_g.setValue(0x11)
        volumen_layout.addWidget(self.slider_farbe_g)

        self.slider_farbe_b = QSlider(Qt.Horizontal)
        self.slider_farbe_b.setRange(0, 255)
        self.slider_farbe_b.setValue(0xED)
        volumen_layout.addWidget(self.slider_farbe_b)

        self.slider_farbe_r.valueChanged.connect(self.aktualisiere_farbvorschau)
        self.slider_farbe_g.valueChanged.connect(self.aktualisiere_farbvorschau)
        self.slider_farbe_b.valueChanged.connect(self.aktualisiere_farbvorschau)

        self.slider_farbe_r.setStyleSheet("""
            QSlider::groove:horizontal { height: 10px; border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 white, stop:1 red); }
            QSlider::handle:horizontal { width: 16px; background: #4A90D9; border: 1px solid #3A73AD;
                border-radius: 8px; margin: -4px 0; }
            """)

        self.slider_farbe_g.setStyleSheet("""
            QSlider::groove:horizontal { height: 10px; border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 white, stop:1 green); }
            QSlider::handle:horizontal { width: 16px; background: #4A90D9; border: 1px solid #3A73AD;
                border-radius: 8px; margin: -4px 0; }
            """)

        self.slider_farbe_b.setStyleSheet("""
            QSlider::groove:horizontal { height: 10px; border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 white, stop:1 blue); }
            QSlider::handle:horizontal { width: 16px; background: #4A90D9; border: 1px solid #3A73AD;
                border-radius: 8px; margin: -4px 0; }
            """)

        self.button_pipette = QPushButton("Pipette (Farbe vom Scan)")
        self.button_pipette.setFixedSize(192, 40)
        self.button_pipette.clicked.connect(self.pipette_aktivieren)
        volumen_layout.addWidget(self.button_pipette)

        farb_grid = QGridLayout()
        farb_grid.setSpacing(2)
        for i, farbe in enumerate(self.erzeuge_farbpalette(50)):
            swatch = QPushButton()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(f"background-color: {farbe}; border: 1px solid #888; border-radius: 2px;")
            swatch.clicked.connect(lambda checked=False, f=farbe: self.setze_markierungsfarbe(f))
            farb_grid.addWidget(swatch, i // 10, i % 10)
        volumen_layout.addLayout(farb_grid)  

        self.knopf_layout.addWidget(self.volumen_container)
        self.volumen_container.setVisible(False)

        self.navigatecontainer = QWidget()
        navigate_layout = QVBoxLayout(self.navigatecontainer)
        self.button_main_menu = QPushButton("Zurück zum Hauptmenü")
        self.button_main_menu.setFixedSize(192, 108)
        self.button_main_menu.clicked.connect(self.lade_main_menu)
        navigate_layout.addWidget(self.button_main_menu)
        self.knopf_layout.addWidget(self.navigatecontainer)
        self.navigatecontainer.setVisible(False)

        aussen_spalte = QWidget()
        aussen_layout = QVBoxLayout(aussen_spalte)
        aussen_layout.addWidget(self.knopf_spalte, stretch=2)   
        self.ordner_browser_widget = QWidget()
        browser_layout = QVBoxLayout(self.ordner_browser_widget)

        self.pfad_eingabe = QLineEdit()
        self.pfad_eingabe.setPlaceholderText("Pfad zum Scan-Ordner bitte hier eingeben")
        self.pfad_eingabe.returnPressed.connect(self.pfad_geladen)
        browser_layout.addWidget(self.pfad_eingabe)

        self.ordner_baum = QTreeView()
        self.dateisystem_modell = QFileSystemModel()
        self.dateisystem_modell.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
        self.ordner_baum.setModel(self.dateisystem_modell)
        for spalte in range(1, 4):
            self.ordner_baum.hideColumn(spalte)   
        self.ordner_baum.clicked.connect(self.baum_klick)
        browser_layout.addWidget(self.ordner_baum)

        aussen_layout.addWidget(self.ordner_browser_widget, stretch=1)  

        haupt_layout.addWidget(aussen_spalte, stretch=1)     

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


    def pfad_geladen(self):
        pfad = self.pfad_eingabe.text().strip()
        if not Path(pfad).is_dir():
            self.hinweis_label.setText("Pfad existiert nicht oder ist kein Ordner.")
            return
        self.dateisystem_modell.setRootPath(pfad)
        self.ordner_baum.setRootIndex(self.dateisystem_modell.index(pfad))


    def baum_klick(self, index):
        pfad = Path(self.dateisystem_modell.filePath(index))
        if list(pfad.glob("*.obj")):
            self.aktueller_ordner = str(pfad)
            self.lade_und_zeige(pfad)


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
        self.volumen_container.setVisible(False)
        self.plotter.clear()
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.zeige_basis_mesh_neu()
        self.plotter.disable_picking()
        self._pipette_aktiv = False                          
        self.plotter.interactor.removeEventFilter(self)       
        self.plotter.interactor.unsetCursor() 

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
        self.button_automatisch.setVisible(False)   
        self.button_manuell.setVisible(False) 
        ordner = Path(self.aktueller_ordner)
        self.isolieren_ablauf = isolate_finger(str(ordner), plotter = self.plotter, zeige_zwischenschritte=True)
        self.isolieren_phase = "picking"
        self.button_weiter.setVisible(True)
        self.navigatecontainer.setVisible(True)
        next(self.isolieren_ablauf)

    def weiter_klick(self):
        self.navigatecontainer.setVisible(False)
        if getattr(self, "automatisch_modus_aktiv", False):
            
            self.automatisch_modus_aktiv = False
            self.button_weiter.setText("Weiter")
            self.button_weiter.setVisible(False)

            try:
                gespeicherter_obj_pfad = generator_bis_ende(self.isolieren_ablauf)  
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

        if getattr(self, "isolieren_phase", None) == "picking":  
            self.isolieren_phase = "ellipsoid"
            self.button_weiter.setVisible(False)
            self.ellipsoid_kontext = next(self.isolieren_ablauf)  
            self.ellipsoid_einstellen_container.setVisible(True)
            self.aktualisiere_ellipsoid_vorschau()
            return

        try:
            next(self.isolieren_ablauf)
        except StopIteration:
            self.button_weiter.setVisible(False)
            self.isolieren_wahl_container.setVisible(False)
            self.haupt_buttons_container.setVisible(True)


    def aktualisiere_ellipsoid_vorschau(self):
        from isolate_finger import erstelle_schnitt_ellipsoid

        if self.aktueller_ellipsoid_actor is not None:
            self.plotter.remove_actor(self.aktueller_ellipsoid_actor, reset_camera=False)

        radius_faktor = self.slider_radius.value() / 100
        laengen_faktor = self.slider_laenge.value() / 100
        unterschreitung = self.slider_unterschreitung.value() / 100

        self.label_radius.setText(f"Breite: {radius_faktor:.2f}")
        self.label_laenge.setText(f"Länge: {laengen_faktor:.2f}")
        self.label_unterschreitung.setText(f"Unterschreitung: {unterschreitung:.2f}")

        ellipsoid = erstelle_schnitt_ellipsoid(
            self.ellipsoid_kontext["avg_point_of_hurt_finger"],
            self.ellipsoid_kontext["normale"],
            self.ellipsoid_kontext["verwendete_vertices"],
            self.ellipsoid_kontext["tiefster_punkt"],
            radius_faktor=radius_faktor, laengen_faktor=laengen_faktor, unterschreitung=unterschreitung,
        )
        self.aktueller_ellipsoid_actor = self.plotter.add_mesh(ellipsoid, color="darkcyan", opacity=0.3)
        self.plotter.render()   


    def ellipsoid_bestaetigen_klick(self):
        werte = {
            "radius_faktor": self.slider_radius.value() / 100,
            "laengen_faktor": self.slider_laenge.value() / 100,
            "unterschreitung": self.slider_unterschreitung.value() / 100,
        }
        ordner = Path(self.aktueller_ordner)
        self.ellipsoid_einstellen_container.setVisible(False)
        self.navigatecontainer.setVisible(False)          

        speichere_isolate_finger_parameter(ordner, **werte)

        try:
            self.isolieren_ablauf.send(werte)
            self.hinweis_label.setText("Unerwarteter weiterer Zwischenschritt - bitte melden.")
            return
        except StopIteration as e:
            gespeicherter_obj_pfad = e.value

        self.aktueller_ordner = Path(gespeicherter_obj_pfad)   
        self.isolieren_phase = None
        self.isolieren_wahl_container.setVisible(False)         
        self.haupt_buttons_container.setVisible(True)
        self.lade_und_zeige(Path(gespeicherter_obj_pfad))


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


    def finde_markierungs_punkte(self,teile: list, hex_code: str, toleranz: float = 40.0) -> np.ndarray:
        ziel_rgb = np.array([int(hex_code.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)])

        alle_markierten_punkte = []
        for pv_mesh, tex in teile:
            if pv_mesh.active_texture_coordinates is None:
                continue
            uv = pv_mesh.active_texture_coordinates
            bild_array = tex.to_array()
            hoehe, breite = bild_array.shape[:2]

            x_pixel = np.clip((uv[:, 0] * (breite - 1)).astype(int), 0, breite - 1)
            y_pixel = np.clip(((1 - uv[:, 1]) * (hoehe - 1)).astype(int), 0, hoehe - 1)

            vertex_farben = bild_array[y_pixel, x_pixel]
            distanzen = np.linalg.norm(vertex_farben.astype(float) - ziel_rgb, axis=1)
            maske = distanzen < toleranz

            if maske.any():
                alle_markierten_punkte.append(pv_mesh.points[maske])

        if not alle_markierten_punkte:
            return np.empty((0, 3))
        return np.vstack(alle_markierten_punkte)


    def volumen_ab_markierung(self,hand_mesh: p_v.PolyData, teile: list, hex_code: str = "#DD11ED", toleranz: float = 40.0):
        markierte_punkte = self.finde_markierungs_punkte(teile, hex_code, toleranz)
        if len(markierte_punkte) == 0:
            raise ValueError(f"Keine Markierung mit Farbe {hex_code} gefunden.")

        schnitt_hoehe = markierte_punkte[:, 2].mean()
        geschnitten = hand_mesh.clip(normal=(0, 0, 1), origin=(0, 0, schnitt_hoehe), invert=False)

        return geschnitten.volume, schnitt_hoehe, len(markierte_punkte)

    def volumen_messen_klick(self):
        self.volumen_container.setVisible(True)
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(True)


    def volumen_ganzes_mesh_messen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        volumen = self.aktuelles_hand_mesh.volume
        self.hinweis_label.setText(f"Volumen des gesamten Mesh: {volumen:.1f} mm³")

    def volumen_Finger_spitze_messen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        try:
            volumen, schnitt_hoehe, anzahl_markiert = self.volumen_ab_markierung(
                self.aktuelles_hand_mesh, self.aktuelle_teile, hex_code=self.markierungsfarbe
            )
        except ValueError as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            return

        bounds = self.aktuelles_hand_mesh.bounds
        mitte_x = (bounds[0] + bounds[1]) / 2
        mitte_y = (bounds[2] + bounds[3]) / 2
        breite = (bounds[1] - bounds[0]) * 1.5
        tiefe = (bounds[3] - bounds[2]) * 1.5

        ebene = p_v.Plane(center=(mitte_x, mitte_y, schnitt_hoehe), direction=(0, 0, 1), i_size=breite, j_size=tiefe)
        self.plotter.add_mesh(ebene, color="yellow", opacity=0.35, name="schnitt_ebene")

        self.hinweis_label.setText(
            f"Volumen ab Markierung: {volumen:.1f} mm³ "
            f"(Schnitthöhe Z={schnitt_hoehe:.1f}, {anzahl_markiert} markierte Punkte gefunden)"
        )

    def aktualisiere_farbvorschau(self):
        hex_code = f"#{self.slider_farbe_r.value():02X}{self.slider_farbe_g.value():02X}{self.slider_farbe_b.value():02X}"
        self.markierungsfarbe = hex_code
        self.farbvorschau.setStyleSheet(f"background-color: {hex_code}; border: 2px solid #4A90D9; border-radius: 6px;")


    def setze_markierungsfarbe(self, hex_code: str):
        self.markierungsfarbe = hex_code
        self.farbvorschau.setStyleSheet(f"background-color: {hex_code}; border: 2px solid #4A90D9; border-radius: 6px;")

        # Slider mitziehen, damit alle 3 Wege (Slider/Grid/Pipette) synchron bleiben
        r, g, b = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
        self.slider_farbe_r.blockSignals(True); self.slider_farbe_r.setValue(r); self.slider_farbe_r.blockSignals(False)
        self.slider_farbe_g.blockSignals(True); self.slider_farbe_g.setValue(g); self.slider_farbe_g.blockSignals(False)
        self.slider_farbe_b.blockSignals(True); self.slider_farbe_b.setValue(b); self.slider_farbe_b.blockSignals(False)


    def erzeuge_farbpalette(self, anzahl = 81):
        import colorsys
        farben = []
        for i in range(anzahl):
            h = i / anzahl
            s = 0.85 if i % 2 == 0 else 0.55
            v = 0.9 if i % 3 != 0 else 0.65
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            farben.append('#{:02X}{:02X}{:02X}'.format(int(r*255), int(g*255), int(b*255)))
        return farben


    def pipette_aktivieren(self):
        self._pipette_aktiv = True
        self.plotter.interactor.setCursor(Qt.CrossCursor)
        self.plotter.interactor.installEventFilter(self)
        self.hinweis_label.setText("Pipette aktiv - auf den Scan klicken, um eine Farbe aufzunehmen.")

    def eventFilter(self, obj, event):
        if getattr(self, "_pipette_aktiv", False) and obj is self.plotter.interactor and event.type() == QEvent.MouseButtonPress:
            self._pipette_aktiv = False
            self.plotter.interactor.unsetCursor()
            self.plotter.interactor.removeEventFilter(self)

            position = event.position().toPoint()
            skala = self.plotter.interactor.devicePixelRatioF()   # HiDPI-Korrektur
            x, y = int(position.x() * skala), int(position.y() * skala)

            bild_array = self.plotter.screenshot(return_img=True)
            hoehe, breite = bild_array.shape[:2]
            x = min(max(x, 0), breite - 1)
            y = min(max(y, 0), hoehe - 1)
            r, g, b = bild_array[y, x][:3]

            self.setze_markierungsfarbe(f"#{r:02X}{g:02X}{b:02X}")
            self.hinweis_label.setText(f"Farbe aufgenommen: {self.markierungsfarbe}")
            return True
        return super().eventFilter(obj, event)

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