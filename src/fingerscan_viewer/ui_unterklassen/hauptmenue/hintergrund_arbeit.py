from PySide6.QtCore import Qt, QObject, QThread, Signal


class HauptthreadAufruf(QObject):
    # Fuehrt eine Funktion im Hauptthread aus und wartet auf ihr Ergebnis.
    # VTK und Qt-Widgets duerfen nur aus dem Hauptthread angefasst werden,
    # eine Rechnung im Hintergrund schickt ihre Plotter-Aufrufe deshalb hierueber.
    # Aus dem Hauptthread selbst wird die Funktion einfach direkt gerufen.

    _auftrag = Signal(object)

    def __init__(self, eltern=None):
        super().__init__(eltern)
        # Blocking: der Hintergrund-Thread wartet, bis der Hauptthread fertig ist
        self._auftrag.connect(self._ausfuehren, Qt.BlockingQueuedConnection)

    def _ausfuehren(self, auftrag):
        try:
            auftrag["ergebnis"] = auftrag["funktion"]()
        except BaseException as e:
            auftrag["fehler"] = e

    def __call__(self, funktion):
        if QThread.currentThread() == self.thread():
            return funktion()
        auftrag = {"funktion": funktion}
        self._auftrag.emit(auftrag)
        if "fehler" in auftrag:
            raise auftrag["fehler"]
        return auftrag.get("ergebnis")


class PlotterVertreter:
    # Steht im Hintergrund-Thread fuer den echten Plotter. Jeder Aufruf
    # (clear, add_mesh, ...) laeuft ueber HauptthreadAufruf im Hauptthread.
    # So muss isolate_finger nichts davon wissen, dass es im Hintergrund laeuft.

    def __init__(self, plotter, hauptthread):
        self._plotter = plotter
        self._hauptthread = hauptthread

    def __getattr__(self, name):
        wert = getattr(self._plotter, name)
        if not callable(wert):
            return wert
        return lambda *args, **kwargs: self._hauptthread(lambda: wert(*args, **kwargs))


class Arbeiter(QThread):
    # Fuehrt arbeit() im Hintergrund aus. Danach kommt im Hauptthread
    # fertig(ergebnis, fehler), genau eins davon ist None.

    fertig = Signal(object, object)

    def __init__(self, arbeit, eltern=None):
        super().__init__(eltern)
        self._arbeit = arbeit

    def run(self):
        try:
            ergebnis = self._arbeit()
        except BaseException as e:
            self.fertig.emit(None, e)
            return
        self.fertig.emit(ergebnis, None)
