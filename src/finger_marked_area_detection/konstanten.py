from pathlib import Path


# ---------- Pfade ----------

ICON_ORDNER = Path(__file__).parent / "icons"
LOGO_PFAD = ICON_ORDNER / "logo.png"

# Tutorials fuer die How-To-Seite: Markdown, Bilder liegen im selben Ordner
HOWTO_ORDNER = Path(__file__).parent / "howto"
HOWTO_DATEI = HOWTO_ORDNER / "anleitung.md"


# ---------- Gespeicherte Einstellungen (QSettings) ----------

EINSTELLUNGEN_FIRMA = "UKR"
EINSTELLUNGEN_APP = "Fingerscan-Viewer"
ROOT_ORDNER_SCHLUESSEL = "root_ordner"


# ---------- Title Screen ----------

GOLDENER_SCHNITT = 0.382    # Logo-Mitte sitzt bei 38,2 % der Hoehe
TITEL_LOGO_GROESSE = 180
TITEL_KNOPF_BREITE = 360    # breit und flach
TITEL_KNOPF_HOEHE = 44

# Hintergrund-Netz: feste Verbindungen, die ganz langsam wabern
# Kosten steigen mit der Zahl der Kanten (~ Punkte x Nachbarn). Python schafft
# bei 1000 Punkten / 10 Nachbarn nur ~20 Bilder pro Sekunde - dann ruckelt es
# und die Knoepfe reagieren traege.
NETZ_PUNKTE = 500
NETZ_NACHBARN = 4           # jeder Punkt wird mit so vielen naechsten Nachbarn verbunden
NETZ_AMPLITUDE_PX = 20      # wie weit ein Punkt maximal aus seiner Ruhelage wandert
NETZ_PERIODE_MIN_S = 25     # eine Hin-und-her-Bewegung dauert 25-45 s
NETZ_PERIODE_MAX_S = 45
NETZ_FPS = 20               # reicht: bei ~3 px/s sind das 0,15 px pro Bild, mehr sieht man nicht
NETZ_FARBE = "#4A90D9"
NETZ_HINTERGRUND = "#F5F7FA"


# ---------- Knoepfe ----------

KNOPF_BREITE = 192
KNOPF_HOEHE = 108
ZAHNRAD_BREITE = 36     # Einstellungsknopf rechts neben dem Hinweistext


# ---------- Nav-Spalte ----------

NAV_KNOPF_BREITE = 80   # Patient-Avatar und Untersuchungs-Knopf
PIKTO_ICON = 24         # Icon im Piktogramm-Knopf - Luft fuer den 2px-Rand
PIKTO_GROESSE = 34      # Typ-Piktogramme links neben der Untersuchung
NEU_UNTERSUCHUNG_HOEHE = 36   # wie ein Untersuchungs-Knopf, passend zu add_Untersuchung.svg
NAV_ABSTAND = 4         # zwischen Piktogramm und Knopf, und Rand der Nav-Spalte


# ---------- Icon-Blase (Sprechblase an der Untersuchung) ----------

BLASE_RAND = 12            # Platz rundum fuer den Schatten
BLASE_POLSTER = 6          # Innenabstand Blase -> Icons
BLASE_VERBINDUNG = 8       # Laenge des Strichs von der Blase zum Knopf
BLASE_RADIUS = 12
BLASE_RANDFARBE = "#C9D0D8"   # hellgrau - die Blase soll sich nicht vor die Knoepfe draengen
BLASE_DAUER_MS = 220


# ---------- Hinweisbereich ueber dem Viewer ----------

# Hoehe des Hinweis-Labels ueber dem 3D-Viewer: mindestens eine Zeile,
# hoechstens HINWEIS_MAX_ZEILEN - darueber hinaus wird gescrollt.
HINWEIS_MAX_ZEILEN = 3
HINWEIS_RAND = 8


# ---------- Ordnerstruktur, Scans und Untersuchungen ----------

TYP_ORDNER = ["originale_scans", "isolierte_scans", "markierte_scans", "vermessene_scans"]
BILD_ENDUNGEN = (".png", ".jpg", ".jpeg")

ICON_ZU_LABEL = {
    "original": "hand.svg",
    "isoliert": "finger.svg",
    "markiert (vom Original)": "stift.svg",
    "markiert (vom isolierten)": "stift.svg",
    "genesungsverlauf": "heatmap3D.svg",
}

# Angaben zu einer Untersuchung (Nummer, Zeit nach OP) liegen als kleine
# JSON-Datei im Original-Scan-Ordner - so wandern sie mit, wenn der Ordner
# verschoben wird.
UNTERSUCHUNG_DATEI = "untersuchung.json"

ZEIT_EINHEITEN = {             # gespeichert  -> (Einzahl, Mehrzahl, Kuerzel fuer Ordnernamen)
    "Tage":   ("Tag",   "Tage",   "T"),
    "Wochen": ("Woche", "Wochen", "W"),
    "Monate": ("Monat", "Monate", "M"),
    "Jahre":  ("Jahr",  "Jahre",  "J"),
}

# gespeichert -> (Anzeige im Dialog, Anzeige auf dem Knopf, Endung im Ordnernamen).
# Im Ordnernamen ohne Umlaut, damit er auch auf Netzlaufwerken/in ZIPs heil bleibt.
OP_BEZUG = {
    "postOP": ("nach OP", "postOP", "postOP"),
    "praeOP": ("vor OP",  "präOP",  "praeOP"),
}


# ---------- Markierungen und Heatmap ----------

HEATMAPFARBEN = {
    "rot" : (220, 20, 20),
    "orange" : (255, 140, 0),
    "gelb" : (240, 220, 0),
    "grün" : (30, 180, 30),
    "blau" : (20, 20, 200)
}

LANDMARK_NAMEN = {
    "1" : "linke_rille",
    "2" : "fingerspitze",
    "3" : "rechte_rille"
}
LANDMARK_FARBE = (30, 30, 220) #blau
LANDMARK_RADIUS = 2

FARB_REIHENFOLGE = ["rot", "orange", "gelb", "grün", "blau"]
FARB_PRIORITAET = {HEATMAPFARBEN[name]: index for index, name in enumerate(FARB_REIHENFOLGE)}


# ---------- Vermessung speichern ----------

# Farbe der vermessenen Flaechen im gespeicherten Scan
MESSUNG_FARBE = (220, 20, 20)      # rot
ZAHL_FARBE = (255, 255, 255)       # weiss

# Die Flaechen liegen exakt auf der Hand-Oberflaeche und wuerden mit ihr
# um die Sichtbarkeit streiten (Z-Fighting). Deshalb werden sie entlang
# ihrer Normalen leicht abgehoben - gleiches Mittel wie in heatmap3D.py.
# Groesser = die Flaeche steht deutlicher ueber dem Scan und ist auch bei
# starker Kruemmung und flachem Blickwinkel noch klar zu sehen. Nicht
# beliebig erhoehen: in konkaven Stellen (Fingerzwischenraum) faltet sich
# die Flaeche in sich selbst, sobald der Versatz an den dortigen
# Kruemmungsradius heranreicht.
FLAECHEN_VERSATZ = 1.0             # mm

# Die Zahl muss immer UEBER der roten Flaeche liegen, darum an deren
# Versatz gekoppelt - sonst versinkt sie, sobald oben geschraubt wird.
ZAHL_ABSTAND_UEBER_FLAECHE = 0.3   # mm
ZAHL_VERSATZ = FLAECHEN_VERSATZ + ZAHL_ABSTAND_UEBER_FLAECHE
ZIFFER_TIEFE = 0.4                 # mm Extrusion

# Fuer die Pruefung, ob die starre Ziffer in einer Hautfalte versinkt
ZIFFER_UMKREIS_FAKTOR = 0.8        # halbe Diagonale, bezogen auf die Hoehe
ZIFFER_LUFT = 0.1                  # mm Sicherheitsabstand
ZIFFER_MIN_HOEHE = 1.0             # mm, kleiner wird die Ziffer nie
