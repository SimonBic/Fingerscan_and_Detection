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
import konstanten as k

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


def aussen_normalen(flaeche: p_v.PolyData, hand_mesh: p_v.PolyData) -> np.ndarray:
    """Punktnormalen der Flaeche, garantiert nach AUSSEN zeigend.

    compute_normals(auto_orient_normals=True) reicht dafuer nicht: das
    Verfahren braucht eine geschlossene Oberflaeche, um 'aussen' ueberhaupt
    bestimmen zu koennen. Ein ausgeschnittenes Flaechenstueck ist offen,
    also zeigen die Normalen je nach Wicklung des Scans mal so und mal so -
    und die Flaeche verschwindet beim Abheben IM Finger.

    Deshalb wird die Richtung hier explizit geprueft: die Flaeche ist ein
    zusammenhaengendes Stueck mit einheitlicher Wicklung, es genuegt also
    ein Vorzeichen fuer alle Punkte. Entschieden wird es daran, ob die
    mittlere Normale vom Mesh-Schwerpunkt weg zeigt (gleiches Mittel wie
    in messungen.schliesse_offenes_ende)."""

    mit_normalen = flaeche.compute_normals(point_normals=True, auto_orient_normals=True)
    normalen = np.asarray(mit_normalen.point_normals, dtype=float)

    nach_aussen = np.asarray(flaeche.points) - np.asarray(hand_mesh.points).mean(axis=0)
    if np.sum(normalen * nach_aussen) < 0:
        normalen = -normalen

    return normalen


def hebe_flaeche_ab(flaeche: p_v.PolyData, hand_mesh: p_v.PolyData,
                    versatz: float = k.FLAECHEN_VERSATZ) -> p_v.PolyData:
    """Schiebt die Flaeche entlang ihrer Normalen nach aussen, damit sie im
    gespeicherten Scan sichtbar ueber der Hand liegt.

    Arbeitet auf einer echten Kopie: compute_normals() gibt ein Mesh
    zurueck, das sich das Punkte-Array mit der Eingabe TEILT. Ohne die
    Kopie wuerde die Flaeche der UI mitverschoben - bei jedem Speichern
    erneut, samt wachsendem Flaecheninhalt."""

    abgehoben = flaeche.copy(deep=True)
    abgehoben.points = np.asarray(flaeche.points) + aussen_normalen(flaeche, hand_mesh) * versatz
    return abgehoben


def platzierung_der_zahl(flaeche: p_v.PolyData, hand_mesh: p_v.PolyData) -> tuple:
    """Findet Position, Normale und 'oben'-Richtung fuer die Nummer einer
    Messung. Rueckgabe: (position, normale, hoch)."""

    # Der Schwerpunkt einer gekruemmten Flaeche liegt IM Finger drin, also
    # zurueck auf die Oberflaeche ziehen.
    schwerpunkt = np.asarray(flaeche.points).mean(axis=0)
    index = flaeche.find_closest_point(schwerpunkt)
    position = np.asarray(flaeche.points[index])

    normale = aussen_normalen(flaeche, hand_mesh)[index]

    # Isolierte Finger liegen entlang Z, das ist die natuerliche Leserichtung.
    hoch = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(hoch, normale / np.linalg.norm(normale))) > 0.95:
        hoch = np.array([1.0, 0.0, 0.0])

    return position, normale, hoch


def ziffer_hoehe(flaeche_mm2: float) -> float:
    # Die Zahl soll kleine Tattoos nicht zudecken und bei grossen nicht
    # verschwinden - daher an die Kantenlaenge der Flaeche gekoppelt.
    return float(np.clip(np.sqrt(max(flaeche_mm2, 0.0)) / 2.5, 1.5, 6.0))


def passende_ziffer_hoehe(hand_mesh: p_v.PolyData, position: np.ndarray,
                          normale: np.ndarray, wunsch_hoehe: float,
                          versatz: float = k.ZAHL_VERSATZ) -> float:
    """Verkleinert die Ziffer, wenn sie sonst in der Oberflaeche versinken
    wuerde.

    Die Ziffer ist eine STARRE flache Platte. In einer engen konkaven
    Stelle (Hautfalte) steigt die Oberflaeche rundherum an, und die Ecken
    der Platte verschwinden darin - mehr Versatz hilft dort nicht, weil
    die Platte dann nur weiter gegen die ansteigenden Waende drueckt.
    Was hilft, ist eine kleinere Ziffer.

    Geprueft wird direkt: steigt die Hand im Umkreis der Ziffer ueber
    deren Ebene? Gemessen entlang der (verlaesslich nach aussen zeigenden)
    Normalen, daher unabhaengig von der Wicklung des Scans."""

    n = np.asarray(normale, dtype=float)
    n = n / np.linalg.norm(n)

    relativ = np.asarray(hand_mesh.points) - np.asarray(position, dtype=float)
    anstieg = relativ @ n                                   # Hoehe ueber der Ebene
    in_ebene = np.linalg.norm(relativ - np.outer(anstieg, n), axis=1)
    abstand = np.linalg.norm(relativ, axis=1)

    hoehe = wunsch_hoehe
    for _ in range(6):
        # halbe Diagonale der Ziffer: Breite liegt bei rund 1.2 x Hoehe
        umkreis = hoehe * k.ZIFFER_UMKREIS_FAKTOR

        # Nur die UMLIEGENDE Oberflaeche zaehlt. Die Begrenzung auf den
        # raeumlichen Abstand ist wichtig: sonst schlagen auch Punkte an,
        # die senkrecht weit weg sind (die gegenueberliegende Seite des
        # Fingers), in der Projektion aber nah liegen.
        nachbarn = (in_ebene <= umkreis) & (abstand <= umkreis + versatz)

        if not np.any(nachbarn) or anstieg[nachbarn].max() < versatz - k.ZIFFER_LUFT:
            break

        hoehe *= 0.75

    # Unter die Mindesthoehe nicht schrumpfen - eine Ziffer, die keiner mehr
    # lesen kann, nuetzt nichts, auch wenn sie dann frei steht.
    return max(hoehe, k.ZIFFER_MIN_HOEHE)


def zahl_auf_oberflaeche(
    text: str,
    position: np.ndarray,
    normale: np.ndarray,
    hoch: np.ndarray,
    hoehe_mm: float,
    versatz: float = k.ZAHL_VERSATZ,
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

    ziffer = p_v.Text3D(text, depth=k.ZIFFER_TIEFE, height=hoehe_mm)
    return ziffer.transform(matrix, inplace=False)


def baue_zahl_fuer_messung(flaeche: p_v.PolyData, hand_mesh: p_v.PolyData,
                           nummer: int, flaeche_mm2: float) -> p_v.PolyData:
    """Bequemlichkeits-Wrapper: Platzierung bestimmen und Ziffer bauen."""
    position, normale, hoch = platzierung_der_zahl(flaeche, hand_mesh)

    hoehe = passende_ziffer_hoehe(
        hand_mesh, position, normale, ziffer_hoehe(flaeche_mm2))

    return zahl_auf_oberflaeche(str(nummer), position, normale, hoch, hoehe)


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

        rote_flaeche = _als_trimesh(hebe_flaeche_ab(flaeche, hand_mesh))
        rote_flaeche.remove_unreferenced_vertices()
        _flaches_material(rote_flaeche, k.MESSUNG_FARBE)
        geometrien[f"vermessung_{nummer}"] = rote_flaeche

        ziffer = _als_trimesh(
            baue_zahl_fuer_messung(flaeche, hand_mesh, nummer, messung["flaeche_mm2"]))
        _flaches_material(ziffer, k.ZAHL_FARBE)
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


def _anteil_flaeche(messung: dict) -> float:
    """Der Teil einer Messung, der zur Bezugsflaeche gehoert, also oberhalb der
    Zwischenfingerfalte liegt. Fehlt die Angabe, zaehlt die ganze Flaeche."""
    return messung.get("flaeche_anteil_mm2", messung["flaeche_mm2"])


def schreibe_ergebnis_liste(messungen: list, ziel_ordner: Path, ziel_name: str,
                            finger_flaeche_mm2: float | None = None):
    """Schreibt die Messergebnisse als Excel-Liste in 'ziel_ordner'.

    Aufgerufen wird das mit 'vermessene_scans' selbst, nicht mit dem
    Scan-Unterordner - die Listen aller Scans eines Patienten liegen also
    nebeneinander, eine Ebene ueber den Scans.

    Gibt den Pfad zurueck - oder None, wenn openpyxl fehlt. Dann ist der
    OBJ-Export trotzdem schon geschrieben und die App laeuft weiter.

    'finger_flaeche_mm2' ist die Oberflaeche des Fingers ab der
    Zwischenfingerfalte (siehe messungen.flaeche_ab_fingerzwischenfalte).
    Wird sie uebergeben, kommt je Messung der Anteil in Prozent dazu."""

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

    # Mit Bezugsflaeche kommt die Spalte "Anteil [%]" dazu
    mit_anteil = bool(finger_flaeche_mm2)
    spalten = ["Nr", "Flaeche [mm2]", "Umfang [mm]"] + (["Anteil [%]"] if mit_anteil else [])

    kopf_zeile = 4
    for spalte, titel in enumerate(spalten, start=1):
        zelle = blatt.cell(row=kopf_zeile, column=spalte, value=titel)
        zelle.font = Font(bold=True)

    for i, messung in enumerate(messungen, start=1):
        zeile = kopf_zeile + i
        blatt.cell(row=zeile, column=1, value=i)
        blatt.cell(row=zeile, column=2, value=round(messung["flaeche_mm2"], 1))
        blatt.cell(row=zeile, column=3, value=round(messung["umfang_mm"], 1))
        if mit_anteil:
            blatt.cell(row=zeile, column=4,
                       value=round(_anteil_flaeche(messung) / finger_flaeche_mm2 * 100, 1))

    flaeche_gesamt = sum(m["flaeche_mm2"] for m in messungen)
    summen_zeile = kopf_zeile + len(messungen) + 1
    blatt.cell(row=summen_zeile, column=1, value="Summe").font = Font(bold=True)
    blatt.cell(row=summen_zeile, column=2, value=round(flaeche_gesamt, 1)).font = Font(bold=True)
    blatt.cell(row=summen_zeile, column=3,
               value=round(sum(m["umfang_mm"] for m in messungen), 1)).font = Font(bold=True)
    if mit_anteil:
        anteil_gesamt = sum(_anteil_flaeche(m) for m in messungen)
        blatt.cell(row=summen_zeile, column=4,
                   value=round(anteil_gesamt / finger_flaeche_mm2 * 100, 1)).font = Font(bold=True)
        # Bezugsgroesse darunter, damit nachvollziehbar ist, worauf sich die Prozente beziehen
        bezug_zeile = summen_zeile + 2
        blatt.cell(row=bezug_zeile, column=1,
                   value="Fingerflaeche ab Zwischenfingerfalte [mm2]").font = Font(bold=True)
        blatt.cell(row=bezug_zeile, column=2, value=round(finger_flaeche_mm2, 1))

    for spalte, breite in zip("ABCD", (42 if mit_anteil else 16, 16, 16, 16)):
        blatt.column_dimensions[spalte].width = breite

    mappe.save(str(pfad))
    print(f"Ergebnisliste gespeichert unter: {pfad}")
    return pfad
