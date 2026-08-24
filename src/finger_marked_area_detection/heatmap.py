from pathlib import Path
import numpy as np
import trimesh
import pyvista as p_v
import matplotlib.pyplot as plt

from draw_area_on_scan_experimental import lese_markierungsfarbe


def punkt_abwickeln(punkt: np.ndarray) -> tuple:
    x, y, z = punkt
    winkel = np.arctan2(y, x) % (2 * np.pi)
    radius = np.hypot(x, y)
    bogenlaenge = winkel * radius
    hoehe = z
    return bogenlaenge, hoehe


def flaeche_abwickeln(punkte_3d: np.ndarray) -> np.ndarray:
    return np.array([punkt_abwickeln(p) for p in punkte_3d])


def lade_markierung(obj_pfad: Path) -> np.ndarray:
    geladen = trimesh.load(str(obj_pfad), process=False, split_objects=True)

    if isinstance(geladen, trimesh.Scene):
        alle_punkte = [
            geom.vertices for name, geom in geladen.geometry.items()
            if not name.startswith("landmark_")
        ]
        if not alle_punkte:
            raise ValueError(f"{obj_pfad} enthaelt keine Flaechen-Geometrie.")
        return np.vstack(alle_punkte)

    return geladen.vertices


def finde_markierte_scans(patienten_ordner: Path) -> list:
    markierte_scans_ordner = patienten_ordner / "markierte_scans"
    if not markierte_scans_ordner.is_dir():
        return []
    return sorted(markierte_scans_ordner.glob("*/*.obj"))


def heatmap_main(path: str):
    # Erzeugt den 2D-'Genesungsverlauf' - eine abgewickelte Ansicht
    # ALLER Untersuchungen desselben Patienten uebereinander, jede
    # Markierung in ihrer eigenen, aus der Datei zurueckgelesenen
    # Untersuchungs-Farbe. Wird zusaetzlich zur 3D-Ansicht erzeugt
    # (baue_3d_genesungsverlauf) - z.B. fuer spaetere ML-Auswertung.
    scan_ordner = Path(path)
    patienten_ordner = scan_ordner.parent.parent

    obj_dateien = finde_markierte_scans(patienten_ordner)
    if not obj_dateien:
        print("Keine markierten Scans fuer diesen Patienten gefunden.")
        return

    fig, ax = plt.subplots(figsize=(8, 10))

    for obj_pfad in obj_dateien:
        try:
            flaeche_punkte = lade_markierung(obj_pfad)
            farbe_rgb = lese_markierungsfarbe(obj_pfad)
        except ValueError as e:
            print(f"Ueberspringe {obj_pfad.name}: {e}")
            continue

        farbe_matplotlib = tuple(c / 255 for c in farbe_rgb)
        koordinaten_2d = flaeche_abwickeln(flaeche_punkte)
        ax.scatter(koordinaten_2d[:, 0], koordinaten_2d[:, 1],
                   color=farbe_matplotlib, label=obj_pfad.parent.name, s=8, alpha=0.7)

    ax.set_xlabel("Bogenlaenge um den Finger (mm)")
    ax.set_ylabel("Hoehe entlang des Fingers (mm)")
    ax.set_title("Genesungsverlauf - abgewickelte Markierungen")
    ax.legend()
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)

    heatmap_ordner = patienten_ordner / "heatmap"
    heatmap_ordner.mkdir(exist_ok=True)
    save_path = heatmap_ordner / "Genesungsverlauf.png"
    plt.savefig(save_path, dpi=150)
    print(f"Plot gespeichert unter: {save_path}")
    plt.show()


def baue_3d_genesungsverlauf(aktueller_scan_mesh: p_v.PolyData, path: str) -> list:
    # Findet fuer JEDEN Punkt JEDER frueheren Markierung den
    # naechstgelegenen Punkt auf dem AKTUELLEN Scan (direkt in 3D,
    # ohne Umweg ueber 2D-Koordinaten) - funktioniert, weil alle
    # isolierten Scans desselben Patienten in derselben kanonischen
    # Ausrichtung liegen (berechne_finale_ausrichtung), auch wenn der
    # Finger bei jeder Untersuchung etwas anders gehalten wurde.

    # Gibt eine Liste von (3D-Punkte-Array, RGB-Farbe) zurueck, eine
    # pro gefundener Untersuchungs-Markierung - zum direkten Anzeigen
    # im Plotter (z.B. per plotter.add_points(punkte, color=farbe))
    scan_ordner = Path(path)
    patienten_ordner = scan_ordner.parent.parent

    ergebnisse = []
    for obj_pfad in finde_markierte_scans(patienten_ordner):
        try:
            punkte = lade_markierung(obj_pfad)
            farbe_rgb = lese_markierungsfarbe(obj_pfad)
        except ValueError as e:
            print(f"Ueberspringe {obj_pfad.name}: {e}")
            continue

        naechste_indices = [aktueller_scan_mesh.find_closest_point(p) for p in punkte]
        naechste_punkte = aktueller_scan_mesh.points[naechste_indices]

        ergebnisse.append((naechste_punkte, farbe_rgb))

    return ergebnisse