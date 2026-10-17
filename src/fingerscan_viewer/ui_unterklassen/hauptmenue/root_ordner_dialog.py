from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QMessageBox,
    QSpinBox,
    QCheckBox)

import konstanten as k
from ui_unterklassen.hauptmenue.schloss_klammer import SchlossKlammer


def root_ordner_waehlen(eltern, aktueller, viewer_anzahl=None, fortgeschritten=False, knopf_groessen=None,
                        groessen_gekoppelt=False):
    # Dialog zum Waehlen des Root-Ordners - gemeinsam fuer den Title Screen
    # und das Zahnrad in der laufenden Software.
    # Mit viewer_anzahl (nur in der laufenden Software) kommt noch die Anzahl
    # der Viewer dazu, auf dem Title Screen gibt es noch keine.
    # Mehr als 9 Viewer und Knopfgroessen ausserhalb von 50 bis 200 % gehen
    # nur im Fortgeschrittenen Modus. Der Haken steht ganz unten.
    # Mit knopf_groessen ({"links": 100, ...} in Prozent) je Gruppe ein Rad,
    # rechts daneben ein Schloss, das die drei Raeder koppelt.
    # Gibt {"pfad", "viewer_anzahl", "fortgeschritten", "knopf_groessen",
    # "groessen_gekoppelt"} zurueck, oder None bei Abbrechen. Speichern ist
    # Sache des Aufrufers.
    dialog = QDialog(eltern)
    dialog.setWindowTitle("Einstellungen")
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Root-Ordner (wird beim Start automatisch geöffnet):"))

    # Eingabefeld, vorbelegt mit dem aktuellen Wert
    pfad_zeile_layout = QHBoxLayout()
    pfad_eingabe = QLineEdit(aktueller or "")
    button_durchsuchen = QPushButton("Files durchsuchen")
    pfad_zeile_layout.addWidget(pfad_eingabe)
    pfad_zeile_layout.addWidget(button_durchsuchen)
    layout.addLayout(pfad_zeile_layout)

    # öffnet  Ordner-Auswahldialog
    def durchsuchen():
        ordner = QFileDialog.getExistingDirectory(dialog, "Root-Ordner wählen", pfad_eingabe.text() or str(Path.home()))
        if ordner:
            pfad_eingabe.setText(ordner)
    button_durchsuchen.clicked.connect(durchsuchen)

    anzahl_eingabe = None
    fortgeschritten_box = None
    if viewer_anzahl is not None:
        # Erklaerung direkt ins senkrechte Haupt-Layout, die Zeile mit dem
        # Rad kommt dann darunter
        layout.addWidget(QLabel("Der ausgewählte Viewer kann mit 'TAB' fortlaufend gewechselt werden.\nMit Halten der 'TAB'-Taste + Rechtsklick kann ein beliebiger Viewer gewählt werden."))
        anzahl_zeile_layout = QHBoxLayout()
        anzahl_zeile_layout.addWidget(QLabel("Anzahl Viewer:"))
        anzahl_eingabe = QSpinBox()
        anzahl_eingabe.setRange(1, k.VIEWER_ANZAHL_MAX if fortgeschritten else k.VIEWER_ANZAHL_NORMAL_MAX)
        anzahl_eingabe.setValue(viewer_anzahl)
        anzahl_zeile_layout.addWidget(anzahl_eingabe)
        anzahl_zeile_layout.addStretch()
        layout.addLayout(anzahl_zeile_layout)

    groessen_eingaben = {}
    schloss = None
    # Koppelung: bei zu gerechnet wird immer vom Stand beim Zuschliessen
    # (basis) aus, so laufen die Werte durch Rundung nicht auseinander.
    # "laeuft" sperrt, solange Raeder von hier aus gesetzt werden, sonst
    # wuerde jedes gesetzte Rad die anderen gleich nochmal umrechnen.
    koppelung = {"basis": {}, "laeuft": False}

    def basis_merken():
        koppelung["basis"] = {gruppe: rad.value() for gruppe, rad in groessen_eingaben.items()}

    def raeder_setzen(werte):
        # Mehrere Raeder auf einmal setzen, ohne dass die Koppelung dazwischenfunkt
        koppelung["laeuft"] = True
        for gruppe, wert in werte.items():
            groessen_eingaben[gruppe].setValue(wert)
        koppelung["laeuft"] = False
        basis_merken()

    def rad_geaendert(gruppe, wert):
        if schloss is None or not schloss.isChecked() or koppelung["laeuft"]:
            return
        # Proportional: wird ein Rad verdoppelt, verdoppeln sich die anderen
        faktor = wert / koppelung["basis"][gruppe]
        koppelung["laeuft"] = True
        for andere, rad in groessen_eingaben.items():
            if andere != gruppe:
                # An den Grenzen bleibt das Rad stehen, beim Zurueckdrehen
                # stimmt es wieder, weil von der Basis aus gerechnet wird
                rad.setValue(round(koppelung["basis"][andere] * faktor))
        koppelung["laeuft"] = False

    if knopf_groessen is not None:
        layout.addSpacing(10)
        kopf_zeile = QHBoxLayout()
        kopf_zeile.addWidget(QLabel("Größe der Knöpfe (100 % = Standard):"))
        kopf_zeile.addStretch()
        knopf_standard = QPushButton("Standard")
        knopf_standard.setToolTip("Alle Knopfgrößen wieder auf 100 % setzen")
        # Die Raeder gibt es erst weiter unten, beim Klick sind sie aber alle da
        knopf_standard.clicked.connect(
            lambda: raeder_setzen({gruppe: 100 for gruppe in groessen_eingaben}))
        kopf_zeile.addWidget(knopf_standard)
        layout.addLayout(kopf_zeile)

        # Raster: Beschriftung | Rad | Schloss-Klammer ueber alle Zeilen
        raster = QGridLayout()
        # Klein, damit sich die Klammer an die Raeder anschmiegt. Zwischen
        # Beschriftung und Rad sorgt die Mindestbreite der Beschriftung fuer Luft.
        raster.setHorizontalSpacing(2)
        for zeile, (gruppe, beschriftung) in enumerate(k.KNOPF_GRUPPEN):
            name = QLabel(beschriftung)
            # Gleich breit, damit die Raeder untereinander buendig stehen
            name.setMinimumWidth(200)
            # Abstand zum Rad, der Raster-Abstand ist fuer die Klammer klein
            name.setContentsMargins(0, 0, 12, 0)
            raster.addWidget(name, zeile, 0)
            rad = QSpinBox()
            if fortgeschritten:
                rad.setRange(k.KNOPF_GROESSE_FORTGESCHRITTEN_MIN, k.KNOPF_GROESSE_FORTGESCHRITTEN_MAX)
            else:
                rad.setRange(k.KNOPF_GROESSE_MIN, k.KNOPF_GROESSE_MAX)
            rad.setSingleStep(10)
            rad.setSuffix(" %")
            rad.setValue(knopf_groessen[gruppe])
            rad.valueChanged.connect(lambda wert, g=gruppe: rad_geaendert(g, wert))
            raster.addWidget(rad, zeile, 1)
            groessen_eingaben[gruppe] = rad

        schloss = SchlossKlammer(list(groessen_eingaben.values()))

        def schloss_umgeschaltet(zu):
            schloss.setToolTip(
                "Gekoppelt: alle drei Größen ändern sich gemeinsam im gleichen Verhältnis.\nKlicken zum Lösen."
                if zu else "Einzeln: jede Größe für sich.\nKlicken, um alle drei gemeinsam zu ändern.")
            if zu:
                basis_merken()
        schloss.toggled.connect(schloss_umgeschaltet)
        schloss.setChecked(groessen_gekoppelt)
        schloss_umgeschaltet(groessen_gekoppelt)
        raster.addWidget(schloss, 0, 2, len(k.KNOPF_GRUPPEN), 1)
        raster.setColumnStretch(3, 1)
        layout.addLayout(raster)

    if anzahl_eingabe is not None or groessen_eingaben:
        layout.addSpacing(10)
        fortgeschritten_box = QCheckBox("Fortgeschrittenen Modus aktivieren")
        fortgeschritten_box.setToolTip(
            f"Erlaubt bis zu {k.VIEWER_ANZAHL_MAX} Viewer statt {k.VIEWER_ANZAHL_NORMAL_MAX} und Knopfgrößen "
            f"von {k.KNOPF_GROESSE_FORTGESCHRITTEN_MIN} bis {k.KNOPF_GROESSE_FORTGESCHRITTEN_MAX} % "
            f"statt {k.KNOPF_GROESSE_MIN} bis {k.KNOPF_GROESSE_MAX} %.\n"
            "Viele Viewer brauchen viel Grafikspeicher, sehr kleine oder große Knöpfe sind kaum bedienbar.")
        fortgeschritten_box.setChecked(fortgeschritten)

        def grenzen_setzen(an):
            # Beim Abwaehlen ziehen setMaximum und setRange zu grosse oder zu
            # kleine Werte selbst auf die Grenze, z.B. 20 Viewer auf 9
            if anzahl_eingabe is not None:
                anzahl_eingabe.setMaximum(k.VIEWER_ANZAHL_MAX if an else k.VIEWER_ANZAHL_NORMAL_MAX)
            # Das Zurueckziehen auf die Grenzen soll die anderen Raeder nicht
            # ueber die Koppelung mitreissen
            koppelung["laeuft"] = True
            for rad in groessen_eingaben.values():
                if an:
                    rad.setRange(k.KNOPF_GROESSE_FORTGESCHRITTEN_MIN, k.KNOPF_GROESSE_FORTGESCHRITTEN_MAX)
                else:
                    rad.setRange(k.KNOPF_GROESSE_MIN, k.KNOPF_GROESSE_MAX)
            koppelung["laeuft"] = False
            basis_merken()
        fortgeschritten_box.toggled.connect(grenzen_setzen)
        layout.addWidget(fortgeschritten_box)

    # OK / Abbrechen
    knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    layout.addWidget(knoepfe)
    knoepfe.rejected.connect(dialog.reject)

    ergebnis = {}

    def speichern():
        p = Path(pfad_eingabe.text().strip()).expanduser()
        if not p.is_dir():
            # Dialog bleibt offen, damit man nur korrigieren muss
            QMessageBox.warning(dialog, "Einstellungen", f"'{p}' ist kein gültiger Ordner.")
            return
        ergebnis["pfad"] = str(p)
        ergebnis["viewer_anzahl"] = anzahl_eingabe.value() if anzahl_eingabe is not None else viewer_anzahl
        ergebnis["fortgeschritten"] = fortgeschritten_box.isChecked() if fortgeschritten_box is not None else fortgeschritten
        ergebnis["knopf_groessen"] = ({gruppe: rad.value() for gruppe, rad in groessen_eingaben.items()}
                                      if groessen_eingaben else knopf_groessen)
        ergebnis["groessen_gekoppelt"] = schloss.isChecked() if schloss is not None else groessen_gekoppelt
        dialog.accept()
    knoepfe.accepted.connect(speichern)

    # Die Beschriftung hat sonst die 25px aus dem globalen QLabel-Stil
    for label in dialog.findChildren(QLabel):
        label.setStyleSheet("font-size: 14px;")

    if dialog.exec() != QDialog.Accepted:
        return None
    return ergebnis
