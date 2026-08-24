import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
import PySide6
qt_lib_pfad = os.path.join(os.path.dirname(PySide6.__file__), "Qt", "lib")
os.environ["LD_LIBRARY_PATH"] = qt_lib_pfad + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")

import sys
from PySide6.QtWidgets import QApplication
 
from theme import QSS
from userinterface import HauptFenster
 
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    fenster = HauptFenster()
    fenster.show()
    sys.exit(app.exec())