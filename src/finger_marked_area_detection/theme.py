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

QPushButton:disabled {
    background-color: #EDEFF2;
    color: #A0A6AE;
    border-color: #C7CDD4;
}

QLabel {
    color: #1F2937;
    font-size: 25px;
}
"""