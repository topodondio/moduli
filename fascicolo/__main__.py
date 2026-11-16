import sys
from PySide6.QtWidgets import QApplication
from .widgets import TEMA
from .finestra import Finestra


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Fascicolo")
    app.setStyle("Fusion")
    app.setStyleSheet(TEMA)
    w = Finestra()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
