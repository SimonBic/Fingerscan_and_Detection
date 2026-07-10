# Finger_scan_and_detection
Im Rahmen eines Forschungsprojekts an der Uniklink Regensburg werden 3D-Handscans mit handgezeichneten Markierungen ausgewertet. Dieses Tool automatisiert:
 
- das Laden von Scan-Dateien (OBJ + MTL + Textur(en))
- interaktives Zuschneiden des Meshes
- interaktives Freihand-Zeichnen/Nachzeichnen von Markierungen (später Automatisch)
- Größenbestimmung (Umfang, Durchmesser, Fläche) in mm (später)
 

## Inhaltsverzeichnis:
 
- [Verwendung](#verwendung)
- [Packages](#packages)
- [Notizen](#notizen)

## Verwendung:

```bash
python draw_area_on_scan_experimental.py
Pfad: <path>
```

## Packages:
- [Pyvista](https://docs.pyvista.org/user-guide/)
- [trimesh](https://trimesh.org/)
- see requirements.txt

## Notizen:

Die Funktionen main, loadscan, draw_area_on_scan und cut_finger wurden mit Fokus auf trimesh entwickelt. 
Jedoch habe ich mich dazu entschieden, auf pyvista zu wechseln.
Grund für den Wechsel sind Berechnungsprobleme bei den Schnittpunkte der Vektoren von der Kamera zum angeklickten Face, siehe dazu beispielsweise pixel_to_ray.
Diese Berechnung wird von pyvista automatisch berechnet und zusätzlich ist (nach meinem Wissen) dieses package der Standart in medizinischer Software. 
Alles noch pre-Alpha.

