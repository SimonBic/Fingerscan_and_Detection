from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QToolButton,
    QCheckBox,
    QSlider,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QApplication)

import konstanten as k
from theme import QSS, knopf_groessen_qss
from ui_unterklassen.hauptmenue.farbauswahl_widget import FarbAuswahlWidget
from ui_unterklassen.hauptmenue.hinweis_label import HinweisLabel, HinweisBereich
from ui_unterklassen.hauptmenue.viewer_raster import ViewerRaster


class UI_Aufbau_Mixin:
    # Alles, was Widgets erzeugt und anordnet. HauptFenster erbt davon.

    def _software_aufbauen(self):
        # Erst jetzt: vorher gibt es keinen Plotter, auf den etwas fallen koennte
        self.setAcceptDrops(True)

        zentral_widget = QWidget()
        # Ersetzt den Title Screen - Qt loescht ihn dabei, sein Netz-Timer endet mit
        self.setCentralWidget(zentral_widget)
        self.titel_bildschirm = None
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
        self.label_pca_radius = QLabel(f"Achsen-Radius: {k.PCA_RADIUS:.0f} mm")
        self.slider_pca_radius = self._ellipsoid_slider(
            int(k.PCA_RADIUS_MIN), int(k.PCA_RADIUS_MAX), int(k.PCA_RADIUS),
            ellipsoid_layout, self.label_pca_radius)
        self.slider_pca_radius.setToolTip(
            "Wie weit ab der Fingerkuppe ENTLANG DER OBERFLÄCHE Punkte für die "
            "Fingerachse gesammelt werden. Zu klein: die Achse wird instabil, weil "
            "nur die runde Kuppe erfasst ist. Zu groß: der Knöchel zieht die Achse schief."
        )
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
        # Der Standardfall: schwarzer Stift auf heller Haut. Braucht weder
        # Pipette noch Farbwahl, weil Schwellwert und Bildaufbereitung fest
        # sind. Steht deshalb ueber der allgemeinen Variante.
        self.button_stift_einzeichnen = self._knopf(
            k.STIFT_KNOPF_TEXT, self.stift_einzeichnen_klick, malen_wahl_layout)
        self.button_stift_einzeichnen.setToolTip(k.STIFT_KNOPF_HILFE)

        self.button_automatisch_einzeichnen = self._knopf(
            "Automatisch einzeichnen", self.automatisch_einzeichnen_klick, malen_wahl_layout)

        self.einzeichnen_farbwahl = FarbAuswahlWidget(standard_farbe="#000000")
        self.einzeichnen_farbwahl.button_pipette.clicked.connect(
            lambda: self.pipette_aktivieren(self.einzeichnen_farbwahl))
        self._farbwahl_merken(self.einzeichnen_farbwahl)
        malen_wahl_layout.addWidget(self.einzeichnen_farbwahl)

        self.knopf_layout.addWidget(self.malen_wahl_container)
        self.malen_wahl_container.setVisible(False)

        # --- Vermessen-Malen (mehrere Flaechen nacheinander) ---
        self.vermessen_malen_container = QWidget()
        vermessen_malen_layout = QVBoxLayout(self.vermessen_malen_container)
        self._knopf("Messung(en)\nspeichern", self.vermessungen_speichern_klick, vermessen_malen_layout)
        self._knopf("Letzte Fläche\nzurücknehmen", self.letzte_flaeche_zuruecknehmen, vermessen_malen_layout)
        # Anteil an der Fingerflaeche - nur sinnvoll bei einem isolierten Finger,
        # sonst waere der Bezugswert die halbe Hand
        self.checkbox_anteil = QCheckBox(k.ANTEIL_CHECKBOX_TEXT)
        self.checkbox_anteil.setObjectName("anteil_checkbox")
        self._seiten_widget_merken(self.checkbox_anteil, k.KNOPF_BREITE)
        vermessen_malen_layout.addWidget(self.checkbox_anteil)
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
        self._farbwahl_merken(self.markierung_farbwahl)
        volumen_layout.addWidget(self.markierung_farbwahl)

        self.knopf_layout.addWidget(self.volumen_container)
        self.volumen_container.setVisible(False)

        # --- Navigation ---
        self.navigatecontainer = QWidget()
        navigate_layout = QVBoxLayout(self.navigatecontainer)
        self._knopf("Zurück zum Hauptmenü", self.lade_main_menu, navigate_layout)
        self.knopf_layout.addWidget(self.navigatecontainer)
        self.navigatecontainer.setVisible(False)

        # --- Fragezeichen, Terminal unten links ---
        
        self.knopf_layout.addStretch(1)
        hilfe_zeile = QHBoxLayout()

        self.knopf_hilfe = QPushButton(k.HILFE_KNOPF_TEXT)
        self.terminal_knopf = QPushButton(">_")

        self.knopf_hilfe.setObjectName("hilfe_knopf")
        self.terminal_knopf.setObjectName("terminal_knopf")

        self.knopf_hilfe.setFixedSize(k.HILFE_KNOPF_GROESSE, k.HILFE_KNOPF_GROESSE)
        self.terminal_knopf.setFixedSize(k.HILFE_KNOPF_GROESSE, k.HILFE_KNOPF_GROESSE)

        self.knopf_hilfe.setToolTip(k.HILFE_KNOPF_HILFE)
        self.terminal_knopf.setToolTip("Hier sind die Terminalausgaben der Software nachzulesen")

        self.knopf_hilfe.clicked.connect(self.zeige_anleitung)
        self.terminal_knopf.clicked.connect(self.zeige_terminal_ausgabe)

        hilfe_zeile.addWidget(self.knopf_hilfe)
        hilfe_zeile.addWidget(self.terminal_knopf)

        hilfe_zeile.addStretch()
        self.knopf_layout.addLayout(hilfe_zeile)

        # --- Knopf-Spalte ganz links ins Haupt-Layout ---
        # In einer Scroll-Flaeche: bei grossen Knoepfen wuerde die Spalte sonst
        # hoeher oder breiter als der Bildschirm und das Fenster gleich mit
        self.knopf_bereich = QScrollArea()
        self.knopf_bereich.setFrameShape(QFrame.NoFrame)
        self.knopf_bereich.setWidgetResizable(True)
        self.knopf_bereich.setWidget(self.knopf_spalte)
        haupt_layout.addWidget(self.knopf_bereich)
        # Wird links ein anderer Container sichtbar oder aendert sich eine
        # Knopfgroesse, die Breite der Spalte neu rechnen
        self.knopf_spalte.installEventFilter(self)

        # --- Navigations-Spalte ganz rechts, feste Breite ---
        self.nav_spalte = QScrollArea()
        self.nav_spalte.setFrameShape(QFrame.NoFrame)
        self.nav_spalte.setWidgetResizable(True)
        # Waagrecht nur, wenn die Knoepfe breiter sind als die erlaubte Spaltenbreite
        self.nav_spalte.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Genau so breit wie der Inhalt: Rand | Piktogramm | Abstand | Avatar | Rand,
        # plus Platz fuer die senkrechte Scrollleiste. Die wird fest reserviert,
        # sonst schiebt sie sich bei vielen Patienten ueber die Avatare.
        self.nav_spalte.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.nav_spalte.verticalScrollBar().ensurePolished()
        self._seitenspalten_breiten_setzen()

        self.nav_inhalt = QWidget()
        self.nav_layout = QVBoxLayout(self.nav_inhalt)
        self.nav_layout.setAlignment(Qt.AlignTop)
        self.nav_layout.setContentsMargins(k.NAV_ABSTAND, k.NAV_ABSTAND, k.NAV_ABSTAND, k.NAV_ABSTAND)
        self.nav_layout.setSpacing(6)
        self.nav_spalte.setWidget(self.nav_inhalt)

        # Zustand fürs Akkordeon
        self._offener_patient = None
        self._blase = None
        self._blase_zu = (None, 0.0)       # (Knopf, Zeitpunkt) des letzten Schliessens

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
        self.hinweis_bereich.setMinimumHeight(zeilen_hoehe + k.HINWEIS_RAND)
        self.hinweis_bereich.setMaximumHeight(zeilen_hoehe * k.HINWEIS_MAX_ZEILEN + k.HINWEIS_RAND)

        # Einstellungsknopf oben rechts neben dem Hinweistext
        self.button_einstellungen = QToolButton()
        self.button_einstellungen.setObjectName("zahnrad_knopf")
        self.button_einstellungen.setText("⚙")
        self.button_einstellungen.setToolTip("Einstellungen")
        # So hoch wie die erste Textzeile: dann sitzt das Zahnrad auf Hoehe
        # des Textes, auch wenn der Hinweis mehrzeilig wird
        self.button_einstellungen.setFixedSize(k.ZAHNRAD_BREITE, zeilen_hoehe + k.HINWEIS_RAND)
        self.button_einstellungen.clicked.connect(self.einstellungen_oeffnen)

        kopf_zeile = QHBoxLayout()
        kopf_zeile.setContentsMargins(0, 0, 0, 0)
        # Links gleich viel Platz wie das Zahnrad rechts - sonst steht der
        # zentrierte Hinweistext nicht mehr ueber der Mitte des Viewers
        kopf_zeile.addSpacing(k.ZAHNRAD_BREITE)
        kopf_zeile.addWidget(self.hinweis_bereich, stretch=1)
        # Oben ausrichten: der Hinweis kann bis zu drei Zeilen hoch werden,
        # das Zahnrad soll trotzdem in der Ecke bleiben
        kopf_zeile.addWidget(self.button_einstellungen, alignment=Qt.AlignTop)
        viewer_layout.addLayout(kopf_zeile)

        # 1 bis 99 Viewer, self.plotter zeigt immer auf den aktiven
        self.viewer_raster = ViewerRaster(self.viewer_spalte, self._viewer_anzahl_lesen(),
                                          self._viewer_wechsel_erlaubt)
        self.viewer_raster.gewechselt.connect(self._viewer_gewechselt)
        viewer_layout.addWidget(self.viewer_raster)
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
        # Die Kacheln im Raster haben ihre neue Groesse erst, wenn das Raster
        # selbst umgebaut ist, deshalb auch dessen Resize mitnehmen
        self.viewer_raster.installEventFilter(self)
        self._positioniere_overlay_buttons()

        # Beobachtet den geoeffneten Patienten auf der Platte: was dort neu
        # gespeichert wird (isolierter Finger, Markierung, Vermessung,
        # Genesungsverlauf, ...), taucht ohne Neustart in der Nav-Spalte auf.
        self._patient_waechter = QFileSystemWatcher(self)
        self._patient_waechter.directoryChanged.connect(lambda _: self._waechter_timer.start())
        
        self._waechter_timer = QTimer(self)
        self._waechter_timer.setSingleShot(True)
        self._waechter_timer.setInterval(400)
        self._waechter_timer.timeout.connect(self._patienten_pruefen)
        self._angezeigte_signaturen = {}

        # Schriften zu den gespeicherten Knopfgroessen, die Nav-Spalte wird
        # gleich darunter ohnehin gebaut
        self._knopf_groessen_anwenden(nav_neu_bauen=False)
        self._root_ordner_anwenden()
        self.baum_neu_aufbauen()

    def _knopf(self, text: str, funktion, ziel_layout, x = k.KNOPF_BREITE, y = k.KNOPF_HOEHE) -> QPushButton:
        button = QPushButton(text)
        # Ueber den Namen findet die Schriftgroesse aus knopf_groessen_qss den Knopf
        button.setObjectName("seiten_knopf")
        self._seiten_widget_merken(button, x, y)
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
        # Oben rechts im aktiven Viewer, bei mehreren Viewern sonst ueber
        # einem ganz anderen Scan
        kachel = self.viewer_raster.aktiv
        oben_rechts = kachel.mapTo(self.viewer_spalte, kachel.rect().topRight())
        rand = 10 + k.VIEWER_RAND
        y = oben_rechts.y() + rand
        for button in self.overlay_buttons:
            button.move(oben_rechts.x() - button.width() - rand + 1, y)
            button.raise_()
            y += button.height() + rand

    # ---------- Knopfgroessen ----------
    # self.knopf_groessen: {"links": 100, "nav": 100, "pikto": 100} in Prozent

    def _skaliert(self, wert, gruppe):
        return max(1, round(wert * self.knopf_groessen[gruppe] / 100))

    def _nav_breite(self):
        return self._skaliert(k.NAV_KNOPF_BREITE, "nav")

    def _patient_icon(self):
        return self._skaliert(k.PATIENT_ICON, "nav")

    def _pikto_groesse(self):
        return self._skaliert(k.PIKTO_GROESSE, "pikto")

    def _pikto_icon(self):
        return self._skaliert(k.PIKTO_ICON, "pikto")

    def _seiten_widget_merken(self, widget, breite, hoehe=None):
        # Alles in der linken Spalte, was mit "Knoepfe links" mitwachsen soll.
        # Gemerkt wird die Groesse bei 100 %, damit man spaeter neu rechnen kann.
        # Ohne Hoehe nur die Breite, die Hoehe ergibt sich dann aus der Schrift.
        self._seiten_widgets.append((widget, breite, hoehe))
        self._seiten_widget_groesse_setzen(widget, breite, hoehe)

    def _seiten_widget_groesse_setzen(self, widget, breite, hoehe):
        if hoehe is None:
            widget.setFixedWidth(self._skaliert(breite, "links"))
        else:
            widget.setFixedSize(self._skaliert(breite, "links"), self._skaliert(hoehe, "links"))

    def _farbwahl_merken(self, farbwahl):
        # Vorschau und Pipette sind so breit wie die Knoepfe darueber und
        # sollen buendig bleiben. Die kleinen Farbfelder bleiben wie sie sind.
        farbwahl.button_pipette.setObjectName("seiten_knopf")
        self._seiten_widget_merken(farbwahl.vorschau, k.KNOPF_BREITE, 40)
        self._seiten_widget_merken(farbwahl.button_pipette, k.KNOPF_BREITE, 40)

    def _seitenspalten_breiten_setzen(self):
        # Beide Seitenspalten so breit wie ihr Inhalt, aber hoechstens
        # SEITENSPALTE_MAX_ANTEIL der Fensterbreite. Was nicht passt, wird
        # gescrollt. Ohne Grenze wuerden grosse Knoepfe das Fenster ueber den
        # Bildschirm hinaus aufziehen.
        if getattr(self, "knopf_bereich", None) is None or getattr(self, "nav_spalte", None) is None:
            return
        max_breite = int(self.width() * k.SEITENSPALTE_MAX_ANTEIL)
        leiste = self.nav_spalte.verticalScrollBar().sizeHint().width()

        # Rand | Piktogramm | Abstand | Avatar | Rand, plus die fest reservierte Scrollleiste
        nav_inhalt = k.NAV_ABSTAND + self._pikto_groesse() + k.NAV_ABSTAND + self._nav_breite() + k.NAV_ABSTAND
        self.nav_spalte.setFixedWidth(min(nav_inhalt + leiste, max_breite))

        # Platz fuer die senkrechte Leiste immer mitrechnen. Taucht sie auf,
        # wuerde sie sonst Breite wegnehmen und gleich noch eine waagrechte erzwingen.
        knopf_inhalt = self.knopf_spalte.sizeHint().width() + leiste
        self.knopf_bereich.setFixedWidth(min(knopf_inhalt, max_breite))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Die Obergrenze haengt an der Fensterbreite
        self._seitenspalten_breiten_setzen()

    def _knopf_groessen_anwenden(self, nav_neu_bauen=True):
        for widget, breite, hoehe in self._seiten_widgets:
            self._seiten_widget_groesse_setzen(widget, breite, hoehe)
        # Die Schriften haengen am App-Stylesheet, also das neu setzen
        QApplication.instance().setStyleSheet(QSS + knopf_groessen_qss(self.knopf_groessen))
        self._seitenspalten_breiten_setzen()
        if nav_neu_bauen:
            # Die Nav-Knoepfe lesen ihre Groesse beim Bauen, also neu bauen
            self._nav_aktualisieren()
