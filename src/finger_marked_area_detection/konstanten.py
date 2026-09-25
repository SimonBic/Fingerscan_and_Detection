from pathlib import Path


# ---------- Pfade ----------

ICON_ORDNER = Path(__file__).parent / "icons"
LOGO_PFAD = ICON_ORDNER / "logo.png"

# Tutorials fuer die How-To-Seite: Markdown, Bilder liegen im selben Ordner
HOWTO_ORDNER = Path(__file__).parent / "howto"
HOWTO_DATEI = HOWTO_ORDNER / "anleitung.md"


# ---------- Anleitung drucken ----------

# Eigenes URL-Schema fuer den Druck-Link in anleitung.md. Damit laesst er
# sich von echten Web-Links unterscheiden, die ins Browserfenster gehoeren.
# Schreibweise in der .md:  [Anleitung drucken](drucken:anleitung)
DRUCK_SCHEMA = "drucken"

DRUCK_FENSTER_TITEL = "Anleitung drucken"
DRUCK_DOKUMENTNAME = "Fingerscan-Viewer - Anleitung"

# Muss explizit gesetzt werden, sonst erbt der Text die System-Palette.
# Bei einem dunklen Desktop-Theme kaeme die Anleitung sonst weiss auf
# weiss aus dem Drucker.
DRUCK_TEXTFARBE = "#000000"

# Die Anleitung als eigenes Fenster, aufrufbar ueber das Fragezeichen unten
# links in der laufenden Software
ANLEITUNG_FENSTER_TITEL = "Anleitung"
ANLEITUNG_FENSTER_GROESSE = (1000, 800)

# Fragezeichen-Knopf unten links. Quadratisch und bewusst klein - er soll
# auffindbar sein, ohne den Hauptknoepfen die Aufmerksamkeit zu nehmen.
HILFE_KNOPF_GROESSE = 36
HILFE_KNOPF_TEXT = "?"
HILFE_KNOPF_HILFE = "Anleitung öffnen"

# Die Anzeige laeuft im dunklen Theme - weisse Schrift auf dunklem Grund
# waere auf Papier unlesbar bzw. eine Tonerverschwendung. Fuer den Druck
# wird das Dokument deshalb neu aufgebaut und schwarz auf weiss gesetzt.
DRUCK_STYLESHEET = """
    body  { color: #000000; font-size: 10pt; }
    h1,h2 { color: #000000; }
    a     { color: #000000; }
    table { border-collapse: collapse; }
    td,th { border: 1px solid #888888; padding: 3px 6px; }
"""


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

# Checkbox beim Flaechen-Vermessen: Anteil der markierten Flaeche an der
# Fingeroberflaeche ab der Zwischenfingerfalte
ANTEIL_CHECKBOX_TEXT = "Anteil an der\nFingerfläche berechnen"
ANTEIL_CHECKBOX_HILFE = ("Berechnet beim Speichern, wie viel Prozent der Fingerfläche "
                         "ab der Zwischenfingerfalte markiert wurde, und schreibt es in "
                         "die Excel-Liste.")
ANTEIL_CHECKBOX_GESPERRT = ("Nur bei einem isolierten Finger möglich. Bei einem ganzen "
                            "Hand-Scan gibt es leider keine Zwischenfingerfalte als Bezug.")


# ---------- Finger isolieren: PCA-Nachbarschaft ----------

# Die Fingerachse entsteht aus einer PCA ueber die Punkte rund um die
# angeklickte Fingerkuppe. Frueher waren das die k naechsten Punkte im
# euklidischen Sinn, die Iddee griff regelmaessig auf den Nachbarfinger ueber,
# der in einem TEst nur etwa 26 mm Luftlinie entfernt ist. Gemessen an einem echten Scan
# stammten bei k=3000 rund 29 % der Punkte vom falschen Finger, und die
# Achse lag 64 Grad daneben.
#
# Jetzt wird geodätisch gemessen, also entlang der Oberflaeche. Von einer
# Fingerkuppe zur anderen sind das 135 mm, weil der Weg einmal runter zur
# Zwischenfingerfalte und wieder hoch muss. Damit ist der Nachbarfinger
# ausser Reichweite, ohne dass man irgendetwas segmentieren muesste.
#
# 40 mm ist an echten Scans eingemessen:
#   20 mm -> Achse entartet (nur die Kuppe, Eigenwerte fast gleich, 66 Grad Fehler)
#   30 mm -> 16 Grad Fehler
#   40 mm -> 7.6 Grad Fehler, Eigenwert-Verhaeltnis 3.5   <- hier
#   50 mm -> 1.4 Grad Fehler
#   60 mm -> driftet wieder, weil der Knoechel dazukommt
# Nach oben ist bis ~100 mm Luft, bevor ueberhaupt der erste Punkt des
# Nachbarfingers erreicht wird.
PCA_RADIUS = 40.0                  # mm, entlang der Oberflaeche

# Scan-Artefakte: einzelne Dreiecke ueberbruecken bis zu 65 mm und wuerden
# den kuerzesten Weg quer durch die Hand springen lassen. 5 mm trennt die
# sauber ab, ohne die Hand zu zerreissen (groesste zusammenhaengende
# Komponente bleibt bei 74973 von 74992 Punkten).
MAX_KANTENLAENGE = 5.0             # mm

# Sitzt der geklickte Punkt auf einem duennen Auswuchs, der in einer
# geschlossenen Blase endet (~1 % der Vertices), liefert der Radius nur
# eine Handvoll Punkte. Dann wird der Radius schrittweise aufgezogen.
MIN_PCA_PUNKTE = 300
RADIUS_MAX_FAKTOR = 4              # bis zum Vierfachen von PCA_RADIUS

# Grenzen des Reglers im Zwischenschritt
PCA_RADIUS_MIN = 15.0              # mm
PCA_RADIUS_MAX = 80.0              # mm


# ---------- Automatische Markierungserkennung ----------

# Die Stiftlinie wird in der Textur gesucht, das Ergebnis aber pro VERTEX
# gebraucht. Beides passt nicht zusammen: an einem echten Scan gemessen ist
# die Linie ~25 Texel breit, benachbarte Vertices liegen aber median 14
# Texel auseinander. Wer pro Vertex genau EIN Texel liest, trifft die Linie
# nur zufaellig - gemessen 1018 von 98600 Vertices, waehrend eine Abtastung
# der Umgebung 2463 findet. Genau das war die Ursache fuer "zu wenig
# erkannt".
#
# Statt die ganze Textur aufzuweiten (8192^2 = 67 Mio. Texel, als RGB rund
# 400 MB) wird pro Vertex ein kleines Raster gelesen und der kleinste
# Farbabstand darin genommen: 25 Nachschlaege pro Vertex statt 67 Mio.
RASTER_GROESSE = 5                 # 5x5 Texel pro Vertex

# Wie weit das Raster gespreizt wird, als Anteil des gemessenen medianen
# Vertexabstands in Texeln. 0.5 heisst: bis zur Mitte zum Nachbarvertex -
# zusammen decken die Vertices die Flaeche damit lueckenlos ab, ohne dass
# sich benachbarte Raster nennenswert ueberlappen.
RASTER_SPREIZUNG = 0.5

# Ein fester Toleranzwert traegt nicht ueber verschiedene Scans: mit der
# korrekten Texturfarbe und Toleranz 100 gelten 8,3 % der Textur als
# Markierung (vor allem beschattete Haut), mit 60 nur 1,4 %. Die Schwelle
# wird deshalb pro Scan bestimmt: typischer Hautabstand minus drei robuste
# Standardabweichungen. Der Faktor 3 ist an echten Scans eingemessen - er
# liefert dort eine Schwelle von ~68 und trifft 3,4 % der Vertices, also
# genau den Bereich, in dem die Stiftlinie endet.
SCHWELLE_MAD_FAKTOR = 3.0

# Die Schwelle muss zu einer plausiblen Markierungsgroesse fuehren -
# sonst greift FALLBACK_TOLERANZ.
MIN_MARKIERUNGS_ANTEIL = 0.0005    # 0,05 % der Vertices
MAX_MARKIERUNGS_ANTEIL = 0.05      # 5 % - darueber ist es keine Markierung mehr


# Greift die Luecken-Suche nicht (z. B. weil die Verteilung keinen klaren
# Sprung hat), wird auf diesen Wert zurueckgefallen.
FALLBACK_TOLERANZ = 60.0

# Die Pipette nimmt nicht stur das getroffene Texel: die Stiftlinie ist
# nur ~25 Texel breit bei ~14 Texel Vertexabstand, ein Vertex trifft den
# Linienkern also selten mittig. Stattdessen wird in dieser Umgebung die
# reinste Auspraegung dessen gesucht, worauf geklickt wurde.
PIPETTE_RADIUS_TEXEL = 10

# Anteil der extremsten Texel, aus denen die Farbe gemittelt wird.
PIPETTE_AUFFAELLIG_PROZENT = 10

# Hebt sich das geklickte Texel weniger als das vom Untergrund ab, war der
# Klick auf gleichmaessiger Flaeche - dann gibt es keine Markierung zu
# treffen und der Untergrund wird zurueckgegeben.
PIPETTE_MIN_ABHEBUNG = 5.0


# ---------- Flaeche aus der Markierung fuellen ----------

# Die erkannte Stiftlinie ist ein BAND von mehreren Vertices Breite, kein
# Strich. Sie zu einer Schleife zu ordnen scheitert daran (gemessen: von
# 20 Naechster-Nachbar-Ketten schloss sich keine einzige, jeder dritte
# Schritt kehrte die Richtung um). Stattdessen wird das Band samt der von
# ihm eingeschlossenen Flaeche genommen - der Zickzack liegt dann innen.

                                   # sondern ein anderer Fleck auf dem Finger


# ---------- Schwarzer Stift auf heller Haut ----------

# Werte aus GIMP 3.2.4, an echten Scans erprobt: leicht entsaettigen,
# Helligkeit und Kontrast anheben, dann harter Schwellwert. Danach ist nur
# noch die Markierung dunkel.
#
# Die Umsetzung benutzt GIMPs eigene Formeln, deshalb entsprechen diese
# Zahlen genau den Reglern im Dialog:
#   Farben > Saettigung           Skala 0,7
#   Farben > Helligkeit/Kontrast  +9 % / +48 %
#   Farben > Schwellwert          110
STIFT_SAETTIGUNG = 0.7
STIFT_HELLIGKEIT = 0.09
STIFT_KONTRAST = 0.48

# Beschriftung des Knopfes: benennt die Bildbedingungen, nicht Menschen.
# Fuer andere Hautfarben ist ein eigenes Verfahren vorgesehen.
STIFT_KNOPF_TEXT = "Schwarzer Stift,\nhelle Haut"
STIFT_KNOPF_HILFE = ("Erkennt eine schwarze Stiftmarkierung auf heller Haut und füllt "
                     "den eingekreisten Bereich. Nur am isolierten Finger.")

# Das Mesh wird vor dem Schneiden unterteilt, sonst ist es zu grob fuer
# die Linie: die Vertices liegen rund 23 Texel auseinander, die Linie ist
# rund 25 Texel breit. Zwei Stufen bringen den Punktabstand auf knapp
# 6 Texel - fein genug, um die Linie durchgehend zu erfassen, und immer
# noch schnell (gemessen 0,1 s fuer einen Finger).
STIFT_UNTERTEILUNGEN = 2

# Wie nah ein Punkt am urspruenglichen Fingerrand liegen muss, um als
# "am Rand" zu gelten
RAND_ABSTAND_TOLERANZ = 0.01       # mm


# ---------- Markierung ueber gerenderte Ansichten ----------

# Der Finger wird von mehreren Seiten gerendert und auf jedes Bild die
# Filterkette angewandt. Gemessen an einem Viewer-Screenshot liegen Haut
# (Median 232 nach der Kette) und Strich (Median 135) weit auseinander,
# und es wird KEINE Haut faelschlich markiert - 0,0 % bei Schwellen von
# 110 bis 140. Auf der rohen Textur liefen dagegen Schatten mit hinein.
ANSICHTEN_RUNDUM = 10              # Kameras rings um die Fingerachse
ANSICHTEN_SCHRAEG = 5              # je Ring von schraeg oben und unten
ANSICHT_SCHRAEG_GRAD = 35.0        # wie weit die schraegen Ringe gekippt sind

# Simons Wert, in GIMP auf einem Viewer-Screenshot eingemessen. Gilt nur
# fuer gerenderte Bilder - auf der Textur bedeutet dieselbe Zahl etwas
# anderes, deshalb steht STIFT_SCHWELLE davon getrennt.
STIFT_SCHWELLE_ANSICHT = 120.0

# An der Umrisskante wird ein Face streifend getroffen: wenige Pixel
# decken viele Faces, und die Zuordnung wird unzuverlaessig. Solche Faces
# werden verworfen - eine andere Ansicht sieht sie ohnehin frontal.
MIN_BLICKWINKEL_COS = 0.35         # entspricht rund 70 Grad zur Normalen


# Diagnosebilder der Ansichten. Liegt ausserhalb des Repositorys -
# Patientendaten gehoeren dort niemals hin.
ANSICHT_DIAGNOSE_ORDNER = (Path.home() / "Arbeit" / "UKR" /
                           "Diagnose_Ausgaben_Fingerscan_Viewer" / "Ausgabe_GIMP_Kette")

# Unterbrechungen im Strich: blasse Stellen oder kleine Loecher im Mesh
# zerlegen die Linie. An einem echten Finger gemessen waren es drei
# grosse Stuecke mit Luecken von 1,15 mm und 1,57 mm.
# 3,5 mm deckt die beobachteten Luecken ab (1,15 / 1,57 / 1,90 mm) und
# laesst den Schatten in der Zwischenfingerfalte draussen, der 8,65 mm
# entfernt liegt und NICHT zur Markierung gehoert.
MAX_LUECKE_MM = 3.5

# Grosszuegig: gebrueckt wird immer vom Hauptstrich aus, und die
# Laengengrenze verhindert Ausreisser. An einem echten Finger waren 27
# Bruecken noetig, die meisten davon unter 1 mm.
MAX_LUECKEN = 80


# Breite, in der eine gezogene Bruecke gezeichnet wird - ungefaehr die
# Dicke des Stiftstrichs, damit die Bruecke nicht als Haarriss auffaellt.
STRICH_DICKE_MM = 0.8

# Kleinere Stuecke ziehen keine Bruecken nach sich: einzelne Fehlpixel
# sollen den Strich nicht quer ueber den Finger verlaengern.
MIN_STUECK_PIXEL = 30
