
import sys
import pyvista as p_v
import numpy as np
from pathlib import Path

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
    QLineEdit)
from PySide6.QtCore import (
    QDir, 
    Qt, 
    QEvent)
from pyvistaqt import QtInteractor

from theme import QSS
from utils import generator_bis_ende
from farberkennung import (
    finde_markierungs_punkte, 
    entferne_ausreisser_punkte, 
    baue_geschlossenen_pfad,
    schliesse_maske)
from messungen import (
    berechne_flaeche_und_umfang, 
    volumen_ab_markierung,
    volumen_ab_ring)
from farbauswahl_widget import FarbAuswahlWidget
from isolate_finger import (
    load_teilmeshe_mit_textur, 
    isolate_finger, 
    erstelle_schnitt_ellipsoid,
    lade_isolate_finger_parameter, 
    speichere_isolate_finger_parameter)
from draw_area_on_scan_experimental import (
    draw_main, 
    save_drawn_area, 
    extract_faces_of_hand, 
    get_hand_region)
from heatmap import heatmap_main


class HauptFenster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fingerscan-Viewer")
        self.resize(1920, 1080)
        self.setAcceptDrops(True)

        self.aktueller_ordner = None
        self.isolieren_ablauf = None
        self.automatisch_modus_aktiv = False
        self.zeichnungs_status = {"flaeche": None, "landmarken": None, "punkte_eingezeichnet": None}
        self.aktuelle_teile = None
        self.vermessen_modus_aktiv = False
        self.ellipsoid_kontext = None
        self.aktueller_ellipsoid_actor = None
        self.isolieren_phase = None

        zentral_widget = QWidget()
        self.setCentralWidget(zentral_widget)
        haupt_layout = QHBoxLayout(zentral_widget)

        self.knopf_spalte = QWidget()
        self.knopf_layout = QVBoxLayout(self.knopf_spalte)

        # --- Hauptmenue ---
        self.haupt_buttons_container = QWidget()
        haupt_buttons_layout = QVBoxLayout(self.haupt_buttons_container)
        self.button_isolieren = self._knopf("Finger isolieren", self.isolieren_klick, haupt_buttons_layout)
        self.button_zeichnen = self._knopf("Bereich einzeichnen", self.zeichnen_klick, haupt_buttons_layout)
        self.button_vermessen = self._knopf("Bereich / Strecke \nvermessen", self.vermessen_klick, haupt_buttons_layout)
        self.button_heatmap = self._knopf("Heatmap erzeugen", self.heatmap_klick, haupt_buttons_layout)
        self.knopf_layout.addWidget(self.haupt_buttons_container)

        # --- Isolieren-Wahl ---
        self.isolieren_wahl_container = QWidget()
        wahl_layout = QVBoxLayout(self.isolieren_wahl_container)
        self.button_automatisch = self._knopf("Automatische\nEinstellungen\nverwenden", self.automatisch_klick, wahl_layout)
        self.button_manuell = self._knopf("Selbst justieren", self.manuell_klick, wahl_layout)

        self.ellipsoid_einstellen_container = QWidget()
        ellipsoid_layout = QVBoxLayout(self.ellipsoid_einstellen_container)
        self.label_radius = QLabel("Breite: 2.00")
        self.slider_radius = self._ellipsoid_slider(100, 400, 200, ellipsoid_layout, self.label_radius)
        self.label_laenge = QLabel("Länge: 0.80")
        self.slider_laenge = self._ellipsoid_slider(30, 150, 80, ellipsoid_layout, self.label_laenge)
        self.label_unterschreitung = QLabel("Unterschreitung: 0.45")
        self.slider_unterschreitung = self._ellipsoid_slider(0, 100, 45, ellipsoid_layout, self.label_unterschreitung)
        self.button_ellipsoid_bestaetigen = self._knopf("Bestätigen", self.ellipsoid_bestaetigen_klick, ellipsoid_layout)
        self.knopf_layout.addWidget(self.ellipsoid_einstellen_container)
        self.ellipsoid_einstellen_container.setVisible(False)

        self.button_weiter = self._knopf("Weiter", self.weiter_klick, wahl_layout)
        self.button_weiter.setVisible(False)
        self.knopf_layout.addWidget(self.isolieren_wahl_container)
        self.isolieren_wahl_container.setVisible(False)

        # --- Malen-Wahl (manuell + automatisch per Farberkennung) ---
        self.malen_wahl_container = QWidget()
        malen_wahl_layout = QVBoxLayout(self.malen_wahl_container)
        self.button_weiter_malen = self._knopf("Fertig manuell\ngemalt", self.weiter_klick_malen, malen_wahl_layout)
        self.button_weiter_malen.setVisible(False)
        self.button_automatisch_einzeichnen = self._knopf(
            "Automatisch einzeichnen", self.automatisch_einzeichnen_klick, malen_wahl_layout)

        self.einzeichnen_farbwahl = FarbAuswahlWidget(standard_farbe="#000000")
        self.einzeichnen_farbwahl.button_pipette.clicked.connect(
            lambda: self.pipette_aktivieren(self.einzeichnen_farbwahl))
        malen_wahl_layout.addWidget(self.einzeichnen_farbwahl)

        self.knopf_layout.addWidget(self.malen_wahl_container)
        self.malen_wahl_container.setVisible(False)

        # --- Farbe-Wahl (Untersuchungs-Farbe beim manuellen Speichern) ---
        self.farbe_wahl_container = QWidget()
        farbe_wahl_layout = QVBoxLayout(self.farbe_wahl_container)
        for name, farbe in [("rot", "rot"), ("orange", "orange"), ("gelb", "gelb"), ("grün", "grün"), ("blau", "blau")]:
            self._knopf(f"Untersuchung 1 \n{name}", lambda checked=False, f=farbe: self.farbenwahl(f), farbe_wahl_layout)
        self.knopf_layout.addWidget(self.farbe_wahl_container)
        self.farbe_wahl_container.setVisible(False)

        # --- Vermessen-Wahl ---
        self.vermessung_wahl_container = QWidget()
        vermessung_wahl_layout = QVBoxLayout(self.vermessung_wahl_container)
        self._knopf("Eingezeichneten \nBereich / Umfang\n / Volumen\nvermessen", self.bereich_vermessen_start, vermessung_wahl_layout)
        self._knopf("Eingezeichnete \nStrecke vermessen", self.strecke_messen_klick, vermessung_wahl_layout)
        self._knopf("Volumen \nvermessen", self.volumen_messen_klick, vermessung_wahl_layout)
        self.knopf_layout.addWidget(self.vermessung_wahl_container)
        self.vermessung_wahl_container.setVisible(False)

        # --- Volumen-Container ---
        self.volumen_container = QWidget()
        volumen_layout = QVBoxLayout(self.volumen_container)
        self._knopf("Gesamtes Volumen\nberechnen", self.volumen_ganzes_mesh_messen_klick, volumen_layout)
        self._knopf("Volumen über\nmarkierter Fläche\nberechnen", self.volumen_alles_ueber_markierung, volumen_layout)
        self._knopf("Volumen ab\nGummiring\nberechnen", self.volumen_ueber_ring, volumen_layout)

        self.markierung_farbwahl = FarbAuswahlWidget(standard_farbe="#DD11ED")
        self.markierung_farbwahl.button_pipette.clicked.connect(
            lambda: self.pipette_aktivieren(self.markierung_farbwahl))
        volumen_layout.addWidget(self.markierung_farbwahl)

        self.knopf_layout.addWidget(self.volumen_container)
        self.volumen_container.setVisible(False)

        # --- Navigation ---
        self.navigatecontainer = QWidget()
        navigate_layout = QVBoxLayout(self.navigatecontainer)
        self._knopf("Zurück zum Hauptmenü", self.lade_main_menu, navigate_layout)
        self.knopf_layout.addWidget(self.navigatecontainer)
        self.navigatecontainer.setVisible(False)

        # --- Ordner-Browser (unten, 1/3 Hoehe) ---
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

        # --- Viewer ---
        self.viewer_spalte = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_spalte)
        self.hinweis_label = QLabel("Scan-Ordner per Drag-and-Drop hierher ziehen")
        self.hinweis_label.setAlignment(Qt.AlignCenter)
        viewer_layout.addWidget(self.hinweis_label)

        self.plotter = QtInteractor(self.viewer_spalte)
        self.plotter.set_background("F5F7FA")
        viewer_layout.addWidget(self.plotter.interactor)
        haupt_layout.addWidget(self.viewer_spalte, stretch=4)

    # ---------- kleine Bau-Helfer ----------

    def _knopf(self, text: str, funktion, ziel_layout) -> QPushButton:
        button = QPushButton(text)
        button.setFixedSize(192, 108)
        button.clicked.connect(funktion)
        ziel_layout.addWidget(button)
        return button

    def _ellipsoid_slider(self, minimum, maximum, start, ziel_layout, label) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(start)
        slider.valueChanged.connect(self.aktualisiere_ellipsoid_vorschau)
        ziel_layout.addWidget(label)
        ziel_layout.addWidget(slider)
        return slider

    # ---------- Drag & Drop / Laden ----------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        self.aktueller_ordner = urls[0].toLocalFile()
        pfad = Path(urls[0].toLocalFile())
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

    def lade_und_zeige(self, ordner: Path):
        try:
            obj_file = list(ordner.glob("*.obj"))
            teile = load_teilmeshe_mit_textur(obj_file)
        except Exception as e:
            self.hinweis_label.setText(f"Fehler beim Laden (ui, lade_und_zeige): {e}")
            return

        self.aktuelle_teile = teile
        self.aktuelles_hand_mesh = p_v.merge([teil for teil, tex in teile])
        self.plotter.clear()
        for pv_mesh, tex in teile:
            self.plotter.add_mesh(pv_mesh, texture=tex)
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
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.plotter.disable_picking()
        self._pipette_aktiv = False
        self.plotter.interactor.removeEventFilter(self)
        self.plotter.interactor.unsetCursor()

    # ---------- Finger isolieren ----------

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
        self.isolieren_ablauf = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=True)
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

    # ---------- Zeichnen ----------

    def zeichnen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        self.navigatecontainer.setVisible(True)
        self.haupt_buttons_container.setVisible(False)
        self.malen_wahl_container.setVisible(True)
        self.button_weiter_malen.setVisible(True)
        self.gezeichnete_flaeche = draw_main(str(self.aktueller_ordner), self.plotter, self.zeichnungs_status)

    def weiter_klick_malen(self):
        if self.zeichnungs_status["flaeche"] is None:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet!")
            return

        flaecheninhalt, umfang = berechne_flaeche_und_umfang(
            self.zeichnungs_status["flaeche"], self.zeichnungs_status["punkte_eingezeichnet"])
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
        if self.zeichnungs_status["flaeche"] is None:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet")
            return

        save_drawn_area(self.zeichnungs_status["flaeche"], Path(self.aktueller_ordner), farbe, self.zeichnungs_status["landmarken"])
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.farbe_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(True)
        self.navigatecontainer.setVisible(False)

    def automatisch_einzeichnen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return

        markierte_punkte = finde_markierungs_punkte(self.aktuelle_teile, hex_code=self.einzeichnen_farbwahl.farbe, toleranz=100.0)
        if len(markierte_punkte) < 3:
            self.hinweis_label.setText("Keine ausreichende Markierung auf dem Scan gefunden.")
            return

        markierte_punkte = entferne_ausreisser_punkte(markierte_punkte)
        pfad = baue_geschlossenen_pfad(markierte_punkte)

        mask = get_hand_region(self.aktuelles_hand_mesh, pfad)
        mask = schliesse_maske(self.aktuelles_hand_mesh, mask, schritte = 2)
        flaeche = extract_faces_of_hand(self.aktuelles_hand_mesh, mask)
        save_drawn_area(flaeche, Path(self.aktueller_ordner), "grün", {})

        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.hinweis_label.setText(f"Fläche erkannt und gespeichert ({len(pfad)} Randpunkte).")

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

    # ---------- Vermessen ----------

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

        self.plotter.enable_point_picking(callback=punkt_geklickt, use_picker=True, show_point=True, color="red", point_size=20)

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

    def volumen_alles_ueber_markierung(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        try:
            volumen, schnitt_hoehe, anzahl_markiert = volumen_ab_markierung(
                self.aktuelles_hand_mesh, self.aktuelle_teile, hex_code=self.markierung_farbwahl.farbe)
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
            f"(Schnitthöhe Z={schnitt_hoehe:.1f}, {anzahl_markiert} markierte Punkte gefunden)")

    def volumen_ueber_ring(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        try:
            volumen, schwerpunkt, normale, anzahl_markiert = volumen_ab_ring(
                self.aktuelles_hand_mesh, self.aktuelle_teile, hex_code=self.markierung_farbwahl.farbe
            )
        except ValueError as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            return

        bounds = self.aktuelles_hand_mesh.bounds
        diagonale = np.linalg.norm([bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]])
        ebene = p_v.Plane(center=schwerpunkt, direction=normale, i_size=diagonale, j_size=diagonale)
        self.plotter.add_mesh(ebene, color="yellow", opacity=0.35, name="schnitt_ebene")

        self.hinweis_label.setText(
            f"Volumen ab Ring: {volumen:.1f} mm³ ({anzahl_markiert} markierte Punkte gefunden)"
        )

    # ---------- Pipette ----------

    def pipette_aktivieren(self, ziel_widget: FarbAuswahlWidget):
        self._pipette_aktiv = True
        self._pipette_ziel_widget = ziel_widget
        self.plotter.interactor.setCursor(Qt.CrossCursor)
        self.plotter.interactor.installEventFilter(self)
        self.hinweis_label.setText("Pipette aktiv - auf den Scan klicken, um eine Farbe aufzunehmen.")

    def eventFilter(self, obj, event):
        if getattr(self, "_pipette_aktiv", False) and obj is self.plotter.interactor and event.type() == QEvent.MouseButtonPress:
            self._pipette_aktiv = False
            self.plotter.interactor.unsetCursor()
            self.plotter.interactor.removeEventFilter(self)

            position = event.position().toPoint()
            skala = self.plotter.interactor.devicePixelRatioF()
            x, y = int(position.x() * skala), int(position.y() * skala)

            bild_array = self.plotter.screenshot(return_img=True)
            hoehe, breite = bild_array.shape[:2]
            x = min(max(x, 0), breite - 1)
            y = min(max(y, 0), hoehe - 1)
            r, g, b = bild_array[y, x][:3]
            hex_code = f"#{r:02X}{g:02X}{b:02X}"

            self._pipette_ziel_widget.setze_farbe(hex_code)
            self.hinweis_label.setText(f"Farbe aufgenommen: {hex_code}")
            return True
        return super().eventFilter(obj, event)

    def heatmap_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        heatmap_main(str(self.aktueller_ordner))

