Willkommen beim **Fingerscan-Viewer**. Hier finden Sie kurze Anleitungen zu allen Funktionen.

[Anleitung drucken](drucken:anleitung)

---

## 1. Einrichten

### Root-Ordner festlegen

Bitte legen Sie einen Root-Ordner fest, in welchem die Scans gespeichert werden sollen. Einfach ein leerer Ordner auf einer Festplatte, welche noch genügend Speicherplatz frei hat, am besten 10 GB oder mehr. Den Rest übernimmt die Software von selbst. Der Pfad zum Root-Ordner wird für spätere Verwendung gespeichert. Der Ordner kann auch auf einer externen Festplatte liegen und mit anderen PCs verwendet werden.

---

## 2. Patienten und Scans verwalten

In der Spalte ganz rechts werden alle Patienten sowie deren Scans verwaltet.

### Neuen Patienten anlegen

Auf das große, quadratische Plus klicken, Name / Kennnummer eintragen, fertig.

### Neuen Scan hinzufügen

Auf einen beliebigen Patienten klicken, dann auf das rechteckige Plus. Anschließend genau eine .obj-Datei, genau eine .mtl-Datei sowie die dazugehörigen Bilddateien gleichzeitig auswählen und öffnen. Dann dem Menü folgen.

### Angaben einer Untersuchung nachtragen

Bei fehlerhaften Angaben zu einer Untersuchung auf diese mit rechter Maustaste klicken und dem Menü folgen.

---

## 3. Scan laden und betrachten

Auf einen beliebigen Patienten klicken, dann auf die gesuchte Untersuchung, dann auf das jeweilige Piktogramm, fertig.

Bedeutung der Piktogramme (erscheinen erst, wenn der jeweilige Scan vorhanden ist):

- Hand -> originaler Scan

- Finger -> isolierter Finger

- Stift -> eingezeichnete Fläche in der Farbe der gewählten Untersuchung

- Lineal -> jeweiliger Scan mit bemessenen Flächen

- 3D- oder 2D-Heatmap -> erscheint neben dem Patienten, zeigt den Genesungsverlauf in gewählter Dimension

Ich empfehle das Arbeiten mit einer Maus. Mit einem Trackpad ist die Verwendung freilich auch möglich, aber mit einer Maus wird ein besseres Erlebnis geboten. Im Viewer in der Mitte des Bildschirm kann durch Halten der linken Maustaste der Scan beliebig gedreht werden. Mit dem Mausrad kann gezoomt werden. Durch Halten der mittleren Maustaste (das Mausrad) kann der Scan hin und her geschoben werden. Durch gleichzeitiges Halten der Steuerungstaste (STRG) und der linken Maustaste kann der Scan gedreht werden, mit der Blickrichtung als Achse.

---

## 4. Finger isolieren

Auf Finger isolieren klicken, dann entweder automatische Einstellungen verwenden oder selbst justieren. Dann die Fingerspitze des verletzten, zu isolierenden Fingers rechtsklicken, dann die benachbarte Fingerspitze. Welche Fingerspitze als zweiter Klick?

(Für nicht medizinische Personen: digitus 1 = Daumen, digitus 2 = Zeigefinger usw.)

- digitus 1 ist verletzt -> digitus 2 als zweiten Klick

- digitus 2 ist verletzt -> digitus 3 als zweiten Klick

- digitus 3 ist verletzt -> digitus 4 als zweiten Klick

- digitus 4 ist verletzt -> digitus 5 als zweiten Klick

- digitus 5 ist verletzt -> digitus 4 als zweiten Klick

Auf "Fertig markiert" klicken, falls selbst justieren geklickt wurde, mit den Reglern das beste Ergebnis wählen. Die dazugehörigen Parameter werden gespeichert und bei dem nächsten Isolieren desselben Patienten als Werte für automatisches Isolieren verwendet. Dann kurz warten, je nach Prozessorleistung dauert das Isolieren einen Moment (~10 s). Der isolierte Finger kann jetzt mit Klick auf das Finger-Piktogramm geladen werden.

---

## 5. Bereiche einzeichnen, wie z. B. ein Taubheitsareal

Auf "Bereich einzeichnen" klicken, dann mit Rechtsklick Punkte setzen und den Bereich einzeichnen. Die Fläche schließt sich automatisch, wenn der Startpunkt ein zweites Mal angeklickt wird (bzw. < 1 mm in der Nähe). Dann auf "Fertig manuell gemalt" klicken und die passende Farbe wählen. Das eingezeichnete Areal ist jetzt unter dem Stift-Piktogramm verfügbar und kann für die 2D- oder auch die 3D-Heatmap als Genesungsverlaufsanzeige verwendet werden. Es ist ebenfalls möglich, einen Bereich automatisch einzeichnen zu lassen, indem man die Randfarbe auswählt, welche auf dem Scan vorhanden ist, z. B. ein schwarzer Kreis auf der Hand. Diese kann man mit einem Klick auf die Pipette wählen, der darauf folgende Klick wählt dann exakt die Farbe des darunterliegenden Pixels aus. Sie ist dann im Vorschaufenster links zu erkennen. Dann auf "Automatisch einzeichnen" klicken und die jeweilige Farbe auswählen. Diese automatische Funktion ist aber noch nicht vollendet, sie sollte aber in späteren Updates korrekt funktionieren.

---

## 6. Vermessen

Unter "Bereich / Strecke vermessen" können Strecken, Umfänge, Flächeninhalte sowie Volumina berechnet bzw. gemessen werden.

- "Eingezeichnete Bereiche / Umfänge vermessen": Wie beim Einzeichnen von Bereichen mit Rechtsklick die gewünschten Bereiche umranden, beliebig viele. Dann auf "Messungen speichern" klicken und die Bereiche werden nach Umfang und Flächeninhalt gemessen und in einer .xlsx-Datei exportiert, welche im Fingerscan-Viewer sowie mit einem Tabellenprogramm Ihrer Wahl (z. B. Excel, LibreOffice Calc) betrachtet werden kann. Zusätzlich wird berechnet, welchen Anteil die markierten Flächen einzeln sowie gesamt an der Gesamtfläche des Fingers ab Höhe der Zwischenfingerfalte haben. Diese Daten werden ab jetzt zusätzlich in der .xlsx-Datei gespeichert. 

- "Eingezeichnete Strecke vermessen": Hier kann der geodätische Pfad auf dem Scan (= tatsächliche Strecke auf dem Scan, nicht einfach die Luftlinie) vermessen werden. Einfach 2 Punkte rechtsklicken und der Wert kann oben abgelesen werden.

- "Volumen vermessen": Hier sind verschiedene Optionen verfügbar, um ein Volumen eines isolierten Fingers zu messen. "Gesamtes Volumen berechnen" ist selbsterklärend. "Volumen ab markierter Fläche berechnen": Hier kann beispielsweise mit der Pipette ein pinker Punkt auf dem Finger markiert werden, ab dem alles darüber zum Volumen dazuzählt. "Volumen ab Gummiring berechnen": Hier kann man wieder mit der Pipette beispielsweise die Farbe eines um den Finger gewickelten Gummirings auswählen. Dann wird dadurch eine Ebene gespannt, worüber das Volumen des Fingers bestimmt wird. "Volumen ab Höhe der Zwischenfingerfalte" berechnet das Volumen ab Höhe der Zwischenfingerfalte.

---

## 7. 2D-Heatmap

Erstellt mit einem Klick eine 2D-Heatmap, welche die eingezeichneten Flächen als Referenz verwendet, um den Genesungsverlauf zu beschreiben. Ergebnis ist eine .png-Datei.

---

## 8. 3D-Genesungsverlauf

Erstellt eine 3D-Heatmap auf den aktuell geöffneten Finger. Bitte dabei bei allen Fingern mit Rechtsklick die Mitte des Fingernagels anklicken, um die Flächen auszurichten.

---

## 9. Empfohlene Leistung

Diese Software lädt, verarbeitet und berechnet Handscans. Erfahrungsgemäß haben diese, je nach Kamera mit welcher der Scan erstellt wurde, bis zu 100.000 Vertices und noch mehr Faces. Trotz vieler Optimierungsmaßnahmen wird dafür eine gewisse Leistung benötigt um eine ansprechende User-Experience zu bieten. Ich empfehle folgende Mindest- und Empfehlungsvorrausetzungen:

| | Minimum | Empfohlen |
|---|---|---|
| Arbeitsspeicher | 8 GB | **16 GB** |
| Grafik | 1 GB Grafikspeicher | dedizierte Karte mit 4 GB |
| Prozessor | 2 Kerne, 2,5 GHz | 4 Kerne, > 3,5 GHz |
| Festplatte | 10 GB frei | SSD mit 50 GB frei |
| Bildschirm | 1600 × 900 | 1920 × 1080 |
| Betriebssystem | Windows 10, macOS 12| Linux |


**Arbeitsspeicher.** Ein einzelner Scan belegt beim Laden rund 1,2 GB. Die Scanner liefern eine PNG-Datei mit 8192 × 8192 Pixeln. Dazu kommt das Programm selbst mit der 3D-Anzeige. 


**Grafik.** Eine eigene Grafikkarte ist nicht nötig, die in den Prozessor eingebaute Grafik reicht. Sie muss aber Texturen mit 8192 Pixeln Kantenlänge verarbeiten können, das können alle Grafikchips ab etwa 2012. Bei älteren Geräten bleibt die Hand grau oder das Programm startet die 3D-Ansicht gar nicht.

**Prozessor.** Die Berechnungen laufen überwiegend auf einem einzigen Kern. Viele Kerne bringen deshalb wenig, eine hohe Taktrate dagegen viel. Das Laden eines Scans dauert auf einem aktuellen Gerät rund 2 Sekunden.

**Festplatte.** Ein Scan belegt etwa 50 MB, davon 35 MB die Textur. Ein Patient mit sechs Untersuchungen kommt also auf rund 300 MB. Eine SSD ist angenehmer als eine HDD, da aus einer SSD Daten deutlich schneller geladen werden kann.

Diese Daten beruhen auf meiner persönlichen Einschätzung, da ich nicht verschiedene Geräte zum Testen zur Verfügung habe.

---

## 10. Bugreport, Empfehlungen, Wünsche, Verbesserungen

Ich bin jederzeit offen und dankbar für Verbesserungen, Bugreports, Wünsche usw. Diese können per Email oder per einem sog. Pullrequest auf dem [GitHub Repository](https://github.com/SimonBic/Fingerscan_and_Detection/pulls) geäußert werden.
