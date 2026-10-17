import math

from PySide6.QtCore import Qt, QEvent, QObject, Signal
from PySide6.QtWidgets import QApplication, QFrame, QWidget, QGridLayout, QVBoxLayout

from pyvistaqt import QtInteractor

import konstanten as k


class ViewerKachel(QFrame):
    # Ein Viewer im Raster. Merkt sich selbst, welcher Scan in ihm geladen
    # ist, das HauptFenster liest das ueber seine Properties immer vom
    # gerade aktiven Viewer.

    def __init__(self, eltern=None):
        super().__init__(eltern)
        self.setObjectName("viewer_kachel")
        self.setProperty("aktiv", False)

        layout = QVBoxLayout(self)
        # Das VTK-Fenster ist nativ und malt ueber alles drueber, auch ueber
        # den Rand. Deshalb Platz drumherum lassen, in dem der Rand sitzt.
        layout.setContentsMargins(k.VIEWER_RAND, k.VIEWER_RAND, k.VIEWER_RAND, k.VIEWER_RAND)

        self.plotter = QtInteractor(self)
        self.plotter.set_background("F5F7FA")
        layout.addWidget(self.plotter.interactor)

        self.ordner = None
        self.teile = None
        self.hand_mesh = None

    def setze_markiert(self, markiert):
        if self.property("aktiv") == markiert:
            return
        self.setProperty("aktiv", markiert)
        # Qt wertet den Selektor [aktiv="true"] nur beim Polieren aus
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def leeren(self):
        self.ordner = None
        self.teile = None
        self.hand_mesh = None
        self.plotter.clear()
        self.plotter.render()

    def schliessen(self):
        self.plotter.close()
        self.deleteLater()


class ViewerRaster(QWidget):
    # Teilt den Viewerbereich in 1 bis 99 Viewer auf und weiss, welcher
    # davon gerade aktiv ist.
    # Tab kurz druecken: naechster Viewer. Tab halten und Rechtsklick: genau
    # diesen Viewer waehlen. Rechtsklick ohne Tab bleibt beim Picking.

    gewechselt = Signal(object)

    def __init__(self, eltern, anzahl, wechsel_erlaubt):
        super().__init__(eltern)
        # Fragt beim HauptFenster nach, ob gerade gewechselt werden darf.
        # Waehrend eines Arbeitsschritts nicht, das zeigt das HauptFenster
        # dann selbst als Hinweis an.
        self._wechsel_erlaubt = wechsel_erlaubt
        self.kacheln = []
        self.aktiv = None

        self._raster = QGridLayout(self)
        self._raster.setContentsMargins(0, 0, 0, 0)
        self._raster.setSpacing(4)
        self._raster_spalten = 0

        self._tab_gehalten = False
        self._rechtsklick_mit_tab = False

        self.setze_anzahl(anzahl)
        # App-weit, weil die Tastatur bei einem beliebigen Widget sein kann.
        # Bewusst ein eigener Filter und nicht das HauptFenster: die Pipette
        # nimmt ihren Filter mit removeEventFilter(self) wieder raus, das
        # soll diesen hier nicht mitnehmen.
        QApplication.instance().installEventFilter(self)

    # ---------- Anzahl und Anordnung ----------

    @staticmethod
    def _zeilen_aufteilung(anzahl):
        # Wie viele Viewer in welcher Zeile stehen, volle Zeilen oben.
        # 3 -> [2, 1], 5 -> [3, 2], 7 -> [3, 2, 2], 9 -> [3, 3, 3], 99 -> [10] * 9 + [9]
        spalten = math.ceil(math.sqrt(anzahl))
        zeilen = math.ceil(anzahl / spalten)
        basis, rest = divmod(anzahl, zeilen)
        return [basis + 1 if zeile < rest else basis for zeile in range(zeilen)]

    def setze_anzahl(self, anzahl):
        anzahl = min(max(int(anzahl), 1), k.VIEWER_ANZAHL_MAX)

        while len(self.kacheln) > anzahl:
            kachel = self.kacheln.pop()
            self._raster.removeWidget(kachel)
            if kachel is self.aktiv:
                self.aktiv = None
            kachel.schliessen()
        while len(self.kacheln) < anzahl:
            self.kacheln.append(ViewerKachel(self))

        if self.aktiv is None:
            self.aktiv = self.kacheln[0]

        self._anordnen()
        self._raender_setzen()
        print(f"{anzahl} viewer(s) open, viewer {self.nummer(self.aktiv)} is active")
        self.gewechselt.emit(self.aktiv)

    def _anordnen(self):
        # Nur ein QGridLayout, so bleiben alle Kacheln im selben Eltern-Widget,
        # umhaengen von nativen VTK-Fenstern geht gerne schief.
        # In einer Zeile stehen immer basis oder basis + 1 Viewer. Mit dem kgV
        # der beiden als Spaltenzahl geht jede Zeile ohne Rest auf, z.B. bei
        # Zeilen mit 3 und 2 Viewern 6 Spalten, jeder Viewer ist 2 bzw. 3 breit.
        aufteilung = self._zeilen_aufteilung(len(self.kacheln))
        spalten = math.lcm(*set(aufteilung))

        for kachel in self.kacheln:
            self._raster.removeWidget(kachel)
        for zeile in range(self._raster.rowCount()):
            self._raster.setRowStretch(zeile, 0)
        # Spalten vom letzten Mal, die es jetzt nicht mehr gibt, auf 0, sonst
        # nehmen sie als leere Spalten weiter Platz weg
        for spalte in range(max(spalten, self._raster_spalten)):
            self._raster.setColumnStretch(spalte, 1 if spalte < spalten else 0)
        self._raster_spalten = spalten

        kacheln = iter(self.kacheln)
        for zeile, anzahl_in_zeile in enumerate(aufteilung):
            breite = spalten // anzahl_in_zeile
            for platz in range(anzahl_in_zeile):
                self._raster.addWidget(next(kacheln), zeile, platz * breite, 1, breite)
            self._raster.setRowStretch(zeile, 1)

    def _raender_setzen(self):
        # Bei nur einem Viewer gibt es nichts zu unterscheiden, also kein Rand
        mehrere = len(self.kacheln) >= 2
        for kachel in self.kacheln:
            kachel.setze_markiert(mehrere and kachel is self.aktiv)

    # ---------- Wechseln ----------

    def nummer(self, kachel):
        return self.kacheln.index(kachel) + 1

    def waehle(self, kachel):
        if kachel is self.aktiv or kachel not in self.kacheln:
            return
        if not self._wechsel_erlaubt():
            return
        self.aktiv = kachel
        self._raender_setzen()
        self.gewechselt.emit(kachel)

    def naechster(self):
        index = self.kacheln.index(self.aktiv)
        self.waehle(self.kacheln[(index + 1) % len(self.kacheln)])

    def kachel_an(self, globale_pos):
        for kachel in self.kacheln:
            if kachel.rect().contains(kachel.mapFromGlobal(globale_pos)):
                return kachel
        return None

    # ---------- Tab und Tab + Rechtsklick ----------

    def _tab_zustaendig(self):
        # Nur im Hauptfenster selbst. In Dialogen, Menues und der Blase
        # soll Tab weiter ganz normal den Fokus weiterschieben.
        if len(self.kacheln) < 2:
            return False
        if QApplication.activePopupWidget() is not None or QApplication.activeModalWidget() is not None:
            return False
        return QApplication.activeWindow() is self.window()

    def eventFilter(self, obj, event):
        typ = event.type()

        # Faellt das Loslassen in ein anderes Fenster, kommt hier nie ein
        # KeyRelease an. Ohne das bliebe Tab fuer immer "gehalten".
        if typ == QEvent.WindowDeactivate and obj is self.window():
            self._tab_gehalten = False
            return False

        if typ in (QEvent.KeyPress, QEvent.KeyRelease) and event.key() == Qt.Key_Tab:
            if not self._tab_zustaendig():
                return False
            # Beim Halten schickt Qt laufend neue Tastendruecke, die sollen
            # nicht jedes Mal weiterspringen
            if event.isAutoRepeat():
                return True
            if typ == QEvent.KeyPress:
                self._tab_gehalten = True
                self._rechtsklick_mit_tab = False
            else:
                self._tab_gehalten = False
                # Wurde waehrend Tab ein Viewer angeklickt, ist der schon
                # gewaehlt, dann nicht noch eins weiter
                if not self._rechtsklick_mit_tab:
                    self.naechster()
            return True

        if (typ == QEvent.MouseButtonPress and self._tab_gehalten
                and event.button() == Qt.RightButton):
            for kachel in self.kacheln:
                if obj is kachel.plotter.interactor:
                    self._rechtsklick_mit_tab = True
                    self.waehle(kachel)
                    # Verschlucken, sonst setzt der Klick im Viewer noch
                    # einen Picking-Punkt
                    return True

        return False
