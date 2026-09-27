
import shutil
import json
import time
import pyvista as p_v
import vtk
import numpy as np
from pathlib import Path
from collections import defaultdict

from PySide6.QtWidgets import (
    QMainWindow, 
    QApplication, 
    QLabel,
    QVBoxLayout, 
    QWidget, 
    QHBoxLayout,
    QGridLayout,
    QPushButton, 
    QDialog,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QMenu,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView)
from PySide6.QtCore import (
    Qt,
    QEvent,
    QSize,
    QSettings,
    QUrl,
    QTimer)
from PySide6.QtGui import (
    QIcon,
    QCursor,
    QDesktopServices,
    QPixmap)

from logik.utils import generator_bis_ende
from logik.farberkennung import (
    finde_markierungs_punkte,
    entferne_ausreisser_punkte,
    baue_geschlossenen_pfad,
    textur_farbe_an_punkt)
from logik.schwarzer_stift import markiere_strich
from logik.messungen import (
    berechne_flaeche_und_umfang, 
    volumen_ab_markierung,
    volumen_ab_ring, 
    volumen_ab_fingerzwischenfalte,
    flaeche_ab_fingerzwischenfalte,
    flaeche_oberhalb_falte,
    volumen_gesamtes_mesh)
from ui_unterklassen.hauptmenue.farbauswahl_widget import FarbAuswahlWidget
from logik.isolate_finger import (
    rendere_teile,
    load_teilmeshe_mit_textur,
    isolate_finger,
    erstelle_schnitt_ellipsoid,
    finger_normale,
    lade_isolate_finger_parameter,
    speichere_isolate_finger_parameter)
from logik.draw_area_on_scan import (
    draw_main, 
    save_drawn_area, 
    extract_faces_of_hand,
    schneide_flaeche_aus_loop,
    lese_markierungsfarbe)
from logik.vermessung_speichern import (
    baue_zahl_fuer_messung,
    speichere_vermessung,
    schreibe_ergebnis_liste,
    vermessungs_ordner)
from logik.heatmap3D import (
    bereiche_in_markierung,
    speichere_genesungsverlauf,
    finde_markierte_scans,
    lade_markierung,
    finde_nagel_normale,
    rotationsmatrix_um_z_fuer_nagel_ausrichtung,
    isolierte_scan_name_aus_markierung,
    farb_prioritaet)
from logik.heatmap2D import heatmap_main
from ui_unterklassen.patientenverwaltung.untersuchungs_dialog import (
    UntersuchungDialog,
    op_bezug)
from ui_unterklassen.patientenverwaltung.blase import IconBlase
from ui_unterklassen.hauptmenue.oberflaeche import UI_Aufbau_Mixin
from ui_unterklassen.titelbildschirm.titel_bildschirm import TitelBildschirm
from ui_unterklassen.hilfe.anleitungfenster import AnleitungFenster
from ui_unterklassen.terminal.terminal_fenster import TerminalFenster
from ui_unterklassen.hauptmenue.root_ordner_dialog import root_ordner_waehlen
import konstanten as k


def zeit_text(meta):
    """'6 Wochen', '1 Monat' - oder None, wenn keine Angabe."""
    if not meta or "wert" not in meta or meta.get("einheit") not in k.ZEIT_EINHEITEN:
        return None
    einzahl, mehrzahl, _ = k.ZEIT_EINHEITEN[meta["einheit"]]
    return f"{meta['wert']} {einzahl if meta['wert'] == 1 else mehrzahl}"

class HauptFenster(UI_Aufbau_Mixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fingerscan-Viewer")
        self.setWindowIcon(QIcon(str(k.LOGO_PFAD)))
        self.resize(1920, 1080)
        # QMainWindow nimmt von sich aus Drops an. Auf dem Title Screen gibt es
        # aber noch keinen Plotter, dropEvent wuerde ins Leere greifen -
        # eingeschaltet wird es erst in _software_aufbauen
        self.setAcceptDrops(False)

        self.einstellungen = QSettings(k.EINSTELLUNGEN_FIRMA, k.EINSTELLUNGEN_APP)
        self.root_ordner = self.einstellungen.value(k.ROOT_ORDNER_SCHLUESSEL, "")

        self.aktueller_ordner = None
        self.isolieren_ablauf = None
        self.automatisch_modus_aktiv = False
        self.zeichnungs_status = {"flaeche": None, "landmarken": None, "punkte_eingezeichnet": None}
        self.aktuelle_teile = None
        # Mehrfach-Vermessung: je Eintrag
        # {"flaeche", "flaeche_mm2", "umfang_mm", "actor", "zahl_actor"}
        self.vermessungen = []
        self.ellipsoid_kontext = None
        self.aktueller_ellipsoid_actor = None
        self.isolieren_phase = None
        self.genesungsverlauf_warteschlange = []
        self.genesungsverlauf_index = 0
        self.genesungsverlauf_gewinner = {}
        self.genesungsverlauf_aktuell_rotiert = None
        self._genesungsverlauf_mesh_fuer_klick = None
        self._anleitung_fenster = None
        self._terminal_fenster = None

        # Zuerst der Title Screen im selben Fenster. Die eigentliche Oberflaeche
        # (mit dem teuren VTK-Viewer) entsteht erst bei "Software starten" -
        # so ist das Fenster sofort da.
        self.titel_bildschirm = TitelBildschirm(self.root_ordner)
        self.titel_bildschirm.software_starten.connect(self._software_starten)
        self.titel_bildschirm.root_ordner_bearbeiten.connect(self._titel_root_ordner)
        self.setCentralWidget(self.titel_bildschirm)

    # ---------- Title Screen ----------

    def _software_starten(self):
        self.titel_bildschirm.zeige_laden()
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.processEvents()      # "Wird gestartet ..." sichtbar machen
        # Nicht direkt aufbauen: das ersetzt den Title Screen, und der wuerde
        # geloescht, waehrend sein eigener Knopf-Klick noch laeuft
        QTimer.singleShot(0, self._software_aufbauen_mit_cursor)

    def _software_aufbauen_mit_cursor(self):
        try:
            self._software_aufbauen()
        finally:
            QApplication.restoreOverrideCursor()

    def _titel_root_ordner(self):
        pfad = root_ordner_waehlen(self, self.root_ordner)
        if pfad is None:
            return
        self.root_ordner = pfad
        self.einstellungen.setValue(k.ROOT_ORDNER_SCHLUESSEL, pfad)
        # Kein _root_ordner_anwenden(): die Nav-Spalte gibt es noch nicht, sie
        # wird beim Start ohnehin aus self.root_ordner gebaut
        self.titel_bildschirm.setze_root_ordner(pfad)

    # ---------- kleine Bau-Helfer ----------

    def zeige_anleitung(self):
        # Einmal bauen und behalten: so bleibt die Scrollposition erhalten,
        # wenn man zwischendurch etwas ausprobiert und wieder nachliest.
        if self._anleitung_fenster is None:
            self._anleitung_fenster = AnleitungFenster(self)
        self._anleitung_fenster.zeige()

    def zeige_terminal_ausgabe(self):
        # Zeigt dem User die Terminalausgabe. Wie bei der Anleitung einmal
        # bauen und behalten, so bleibt die Scrollposition erhalten.
        if self._terminal_fenster is None:
            self._terminal_fenster = TerminalFenster(self)
        self._terminal_fenster.zeige()

    # ---------- Drag & Drop / Laden / Einstellungen ----------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        self.aktueller_ordner = urls[0].toLocalFile()
        pfad = Path(urls[0].toLocalFile())
        ordner = pfad.parent if pfad.is_file() else pfad
        self.lade_und_zeige(ordner)

    def _rendere_teile(self, teile: list) -> None:
        # Gemeinsame Funktion, damit die Screenshots der
        # Markierungserkennung exakt so aussehen wie der Viewer.
        rendere_teile(self.plotter, teile)

    def lade_und_zeige(self, pfad: Path):
        # Patient des geladenen Scans mitbeobachten
        self._patienten_beobachten()
        self.plotter.clear()
        teile = load_teilmeshe_mit_textur(pfad)

        if not teile:
            print("Keine gültigen Meshes gefunden.")
            return

        self.aktuelle_teile = teile
        self.aktuelles_hand_mesh = p_v.merge([teil for teil, tex in teile])

        self._rendere_teile(teile)

    def zeige_basis_mesh_neu(self):
        self.plotter.clear()
        self._rendere_teile(self.aktuelle_teile)

    def lade_main_menu(self):

        self.haupt_buttons_container.setVisible(True)
        self.isolieren_wahl_container.setVisible(False)
        self.malen_wahl_container.setVisible(False)
        self.vermessen_malen_container.setVisible(False)
        self.farbe_wahl_container.setVisible(False)
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(False)
        self.volumen_container.setVisible(False)
        self.vermessungen.clear()
        for button in (self.overlay_buttons):
            button.setVisible(False)
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.plotter.disable_picking()
        self._pipette_aktiv = False
        self.plotter.interactor.removeEventFilter(self)
        self.plotter.interactor.unsetCursor()
        print("Main Menu loaded succesfully")

    def einstellungen_oeffnen(self):
        # Zahnrad in der laufenden Software, gleicher Dialog wie auf dem Title Screen
        pfad = root_ordner_waehlen(self, self.root_ordner)
        if pfad is None:
            return
        self.root_ordner = pfad
        self.einstellungen.setValue(k.ROOT_ORDNER_SCHLUESSEL, pfad)
        self._root_ordner_anwenden()
        print("settings loaded succesfully.")

    def _root_ordner_anwenden(self):
        if not self.root_ordner or not Path(self.root_ordner).is_dir():
            return
        self.baum_neu_aufbauen()


    def _scan_analysieren(self, scan_name):
        # Vermessen wird auf einem beliebigen Scan (original, isoliert,
        # markiert) - die Herkunft kommt ins Label, damit sich zwei
        # Vermessungen derselben Untersuchung nicht ueberschreiben.
        if scan_name.endswith("_vermessen"):
            basis, herkunft = self._scan_analysieren(scan_name[:-len("_vermessen")])
            return basis, f"vermessen – {herkunft}"
        if scan_name.endswith("_isoliert_marked"):
            return scan_name[:-len("_isoliert_marked")], "markiert (vom isolierten)"
        if scan_name.endswith("_marked"):
            return scan_name[:-len("_marked")], "markiert (vom Original)"
        if scan_name.endswith("_isoliert"):
            return scan_name[:-len("_isoliert")], "isoliert"
        return scan_name, "original"

    def baum_neu_aufbauen(self):
        #Baut die Navigations-Spalte: Patienten als Avatar-Knoepfe,
        #darunter aufklappbar die Untersuchungen, darunter die Typ-Piktogramme.
        # Alte Patienten-Widgets entfernen
        while self.nav_layout.count() > 0:
            item = self.nav_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Die Knoepfe, an denen eine offene Blase haengt, werden gleich geloescht
        if self._blase is not None:
            self._blase.close()
        self._offener_patient = None
        self._offener_patient_name = None
        self._patient_aufklapp_widgets = {}
        self._angezeigte_signaturen = {}

        if not self.root_ordner or not Path(self.root_ordner).is_dir():
            print("Navigationcolumn did not load, path is not a directory or path not found.")
            return

        root = Path(self.root_ordner)
        for patient_ordner in sorted(p for p in root.iterdir() if p.is_dir()):
            # Stand merken, den die Spalte ab jetzt anzeigt, dagegen prueft
            # der Waechter. Fuer alle Patienten, nicht nur die beobachteten:
            # wer spaeter aufgeklappt wird, braucht den Vergleich auch.
            self._angezeigte_signaturen[patient_ordner.resolve()] = self._patient_signatur(patient_ordner)
            struktur = self._untersuchungen_sammeln(patient_ordner)
            
            if not struktur and not any((patient_ordner / t).is_dir() for t in k.TYP_ORDNER):
                continue
            self._patient_block_bauen(patient_ordner, struktur)

        self._neuer_patient_knopf_bauen()
        self._patienten_beobachten()
        print("Navigationcolumn loaded succesfully. ")


    # ---------- Nav-Spalte aktuell halten ----------

    def _nav_aktualisieren(self):
        #neu aufbauen die navsplte, und den aktuellen pat und scrollstelle etc gleich lassen
        # Eine offene Icon-Blase wird bewusst nicht wieder aufgemacht, sie
        # wuerde sonst nach jedem Speichern unvermittelt aufploppen.
        patient = self._offener_patient_name
        scroll = self.nav_spalte.verticalScrollBar().value()

        self.baum_neu_aufbauen()
        if patient in self._patient_aufklapp_widgets:
            self._patient_toggle(self._patient_aufklapp_widgets[patient])
        # Das Layout steht erst nach dem nächsten Event-Durchlauf
        QTimer.singleShot(0, lambda: self.nav_spalte.verticalScrollBar().setValue(scroll))

    def _patient_signatur(self, patient_ordner):
        #Alles, was die Nav-Spalte von einem Patienten anzeigt. ändert
        #sich das, muss neu gebaut werden
        struktur = self._untersuchungen_sammeln(patient_ordner) if patient_ordner.is_dir() else {}
        return (
            tuple((basis, tuple(sorted(typen.items())), tuple(sorted(self._untersuchung_meta(typen).items())))
                  for basis, typen in struktur.items()),
            self._neuester_genesungsverlauf(patient_ordner),
            (patient_ordner / "heatmap" / "Genesungsverlauf.png").is_file(),
        )

    def _beobachtete_patienten(self):
        #Der aufgeklappte Patient und der Patient des geladenen Scans.
        if not self.root_ordner or not Path(self.root_ordner).is_dir():
            return set()
        root = Path(self.root_ordner).resolve()
        patienten = set()
        if self._offener_patient_name:
            patienten.add(root / self._offener_patient_name)
        if self.aktueller_ordner is not None:
            for vorfahr in Path(self.aktueller_ordner).resolve().parents:
                if vorfahr.parent == root:
                    patienten.add(vorfahr)
                    break
        return patienten

    def _patienten_beobachten(self):
        #Wächter auf die aktuell relevanten Patienten umstellen.
        
        if not hasattr(self, "_patient_waechter"):
            return
        patienten = self._beobachtete_patienten()

        pfade = set()
        for patient in patienten:
            if not patient.is_dir():
                continue
            pfade.add(str(patient))
            for typ in (d for d in patient.iterdir() if d.is_dir()):
                pfade.add(str(typ))
                pfade.update(str(scan) for scan in typ.iterdir() if scan.is_dir())

        bisher = set(self._patient_waechter.directories())
        if bisher - pfade:
            self._patient_waechter.removePaths(list(bisher - pfade))
        if pfade - bisher:
            self._patient_waechter.addPaths(list(pfade - bisher))
        

    def _patienten_pruefen(self):
        #Weicht die Platte von dem ab, was die Nav-Spalte zeigt?
        geaendert = any(self._patient_signatur(p) != self._angezeigte_signaturen.get(p)
                        for p in self._beobachtete_patienten())
        if geaendert:
            self._nav_aktualisieren()      # baut neu und beobachtet dabei neu
        else:
            # Nichts Sichtbares neu - aber evtl. neue Unterordner, die ab
            # jetzt mitbeobachtet werden muessen
            self._patienten_beobachten()

    def _neuer_patient_knopf_bauen(self):
        #'''+'-Knopf am Ende der Patientenliste, gleiche Groesse und Flucht
        # wie die Patienten-Avatare darueber.'''
        knopf = QToolButton()
        knopf.setObjectName("patient_knopf")
        knopf.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        knopf.setFixedSize(k.NAV_KNOPF_BREITE, k.NAV_KNOPF_BREITE)
        knopf.setIconSize(QSize(44, 44))
        knopf.setIcon(QIcon(str(k.ICON_ORDNER / "add_patient.svg")))
        knopf.setText("Neu")
        knopf.setToolTip("Neuen Patienten anlegen")
        knopf.clicked.connect(self.neuer_patient_klick)

        zeile = QWidget()
        z_layout = QHBoxLayout(zeile)
        z_layout.setContentsMargins(0, 0, 0, 0)
        z_layout.setSpacing(0)
        # Platz der Patienten-Piktogramme freihalten -> buendig mit den Avataren
        z_layout.addSpacing(k.PIKTO_GROESSE + k.NAV_ABSTAND)
        z_layout.addWidget(knopf)
        self.nav_layout.addWidget(zeile, alignment=Qt.AlignLeft)

    def neuer_patient_klick(self):
        root = Path(self.root_ordner)
        name = ""
        while True:
            name, ok = QInputDialog.getText(self, "Neuer Patient", "Name des Patienten:", text=name)
            if not ok:
                return
            name = name.strip()
            fehler = self._ordner_name_pruefen(root, name)
            if fehler is None:
                break
            QMessageBox.warning(self, "Neuer Patient", fehler)

        patient_ordner = root / name
        try:
            patient_ordner.mkdir()
            # Die Scan-Typ-Ordner gleich mit anlegen: daran erkennt die
            # Nav-Spalte einen Patientenordner, auch solange er leer ist.
            for typ in k.TYP_ORDNER:
                (patient_ordner / typ).mkdir()
        except OSError as e:
            QMessageBox.warning(self, "Neuer Patient", f"Ordner konnte nicht angelegt werden:\n{e}")
            print(f"create patient failed, directory could not be created:\n{e}")
            return

        self.baum_neu_aufbauen()
        if name in self._patient_aufklapp_widgets:
            self._patient_toggle(self._patient_aufklapp_widgets[name])
        self.hinweis_label.setText(f"Patient '{name}' angelegt.")
        print("Patient created succesfully")

    @staticmethod
    def _ordner_name_pruefen(eltern, name):
        #Taugt 'name' als neuer Ordner in 'eltern'? Fehlermeldung als Text,
        #oder None falls ja
        if not name:
            return "Bitte einen Namen eingeben."
        if name in (".", ".."):
            return f"'{name}' ist als Name nicht erlaubt."
        if any(z in name for z in '/\\:*?"<>|'):
            return 'Der Name darf keines dieser Zeichen enthalten:  / \\ : * ? " < > |'
        # Gross/klein ignorieren - auf Windows waeren 'Pat1' und 'pat1'
        # derselbe Ordner.
        vorhanden = {p.name.lower() for p in eltern.iterdir()} if eltern.is_dir() else set()
        if name.lower() in vorhanden:
            return f"'{name}' gibt es hier bereits."
        return None

    # ---------- Neuen Scan hinzufuegen ----------


    def neuer_scan_klick(self, patient_ordner):
        dateien, _ = QFileDialog.getOpenFileNames(
            self, f"Scan für {patient_ordner.name} hinzufügen, bitte .obj, .mtl und Texturbilder auswählen",
            str(Path.home()),
            "Scan-Dateien (*.obj *.mtl *.png *.jpg *.jpeg);;Alle Dateien (*)")
        if not dateien:
            print("no data found while creating new scan")
            return
        dateien = [Path(d) for d in dateien]

        fehler = self._scan_dateien_pruefen(dateien)
        if fehler:
            QMessageBox.warning(
                self, "Scan unvollständig",
                "Der Scan kann so nicht hinzugefügt werden:\n\n"
                + "\n".join(f"•  {f}" for f in fehler))
            print(f"Missing data in scan" + "\n".join(f"•  {f}" for f in fehler))
            return

        # Nummer, Zeit nach OP und Ordnername abfragen
        ziel_eltern = patient_ordner / "originale_scans"
        dialog = UntersuchungDialog(
            self, f"Neuer Scan für {patient_ordner.name}",
            {"nummer": self._naechste_nummer(patient_ordner)},
            lambda nummer, ordner: (self._nummer_pruefen(patient_ordner, nummer)
                                    or self._ordner_name_pruefen(ziel_eltern, ordner)
                                    or self._scan_name_pruefen(ordner)),
            ordnername="")
        if dialog.exec() != QDialog.Accepted:
            print("Data while creating new scna was not accepted")
            return
        name = dialog.ordner()

        ziel = ziel_eltern / name
        try:
            ziel.mkdir(parents=True)
            for d in dateien:
                shutil.copy2(d, ziel / d.name)
            self._meta_schreiben(ziel, dialog.meta())
            print("New scan created succesfully")
        except OSError as e:
            # halb kopierten Ordner nicht liegen lassen , der wuerde sonst
            # als kaputte Untersuchung in der Nav-Spalte auftauchen
            shutil.rmtree(ziel, ignore_errors=True)
            QMessageBox.warning(self, "Neuer Scan", f"Kopieren fehlgeschlagen:\n{e}")
            print(f"Copying data for new scan failed {e}")
            return

        self._nav_aktualisieren()
        self.hinweis_label.setText(f"Scan '{name}' zu {patient_ordner.name} hinzugefügt.")

    @classmethod
    def _scan_dateien_pruefen(cls, dateien):
        
        objs = [d for d in dateien if d.suffix.lower() == ".obj"]
        mtls = [d for d in dateien if d.suffix.lower() == ".mtl"]
        bilder = [d for d in dateien if d.suffix.lower() in k.BILD_ENDUNGEN]
        fehler = []

        if not objs:
            fehler.append("Es fehlt die .obj-Datei (das 3D-Modell).")
            print("no .obj file found")
        elif len(objs) > 1:
            fehler.append(f"Mehrere .obj-Dateien ausgewählt ({', '.join(d.name for d in objs)}) – bitte nur eine.")
            print("too many .obj file, maximum 1")
        if not mtls:
            fehler.append("Es fehlt die .mtl-Datei (die Materialbeschreibung).")
            print("no .mtl file found")
        elif len(mtls) > 1:
            fehler.append(f"Mehrere .mtl-Dateien ausgewählt ({', '.join(d.name for d in mtls)}) – bitte nur eine.")
            print("too many .mtl files, maximum 1")
        if not bilder:
            fehler.append("Es fehlt mindestens ein Texturbild (.png oder .jpg).")
            print("no texture found, please add at least 1")

        # Passen die Dateien auch zusammen? Die .obj nennt ihre .mtl, die
        # .mtl nennt ihre Bilder - fehlt eins davon, laedt der Scan ohne Textur.
        if len(objs) == 1 and len(mtls) == 1:
            erwartet = cls._verweise(objs[0], "mtllib")
            if erwartet and mtls[0].name not in erwartet:
                fehler.append(f"Die .obj erwartet '{', '.join(erwartet)}', ausgewählt ist aber '{mtls[0].name}'.")
        if len(mtls) == 1 and bilder:
            vorhanden = {b.name for b in bilder}
            fehlend = [b for b in cls._verweise(mtls[0], "map_Kd") if b not in vorhanden]
            if fehlend:
                fehler.append(f"Die .mtl braucht noch diese Bilder: {', '.join(fehlend)}")

        return fehler

    @staticmethod
    def _verweise(datei, schluessel):
        #Dateinamen hinter 'schluessel' (mtllib / map_Kd), ohne Doppelte.
        #Optionen wie '-s 1 1 1' vor dem Namen werden uebersprungen - der
        #Name steht immer am Ende der Zeile.
        namen = []
        try:
            with open(datei, encoding="utf-8", errors="replace") as f:
                for zeile in f:
                    teile = zeile.split()
                    if len(teile) >= 2 and teile[0] == schluessel:
                        name = Path(teile[-1].replace("\\", "/")).name
                        if name not in namen:
                            namen.append(name)
        except OSError:
            pass
        return namen

    @staticmethod
    def _scan_name_pruefen(name):
        # Diese Endungen liest _scan_analysieren als Scan-Typ - ein Original
        # mit so einem Namen wuerde falsch einsortiert.
        for endung in ("_isoliert", "_marked", "_vermessen", "_genesungsverlauf"):
            if name.endswith(endung):
                print("all filenames created by users cannot end with _isoliert, _marked, _vermessen or _genesungsverlauf")
                return f"Der Name darf nicht auf '{endung}' enden das ist für bearbeitete Scans reserviert."
        return None

    def _untersuchungen_sammeln(self, patient_ordner):
        #{untersuchung_basis: {typ_label: pfad}}, lexikografisch nach Basis."""
        untersuchungen = defaultdict(dict)
        for typ in k.TYP_ORDNER:
            typ_pfad = patient_ordner / typ
            if not typ_pfad.is_dir():
                continue
            for scan in sorted(s for s in typ_pfad.iterdir() if s.is_dir()):
                basis, label = self._scan_analysieren(scan.name)
                untersuchungen[basis][label] = str(scan)
        # Nach eingetragener Nummer; Untersuchungen ohne Angabe ans Ende,
        # untereinander alphabetisch (alter Stand)
        def reihenfolge(eintrag):
            nummer = self._untersuchung_meta(eintrag[1]).get("nummer")
            return (nummer is None, nummer or 0, eintrag[0])
        return dict(sorted(untersuchungen.items(), key=reihenfolge))

    @staticmethod
    def _meta_ordner(typen):
        """Wo die Angaben einer Untersuchung liegen: im Original-Scan, und
        falls es keinen gibt, im ersten vorhandenen Scan dieser Untersuchung."""
        try:
            return Path(typen.get("original") or next(iter(typen.values())))
        except:
            print("Meta not found")

    @classmethod    
    def _untersuchung_meta(cls, typen):
        for ordner in [cls._meta_ordner(typen), *map(Path, typen.values())]:
            datei = ordner / k.UNTERSUCHUNG_DATEI
            if datei.is_file():
                try:
                    return json.loads(datei.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    return {}
        return {}

    @staticmethod
    def _meta_schreiben(ordner, meta):
        (Path(ordner) / k.UNTERSUCHUNG_DATEI).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Meta data {meta} written in {ordner}")

    def _nummer_pruefen(self, patient_ordner, nummer, ausser_basis=None):
        """Fehlertext, wenn die Nummer bei diesem Patienten schon vergeben ist."""
        for basis, typen in self._untersuchungen_sammeln(patient_ordner).items():
            if basis != ausser_basis and self._untersuchung_meta(typen).get("nummer") == nummer:
                return f"Untersuchung {nummer} gibt es bei {patient_ordner.name} schon (Ordner '{basis}')."
        return None


    def _patient_block_bauen(self, patient_ordner, struktur):
        patient_name = patient_ordner.name
        # Avatar-Knopf
        patient_knopf = QToolButton()
        patient_knopf.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        patient_knopf.setFixedSize(k.NAV_KNOPF_BREITE, k.NAV_KNOPF_BREITE)
        patient_knopf.setIconSize(QSize(44, 44))
        patient_knopf.setIcon(QIcon(str(k.ICON_ORDNER / "person.svg")))
        patient_knopf.setText(patient_name)
        patient_knopf.setObjectName("patient_knopf")

       
        patient_zeile = QWidget()
        pz_layout = QHBoxLayout(patient_zeile)
        pz_layout.setContentsMargins(0, 0, 0, 0)
        pz_layout.setSpacing(k.NAV_ABSTAND)

        # Senkrechte Spalte fuer alles, was den ganzen Patienten betrifft
        # (3D-Verlauf, 2D-Heatmap). Zwei Knoepfe passen neben den Avatar.
        patient_piktos = QWidget()
        patient_piktos.setFixedWidth(k.PIKTO_GROESSE)
        pp_layout = QVBoxLayout(patient_piktos)
        pp_layout.setContentsMargins(0, 0, 0, 0)
        pp_layout.setSpacing(k.NAV_ABSTAND)
        pp_layout.setAlignment(Qt.AlignTop)

        patient_knoepfe = [knopf for knopf in (self._genesungsverlauf_knopf_bauen(patient_ordner), self._heatmap_2d_knopf_bauen(patient_ordner)) if knopf is not None]
        for knopf in patient_knoepfe:
            pp_layout.addWidget(knopf)

        pz_layout.addWidget(patient_piktos)
        pz_layout.addWidget(patient_knopf)
        self.nav_layout.addWidget(patient_zeile, alignment=Qt.AlignLeft)

        # Container fuer die Untersuchungen (anfangs versteckt).
        # Raster: Spalte 0 = Piktogramme, Spalte 1 = Untersuchungs-Knopf.
        untersuchungen_container = QWidget()
        uc_layout = QGridLayout(untersuchungen_container)
        uc_layout.setContentsMargins(0, 0, 0, 0)
        uc_layout.setHorizontalSpacing(k.NAV_ABSTAND)
        uc_layout.setVerticalSpacing(3)
        # Spalte 0 behaelt ihre Breite auch wenn die Piktogramme versteckt
        # sind - sonst springt der Untersuchungs-Knopf beim Aufklappen zur Seite.
        uc_layout.setColumnMinimumWidth(0, k.PIKTO_GROESSE)
        untersuchungen_container.setVisible(False)
        self.nav_layout.addWidget(untersuchungen_container, alignment=Qt.AlignLeft)

        # Untersuchungen in der Reihenfolge ihrer Nummer
        for zeile, (basis, typen) in enumerate(struktur.items()):
            self._untersuchung_block_bauen(uc_layout, zeile, patient_ordner, basis, typen)

        # Unter der letzten Untersuchung: neuen Scan hinzufuegen
        neu_knopf = QToolButton()
        neu_knopf.setObjectName("untersuchung_neu_knopf")
        neu_knopf.setFixedSize(k.NAV_KNOPF_BREITE, k.NEU_UNTERSUCHUNG_HOEHE)
        neu_knopf.setIconSize(QSize(k.NAV_KNOPF_BREITE, k.NEU_UNTERSUCHUNG_HOEHE))
        neu_knopf.setIcon(QIcon(str(k.ICON_ORDNER / "add_Untersuchung.svg")))
        neu_knopf.setToolTip("Neuen Scan hinzufügen")
        neu_knopf.clicked.connect(lambda _, po=patient_ordner: self.neuer_scan_klick(po))
        uc_layout.addWidget(neu_knopf, len(struktur), 1, alignment=Qt.AlignTop)

        # Patienten-Piktogramme nur bei aufgeklapptem Patienten zeigen
        aufklapp_widgets = [untersuchungen_container, *patient_knoepfe]
        self._patient_aufklapp_widgets[patient_name] = aufklapp_widgets
        patient_knopf.clicked.connect(
            lambda _, w=aufklapp_widgets: self._patient_toggle(w)
        )
        print(f"Patient {patient_name} added to the navigation column with {len(struktur)} examinations")

    @staticmethod
    def _neuester_genesungsverlauf(patient_ordner):
        verlauf_ordner = patient_ordner / "genesungsverlauf"
        if not verlauf_ordner.is_dir():
            return None
        verlaeufe = [v for v in verlauf_ordner.iterdir() if v.is_dir() and list(v.glob("*.obj"))]
        if not verlaeufe:
            return None
        return max(verlaeufe, key=lambda v: v.stat().st_mtime)

    def _genesungsverlauf_knopf_bauen(self, patient_ordner):
        """Heatmap-Knopf fuer den neuesten gespeicherten Genesungsverlauf,
        None wenn der Patient keinen hat."""
        neuester = self._neuester_genesungsverlauf(patient_ordner)
        if neuester is None:
            return None

        return self._patient_pikto(
            "heatmap3D.svg", f"3D-Genesungsverlauf: {neuester.name}",
            lambda _, pf=neuester: self._scan_laden_aus_pfad(pf))

    def _heatmap_2d_knopf_bauen(self, patient_ordner):
        """Knopf fuer die 2D-Heatmap aus heatmap_main(), None wenn es keine gibt."""
        bild = patient_ordner / "heatmap" / "Genesungsverlauf.png"
        if not bild.is_file():
            return None
        return self._patient_pikto(
            "heatmap2D.svg", "2D-Heatmap / Genesungsverlauf",
            lambda _, pf=bild: self._bild_zeigen(pf))

    def _patient_pikto(self, icon_datei, tooltip, slot):
        knopf = QToolButton()
        knopf.setObjectName("pikto_knopf")
        knopf.setIconSize(QSize(k.PIKTO_ICON, k.PIKTO_ICON))
        knopf.setFixedSize(k.PIKTO_GROESSE, k.PIKTO_GROESSE)
        knopf.setIcon(QIcon(str(k.ICON_ORDNER / icon_datei)))
        knopf.setToolTip(tooltip)
        knopf.clicked.connect(slot)
        knopf.setVisible(False)
        return knopf


    def _untersuchung_block_bauen(self, eltern_layout, zeile, patient_ordner, basis, typen):
        meta = self._untersuchung_meta(typen)
        zeit = zeit_text(meta)
        nummer = meta.get("nummer")

        # "Untersuchung 2" passt nicht in 80px - daher kurz wie in den
        # Ordnernamen (U1_2W_postOP), ausfuehrlich im Tooltip
        if nummer and zeit:
            dialog_text, knopf_text, _ = k.OP_BEZUG[op_bezug(meta)]
            u_knopf = QPushButton(f"U{nummer} · {knopf_text}\n{zeit}")
        else:
            u_knopf = QPushButton("U?\nohne Angabe")
            print(f"Examination {basis} has no number and no time saved, listed as unknown")
        u_knopf.setObjectName("untersuchung_knopf")
        u_knopf.setFixedWidth(k.NAV_KNOPF_BREITE)
        if nummer and zeit:
            u_knopf.setToolTip(f"Untersuchung {nummer}; {zeit} {dialog_text}\nOrdner: {basis}")
        else:
            u_knopf.setToolTip(f"Ordner: {basis}\nNoch keine Angaben; Rechtsklick, Angaben bearbeiten")
        u_knopf.setContextMenuPolicy(Qt.CustomContextMenu)
        u_knopf.customContextMenuRequested.connect(
            lambda pos, kn=u_knopf, po=patient_ordner, b=basis, t=typen: self._untersuchung_menue(kn, pos, po, b, t))
        eltern_layout.addWidget(u_knopf, zeile, 1, alignment=Qt.AlignTop)
        u_knopf.clicked.connect(
            lambda _, kn=u_knopf, t=typen: self._untersuchung_klick(kn, t))


    def _untersuchung_klick(self, knopf, typen):
        """Icon-Blase an diesem Knopf aufploppen lassen - oder zu lassen, wenn
        genau dieser Klick sie eben geschlossen hat."""
        # Qt.Popup schliesst sich beim Klick daneben und reicht den Klick dann
        # an den Knopf darunter weiter. War das der Knopf der Blase, soll der
        # Klick sie nur schliessen, nicht sofort wieder oeffnen.
        letzter_knopf, zeitpunkt = self._blase_zu
        if letzter_knopf is knopf and time.monotonic() - zeitpunkt < 0.3:
            return

        blase = IconBlase(knopf, self._pikto_knoepfe(typen))
        blase.geschlossen.connect(lambda kn=knopf: self._blase_geschlossen(kn))
        self._blase = blase
        blase.zeigen()
        print(f"Examination opened, {len(typen)} scan types available: {', '.join(typen)}")

    def _blase_geschlossen(self, knopf):
        self._blase = None
        self._blase_zu = (knopf, time.monotonic())

    def _pikto_knoepfe(self, typen):
        knoepfe = []
        for typ_label, pfad in typen.items():
            pikto = QToolButton()
            pikto.setObjectName("pikto_knopf")
            pikto.setIconSize(QSize(k.PIKTO_ICON, k.PIKTO_ICON))
            pikto.setFixedSize(k.PIKTO_GROESSE, k.PIKTO_GROESSE)
            pikto.setToolTip(typ_label)
            if typ_label.startswith("vermessen"):
                pikto.setIcon(QIcon(str(k.ICON_ORDNER / "vermessen.svg")))
                aktion = lambda pf=pfad: self._vermessung_anzeigen(pf)
            else:
                pikto.setIcon(QIcon(str(k.ICON_ORDNER / k.ICON_ZU_LABEL.get(typ_label, "hand.svg"))))
                aktion = lambda pf=pfad: self._scan_laden_aus_pfad(pf)
            pikto.clicked.connect(lambda _, a=aktion: self._aus_blase_laden(a))
            knoepfe.append(pikto)
        return knoepfe

    def _aus_blase_laden(self, aktion):
        # Erst die Blase weg, DANN laden: das Laden blockiert die Oberflaeche
        # eine Weile, und so lange soll keine Blase mehr herumstehen.
        if self._blase is not None:
            self._blase.close()
        QTimer.singleShot(0, aktion)

    def _patient_toggle(self, widgets):
        """widgets[0] ist der Untersuchungs-Container, der Rest (z.B. der
        Genesungsverlauf-Knopf) klappt mit ihm auf und zu."""
        # anderen offenen Patienten zuklappen
        if self._offener_patient is not None and self._offener_patient is not widgets:
            for w in self._offener_patient:
                w.setVisible(False)
        oeffnen = not widgets[0].isVisible()
        for w in widgets:
            w.setVisible(oeffnen)
        self._offener_patient = widgets if oeffnen else None
        self._offener_patient_name = next(
            (n for n, w in self._patient_aufklapp_widgets.items() if w is self._offener_patient), None)
        self._patienten_beobachten()
        if oeffnen:
            # Was sich getan hat, waehrend der Patient zu (= unbeobachtet) war
            self._waechter_timer.start()
            print(f"Patient {self._offener_patient_name} expanded")
        else:
            print("Patient collapsed")

    def _untersuchung_menue(self, knopf, pos, patient_ordner, basis, typen):
        menue = QMenu(knopf)
        menue.addAction("Angaben bearbeiten …",
                        lambda: self.untersuchung_bearbeiten(patient_ordner, basis, typen))
        menue.exec(knopf.mapToGlobal(pos))

    def untersuchung_bearbeiten(self, patient_ordner, basis, typen):
        """Nummer / Zeit nach OP nachtragen oder aendern - auch fuer Scans,
        die angelegt wurden, bevor es diese Angaben gab."""
        meta = self._untersuchung_meta(typen)
        if "nummer" not in meta:
            # Vorschlag: naechste freie Nummer
            meta = {**meta, "nummer": self._naechste_nummer(patient_ordner)}
        dialog = UntersuchungDialog(
            self, f"Untersuchung bearbeiten – {basis}", meta,
            lambda nummer, _: self._nummer_pruefen(patient_ordner, nummer, ausser_basis=basis))
        if dialog.exec() != QDialog.Accepted:
            print("Editing the examination data was cancelled")
            return
        try:
            self._meta_schreiben(self._meta_ordner(typen), dialog.meta())
        except OSError as e:
            QMessageBox.warning(self, "Untersuchung bearbeiten", f"Speichern fehlgeschlagen:\n{e}")
            print(f"Writing the examination data failed {e}")
            return
        print(f"Examination data of {basis} updated")
        self._nav_aktualisieren()

    def _naechste_nummer(self, patient_ordner):
        nummern = [self._untersuchung_meta(t).get("nummer") or 0
                   for t in self._untersuchungen_sammeln(patient_ordner).values()]
        return max(nummern, default=0) + 1


    def _vermessung_anzeigen(self, pfad):
        """Vermessenen Scan laden und, falls vorhanden, die Ergebnisliste zeigen."""
        self._scan_laden_aus_pfad(pfad)
        liste = self._vermessungs_liste_finden(Path(pfad))
        if liste is None:
            print("No result list found next to this measured scan")
            return
        self._ergebnis_liste_zeigen(liste)

    def _vermessungs_liste_finden(self, scan_ordner):
        # schreibe_ergebnis_liste() legt die Liste neben den Scan-Ordner
        # (direkt in 'vermessene_scans'); im Ordner selbst nur als Rueckfall.
        for kandidat in (scan_ordner.parent / f"{scan_ordner.name}.xlsx",
                         scan_ordner / f"{scan_ordner.name}.xlsx"):
            if kandidat.is_file():
                return kandidat
        return None

    def _ergebnis_liste_zeigen(self, xlsx_pfad):
        """Zeigt die Excel-Liste in einem Nebenfenster."""
        try:
            from openpyxl import load_workbook
        except ImportError:
            # ohne openpyxl wenigstens im Standardprogramm oeffnen
            print("openpyxl is not installed, opening the result list in the default program instead")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(xlsx_pfad)))
            return

        blatt = load_workbook(xlsx_pfad, read_only=True, data_only=True).active
        zeilen = [["" if w is None else str(w) for w in zeile]
                  for zeile in blatt.iter_rows(values_only=True)]

        fenster, layout = self._neben_fenster(xlsx_pfad.stem)

        tabelle = QTableWidget(len(zeilen), max((len(z) for z in zeilen), default=0))
        tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        tabelle.horizontalHeader().setVisible(False)
        tabelle.verticalHeader().setVisible(False)
        for r, zeile in enumerate(zeilen):
            for c, wert in enumerate(zeile):
                tabelle.setItem(r, c, QTableWidgetItem(wert))
        tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(tabelle)

        oeffnen = QPushButton("In Excel öffnen")
        oeffnen.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(xlsx_pfad))))
        layout.addWidget(oeffnen)

        fenster.resize(420, 320)
        fenster.show()
        print(f"Result list {xlsx_pfad.name} shown with {len(zeilen)} rows")

    def _bild_zeigen(self, png_pfad):
        """Zeigt ein gespeichertes Bild (2D-Heatmap) in einem Nebenfenster."""
        bild = QPixmap(str(png_pfad))
        if bild.isNull():
            self.hinweis_label.setText(f"Bild konnte nicht geladen werden:\n{png_pfad}")
            print(f"Image could not be loaded from {png_pfad}")
            return

        fenster, layout = self._neben_fenster(Path(png_pfad).parent.parent.name + " - 2D-Heatmap")
        anzeige = QLabel()
        anzeige.setAlignment(Qt.AlignCenter)
        # matplotlib speichert mit 150 dpi - fuer den Bildschirm verkleinern
        anzeige.setPixmap(bild.scaled(QSize(700, 800), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(anzeige)

        oeffnen = QPushButton("Im Bildbetrachter öffnen")
        oeffnen.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(png_pfad))))
        layout.addWidget(oeffnen)

        fenster.adjustSize()
        fenster.show()
        print(f"Image {Path(png_pfad).name} shown next to the viewer")

    def _neben_fenster(self, titel):
        """Nicht-modales Fenster neben dem Viewer (Excel-Liste, Heatmap), damit
        man den Scan daneben weiter drehen kann. Es gibt immer nur eins - ein
        altes wird geschlossen, sonst stapeln sie sich bei jedem Klick."""
        if getattr(self, "_aktuelles_neben_fenster", None) is not None:
            self._aktuelles_neben_fenster.close()

        fenster = QDialog(self)
        fenster.setWindowTitle(titel)
        fenster.setAttribute(Qt.WA_DeleteOnClose)
        self._aktuelles_neben_fenster = fenster
        # Das Loeschen passiert verzoegert - nur zuruecksetzen, wenn noch
        # kein neueres Fenster eingetragen ist.
        fenster.destroyed.connect(lambda _=None, f=fenster: self._neben_fenster_weg(f))
        return fenster, QVBoxLayout(fenster)

    def _neben_fenster_weg(self, fenster):
        if getattr(self, "_aktuelles_neben_fenster", None) is fenster:
            self._aktuelles_neben_fenster = None

    def _scan_laden_aus_pfad(self, pfad):
        ordner = Path(pfad)
        if not ordner.is_dir():
            self.hinweis_label.setText("Scan-Ordner existiert nicht mehr.")
            print(f"Scan folder does not exist anymore: {ordner}")
            return
        self.aktueller_ordner = ordner
        print(f"Loading scan from {ordner}")
        self.lade_und_zeige(ordner)

    # ---------- Finger isolieren ----------

    def isolieren_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Finger isolation needs a loaded scan")
            return
        print("Finger isolation started, choose automatic or manual settings")
        self.zeige_basis_mesh_neu()
        self.button_automatisch.setVisible(True)
        self.button_manuell.setVisible(True)
        self.isolieren_wahl_container.setVisible(True)
        self.haupt_buttons_container.setVisible(False)
        self.navigatecontainer.setVisible(True)

    def automatisch_klick(self):
        self.zeige_basis_mesh_neu()
        self.button_automatisch.setVisible(False)
        self.button_manuell.setVisible(False)
        self.navigatecontainer.setVisible(True)
        ordner = Path(self.aktueller_ordner)
        gespeichert = lade_isolate_finger_parameter(ordner)

        if gespeichert:
            print(f"Automatic isolation, using the parameters saved for this patient: {gespeichert}")
            self.isolieren_ablauf = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=False, **gespeichert)
        else:
            print("Automatic isolation, no parameters saved yet for this patient, using the defaults")
            self.isolieren_ablauf = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=False)

        self.automatisch_modus_aktiv = True
        self.button_weiter.setText("Fertig markiert")
        self.button_weiter.setVisible(True)
        next(self.isolieren_ablauf)
        print("Right click the hurt fingertip, then the neighbouring fingertip")

    def manuell_klick(self):
        self.button_automatisch.setVisible(False)
        self.button_manuell.setVisible(False)
        ordner = Path(self.aktueller_ordner)
        self.isolieren_ablauf = isolate_finger(str(ordner), plotter=self.plotter, zeige_zwischenschritte=True)
        self.isolieren_phase = "picking"
        self.button_weiter.setVisible(True)
        self.navigatecontainer.setVisible(True)
        next(self.isolieren_ablauf)
        print("Manual isolation started, right click the hurt fingertip, then the neighbouring fingertip")

    def weiter_klick(self):
        self.navigatecontainer.setVisible(False)
        if getattr(self, "automatisch_modus_aktiv", False):
            self.automatisch_modus_aktiv = False
            self.button_weiter.setText("Weiter")
            self.button_weiter.setVisible(False)
            print("Isolating the finger, this takes a moment")
            try:
                gespeicherter_obj_pfad = generator_bis_ende(self.isolieren_ablauf)
                self.aktueller_ordner = Path(gespeicherter_obj_pfad)
            except Exception as e:
                self.hinweis_label.setText(f"Fehler: {e}")
                print(f"Isolating the finger failed: {e}")
                self.isolieren_wahl_container.setVisible(False)
                self.haupt_buttons_container.setVisible(True)
                return
            self.isolieren_wahl_container.setVisible(False)
            self.haupt_buttons_container.setVisible(True)
            print(f"Isolated finger saved in {gespeicherter_obj_pfad}")
            self.lade_und_zeige(Path(gespeicherter_obj_pfad))
            return

        if getattr(self, "isolieren_phase", None) == "picking":
            self.isolieren_phase = "ellipsoid"
            self.button_weiter.setVisible(False)
            self.ellipsoid_kontext = next(self.isolieren_ablauf)
            self.ellipsoid_einstellen_container.setVisible(True)
            self.aktualisiere_ellipsoid_vorschau()
            print("Fingertips accepted, now adjust the cutting ellipsoid with the sliders")
            return

        try:
            next(self.isolieren_ablauf)
        except StopIteration:
            self.button_weiter.setVisible(False)
            self.isolieren_wahl_container.setVisible(False)
            self.haupt_buttons_container.setVisible(True)
            print("Isolation workflow finished")

    def aktualisiere_ellipsoid_vorschau(self):
        if self.aktueller_ellipsoid_actor is not None:
            self.plotter.remove_actor(self.aktueller_ellipsoid_actor, reset_camera=False)

        radius_faktor = self.slider_radius.value() / 100
        laengen_faktor = self.slider_laenge.value() / 100
        unterschreitung = self.slider_unterschreitung.value() / 100
        pca_radius = float(self.slider_pca_radius.value())
        self.label_radius.setText(f"Breite: {radius_faktor:.2f}")
        self.label_laenge.setText(f"Länge: {laengen_faktor:.2f}")
        self.label_unterschreitung.setText(f"Unterschreitung: {unterschreitung:.2f}")

        if pca_radius != self.ellipsoid_kontext.get("pca_radius"):
            #Der Kantengraph kommt fertig aus der Pipeline, die Neuberechnung
            #kostet damit nur wenige Millisekunden - das darf am Regler haengen.
            normale, verwendete_vertices, avg_point_of_hurt_finger = finger_normale(
                self.ellipsoid_kontext["hand_ausgerichtet"],
                self.ellipsoid_kontext["hurt_finger"],
                pca_radius,
                self.ellipsoid_kontext["kantengraph"],
            )
            self.ellipsoid_kontext["normale"] = normale
            self.ellipsoid_kontext["verwendete_vertices"] = verwendete_vertices
            self.ellipsoid_kontext["avg_point_of_hurt_finger"] = avg_point_of_hurt_finger
            self.ellipsoid_kontext["pca_radius"] = pca_radius
            print(f"PCA radius set to {pca_radius:.0f} mm, {len(verwendete_vertices)} points used for the finger normal")

        self.label_pca_radius.setText(
            f"Achsen-Radius: {pca_radius:.0f} mm "
            f"({len(self.ellipsoid_kontext['verwendete_vertices'])} Punkte)"
        )

        ellipsoid = erstelle_schnitt_ellipsoid(
            self.ellipsoid_kontext["avg_point_of_hurt_finger"],
            self.ellipsoid_kontext["normale"],
            self.ellipsoid_kontext["verwendete_vertices"],
            self.ellipsoid_kontext["tiefster_punkt"],
            radius_faktor=radius_faktor, laengen_faktor=laengen_faktor, unterschreitung=unterschreitung,
        )
        self.aktueller_ellipsoid_actor = self.plotter.add_mesh(ellipsoid, color="darkcyan", opacity=0.3)
        self.plotter.render()

    def ellipsoid_bestaetigen_klick(self):
        werte = {
            "radius_faktor": self.slider_radius.value() / 100,
            "laengen_faktor": self.slider_laenge.value() / 100,
            "unterschreitung": self.slider_unterschreitung.value() / 100,
            "pca_radius": float(self.slider_pca_radius.value()),
        }
        ordner = Path(self.aktueller_ordner)
        self.ellipsoid_einstellen_container.setVisible(False)
        self.navigatecontainer.setVisible(False)
        speichere_isolate_finger_parameter(ordner, **werte)
        print(f"Ellipsoid confirmed and saved for the next isolation of this patient: {werte}")
        print("Cutting the finger out, this takes a moment")

        try:
            self.isolieren_ablauf.send(werte)
            self.hinweis_label.setText("Unerwarteter weiterer Zwischenschritt - bitte melden.")
            print("Unexpected extra step in the isolation workflow, nothing was saved")
            return
        except StopIteration as e:
            gespeicherter_obj_pfad = e.value

        self.aktueller_ordner = Path(gespeicherter_obj_pfad)
        self.isolieren_phase = None
        self.isolieren_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(True)

        print(f"Isolated finger saved in {gespeicherter_obj_pfad}")
        self.lade_und_zeige(Path(gespeicherter_obj_pfad))

    # ---------- Zeichnen ----------

    def setze_zeichnungs_status_zurueck(self):
        # Sonst bleibt nach einem abgebrochenen (nicht geschlossenen) Strich
        # das Ergebnis des vorherigen Zeichenvorgangs stehen
        #Liste, weil mehrere Bereiche auf einmal eingekreist sein koennen.
        #Nach Groesse sortiert, der erste Eintrag ist Bereich 1.
        self.zeichnungs_status["flaeche"] = []
        self.zeichnungs_status["landmarken"] = None
        self.zeichnungs_status["punkte_eingezeichnet"] = None

    def zeichnen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Drawing an area needs a loaded scan")
            return
        print("Drawing started, right click to set points and close the loop on the first point")
        self.setze_zeichnungs_status_zurueck()
        self.navigatecontainer.setVisible(True)
        self.haupt_buttons_container.setVisible(False)
        self.malen_wahl_container.setVisible(True)
        self.button_weiter_malen.setVisible(True)
        self.gezeichnete_flaeche = draw_main(str(self.aktueller_ordner), self.plotter, self.zeichnungs_status)

    def weiter_klick_malen(self):
        if not self.zeichnungs_status["flaeche"]:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet!")
            print("No area drawn yet, nothing to continue with")
            return

        messwerte = self._messwerte_je_bereich()
        print(f"{len(messwerte)} area(s) drawn")
        for m in messwerte:
            print(f"   Area {m['nummer']}: {m['flaeche_mm2']:.1f} mm² surface, {m['umfang_mm']:.1f} mm perimeter")
        if len(messwerte) == 1:
            m = messwerte[0]
            self.hinweis_label.setText(
                f"Fläche: {m['flaeche_mm2']:.1f} mm² | Umfang: {m['umfang_mm']:.1f} mm")
        else:
            teile = "  ".join(f"{m['nummer']}: {m['flaeche_mm2']:.0f} mm²" for m in messwerte)
            self.hinweis_label.setText(f"{len(messwerte)} Bereiche  |  {teile}")
        self.malen_wahl_container.setVisible(False)

        # Nur noch der Einzeichnen-Weg landet hier; das Vermessen laeuft
        # ueber vermessungen_speichern_klick().
        self.haupt_buttons_container.setVisible(False)
        self.farbe_wahl_container.setVisible(True)
        self.navigatecontainer.setVisible(True)

    def _heatmap_moeglich(self):
        #Die Heatmaps rechnen noch mit genau einer Flaeche je Scan. Solange
        #das so ist, wird bei mehreren eingekreisten Bereichen abgelehnt
        anzahl = bereiche_in_markierung(Path(self.aktueller_ordner))
        if anzahl > 1:
            self.hinweis_label.setText(
                f"Die Markierung hat {anzahl} getrennte Bereiche. Die Heatmap kann "
                "bisher nur einen verarbeiten, das kommt spaeter, falls nötig.")
            print(f"Heatmap refused, the saved marking has {anzahl} separate areas and only one is supported so far")
            return False
        return True

    def _messwerte_je_bereich(self):
        #Flaeche und Umfang je eingekreistem Bereich, durchnummeriert.
        #Die Liste ist schon nach Groesse sortiert, Bereich 1 ist der
        #groesste.
        messwerte = []
        for nummer, flaeche in enumerate(self.zeichnungs_status["flaeche"], start=1):
            flaecheninhalt, umfang = berechne_flaeche_und_umfang(
                flaeche, self.zeichnungs_status["punkte_eingezeichnet"])
            messwerte.append({"nummer": nummer, "flaeche": flaeche,
                              "flaeche_mm2": flaecheninhalt, "umfang_mm": umfang})
        return messwerte

    def _schreibe_markierungs_liste(self, gespeicherter_pfad):
        #Excel-Liste neben das gespeicherte OBJ, also in den
        #markierte_scans-Unterordner des Scans. 
        if gespeicherter_pfad is None:
            print("The marking was not saved, so no result list was written")
            return
        ordner = Path(gespeicherter_pfad).parent
        liste_pfad = schreibe_ergebnis_liste(self._messwerte_je_bereich(), ordner, ordner.name)
        if liste_pfad is None:
            print("Result list skipped, openpyxl is not installed")
        else:
            print(f"Result list of the marked areas written to {liste_pfad}")

    def farbenwahl(self, farbe: str):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Kein Scan geladen.")
            print("Saving the marked area needs a loaded scan")
            return
        if not self.zeichnungs_status["flaeche"]:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet")
            print("No area drawn yet, nothing to save")
            return

        #Alle Bereiche in ein Mesh, das OBJ bleibt damit eine Datei
        gesamt = self.zeichnungs_status["flaeche"][0]
        for weiteres in self.zeichnungs_status["flaeche"][1:]:
            gesamt = gesamt.merge(weiteres)

        print(f"Saving {len(self.zeichnungs_status['flaeche'])} marked area(s) in color {farbe}")
        gespeichert = save_drawn_area(gesamt, Path(self.aktueller_ordner), farbe,
                                      self.zeichnungs_status["landmarken"])
        print(f"Marked scan saved in {gespeichert}")
        self._schreibe_markierungs_liste(gespeichert)
        self.lade_und_zeige(Path(self.aktueller_ordner))
        self.farbe_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(True)
        self.navigatecontainer.setVisible(False)

    def stift_einzeichnen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Pen detection needs a loaded scan")
            return

        # Nur am isolierten Finger: dort liegt die gesamte Textur, die
        # ueberhaupt abgetastet wird, auf dem Finger selbst - Nachbar-
        # finger und Hintergrund koennen gar nicht hineingeraten.
        if not self._ist_isolierter_finger():
            self.hinweis_label.setText(
                "Diese Funktion funktioniert nur am isolierten Finger. Bitte erst 'Finger isolieren' "
                "(Punkt 4 der Anleitung).")
            print("Pen detection only works on an isolated finger, isolate it first")
            return

        self.setze_zeichnungs_status_zurueck()
        print("Looking for the black pen stroke, the viewer takes pictures from all sides and is locked while it does")
        self.hinweis_label.setText("Markierung wird gesucht ...")
        QApplication.processEvents()

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            flaechen, bericht = markiere_strich(
                self.plotter, self.aktuelle_teile,
                diagnose_ordner=k.ANSICHT_DIAGNOSE_ORDNER)
        finally:
            QApplication.restoreOverrideCursor()

        print(f"{bericht.get('gesehen', 0)} of {bericht.get('faces', 0)} faces were visible in the views, "
              f"{bericht.get('strich', 0)} of them look like the pen stroke")
        if not flaechen:
            self.hinweis_label.setText(
                "Kein Strich gefunden. Die Ansichten liegen zum Nachsehen in "
                f"{k.ANSICHT_DIAGNOSE_ORDNER}.")
            print(f"No stroke found, the recorded views are in {k.ANSICHT_DIAGNOSE_ORDNER} for checking")
            return

        self.zeichnungs_status["flaeche"] = flaechen
        self.zeichnungs_status["landmarken"] = {}
        self.zeichnungs_status["punkte_eingezeichnet"] = None

        #Jeden Bereich einzeln einfaerben, damit man sie auseinanderhalten
        #kann. Die Reihenfolge entspricht der Nummerierung in der Liste.
        for nummer, flaeche in enumerate(flaechen):
            farbe = k.BEREICH_FARBEN[nummer % len(k.BEREICH_FARBEN)]
            self.plotter.add_mesh(flaeche, color=farbe, opacity=0.5)
            print(f"   Area {nummer + 1} shown in {farbe}")
        self.plotter.render()

        messwerte = self._messwerte_je_bereich()
        print(f"{len(messwerte)} area(s) found, sorted by size, area 1 is the biggest")
        for m in messwerte:
            print(f"   Area {m['nummer']}: {m['flaeche_mm2']:.1f} mm² surface, {m['umfang_mm']:.1f} mm perimeter")
        teile_text = "  ".join(f"{m['nummer']}: {m['flaeche_mm2']:.0f} mm²" for m in messwerte)
        self.hinweis_label.setText(
            f"{len(messwerte)} Bereich(e) erkannt.  {teile_text}.  Jetzt die Farbe waehlen.")

        self.malen_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(False)
        self.farbe_wahl_container.setVisible(True)

    def automatisch_einzeichnen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Automatic drawing needs a loaded scan")
            return

        self.setze_zeichnungs_status_zurueck()

        print(f"Looking for the color {self.einzeichnen_farbwahl.farbe} on the scan texture")
        markierte_punkte = finde_markierungs_punkte(
            self.aktuelle_teile, hex_code=self.einzeichnen_farbwahl.farbe, toleranz=100.0)
        if len(markierte_punkte) < 3:
            self.hinweis_label.setText("Keine ausreichende Markierung auf dem Scan gefunden.")
            print(f"Only {len(markierte_punkte)} points match that color, at least 3 are needed")
            return

        print(f"{len(markierte_punkte)} points match that color")
        markierte_punkte = entferne_ausreisser_punkte(markierte_punkte)
        pfad = baue_geschlossenen_pfad(markierte_punkte)
        print(f"{len(markierte_punkte)} points left after dropping the outliers, path closed over {len(pfad)} points")

        flaeche = schneide_flaeche_aus_loop(self.aktuelles_hand_mesh, pfad)
        if flaeche is None:
            self.hinweis_label.setText("Markierung konnte nicht auf dem Scan geschlossen werden.")
            print("The marking could not be closed into an area on the scan")
            return

        print(f"Area cut out of the scan, {flaeche.n_cells} faces, now choose the color")

        self.zeichnungs_status["flaeche"] = flaeche
        self.zeichnungs_status["landmarken"] = {}
        self.zeichnungs_status["punkte_eingezeichnet"] = pfad
        self.malen_wahl_container.setVisible(False)
        self.haupt_buttons_container.setVisible(False)
        self.farbe_wahl_container.setVisible(True)

    def bereich_vermessen_start(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Measuring areas needs a loaded scan")
            return
        print("Measuring areas started, draw as many areas as needed and close every loop")
        self.setze_zeichnungs_status_zurueck()
        self.vermessungen.clear()
        self.zeige_basis_mesh_neu()
        self.vermessung_wahl_container.setVisible(False)
        self.vermessen_malen_container.setVisible(True)
        self._anteil_checkbox_vorbereiten()
        self.hinweis_label.setText(
            "Fläche einzeichnen und Schleife schließen. Beliebig viele nacheinander.")
        draw_main(str(self.aktueller_ordner), self.plotter, self.zeichnungs_status,
                  bei_flaeche_fertig=self.flaeche_fertig_gemalt)
        self.navigatecontainer.setVisible(True)

    def _ist_isolierter_finger(self):
        """Ist der geladene Scan ein isolierter Finger? Nur dann gibt es die
        Zwischenfingerfalte bei Z = 0 als Bezug.

        Entscheidend ist der Ordner: Ein ganzer Hand-Scan reicht ebenfalls ueber
        Z = 0 hinweg, die Mesh-Ausdehnung allein wuerde ihn also durchwinken und
        als Bezugsflaeche die halbe Hand liefern."""
        if self.aktueller_ordner is None or self.aktuelles_hand_mesh is None:
            return False
        pfad = Path(self.aktueller_ordner)
        ordner = pfad.parent if pfad.is_file() else pfad
        if "_isoliert" not in ordner.name and ordner.parent.name != "isolierte_scans":
            return False
        # Zusaetzlich: ausgerichtet, also Falte bei Z = 0 und Finger darueber
        bounds = self.aktuelles_hand_mesh.bounds
        return bounds[4] <= 0 <= bounds[5]

    def _anteil_checkbox_vorbereiten(self):
        moeglich = self._ist_isolierter_finger()
        if moeglich:
            print("Isolated and aligned finger, the share of the finger surface can be calculated")
        else:
            print("Not an isolated finger, the share of the finger surface stays switched off")
        self.checkbox_anteil.setEnabled(moeglich)
        self.checkbox_anteil.setChecked(moeglich)
        self.checkbox_anteil.setToolTip(
            k.ANTEIL_CHECKBOX_HILFE if moeglich else k.ANTEIL_CHECKBOX_GESPERRT)

    # ---------- Mehrfach-Vermessung ----------

    def flaeche_fertig_gemalt(self, flaeche):
        # Wird aus dem Picking-Callback aufgerufen, sobald eine Schleife
        # geschlossen wurde. Danach ist sofort die naechste Flaeche dran.
        flaecheninhalt, umfang = berechne_flaeche_und_umfang(flaeche)
        nummer = len(self.vermessungen) + 1

        actor = self.plotter.add_mesh(
            flaeche, color="red", opacity=1, name=f"vermessung_{nummer}")

        zahl = baue_zahl_fuer_messung(
            flaeche, self.aktuelles_hand_mesh, nummer, flaecheninhalt)
        zahl_actor = self.plotter.add_mesh(
            zahl, color="white", name=f"vermessung_zahl_{nummer}")

        self.vermessungen.append({
            "flaeche": flaeche,
            "flaeche_mm2": flaecheninhalt,
            "umfang_mm": umfang,
            "actor": actor,
            "zahl_actor": zahl_actor,
        })
        print(f"Area {nummer} closed: {flaecheninhalt:.1f} mm² surface, {umfang:.1f} mm perimeter")
        self.zeige_messergebnisse()

    def zeige_messergebnisse(self):
        if not self.vermessungen:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet!")
            return

        zeilen = [f"{len(self.vermessungen)} Fläche(n) gemessen"]
        for nummer, messung in enumerate(self.vermessungen, start=1):
            zeilen.append(
                f"{nummer}: {messung['flaeche_mm2']:.1f} mm²  |  {messung['umfang_mm']:.1f} mm")
        self.hinweis_label.setText("\n".join(zeilen))

    def letzte_flaeche_zuruecknehmen(self):
        if not self.vermessungen:
            self.hinweis_label.setText("Es gibt nichts zurückzunehmen.")
            print("Nothing to take back, no area measured yet")
            return

        messung = self.vermessungen.pop()
        print(f"Area {len(self.vermessungen) + 1} taken back, {len(self.vermessungen)} left")
        for actor in (messung["actor"], messung["zahl_actor"]):
            if actor is not None:
                self.plotter.remove_actor(actor, reset_camera=False)
        self.plotter.render()
        self.zeige_messergebnisse()

    def vermessungen_speichern_klick(self):
        if not self.vermessungen:
            self.hinweis_label.setText("Noch keine Fläche gezeichnet!")
            print("No area measured yet, nothing to save")
            return

        self.plotter.disable_picking()
        scan_ordner = Path(self.aktueller_ordner)

        print(f"Saving {len(self.vermessungen)} measurement(s) for {scan_ordner.name}")
        try:
            obj_pfad = speichere_vermessung(
                self.aktuelle_teile, self.aktuelles_hand_mesh, self.vermessungen, scan_ordner)
        except Exception as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            print(f"Saving the measured scan failed: {e}")
            return

        print(f"Measured scan saved in {obj_pfad.parent}")

        # Bezugsflaeche fuer den Prozentwert. Schlaegt das fehl, wird die Liste
        # trotzdem geschrieben - der OBJ-Export ist schon durch, ein Abbruch
        # wuerde nur die Messung kosten.
        finger_flaeche = None
        anteil_fehler = ""
        if self.checkbox_anteil.isChecked():
            try:
                finger_flaeche = flaeche_ab_fingerzwischenfalte(self.aktuelles_hand_mesh)
                # Nur der Teil einer Markierung, der ueber der Falte liegt, gehoert
                # zur Bezugsflaeche - sonst koennte der Anteil ueber 100 % steigen
                for messung in self.vermessungen:
                    messung["flaeche_anteil_mm2"] = flaeche_oberhalb_falte(messung["flaeche"])
                print(f"Finger surface above the web between the fingers: {finger_flaeche:.1f} mm²")
            except Exception as e:
                finger_flaeche = None
                anteil_fehler = f"\nAnteil nicht berechenbar: {e}"
                print(f"The share of the finger surface could not be calculated, the list is written anyway: {e}")

        ziel_ordner, ziel_name = vermessungs_ordner(scan_ordner)
        # Die Ergebnisliste liegt eine Ebene ueber dem Scan-Ordner, also
        # direkt in 'vermessene_scans'.
        liste_pfad = schreibe_ergebnis_liste(self.vermessungen, ziel_ordner.parent, ziel_name,
                                             finger_flaeche_mm2=finger_flaeche)
        if liste_pfad is None:
            print("Result list skipped, openpyxl is not installed")
        else:
            print(f"Result list written to {liste_pfad}")

        if finger_flaeche:
            gezaehlt = sum(m["flaeche_anteil_mm2"] for m in self.vermessungen)
            gemalt = sum(m["flaeche_mm2"] for m in self.vermessungen)
            print(f"Marked {gezaehlt / finger_flaeche * 100:.1f} % of the finger surface above the web")
            anteil_text = f"\nMarkiert: {gezaehlt / finger_flaeche * 100:.1f} % der Fingerfläche ab Zwischenfingerfalte"
            if gemalt - gezaehlt > 0.5:
                anteil_text += f" ({gemalt - gezaehlt:.1f} mm² liegen darunter und zählen nicht mit)"
        else:
            anteil_text = anteil_fehler

        if liste_pfad is None:
            self.hinweis_label.setText(
                f"Gespeichert unter {obj_pfad.parent}{anteil_text}\n"
                "Excel-Liste übersprungen - openpyxl ist nicht installiert.")
        else:
            self.hinweis_label.setText(
                f"{len(self.vermessungen)} Messung(en) gespeichert{anteil_text}\n"
                f"Scan: {obj_pfad.parent}\n"
                f"Liste: {liste_pfad}")

        self.vermessen_malen_container.setVisible(False)
        self.lade_main_menu()

    # ---------- Vermessen ----------

    def vermessen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Measuring needs a loaded scan")
            return
        print("Measuring menu opened")
        self.haupt_buttons_container.setVisible(False)
        self.vermessung_wahl_container.setVisible(True)
        self.navigatecontainer.setVisible(True)

    def strecke_messen_klick(self):
        self.zeige_basis_mesh_neu()
        self.plotter.disable_picking()
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(True)
        self.hinweis_label.setText("2x rechtsklicken: Start- und Endpunkt der Strecke.")
        print("Distance measuring started, right click the start point and the end point")

        hand_mesh = self.aktuelles_hand_mesh
        punkte_indices = []

        def punkt_geklickt(punkt, picker):
            punkte_indices.append(hand_mesh.find_closest_point(punkt))
            if len(punkte_indices) == 2:
                self.plotter.disable_picking()
                pfad = hand_mesh.geodesic(punkte_indices[0], punkte_indices[1])
                distanz = np.linalg.norm(np.diff(pfad.points, axis=0), axis=1).sum()
                self.hinweis_label.setText(f"Strecke auf der Oberfläche: {distanz:.1f} mm")
                print(f"Distance along the surface: {distanz:.1f} mm over {pfad.n_points} path points")
                self.navigatecontainer.setVisible(False)
                self.haupt_buttons_container.setVisible(True)

        self.plotter.enable_point_picking(callback=punkt_geklickt, 
                                          tolerance = 0.01,  
                                          use_picker=True, 
                                          show_point=True, 
                                          color="red", 
                                          point_size=20)

    def volumen_messen_klick(self):
        print("Volume menu opened")
        self.volumen_container.setVisible(True)
        self.vermessung_wahl_container.setVisible(False)
        self.navigatecontainer.setVisible(True)

    def volumen_ganzes_mesh_messen_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Measuring the volume needs a loaded scan")
            return
        elif "iso" not in str(self.aktueller_ordner):
            self.hinweis_label.setText("Erst den Finger isolieren")
            print("Measuring the volume only works on an isolated finger, isolate it first")
            return
        
        volumen = volumen_gesamtes_mesh(self.aktuelles_hand_mesh)
        self.hinweis_label.setText(f"Volumen des gesamten Mesh: {volumen:.1f} mm³")
        print(f"Volume of the whole mesh: {volumen:.1f} mm³")

    def volumen_alles_ueber_markierung(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Measuring the volume needs a loaded scan")
            return
        print(f"Looking for the color {self.markierung_farbwahl.farbe} to cut the finger at")
        try:
            volumen, schnitt_hoehe, anzahl_markiert = volumen_ab_markierung(
                self.aktuelles_hand_mesh, self.aktuelle_teile, hex_code=self.markierung_farbwahl.farbe)
        except ValueError as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            print(f"Volume above the marking could not be measured: {e}")
            return

        bounds = self.aktuelles_hand_mesh.bounds
        mitte_x = (bounds[0] + bounds[1]) / 2
        mitte_y = (bounds[2] + bounds[3]) / 2
        breite = (bounds[1] - bounds[0]) * 1.5
        tiefe = (bounds[3] - bounds[2]) * 1.5
        ebene = p_v.Plane(center=(mitte_x, mitte_y, schnitt_hoehe), direction=(0, 0, 1), i_size=breite, j_size=tiefe)
        self.plotter.add_mesh(ebene, color="yellow", opacity=0.35, name="schnitt_ebene")

        self.hinweis_label.setText(
            f"Volumen ab Markierung: {volumen:.1f} mm³ "
            f"(Schnitthöhe Z={schnitt_hoehe:.1f}, {anzahl_markiert} markierte Punkte gefunden)")
        print(f"Volume above the marking: {volumen:.1f} mm³, cut at Z={schnitt_hoehe:.1f} mm, "
              f"{anzahl_markiert} marked points found")

    def volumen_ueber_ring(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Measuring the volume needs a loaded scan")
            return
        print(f"Looking for the color {self.markierung_farbwahl.farbe} of the rubber ring")
        try:
            volumen, schwerpunkt, normale, anzahl_markiert = volumen_ab_ring(
                self.aktuelles_hand_mesh, self.aktuelle_teile, hex_code=self.markierung_farbwahl.farbe
            )
        except ValueError as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            print(f"Volume above the ring could not be measured: {e}")
            return

        bounds = self.aktuelles_hand_mesh.bounds
        diagonale = np.linalg.norm([bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]])
        ebene = p_v.Plane(center=schwerpunkt, direction=normale, i_size=diagonale, j_size=diagonale)
        self.plotter.add_mesh(ebene, color="yellow", opacity=0.35, name="schnitt_ebene")

        self.hinweis_label.setText(
            f"Volumen ab Ring: {volumen:.1f} mm³ ({anzahl_markiert} markierte Punkte gefunden)"
        )
        print(f"Volume above the ring: {volumen:.1f} mm³, {anzahl_markiert} points of the ring found")

    def volumen_ab_fingerzwischenfalte_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Measuring the volume needs a loaded scan")
            return
        if "iso" not in str(self.aktueller_ordner):
            self.hinweis_label.setText("Erst den Finger isolieren")
            print("This volume only works on an isolated finger, isolate it first")
            return

        try:
            volumen = volumen_ab_fingerzwischenfalte(self.aktuelles_hand_mesh)
        except ValueError as e:
            self.hinweis_label.setText(f"Fehler: {e}")
            print(f"Volume above the web between the fingers could not be measured: {e}")
            return

        bounds = self.aktuelles_hand_mesh.bounds
        mitte_x = (bounds[0] + bounds[1]) / 2
        mitte_y = (bounds[2] + bounds[3]) / 2
        breite = (bounds[1] - bounds[0]) * 1.5
        tiefe = (bounds[3] - bounds[2]) * 1.5
        ebene = p_v.Plane(center=(mitte_x, mitte_y, 0), direction=(0, 0, 1), i_size=breite, j_size=tiefe)
        self.plotter.add_mesh(ebene, color="yellow", opacity=0.35, name="schnitt_ebene")

        self.hinweis_label.setText(
            f"Volumen ab der Höhe der Fingerzwischenfalte: {volumen:.1f} mm³")
        print(f"Volume above the web between the fingers: {volumen:.1f} mm³")
        
    # ---------- Pipette & Overlay Buttons ----------

    def pipette_aktivieren(self, ziel_widget: FarbAuswahlWidget):
        self._pipette_aktiv = True
        self._pipette_ziel_widget = ziel_widget
        self.plotter.interactor.setCursor(Qt.CrossCursor)
        self.plotter.interactor.installEventFilter(self)
        self.hinweis_label.setText("Pipette aktiv - auf den Scan klicken, um eine Farbe aufzunehmen.")
        print("Color picker active, click on the scan to take a color")

    def _farbe_am_klick(self, x: int, y: int) -> tuple:
        # Bevorzugt die Textur: dazu muss der Klick erst auf das Mesh
        # abgebildet werden. Klappt das nicht (daneben geklickt, keine
        # Teile geladen), bleibt der alte Weg ueber den Screenshot - der
        # liefert dann zwar die beleuchtete Farbe, aber immerhin etwas.
        if self.aktuelle_teile:
            punkt = self._punkt_unter_maus(x, y)
            if punkt is not None:
                hex_code = textur_farbe_an_punkt(self.aktuelle_teile, punkt)
                if hex_code is not None:
                    print("Color read straight from the scan texture")
                    return hex_code, "aus der Textur"

        print("The click did not hit the mesh, reading the color from the screenshot instead")
        bild_array = self.plotter.screenshot(return_img=True)
        hoehe, breite = bild_array.shape[:2]
        r, g, b = bild_array[min(max(y, 0), hoehe - 1), min(max(x, 0), breite - 1)][:3]
        return f"#{r:02X}{g:02X}{b:02X}", "vom Bildschirm, bitte genauer treffen"

    def _punkt_unter_maus(self, x: int, y: int):
        # VTK zaehlt die Bildzeilen von UNTEN, Qt von oben - ohne das
        # Umdrehen greift die Pipette gespiegelt daneben.
        _, fenster_hoehe = self.plotter.render_window.GetSize()
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        picker.Pick(x, fenster_hoehe - 1 - y, 0, self.plotter.renderer)
        if picker.GetCellId() < 0:
            return None
        return np.array(picker.GetPickPosition())

    def eventFilter(self, obj, event):
        if obj is self.viewer_spalte and event.type() == QEvent.Resize:
            self._positioniere_overlay_buttons()                             
            return super().eventFilter(obj, event)   
    
        if getattr(self, "_pipette_aktiv", False) and obj is self.plotter.interactor and event.type() == QEvent.MouseButtonPress:
            self._pipette_aktiv = False
            self.plotter.interactor.unsetCursor()
            self.plotter.interactor.removeEventFilter(self)

            position = event.position().toPoint()
            skala = self.plotter.interactor.devicePixelRatioF()
            x, y = int(position.x() * skala), int(position.y() * skala)

            hex_code, quelle = self._farbe_am_klick(x, y)
            self._pipette_ziel_widget.setze_farbe(hex_code)
            self.hinweis_label.setText(f"Farbe aufgenommen: {hex_code} ({quelle})")
            print(f"Color picked: {hex_code}")
            return True
        return super().eventFilter(obj, event)


    #--- heatmap -----

    def heatmap_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("The 2D heatmap needs a loaded scan")
            return
        if not self._heatmap_moeglich():
            return
        print("Building the 2D heatmap from all marked scans of this patient")
        bild = heatmap_main(str(self.aktueller_ordner))
        if bild is None:
            self.hinweis_label.setText("Keine markierten Scans für diesen Patienten gefunden.")
            print("No marked scans found for this patient, nothing to compare")
            return
        print(f"2D heatmap saved as {bild}")
        self._bild_zeigen(bild)

        # Nav-Spalte neu aufbauen, damit der 2D-Knopf sofort auftaucht, und
        # den Patienten wieder aufklappen - sonst ist man ploetzlich raus.
        patient = Path(self.aktueller_ordner).parent.parent.name
        self.baum_neu_aufbauen()
        if patient in self._patient_aufklapp_widgets:
            self._patient_toggle(self._patient_aufklapp_widgets[patient])


    #--- Genesungsverlauf ---

    def genesungsverlauf_3d_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("The 3D recovery progress needs a loaded scan")
            return
        if not self._heatmap_moeglich():
            return

        scan_ordner = Path(self.aktueller_ordner)
        patienten_ordner = scan_ordner.parent.parent

        self.button_abbruch_overlay.setVisible(True)

        andere_eintraege = []
        aktueller_eintrag = None

        for obj_pfad in finde_markierte_scans(patienten_ordner):
            isolierter_name = isolierte_scan_name_aus_markierung(obj_pfad.parent.name)
            isolierter_pfad = patienten_ordner / "isolierte_scans" / isolierter_name
            if not isolierter_pfad.is_dir():
                print(f"Skipping {obj_pfad.name}, the matching isolated scan {isolierter_name} does not exist")
                continue

            eintrag = {"isolierter_pfad": isolierter_pfad, "markierungs_pfad": obj_pfad}
            if isolierter_pfad.resolve() == scan_ordner.resolve():
                aktueller_eintrag = eintrag   # das IST der aktuelle Scan - merken, nicht doppelt aufnehmen
            else:
                andere_eintraege.append(eintrag)

        if aktueller_eintrag is None:
            # Aktueller Scan hat selbst noch keine Markierung - trotzdem
            # als reiner Referenz-Eintrag noetig (kein markierungs_pfad)
            aktueller_eintrag = {"isolierter_pfad": scan_ordner, "markierungs_pfad": None}

        self.genesungsverlauf_warteschlange = [aktueller_eintrag] + andere_eintraege

        if len(self.genesungsverlauf_warteschlange) < 2 and aktueller_eintrag["markierungs_pfad"] is None:
            self.hinweis_label.setText("Keine markierten Untersuchungen für diesen Patienten gefunden.")
            print("No marked examinations found for this patient, nothing to build a progress from")
            return

        print(f"3D recovery progress started, {len(self.genesungsverlauf_warteschlange)} examination(s) in the queue")

        self.genesungsverlauf_index = 0
        self.genesungsverlauf_gewinner = {}
        self.genesungsverlauf_aktuell_rotiert = None
        self._genesungsverlauf_letzter_klick = None
        self._genesungsverlauf_naechsten_schritt_zeigen()

    def _genesungsverlauf_naechsten_schritt_zeigen(self):
        eintrag = self.genesungsverlauf_warteschlange[self.genesungsverlauf_index]
        ist_aktuell = eintrag["isolierter_pfad"].resolve() == Path(self.aktueller_ordner).resolve()

        if ist_aktuell:
            self._genesungsverlauf_mesh_fuer_klick = self.aktuelles_hand_mesh
            self.zeige_basis_mesh_neu()
        else:
            teile = load_teilmeshe_mit_textur(eintrag["isolierter_pfad"])
            self._genesungsverlauf_mesh_fuer_klick = p_v.merge([teil for teil, tex in teile])
            self.plotter.clear()
            self._rendere_teile(teile)
            self.plotter.reset_camera()

        self._genesungsverlauf_letzter_klick = None   
        print(f"Step {self.genesungsverlauf_index + 1} of {len(self.genesungsverlauf_warteschlange)}: "
              f"{eintrag['isolierter_pfad'].name} shown, right click the middle of the fingernail")
        self.hinweis_label.setText(
            f"Genesungsverlauf ({self.genesungsverlauf_index + 1}/{len(self.genesungsverlauf_warteschlange)}): "
            f"Fingernagel anklicken, dann 'Nächsten Finger markieren' zum Bestätigen."
        )
        self.button_naechster_finger_overlay.setVisible(True)
        self._positioniere_overlay_buttons()
        self._genesungsverlauf_picking_aktivieren()

    def _genesungsverlauf_picking_aktivieren(self):
        self.plotter.disable_picking()

        def nagel_geklickt(punkt, picker):
            self._genesungsverlauf_letzter_klick = np.array(punkt)   
            self.plotter.add_points(
                np.array([punkt]), color="yellow", point_size=15,
                render_points_as_spheres=True, name="genesungsverlauf_nagel_marker"  
            )

        self.plotter.enable_point_picking(
            callback=nagel_geklickt, 
            tolerance = 0.01,
            use_picker=True, 
            show_point=False 
        )

    def naechster_finger_markieren_klick(self):
        if not self.genesungsverlauf_warteschlange:
            return
        if self._genesungsverlauf_letzter_klick is None:
            self.hinweis_label.setText("Bitte zuerst den Fingernagel anklicken.")
            print("No fingernail clicked yet, click it before going on")
            return

        self.plotter.disable_picking()
        self._genesungsverlauf_nagel_verarbeiten(self._genesungsverlauf_letzter_klick)


    def _genesungsverlauf_nagel_verarbeiten(self, geklickter_punkt):
        eintrag = self.genesungsverlauf_warteschlange[self.genesungsverlauf_index]
        mesh = self._genesungsverlauf_mesh_fuer_klick
        ist_aktuell = eintrag["isolierter_pfad"].resolve() == Path(self.aktueller_ordner).resolve()
        print(f"Aligning step {self.genesungsverlauf_index + 1}, this is the loaded scan: {ist_aktuell}, "
              f"reference already rotated: {self.genesungsverlauf_aktuell_rotiert is not None}")
        normale = finde_nagel_normale(mesh, geklickter_punkt)
        R = rotationsmatrix_um_z_fuer_nagel_ausrichtung(normale)
        versatz = self._genesungsverlauf_hoehen_versatz(mesh)

        if ist_aktuell:
            rotierte_punkte = (R @ self.aktuelles_hand_mesh.points.T).T
            rotierte_punkte[:, 2] += versatz
            self.genesungsverlauf_aktuell_rotiert = self.aktuelles_hand_mesh.copy()
            self.genesungsverlauf_aktuell_rotiert.points = rotierte_punkte

        if eintrag["markierungs_pfad"] is not None:
            try:
                markierung_punkte = lade_markierung(eintrag["markierungs_pfad"])
                farbe = lese_markierungsfarbe(eintrag["markierungs_pfad"])
                markierung_rotiert = (R @ markierung_punkte.T).T
                markierung_rotiert[:, 2] += versatz
                for p in markierung_rotiert:
                    vertex_index = self.genesungsverlauf_aktuell_rotiert.find_closest_point(p)
                    bisherige_farbe = self.genesungsverlauf_gewinner.get(vertex_index)
                    if farb_prioritaet(farbe) > farb_prioritaet(bisherige_farbe):
                        self.genesungsverlauf_gewinner[vertex_index] = farbe
                print(f"{len(markierung_punkte)} marked points taken over from {eintrag['markierungs_pfad'].parent.name}")
            except ValueError as e:
                print(f"Skipping this marking, it could not be read: {e}")

        self.genesungsverlauf_index += 1
        if self.genesungsverlauf_index < len(self.genesungsverlauf_warteschlange):
            self._genesungsverlauf_naechsten_schritt_zeigen()
        else:
            self._genesungsverlauf_abschliessen()


    def _genesungsverlauf_abschliessen(self):
        self.button_naechster_finger_overlay.setVisible(False)
        self.button_abbruch_overlay.setVisible(False)
        self.zeige_basis_mesh_neu()

        #self.genesungsverlauf_gewinner = bereinige_gewinner(self.aktuelles_hand_mesh, self.genesungsverlauf_gewinner)

        
        farben_gruppen = {}
        for vertex_index, farbe in self.genesungsverlauf_gewinner.items():
            farben_gruppen.setdefault(farbe, []).append(vertex_index)

        print(f"{len(self.genesungsverlauf_gewinner)} vertices marked in {len(farben_gruppen)} colors")
        for farbe, indices in farben_gruppen.items():
            maske = np.zeros(self.aktuelles_hand_mesh.n_points, dtype=bool)
            maske[indices] = True
            flaeche = extract_faces_of_hand(self.aktuelles_hand_mesh, maske)
            if flaeche.n_points == 0:
                continue

            flaeche = flaeche.clean()
            flaeche = flaeche.compute_normals(point_normals=True, auto_orient_normals=True)
            flaeche.points = flaeche.points + flaeche.point_normals * 0.3

            farbe_hex = f"#{farbe[0]:02X}{farbe[1]:02X}{farbe[2]:02X}"
            self.plotter.add_mesh(flaeche, color=farbe_hex, opacity=1.0)

        save_path = speichere_genesungsverlauf(
            self.aktuelles_hand_mesh, self.aktuelle_teile, self.genesungsverlauf_gewinner, str(self.aktueller_ordner)
        )
        self.hinweis_label.setText(f"Genesungsverlauf erstellt und gespeichert: {save_path.parent.name}")
        print(f"3D recovery progress built and saved in {save_path.parent}")

    def _genesungsverlauf_hoehen_versatz(self, mesh, ziel_hoehe=30):
        #Verstz auf Höhe, dass die Fingerspitze auf Höhe 30 ist, dass die Höhe genau passt
        return ziel_hoehe - mesh.bounds[5]

    def genesungsverlauf_speichern_klick(self):
        if self.aktueller_ordner is None:
            self.hinweis_label.setText("Erst einen Scan laden!")
            print("Saving the recovery progress needs a loaded scan")
            return

        save_path = speichere_genesungsverlauf(self.aktuelles_hand_mesh, self.aktuelle_teile, str(self.aktueller_ordner))
        self.hinweis_label.setText(f"Genesungsverlauf gespeichert: {save_path.parent.name}")
        print(f"Recovery progress saved in {save_path.parent}")
        self.button_speichere_genesungsverlauf_overlay.setVisible(False)
