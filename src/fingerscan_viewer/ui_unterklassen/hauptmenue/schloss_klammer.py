from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor
from PySide6.QtWidgets import QWidget


class SchlossKlammer(QWidget):
    # Grauer Buegel rechts neben mehreren Raedern, oben und unten mit einem
    # kurzen Strich an die Raeder angesetzt, in der Mitte unterbrochen. Dort
    # sitzt ein Schloss. Klick irgendwo auf den Buegel: auf oder zu.
    # Selbst gemalt, ein Schloss-Zeichen aus der Schrift fehlt je nach System.

    toggled = Signal(bool)

    BREITE = 30
    STRICH_FARBE = "#A0A6AE"
    SCHLOSS_ZU_FARBE = "#4B5563"
    SCHLOSS_OFFEN_FARBE = "#A0A6AE"

    def __init__(self, raeder, eltern=None):
        super().__init__(eltern)
        # Die Raeder braucht es nur, um zu wissen, auf welcher Hoehe der
        # Buegel oben und unten ansetzt
        self._raeder = raeder
        self._zu = False
        self.setFixedWidth(self.BREITE)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self):
        return self._zu

    def setChecked(self, zu):
        if zu == self._zu:
            return
        self._zu = zu
        self.update()
        self.toggled.emit(zu)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._zu)
            return
        super().mousePressEvent(event)

    def _mitte_von(self, rad):
        return self.mapFromGlobal(rad.mapToGlobal(rad.rect().center())).y()

    def paintEvent(self, event):
        if not self._raeder:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        oben = self._mitte_von(self._raeder[0])
        unten = self._mitte_von(self._raeder[-1])
        mitte_y = (oben + unten) / 2
        x = self.width() / 2

        # Buegel: oben und unten ein kurzer Strich nach links an das Rad,
        # dazwischen senkrecht, um das Schloss herum ausgespart
        strich = QPen(QColor(self.STRICH_FARBE), 2)
        strich.setCapStyle(Qt.FlatCap)
        p.setPen(strich)
        p.drawLine(QPointF(0, oben), QPointF(x, oben))
        p.drawLine(QPointF(0, unten), QPointF(x, unten))
        p.drawLine(QPointF(x, oben), QPointF(x, mitte_y - 16))
        p.drawLine(QPointF(x, mitte_y + 11), QPointF(x, unten))

        farbe = QColor(self.SCHLOSS_ZU_FARBE if self._zu else self.SCHLOSS_OFFEN_FARBE)

        # Buegel des Schlosses: offen ist er ein Stueck hochgezogen und der
        # rechte Schenkel steckt nicht mehr im Koerper
        koerper_oben = mitte_y - 1
        hub = 0 if self._zu else 4
        bogen_mitte = koerper_oben - 3 - hub
        pfad = QPainterPath()
        pfad.moveTo(x - 4, koerper_oben)
        pfad.lineTo(x - 4, bogen_mitte)
        pfad.arcTo(QRectF(x - 4, bogen_mitte - 4, 8, 8), 180, -180)
        pfad.lineTo(x + 4, koerper_oben if self._zu else bogen_mitte + 1)
        p.setPen(QPen(farbe, 2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(pfad)

        # Koerper
        p.setPen(Qt.NoPen)
        p.setBrush(farbe)
        p.drawRoundedRect(QRectF(x - 6, koerper_oben, 12, 9), 2, 2)
