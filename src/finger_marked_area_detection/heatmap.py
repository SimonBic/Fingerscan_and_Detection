from pathlib import Path

import numpy as np
import trimesh
import matplotlib.pyplot as plt


def erstelle_koordinatensystem(landmarken: dict) -> dict:
    # Haut des Fingers wird abgewickelt nach Zylinderkoordinaten
    #stab des Zylinders ist die Achse von mitt der beiden rillen zur Fingerspitze

    linke_rille = landmarken["linke_rille"]
    rechte_rille = landmarken["rechte_rille"]
    fingerspitze = landmarken["fingerspitze"]

    #Mitte der beiden Rillen
    basis_mitte = (linke_rille + rechte_rille) / 2
    #Vektor der Achse
    achse_richtung = fingerspitze - basis_mitte
    achse_richtung = achse_richtung / np.linalg.norm(achse_richtung)

    # Referenzrichtung (Winkel = 0) zeigt zur linken Rille
    referenz_radial = linke_rille - basis_mitte
    referenz_radial = referenz_radial - np.dot(referenz_radial, achse_richtung) * achse_richtung
    referenz_radial = referenz_radial / np.linalg.norm(referenz_radial)

    quer_richtung = np.cross(achse_richtung, referenz_radial)

    # Hoehen-Nullpunkt = Hoehe der linken Rille selbst
    h_offset = np.dot(linke_rille - basis_mitte, achse_richtung)

    return dict(
        basis_mitte=basis_mitte,
        achse_richtung=achse_richtung,
        referenz_radial=referenz_radial,
        quer_richtung=quer_richtung,
        h_offset=h_offset,
    )


def punkt_abwickeln(punkt: np.ndarray, ks: dict) -> tuple:
    """Wandelt einen einzelnen 3D-Punkt in (bogenlaenge, hoehe) um.
    Fuer die reine 2D-Darstellung (Plot)."""
    relativ = punkt - ks["basis_mitte"]
    hoehe_roh = np.dot(relativ, ks["achse_richtung"])
    hoehe = hoehe_roh - ks["h_offset"]

    radial = relativ - hoehe_roh * ks["achse_richtung"]
    radius = np.linalg.norm(radial)

    if radius < 1e-9:
        return 0.0, hoehe  # Punkt liegt exakt auf der Mittelachse

    winkel = np.arctan2(np.dot(radial, ks["quer_richtung"]), np.dot(radial, ks["referenz_radial"]))
    bogenlaenge = winkel * radius
    return bogenlaenge, hoehe


def punkt_zu_zylinderkoordinaten(punkt: np.ndarray, ks: dict) -> tuple:
    relativ = punkt - ks["basis_mitte"]
    hoehe_roh = np.dot(relativ, ks["achse_richtung"])
    hoehe = hoehe_roh - ks["h_offset"]

    radial = relativ - hoehe_roh * ks["achse_richtung"]
    radius = np.linalg.norm(radial)

    if radius < 1e-9:
        return 0.0, hoehe, 0.0

    winkel = np.arctan2(np.dot(radial, ks["quer_richtung"]), np.dot(radial, ks["referenz_radial"]))
    return winkel, hoehe, radius


def zylinderkoordinaten_zu_punkt(winkel: float, hoehe: float, radius: float, ks: dict) -> np.ndarray:
    """Exakte Umkehrfunktion zu punkt_zu_zylinderkoordinaten()."""
    hoehe_roh = hoehe + ks["h_offset"]
    achsen_punkt = ks["basis_mitte"] + hoehe_roh * ks["achse_richtung"]
    radial = radius * (np.cos(winkel) * ks["referenz_radial"] + np.sin(winkel) * ks["quer_richtung"])
    return achsen_punkt + radial


def flaeche_abwickeln(punkte_3d: np.ndarray, landmarken: dict) -> np.ndarray:
    """Wandelt mehrere 3D-Punkte auf einmal in 2D-Koordinaten um.
    Gibt ein (n,2)-Array zurueck: Spalte 0 = Bogenlaenge, Spalte 1 = Hoehe."""
    ks = erstelle_koordinatensystem(landmarken)
    return np.array([punkt_abwickeln(p, ks) for p in punkte_3d])


def lade_markierung_mit_landmarken(obj_pfad: Path):
    #Lädt die Markierungen, identifiziert dabei die Landmarken und speichert sie
    geladen = trimesh.load(str(obj_pfad), process=False, split_objects=True)

    if not isinstance(geladen, trimesh.Scene):
        raise ValueError(
            f"{obj_pfad} enthaelt keine Szene mit mehreren Teilen - "
            f"wurden die Landmarken beim Speichern mit exportiert?"
        )

    flaeche_punkte = None
    landmarken = {}

    for name, geom in geladen.geometry.items():
        if name.startswith("landmark_"):
            # Name hat die Form 'landmark_<name>_material_X' - den
            # eigentlichen Landmark-Namen dazwischen extrahieren
            landmark_name = name.replace("landmark_", "", 1).rsplit("_material_", 1)[0]
            landmarken[landmark_name] = geom.vertices.mean(axis=0)
        else:
            flaeche_punkte = geom.vertices

    return flaeche_punkte, landmarken


def heatmap_main(path: str):
    import matplotlib.pyplot as plt

    markierungen_ordner = Path(path)
    obj_dateien = sorted(markierungen_ordner.glob("*.obj"))

    if not obj_dateien:
        print("Keine .obj-Dateien gefunden.")
    else:
        fig, ax = plt.subplots(figsize=(8, 10))

        for obj_pfad in obj_dateien:
            flaeche_punkte, landmarken = lade_markierung_mit_landmarken(obj_pfad)

            if not all(k in landmarken for k in ("linke_rille", "rechte_rille", "fingerspitze")):
                print(f"Ueberspringe {obj_pfad.name}: nicht alle Landmarken gefunden.")
                continue

            koordinaten_2d = flaeche_abwickeln(flaeche_punkte, landmarken)

            ax.scatter(koordinaten_2d[:, 0], koordinaten_2d[:, 1], label=obj_pfad.stem, s=8, alpha=0.6)

        ax.set_xlabel("Bogenlaenge um den Finger (mm)")
        ax.set_ylabel("Hoehe entlang des Fingers (mm)")
        ax.set_title("Genesungsverlauf - abgewickelte Markierungen")
        ax.legend()
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)

        plt.savefig(markierungen_ordner / "heatmap_verlauf.png", dpi=150)
        print(f"Plot gespeichert unter: {markierungen_ordner / 'heatmap_verlauf.png'}")
        plt.show()