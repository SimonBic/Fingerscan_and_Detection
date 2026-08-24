# Fingerscan_and_Detection

Tool zur automatisierten Auswertung von 3D-Handscans im Rahmen eines Forschungsprojekts am Universitätsklinikum Regensburg (UKR). Bei Patienten mit Nervenverletzungen an der Hand wird über mehrere Untersuchungen hinweg gescannt, wie sich der Bereich mit Gefühlsverlust und das Fingerkuppen-Volumen mit der Zeit verändern.

Läuft komplett lokal.

## Funktionen:

### Finger isolieren

Aus dem kompletten Handscan wird der verletzte Finger automatisch herausgeschnitten. Man klickt zwei Punkte an (Fingernagel des verletzten Fingers und dann des Nachbarfingers), der Rest läuft automatisch: Hand ausrichten, geodätischen Pfad zwischen beiden Fingern berechnen (Dijkstra), den tiefsten Punkt davon als Zwischenfingerfalte nehmen, per PCA die Fingerachse bestimmen, und dann mit einem passend ausgerichteten Ellipsoid schneiden.

Zwei Modi stehen zur Wahl:

- **Automatisch** - nutzt gespeicherte Parameter, falls für den Patienten schon mal manuell justiert wurde, sonst Standardwerte
- **Selbst justieren** - drei Regler (Breite, Länge, Unterschreitung) mit Live-Vorschau des Schnitt-Ellipsoids

Einmal manuell festgelegte Parameter werden pro Patient gespeichert, damit alle Untersuchungen desselben Patienten konsistent geschnitten werden, ansonsten wären die späteren Vergleiche über die Zeit hinweg nicht sauber möglich.

Der isolierte Finger wird am Ende zusätzlich ausgerichtet: Fingerachse exakt auf der Z-Achse, Zwischenfingerfalte exakt auf der X-Achse bei Z=0. Sehr wichtig für spätere Funktionen wie das Volumenmessen oder den 3D Genesungsverlauf

### Bereich einzeichnen

Zwei Wege, eine markierte Fläche (z. B. den Bereich ohne Gefühl) auf dem Scan festzuhalten:

- **Manuell** – Freihand direkt auf dem 3D-Modell malen
- **Automatisch** – wird vorher mit einem farbigen Stift auf der Haut eingezeichnet (standardmäßig schwarz), das Programm erkennt die Farbe auf dem Scan, verbindet die gefundenen Punkte zu einer geschlossenen Linie (überbrückt dabei auch kleine Lücken, z. B. durch Lichtreflexe auf dem Stift) und berechnet die eingeschlossene Fläche

Die Erkennungsfarbe lässt sich frei einstellen, entweder per RGB-Regler, per Farb-Raster oder per Pipette direkt vom Scan.

### Vermessen

- **Strecke** - geodätischer Abstand zwischen zwei Punkten, entlang der Oberfläche gemessen, nicht Luftlinie
- **Fläche / Umfang** - der zuletzt eingezeichnete Bereich
- **Volumen**, in drei Varianten:
  - ganzer isolierter Finger
  - ab einer farbig markierten Fläche (z. B. ein Gummiring (kann auch aus einem Gummihandschuh gebastelt werden), der um den Finger gewickelt wird oder eine gemalte Markierung): dafür wird eine Ebene per PCA durch die Markierung gelegt, auch wenn der Ring nicht ganz gerade sitzt
  - ab der Zwischenfingerfalte, braucht gar keine zusätzliche Markierung, weil deren Höhe durch die Ausrichtung beim Isolieren ja schon feststeht

### Genesungsverlauf

Über mehrere Untersuchungen hinweg werden die Markierungen gesammelt, jede Untersuchung in ihrer eigenen Farbe (rot, orange, gelb, grün, blau), und:

- als 2D-Verlauf abgewickelt und als PNG gespeichert – Bogenlänge um den Finger gegen Höhe entlang des Fingers. Der Schnitt der Abwicklung liegt bewusst genau an der Zwischenfingerfalte, damit er möglichst selten mitten durch eine tatsächliche Markierung läuft
- direkt auf den aktuellsten 3D-Scan projiziert (jeder alte Markierungspunkt wandert auf den nächstgelegenen Punkt des aktuellen Scans), sodass man den Verlauf am Finger selbst sieht, ohne Umweg über die 2D-Abwicklung

Beides parallel, nicht nur eins – die 2D-Variante ist vor allem für eine mögliche spätere ML-Auswertung gedacht.

## Installation

Voraussetzung: Python 3.14, Linux (Fedora bzw. Red Hat, Ubuntu bzw. Debian schon selbst getestet).
(Ich arbeite an der Anbindung zu Windows und MacOS)
```bash
git clone https://github.com/SimonBic/Fingerscan_and_Detection
cd Fingerscan_and_Detection/src/installer
./install.sh
```

Das Skript legt eine eigene virtuelle Umgebung an, installiert alle Pakete in exakt den getesteten Versionen aus `requirements.txt` und richtet ein Desktop-Icon ein. Läuft auf Fedora und Ubuntu.

## Verwendung

```bash
.venv/bin/python src/finger_marked_area_detection/main.py
```

Oder einfach über das Desktop-Icon nach der Installation.

Scan-Ordner lassen sich per Drag-and-Drop reinziehen oder über den eingebauten Ordner-Browser links unten öffnen.

## Ordnerstruktur

Ausführlichere Doku dazu liegt in `docs/`. Kurzfassung: pro Patient ein Ordner mit `originale_scans/`, `isolierte_scans/`, `markierte_scans/`, `heatmap/` und `pat_parameter/`.

## Verwendete Pakete

- [PySide6](https://doc.qt.io/qtforpython/) für die Oberfläche
- [PyVista](https://docs.pyvista.org/) und [VTK](https://vtk.org/) zur 3D-Verarbeitung und -Darstellung
- [trimesh](https://trimesh.org/) zum Laden von OBJ/MTL
- [scipy](https://scipy.org/), [numpy](https://numpy.org/) für die Geometrie und Numerik
- [matplotlib](https://matplotlib.org/) für den 2D-Genesungsverlauf

Genaue Versionen in `requirements.txt`, bewusst fest gepinnt statt mit Mindestversionen, um Versionskonflikte zwischen verschiedenen Rechnern zu vermeiden.

## Stand

Aktiv in Entwicklung. Die automatische Flächenerkennung funktioniert schon gut, hakt aber bei manchen Scans noch (z. B. bei starken Lichtreflexen auf dem Markierungsstift). 
