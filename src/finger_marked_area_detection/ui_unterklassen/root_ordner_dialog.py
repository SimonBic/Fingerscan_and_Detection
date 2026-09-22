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
    QMessageBox)


def root_ordner_waehlen(eltern, aktueller):
    # Dialog zum Waehlen des Root-Ordners - gemeinsam fuer den Title Screen
    # und das Zahnrad in der laufenden Software.
    # Gibt den neuen Pfad zurueck, oder None bei Abbrechen. Speichern ist
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
        dialog.accept()
    knoepfe.accepted.connect(speichern)

    # Die Beschriftung hat sonst die 25px aus dem globalen QLabel-Stil
    for label in dialog.findChildren(QLabel):
        label.setStyleSheet("font-size: 14px;")

    if dialog.exec() != QDialog.Accepted:
        return None
    return ergebnis.get("pfad")
