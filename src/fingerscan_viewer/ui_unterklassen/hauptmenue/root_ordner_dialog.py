from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QMessageBox,
    QSpinBox,
    QCheckBox)

import konstanten as k


def root_ordner_waehlen(eltern, aktueller, viewer_anzahl=None, fortgeschritten=False):
    # Dialog zum Waehlen des Root-Ordners - gemeinsam fuer den Title Screen
    # und das Zahnrad in der laufenden Software.
    # Mit viewer_anzahl (nur in der laufenden Software) kommt noch die Anzahl
    # der Viewer dazu, auf dem Title Screen gibt es noch keine.
    # Mehr als 9 Viewer gehen nur im Fortgeschrittenen Modus.
    # Gibt {"pfad": ..., "viewer_anzahl": ..., "fortgeschritten": ...} zurueck,
    # oder None bei Abbrechen. Speichern ist Sache des Aufrufers.
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

        fortgeschritten_box = QCheckBox("Fortgeschrittenen Modus aktivieren")
        fortgeschritten_box.setToolTip(
            f"Erlaubt bis zu {k.VIEWER_ANZAHL_MAX} Viewer statt {k.VIEWER_ANZAHL_NORMAL_MAX}.\n"
            "Viele Viewer brauchen viel Grafikspeicher und werden sehr klein.")
        fortgeschritten_box.setChecked(fortgeschritten)
        # Beim Abwaehlen setzt setMaximum eine zu grosse Anzahl selbst auf 9 zurueck
        fortgeschritten_box.toggled.connect(
            lambda an: anzahl_eingabe.setMaximum(k.VIEWER_ANZAHL_MAX if an else k.VIEWER_ANZAHL_NORMAL_MAX))
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
        dialog.accept()
    knoepfe.accepted.connect(speichern)

    # Die Beschriftung hat sonst die 25px aus dem globalen QLabel-Stil
    for label in dialog.findChildren(QLabel):
        label.setStyleSheet("font-size: 14px;")

    if dialog.exec() != QDialog.Accepted:
        return None
    return ergebnis
