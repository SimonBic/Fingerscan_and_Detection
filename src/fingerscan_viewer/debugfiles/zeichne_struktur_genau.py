#Wie zeichne_struktur.py, aber eine Ebene tiefer: jede Klasse, jede Methode
#und jede Funktion, und wer wen aufruft. Liest den Code ueber den AST, laeuft
#also nichts davon aus.

#Zwei Arten von Beziehungen:
#    Aufruf    self.methode(), funktion(), modul.funktion(), Klasse(...)
#    Verweis   die Methode wird nicht aufgerufen, sondern weitergegeben, z.B.
#              knopf.clicked.connect(self.isolieren_klick) oder
#              bei_punkt_gesetzt=self._isolieren_punkt_gesetzt. Bei Qt ist das
#              oft die eigentliche Verbindung, deshalb zaehlt sie mit.

#self.methode() wird erst in der eigenen Klasse gesucht, dann in deren
#Basisklassen, und zuletzt in Klassen, die von ihr erben. Letzteres fuer die
#Mixins: UI_Aufbau_Mixin ruft self.isolieren_klick, das steht in HauptFenster.

#self.attribut.methode() geht auch, wenn irgendwo self.attribut = Klasse(...)
#steht, z.B. self.viewer_raster = ViewerRaster(...). Tiefer (self.a.b.c())
#nicht, dafuer muesste man den Code ausfuehren.

#Ein Aufruf in einem lambda zaehlt als Verweis, nicht als Aufruf: er laeuft
#erst spaeter, z.B. clicked.connect(lambda: self.pipette_aktivieren(...)).

#Aufrufe in Fremdpakete (numpy, PySide6, pyvista ...) und auf Qt-Methoden wie
#self.setWindowTitle bleiben weg, die gehoeren nicht in dieses Bild.

#Aufruf:
#    python debugfiles/zeichne_struktur_genau.py --je-modul ORDNER      empfohlen: ORDNER/index.svg als Uebersicht,
#                                                                       dazu eine Seite je Modul, alles klickbar
#    python debugfiles/zeichne_struktur_genau.py --modul NAME --svg Z  nur eine Modulseite
#    python debugfiles/zeichne_struktur_genau.py --svg ZIEL.svg        alles in einem Bild (sehr gross)
#    python debugfiles/zeichne_struktur_genau.py --pdf ZIEL.pdf        dasselbe als PDF
#    python debugfiles/zeichne_struktur_genau.py                       Graphviz (.dot) auf die Konsole
#    --ohne-verweise    nur echte Aufrufe, keine weitergegebenen Methoden
#    --hoch             von oben nach unten statt quer

#Die SVGs im Browser oeffnen (Datei ins Fenster ziehen): stufenlos zoomen,
#Strg+F sucht Methoden, Maus ueber einem Kasten zeigt Signatur und Kommentar,
#Klick auf ein Modul oder eine fremde Methode springt auf deren Seite.

#Jede Modulseite ist gleich aufgebaut: links, wer das Modul aufruft, in der
#Mitte das Modul selbst (Klassen, darin die Abschnitte aus den
#"# ---------- Titel ----------" Kommentaren), rechts, was es aufruft.

#Am einfachsten, geht im normalen Terminal und im Terminal von VS Code:
# cd /home/simonbichler/Arbeit/UKR/Code/repo/Fingerscan_and_Detection
# python src/fingerscan_viewer/debugfiles/zeichne_struktur_genau.py --je-modul docs/struktur

import ast
import html
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

PAKET = Path(__file__).resolve().parent.parent

#Wie in zeichne_struktur.py: alter Code und Werkzeuge stellen das Bild nur voll
UEBERSPRINGEN = ("prototyp", "debugfiles", "__pycache__")

#Farben aus theme.py, wie in zeichne_struktur.py
STIL = {
    "wurzel": ("#FFFFFF", "#1F2937"),
    "logik":  ("#D6E4F0", "#4A90D9"),
    "ui":     ("#EDEFF2", "#9AA3AE"),
}

#Laengere Kommentare werden im Tooltip abgeschnitten
BESCHREIBUNG_MAX = 220

#Abstaende im Graphen, in Zoll wie bei Graphviz. Bei ueber 300 Methoden
#liegt sonst alles so dicht, dass man die Pfeile nicht auseinanderhalten kann.
ABSTAND_KNOTEN = 0.45       #zwischen Kaesten nebeneinander
ABSTAND_EBENEN = 2.0        #zwischen den Ebenen, in Pfeilrichtung
CLUSTER_RAND = 20           #Punkte zwischen Rahmen und Inhalt
SCHRIFT_KNOTEN = 12
SCHRIFT_ABSCHNITT = 12
SCHRIFT_KLASSE = 14
SCHRIFT_MODUL = 18

#Fremde Methoden auf einer Modulseite: blass, damit das Modul selbst vorne steht
FREMD_FUELLUNG = "#FFFFFF"
FREMD_RAND = "#C7CDD4"
FREMD_SCHRIFT = "#6B7280"
PFEIL_INNEN = "#4B5563"
PFEIL_AUSSEN = "#B8BEC6"

#Ab so vielen Funktionen und Methoden bekommt ein Modul keine eigene
#Detailseite mehr, sondern eine Seite je Abschnitt. Eine Seite mit ueber 100
#Methoden ist nicht mehr zu lesen. Betrifft im Moment nur userinterface.
GROSS_AB = 40
OHNE_ABSCHNITT = "ohne Abschnitt"

#Abschnitts-Ueberschriften im Code, z.B. "# ---------- Finger isolieren ----------"
#oder "#--- heatmap -----". Der Titel ist alles zwischen den Strichen.
ABSCHNITT_MUSTER = re.compile(r"^(\s*)#+\s*-{3,}\s*(.*?)[\s-]*$")


# ---------- Datenmodell ----------

@dataclass
class Funktion:
    modul: str
    klasse: str | None          #None bei Funktionen auf Modulebene
    name: str
    zeile: int
    signatur: str
    beschreibung: str
    art: str = ""               #"property", "staticmethod", "classmethod" oder leer
    knoten: ast.AST = None
    abschnitt: str = ""         #Titel der letzten Abschnitts-Ueberschrift davor

    @property
    def kennung(self):
        return f"{self.modul}:{self.klasse}.{self.name}" if self.klasse else f"{self.modul}:{self.name}"

    @property
    def kurz(self):
        return f"{self.klasse}.{self.name}" if self.klasse else self.name


@dataclass
class Klasse:
    modul: str
    name: str
    zeile: int
    basen: list                 #Namen wie im Code geschrieben
    beschreibung: str
    methoden: dict = field(default_factory=dict)
    basen_im_paket: list = field(default_factory=list)   #(modul, klasse), nach dem Aufloesen

    @property
    def kennung(self):
        return f"{self.modul}:{self.name}"


# ---------- Einlesen ----------

def modulname(pfad):
    return ".".join(pfad.relative_to(PAKET).with_suffix("").parts)


def paket_module():
    module = {}
    for datei in sorted(PAKET.rglob("*.py")):
        if any(teil in UEBERSPRINGEN for teil in datei.relative_to(PAKET).parts):
            continue
        module[modulname(datei)] = datei
    return module


def beschreibung_von(knoten, quelltext_zeilen):
    #Docstring, falls es einen gibt. Sonst die Kommentarzeilen direkt unter
    #der def- bzw. class-Zeile, so sind die meisten Funktionen hier beschrieben.
    doc = ast.get_docstring(knoten)
    if doc:
        text = " ".join(doc.split())
    else:
        if not knoten.body:
            return ""
        zeilen = []
        for nummer in range(knoten.lineno, knoten.body[0].lineno - 1):
            zeile = quelltext_zeilen[nummer].strip()
            if zeile.startswith("#"):
                zeilen.append(zeile.lstrip("#").strip())
            elif zeilen and not zeile:
                break
        text = " ".join(z for z in zeilen if z)
    if len(text) > BESCHREIBUNG_MAX:
        text = text[:BESCHREIBUNG_MAX].rsplit(" ", 1)[0] + " ..."
    return text


def signatur_von(knoten):
    #Parameter wie im Code, ohne self und cls
    args = knoten.args
    teile = ast.unparse(args).split(", ") if (args.args or args.posonlyargs or args.vararg
                                              or args.kwonlyargs or args.kwarg) else []
    if teile and teile[0] in ("self", "cls"):
        teile = teile[1:]
    return f"{knoten.name}({', '.join(teile)})"


def art_von(knoten):
    for deko in knoten.decorator_list:
        name = deko.id if isinstance(deko, ast.Name) else getattr(deko, "attr", "")
        if name in ("property", "staticmethod", "classmethod"):
            return name
        if name in ("setter", "getter", "deleter"):
            return "property"
    return ""


def abschnitte_finden(zeilen):
    #(zeile, einzug, titel) jeder Abschnitts-Ueberschrift
    gefunden = []
    for nummer, zeile in enumerate(zeilen, start=1):
        treffer = ABSCHNITT_MUSTER.match(zeile)
        if treffer and treffer.group(2):
            gefunden.append((nummer, len(treffer.group(1)), treffer.group(2)))
    return gefunden


def abschnitt_fuer(abschnitte, zeile, einzug, ab_zeile=0):
    #Die letzte Ueberschrift vor der def-Zeile, auf derselben Einrueckung.
    #Ueberschriften innerhalb einer Methode (tiefer eingerueckt) zaehlen
    #nicht, und bei Methoden nur die innerhalb der Klasse.
    titel = ""
    for nummer, ueber_einzug, ueber_titel in abschnitte:
        if nummer >= zeile:
            break
        if ueber_einzug == einzug and nummer > ab_zeile:
            titel = ueber_titel
    return titel


def modul_einlesen(name, datei, funktionen, klassen):
    quelltext = datei.read_text(encoding="utf-8")
    zeilen = quelltext.splitlines()
    abschnitte = abschnitte_finden(zeilen)
    baum = ast.parse(quelltext)
    for knoten in baum.body:
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f = Funktion(name, None, knoten.name, knoten.lineno, signatur_von(knoten),
                         beschreibung_von(knoten, zeilen), art_von(knoten), knoten)
            f.abschnitt = abschnitt_fuer(abschnitte, knoten.lineno, knoten.col_offset)
            funktionen[f.kennung] = f
        elif isinstance(knoten, ast.ClassDef):
            k = Klasse(name, knoten.name, knoten.lineno,
                       [ast.unparse(b) for b in knoten.bases], beschreibung_von(knoten, zeilen))
            for teil in knoten.body:
                if not isinstance(teil, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                #Property mit Setter: zweimal derselbe Name, einmal reicht
                if teil.name in k.methoden:
                    continue
                f = Funktion(name, knoten.name, teil.name, teil.lineno, signatur_von(teil),
                             beschreibung_von(teil, zeilen), art_von(teil), teil)
                f.abschnitt = abschnitt_fuer(abschnitte, teil.lineno, teil.col_offset, knoten.lineno)
                k.methoden[teil.name] = f
                funktionen[f.kennung] = f
            klassen[k.kennung] = k
    return baum


def namen_aus_importen(baum, module):
    #Welcher Name in diesem Modul steht fuer was aus dem eigenen Paket?
    #    from logik.isolate_finger import rendere_teile   -> ("logik.isolate_finger", "rendere_teile")
    #    import konstanten as k                           -> ("konstanten", None), also ein Modul
    namen = {}
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.module in module and knoten.level == 0:
            for a in knoten.names:
                namen[a.asname or a.name] = (knoten.module, a.name)
        elif isinstance(knoten, ast.Import):
            for a in knoten.names:
                if a.name in module:
                    namen[a.asname or a.name] = (a.name, None)
    return namen


# ---------- Beziehungen aufloesen ----------

class Aufloeser:
    def __init__(self, funktionen, klassen, importe):
        self.funktionen = funktionen
        self.klassen = klassen
        self.importe = importe          #modul -> {lokaler Name: (modul, name)}
        self._basen_aufloesen()
        #Wer erbt von wem, fuer die Suche in Unterklassen (Mixins)
        self.erben = defaultdict(list)
        for k in klassen.values():
            for basis in k.basen_im_paket:
                self.erben[basis].append(k.kennung)
        self.attribut_typen = self._attribut_typen_sammeln()

    def _attribut_typen_sammeln(self):
        #(klasse, attribut) -> Klasse aus dem Paket, aus self.attribut = Klasse(...)
        typen = {}
        for k in self.klassen.values():
            for f in k.methoden.values():
                for knoten in ast.walk(f.knoten):
                    if not isinstance(knoten, ast.Assign) or not isinstance(knoten.value, ast.Call):
                        continue
                    ziel_klasse = self.ziel_von(knoten.value.func, f, ohne_attribute=True)
                    if ziel_klasse not in self.klassen:
                        continue
                    for ziel in knoten.targets:
                        if isinstance(ziel, ast.Attribute) and isinstance(ziel.value, ast.Name) \
                                and ziel.value.id == "self":
                            typen[(k.kennung, ziel.attr)] = ziel_klasse
        return typen

    def attribut_typ(self, klassen_kennung, attribut, gesehen=None):
        #Wie bei den Methoden: eigene Klasse, Basen, dann Unterklassen
        gesehen = gesehen or set()
        if klassen_kennung in gesehen:
            return None
        gesehen.add(klassen_kennung)
        if (klassen_kennung, attribut) in self.attribut_typen:
            return self.attribut_typen[(klassen_kennung, attribut)]
        k = self.klassen.get(klassen_kennung)
        for andere in (k.basen_im_paket if k else []) + self.erben.get(klassen_kennung, []):
            treffer = self.attribut_typ(andere, attribut, gesehen)
            if treffer:
                return treffer
        return None

    def _basen_aufloesen(self):
        for k in self.klassen.values():
            for basis in k.basen:
                ziel = self.name_im_modul(k.modul, basis)
                if ziel in self.klassen:
                    k.basen_im_paket.append(ziel)

    def name_im_modul(self, modul, name):
        #Kennung einer Funktion oder Klasse, die unter diesem Namen im Modul
        #sichtbar ist, sonst None
        if f"{modul}:{name}" in self.funktionen or f"{modul}:{name}" in self.klassen:
            return f"{modul}:{name}"
        quelle = self.importe[modul].get(name)
        if quelle and quelle[1] is not None:
            return f"{quelle[0]}:{quelle[1]}"
        return None

    def methode_suchen(self, klassen_kennung, name, gesehen=None):
        #Erst die Klasse selbst, dann ihre Basisklassen im Paket
        gesehen = gesehen or set()
        if klassen_kennung in gesehen or klassen_kennung not in self.klassen:
            return None
        gesehen.add(klassen_kennung)
        k = self.klassen[klassen_kennung]
        if name in k.methoden:
            return k.methoden[name].kennung
        for basis in k.basen_im_paket:
            treffer = self.methode_suchen(basis, name, gesehen)
            if treffer:
                return treffer
        return None

    def self_methode(self, klassen_kennung, name):
        treffer = self.methode_suchen(klassen_kennung, name)
        if treffer:
            return treffer
        #Mixin: die Methode steht in einer Klasse, die vom Mixin erbt
        for unter in self.erben.get(klassen_kennung, []):
            treffer = self.self_methode(unter, name)
            if treffer:
                return treffer
        return None

    def ziel_von(self, ausdruck, funktion, ohne_attribute=False):
        #Worauf zeigt ein Ausdruck wie self.x, x, modul.x oder self.a.x?
        #Kennung oder None. ohne_attribute: beim Sammeln der Attribut-Typen
        #gibt es die noch nicht.
        if not ohne_attribute and isinstance(ausdruck, ast.Attribute) \
                and isinstance(ausdruck.value, ast.Attribute) \
                and isinstance(ausdruck.value.value, ast.Name) and ausdruck.value.value.id == "self" \
                and funktion.klasse:
            typ = self.attribut_typ(f"{funktion.modul}:{funktion.klasse}", ausdruck.value.attr)
            return self.methode_suchen(typ, ausdruck.attr) if typ else None
        if isinstance(ausdruck, ast.Attribute) and isinstance(ausdruck.value, ast.Name):
            vorne = ausdruck.value.id
            if vorne in ("self", "cls") and funktion.klasse:
                return self.self_methode(f"{funktion.modul}:{funktion.klasse}", ausdruck.attr)
            quelle = self.importe[funktion.modul].get(vorne)
            if quelle and quelle[1] is None:
                ziel = f"{quelle[0]}:{ausdruck.attr}"
                if ziel in self.funktionen or ziel in self.klassen:
                    return ziel
            #Klasse.methode, z.B. LoeschDialog.ENDGUELTIG oder ViewerRaster._zeilen_aufteilung
            klasse = self.name_im_modul(funktion.modul, vorne)
            if klasse in self.klassen:
                return self.methode_suchen(klasse, ausdruck.attr)
        elif isinstance(ausdruck, ast.Name):
            return self.name_im_modul(funktion.modul, ausdruck.id)
        return None

    def beziehungen(self, funktion):
        #Gibt (aufrufe, verweise) zurueck, je eine Menge von Kennungen.
        #Verschachtelte Funktionen und lambdas zaehlen zur umgebenden Funktion.
        aufrufe, verweise = set(), set()
        aufgerufen = set()
        #Alles innerhalb eines lambdas laeuft erst spaeter
        in_lambda = {id(innen) for knoten in ast.walk(funktion.knoten) if isinstance(knoten, ast.Lambda)
                     for innen in ast.walk(knoten.body)}
        for knoten in ast.walk(funktion.knoten):
            if isinstance(knoten, ast.Call):
                aufgerufen.add(id(knoten.func))
                ziel = self.ziel_von(knoten.func, funktion)
                if ziel:
                    (verweise if id(knoten) in in_lambda else aufrufe).add(ziel)
        for knoten in ast.walk(funktion.knoten):
            #Alles, was auf eine Methode zeigt, ohne selbst aufgerufen zu werden
            if isinstance(knoten, (ast.Attribute, ast.Name)) and id(knoten) not in aufgerufen \
                    and isinstance(knoten.ctx, ast.Load):
                ziel = self.ziel_von(knoten, funktion)
                if ziel and ziel in self.funktionen and self.funktionen[ziel].art != "property":
                    verweise.add(ziel)
        aufrufe.discard(funktion.kennung)
        verweise.discard(funktion.kennung)
        return aufrufe, verweise - aufrufe


def alles_einlesen():
    module = paket_module()
    funktionen, klassen, importe = {}, {}, {}
    for name, datei in module.items():
        baum = modul_einlesen(name, datei, funktionen, klassen)
        importe[name] = namen_aus_importen(baum, module)
    aufloeser = Aufloeser(funktionen, klassen, importe)
    aufrufe, verweise = {}, {}
    for kennung, f in funktionen.items():
        aufrufe[kennung], verweise[kennung] = aufloeser.beziehungen(f)
    return module, funktionen, klassen, aufrufe, verweise


def modul_von(kennung):
    return kennung.split(":")[0]


# ---------- Bausteine fuer Graphviz ----------

def stil_fuer(modul):
    if modul.startswith("logik."):
        return "logik"
    if modul.startswith("ui_unterklassen."):
        return "ui"
    return "wurzel"


def anzahl_text(n, einzahl, mehrzahl):
    return f"{n} {einzahl if n == 1 else mehrzahl}"


def kurzname(modul):
    return modul.replace("ui_unterklassen.", "ui/")


def seite_von(modul):
    #Dateiname der Modulseite, die Links zeigen darauf
    return f"{modul}.svg"


def dot_text(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def tooltip_text(f):
    #Steht im SVG, wenn die Maus ueber dem Kasten ist. Im PDF ohne Wirkung.
    text = f"{f.signatur}\nZeile {f.zeile} in {f.modul}"
    if f.beschreibung:
        text += f"\n\n{f.beschreibung}"
    return text


def tooltip(f):
    #Fuer normale Graphviz-Attribute. Echte Zeilenumbrueche als \n schreiben,
    #so liest Graphviz sie. Erst nach dot_text, das wuerde den Backslash sonst
    #nochmal verdoppeln.
    return dot_text(tooltip_text(f)).replace("\n", "\\n")


def kopf(name, richtung):
    return [
        f"digraph {name} {{",
        f"    rankdir={richtung};",
        f"    compound=true; newrank=true; nodesep={ABSTAND_KNOTEN}; ranksep={ABSTAND_EBENEN}; pad=0.6;",
        #Kein margin hier: im obersten Graphen waeren das Zoll Rand ums ganze Bild
        f'    graph [fontname="Helvetica" fontsize={SCHRIFT_MODUL}];',
        f'    node [shape=box style="filled,rounded" fontname="Helvetica" fontsize={SCHRIFT_KNOTEN} '
        f'height=0.4 margin="0.18,0.08"];',
        f'    edge [color="{PFEIL_INNEN}" arrowsize=0.8 penwidth=1.1];',
    ]


def knoten_zeile(f, einzug, fremd=False, mit_klasse=False):
    name = f.kurz if mit_klasse else f.name
    beschriftung = name if f.klasse else f"{name}()"
    if fremd:
        #Klick auf eine fremde Methode oeffnet die Seite ihres Moduls
        farben = (f'fillcolor="{FREMD_FUELLUNG}" color="{FREMD_RAND}" fontcolor="{FREMD_SCHRIFT}" '
                  f'URL="{seite_von(f.modul)}" target="_top"')
    else:
        fuellung, rand = STIL[stil_fuer(f.modul)]
        farben = f'fillcolor="{fuellung}" color="{rand}"'
    return f'{einzug}"{f.kennung}" [label="{dot_text(beschriftung)}" tooltip="{tooltip(f)}" {farben}];'


def nach_abschnitt(liste):
    #In Code-Reihenfolge, je Abschnitt zusammengefasst: [(titel, [f, ...]), ...]
    gruppen = []
    for f in sorted(liste, key=lambda f: f.zeile):
        if not gruppen or gruppen[-1][0] != f.abschnitt:
            gruppen.append((f.abschnitt, []))
        gruppen[-1][1].append(f)
    return gruppen


def abschnitte_zeilen(liste, einzug, praefix):
    #Funktionen, je Abschnitt in einem eigenen gestrichelten Rahmen. Ohne
    #Abschnitt stehen sie frei.
    zeilen = []
    for nummer, (titel, gruppe) in enumerate(nach_abschnitt(liste)):
        if titel:
            zeilen.append(f"{einzug}subgraph cluster_{praefix}_a{nummer} {{")
            zeilen.append(f'{einzug}    label="{dot_text(titel)}"; style="rounded,dashed"; color="#C7CDD4"; '
                          f'fontsize={SCHRIFT_ABSCHNITT}; fontcolor="#6B7280"; margin=12;')
            zeilen += [knoten_zeile(f, einzug + "    ") for f in gruppe]
            zeilen.append(f"{einzug}}}")
        else:
            zeilen += [knoten_zeile(f, einzug) for f in gruppe]
    return zeilen


def modul_zeilen(modul, funktionen, klassen, klassen_ziele, nummer, einzug="    "):
    #Ein Modul mit seinen Klassen und Funktionen, als Rahmen
    fuellung, rand = STIL[stil_fuer(modul)]
    zeilen = [f"{einzug}subgraph cluster_m{nummer} {{",
              f'{einzug}    label="{kurzname(modul)}"; color="{rand}"; style="rounded"; penwidth=2; '
              f'fontsize={SCHRIFT_MODUL}; margin={CLUSTER_RAND};']
    eigene_klassen = sorted((k for k in klassen.values() if k.modul == modul), key=lambda k: k.zeile)
    for k_nr, k in enumerate(eigene_klassen):
        basen = f"({', '.join(k.basen)})" if k.basen else ""
        zeilen.append(f"{einzug}    subgraph cluster_m{nummer}_k{k_nr} {{")
        zeilen.append(f'{einzug}        label="class {dot_text(k.name + basen)}"; color="#D8DEE6"; '
                      f'style="rounded,filled"; fillcolor="#FAFBFC"; fontsize={SCHRIFT_KLASSE}; '
                      f'margin={CLUSTER_RAND};')
        if k.kennung in klassen_ziele:
            zeilen.append(f'{einzug}        "{k.kennung}" [label="{dot_text(k.name)}(...)" shape=ellipse '
                          f'tooltip="{dot_text(k.beschreibung or k.name)}" fillcolor="{fuellung}" color="{rand}"];')
        methoden = [f for f in k.methoden.values() if f.kennung in funktionen]
        zeilen += abschnitte_zeilen(methoden, einzug + "        ", f"m{nummer}_k{k_nr}")
        zeilen.append(f"{einzug}    }}")
    lose = [f for f in funktionen.values() if f.modul == modul and not f.klasse]
    zeilen += abschnitte_zeilen(lose, einzug + "    ", f"m{nummer}_f")
    zeilen.append(f"{einzug}}}")
    return zeilen


def kanten_zeilen(aufrufe, verweise, bekannt, innen=None, endpunkte=None):
    #innen: Kennungen des Moduls einer Modulseite. Pfeile nach aussen und
    #von aussen werden dann blasser, damit die inneren hervorstehen.
    #endpunkte: Kennung -> wo der Pfeil in Graphviz ansetzt, fuer die
    #Zeilen in den Listen der fremden Module ("knoten":zeile).
    endpunkte = endpunkte or {}
    zeilen = []
    for kanten, gestrichelt in ((aufrufe, False), (verweise, True)):
        for von in sorted(kanten):
            for nach in sorted(kanten[von]):
                if von not in bekannt or nach not in bekannt:
                    continue
                #Auf einer Modulseite nur, was das Modul betrifft. Pfeile
                #zwischen zwei fremden Methoden gehoeren auf deren Seite.
                if innen is not None and von not in innen and nach not in innen:
                    continue
                attribute = []
                if gestrichelt:
                    attribute.append("style=dashed")
                if innen is not None and not (von in innen and nach in innen):
                    attribute.append(f'color="{PFEIL_AUSSEN}"')
                elif gestrichelt:
                    attribute.append('color="#A0A6AE"')
                start = endpunkte.get(von, f'"{von}"')
                ziel = endpunkte.get(nach, f'"{nach}"')
                zeilen.append(f"    {start} -> {ziel}" + (f" [{' '.join(attribute)}];" if attribute else ";"))
    return zeilen


# ---------- Die drei Ansichten ----------

def dot_alles(funktionen, klassen, aufrufe, verweise, richtung="LR"):
    #Alles in einem Bild. Bei der Menge unuebersichtlich, --je-modul ist besser.
    zeilen = kopf("struktur_genau", richtung)
    klassen_ziele = {z for ziele in aufrufe.values() for z in ziele if z in klassen}
    module = sorted({f.modul for f in funktionen.values()} | {k.modul for k in klassen.values()})
    for nummer, modul in enumerate(module):
        zeilen += modul_zeilen(modul, funktionen, klassen, klassen_ziele, nummer)
    zeilen += kanten_zeilen(aufrufe, verweise, set(funktionen) | klassen_ziele)
    zeilen.append("}")
    return "\n".join(zeilen)


def html_text(text):
    #Fuer die HTML-Beschriftungen von Graphviz
    return html.escape(text, quote=True)


@dataclass
class Gruppe:
    #Was auf einer Detailseite in der Mitte steht: ein ganzes Modul, oder bei
    #grossen Modulen ein Abschnitt daraus
    modul: str
    abschnitt: str | None
    kennungen: set = field(default_factory=set)

    @property
    def name(self):
        return self.modul if self.abschnitt is None else f"{self.modul}#{self.abschnitt}"

    @property
    def seite(self):
        if self.abschnitt is None:
            return seite_von(self.modul)
        #Dateiname aus dem Titel: "Drag & Drop / Laden" -> "drag_drop_laden"
        kurz = self.abschnitt.lower()
        for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            kurz = kurz.replace(alt, neu)
        kurz = re.sub(r"[^a-z0-9]+", "_", kurz).strip("_")
        return f"{self.modul}__{kurz}.svg"

    @property
    def titel(self):
        return kurzname(self.modul) if self.abschnitt is None else f"{kurzname(self.modul)}: {self.abschnitt}"


def gruppen_bilden(funktionen, klassen):
    #Gibt ({gruppenname: Gruppe}, {kennung: Gruppe}, {modul, das aufgeteilt ist}) zurueck
    nach_modul = defaultdict(list)
    for kennung, f in funktionen.items():
        nach_modul[f.modul].append(kennung)
    for kennung, k in klassen.items():
        nach_modul[k.modul].append(kennung)

    gruppen, von = {}, {}
    aufgeteilt = set()
    for modul, kennungen in nach_modul.items():
        gross = sum(1 for k in kennungen if k in funktionen) > GROSS_AB
        if gross:
            aufgeteilt.add(modul)
        for kennung in kennungen:
            if not gross:
                abschnitt = None
            elif kennung in funktionen:
                abschnitt = funktionen[kennung].abschnitt or OHNE_ABSCHNITT
            else:
                #Eine Klasse gehoert zum Abschnitt ihres __init__
                init = klassen[kennung].methoden.get("__init__")
                abschnitt = (init.abschnitt if init and init.abschnitt else OHNE_ABSCHNITT)
            g = Gruppe(modul, abschnitt)
            g = gruppen.setdefault(g.name, g)
            g.kennungen.add(kennung)
            von[kennung] = g
    return gruppen, von, aufgeteilt


def html_text(text):
    #Fuer die HTML-Beschriftungen von Graphviz
    return html.escape(text, quote=True)


def titel_html(titel, zurueck):
    #Ueberschrift mit Links zurueck, [(text, seite), ...], als HTML-Tabelle
    links = "".join(f'<TD HREF="{seite}" TARGET="_top" TOOLTIP="{html_text(text)}">'
                    f'<FONT COLOR="#4A90D9" POINT-SIZE="18">&#9664; {html_text(text)}</FONT></TD>'
                    for text, seite in zurueck)
    return (f'<TABLE BORDER="0" CELLSPACING="12"><TR>{links}'
            f'<TD><FONT POINT-SIZE="24">{html_text(titel)}</FONT></TD></TR></TABLE>')


def kopf_zeile(titel, zurueck):
    #Als Beschriftung des ganzen Bildes. Als eigene Kaesten wuerde Graphviz
    #die Links irgendwo in die erste Spalte legen.
    return f'    label=<{titel_html(titel, zurueck)}>; labelloc=t;'


def zurueck_links(gruppe):
    if gruppe.abschnitt is None:
        return [("Übersicht", "index.svg")]
    return [("Übersicht", "index.svg"), (kurzname(gruppe.modul), seite_von(gruppe.modul))]


def fremd_liste(knoten_name, gruppe, kennungen, funktionen, klassen):
    #Eine fremde Gruppe (Modul oder Abschnitt) als kompakte Liste, eine Zeile
    #je Methode. Viel ruhiger als ein Kasten je Methode. Die Pfeile setzen an
    #der jeweiligen Zeile an, Klick oeffnet die Seite der Gruppe.
    #Gibt (zeile fuer Graphviz, {kennung: endpunkt}) zurueck.
    reihen = [f'<TR><TD HREF="{gruppe.seite}" TARGET="_top" BGCOLOR="#EEF1F4" '
              f'TOOLTIP="{html_text(gruppe.titel)} oeffnen">'
              f'<FONT COLOR="#4B5563" POINT-SIZE="{SCHRIFT_ABSCHNITT}"><B>{html_text(gruppe.titel)}</B>'
              f'</FONT></TD></TR>']
    endpunkte = {}
    for nummer, kennung in enumerate(sorted(kennungen, key=lambda k: (k in klassen, k))):
        if kennung in funktionen:
            f = funktionen[kennung]
            text = f.kurz if f.klasse else f"{f.name}()"
            #In HTML-Beschriftungen gilt HTML, also anders maskieren
            hinweis = html_text(tooltip_text(f)).replace("\n", "&#10;")
        else:
            text = f"{klassen[kennung].name}(...)"
            hinweis = html_text(klassen[kennung].beschreibung or klassen[kennung].name)
        reihen.append(f'<TR><TD PORT="z{nummer}" ALIGN="LEFT" HREF="{gruppe.seite}" TARGET="_top" '
                      f'TOOLTIP="{hinweis}"><FONT COLOR="{FREMD_SCHRIFT}">{html_text(text)}</FONT></TD></TR>')
        endpunkte[kennung] = f'"{knoten_name}":z{nummer}'
    tabelle = (f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" COLOR="{FREMD_RAND}" '
               f'BGCOLOR="{FREMD_FUELLUNG}" STYLE="ROUNDED">{"".join(reihen)}</TABLE>')
    return f'    "{knoten_name}" [shape=plain label=<{tabelle}>];', endpunkte


def dot_gruppenseite(gruppe, gruppe_von, funktionen, klassen, aufrufe, verweise, richtung="LR"):
    #Links wer die Gruppe aufruft, Mitte die Gruppe, rechts was sie aufruft.
    #Fremde Gruppen als Listen, blass und klickbar.
    innen = gruppe.kennungen
    aufrufer, ziele = set(), set()
    for kanten in (aufrufe, verweise):
        for von, nach_menge in kanten.items():
            for nach in nach_menge:
                if von in innen and nach not in innen:
                    ziele.add(nach)
                elif nach in innen and von not in innen:
                    aufrufer.add(von)
    #Wer beides ist, steht links
    ziele -= aufrufer
    innen_klassen_ziele = {z for ziele_menge in aufrufe.values() for z in ziele_menge
                           if z in klassen and z in innen}
    innen_knoten = (innen & set(funktionen)) | innen_klassen_ziele

    zeilen = kopf("gruppe", richtung)
    zeilen.append(kopf_zeile(gruppe.titel, zurueck_links(gruppe)))

    endpunkte = {}
    spalten = {}
    for seite, menge in (("links", aufrufer), ("rechts", ziele)):
        nach_gruppe = defaultdict(list)
        for kennung in menge:
            nach_gruppe[gruppe_von[kennung].name].append(kennung)
        spalten[seite] = []
        for nummer, name in enumerate(sorted(nach_gruppe)):
            knoten = f"fremd_{seite}_{nummer}"
            zeile, neue = fremd_liste(knoten, gruppe_von[nach_gruppe[name][0]], nach_gruppe[name],
                                      funktionen, klassen)
            zeilen.append(zeile)
            endpunkte.update(neue)
            spalten[seite].append(knoten)

    zeilen += modul_zeilen(gruppe.modul, {k: f for k, f in funktionen.items() if k in innen},
                           {k: v for k, v in klassen.items()
                            if k in innen or any(m.kennung in innen for m in v.methoden.values())},
                           innen_klassen_ziele, 0)
    bekannt = innen_knoten | aufrufer | ziele
    zeilen += kanten_zeilen(aufrufe, verweise, bekannt, innen, endpunkte)

    #Feste Ordnung: Aufrufer in die erste Spalte, Ziele in die letzte, die
    #Gruppe dazwischen. Geht ueber Rahmen hinweg nur dank newrank=true im Kopf.
    zeilen.append("    { rank=min; anker; " + " ".join(f'"{n}";' for n in spalten["links"]) + " }")
    if spalten["rechts"]:
        zeilen.append("    { rank=max; " + " ".join(f'"{n}";' for n in spalten["rechts"]) + " }")
    #Methoden, die in der Gruppe niemand aufruft, wuerden sonst ebenfalls in
    #der ersten Spalte landen, und die Aufrufer-Listen wuerden unter die
    #Gruppe geschoben. Ein unsichtbarer Pfeil von einem Anker schiebt sie eine
    #Spalte weiter. Nur zu diesen, ein langer unsichtbarer Pfeil wuerde in
    #jeder Spalte Platz belegen und das Bild aufblaehen.
    von_innen_erreicht = {nach for kanten in (aufrufe, verweise) for von, nach_menge in kanten.items()
                          if von in innen for nach in nach_menge}
    zeilen.append('    anker [style=invis label="" width=0 height=0];')
    for kennung in sorted(innen_knoten - von_innen_erreicht):
        zeilen.append(f'    anker -> "{kennung}" [style=invis];')
    zeilen.append("}")
    return "\n".join(zeilen)


def gruppen_zaehlen(aufrufe, verweise, schluessel):
    #{(von, nach): [aufrufe, verweise]} zwischen verschiedenen Gruppen,
    #schluessel(kennung) bestimmt die Gruppe
    zaehler = defaultdict(lambda: [0, 0])
    for nummer, kanten in enumerate((aufrufe, verweise)):
        for von, nach_menge in kanten.items():
            for nach in nach_menge:
                a, b = schluessel(von), schluessel(nach)
                if a is not None and b is not None and a != b:
                    zaehler[(a, b)][nummer] += 1
    return zaehler


def zaehl_pfeil(von, nach, n_aufrufe, n_verweise, farbe=PFEIL_INNEN):
    gesamt = n_aufrufe + n_verweise
    stil = " style=dashed" if not n_aufrufe else ""
    return (f'    "{von}" -> "{nach}" [label="{gesamt}" fontsize=10 fontcolor="#6B7280" color="{farbe}" '
            f'penwidth={1 + min(gesamt, 30) / 6:.1f}{stil} tooltip="{n_aufrufe} Aufrufe, {n_verweise} Verweise"];')


def dot_abschnitte(modul, gruppen, gruppe_von, aufrufe, verweise, funktionen, richtung="LR"):
    #Seite eines grossen Moduls: ein Kasten je Abschnitt, klickbar, mit
    #Pfeilen und Anzahl der Aufrufe. Links und rechts die anderen Module.
    #Reihenfolge wie im Code: nach der ersten Zeile im Abschnitt
    gruppe_zeile = {k: f.zeile for k, f in funktionen.items()}
    eigene = sorted((g for g in gruppen.values() if g.modul == modul),
                    key=lambda g: min((gruppe_zeile.get(k, 10 ** 9) for k in g.kennungen), default=10 ** 9))

    def schluessel(kennung):
        g = gruppe_von.get(kennung)
        if g is None:
            return None
        return g.name if g.modul == modul else g.modul

    zaehler = gruppen_zaehlen(aufrufe, verweise, schluessel)
    fuellung, rand = STIL[stil_fuer(modul)]
    #Andere Module nur als zwei Listen ohne Pfeile: die vielen langen Pfeile
    #quer uebers Bild wuerden die Abschnitte verdecken, und welche Methode
    #genau wohin geht, steht auf den Abschnittsseiten.
    eigen = lambda name: name.startswith(modul + "#")
    rein, raus = defaultdict(int), defaultdict(int)
    for (von, nach), (n_a, n_v) in zaehler.items():
        if eigen(nach) and not eigen(von):
            rein[von] += n_a + n_v
        elif eigen(von) and not eigen(nach):
            raus[nach] += n_a + n_v

    def modul_raster(titel, anzahl, spalten=4):
        #Ein Raster aus klickbaren Modulnamen mit Anzahl, je Zeile 'spalten'
        #Eintraege. Schrift ausdruecklich klein, sonst erbt sie die 18 pt des Titels.
        eintraege = [f'<TD ALIGN="LEFT" HREF="{seite_von(fremd)}" TARGET="_top" '
                     f'TOOLTIP="{html_text(fremd)} oeffnen"><FONT COLOR="{FREMD_SCHRIFT}" POINT-SIZE="11">'
                     f'{html_text(kurzname(fremd))} ({anzahl[fremd]})</FONT></TD>'
                     for fremd in sorted(anzahl, key=lambda m: (-anzahl[m], m))]
        reihen = [f'<TR><TD COLSPAN="{spalten}" ALIGN="LEFT" BGCOLOR="#EEF1F4"><FONT COLOR="#4B5563" '
                  f'POINT-SIZE="{SCHRIFT_ABSCHNITT}"><B>{html_text(titel)}</B></FONT></TD></TR>']
        for start in range(0, len(eintraege), spalten):
            teil = eintraege[start:start + spalten]
            teil += ["<TD></TD>"] * (spalten - len(teil))
            reihen.append(f"<TR>{''.join(teil)}</TR>")
        return (f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="{FREMD_RAND}" '
                f'BGCOLOR="{FREMD_FUELLUNG}" STYLE="ROUNDED">{"".join(reihen)}</TABLE>')

    #Die Listen stehen im Kopf der Seite, untereinander unter dem Titel. Als
    #Kaesten im Bild hat Graphviz sie ohne Pfeile nicht verlaesslich an den
    #Rand gestellt (rank=min/max, source/sink und Hilfspfeile probiert).
    reihen = [f'<TR><TD>{titel_html(f"{kurzname(modul)}: Abschnitte (Klick oeffnet einen Abschnitt)", [("Übersicht", "index.svg")])}</TD></TR>']
    if rein:
        reihen.append(f"<TR><TD>{modul_raster('wird aufgerufen von', rein)}</TD></TR>")
    if raus:
        reihen.append(f"<TR><TD>{modul_raster('ruft auf', raus)}</TD></TR>")
    zeilen = kopf("abschnitte", richtung)
    zeilen.append(f'    label=<<TABLE BORDER="0" CELLSPACING="8">{"".join(reihen)}</TABLE>>; labelloc=t;')
    for g in eigene:
        n = sum(1 for k in g.kennungen if k in gruppe_zeile)
        zeilen.append(f'    "{g.name}" [label="{dot_text(g.abschnitt)}\\n{anzahl_text(n, "Methode", "Methoden")}" fillcolor="{fuellung}" '
                      f'color="{rand}" penwidth=1.5 URL="{g.seite}" target="_top" '
                      f'tooltip="{dot_text(g.titel)}: Details oeffnen"];')
    for (von, nach), (n_a, n_v) in sorted(zaehler.items()):
        if eigen(von) and eigen(nach):
            zeilen.append(zaehl_pfeil(von, nach, n_a, n_v))
    zeilen.append("}")
    return "\n".join(zeilen)


def dot_uebersicht(module, funktionen, klassen, aufrufe, verweise, richtung="LR"):
    #Ein Kasten je Modul, klickbar. Pfeile: wie oft ein Modul ein anderes
    #aufruft oder auf es verweist, die Zahl steht dran.
    zaehler = defaultdict(lambda: [0, 0])
    for nummer, kanten in enumerate((aufrufe, verweise)):
        for von, nach_menge in kanten.items():
            for nach in nach_menge:
                if modul_von(von) != modul_von(nach):
                    zaehler[(modul_von(von), modul_von(nach))][nummer] += 1

    mit_inhalt = sorted({f.modul for f in funktionen.values()} | {k.modul for k in klassen.values()})
    zeilen = kopf("uebersicht", richtung)
    zeilen.append('    label="Fingerscan-Viewer: Module (Klick oeffnet die Details)"; labelloc=t; fontsize=24;')
    nach_ordner = defaultdict(list)
    for modul in mit_inhalt:
        nach_ordner[modul.rsplit(".", 1)[0] if "." in modul else ""].append(modul)
    for nummer, ordner in enumerate(sorted(nach_ordner)):
        if ordner:
            zeilen.append(f"    subgraph cluster_o{nummer} {{")
            zeilen.append(f'        label="{kurzname(ordner)}"; style="rounded"; color="#D8DEE6"; '
                          f'fontsize={SCHRIFT_KLASSE}; margin={CLUSTER_RAND};')
        for modul in nach_ordner[ordner]:
            fuellung, rand = STIL[stil_fuer(modul)]
            n_klassen = sum(1 for k in klassen.values() if k.modul == modul)
            n_methoden = sum(1 for f in funktionen.values() if f.modul == modul and f.klasse)
            n_funktionen = sum(1 for f in funktionen.values() if f.modul == modul and not f.klasse)
            teile = [anzahl_text(n, einzahl, mehrzahl) for n, einzahl, mehrzahl in (
                (n_klassen, "Klasse", "Klassen"), (n_methoden, "Methode", "Methoden"),
                (n_funktionen, "Funktion", "Funktionen")) if n]
            zeilen.append(f'        "{modul}" [label="{modul.split(".")[-1]}\\n{", ".join(teile)}" '
                          f'fillcolor="{fuellung}" color="{rand}" penwidth=1.5 URL="{seite_von(modul)}" '
                          f'target="_top" tooltip="{modul}: Details oeffnen"];')
        if ordner:
            zeilen.append("    }")
    for (von, nach), (n_aufrufe, n_verweise) in sorted(zaehler.items()):
        if von not in mit_inhalt or nach not in mit_inhalt:
            continue
        gesamt = n_aufrufe + n_verweise
        stil = ' style=dashed' if not n_aufrufe else ""
        zeilen.append(f'    "{von}" -> "{nach}" [label="{gesamt}" fontsize=10 fontcolor="#6B7280" '
                      f'penwidth={1 + min(gesamt, 30) / 6:.1f}{stil} '
                      f'tooltip="{n_aufrufe} Aufrufe, {n_verweise} Verweise"];')
    zeilen.append("}")
    return "\n".join(zeilen)


def bild_erzeugen(dot_quelltext, ziel, format):
    #format: "pdf" oder "svg". dot direkt, wenn es da ist. Im Terminal von VS Code (Flatpak) gibt es
    #dot nicht, dann ueber flatpak-spawn auf dem System. Ein- und Ausgabe
    #laufen ueber Pipes: das System sieht das /tmp der Sandbox nicht.
    if shutil.which("dot"):
        befehl = ["dot", f"-T{format}"]
    elif shutil.which("flatpak-spawn"):
        befehl = ["flatpak-spawn", "--host", "dot", f"-T{format}"]
    else:
        print("dot nicht gefunden. Graphviz installieren: sudo dnf install graphviz", file=sys.stderr)
        sys.exit(1)

    ergebnis = subprocess.run(befehl, input=dot_quelltext.encode("utf-8"), capture_output=True)
    #Nur schreiben, was wirklich ein PDF bzw. SVG ist. Sonst landet z.B. eine
    #Fehlermeldung in der Datei und der Betrachter meldet "beschaedigt".
    echt = (ergebnis.stdout.startswith(b"%PDF") if format == "pdf"
            else b"<svg" in ergebnis.stdout[:2000])
    if ergebnis.returncode != 0 or not echt:
        print(f"dot ist fehlgeschlagen, kein {format.upper()} geschrieben:\n"
              f"{ergebnis.stderr.decode('utf-8', 'replace') or ergebnis.stdout[:500].decode('utf-8', 'replace')}",
              file=sys.stderr)
        sys.exit(1)
    Path(ziel).write_bytes(ergebnis.stdout)
    print(f"{format.upper()} geschrieben: {ziel}", file=sys.stderr)


# ---------- Hauptfunktion ----------

def wert_nach(option):
    if option in sys.argv:
        stelle = sys.argv.index(option)
        if stelle + 1 < len(sys.argv):
            return sys.argv[stelle + 1]
    return None


def modul_finden(name, module):
    #Auch nur der letzte Teil reicht, z.B. "isolate_finger" statt "logik.isolate_finger"
    treffer = [m for m in module if m == name or m.split(".")[-1] == name]
    if len(treffer) != 1:
        print(f"Modul '{name}' nicht eindeutig gefunden, moeglich: {', '.join(sorted(module))}",
              file=sys.stderr)
        sys.exit(1)
    return treffer[0]


def ausgeben(graph):
    ziele = {format: wert_nach(f"--{format}") for format in ("pdf", "svg")}
    for format, ziel in ziele.items():
        if ziel:
            bild_erzeugen(graph, ziel, format)
    if not any(ziele.values()):
        print(graph)


def main():
    module, funktionen, klassen, aufrufe, verweise = alles_einlesen()
    richtung = "TB" if "--hoch" in sys.argv else "LR"

    if "--ohne-verweise" in sys.argv:
        verweise = {k: set() for k in verweise}

    ordner = wert_nach("--je-modul")
    modul = wert_nach("--modul")
    gruppen, gruppe_von, aufgeteilt = gruppen_bilden(funktionen, klassen)

    def modul_seiten(m):
        #[(dateiname, dot), ...] fuer ein Modul: eine Seite, oder bei grossen
        #Modulen die Abschnitts-Uebersicht und eine Seite je Abschnitt
        if m not in aufgeteilt:
            return [(seite_von(m), dot_gruppenseite(gruppen[m], gruppe_von, funktionen, klassen,
                                                    aufrufe, verweise, richtung))]
        seiten = [(seite_von(m), dot_abschnitte(m, gruppen, gruppe_von, aufrufe, verweise,
                                                funktionen, richtung))]
        for g in gruppen.values():
            if g.modul == m:
                seiten.append((g.seite, dot_gruppenseite(g, gruppe_von, funktionen, klassen,
                                                         aufrufe, verweise, richtung)))
        return seiten

    if ordner:
        ordner = Path(ordner)
        ordner.mkdir(parents=True, exist_ok=True)
        bild_erzeugen(dot_uebersicht(module, funktionen, klassen, aufrufe, verweise, richtung),
                      ordner / "index.svg", "svg")
        mit_inhalt = sorted({f.modul for f in funktionen.values()} | {k.modul for k in klassen.values()})
        for m in mit_inhalt:
            for datei, graph in modul_seiten(m):
                bild_erzeugen(graph, ordner / datei, "svg")
        print(f"\nIm Browser oeffnen: {ordner / 'index.svg'}", file=sys.stderr)
    elif modul:
        #Bei grossen Modulen nur die Abschnitts-Uebersicht, die Abschnitte
        #selbst gibt es mit --je-modul
        ausgeben(modul_seiten(modul_finden(modul, module))[0][1])
    else:
        #--dot von frueher wird einfach ignoriert, es gibt nur noch Graphviz
        ausgeben(dot_alles(funktionen, klassen, aufrufe, verweise, richtung))

    anzahl_methoden = sum(1 for f in funktionen.values() if f.klasse)
    print(f"\n{len(module)} Module, {len(klassen)} Klassen, {anzahl_methoden} Methoden, "
          f"{len(funktionen) - anzahl_methoden} Funktionen, "
          f"{sum(len(z) for z in aufrufe.values())} Aufrufe, "
          f"{sum(len(z) for z in verweise.values())} Verweise", file=sys.stderr)


if __name__ == "__main__":
    main()
