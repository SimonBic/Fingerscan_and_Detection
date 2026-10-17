import math

from PySide6.QtCore import (
    Qt,
    QPoint,
    QRect,
    QPointF,
    QRectF,
    Signal,
    QVariantAnimation,
    QEasingCurve)
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor)
from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QGraphicsDropShadowEffect)

import konstanten as k


class _BlasenFlaeche(QWidget):
    #Malt die Sprechblase: abgerundetes Rechteck, rechts davon ein Strich
    #rüber zum Untersuchungs-Knopf

    def __init__(self, strich_y, eltern=None):
        super().__init__(eltern)
        self._strich_y = strich_y

    def setze_strich_y(self, strich_y):
        # Wird die Blase verschoben, damit sie ins Fenster passt, muss der
        # Strich trotzdem auf die Mitte des Knopfs zeigen
        self._strich_y = strich_y
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        stift = QPen(QColor(k.BLASE_RANDFARBE), 2)
        # 1px nach innen, damit der 2px-Rand nicht am Widgetrand abgeschnitten wird
        koerper = QRectF(1, 1, self.width() - k.BLASE_VERBINDUNG - 2, self.height() - 2)

        # Strich zuerst: sein Anfang verschwindet so unter dem Blasenrand
        p.setPen(stift)
        p.drawLine(QPointF(koerper.right(), self._strich_y), QPointF(self.width(), self._strich_y))

        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(koerper, k.BLASE_RADIUS, k.BLASE_RADIUS)


class IconBlase(QWidget):
    #Blase, welche die Icons der Piktogramm-Knoepfe umgibt, wenn sie aufploppen.
    #Eigenes Widget, da das ein wenig über den Viewer ragt

    geschlossen = Signal()

    def __init__(self, anker, knoepfe):
        super().__init__(anker, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._anker = anker
        self._bild = None
        self._t = 1.0

        # Strich auf Hoehe der Knopfmitte; die erste Icon-Reihe beginnt auf
        # Hoehe der Knopf-Oberkante
        self._strich_y = k.BLASE_POLSTER + anker.height() / 2
        self._flaeche = _BlasenFlaeche(self._strich_y, self)
        layout = QGridLayout(self._flaeche)
        layout.setContentsMargins(k.BLASE_POLSTER, k.BLASE_POLSTER,
                                  k.BLASE_POLSTER + k.BLASE_VERBINDUNG, k.BLASE_POLSTER)
        layout.setSpacing(k.NAV_ABSTAND)
        # Normal eine Spalte untereinander. Bei grossen Piktogrammen passt
        # die nicht mehr ins Fenster, dann auf mehrere Spalten verteilen.
        reihen = self._reihen_die_passen(knoepfe)
        for nummer, knopf in enumerate(knoepfe):
            layout.addWidget(knopf, nummer % reihen, nummer // reihen)

        schatten = QGraphicsDropShadowEffect(self._flaeche)
        schatten.setBlurRadius(14)
        schatten.setOffset(0, 2)
        schatten.setColor(QColor(0, 0, 0, 55))
        self._flaeche.setGraphicsEffect(schatten)

        self._flaeche.adjustSize()
        self._flaeche.move(k.BLASE_RAND, k.BLASE_RAND)
        self.resize(self._flaeche.width() + 2 * k.BLASE_RAND, self._flaeche.height() + 2 * k.BLASE_RAND)

        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(k.BLASE_DAUER_MS)
        self._animation.valueChanged.connect(self._schritt)
        self._animation.finished.connect(self._fertig)

    def _grenze(self):
        # Der Bereich, in dem die Blase bleiben soll: das Hauptfenster, und
        # davon nur, was auch auf dem Bildschirm liegt
        fenster = self._anker.window()
        grenze = QRect(fenster.mapToGlobal(QPoint(0, 0)), fenster.size())
        bildschirm = self._anker.screen()
        if bildschirm is not None:
            grenze = grenze.intersected(bildschirm.availableGeometry())
        return grenze

    def _reihen_die_passen(self, knoepfe):
        if not knoepfe:
            return 1
        knopf_hoehe = knoepfe[0].minimumHeight() or knoepfe[0].sizeHint().height()
        platz = self._grenze().height() - 2 * k.BLASE_RAND - 2 * k.BLASE_POLSTER
        reihen = max(1, (platz + k.NAV_ABSTAND) // (knopf_hoehe + k.NAV_ABSTAND))
        # Gleichmaessig verteilen: 5 Knoepfe bei 4 passenden Reihen werden
        # 3 + 2 statt 4 + 1
        spalten = math.ceil(len(knoepfe) / reihen)
        return math.ceil(len(knoepfe) / spalten)

    def zeigen(self):
        # Strich endet genau an der linken Kante des Knopfs
        oben_links = self._anker.mapToGlobal(QPoint(0, 0))
        x = oben_links.x() - self._flaeche.width() - k.BLASE_RAND
        y = oben_links.y() - k.BLASE_POLSTER - k.BLASE_RAND

        # Ragt die Blase unten aus dem Fenster, so weit hochschieben, bis sie
        # passt. Oben aber nicht ueber den Fensterrand hinaus.
        grenze = self._grenze()
        if y + self.height() > grenze.bottom() + 1:
            y = grenze.bottom() + 1 - self.height()
        y = max(y, grenze.top())
        self.move(x, y)

        # Der Strich zeigt weiter auf die Knopfmitte, auch wenn die Blase
        # verschoben wurde. Nicht in die runden Ecken hinein.
        knopf_mitte = oben_links.y() + self._anker.height() / 2 - (y + k.BLASE_RAND)
        self._strich_y = min(max(knopf_mitte, k.BLASE_RADIUS),
                             self._flaeche.height() - k.BLASE_RADIUS)
        self._flaeche.setze_strich_y(self._strich_y)

        # Fuer das Aufploppen wird ein Standbild skaliert: echte Widgets
        # lassen sich nicht stufenlos skalieren. Am Ende uebernehmen wieder
        # die echten Knoepfe (Hover, Klick).
        self._bild = self.grab()
        self._flaeche.hide()
        self._t = 0.0
        self.show()
        self._animation.start()

    def _schritt(self, t):
        self._t = t
        self.update()

    def _fertig(self):
        self._bild = None
        self._flaeche.show()
        self.update()

    def paintEvent(self, event):
        if self._bild is None:
            return
        # Aus dem Strichende am Knopf heraus: leicht ueber das Ziel hinaus (OutBack) und
        # zurueck, für ein hübsches Plopp
        groesse = 0.55 + 0.45 * QEasingCurve(QEasingCurve.OutBack).valueForProgress(self._t)
        deckkraft = QEasingCurve(QEasingCurve.OutCubic).valueForProgress(min(1.0, self._t * 1.6))
        spitze = QPointF(k.BLASE_RAND + self._flaeche.width(),
                         k.BLASE_RAND + self._strich_y)
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(deckkraft)
        p.translate(spitze)
        p.scale(groesse, groesse)
        p.translate(-spitze)
        p.drawPixmap(0, 0, self._bild)

    def hideEvent(self, event):
        self.geschlossen.emit()
        super().hideEvent(event)
