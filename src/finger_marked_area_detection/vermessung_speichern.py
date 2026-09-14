"""Speichert eine Vermessungs-Sitzung (mehrere eingezeichnete Flaechen)
als eigenen Scan-Ordner unter 'vermessene_scans' ab:

  <patient>/vermessene_scans/<scan_name>_vermessen/
      <scan_name>_vermessen.obj   Hand mit Textur + rote Flaechen + Zahlen
      <scan_name>_vermessen.mtl   (schreibt trimesh mit)
      material_*.png              (schreibt trimesh mit)
      <scan_name>_vermessen.xlsx  Ergebnisliste

Der Aufbau folgt speichere_isolierten_finger() aus isolate_finger.py und
speichere_genesungsverlauf() aus heatmap3D.py: alle Geometrien landen in
EINER trimesh.Scene, ein einziges scene.export() schreibt OBJ + MTL +
Texturbilder in den Zielordner.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pyvista as p_v
import trimesh
from PIL import Image

# Farbe der vermessenen Flaechen im gespeicherten Scan
MESSUNG_FARBE = (220, 20, 20)      # rot
ZAHL_FARBE = (255, 255, 255)       # weiss

# Die Flaechen liegen exakt auf der Hand-Oberflaeche und wuerden mit ihr
# um die Sichtbarkeit streiten (Z-Fighting). Deshalb werden sie entlang
# ihrer Normalen leicht abgehoben - gleiches Mittel wie in heatmap3D.py.
FLAECHEN_VERSATZ = 0.3             # mm
ZAHL_VERSATZ = 0.6                 # mm, liegt nochmal ueber der Flaeche
ZIFFER_TIEFE = 0.4                 # mm Extrusion


def _flaches_material(tmesh: trimesh.Trimesh, farbe_rgb: tuple) -> None:
    # Repo-weites Rezept fuer "einfarbig ohne Vertex-Farben": ein winziges
    # einfarbiges Bild und alle UVs auf 0.5. Ueberlebt den OBJ/MTL-Umweg.
    tmesh.visual = trimesh.visual.texture.TextureVisuals(
        uv=np.full((len(tmesh.vertices), 2), 0.5),
        image=Image.new("RGB", (64, 64), farbe_rgb),
    )


def _als_trimesh(mesh: p_v.PolyData) -> trimesh.Trimesh:
    dreiecke = mesh.triangulate()
    faces = dreiecke.faces.reshape(-1, 4)[:, 1:]
    return trimesh.Trimesh(vertices=dreiecke.points, faces=faces, process=False)


def hebe_flaeche_ab(flaeche: p_v.PolyData, versatz: float = FLAECHEN_VERSATZ) -> p_v.PolyData:
    """Schiebt die Flaeche entlang ihrer Punktnormalen nach aussen, damit
    sie im gespeicherten Scan sichtbar ueber der Hand liegt."""
    abgehoben = flaeche.compute_normals(point_normals=True, auto_orient_normals=True)
    abgehoben.points = abgehoben.points + abgehoben.point_normals * versatz
    return abgehoben


def platzierung_der_zahl(flaeche: p_v.PolyData, hand_mesh: p_v.PolyData) -> tuple:
    """Findet Position, Normale und 'oben'-Richtung fuer die Nummer einer
    Messung. Rueckgabe: (position, normale, hoch)."""

    # Der Schwerpunkt einer gekruemmten Flaeche liegt IM Finger drin, also
    # zurueck auf die Oberflaeche ziehen.
    schwerpunkt = np.asarray(flaeche.points).mean(axis=0)
    index = flaeche.find_closest_point(schwerpunkt)
    position = np.asarray(flaeche.points[index])

    mit_normalen = flaeche.compute_normals(point_normals=True, auto_orient_normals=True)
    normale = np.asarray(mit_normalen.point_normals[index], dtype=float)

    # auto_orient_normals kann bei einem offenen Flaechenstueck nach innen
    # zeigen - gegen die Richtung "weg vom Mesh-Schwerpunkt" pruefen.
    nach_aussen = position - np.asarray(hand_mesh.points).mean(axis=0)
    if np.dot(normale, nach_aussen) < 0:
        normale = -normale

    # Isolierte Finger liegen entlang Z, das ist die natuerliche Leserichtung.
    hoch = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(hoch, normale / np.linalg.norm(normale))) > 0.95:
        hoch = np.array([1.0, 0.0, 0.0])

    return position, normale, hoch


def ziffer_hoehe(flaeche_mm2: float) -> float:
    # Die Zahl soll kleine Tattoos nicht zudecken und bei grossen nicht
    # verschwinden - daher an die Kantenlaenge der Flaeche gekoppelt.
    return float(np.clip(np.sqrt(max(flaeche_mm2, 0.0)) / 2.5, 1.5, 6.0))


def zahl_auf_oberflaeche(
    text: str,
    position: np.ndarray,
    normale: np.ndarray,
    hoch: np.ndarray,
    hoehe_mm: float,
    versatz: float = ZAHL_VERSATZ,
) -> p_v.PolyData:
    """Baut eine 3D-Ziffer, die aufrecht und plan auf der Oberflaeche steht.

    pv.Text3D liegt flach in der xy-Ebene. Mit einer Orthonormalbasis
    (x = rechts, y = hoch, z = normale) als 4x4-Matrix wird sie an die
    richtige Stelle gedreht und geschoben."""

    n = np.asarray(normale, dtype=float)
    n = n / np.linalg.norm(n)

    hoch = np.asarray(hoch, dtype=float)
    hoch = hoch - np.dot(hoch, n) * n        # in die Tangentialebene projizieren
    hoch = hoch / np.linalg.norm(hoch)

    rechts = np.cross(hoch, n)

    matrix = np.eye(4)
    matrix[:3, 0] = rechts
    matrix[:3, 1] = hoch
    matrix[:3, 2] = n
    matrix[:3, 3] = np.asarray(position, dtype=float) + n * versatz

    ziffer = p_v.Text3D(text, depth=ZIFFER_TIEFE, height=hoehe_mm)
    return ziffer.transform(matrix, inplace=False)


def baue_zahl_fuer_messung(flaeche: p_v.PolyData, hand_mesh: p_v.PolyData,
                           nummer: int, flaeche_mm2: float) -> p_v.PolyData:
    """Bequemlichkeits-Wrapper: Platzierung bestimmen und Ziffer bauen."""
    position, normale, hoch = platzierung_der_zahl(flaeche, hand_mesh)
    return zahl_auf_oberflaeche(
        str(nummer), position, normale, hoch, ziffer_hoehe(flaeche_mm2))


def vermessungs_ordner(scan_ordner: Path) -> tuple:
    """Zielordner und Basisname fuer die gespeicherte Vermessung.
    Ordnerstruktur wie ueberall im Repo: patient = scan_ordner.parent.parent"""
    scan_ordner = Path(scan_ordner)
    patienten_ordner = scan_ordner.parent.parent

    ziel_name = scan_ordner.name + "_vermessen"
    ziel_ordner = patienten_ordner / "vermessene_scans" / ziel_name

    return ziel_ordner, ziel_name


def speichere_vermessung(aktuelle_teile: list, hand_mesh: p_v.PolyData,
                         messungen: list, scan_ordner: Path) -> Path:
    """Schreibt den Scan samt vermessener Flaechen und Nummern als OBJ.

    'messungen' ist die Liste aus der UI, je Eintrag mindestens
    {"flaeche": PolyData, "flaeche_mm2": float}."""

    if not messungen:
        raise ValueError("Keine Messungen zum Speichern vorhanden.")

    ziel_ordner, ziel_name = vermessungs_ordner(scan_ordner)
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    save_path = ziel_ordner / f"{ziel_name}.obj"

    geometrien = {}

    # 1) Die vermessenen Flaechen in Rot, plus ihre Nummer
    for nummer, messung in enumerate(messungen, start=1):
        flaeche = messung["flaeche"]

        rote_flaeche = _als_trimesh(hebe_flaeche_ab(flaeche))
        rote_flaeche.remove_unreferenced_vertices()
        _flaches_material(rote_flaeche, MESSUNG_FARBE)
        geometrien[f"vermessung_{nummer}"] = rote_flaeche

        ziffer = _als_trimesh(
            baue_zahl_fuer_messung(flaeche, hand_mesh, nummer, messung["flaeche_mm2"]))
        _flaches_material(ziffer, ZAHL_FARBE)
        geometrien[f"vermessung_zahl_{nummer}"] = ziffer

    # 2) Die Hand selbst - mit ihrer echten Textur bzw. Vertex-Farben
    for i, (pv_mesh, tex) in enumerate(aktuelle_teile):
        dreiecks_mesh = pv_mesh.triangulate()
        faces = dreiecks_mesh.faces.reshape(-1, 4)[:, 1:]

        if tex is not None:
            tmesh = trimesh.Trimesh(
                vertices=dreiecks_mesh.points, faces=faces, process=False)
            tmesh.visual = trimesh.visual.texture.TextureVisuals(
                uv=np.asarray(dreiecks_mesh.active_texture_coordinates),
                image=Image.fromarray(tex.to_array()),
            )

        elif "RGB" in dreiecks_mesh.point_data:
            tmesh = trimesh.Trimesh(
                vertices=dreiecks_mesh.points, faces=faces,
                vertex_colors=np.asarray(dreiecks_mesh.point_data["RGB"]), process=False)

        else:
            print(f"Warnung: Scan-Teil {i} hat weder Textur noch Vertex-Farben, wird uebersprungen.")
            continue

        geometrien[f"scan_teil_{i}"] = tmesh

    trimesh.Scene(geometrien).export(str(save_path))

    print(f"Vermessung ({len(messungen)} Flaechen) gespeichert unter: {save_path}")
    return save_path


def schreibe_ergebnis_liste(messungen: list, ziel_ordner: Path, ziel_name: str):
    """Schreibt die Messergebnisse als Excel-Liste neben den Scan.

    Gibt den Pfad zurueck - oder None, wenn openpyxl fehlt. Dann ist der
    OBJ-Export trotzdem schon geschrieben und die App laeuft weiter."""

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        print("openpyxl ist nicht installiert - Excel-Liste wird uebersprungen.")
        return None

    pfad = Path(ziel_ordner) / f"{ziel_name}.xlsx"

    mappe = Workbook()
    blatt = mappe.active
    blatt.title = "Vermessung"

    blatt["A1"] = "Scan"
    blatt["B1"] = ziel_name
    blatt["A2"] = "Datum"
    blatt["B2"] = date.today().isoformat()

    kopf_zeile = 4
    for spalte, titel in enumerate(["Nr", "Flaeche [mm2]", "Umfang [mm]"], start=1):
        zelle = blatt.cell(row=kopf_zeile, column=spalte, value=titel)
        zelle.font = Font(bold=True)

    for i, messung in enumerate(messungen, start=1):
        zeile = kopf_zeile + i
        blatt.cell(row=zeile, column=1, value=i)
        blatt.cell(row=zeile, column=2, value=round(messung["flaeche_mm2"], 1))
        blatt.cell(row=zeile, column=3, value=round(messung["umfang_mm"], 1))

    summen_zeile = kopf_zeile + len(messungen) + 1
    blatt.cell(row=summen_zeile, column=1, value="Summe").font = Font(bold=True)
    blatt.cell(row=summen_zeile, column=2,
               value=round(sum(m["flaeche_mm2"] for m in messungen), 1)).font = Font(bold=True)
    blatt.cell(row=summen_zeile, column=3,
               value=round(sum(m["umfang_mm"] for m in messungen), 1)).font = Font(bold=True)

    for spalte, breite in zip("ABC", (16, 16, 16)):
        blatt.column_dimensions[spalte].width = breite

    mappe.save(str(pfad))
    print(f"Ergebnisliste gespeichert unter: {pfad}")
    return pfad
