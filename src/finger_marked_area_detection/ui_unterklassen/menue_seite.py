from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout)

import konstanten as k


class MenueSeite(QWidget):
    # Logo, Titel und die drei Knoepfe - so platziert, dass die Logo-Mitte
    # im goldenen Schnitt der Hoehe liegt

    def __init__(self, eltern=None):
        super().__init__(eltern)
        self.setObjectName("titel_seite")

        # Breite ergibt sich aus dem breitesten Element (dem Titel) - die
        # schmaleren Knoepfe werden darin zentriert
        self.inhalt = QWidget(self)
        self.inhalt.setObjectName("titel_inhalt")
        spalte = QVBoxLayout(self.inhalt)
        spalte.setContentsMargins(0, 0, 0, 0)
        spalte.setSpacing(12)

        logo = QLabel()
        logo.setFixedSize(k.TITEL_LOGO_GROESSE, k.TITEL_LOGO_GROESSE)
        bild = QPixmap(str(k.LOGO_PFAD))
        # Fuer scharfe Darstellung auf HiDPI-Bildschirmen in voller Aufloesung skalieren
        dpr = self.devicePixelRatioF()
        bild = bild.scaled(int(k.TITEL_LOGO_GROESSE * dpr), int(k.TITEL_LOGO_GROESSE * dpr),
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
        bild.setDevicePixelRatio(dpr)
        logo.setPixmap(bild)
        spalte.addWidget(logo, alignment=Qt.AlignHCenter)

        titel = QLabel("Fingerscan-Viewer")
        titel.setObjectName("titel_schrift")
        titel.setAlignment(Qt.AlignCenter)
        spalte.addWidget(titel)
        spalte.addSpacing(24)

        self.knopf_start = self._knopf("Software starten", spalte)
        self.knopf_root = self._knopf("Root Ordner bearbeiten", spalte)
        self.root_anzeige = QLabel()
        self.root_anzeige.setObjectName("titel_root")
        self.root_anzeige.setAlignment(Qt.AlignCenter)
        spalte.addWidget(self.root_anzeige)
        self.knopf_howto = self._knopf("How To", spalte)

    def _knopf(self, text, spalte):
        knopf = QPushButton(text)
        knopf.setObjectName("titel_knopf")
        knopf.setFixedSize(k.TITEL_KNOPF_BREITE, k.TITEL_KNOPF_HOEHE)
        spalte.addWidget(knopf, alignment=Qt.AlignHCenter)
        return knopf

    def setze_root_ordner(self, pfad):
        if pfad:
            # Lange Pfade in der Mitte kuerzen, der volle Pfad steht im Tooltip
            text = self.root_anzeige.fontMetrics().elidedText(
                f"Root: {pfad}", Qt.ElideMiddle, k.TITEL_KNOPF_BREITE)
            self.root_anzeige.setText(text)
            self.root_anzeige.setToolTip(pfad)
        else:
            self.root_anzeige.setText("Noch kein Root-Ordner gewählt")
            self.root_anzeige.setToolTip("")

    def resizeEvent(self, event):
        self.inhalt.adjustSize()
        x = (self.width() - self.inhalt.width()) // 2
        # Das Logo ist das oberste Element der Spalte: seine Mitte liegt
        # eine halbe Logohoehe unter der Oberkante der Spalte
        y = int(self.height() * k.GOLDENER_SCHNITT - k.TITEL_LOGO_GROESSE / 2)
        # Bei sehr kleinen Fenstern nicht nach unten hinausschieben
        y = max(10, min(y, self.height() - self.inhalt.height() - 10))
        self.inhalt.move(x, y)
        super().resizeEvent(event)
