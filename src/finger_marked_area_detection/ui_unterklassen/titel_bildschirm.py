from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QStackedWidget)

from ui_unterklassen.netzhintergrund import NetzHintergrund
from ui_unterklassen.menue_seite import MenueSeite
from ui_unterklassen.how_to_seite import HowToSeite


class TitelBildschirm(QWidget):
    #meldet nur per Signal, was geklickt wurde.

    software_starten = Signal()
    root_ordner_bearbeiten = Signal()

    def __init__(self, root_ordner="", eltern=None):
        super().__init__(eltern)
        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(0, 0, 0, 0)

        self.hintergrund = NetzHintergrund()
        aussen.addWidget(self.hintergrund)

        # Seiten liegen durchsichtig auf dem Netz
        auf_netz = QVBoxLayout(self.hintergrund)
        auf_netz.setContentsMargins(0, 0, 0, 0)
        self.seiten = QStackedWidget()
        self.seiten.setObjectName("titel_stapel")
        auf_netz.addWidget(self.seiten)

        self.menue = MenueSeite()
        self.howto = HowToSeite()
        self.seiten.addWidget(self.menue)
        self.seiten.addWidget(self.howto)

        self.menue.knopf_start.clicked.connect(self.software_starten)
        self.menue.knopf_root.clicked.connect(self.root_ordner_bearbeiten)
        self.menue.knopf_howto.clicked.connect(self._zeige_howto)
        self.howto.knopf_zurueck.clicked.connect(lambda: self.seiten.setCurrentWidget(self.menue))

        self.setze_root_ordner(root_ordner)

    def _zeige_howto(self):
        self.howto.lade_anleitung()
        self.seiten.setCurrentWidget(self.howto)

    def setze_root_ordner(self, pfad):
        self.menue.setze_root_ordner(pfad)

    def zeige_laden(self):
        # Rueckmeldung, waehrend das Hauptfenster aufgebaut wird (dauert kurz)
        self.menue.knopf_start.setText("Wird gestartet …")
        for knopf in (self.menue.knopf_start, self.menue.knopf_root, self.menue.knopf_howto):
            knopf.setEnabled(False)
