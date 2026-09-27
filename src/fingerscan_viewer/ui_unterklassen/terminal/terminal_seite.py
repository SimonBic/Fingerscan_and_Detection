from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QApplication)

import konstanten as k
from ui_unterklassen.terminal import terminal_mitschnitt


class TerminalSeite(QWidget):
    # Wie die How-To-Seite aufgebaut: dieselbe Karte, dieselbe Ueberschrift,
    # derselbe Zurueck-Knopf. Nur steht hier kein Markdown, sondern die
    # mitgeschnittene Ausgabe von stdout und stderr.

    def __init__(self, eltern=None):
        super().__init__(eltern)
        self.setObjectName("titel_seite")
        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(60, 60, 60, 60)

        karte = QFrame()
        karte.setObjectName("howto_karte")
        karte.setMaximumWidth(1000)
        innen = QVBoxLayout(karte)
        innen.setContentsMargins(32, 28, 32, 28)

        ueberschrift = QLabel(k.TERMINAL_FENSTER_TITEL)
        ueberschrift.setObjectName("howto_titel")
        innen.addWidget(ueberschrift)

        # QPlainTextEdit und nicht QTextBrowser: das haelt auch bei
        # zehntausenden Zeilen noch mit und macht aus Klammern und
        # Sternchen in der Ausgabe kein Markdown
        self.inhalt = QPlainTextEdit()
        self.inhalt.setObjectName("terminal_inhalt")
        self.inhalt.setReadOnly(True)
        # Kein Umbruch, sonst rutschen lange Pfade und Zahlenkolonnen
        # auseinander und man verliert die Spalten
        self.inhalt.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.inhalt.setFont(QFont(k.TERMINAL_SCHRIFT, k.TERMINAL_SCHRIFTGROESSE))
        # Unbegrenzt, das Kuerzen macht schon der Ringpuffer im Mitschnitt
        self.inhalt.setMaximumBlockCount(0)
        innen.addWidget(self.inhalt, stretch=1)

        zeile = QHBoxLayout()
        self.knopf_zurueck = QPushButton("Zurück")
        self.knopf_zurueck.setObjectName("titel_knopf")
        self.knopf_zurueck.setFixedSize(160, k.TITEL_KNOPF_HOEHE)
        zeile.addWidget(self.knopf_zurueck)
        zeile.addStretch()

        # Leeren, dann den Fehler noch einmal ausloesen, dann kopieren - so
        # steht im Bugreport nur das, was zur Sache gehoert
        self.knopf_leeren = QPushButton("Leeren")
        self.knopf_leeren.setObjectName("titel_knopf")
        self.knopf_leeren.setFixedSize(160, k.TITEL_KNOPF_HOEHE)
        self.knopf_leeren.setToolTip("Den Mitschnitt verwerfen und von hier an neu aufzeichnen")
        self.knopf_leeren.clicked.connect(self.leere_ausgabe)
        zeile.addWidget(self.knopf_leeren)

        self.knopf_kopieren = QPushButton("Kopieren")
        self.knopf_kopieren.setObjectName("titel_knopf")
        self.knopf_kopieren.setFixedSize(160, k.TITEL_KNOPF_HOEHE)
        self.knopf_kopieren.setToolTip("Die ganze Ausgabe in die Zwischenablage legen, z. B. für einen Bugreport")
        self.knopf_kopieren.clicked.connect(self.kopiere_ausgabe)
        zeile.addWidget(self.knopf_kopieren)
        innen.addLayout(zeile)

        # Karte so breit wie moeglich (bis zur Maximalbreite), Rest links und
        # rechts gleich verteilt - wie auf der How-To-Seite
        zentriert = QHBoxLayout()
        zentriert.addStretch(1)
        zentriert.addWidget(karte, stretch=20)
        zentriert.addStretch(1)
        aussen.addLayout(zentriert)

        # Solange die Seite zu sehen ist, wird sie nachgezogen. Der Timer
        # laeuft deshalb erst ab showEvent, nicht schon ab dem Aufbau.
        self._stand = -1
        self._timer = QTimer(self)
        self._timer.setInterval(k.TERMINAL_AKTUALISIERUNG_MS)
        self._timer.timeout.connect(self._nachziehen)

        self.lade_ausgabe()

    def lade_ausgabe(self):
        # Kompletter Puffer, danach ans Ende springen - ein Terminal zeigt
        # auch das Neueste, und hochscrollen kann man ja
        self.inhalt.setPlainText(terminal_mitschnitt.hole_text())
        self._stand = terminal_mitschnitt.stand()
        self._ans_ende()

    def _nachziehen(self):
        # Nur wenn wirklich neue Zeilen da sind: sonst baut die Anzeige
        # zweimal pro Sekunde denselben Text neu auf
        if terminal_mitschnitt.stand() == self._stand:
            return

        balken = self.inhalt.verticalScrollBar()
        # Nur mitlaufen, wenn man schon unten steht. Wer hochgescrollt hat und
        # etwas liest, soll nicht bei jeder neuen Zeile weggerissen werden.
        war_unten = balken.value() >= balken.maximum() - 4
        vorher = balken.value()

        self.inhalt.setPlainText(terminal_mitschnitt.hole_text())
        self._stand = terminal_mitschnitt.stand()

        if war_unten:
            self._ans_ende()
        else:
            balken.setValue(min(vorher, balken.maximum()))

    def _ans_ende(self):
        balken = self.inhalt.verticalScrollBar()
        balken.setValue(balken.maximum())

    def kopiere_ausgabe(self):
        QApplication.clipboard().setText(terminal_mitschnitt.hole_text())

    def leere_ausgabe(self):
        terminal_mitschnitt.leeren()
        self.lade_ausgabe()

    def showEvent(self, event):
        # Beim Oeffnen neu einlesen, wie auf der How-To-Seite auch
        self.lade_ausgabe()
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)
