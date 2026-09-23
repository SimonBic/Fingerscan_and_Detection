QSS = """
QMainWindow, QWidget {
    background-color: #F5F7FA;
    color: #1F2937;
    font-size: 14px;
    font-family: "Latin Modern Roman", "CMU Serif", serif;
}

QWidget#knopf_spalte {
    background-color: #FFFFFF;
    border-right: 1px solid #D8DEE6;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 #FFFFFF, stop:1 #EDF2F8);
    color: #1F2937;
    border: 2px solid #4A90D9;
    border-radius: 10px;
    padding: 8px;
    font-weight: 500;
}

QToolButton#patient_knopf {
    border: none;
    background: #F0F0F0;
    border-radius: 8px;
    font-size: 10px;
}
QToolButton#patient_knopf:hover { background: #E0E8F0; }
/* Aussehen (Verlauf, blauer Rand, Hover) kommt vom allgemeinen
   QPushButton oben. Hier nur, was fuer die 80px Breite noetig ist -
   KEIN background/border setzen: ein #id-Selektor schlaegt
   QPushButton:hover, der Hover-Effekt waere sonst weg. */
QPushButton#untersuchung_knopf {
    padding: 4px 2px;
    font-size: 10px;
}

/* Icon-Knoepfe (Hand, Finger, Stift, Lineal, 3D/2D): gleicher Rahmen und
   Verlauf wie QPushButton, aber beim Hover nur ganz hell blau statt des
   dunklen Blaus - das Icon soll erkennbar bleiben. */
QToolButton#pikto_knopf {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FFFFFF, stop:1 #EDF2F8);
    border: 2px solid #4A90D9;
    border-radius: 10px;
    padding: 0px;
}
QToolButton#pikto_knopf:hover {
    background: #E3F0FC;
    border-color: #6AA8E8;
}
QToolButton#pikto_knopf:pressed {
    background: #C9E1F7;
    border-color: #3A73AD;
}

/* Das SVG ist der ganze Knopf - kein eigener Rahmen/Hintergrund */
QToolButton#untersuchung_neu_knopf {
    border: none;
    background: transparent;
    padding: 0px;
}

QPushButton#overlay_button {
    border-radius: 0px;
}


QPushButton#hilfe_knopf {
    
    border-radius: 6px;
    padding: 0px;
    font-size: 18px;
    font-weight: bold;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 #9CBFE2, stop:1 #7FA5C9);
    color: #FFFFFF;
}

QPushButton:pressed {
    background-color: #4A90D9;
    color: #FFFFFF;
    border-color: #3A73AD;
}

QToolButton#zahnrad_knopf {
    border: none;
    background: transparent;
    color: #555555;
    font-size: 28px;   /* das Zeichen ist in den meisten Schriften klein gezeichnet */
}
QToolButton#zahnrad_knopf:hover {
    color: #333333;
}


QTreeWidget {
    border: none;
    background: transparent;
    outline: 0;
}
QTreeWidget::item {
    height: 28px;
    padding-left: 4px;
}
QTreeWidget::item:hover {
    background: #EAF1F7;
}
QTreeWidget::item:selected {
    background: #D6E4F0;
    color: black;
}

QCheckBox#anteil_checkbox {
    font-size: 12px;
    color: #1F2937;
    spacing: 6px;
}
QCheckBox#anteil_checkbox:disabled {
    color: #A0A6AE;
}

QPushButton:disabled {
    background-color: #EDEFF2;
    color: #A0A6AE;
    border-color: #C7CDD4;
}

QLabel {
    color: #1F2937;
    font-size: 25px;
}

/* ---------- Title Screen ----------
   Alles, was auf dem Netz-Hintergrund liegt, muss durchsichtig sein -
   die allgemeine QWidget-Regel oben wuerde es sonst grau uebermalen. */
QStackedWidget#titel_stapel,
QWidget#titel_seite,
QWidget#titel_inhalt,
QWidget#titel_inhalt QLabel {
    background: transparent;
}
QLabel#titel_schrift {
    font-size: 40px;
    font-weight: 600;
    color: #1F2937;
}
QLabel#titel_root {
    font-size: 12px;
    color: #6B7280;
}
QPushButton#titel_knopf {
    font-size: 16px;
    padding: 0px;
}

QFrame#howto_karte {
    background: rgba(255, 255, 255, 0.88);
    border: 1px solid #D8DEE6;
    border-radius: 16px;
}
QFrame#howto_karte QLabel,
QTextBrowser#howto_inhalt {
    background: transparent;
    border: none;
}
QTextBrowser#howto_inhalt {
    font-size: 15px;
    color: #1F2937;
}
QLabel#howto_titel {
    font-size: 32px;
    font-weight: 600;
}

 QScrollBar:vertical {
    background: transparent;
    width: 14px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #4A90D9;
    border-radius: 2px;
    min-height: 20px;
    margin: 0px 4.5px 0px 4.5px;
}
QScrollBar::handle:vertical:hover {
    background: #3A73AD;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
 
QScrollBar:horizontal {
    background: transparent;
    height: 14px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #4A90D9;
    border-radius: 2px;
    min-width: 20px;
    margin: 4.5px 0px 4.5px 0px;
}
QScrollBar::handle:horizontal:hover {
    background: #3A73AD;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""