
import sys
from matplotlib import container
import pyvista as p_v
import numpy as np
from pathlib import Path
from collections import defaultdict

from PySide6.QtWidgets import (
    QMainWindow, 
    QApplication, 
    QLabel,
    QVBoxLayout, 
    QWidget, 
    QHBoxLayout,
    QGridLayout,
    QPushButton, 
    QSlider, 
    QLineEdit,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QDialog,
    QFileDialog,
    QDialogButtonBox,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    )
from PySide6.QtCore import (
    Qt,
    QEvent,
    QSize,
    QSettings,
    QUrl,
    )
from PySide6.QtGui import (
    QIcon,
    QDesktopServices,
    QPixmap,
)
from pyvistaqt import QtInteractor

from theme import QSS
from utils import generator_bis_ende
from farberkennung import (
    finde_markierungs_punkte,
    entferne_ausreisser_punkte,
    baue_geschlossenen_pfad)
from messungen import (
    berechne_flaeche_und_umfang, 
    volumen_ab_markierung,
    volumen_ab_ring, 
    volumen_ab_fingerzwischenfalte,
    volumen_gesamtes_mesh)
from farbauswahl_widget import FarbAuswahlWidget
from isolate_finger import (
    load_teilmeshe_mit_textur,
    isolate_finger,
    erstelle_schnitt_ellipsoid,
    finger_normale,
    lade_isolate_finger_parameter,
    speichere_isolate_finger_parameter)
from draw_area_on_scan import (
    draw_main, 
    save_drawn_area, 
    extract_faces_of_hand,
    schneide_flaeche_aus_loop,
    lese_markierungsfarbe)
from vermessung_speichern import (
    baue_zahl_fuer_messung,
    speichere_vermessung,
    schreibe_ergebnis_liste,
    vermessungs_ordner)
from heatmap3D import (
    baue_3d_genesungsverlauf,
    speichere_genesungsverlauf,
    finde_markierte_scans,
    lade_markierung,
    finde_nagel_normale,
    rotationsmatrix_um_z_fuer_nagel_ausrichtung,
    isolierte_scan_name_aus_markierung,
    baue_farbgruppen_aus_gewinner,
    farb_prioritaet)
from heatmap2D import heatmap_main

# Hoehe des Hinweis-Labels ueber dem 3D-Viewer: mindestens eine Zeile,
# hoechstens HINWEIS_MAX_ZEILEN - darueber hinaus wird gescrollt.
KNOPF_BREITE = 192
NAV_KNOPF_BREITE = 80   # Patient-Avatar und Untersuchungs-Knopf
PIKTO_GROESSE = 34      # Typ-Piktogramme links neben der Untersuchung
NAV_ABSTAND = 4         # zwischen Piktogramm und Knopf, und Rand der Nav-Spalte
KNOPF_HOEHE = 108
HINWEIS_MAX_ZEILEN = 3
HINWEIS_RAND = 8
ICON_ORDNER = Path(__file__).parent / "icons"

class HinweisBereich(QScrollArea):
    """Scroll-Bereich fuers Hinweis-Label, der genau so hoch wird wie sein
    Inhalt - mindestens eine, hoechstens HINWEIS_MAX_ZEILEN Zeilen.

    Noetig, weil QScrollArea seinen sizeHint NICHT vom eingesetzten Widget
    ableitet: ohne diese Ueberschreibung waere der Bereich immer so hoch
    wie erlaubt, also auch bei einer einzigen Zeile drei Zeilen hoch."""

    def _gewuenschte_hoehe(self) -> int:
        hinweis = self.widget()
        if hinweis is None:
            return super().sizeHint().height()

        zeilen_hoehe = hinweis.fontMetrics().lineSpacing()
        noetige_hoehe = hinweis.sizeHint().height()
        hoehe = min(max(noetige_hoehe, zeilen_hoehe), zeilen_hoehe * HINWEIS_MAX_ZEILEN)

        return hoehe + HINWEIS_RAND

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self._gewuenschte_hoehe())

    def minimumSizeHint(self) -> QSize:
        # Muss ebenfalls ueberschrieben werden: QAbstractScrollArea meldet
        # sonst eine Mindesthoehe aus Rahmen und Scrollbar-Breite, die
        # groesser als eine Textzeile ist und den sizeHint aushebelt.
        return QSize(super().minimumSizeHint().width(), self._gewuenschte_hoehe())


class HinweisLabel(QLabel):
    """QLabel, das seinen HinweisBereich nach jeder Textaenderung neu
    vermessen laesst. Ohne das bliebe der Bereich auf der Hoehe stehen,
    die er beim ersten Anzeigen hatte - QLabel.setText() loest von sich
    aus keine Neuberechnung im umgebenden Layout aus."""

    def setText(self, text: str) -> None:
        super().setText(text)
        self.updateGeometry()

        bereich = self.parentWidget()
        while bereich is not None and not isinstance(bereich, HinweisBereich):
            bereich = bereich.parentWidget()

        if bereich is not None:
            bereich.updateGeometry()
            bereich.verticalScrollBar().setValue(0)   # neue Meldung von oben zeigen


class HauptFenster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fingerscan-Viewer")
        self.resize(1920, 1080)
        self.setAcceptDrops(True)

        self.einstellungen = QSettings("UKR", "Fingerscan-Viewer")
        self.root_ordner = self.einstellungen.value("root_ordner", "")

        self.aktueller_ordner = None
        self.isolieren_ablauf = None
        self.automatisch_modus_aktiv = False
        self.zeichnungs_status = {"flaeche": None, "landmarken": None, "punkte_eingezeichnet": None}
        self.aktuelle_teile = None
        # Mehrfach-Vermessung: je Eintrag
        # {"flaeche", "flaeche_mm2", "umfang_mm", "actor", "zahl_actor"}
        self.vermessungen = []
        self.ellipsoid_kontext = None
        self.aktueller_ellipsoid_actor = None
        self.isolieren_phase = None
        self.genesungsverlauf_warteschlange = []
        self.genesungsverlauf_index = 0
        self.genesungsverlauf_gewinner = {}
        self.genesungsverlauf_aktuell_rotiert = None
        self._genesungsverlauf_mesh_fuer_klick = None

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
        self.button_heatmap = self._knopf("2D Heatmap /\nGenesungsverlauf\nerzeugen", self.heatmap_klick, haupt_buttons_layout)
        self.button_genesungsverlauf = self._knopf("3D Heatmap/\nGenesungsverlauf\nerzeugen", self.genesungsverlauf_3d_klick, haupt_buttons_layout)
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
        self.label_pca_punkte = QLabel("PCA-Punkte: 3000")
        self.slider_pca_punkte = self._ellipsoid_slider(200, 20000, 3000, ellipsoid_layout, self.label_pca_punkte)
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

        # --- Vermessen-Malen (mehrere Flaechen nacheinander) ---
        self.vermessen_malen_container = QWidget()
        vermessen_malen_layout = QVBoxLayout(self.vermessen_malen_container)
        self._knopf("Messung(en)\nspeichern", self.vermessungen_speichern_klick, vermessen_malen_layout)
        self._knopf("Letzte Fläche\nzurücknehmen", self.letzte_flaeche_zuruecknehmen, vermessen_malen_layout)
        self.knopf_layout.addWidget(self.vermessen_malen_container)
        self.vermessen_malen_container.setVisible(False)

        # --- Farbe-Wahl (Untersuchungs-Farbe beim manuellen Speichern) ---
        self.farbe_wahl_container = QWidget()
        farbe_wahl_layout = QVBoxLayout(self.farbe_wahl_container)
        num_untersuchung = 1
        for name, farbe in [("rot", "rot"), ("orange", "orange"), ("gelb", "gelb"), ("grün", "grün"), ("blau", "blau")]:
            self._knopf(f"Untersuchung {num_untersuchung} \n{name}", lambda checked=False, f=farbe: self.farbenwahl(f), farbe_wahl_layout)
            num_untersuchung = num_untersuchung + 1
        num_untersuchung = 1
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
        self._knopf("Gesamtes Volumen\nberechnen", self.volumen_ganzes_mesh_messen_klick, volumen_layout, x = 192, y = 60)
        self._knopf("Volumen über markierter\n Fläche berechnen", self.volumen_alles_ueber_markierung, volumen_layout, x = 192, y = 60)
        self._knopf("Volumen ab\nGummiring berechnen", self.volumen_ueber_ring, volumen_layout, x = 192, y = 60)
        self._knopf("Volumen ab Höhe der\nZwischnfingerfalte", self.volumen_ab_fingerzwischenfalte_klick, volumen_layout, x = 192, y = 60)

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

        

        # --- Knopf-Spalte ganz links ins Haupt-Layout ---
        haupt_layout.addWidget(self.knopf_spalte)

        # --- Navigations-Spalte ganz rechts, feste Breite ---
        self.nav_spalte = QScrollArea()
        self.nav_spalte.setFrameShape(QFrame.NoFrame)
        self.nav_spalte.setWidgetResizable(True)
        self.nav_spalte.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Genau so breit wie der Inhalt: Rand | Piktogramm | Abstand | Avatar | Rand,
        # plus Platz fuer die senkrechte Scrollleiste. Die wird fest reserviert,
        # sonst schiebt sie sich bei vielen Patienten ueber die Avatare.
        self.nav_spalte.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.nav_spalte.verticalScrollBar().ensurePolished()
        inhalt_breite = NAV_ABSTAND + PIKTO_GROESSE + NAV_ABSTAND + NAV_KNOPF_BREITE + NAV_ABSTAND
        self.nav_spalte.setFixedWidth(inhalt_breite + self.nav_spalte.verticalScrollBar().sizeHint().width())

        self.nav_inhalt = QWidget()
        self.nav_layout = QVBoxLayout(self.nav_inhalt)
        self.nav_layout.setAlignment(Qt.AlignTop)
        self.nav_layout.setContentsMargins(NAV_ABSTAND, NAV_ABSTAND, NAV_ABSTAND, NAV_ABSTAND)
        self.nav_layout.setSpacing(6)
        self.nav_spalte.setWidget(self.nav_inhalt)

        # Einstellungsknopf oben in die Spalte
        self.button_einstellungen = QToolButton()
        self.button_einstellungen.setObjectName("zahnrad_knopf")
        self.button_einstellungen.setText("⚙")
        self.button_einstellungen.setToolTip("Einstellungen")
        self.button_einstellungen.clicked.connect(self.einstellungen_oeffnen)
        self.nav_layout.addWidget(self.button_einstellungen, alignment=Qt.AlignRight)

        # Zustand fürs Akkordeon
        self._offener_patient = None
        self._offene_untersuchung = None

        # --- Viewer ---
        self.viewer_spalte = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_spalte)
        self.hinweis_label = HinweisLabel("Scan-Ordner per Drag-and-Drop hierher ziehen")
        self.hinweis_label.setAlignment(Qt.AlignCenter)
        # ensurePolished() zieht die Schriftgroesse aus dem Stylesheet in die
        # Font-Metriken. Ohne das rechnet lineSpacing() noch mit der
        # Standardschrift und die Hoehen unten waeren zu klein.
        self.hinweis_label.ensurePolished()

        # Bei mehreren Messungen wird das Label mehrzeilig. Es soll mindestens
        # eine und hoechstens drei Zeilen hoch sein - alles darueber wird
        # scrollbar, damit der 3D-Viewer nicht immer weiter schrumpft.
        self.hinweis_bereich = HinweisBereich()
        self.hinweis_bereich.setWidget(self.hinweis_label)
        self.hinweis_bereich.setWidgetResizable(True)
        self.hinweis_bereich.setFrameShape(QFrame.NoFrame)
        self.hinweis_bereich.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Vertikal Fixed, damit das Layout genau den sizeHint von
        # HinweisBereich nimmt statt den Bereich auf die Maximalhoehe
        # aufzublasen.
        self.hinweis_bereich.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        zeilen_hoehe = self.hinweis_label.fontMetrics().lineSpacing()
        self.hinweis_bereich.setMinimumHeight(zeilen_hoehe + HINWEIS_RAND)
        self.hinweis_bereich.setMaximumHeight(zeilen_hoehe * HINWEIS_MAX_ZEILEN + HINWEIS_RAND)
        viewer_layout.addWidget(self.hinweis_bereich)

        self.plotter = QtInteractor(self.viewer_spalte)
        self.plotter.set_background("F5F7FA")
        viewer_layout.addWidget(self.plotter.interactor)
        haupt_layout.addWidget(self.viewer_spalte, stretch=4)

        # ganz rechts, nach dem Viewer
        haupt_layout.addWidget(self.nav_spalte)

        # --- Buttons im Viewer, oben rechts ---
        self.overlay_buttons = []

        # self.button_speichere_genesungsverlauf_overlay = QPushButton("Genesungsverlauf\nspeichern", self.viewer_spalte)
        # self.button_speichere_genesungsverlauf_overlay.setFixedSize(160, 80)
        # self.button_speichere_genesungsverlauf_overlay.setVisible(False)
        # self.button_speichere_genesungsverlauf_overlay.clicked.connect(self.genesungsverlauf_speichern_klick)
        # self.overlay_buttons.append(self.button_speichere_genesungsverlauf_overlay)

        self.button_naechster_finger_overlay = QPushButton("Nächsten Finger\nmarkieren", self.viewer_spalte)
        self.button_naechster_finger_overlay.setFixedSize(160, 80)
        self.button_naechster_finger_overlay.clicked.connect(self.naechster_finger_markieren_klick)
        self.button_naechster_finger_overlay.setVisible(False)   
        self.overlay_buttons.append(self.button_naechster_finger_overlay)

        self.button_abbruch_overlay = QPushButton("Abbrechen", self.viewer_spalte)
        self.button_abbruch_overlay.setFixedSize(160, 80)
        self.button_abbruch_overlay.setVisible(False)
        self.button_abbruch_overlay.clicked.connect(self.lade_main_menu)
        self.overlay_buttons.append(self.button_abbruch_overlay)

        self.button_abbruch_overlay.setObjectName("overlay_button")
        self.button_naechster_finger_overlay.setObjectName("overlay_button")

        self.viewer_spalte.installEventFilter(self)
        self._positioniere_overlay_buttons()

        self._root_ordner_anwenden()
        self.baum_neu_aufbauen()
    # ---------- kleine Bau-Helfer ----------

    def _knopf(self, text: str, funktion, ziel_layout, x = KNOPF_BREITE, y = KNOPF_HOEHE) -> QPushButton:
        button = QPushButton(text)
        button.setFixedSize(x, y)
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


    def _positioniere_overlay_buttons(self):
        rand = 10
        y = rand
        for button in self.overlay_buttons:
            button.move(self.viewer_spalte.width() - button.width() - rand, y)
            button.raise_()
            y += button.height() + rand 

    # ---------- Drag & Drop / Laden / Einstellungen ----------

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

    def _rendere_teile(self, teile: list) -> None:
        for pv_mesh, tex in teile:

            if tex is not None:
                # -----------------------------------------
                # Mesh besitzt eine JPG/PNG-Textur
                # -----------------------------------------
                self.plotter.add_mesh(
                    pv_mesh,
                    texture=tex,
                    smooth_shading=False
                )

            elif "RGB" in pv_mesh.point_data:
                # -----------------------------------------
                # Mesh besitzt Vertex-Farben
                # -----------------------------------------
                self.plotter.add_mesh(
                    pv_mesh,
                    scalars="RGB",
                    rgb=True,
                    smooth_shading=True
                )

            else:
                # -----------------------------------------
                # Fallback: Mesh ohne Farbe/Textur
                # -----------------------------------------
                self.plotter.add_mesh(
                    pv_mesh,
                    smooth_shading=False
                )

    def lade_und_zeige(self, pfad: Path):
        self.plotter.clear()
        teile = load_teilmeshe_mit_textur(pfad)

        if not teile:
            print("Keine gültigen Meshes gefunden.")
            return

        self.aktuelle_teile = teile
        self.aktuelles_hand_mesh = p_v.merge([teil for teil, tex in teile])

        self._rendere_teile(teile)

    def zeige_basis_mesh_neu(self):
        self.plotter.clear()
        self._rendere_teile(self.aktuelle_teile)

    def lade_main_menu(self):
        self.haupt_buttons_container.setVisible(True)
        self.isolieren_wahl_container.setVisible(False)
        self.malen_wahl_container.setVisible(False)
        self.vermessen_malen_container.setVisible(False)
        self.farbe_wahl_container.setVisible(False)
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(False)
        self.volumen_container.setVisible(False)
        self.vermessungen.clear()
        for button in (self.overlay_buttons):
            button.setVisible(False)
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.plotter.disable_picking()
        self._pipette_aktiv = False
        self.plotter.interactor.removeEventFilter(self)
        self.plotter.interactor.unsetCursor()

    def einstellungen_oeffnen(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Einstellungen")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Root-Ordner (wird beim Start automatisch geöffnet):"))

        # Eingabefeld, vorbelegt mit dem aktuellen Wert
        pfad_zeile_layout = QHBoxLayout()
        pfad_eingabe = QLineEdit(self.root_ordner)
        button_durchsuchen = QPushButton("Files durchsuchen")
        pfad_zeile_layout.addWidget(pfad_eingabe)
        pfad_zeile_layout.addWidget(button_durchsuchen)
        layout.addLayout(pfad_zeile_layout)

        # öffnet  Ordner-Auswahldialog
        def durchsuchen():
            ordner = QFileDialog.getExistingDirectory(dialog, "Root-Ordner wählen", pfad_eingabe.text() or str(Path.home()))
            if ordner:
                pfad_eingabe.setText(ordner)
        button_durchsuchen.clicked.connect(durchsuchen)

        # OK / Abbrechen
        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(knoepfe)
        knoepfe.rejected.connect(dialog.reject)

        def speichern():
            eingabe = pfad_eingabe.text().strip()
            p = Path(eingabe).expanduser()
            if not p.is_dir():
                self.hinweis_label.setText("Kein gültiger Ordner, Einstellung nicht gespeichert.")
                return
            self.root_ordner = str(p)
            self.einstellungen.setValue("root_ordner", self.root_ordner)
            self._root_ordner_anwenden()
            dialog.accept()
        knoepfe.accepted.connect(speichern)

        dialog.exec()

    def _root_ordner_anwenden(self):
        if not self.root_ordner or not Path(self.root_ordner).is_dir():
            return
        self.baum_neu_aufbauen()

    TYP_ORDNER = ["originale_scans", "isolierte_scans", "markierte_scans", "vermessene_scans"]

    def _scan_analysieren(self, scan_name):
        # Vermessen wird auf einem beliebigen Scan (original, isoliert,
        # markiert) - die Herkunft kommt ins Label, damit sich zwei
        # Vermessungen derselben Untersuchung nicht ueberschreiben.
        if scan_name.endswith("_vermessen"):
            basis, herkunft = self._scan_analysieren(scan_name[:-len("_vermessen")])
            return basis, f"vermessen – {herkunft}"
        if scan_name.endswith("_isoliert_marked"):
            return scan_name[:-len("_isoliert_marked")], "markiert (vom isolierten)"
        if scan_name.endswith("_marked"):
            return scan_name[:-len("_marked")], "markiert (vom Original)"
        if scan_name.endswith("_isoliert"):
            return scan_name[:-len("_isoliert")], "isoliert"
        return scan_name, "original"

    def baum_neu_aufbauen(self):
        """Baut die Navigations-Spalte: Patienten als Avatar-Knoepfe,
        darunter aufklappbar die Untersuchungen, darunter die Typ-Piktogramme."""
        # Alte Patienten-Widgets entfernen (Einstellungsknopf behalten)
        while self.nav_layout.count() > 1:
            item = self.nav_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        self._offener_patient = None
        self._offene_untersuchung = None
        self._patient_aufklapp_widgets = {}

        if not self.root_ordner or not Path(self.root_ordner).is_dir():
            return

        root = Path(self.root_ordner)
        for patient_ordner in sorted(p for p in root.iterdir() if p.is_dir()):
            struktur = self._untersuchungen_sammeln(patient_ordner)
            if not struktur:
                continue
            self._patient_block_bauen(patient_ordner, struktur)


    def _untersuchungen_sammeln(self, patient_ordner):
        """{untersuchung_basis: {typ_label: pfad}}, lexikografisch nach Basis."""
        untersuchungen = defaultdict(dict)
        for typ in self.TYP_ORDNER:
            typ_pfad = patient_ordner / typ
            if not typ_pfad.is_dir():
                continue
            for scan in sorted(s for s in typ_pfad.iterdir() if s.is_dir()):
                basis, label = self._scan_analysieren(scan.name)
                untersuchungen[basis][label] = str(scan)
        return dict(sorted(untersuchungen.items()))


    def _patient_block_bauen(self, patient_ordner, struktur):
        patient_name = patient_ordner.name
        # Avatar-Knopf
        patient_knopf = QToolButton()
        patient_knopf.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        patient_knopf.setFixedSize(NAV_KNOPF_BREITE, NAV_KNOPF_BREITE)
        patient_knopf.setIconSize(QSize(44, 44))
        patient_knopf.setIcon(QIcon(str(ICON_ORDNER / "person.svg")))
        patient_knopf.setText(patient_name)
        patient_knopf.setObjectName("patient_knopf")

        # Zeile: [Patienten-Piktogramme] [Avatar] - gleiche Aufteilung wie
        # die Untersuchungs-Zeilen darunter, damit der Avatar buendig ueber
        # den Untersuchungs-Knoepfen sitzt.
        patient_zeile = QWidget()
        pz_layout = QHBoxLayout(patient_zeile)
        pz_layout.setContentsMargins(0, 0, 0, 0)
        pz_layout.setSpacing(NAV_ABSTAND)

        # Senkrechte Spalte fuer alles, was den ganzen Patienten betrifft
        # (3D-Verlauf, 2D-Heatmap). Zwei Knoepfe passen neben den Avatar.
        patient_piktos = QWidget()
        patient_piktos.setFixedWidth(PIKTO_GROESSE)
        pp_layout = QVBoxLayout(patient_piktos)
        pp_layout.setContentsMargins(0, 0, 0, 0)
        pp_layout.setSpacing(NAV_ABSTAND)
        pp_layout.setAlignment(Qt.AlignTop)

        patient_knoepfe = [k for k in (self._genesungsverlauf_knopf_bauen(patient_ordner),
                                       self._heatmap_2d_knopf_bauen(patient_ordner))
                           if k is not None]
        for k in patient_knoepfe:
            pp_layout.addWidget(k)

        pz_layout.addWidget(patient_piktos)
        pz_layout.addWidget(patient_knopf)
        self.nav_layout.addWidget(patient_zeile, alignment=Qt.AlignLeft)

        # Container fuer die Untersuchungen (anfangs versteckt).
        # Raster: Spalte 0 = Piktogramme, Spalte 1 = Untersuchungs-Knopf.
        untersuchungen_container = QWidget()
        uc_layout = QGridLayout(untersuchungen_container)
        uc_layout.setContentsMargins(0, 0, 0, 0)
        uc_layout.setHorizontalSpacing(NAV_ABSTAND)
        uc_layout.setVerticalSpacing(3)
        # Spalte 0 behaelt ihre Breite auch wenn die Piktogramme versteckt
        # sind - sonst springt der Untersuchungs-Knopf beim Aufklappen zur Seite.
        uc_layout.setColumnMinimumWidth(0, PIKTO_GROESSE)
        untersuchungen_container.setVisible(False)
        self.nav_layout.addWidget(untersuchungen_container, alignment=Qt.AlignLeft)

        # Untersuchungen generisch nummeriert
        for nummer, (basis, typen) in enumerate(struktur.items(), start=1):
            self._untersuchung_block_bauen(uc_layout, nummer - 1, nummer, typen)

        # Patienten-Piktogramme nur bei aufgeklapptem Patienten zeigen
        aufklapp_widgets = [untersuchungen_container, *patient_knoepfe]
        self._patient_aufklapp_widgets[patient_name] = aufklapp_widgets
        patient_knopf.clicked.connect(
            lambda _, w=aufklapp_widgets: self._patient_toggle(w)
        )

    def _genesungsverlauf_knopf_bauen(self, patient_ordner):
        """Heatmap-Knopf fuer den neuesten gespeicherten Genesungsverlauf,
        None wenn der Patient keinen hat."""
        verlauf_ordner = patient_ordner / "genesungsverlauf"
        if not verlauf_ordner.is_dir():
            return None
        verlaeufe = [v for v in verlauf_ordner.iterdir() if v.is_dir() and list(v.glob("*.obj"))]
        if not verlaeufe:
            return None
        neuester = max(verlaeufe, key=lambda v: v.stat().st_mtime)

        return self._patient_pikto(
            "heatmap3D.svg", f"3D-Genesungsverlauf: {neuester.name}",
            lambda _, pf=neuester: self._scan_laden_aus_pfad(pf))

    def _heatmap_2d_knopf_bauen(self, patient_ordner):
        """Knopf fuer die 2D-Heatmap aus heatmap_main(), None wenn es keine gibt."""
        bild = patient_ordner / "heatmap" / "Genesungsverlauf.png"
        if not bild.is_file():
            return None
        return self._patient_pikto(
            "heatmap2D.svg", "2D-Heatmap / Genesungsverlauf",
            lambda _, pf=bild: self._bild_zeigen(pf))

    def _patient_pikto(self, icon_datei, tooltip, slot):
        knopf = QToolButton()
        knopf.setIconSize(QSize(28, 28))
        knopf.setFixedSize(PIKTO_GROESSE, PIKTO_GROESSE)
        knopf.setIcon(QIcon(str(ICON_ORDNER / icon_datei)))
        knopf.setToolTip(tooltip)
        knopf.clicked.connect(slot)
        knopf.setVisible(False)
        return knopf


    def _untersuchung_block_bauen(self, eltern_layout, zeile, nummer, typen):
        # Gleiche Breite wie der Patient-Avatar darueber; der Text braucht
        # dafuer den Umbruch.
        u_knopf = QPushButton(f"Untersuchung\n{nummer}")
        u_knopf.setObjectName("untersuchung_knopf")
        u_knopf.setFixedWidth(NAV_KNOPF_BREITE)
        eltern_layout.addWidget(u_knopf, zeile, 1, alignment=Qt.AlignTop)

        # Piktogramm-Spalte links daneben (anfangs versteckt)
        pikto_container = QWidget()
        pikto_container.setFixedWidth(PIKTO_GROESSE)
        p_layout = QVBoxLayout(pikto_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(4)
        pikto_container.setVisible(False)
        eltern_layout.addWidget(pikto_container, zeile, 0, alignment=Qt.AlignTop)

        ICON_ZU_LABEL = {
            "original": "hand.svg",
            "isoliert": "finger.svg",
            "markiert (vom Original)": "stift.svg",
            "markiert (vom isolierten)": "stift.svg",
            "genesungsverlauf": "heatmap3D.svg",
        }
        for typ_label, pfad in typen.items():
            pikto = QToolButton()
            pikto.setIconSize(QSize(28, 28))
            pikto.setFixedSize(PIKTO_GROESSE, PIKTO_GROESSE)
            pikto.setToolTip(typ_label)
            if typ_label.startswith("vermessen"):
                pikto.setIcon(QIcon(str(ICON_ORDNER / "vermessen.svg")))
                pikto.clicked.connect(lambda _, pf=pfad: self._vermessung_anzeigen(pf))
            else:
                pikto.setIcon(QIcon(str(ICON_ORDNER / ICON_ZU_LABEL.get(typ_label, "hand.svg"))))
                pikto.clicked.connect(lambda _, pf=pfad: self._scan_laden_aus_pfad(pf))
            p_layout.addWidget(pikto)

        u_knopf.clicked.connect(
            lambda _, c=pikto_container: self._untersuchung_toggle(c)
        )

    def _patient_toggle(self, widgets):
        """widgets[0] ist der Untersuchungs-Container, der Rest (z.B. der
        Genesungsverlauf-Knopf) klappt mit ihm auf und zu."""
        # anderen offenen Patienten zuklappen
        if self._offener_patient is not None and self._offener_patient is not widgets:
            for w in self._offener_patient:
                w.setVisible(False)
        oeffnen = not widgets[0].isVisible()
        for w in widgets:
            w.setVisible(oeffnen)
        self._offener_patient = widgets if oeffnen else None

    def _untersuchung_toggle(self, container):
        if self._offene_untersuchung is not None and self._offene_untersuchung is not container:
            self._offene_untersuchung.setVisible(False)
        container.setVisible(not container.isVisible())
        self._offene_untersuchung = container if container.isVisible() else None

    def _vermessung_anzeigen(self, pfad):
        """Vermessenen Scan laden und, falls vorhanden, die Ergebnisliste zeigen."""
        self._scan_laden_aus_pfad(pfad)
        liste = self._vermessungs_liste_finden(Path(pfad))
        if liste is not None:
            self._ergebnis_liste_zeigen(liste)

    def _vermessungs_liste_finden(self, scan_ordner):
        # schreibe_ergebnis_liste() legt die Liste neben den Scan-Ordner
        # (direkt in 'vermessene_scans'); im Ordner selbst nur als Rueckfall.
        for kandidat in (scan_ordner.parent / f"{scan_ordner.name}.xlsx",
                         scan_ordner / f"{scan_ordner.name}.xlsx"):
            if kandidat.is_file():
                return kandidat
        return None

    def _ergebnis_liste_zeigen(self, xlsx_pfad):
        """Zeigt die Excel-Liste in einem Nebenfenster."""
        try:
            from openpyxl import load_workbook
        except ImportError:
            # ohne openpyxl wenigstens im Standardprogramm oeffnen
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(xlsx_pfad)))
            return

        blatt = load_workbook(xlsx_pfad, read_only=True, data_only=True).active
        zeilen = [["" if w is None else str(w) for w in zeile]
                  for zeile in blatt.iter_rows(values_only=True)]

        fenster, layout = self._neben_fenster(xlsx_pfad.stem)

        tabelle = QTableWidget(len(zeilen), max((len(z) for z in zeilen), default=0))
        tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        tabelle.horizontalHeader().setVisible(False)
        tabelle.verticalHeader().setVisible(False)
        for r, zeile in enumerate(zeilen):
            for c, wert in enumerate(zeile):
                tabelle.setItem(r, c, QTableWidgetItem(wert))
        tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(tabelle)

        oeffnen = QPushButton("In Excel öffnen")
        oeffnen.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(xlsx_pfad))))
        layout.addWidget(oeffnen)

        fenster.resize(420, 320)
        fenster.show()

    def _bild_zeigen(self, png_pfad):
        """Zeigt ein gespeichertes Bild (2D-Heatmap) in einem Nebenfenster."""
        bild = QPixmap(str(png_pfad))
        if bild.isNull():
            self.hinweis_label.setText(f"Bild konnte nicht geladen werden:\n{png_pfad}")
            return

        fenster, layout = self._neben_fenster(Path(png_pfad).parent.parent.name + " - 2D-Heatmap")
        anzeige = QLabel()
        anzeige.setAlignment(Qt.AlignCenter)
        # matplotlib speichert mit 150 dpi - fuer den Bildschirm verkleinern
        anzeige.setPixmap(bild.scaled(QSize(700, 800), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(anzeige)

        oeffnen = QPushButton("Im Bildbetrachter öffnen")
        oeffnen.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(png_pfad))))
        layout.addWidget(oeffnen)

        fenster.adjustSize()
        fenster.show()

    def _neben_fenster(self, titel):
        """Nicht-modales Fenster neben dem Viewer (Excel-Liste, Heatmap), damit
        man den Scan daneben weiter drehen kann. Es gibt immer nur eins - ein
        altes wird geschlossen, sonst stapeln sie sich bei jedem Klick."""
        if getattr(self, "_aktuelles_neben_fenster", None) is not None:
            self._aktuelles_neben_fenster.close()

        fenster = QDialog(self)
        fenster.setWindowTitle(titel)
        fenster.setAttribute(Qt.WA_DeleteOnClose)
        self._aktuelles_neben_fenster = fenster
        # Das Loeschen passiert verzoegert - nur zuruecksetzen, wenn noch
        # kein neueres Fenster eingetragen ist.
        fenster.destroyed.connect(lambda _=None, f=fenster: self._neben_fenster_weg(f))
        return fenster, QVBoxLayout(fenster)

    def _neben_fenster_weg(self, fenster):
        if getattr(self, "_aktuelles_neben_fenster", None) is fenster:
            self._aktuelles_neben_fenster = None

    def _scan_laden_aus_pfad(self, pfad):
        ordner = Path(pfad)
        if not ordner.is_dir():
            self.hinweis_label.setText("Scan-Ordner existiert nicht mehr.")
            return
        self.aktueller_ordner = ordner
        self.lade_und_zeige(ordner)

    # ---------- Finger isolieren ----------

    def isolieren_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
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
        anzahl_punkte_pca = self.slider_pca_punkte.value()
        self.label_radius.setText(f"Breite: {radius_faktor:.2f}")
        self.label_laenge.setText(f"Länge: {laengen_faktor:.2f}")
        self.label_unterschreitung.setText(f"Unterschreitung: {unterschreitung:.2f}")
        self.label_pca_punkte.setText(f"PCA-Punkte: {anzahl_punkte_pca}")

        if anzahl_punkte_pca != self.ellipsoid_kontext.get("anzahl_punkte_pca"):
            normale, verwendete_vertices, avg_point_of_hurt_finger = finger_normale(
                self.ellipsoid_kontext["hand_ausgerichtet"],
                self.ellipsoid_kontext["hurt_finger"],
                anzahl_punkte_pca,
            )
            self.ellipsoid_kontext["normale"] = normale
            self.ellipsoid_kontext["verwendete_vertices"] = verwendete_vertices
            self.ellipsoid_kontext["avg_point_of_hurt_finger"] = avg_point_of_hurt_finger
            self.ellipsoid_kontext["anzahl_punkte_pca"] = anzahl_punkte_pca

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
            "anzahl_punkte_pca": self.slider_pca_punkte.value(),
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

    def setze_zeichnungs_status_zurueck(self):
        # Sonst bleibt nach einem abgebrochenen (nicht geschlossenen) Strich
        # das Ergebnis des vorherigen Zeichenvorgangs stehen
        self.zeichnungs_status["flaeche"] = None
        self.zeichnungs_status["landmarken"] = None
        self.zeichnungs_status["punkte_eingezeichnet"] = None

    def zeichnen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        self.setze_zeichnungs_status_zurueck()
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

        # Nur noch der Einzeichnen-Weg landet hier; das Vermessen laeuft
        # ueber vermessungen_speichern_klick().
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

        self.setze_zeichnungs_status_zurueck()

        markierte_punkte = finde_markierungs_punkte(self.aktuelle_teile, hex_code=self.einzeichnen_farbwahl.farbe, toleranz=100.0)
        if len(markierte_punkte) < 3:
            self.hinweis_label.setText("Keine ausreichende Markierung auf dem Scan gefunden.")
            return

        markierte_punkte = entferne_ausreisser_punkte(markierte_punkte)
        pfad = baue_geschlossenen_pfad(markierte_punkte)

        flaeche = schneide_flaeche_aus_loop(self.aktuelles_hand_mesh, pfad)
        if flaeche is None:
            self.hinweis_label.setText("Markierung konnte nicht auf dem Scan geschlossen werden.")
            return

        self.zeichnungs_status["flaeche"] = flaeche
        self.zeichnungs_status["landmarken"] = {}
        self.zeichnungs_status["punkte_eingezeichnet"] = pfad
        self.malen_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(False)
        self.farbe_wahl_container.setVisible(True)

    def bereich_vermessen_start(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        self.setze_zeichnungs_status_zurueck()
        self.vermessungen.clear()
        self.zeige_basis_mesh_neu()
        self.vermessung_wahl_container.setVisible(False)
        self.vermessen_malen_container.setVisible(True)
        self.hinweis_label.setText(
            "Fläche einzeichnen und Schleife schließen. Beliebig viele nacheinander.")
        draw_main(str(self.aktueller_ordner), self.plotter, self.zeichnungs_status,
                  bei_flaeche_fertig=self.flaeche_fertig_gemalt)
        self.navigatecontainer.setVisible(True)

    # ---------- Mehrfach-Vermessung ----------

    def flaeche_fertig_gemalt(self, flaeche):
        # Wird aus dem Picking-Callback aufgerufen, sobald eine Schleife
        # geschlossen wurde. Danach ist sofort die naechste Flaeche dran.
        flaecheninhalt, umfang = berechne_flaeche_und_umfang(flaeche)
        nummer = len(self.vermessungen) + 1

        actor = self.plotter.add_mesh(
            flaeche, color="red", opacity=1, name=f"vermessung_{nummer}")

        zahl = baue_zahl_fuer_messung(
            flaeche, self.aktuelles_hand_mesh, nummer, flaecheninhalt)
        zahl_actor = self.plotter.add_mesh(
            zahl, color="white", name=f"vermessung_zahl_{nummer}")

        self.vermessungen.append({
            "flaeche": flaeche,
            "flaeche_mm2": flaecheninhalt,
            "umfang_mm": umfang,
            "actor": actor,
            "zahl_actor": zahl_actor,
        })
        self.zeige_messergebnisse()

    def zeige_messergebnisse(self):
        if not self.vermessungen:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet!")
            return

        zeilen = [f"{len(self.vermessungen)} Fläche(n) gemessen"]
        for nummer, messung in enumerate(self.vermessungen, start=1):
            zeilen.append(
                f"{nummer}: {messung['flaeche_mm2']:.1f} mm²  |  {messung['umfang_mm']:.1f} mm")
        self.hinweis_label.setText("\n".join(zeilen))

    def letzte_flaeche_zuruecknehmen(self):
        if not self.vermessungen:
            self.hinweis_label.setText("Es gibt nichts zurückzunehmen.")
            return

        messung = self.vermessungen.pop()
        for actor in (messung["actor"], messung["zahl_actor"]):
            if actor is not None:
                self.plotter.remove_actor(actor, reset_camera=False)
        self.plotter.render()
        self.zeige_messergebnisse()

    def vermessungen_speichern_klick(self):
        if not self.vermessungen:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet!")
            return

        self.plotter.disable_picking()
        scan_ordner = Path(self.aktueller_ordner)

        try:
            obj_pfad = speichere_vermessung(
                self.aktuelle_teile, self.aktuelles_hand_mesh, self.vermessungen, scan_ordner)
        except Exception as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            return

        ziel_ordner, ziel_name = vermessungs_ordner(scan_ordner)
        # Die Ergebnisliste liegt eine Ebene ueber dem Scan-Ordner, also
        # direkt in 'vermessene_scans'.
        liste_pfad = schreibe_ergebnis_liste(self.vermessungen, ziel_ordner.parent, ziel_name)

        if liste_pfad is None:
            self.hinweis_label.setText(
                f"Gespeichert unter {obj_pfad.parent}\n"
                "Excel-Liste übersprungen - openpyxl ist nicht installiert.")
        else:
            self.hinweis_label.setText(
                f"{len(self.vermessungen)} Messung(en) gespeichert\n"
                f"Scan: {obj_pfad.parent}\n"
                f"Liste: {liste_pfad}")

        self.vermessen_malen_container.setVisible(False)
        self.lade_main_menu()

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

        self.plotter.enable_point_picking(callback=punkt_geklickt, 
                                          tolerance = 0.01,  
                                          use_picker=True, 
                                          show_point=True, 
                                          color="red", 
                                          point_size=20)

    def volumen_messen_klick(self):
        self.volumen_container.setVisible(True)
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(True)

    def volumen_ganzes_mesh_messen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        elif "iso" not in str(self.aktueller_ordner):
            self.hinweis_label.setText("Erst den Finger isolieren")
            return
        
        volumen = volumen_gesamtes_mesh(self.aktuelles_hand_mesh)
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

    def volumen_ab_fingerzwischenfalte_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        if "iso" not in str(self.aktueller_ordner):
            self.hinweis_label.setText("Erst den Finger isolieren")
            return

        try:
            volumen = volumen_ab_fingerzwischenfalte(self.aktuelles_hand_mesh)
        except ValueError as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            return

        bounds = self.aktuelles_hand_mesh.bounds
        mitte_x = (bounds[0] + bounds[1]) / 2
        mitte_y = (bounds[2] + bounds[3]) / 2
        breite = (bounds[1] - bounds[0]) * 1.5
        tiefe = (bounds[3] - bounds[2]) * 1.5
        ebene = p_v.Plane(center=(mitte_x, mitte_y, 0), direction=(0, 0, 1), i_size=breite, j_size=tiefe)
        self.plotter.add_mesh(ebene, color="yellow", opacity=0.35, name="schnitt_ebene")

        self.hinweis_label.setText(
            f"Volumen ab der Höhe der Fingerzwischenfalte: {volumen:.1f} mm³")
        
    # ---------- Pipette & Overlay Buttons ----------

    def pipette_aktivieren(self, ziel_widget: FarbAuswahlWidget):
        self._pipette_aktiv = True
        self._pipette_ziel_widget = ziel_widget
        self.plotter.interactor.setCursor(Qt.CrossCursor)
        self.plotter.interactor.installEventFilter(self)
        self.hinweis_label.setText("Pipette aktiv - auf den Scan klicken, um eine Farbe aufzunehmen.")

    def eventFilter(self, obj, event):
        if obj is self.viewer_spalte and event.type() == QEvent.Resize:
            self._positioniere_overlay_buttons()                             
            return super().eventFilter(obj, event)   
    
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


    #--- heatmap -----

    def heatmap_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return
        bild = heatmap_main(str(self.aktueller_ordner))
        if bild is None:
            self.hinweis_label.setText("Keine markierten Scans für diesen Patienten gefunden.")
            return
        self._bild_zeigen(bild)

        # Nav-Spalte neu aufbauen, damit der 2D-Knopf sofort auftaucht, und
        # den Patienten wieder aufklappen - sonst ist man ploetzlich raus.
        patient = Path(self.aktueller_ordner).parent.parent.name
        self.baum_neu_aufbauen()
        if patient in self._patient_aufklapp_widgets:
            self._patient_toggle(self._patient_aufklapp_widgets[patient])


    #--- Genesungsverlauf ---

    def genesungsverlauf_3d_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return

        scan_ordner = Path(self.aktueller_ordner)
        patienten_ordner = scan_ordner.parent.parent

        self.button_abbruch_overlay.setVisible(True)

        andere_eintraege = []
        aktueller_eintrag = None

        for obj_pfad in finde_markierte_scans(patienten_ordner):
            isolierter_name = isolierte_scan_name_aus_markierung(obj_pfad.parent.name)
            isolierter_pfad = patienten_ordner / "isolierte_scans" / isolierter_name
            if not isolierter_pfad.is_dir():
                print(f"Überspringe {obj_pfad.name}: zugehöriger isolierter Scan nicht gefunden.")
                continue

            eintrag = {"isolierter_pfad": isolierter_pfad, "markierungs_pfad": obj_pfad}
            if isolierter_pfad.resolve() == scan_ordner.resolve():
                aktueller_eintrag = eintrag   # das IST der aktuelle Scan - merken, nicht doppelt aufnehmen
            else:
                andere_eintraege.append(eintrag)

        if aktueller_eintrag is None:
            # Aktueller Scan hat selbst noch keine Markierung - trotzdem
            # als reiner Referenz-Eintrag noetig (kein markierungs_pfad)
            aktueller_eintrag = {"isolierter_pfad": scan_ordner, "markierungs_pfad": None}

        self.genesungsverlauf_warteschlange = [aktueller_eintrag] + andere_eintraege

        if len(self.genesungsverlauf_warteschlange) < 2 and aktueller_eintrag["markierungs_pfad"] is None:
            self.hinweis_label.setText("Keine markierten Untersuchungen für diesen Patienten gefunden.")
            return

        self.genesungsverlauf_index = 0
        self.genesungsverlauf_gewinner = {}
        self.genesungsverlauf_aktuell_rotiert = None
        self._genesungsverlauf_letzter_klick = None
        self._genesungsverlauf_naechsten_schritt_zeigen()

    def _genesungsverlauf_naechsten_schritt_zeigen(self):
        eintrag = self.genesungsverlauf_warteschlange[self.genesungsverlauf_index]
        ist_aktuell = eintrag["isolierter_pfad"].resolve() == Path(self.aktueller_ordner).resolve()

        if ist_aktuell:
            self._genesungsverlauf_mesh_fuer_klick = self.aktuelles_hand_mesh
            self.zeige_basis_mesh_neu()
        else:
            teile = load_teilmeshe_mit_textur(eintrag["isolierter_pfad"])
            self._genesungsverlauf_mesh_fuer_klick = p_v.merge([teil for teil, tex in teile])
            self.plotter.clear()
            self._rendere_teile(teile)
            self.plotter.reset_camera()

        self._genesungsverlauf_letzter_klick = None   
        self.hinweis_label.setText(
            f"Genesungsverlauf ({self.genesungsverlauf_index + 1}/{len(self.genesungsverlauf_warteschlange)}): "
            f"Fingernagel anklicken, dann 'Nächsten Finger markieren' zum Bestätigen."
        )
        self.button_naechster_finger_overlay.setVisible(True)
        self._positioniere_overlay_buttons()
        self._genesungsverlauf_picking_aktivieren()

    def _genesungsverlauf_picking_aktivieren(self):
        self.plotter.disable_picking()

        def nagel_geklickt(punkt, picker):
            self._genesungsverlauf_letzter_klick = np.array(punkt)   
            self.plotter.add_points(
                np.array([punkt]), color="yellow", point_size=15,
                render_points_as_spheres=True, name="genesungsverlauf_nagel_marker"  
            )

        self.plotter.enable_point_picking(
            callback=nagel_geklickt, 
            tolerance = 0.01,
            use_picker=True, 
            show_point=False 
        )

    def naechster_finger_markieren_klick(self):
        if not self.genesungsverlauf_warteschlange:
            return
        if self._genesungsverlauf_letzter_klick is None:
            self.hinweis_label.setText("Bitte zuerst den Fingernagel anklicken.")
            return

        self.plotter.disable_picking()
        self._genesungsverlauf_nagel_verarbeiten(self._genesungsverlauf_letzter_klick)


    def _genesungsverlauf_nagel_verarbeiten(self, geklickter_punkt):
        eintrag = self.genesungsverlauf_warteschlange[self.genesungsverlauf_index]
        mesh = self._genesungsverlauf_mesh_fuer_klick
        ist_aktuell = eintrag["isolierter_pfad"].resolve() == Path(self.aktueller_ordner).resolve()
        print(  f"DEBUG: Index={self.genesungsverlauf_index}, ist_aktuell={ist_aktuell}, "
                f"aktuell_rotiert vorhanden={self.genesungsverlauf_aktuell_rotiert is not None}")   
        normale = finde_nagel_normale(mesh, geklickter_punkt)
        R = rotationsmatrix_um_z_fuer_nagel_ausrichtung(normale)
        versatz = self._genesungsverlauf_hoehen_versatz(mesh)

        if ist_aktuell:
            rotierte_punkte = (R @ self.aktuelles_hand_mesh.points.T).T
            rotierte_punkte[:, 2] += versatz
            self.genesungsverlauf_aktuell_rotiert = self.aktuelles_hand_mesh.copy()
            self.genesungsverlauf_aktuell_rotiert.points = rotierte_punkte

        if eintrag["markierungs_pfad"] is not None:
            try:
                markierung_punkte = lade_markierung(eintrag["markierungs_pfad"])
                farbe = lese_markierungsfarbe(eintrag["markierungs_pfad"])
                markierung_rotiert = (R @ markierung_punkte.T).T
                markierung_rotiert[:, 2] += versatz
                for p in markierung_rotiert:
                    vertex_index = self.genesungsverlauf_aktuell_rotiert.find_closest_point(p)
                    bisherige_farbe = self.genesungsverlauf_gewinner.get(vertex_index)
                    if farb_prioritaet(farbe) > farb_prioritaet(bisherige_farbe):
                        self.genesungsverlauf_gewinner[vertex_index] = farbe
            except ValueError as e:
                print(f"Überspringe: {e}")

        self.genesungsverlauf_index += 1
        if self.genesungsverlauf_index < len(self.genesungsverlauf_warteschlange):
            self._genesungsverlauf_naechsten_schritt_zeigen()
        else:
            self._genesungsverlauf_abschliessen()


    def _genesungsverlauf_abschliessen(self):
        self.button_naechster_finger_overlay.setVisible(False)
        self.button_abbruch_overlay.setVisible(False)
        self.zeige_basis_mesh_neu()

        #self.genesungsverlauf_gewinner = bereinige_gewinner(self.aktuelles_hand_mesh, self.genesungsverlauf_gewinner)

        
        farben_gruppen = {}
        for vertex_index, farbe in self.genesungsverlauf_gewinner.items():
            farben_gruppen.setdefault(farbe, []).append(vertex_index)

        for farbe, indices in farben_gruppen.items():
            maske = np.zeros(self.aktuelles_hand_mesh.n_points, dtype=bool)
            maske[indices] = True
            flaeche = extract_faces_of_hand(self.aktuelles_hand_mesh, maske)
            if flaeche.n_points == 0:
                continue

            flaeche = flaeche.clean()
            flaeche = flaeche.compute_normals(point_normals=True, auto_orient_normals=True)
            flaeche.points = flaeche.points + flaeche.point_normals * 0.3

            farbe_hex = f"#{farbe[0]:02X}{farbe[1]:02X}{farbe[2]:02X}"
            self.plotter.add_mesh(flaeche, color=farbe_hex, opacity=1.0)

        save_path = speichere_genesungsverlauf(
            self.aktuelles_hand_mesh, self.aktuelle_teile, self.genesungsverlauf_gewinner, str(self.aktueller_ordner)
        )
        self.hinweis_label.setText(f"Genesungsverlauf erstellt und gespeichert: {save_path.parent.name}")

    def _genesungsverlauf_hoehen_versatz(self, mesh, ziel_hoehe=30):
        #Verstz auf Höhe, dass die Fingerspitze auf Höhe 30 ist, dass die Höhe genau passt
        return ziel_hoehe - mesh.bounds[5]

    def genesungsverlauf_speichern_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            return

        save_path = speichere_genesungsverlauf(self.aktuelles_hand_mesh, self.aktuelle_teile, str(self.aktueller_ordner))
        self.hinweis_label.setText(f"Genesungsverlauf gespeichert: {save_path.parent.name}")
        self.button_speichere_genesungsverlauf_overlay.setVisible(False)
