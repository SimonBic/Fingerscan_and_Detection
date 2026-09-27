from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLayout,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QHBoxLayout)

import konstanten as k


class LoeschDialog(QDialog):
    # Eigener Dialog statt QMessageBox. Dort bestimmt der Plattform-Stil die
    # Anordnung, und die beiden Loesch-Knoepfe liessen sich nicht vom
    # Abbrechen absetzen: eine Dehnfuge im Knopfkasten bewegt dort 8 Pixel.

    PAPIERKORB = "papierkorb"
    ENDGUELTIG = "endgueltig"

    def __init__(self, scan_ordner, typ_label, eltern=None):
        super().__init__(eltern)
        self.setWindowTitle(k.LOESCH_FENSTER_TITEL)
        self.antwort = None
        #Breite zuerst: ein Label mit Wortumbruch kann seine Hoehe erst
        #ausrechnen, wenn es weiss, wie breit es werden darf
        self.setMinimumWidth(k.LOESCH_FENSTER_BREITE)
        self.setMinimumHeight(k.LOESCH_FENSTER_HOEHE)

        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(24, 20, 24, 16)
        aussen.setSpacing(14)

        # Fragezeichen wie bei einem Systemdialog, damit man sofort sieht,
        # dass hier eine Entscheidung ansteht
        kopf = QHBoxLayout()
        kopf.setSpacing(16)
        symbol = QLabel()
        symbol.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxQuestion).pixmap(48, 48))
        symbol.setAlignment(Qt.AlignTop)
        kopf.addWidget(symbol)

        frage = QLabel(f"Den Scan '{typ_label}' entfernen?")
        frage.setObjectName("loesch_frage")
        frage.setWordWrap(True)
        kopf.addWidget(frage, stretch=1)
        aussen.addLayout(kopf)

        erklaerung = QLabel(
            f"{scan_ordner}\n\n"
            f"Papierkorb: verschiebt den Ordner nach '{k.PAPIERKORB_ORDNER}' im Root-Ordner. "
            "Von dort lässt er sich zurückholen.\n\n"
            "Endgültig: der Ordner ist danach weg, auch am Papierkorb des Systems vorbei."
            "\nDer Scan ist dann nicht mehr wiederherstellbar, die Inode wird wieder frei gegeben"
            "\nSichere Variante zum Löschen, da danach nicht mehr wiederherstellbar.")
        erklaerung.setObjectName("loesch_erklaerung")
        erklaerung.setWordWrap(True)
        erklaerung.setMinimumWidth(k.LOESCH_FENSTER_BREITE - 2 * 24)
        aussen.addWidget(erklaerung)

        # Links die zwei, die Daten entfernen, rechts der Rueckzieher. Die
        # Dehnfuge dazwischen ist der Grund fuer den eigenen Dialog.
        zeile = QHBoxLayout()
        zeile.setSpacing(10)
        self.knopf_papierkorb = self._knopf("In den Papierkorb", "loeschen_knopf", zeile)
        self.knopf_endgueltig = self._knopf("Endgültig löschen", "loeschen_knopf", zeile)
        zeile.addStretch(1)
        self.knopf_abbrechen = self._knopf("Abbrechen", "abbrechen_knopf", zeile)
        aussen.addLayout(zeile)

        self.knopf_papierkorb.clicked.connect(lambda: self._entscheiden(self.PAPIERKORB))
        self.knopf_endgueltig.clicked.connect(lambda: self._entscheiden(self.ENDGUELTIG))
        self.knopf_abbrechen.clicked.connect(self.reject)

        # Die harmlose Wahl liegt auf der Eingabetaste, Escape bricht ab
        self.knopf_papierkorb.setDefault(True)

        #Damit das Fenster auf den umgebrochenen Text waechst statt ihn
        #abzuschneiden
        aussen.setSizeConstraint(QLayout.SetMinimumSize)

    def _knopf(self, text, name, zeile):
        knopf = QPushButton(text)
        # Name direkt nach dem Erzeugen: wird er spaeter gesetzt, ist der
        # Knopf schon poliert und die Farbe aus theme.py greift nicht mehr
        knopf.setObjectName(name)
        knopf.setFixedHeight(k.LOESCH_KNOPF_HOEHE)
        zeile.addWidget(knopf)
        return knopf

    def _entscheiden(self, antwort):
        self.antwort = antwort
        self.accept()

    def frage_stellen(self):
        # "papierkorb", "endgueltig", oder None bei Abbrechen
        self.exec()
        return self.antwort
