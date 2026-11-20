import os
import sys

if sys.platform.startswith("win"):
    # niente modalità scura automatica di Windows: l'interfaccia ha i suoi colori
    os.environ.setdefault("QT_QPA_PLATFORM", "windows:darkmode=0")
    try:  # icona di Modulo (e non di Python) nella barra delle applicazioni
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("topodondio.Fascicolo")
    except Exception:
        pass

from PySide6.QtCore import QTranslator, QLibraryInfo, QLocale
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
from .widgets import TEMA
from .finestra import Finestra


def tavolozza_chiara():
    """Colori fissi: l'interfaccia resta leggibile anche con Windows/macOS in modalità scura."""
    p = QPalette()
    testo, sfondo, base = QColor("#1f2b2e"), QColor("#f4f5f2"), QColor("#ffffff")
    for gruppo in (QPalette.Active, QPalette.Inactive):
        p.setColor(gruppo, QPalette.Window, sfondo)
        p.setColor(gruppo, QPalette.WindowText, testo)
        p.setColor(gruppo, QPalette.Base, base)
        p.setColor(gruppo, QPalette.AlternateBase, QColor("#f7f8f5"))
        p.setColor(gruppo, QPalette.Text, testo)
        p.setColor(gruppo, QPalette.Button, base)
        p.setColor(gruppo, QPalette.ButtonText, testo)
        p.setColor(gruppo, QPalette.ToolTipBase, base)
        p.setColor(gruppo, QPalette.ToolTipText, testo)
        p.setColor(gruppo, QPalette.PlaceholderText, QColor("#8b948f"))
        p.setColor(gruppo, QPalette.Highlight, QColor("#cfe5df"))
        p.setColor(gruppo, QPalette.HighlightedText, testo)
        p.setColor(gruppo, QPalette.BrightText, QColor("#b3261e"))
        p.setColor(gruppo, QPalette.Link, QColor("#2f7d6d"))
    grigio = QColor("#9aa39f")
    for ruolo in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, ruolo, grigio)
    p.setColor(QPalette.Disabled, QPalette.Base, QColor("#eef0ec"))
    p.setColor(QPalette.Disabled, QPalette.Window, sfondo)
    p.setColor(QPalette.Disabled, QPalette.Button, QColor("#eef0ec"))
    return p


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Modulo")
    app.setStyle("Fusion")
    from PySide6.QtGui import QIcon
    from .core import APP_DIR
    if (APP_DIR / "assets" / "fascicolo.ico").exists():
        app.setWindowIcon(QIcon(str(APP_DIR / "assets" / "fascicolo.ico")))
    app.setPalette(tavolozza_chiara())
    tr = QTranslator(app)  # pulsanti standard in italiano (Sì/No/Annulla)
    if tr.load(QLocale("it_IT"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
    app.setStyleSheet(TEMA)
    w = Finestra()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
