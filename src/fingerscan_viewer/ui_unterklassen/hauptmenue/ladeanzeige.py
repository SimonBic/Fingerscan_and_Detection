import numpy as np

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QImage
from PySide6.QtWidgets import QWidget

import konstanten as k


class Ladeanzeige(QWidget):
    # Legt sich ueber einen Viewer, solange im Hintergrund gerechnet wird:
    # der Viewer blass dahinter, in der Mitte dreht sich ein blauer Kreis.
    #
    # Das VTK-Fenster ist ein natives Fenster, darueber laesst sich nichts
    # halbdurchsichtig legen. Deshalb ein Standbild des Viewers, das hier
    # selbst mit 50 % Deckkraft gemalt wird. Dafuer ist die Anzeige komplett
    # undurchsichtig und kann ein eigenes natives Fenster sein, das sicher
    # ueber dem VTK-Fenster liegt.

    def __init__(self, kachel):
        super().__init__(kachel)
        # Eigenes natives Fenster, aber ohne die Eltern mit umzubauen. Das
        # wuerde das VTK-Fenster der Kachel neu einhaengen.
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)

        self._bild = self._standbild(kachel.plotter)
        self._winkel = 0
        self.setGeometry(kachel.plotter.interactor.geometry())

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._drehen)
        self._timer.start()

        self.show()
        self.raise_()

    @staticmethod
    def _standbild(plotter):
        try:
            bild = plotter.screenshot(return_img=True)
        except Exception as e:
            # Ohne Standbild geht es auch, dann nur der Kreis auf hellem Grund
            print(f"No still image of the viewer for the loading overlay: {e}")
            return None
        bild = np.ascontiguousarray(bild[:, :, :3])
        hoehe, breite = bild.shape[:2]
        # copy(): das QImage zeigt sonst auf den Speicher des numpy-Arrays
        return QImage(bild.data, breite, hoehe, 3 * breite, QImage.Format_RGB888).copy()

    def _drehen(self):
        self._winkel = (self._winkel + k.LADEKREIS_GRAD_PRO_BILD) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(k.LADE_HINTERGRUND))
        if self._bild is not None:
            p.setOpacity(k.LADE_VIEWER_DECKKRAFT)
            p.drawImage(QRectF(self.rect()), self._bild)
            p.setOpacity(1.0)

        radius = min(max(min(self.width(), self.height()) * 0.06, 18), 40)
        mitte = QRectF(self.rect()).center()
        kreis = QRectF(mitte.x() - radius, mitte.y() - radius, 2 * radius, 2 * radius)
        stift = QPen(QColor(k.LADEKREIS_FARBE), max(4, radius / 5))
        stift.setCapStyle(Qt.RoundCap)
        p.setPen(stift)
        # Qt zaehlt in 1/16 Grad, gegen den Uhrzeigersinn. Minus dreht ihn
        # im Uhrzeigersinn, ein Viertel bleibt als Luecke offen.
        p.drawArc(kreis, int(-self._winkel * 16), 270 * 16)

    def schliessen(self):
        self._timer.stop()
        self.hide()
        self.deleteLater()
