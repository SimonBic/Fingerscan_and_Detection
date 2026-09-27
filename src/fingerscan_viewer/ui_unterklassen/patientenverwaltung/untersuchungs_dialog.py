
from PySide6.QtWidgets import (
    QDialog, 
    QFormLayout, QHBoxLayout,
    QSpinBox,
    QComboBox, 
    QLineEdit,
    QDialogButtonBox, 
    QMessageBox, 
    QLabel)
import konstanten as k


def op_bezug(meta):
    # Angaben ohne 'bezug' stammen aus der Zeit, als es nur post-OP gab
    bezug = (meta or {}).get("bezug", "postOP")
    return bezug if bezug in k.OP_BEZUG else "postOP"

class UntersuchungDialog(QDialog):
    """Fragt Nummer der Untersuchung und Zeit nach der OP ab - beim Hinzufuegen
    eines Scans zusaetzlich den Ordnernamen.

    'pruefen' ist eine Funktion (nummer, ordnername) -> Fehlertext oder None.
    Bei einem Fehler bleibt der Dialog offen, damit nichts neu eingegeben
    werden muss."""

    def __init__(self, eltern, titel, meta, pruefen, ordnername=None):
        super().__init__(eltern)
        self.setWindowTitle(titel)
        self._pruefen = pruefen
        form = QFormLayout(self)

        self.nummer = QSpinBox()
        self.nummer.setRange(1, 99)
        self.nummer.setValue(meta.get("nummer", 1))
        form.addRow("Untersuchung Nr.:", self.nummer)

        zeit_zeile = QHBoxLayout()
        self.wert = QSpinBox()
        self.wert.setRange(0, 999)
        self.wert.setValue(meta.get("wert", 0))
        self.einheit = QComboBox()
        self.einheit.addItems(list(k.ZEIT_EINHEITEN))
        self.einheit.setCurrentText(meta.get("einheit", "Wochen"))
        self.bezug = QComboBox()
        for schluessel, (text, _, _) in k.OP_BEZUG.items():
            self.bezug.addItem(text, schluessel)
        self.bezug.setCurrentIndex(self.bezug.findData(op_bezug(meta)))
        zeit_zeile.addWidget(self.wert)
        zeit_zeile.addWidget(self.einheit)
        zeit_zeile.addWidget(self.bezug)
        form.addRow("Zeitpunkt:", zeit_zeile)

        # Ordnername nur beim Hinzufuegen. Er folgt den Angaben oben, bis man
        # ihn selbst aendert - danach bleibt er, wie man ihn geschrieben hat.
        self.ordnername = None
        if ordnername is not None:
            self.ordnername = QLineEdit(ordnername)
            self._ordnername_von_hand = False
            self.ordnername.textEdited.connect(lambda _: setattr(self, "_ordnername_von_hand", True))
            for signal in (self.nummer.valueChanged, self.wert.valueChanged,
                           self.einheit.currentTextChanged, self.bezug.currentIndexChanged):
                signal.connect(self._ordnername_nachziehen)
            self._ordnername_nachziehen()
            form.addRow("Ordnername:", self.ordnername)

        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        form.addRow(knoepfe)

        # Die Beschriftungen haben sonst die 25px aus dem globalen QLabel-Stil
        for label in self.findChildren(QLabel):
            label.setStyleSheet("font-size: 14px;")

    def _ordnername_nachziehen(self):
        if self._ordnername_von_hand:
            return
        kuerzel = k.ZEIT_EINHEITEN[self.einheit.currentText()][2]
        endung = k.OP_BEZUG[self.bezug.currentData()][2]
        self.ordnername.setText(f"U{self.nummer.value()}_{self.wert.value()}{kuerzel}_{endung}")

    def meta(self):
        return {"nummer": self.nummer.value(), "wert": self.wert.value(),
                "einheit": self.einheit.currentText(), "bezug": self.bezug.currentData()}

    def ordner(self):
        return self.ordnername.text().strip() if self.ordnername is not None else None

    def accept(self):
        fehler = self._pruefen(self.nummer.value(), self.ordner())
        if fehler:
            QMessageBox.warning(self, self.windowTitle(), fehler)
            return
        super().accept()