#Zeichnet, wer wen benutzt. Liest die Importe im Paket ueber den AST und gibt
#einen Graphen aus, den man in die Doku kleben kann.

#Erzeugt statt von Hand getippt, weil die Struktur sich staendig aendert und
#ein handgemalter Graph nach dem ersten Umbau falsch ist, ohne dass es
#jemandem auffaellt.

#Aufruf:
#    python debugfiles/zeichne_struktur.py                   Mermaid, fuer GitHub und die README
#    python debugfiles/zeichne_struktur.py --dot             Graphviz, fuer ein PDF in docs/
#    python debugfiles/zeichne_struktur.py --mit-naben       auch die Pfeile auf konstanten
#    python debugfiles/zeichne_struktur.py --dot --hoch      von oben nach unten statt quer

import ast
import sys
from collections import defaultdict
from pathlib import Path

PAKET = Path(__file__).resolve().parent.parent

#prototyp ist alter Code, der nur noch herumliegt, debugfiles sind Werkzeuge.
#Beide wuerden das Bild vollstellen, ohne etwas ueber die App zu sagen.
UEBERSPRINGEN = ("prototyp", "debugfiles", "__pycache__")

#Module, die fast jede Datei liest. Ihre Pfeile bleiben standardmaessig weg:
#18 von 27 Modulen zeigen auf konstanten, das ergibt ein Knaeuel und sagt
#nichts, was man nicht ohnehin annimmt. Mit --mit-naben kommen sie dazu.
NABEN = ("konstanten",)

#Farben aus theme.py, damit der Graph zur Software passt. Blau fuer die
#Logik, Grau fuer die Oberflaeche: zwei Blautoene waren im Ausdruck nicht
#auseinanderzuhalten.
STIL = {
    "wurzel": ("#FFFFFF", "#1F2937"),
    "logik":  ("#D6E4F0", "#4A90D9"),
    "ui":     ("#EDEFF2", "#9AA3AE"),
}


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


def importe(datei, bekannt):
    #Nur Importe aus dem eigenen Paket. Fremdpakete wie numpy oder PySide6
    #stehen in requirements.txt, die gehoeren nicht in dieses Bild.
    gefunden = set()
    baum = ast.parse(datei.read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        namen = []
        if isinstance(knoten, ast.ImportFrom) and knoten.module and knoten.level == 0:
            namen.append(knoten.module)
        elif isinstance(knoten, ast.Import):
            namen.extend(a.name for a in knoten.names)
        for name in namen:
            #Ein Modul kann als "paket.modul" oder nur als "modul" angesprochen
            #werden, beides gilt
            if name in bekannt:
                gefunden.add(name)
    return gefunden


def graph_einlesen(mit_naben=False):
    module = paket_module()
    kanten = defaultdict(set)
    verschwiegen = defaultdict(int)
    for name, datei in module.items():
        for ziel in importe(datei, module):
            if ziel == name:
                continue
            if ziel in NABEN and not mit_naben:
                verschwiegen[ziel] += 1
                continue
            kanten[name].add(ziel)
    return module, kanten, verschwiegen


# ---------- Gruppieren ----------

def gruppe(name):
    #Der Ordner, in dem das Modul liegt. Die Wurzel bekommt keinen Untergraphen,
    #ihre Dateien sollen frei stehen.
    teile = name.split(".")
    return "" if len(teile) == 1 else ".".join(teile[:-1])


def stil_fuer(name):
    if name.startswith("logik."):
        return "logik"
    if name.startswith("ui_unterklassen."):
        return "ui"
    return "wurzel"


def kennung(name):
    return name.replace(".", "_")


# ---------- Ausgeben ----------

def beschriftung(name, verschwiegen):
    kurz = name.split(".")[-1]
    #Eine Nabe steht ohne Pfeile da, das saehe nach ungenutzt aus. Deshalb
    #die Zahl direkt ins Kaestchen.
    if name in verschwiegen:
        return f"{kurz}<br/>von {verschwiegen[name]} Modulen gelesen"
    return kurz


def mermaid(module, kanten, verschwiegen):
    zeilen = ["flowchart LR"]
    for art, (fuellung, rand) in STIL.items():
        zeilen.append(f"    classDef stil_{art} fill:{fuellung},stroke:{rand},stroke-width:2px")

    nach_gruppe = defaultdict(list)
    for name in sorted(module):
        nach_gruppe[gruppe(name)].append(name)

    for g in sorted(nach_gruppe):
        namen = nach_gruppe[g]
        if g:
            zeilen.append(f'    subgraph {kennung(g)}["{g.replace("ui_unterklassen.", "ui/")}"]')
            einzug = "        "
        else:
            einzug = "    "
        for name in namen:
            zeilen.append(f'{einzug}{kennung(name)}["{beschriftung(name, verschwiegen)}"]')
        if g:
            zeilen.append("    end")

    for von in sorted(kanten):
        for nach in sorted(kanten[von]):
            zeilen.append(f"    {kennung(von)} --> {kennung(nach)}")

    for name in sorted(module):
        zeilen.append(f"    class {kennung(name)} stil_{stil_fuer(name)}")
    return "\n".join(zeilen)


def dot(module, kanten, verschwiegen, richtung="LR"):
    zeilen = [
        "digraph struktur {",
        f"    rankdir={richtung};",
        #Buendelt die vielen Pfeile aus userinterface, sonst ist das Bild
        #ein Faecher quer ueber die ganze Breite
        "    concentrate=true;",
        "    nodesep=0.3; ranksep=0.7;",
        '    graph [fontname="Helvetica" fontsize=11];',
        '    node [shape=box style="filled,rounded" fontname="Helvetica" fontsize=10];',
        '    edge [color="#6B7280" arrowsize=0.7];',
    ]
    nach_gruppe = defaultdict(list)
    for name in sorted(module):
        nach_gruppe[gruppe(name)].append(name)

    for nummer, g in enumerate(sorted(nach_gruppe)):
        if g:
            zeilen.append(f'    subgraph cluster_{nummer} {{')
            zeilen.append(f'        label="{g.replace("ui_unterklassen.", "ui/")}"; color="#D8DEE6";')
        for name in nach_gruppe[g]:
            fuellung, rand = STIL[stil_fuer(name)]
            beschriftet = beschriftung(name, verschwiegen).replace("<br/>", "\\n")
            zeilen.append(f'        "{name}" [label="{beschriftet}" fillcolor="{fuellung}" color="{rand}"];')
        if g:
            zeilen.append("    }")

    for von in sorted(kanten):
        for nach in sorted(kanten[von]):
            zeilen.append(f'    "{von}" -> "{nach}";')
    zeilen.append("}")
    return "\n".join(zeilen)


# ---------- Hauptfunktion ----------

def richtung_aus_argumenten():
    #--hoch fuer A4 hochkant, sonst quer
    return "TB" if "--hoch" in sys.argv else "LR"


def main():
    mit_naben = "--mit-naben" in sys.argv
    module, kanten, verschwiegen = graph_einlesen(mit_naben)
    if "--dot" in sys.argv:
        print(dot(module, kanten, verschwiegen, richtung_aus_argumenten()))
    else:
        print("```mermaid")
        print(mermaid(module, kanten, verschwiegen))
        print("```")
        for nabe, anzahl in sorted(verschwiegen.items()):
            print(f"\n`{nabe}` wird von {anzahl} der {len(module)} Module gelesen. "
                  "Die Pfeile dorthin sind weggelassen, damit der Graph lesbar bleibt.")

    gezeichnet = sum(len(z) for z in kanten.values())
    weg = sum(verschwiegen.values())
    print(f"\n{len(module)} Module, {gezeichnet} gezeichnete Abhaengigkeiten"
          + (f", {weg} auf Naben weggelassen" if weg else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
