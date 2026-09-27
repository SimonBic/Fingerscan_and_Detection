import time

import numpy as np
from scipy.spatial import cKDTree

from PySide6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QLineF)
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor)
from PySide6.QtWidgets import QWidget

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
