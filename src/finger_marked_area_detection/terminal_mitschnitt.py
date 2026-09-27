#Schneidet alles mit, was die Software nach stdout und stderr schreibt, damit
#man es im Terminal-Fenster nachlesen kann. Das echte Terminal bekommt
#weiterhin jede Zeile, beim Entwickeln aendert sich also nichts.

#Muss vor allen anderen Importen gestartet werden, sonst fehlt genau das,
#was beim Laden der Bibliotheken ausgegeben wird.

import sys
import threading
from collections import deque

import konstanten as k


# ---------- Puffer ----------

class _Mitschnitt:
    #Ringpuffer ueber die Zeilen. Mit maxlen, weil ein Arbeitstag mit vielen
    #Scans sonst beliebig viel Speicher belegt

    def __init__(self, max_zeilen):
        self.zeilen = deque(maxlen=max_zeilen)
        self.verworfen = 0
        self.geschrieben = 0
        # Angefangene Zeile ohne Zeilenumbruch. print() schreibt Text und
        # Umbruch getrennt, ohne das hier waere jede Ausgabe doppelt geteilt
        self._rest = ""
        # Ausgaben koennen aus jedem Thread kommen (Qt, VTK)
        self._schloss = threading.Lock()

    def dazu(self, text):
        with self._schloss:
            self._rest += text
            *fertig, self._rest = self._rest.split("\n")
            for zeile in fertig:
                if len(self.zeilen) == self.zeilen.maxlen:
                    self.verworfen += 1
                self.zeilen.append(zeile)
                self.geschrieben += 1

    def text(self):
        with self._schloss:
            alles = list(self.zeilen)
            if self._rest:
                alles.append(self._rest)
            verworfen = self.verworfen
        if verworfen:
            alles.insert(0, f"[... {verworfen} aeltere Zeilen sind aus dem Puffer gelaufen ...]")
        return "\n".join(alles)

    def leeren(self):
        with self._schloss:
            self.zeilen.clear()
            self.verworfen = 0
            self._rest = ""
            self.geschrieben += 1      # damit die Anzeige den Stand als geaendert sieht


# ---------- Weiche vor die echten Stroeme ----------

class _Weiche:
    #Haengt sich vor sys.stdout bzw. sys.stderr und schreibt in beide
    #Richtungen: in den Puffer und weiter ans echte Terminal

    def __init__(self, original, puffer):
        self._original = original
        self._puffer = puffer

    def write(self, text):
        self._puffer.dazu(text)
        if self._original is not None:
            self._original.write(text)
            
            self._original.flush()
        return len(text)

    def writelines(self, zeilen):
        for zeile in zeilen:
            self.write(zeile)

    def flush(self):
        if self._original is not None:
            self._original.flush()

    def isatty(self):
        return self._original is not None and self._original.isatty()

    def fileno(self):
        # Ohne Konsole (z.B. als Fenster-Anwendung gestartet) gibt es keine
        if self._original is None:
            raise OSError("kein echter Datenstrom vorhanden")
        return self._original.fileno()

    def __getattr__(self, name):
        # encoding, writable und was Bibliotheken sonst noch abfragen
        return getattr(self._original, name)


# ---------- Starten ----------

_puffer = None


def starte_mitschnitt():
    # Nur einmal: ein zweiter Aufruf haengte eine Weiche vor die Weiche und
    # jede Zeile landete doppelt im Puffer
    global _puffer
    if _puffer is None:
        _puffer = _Mitschnitt(k.TERMINAL_MAX_ZEILEN)
        sys.stdout = _Weiche(sys.stdout, _puffer)
        sys.stderr = _Weiche(sys.stderr, _puffer)
        # Abstuerze braucht es nicht eigens abzufangen: Python schreibt sie
        # nach sys.stderr, und der laeuft ab hier durch den Puffer.
        # Die Meldungen von VTK kommen ebenfalls an: die schreibt zwar C++
        # direkt ins Terminal, pyvista holt sie aber ueber logging noch einmal
        # nach sys.stderr. Deshalb muss der Mitschnitt vor pyvista stehen.
    return _puffer


def hole_text():
    if _puffer is None:
        return ("Der Mitschnitt laeuft nicht.\n\n"
                "starte_mitschnitt() muss in main.py aufgerufen werden, bevor "
                "die uebrigen Module importiert werden.")
    return _puffer.text()


def stand():
    # Zaehler ueber alle je geschriebenen Zeilen. Die Anzeige liest daran ab,
    # ob sich etwas getan hat, statt jedes Mal den ganzen Text zu vergleichen
    return 0 if _puffer is None else _puffer.geschrieben


def leeren():
    if _puffer is not None:
        _puffer.leeren()
