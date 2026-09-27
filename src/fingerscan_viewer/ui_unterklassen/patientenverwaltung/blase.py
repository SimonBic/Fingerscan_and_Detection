from PySide6.QtCore import (
    Qt,
    QPoint,
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
    QVBoxLayout,
    QGraphicsDropShadowEffect)

import konstanten as k


class _BlasenFlaeche(QWidget):
    #Malt die Sprechblase: abgerundetes Rechteck, rechts davon ein Strich
    #rüber zum Untersuchungs-Knopf

    def __init__(self, strich_y, eltern=None):
        super().__init__(eltern)
        self._strich_y = strich_y

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
        self._flaeche = _BlasenFlaeche(k.BLASE_POLSTER + anker.height() / 2, self)
        layout = QVBoxLayout(self._flaeche)
        layout.setContentsMargins(k.BLASE_POLSTER, k.BLASE_POLSTER,
                                  k.BLASE_POLSTER + k.BLASE_VERBINDUNG, k.BLASE_POLSTER)
        layout.setSpacing(k.NAV_ABSTAND)
        for knopf in knoepfe:
            layout.addWidget(knopf)

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

    def zeigen(self):
        # Strich endet genau an der linken Kante des Knopfs
        oben_links = self._anker.mapToGlobal(QPoint(0, 0))
        self.move(oben_links.x() - self._flaeche.width() - k.BLASE_RAND,
                  oben_links.y() - k.BLASE_POLSTER - k.BLASE_RAND)

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
                         k.BLASE_RAND + k.BLASE_POLSTER + self._anker.height() / 2)
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
