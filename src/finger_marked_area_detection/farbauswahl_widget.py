from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QSlider, QPushButton
from PySide6.QtCore import Qt

from farberkennung import erzeuge_farbpalette


class FarbAuswahlWidget(QWidget):
    def __init__(self, standard_farbe: str = "#000000", parent=None):
        super().__init__(parent)
        self.farbe = standard_farbe

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.vorschau = QLabel()
        self.vorschau.setFixedSize(192, 40)
        layout.addWidget(self.vorschau)

        self.slider_r = self._baue_slider("red")
        self.slider_g = self._baue_slider("green")
        self.slider_b = self._baue_slider("blue")
        for slider in (self.slider_r, self.slider_g, self.slider_b):
            layout.addWidget(slider)
            slider.valueChanged.connect(self._slider_geaendert)

        self.button_pipette = QPushButton("Pipette (Farbe vom Scan)")
        self.button_pipette.setFixedSize(192, 40)
        layout.addWidget(self.button_pipette)

        farb_grid = QGridLayout()
        farb_grid.setSpacing(2)
        for i, farbe in enumerate(erzeuge_farbpalette(50)):
            swatch = QPushButton()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(f"background-color: {farbe}; border: 1px solid #888; border-radius: 2px;")
            swatch.clicked.connect(lambda checked=False, f=farbe: self.setze_farbe(f))
            farb_grid.addWidget(swatch, i // 10, i % 10)
        layout.addLayout(farb_grid)

        self.setze_farbe(standard_farbe)

    def _baue_slider(self, farbname: str) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 255)
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height: 10px; border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 white, stop:1 {farbname}); }}
            QSlider::handle:horizontal {{ width: 16px; background: #4A90D9; border: 1px solid #3A73AD;
                border-radius: 8px; margin: -4px 0; }}
            """)
        return slider

    def _slider_geaendert(self):
        hex_code = f"#{self.slider_r.value():02X}{self.slider_g.value():02X}{self.slider_b.value():02X}"
        self.farbe = hex_code
        self.vorschau.setStyleSheet(f"background-color: {hex_code}; border: 2px solid #4A90D9; border-radius: 6px;")

    def setze_farbe(self, hex_code: str) -> None:
        """Setzt die Farbe von aussen (Raster-Klick, Pipette) - hält
        Vorschau UND Slider synchron."""
        self.farbe = hex_code
        self.vorschau.setStyleSheet(f"background-color: {hex_code}; border: 2px solid #4A90D9; border-radius: 6px;")

        r, g, b = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
        for slider, wert in [(self.slider_r, r), (self.slider_g, g), (self.slider_b, b)]:
            slider.blockSignals(True)
            slider.setValue(wert)
            slider.blockSignals(False)