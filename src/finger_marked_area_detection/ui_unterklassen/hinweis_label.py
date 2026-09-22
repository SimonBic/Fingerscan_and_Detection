from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QLabel, 
    QScrollArea)
import konstanten as k


class HinweisBereich(QScrollArea):
    # Scrollbereich für das HinweisLabel, damit genau so viele Zeilen angezeigt werden, wie der Text hat (maximal HINWEIS_MAX_ZEILEN)

    def _gewuenschte_hoehe(self) -> int:
        hinweis = self.widget()
        if hinweis is None:
            return super().sizeHint().height()

        zeilen_hoehe = hinweis.fontMetrics().lineSpacing()
        noetige_hoehe = hinweis.sizeHint().height()
        hoehe = min(max(noetige_hoehe, zeilen_hoehe), zeilen_hoehe * k.HINWEIS_MAX_ZEILEN)

        return hoehe + k.HINWEIS_RAND

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self._gewuenschte_hoehe())

    def minimumSizeHint(self) -> QSize:
        # Muss ebenfalls ueberschrieben werden: QAbstractScrollArea meldet
        # sonst eine Mindesthoehe aus Rahmen und Scrollbar-Breite, die
        # groesser als eine Textzeile ist und den sizeHint aushebelt.
        return QSize(super().minimumSizeHint().width(), self._gewuenschte_hoehe())


class HinweisLabel(QLabel):
    # Ein Label, welches deie Größe jeweils auf die Anzahl der Zeilen anpasst, bis zu einer maximalen Anzahl von Zeilen. 
    # Wird in einem HinweisBereich (QScrollArea) angezeigt.
    def setText(self, text: str) -> None:
        super().setText(text)
        self.updateGeometry()

        bereich = self.parentWidget()
        while bereich is not None and not isinstance(bereich, HinweisBereich):
            bereich = bereich.parentWidget()

        if bereich is not None:
            bereich.updateGeometry()
            bereich.verticalScrollBar().setValue(0)   # neue Meldung von oben zeigen
