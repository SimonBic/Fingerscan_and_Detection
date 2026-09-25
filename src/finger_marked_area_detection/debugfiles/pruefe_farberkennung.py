
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import konstanten as k
from farberkennung import (
    finde_markierungs_punkte,
    hex_zu_rgb,
    kleinster_farbabstand,
    medianer_texelabstand,
    schwelle_aus_verteilung,
    texel_koordinaten,
)
from isolate_finger import load_teilmeshe_mit_textur

Image.MAX_IMAGE_PIXELS = None       # die Scanner liefern 8192x8192

# Die Overlays sind aus echten Patientenscans gerechnet. Sie gehoeren
# ausserhalb des Repositorys, damit sie nicht versehentlich mitcommittet
# oder auf GitHub gepusht werden.
REPO_WURZEL = Path(__file__).resolve().parents[3]
# .../Arbeit/UKR/Code/repo/Fingerscan_and_Detection -> .../Arbeit/UKR
AUSGABE_ORDNER = REPO_WURZEL.parents[2] / "Diagnose_Ausgaben"


def pruefe_ausgabe_ordner(ordner: Path) -> Path:
    # Harte Sperre: nichts, was aus Patientendaten entsteht, darf im
    # Repository landen - auch nicht, wenn jemand --ausgabe falsch setzt.
    ordner = ordner.resolve()
    if ordner == REPO_WURZEL or REPO_WURZEL in ordner.parents:
        raise SystemExit(
            f"Abbruch: {ordner} liegt im Repository. Overlays aus Patientenscans\n"
            f"gehoeren ausserhalb, zum Beispiel nach {AUSGABE_ORDNER}."
        )
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def stiftfarbe_schaetzen(bild: np.ndarray) -> np.ndarray:
    # Ersatz fuer den Pipetten-Klick, damit die Messung ohne GUI laeuft:
    # der Median der dunkelsten Texel. Trifft eine Stiftmarkierung gut,
    # waere fuer eine helle Markierung aber falsch - dort muss die echte
    # Pipette ran.
    hell = bild.reshape(-1, 3).mean(axis=1)
    grenze = np.percentile(hell, 0.2)
    return np.median(bild.reshape(-1, 3)[hell <= grenze], axis=0)


def overlay_schreiben(bild: np.ndarray, ziel_rgb: np.ndarray, toleranz: float, ziel: Path):
    # Maske ueber der verkleinerten Textur, damit Fehltreffer sichtbar
    # werden. Die Textur wird vorher verkleinert - sonst waeren es 67 Mio.
    # Texel mal drei Kanaele als float.
    klein = np.asarray(Image.fromarray(bild).resize((1200, 1200), Image.BILINEAR)).astype(np.float32)
    treffer = np.linalg.norm(klein - ziel_rgb, axis=2) < toleranz
    darstellung = (klein * 0.45).astype(np.uint8)
    darstellung[treffer] = (0, 255, 0)
    Image.fromarray(darstellung).save(ziel)


def pruefe(ordner: Path, ausgabe: Path):
    print(f"\n{'=' * 78}\n{ordner.name}\n{'=' * 78}")
    teile = load_teilmeshe_mit_textur(ordner)
    if not teile:
        print("  Keine texturierten Teile gefunden.")
        return

    mit_textur = [(m, t) for m, t in teile if t is not None]
    if not mit_textur:
        print("  Nur Vertex-Farben, kein Texturvergleich moeglich.")
        return

    bild = mit_textur[0][1].to_array()
    ziel_rgb = stiftfarbe_schaetzen(bild)
    hex_code = "#%02X%02X%02X" % tuple(ziel_rgb.astype(int))
    vertices = sum(m.n_points for m, _ in teile)
    print(f"  Vertices gesamt        {vertices}")
    print(f"  Textur                 {bild.shape[1]}x{bild.shape[0]}")
    print(f"  Stiftfarbe (Textur)    {hex_code}")

    mesh, tex = mit_textur[0]
    x, y = texel_koordinaten(np.asarray(mesh.active_texture_coordinates), bild.shape[1], bild.shape[0])
    abstand_texel = medianer_texelabstand(x, y)
    print(f"  Vertexabstand          {abstand_texel:.1f} Texel"
          f"  -> Raster {k.RASTER_GROESSE}x{k.RASTER_GROESSE}"
          f", gespreizt +-{abstand_texel * k.RASTER_SPREIZUNG:.0f}")

    alt = np.linalg.norm(bild[y, x].astype(np.float32) - ziel_rgb, axis=1)
    neu = kleinster_farbabstand(bild, x, y, ziel_rgb, abstand_texel * k.RASTER_SPREIZUNG)
    schwelle = schwelle_aus_verteilung(neu)
    print(f"  Automatische Schwelle  {schwelle:.1f}"
          f"{'  (Rueckfallwert)' if schwelle == k.FALLBACK_TOLERANZ else ''}")

    print(f"\n  Getroffene Vertices bei dieser Schwelle:")
    print(f"    ein Texel  (bisher)  {(alt < schwelle).sum():6d}")
    print(f"    Umgebung   (neu)     {(neu < schwelle).sum():6d}"
          f"   {(neu < schwelle).sum() / max((alt < schwelle).sum(), 1):.1f}x")

    punkte = finde_markierungs_punkte(teile, hex_code)
    anteil = len(punkte) / vertices * 100
    print(f"\n  finde_markierungs_punkte() liefert {len(punkte)} Punkte ({anteil:.2f} % der Vertices)")
    if len(punkte) < k.MIN_MARKIERUNGS_PUNKTE:
        print("    -> zu wenig, der Aufrufer meldet 'keine Markierung gefunden'")

    flaeche = (np.linalg.norm(bild[::8, ::8].astype(np.float32) - ziel_rgb, axis=2) < schwelle).mean() * 100
    print(f"  Anteil markierter Texturflaeche    {flaeche:.2f} %")

    ziel = ausgabe / f"overlay_{ordner.name[:30]}.png"
    overlay_schreiben(bild, ziel_rgb, schwelle, ziel)
    print(f"  Overlay: {ziel}")


if __name__ == "__main__":
    argumente = sys.argv[1:]
    ausgabe = AUSGABE_ORDNER
    if "--ausgabe" in argumente:
        i = argumente.index("--ausgabe")
        ausgabe = Path(argumente[i + 1])
        del argumente[i:i + 2]

    if not argumente:
        print(__doc__)
        sys.exit(1)

    ausgabe = pruefe_ausgabe_ordner(ausgabe)
    print(f"Overlays werden geschrieben nach: {ausgabe}")
    for pfad in argumente:
        pruefe(Path(pfad), ausgabe)
