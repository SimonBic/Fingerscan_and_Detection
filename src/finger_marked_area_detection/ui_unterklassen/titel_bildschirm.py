import time

import numpy as np
from scipy.spatial import cKDTree

from PySide6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QLineF,
    Signal)
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QPixmap,
    QTextCursor,
    QTextBlockFormat)
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QTextBrowser)

import konstanten as k


class NetzHintergrund(QWidget):
    # Hintergrund des Title Screens: zufaellige Punkte, jeder fest mit seinen
    # naechsten Nachbarn verbunden. 
    # "Wabert" vor sich hin

    #Je kürzer eine Kante desto dicker
    KANTEN_ALPHA = (90, 60, 35)
    PUNKT_ALPHA = 140
    PUNKT_RADIUS = 2.0

    def __init__(self, eltern=None):
        super().__init__(eltern)
        # Ohne Seed: bei jedem Start ein anderes Netz
        rng = np.random.default_rng()
        n = k.NETZ_PUNKTE

        # Ruhelage in normierten Koordinaten, etwas ueber den Rand hinaus,
        # damit das Netz nicht sichtbar an der Fensterkante aufhoert
        self._basis = rng.uniform(-0.05, 1.05, size=(n, 2))

        # Je Punkt und Achse zwei Sinuswellen mit eigener Periode und Phase -
        # ueberlagert wirkt das organischer als eine einzelne Welle
        perioden = rng.uniform(k.NETZ_PERIODE_MIN_S, k.NETZ_PERIODE_MAX_S, size=(n, 2, 2))
        self._kreisfrequenz = 2 * np.pi / perioden
        self._phase = rng.uniform(0, 2 * np.pi, size=(n, 2, 2))

        # Kanten erst, wenn die Groesse bekannt ist (Nachbarn sollen im
        # Seitenverhaeltnis des Fensters nah sein, nicht im Einheitsquadrat)
        self._kanten_gruppen = None
        self._start = time.monotonic()

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // k.NETZ_FPS)
        self._timer.timeout.connect(self.update)

    def anzahl_kanten(self):
        return 0 if self._kanten_gruppen is None else sum(len(g) for g in self._kanten_gruppen)

    def _kanten_bauen(self, breite, hoehe):
        skaliert = self._basis * (breite, hoehe)
        # k+1, weil der naechste Nachbar jedes Punktes er selbst ist
        _, nachbarn = cKDTree(skaliert).query(skaliert, k=k.NETZ_NACHBARN + 1)
        paare = {(min(i, j), max(i, j)) for i, zeile in enumerate(nachbarn) for j in zeile[1:]}
        kanten = np.array(sorted(paare))

        laengen = np.linalg.norm(skaliert[kanten[:, 0]] - skaliert[kanten[:, 1]], axis=1)
        grenzen = np.quantile(laengen, [1 / 3, 2 / 3])
        gruppe = np.searchsorted(grenzen, laengen)
        self._kanten_gruppen = [kanten[gruppe == g] for g in range(3)]

    def positionen(self):
        # Aktuelle Punktpositionen in Pixeln
        t = time.monotonic() - self._start
        welle = np.sin(self._kreisfrequenz * t + self._phase).sum(axis=2) / 2   # -1 .. 1
        return self._basis * (self.width(), self.height()) + k.NETZ_AMPLITUDE_PX * welle

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(k.NETZ_HINTERGRUND))
        if self.width() <= 0 or self.height() <= 0:
            return
        if self._kanten_gruppen is None:
            self._kanten_bauen(self.width(), self.height())

        p.setRenderHint(QPainter.Antialiasing)
        pos = self.positionen()
        farbe = QColor(k.NETZ_FARBE)

        for alpha, kanten in zip(self.KANTEN_ALPHA, self._kanten_gruppen):
            farbe.setAlpha(alpha)
            p.setPen(QPen(farbe, 1))
            # Anfang und Ende jeder Kante nebeneinander, dann .tolist(): ueber
            # eine Python-Liste zu laufen ist um ein Vielfaches schneller als
            # ueber numpy-Zeilen (dort wird jede Zahl einzeln ausgepackt)
            enden = np.hstack((pos[kanten[:, 0]], pos[kanten[:, 1]])).tolist()
            p.drawLines([QLineF(x1, y1, x2, y2) for x1, y1, x2, y2 in enden])

        # Alle Punkte in einem Aufruf: runde Stiftspitze statt einzelner Kreise
        farbe.setAlpha(self.PUNKT_ALPHA)
        stift = QPen(farbe, 2 * self.PUNKT_RADIUS)
        stift.setCapStyle(Qt.RoundCap)
        p.setPen(stift)
        p.drawPoints([QPointF(x, y) for x, y in pos.tolist()])

    # Nur animieren, solange man es sieht
    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)


class _MenueSeite(QWidget):
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


class _HowToSeite(QWidget):
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
        self.inhalt.setOpenExternalLinks(True)                # Web-Links im Browser oeffnen
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


class TitelBildschirm(QWidget):
    # Startseite im Hauptfenster. Kennt weder QSettings noch das Hauptfenster -
    # es meldet nur per Signal, was geklickt wurde.

    software_starten = Signal()
    root_ordner_bearbeiten = Signal()

    def __init__(self, root_ordner="", eltern=None):
        super().__init__(eltern)
        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(0, 0, 0, 0)

        self.hintergrund = NetzHintergrund()
        aussen.addWidget(self.hintergrund)

        # Seiten liegen durchsichtig auf dem Netz - es laeuft auf beiden weiter
        auf_netz = QVBoxLayout(self.hintergrund)
        auf_netz.setContentsMargins(0, 0, 0, 0)
        self.seiten = QStackedWidget()
        self.seiten.setObjectName("titel_stapel")
        auf_netz.addWidget(self.seiten)

        self.menue = _MenueSeite()
        self.howto = _HowToSeite()
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
