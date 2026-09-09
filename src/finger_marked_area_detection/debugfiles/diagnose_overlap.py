#Diagnose Skript, prüft, ob sich Teile in einem Scan-Ordner überlappen
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from isolate_finger import load_teilmeshe_mit_textur


def pruefe_overlap(ordner: Path, toleranz_faktor: float = 0.25) -> None:
    teile = load_teilmeshe_mit_textur(ordner)
    print(f"{len(teile)} Teile geladen.\n")

    if len(teile) < 2:
        print("Nur ein Teil vorhanden - zwischen Teilen kann es keine Ueberlappung geben.")
        return

    # Typischen Punktabstand pro Teil bestimmen, als Referenz-Skala.
    kantenlaengen = []
    for pv_mesh, _ in teile:
        baum = cKDTree(pv_mesh.points)
        dists, _ = baum.query(pv_mesh.points, k=2)
        kantenlaengen.append(np.median(dists[:, 1]))
    typische_kantenlaenge = float(np.median(kantenlaengen))
    toleranz = typische_kantenlaenge * toleranz_faktor
    print(f"Typischer Punktabstand: {typische_kantenlaenge:.4f}")
    print(f"Verwendete Toleranz fuer 'nahe' Punkte: {toleranz:.4f}\n")

    for i in range(len(teile)):
        pts_i = teile[i][0].points
        n_i = len(pts_i)
        # Erwartete Groessenordnung, wenn zwei Teile sich nur an einer
        # gemeinsamen Randkurve beruehren (Randlaenge ~ sqrt(Flaeche/Anzahl Punkte)).
        erwartet_rand = np.sqrt(n_i)

        for j in range(len(teile)):
            if i == j:
                continue
            pts_j = teile[j][0].points

            baum_j = cKDTree(pts_j)
            dists, _ = baum_j.query(pts_i)
            nahe = dists < toleranz
            anzahl = int(nahe.sum())

            if anzahl == 0:
                continue

            anteil = anzahl / n_i * 100
            print(
                f"Teil {i} ({n_i} Punkte) <-> Teil {j}: "
                f"{anzahl} Punkte naeher als Toleranz an Teil {j} "
                f"({anteil:.1f} % von Teil {i}). "
                f"Erwartet fuer reine Randberuehrung: ~{erwartet_rand:.0f} Punkte."
            )

            if anzahl > erwartet_rand * 5:
                print(
                    "  -> Deutlich mehr als eine schmale Randkurve: "
                    "sieht nach echter FLAECHIGER Ueberlappung aus."
                )
            else:
                print(
                    "  -> Groessenordnung passt zu einer normalen, "
                    "schmalen gemeinsamen Randkurve zwischen Nachbarteilen."
                )
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Verwendung: python diagnose_overlap.py <scan_ordner>")
        sys.exit(1)
    pruefe_overlap(Path(sys.argv[1]))
