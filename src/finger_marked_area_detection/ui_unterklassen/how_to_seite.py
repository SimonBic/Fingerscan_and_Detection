from PySide6.QtGui import (
    QColor,
    QTextCursor,
    QTextBlockFormat,
    QTextCharFormat,
    QTextDocument,
    QDesktopServices)
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser)

import konstanten as k


class HowToSeite(QWidget):
    # Platz fuer spaetere Tutorials 

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

        ueberschrift = QLabel("How To")
        ueberschrift.setObjectName("howto_titel")
        innen.addWidget(ueberschrift)

        # Die Tutorials stehen als Markdown in howto/anleitung.md - so lassen
        # sie sich in jedem Editor schreiben. QTextBrowser zeigt Ueberschriften,
        # Listen, Bilder und Links an und scrollt bei langem Text von selbst.
        self.inhalt = QTextBrowser()
        self.inhalt.setObjectName("howto_inhalt")
        # setOpenLinks(False) statt setOpenExternalLinks(True): der
        # Druck-Link ist kein Web-Link, sondern loest eine Aktion aus.
        # Wuerde Qt die Links selbst oeffnen, landete "drucken:anleitung"
        # beim Betriebssystem und die Anleitung waere aus dem Fenster
        # gescrollt. Also alle Klicks selbst entgegennehmen und verteilen.
        self.inhalt.setOpenLinks(False)
        self.inhalt.anchorClicked.connect(self.link_geklickt)
        self.inhalt.setSearchPaths([str(k.HOWTO_ORDNER)])      # Bilder neben der .md finden
        self.lade_anleitung()

        innen.addWidget(self.inhalt, stretch=1)

        zeile = QHBoxLayout()
        self.knopf_zurueck = QPushButton("Zurück")
        self.knopf_zurueck.setObjectName("titel_knopf")
        self.knopf_zurueck.setFixedSize(160, k.TITEL_KNOPF_HOEHE)
        zeile.addWidget(self.knopf_zurueck)
        zeile.addStretch()
        innen.addLayout(zeile)

        # Karte so breit wie moeglich (bis zur Maximalbreite), Rest links und
        # rechts gleich verteilt - mit AlignHCenter schrumpfte sie auf ihren
        # (leeren) Inhalt
        zentriert = QHBoxLayout()
        zentriert.addStretch(1)
        zentriert.addWidget(karte, stretch=20)
        zentriert.addStretch(1)
        aussen.addLayout(zentriert)

    def link_geklickt(self, url):
        # Der Druck-Link in der .md traegt das eigene Schema "drucken:",
        # damit er sich von echten Web-Links unterscheiden laesst.
        if url.scheme() == k.DRUCK_SCHEMA:
            self.drucke_anleitung()
            return
        QDesktopServices.openUrl(url)

    def drucke_anleitung(self):
        # Vorschau statt direktem Druckdialog: die Anleitung ist mehrere
        # Seiten lang, da will man vorher sehen, was herauskommt. Ueber den
        # Dialog laesst sie sich auch als PDF sichern.
        drucker = QPrinter(QPrinter.HighResolution)
        drucker.setDocName(k.DRUCK_DOKUMENTNAME)

        dialog = QPrintPreviewDialog(drucker, self)
        dialog.setWindowTitle(k.DRUCK_FENSTER_TITEL)
        dialog.resize(900, 1000)
        # Das Dokument der Anzeige traegt die Bildschirmbreite und die
        # Farben des dunklen Themes. Gedruckt wird deshalb eine eigene,
        # saubere Kopie aus derselben Markdown-Quelle.
        dialog.paintRequested.connect(
            lambda ziel: self._druck_dokument().print_(ziel))
        dialog.exec()

    def _druck_dokument(self):
        if k.HOWTO_DATEI.is_file():
            markdown = k.HOWTO_DATEI.read_text(encoding="utf-8")
        else:
            markdown = "*Noch keine Anleitung vorhanden.*"

        # Der Druck-Link ist auf Papier sinnlos - Zeilen mit dem eigenen
        # Schema fliegen deshalb raus, samt der dadurch leeren Zeile.
        zeilen = [z for z in markdown.splitlines() if f"({k.DRUCK_SCHEMA}:" not in z]
        markdown = "\n".join(zeilen).replace("\n\n\n", "\n\n")

        dokument = QTextDocument()
        dokument.setDefaultStyleSheet(k.DRUCK_STYLESHEET)
        dokument.setMarkdown(markdown)

        # Ohne das hier kann die Anleitung weiss auf weiss aus dem Drucker
        # kommen: die Textfarbe stammt sonst aus der System-Palette, und die
        # ist bei einem dunklen Desktop-Theme nahezu weiss - unabhaengig
        # davon, dass die App selbst hell gestaltet ist. Weder das Stylesheet
        # noch die Stiftfarbe des Druckers setzen sich dagegen durch, die
        # Zeichenformate muessen deshalb direkt gesetzt werden.
        cursor = QTextCursor(dokument)
        cursor.select(QTextCursor.Document)
        format = QTextCharFormat()
        format.setForeground(QColor(k.DRUCK_TEXTFARBE))
        cursor.mergeCharFormat(format)

        return dokument

    def lade_anleitung(self):
        # Beim Oeffnen der Seite neu lesen: Aenderungen an der .md sind so
        # ohne Neustart der App zu sehen
        if k.HOWTO_DATEI.is_file():
            self.inhalt.setMarkdown(k.HOWTO_DATEI.read_text(encoding="utf-8"))
        else:
            self.inhalt.setMarkdown(f"*Noch keine Anleitung vorhanden.*\n\nSie wird aus `{k.HOWTO_DATEI}` geladen.")
        self._abstaende_setzen()

    def _abstaende_setzen(self):
        # Qt setzt alle Bloecke dicht untereinander und ignoriert dabei, wie
        # viele Leerzeilen in der .md stehen. Die Abstaende muessen deshalb
        # hier gesetzt werden, sonst klebt der Text an den Ueberschriften.
        cursor = QTextCursor(self.inhalt.document())
        cursor.beginEditBlock()
        block = self.inhalt.document().begin()
        while block.isValid():
            ebene = block.blockFormat().headingLevel()
            in_liste = block.textList() is not None
            format = QTextBlockFormat()
            if ebene == 1:
                format.setTopMargin(26); format.setBottomMargin(10)
            elif ebene:
                format.setTopMargin(18); format.setBottomMargin(6)
            elif in_liste:
                format.setTopMargin(3); format.setBottomMargin(3)
            else:
                format.setTopMargin(4); format.setBottomMargin(10)
            # etwas mehr Zeilenabstand; der Typ muss hier als Zahl uebergeben werden
            format.setLineHeight(135, QTextBlockFormat.ProportionalHeight.value)
            cursor.setPosition(block.position())
            cursor.mergeBlockFormat(format)
            block = block.next()
        cursor.endEditBlock()
