from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout)

import konstanten as k
from ui_unterklassen.terminal.terminal_seite import TerminalSeite


class TerminalFenster(QDialog):
    # Die Terminal-Seite als eigenes Fenster, aufrufbar ueber den ">_"-Knopf
    # unten links in der laufenden Software

    def __init__(self, eltern=None):
        super().__init__(eltern)
        self.setWindowTitle(k.TERMINAL_FENSTER_TITEL)
        self.resize(*k.TERMINAL_FENSTER_GROESSE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.seite = TerminalSeite(self)
        # Im Fenster fuehrt "Zurueck" nicht auf eine andere Seite, sondern
        # schliesst es
        self.seite.knopf_zurueck.setText("Schließen")
        self.seite.knopf_zurueck.clicked.connect(self.accept)
        layout.addWidget(self.seite)

    def zeige(self):
        # Beim Oeffnen neu einlesen, damit alles dasteht, was seit dem
        # letzten Blick dazugekommen ist
        self.seite.lade_ausgabe()
        self.show()
        self.raise_()
        self.activateWindow()
