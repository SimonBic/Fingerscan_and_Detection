from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout)

import konstanten as k
from ui_unterklassen.how_to_seite import HowToSeite


class AnleitungFenster(QDialog):
    # Dieselbe How-To-Seite, nur als eigenes Fenster - so kommt man auch
    # aus der laufenden Software an die Anleitung (Fragezeichen-Knopf)

    def __init__(self, eltern=None):
        super().__init__(eltern)
        self.setWindowTitle(k.ANLEITUNG_FENSTER_TITEL)
        self.resize(*k.ANLEITUNG_FENSTER_GROESSE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.seite = HowToSeite(self)
        # Im Fenster fuehrt "Zurueck" nicht auf eine andere Seite, sondern
        # schliesst es
        self.seite.knopf_zurueck.setText("Schließen")
        self.seite.knopf_zurueck.clicked.connect(self.accept)
        layout.addWidget(self.seite)

    def zeige(self):
        # Beim Oeffnen neu einlesen, wie auf dem Title Screen auch
        self.seite.lade_anleitung()
        self.show()
        self.raise_()
        self.activateWindow()
