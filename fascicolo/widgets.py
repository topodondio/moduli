"""Widget dei campi e tema grafico di Fascicolo."""
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (QWidget, QLineEdit, QComboBox, QCheckBox, QPlainTextEdit, QTableWidget,
                               QTableWidgetItem, QHBoxLayout, QToolButton, QCalendarWidget, QMenu,
                               QWidgetAction, QHeaderView, QAbstractItemView)

ACCENTO = "#2f7d6d"

TEMA = f"""
* {{ font-size: 13px; }}
QMainWindow, QDialog, QMessageBox {{ background: #f4f5f2; color: #1f2b2e; }}
QLabel {{ color: #1f2b2e; }}
QMessageBox QLabel {{ color: #1f2b2e; }}
QTableWidget, QTreeView, QListWidget {{ color: #1f2b2e; }}
QGroupBox {{ color: #1f2b2e; }}
QMenu {{ background: #ffffff; color: #1f2b2e; }}
QToolTip {{ background: #ffffff; color: #1f2b2e; border: 1px solid #cfd5cf; }}
#barra {{ background: #1f2b2e; }}
#barra QLabel {{ color: #e8eeec; }}
#barra #sottotitoloApp {{ color: #8fa5a0; }}
#titoloApp {{ font-size: 20px; font-weight: 600; color: #ffffff; padding: 4px 2px; }}
#sottotitoloApp {{ color: #8fa5a0; font-size: 11px; }}
#barra QLineEdit {{ background: #2c3a3d; border: 1px solid #3a4b4f; color: #e8eeec; border-radius: 6px; padding: 6px 8px; }}
#listaPratiche {{ background: transparent; border: none; color: #dfe7e5; outline: 0; }}
#listaPratiche::item {{ padding: 8px 8px; border-radius: 6px; margin: 1px 0; }}
#listaPratiche::item:selected {{ background: {ACCENTO}; color: white; }}
#listaPratiche::item:hover:!selected {{ background: #2c3a3d; }}
#barra QPushButton {{ background: #2c3a3d; color: #dfe7e5; border: none; border-radius: 6px; padding: 7px 10px; text-align: left; }}
#barra QPushButton:hover {{ background: #364649; }}
#barra QPushButton#piccolo {{ text-align: center; padding: 5px 4px; font-size: 12px; }}
#barra QPushButton#primario {{ background: {ACCENTO}; color: white; text-align: center; font-weight: 600; }}
#barra QPushButton#primario:hover {{ background: #378f7d; }}
#intestazione {{ background: #ffffff; border-bottom: 1px solid #dfe2dc; }}
#nomePratica {{ font-size: 19px; font-weight: 600; color: #1f2b2e; }}
#infoPratica {{ color: #6b7672; }}
QTabWidget::pane {{ border: none; background: #f4f5f2; }}
QTabBar::tab {{ background: transparent; padding: 9px 18px; color: #5d6a66; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: #1f2b2e; border-bottom: 2px solid {ACCENTO}; font-weight: 600; }}
QTabBar::tab:hover {{ color: #1f2b2e; }}
#navSezioni {{ background: #ffffff; border: 1px solid #dfe2dc; border-radius: 8px; outline: 0; padding: 4px; }}
#navSezioni::item {{ padding: 8px 10px; border-radius: 6px; color: #33403d; }}
#navSezioni::item:selected {{ background: #e3efec; color: {ACCENTO}; font-weight: 600; }}
#scheda {{ background: #ffffff; border: 1px solid #dfe2dc; border-radius: 8px; }}
#titoloSezione {{ font-size: 16px; font-weight: 600; color: #1f2b2e; }}
#nota {{ color: #6b7672; }}
#avviso {{ background: #fff6e0; border: 1px solid #f0d58a; border-radius: 6px; padding: 8px; color: #6b5310; }}
QLineEdit, QComboBox, QPlainTextEdit {{ background: #ffffff; border: 1px solid #cfd5cf; border-radius: 5px; padding: 5px 7px; color: #1f2b2e; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {ACCENTO}; }}
QLineEdit:disabled, QComboBox:disabled {{ background: #eef0ec; color: #8b948f; }}
QLineEdit[mancante="true"] {{ border: 1px solid #d9822b; background: #fffaf2; }}
QPushButton {{ background: #ffffff; border: 1px solid #cfd5cf; border-radius: 6px; padding: 6px 14px; color: #1f2b2e; }}
QPushButton:hover {{ border-color: {ACCENTO}; color: {ACCENTO}; }}
QPushButton#primario {{ background: {ACCENTO}; color: #ffffff; border: none; font-weight: 600; }}
QPushButton#primario:hover {{ background: #378f7d; color: #ffffff; }}
QPushButton:disabled {{ color: #a3aba7; border-color: #e0e3df; }}
QTableWidget, QTreeView {{ background: #ffffff; border: 1px solid #dfe2dc; border-radius: 8px; gridline-color: #eceeea; selection-background-color: #e3efec; selection-color: #1f2b2e; }}
QHeaderView::section {{ background: #f4f5f2; border: none; border-bottom: 1px solid #dfe2dc; padding: 6px; color: #5d6a66; font-weight: 600; }}
QScrollArea {{ border: none; background: transparent; }}
QCheckBox {{ color: #1f2b2e; spacing: 8px; }}
QMenuBar {{ background: #1f2b2e; color: #dfe7e5; padding: 2px 6px; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: #2c3a3d; }}
QMenu::item {{ padding: 6px 22px; }}
QMenu::item:selected {{ background: #e3efec; color: #1f2b2e; }}
QLabel#numero {{ background: #e3efec; color: #2f7d6d; font-weight: 700; border-radius: 6px; padding: 5px 0; }}
QLabel#presa {{ color: #9aa39f; font-size: 18px; padding: 0 2px; }}
#elencoModuli {{ background: #ffffff; border: 1px solid #dfe2dc; border-radius: 8px; outline: 0; padding: 6px; }}
#elencoModuli::item {{ border-bottom: 1px solid #eef0ec; }}
#elencoModuli::item:selected {{ background: #f1f7f5; }}
QLabel#etichetta {{ color: #4a5653; }}
"""


class Campo(QWidget):
    """Widget generico per un campo dello schema: espone valore()/imposta() e il segnale cambiato.QPushButton#togli { color: #6b7075; }
QPushButton#togli:hover { color: #b3261e; border-color: #b3261e; background: #fbeeed; }
"""
    cambiato = Signal()

    def __init__(self, defn, comuni=None, parent=None):
        super().__init__(parent)
        self.defn = defn
        t = defn.get("t", "text")
        self.t = t
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        if t in ("text", "date"):
            self.w = QLineEdit()
            self.w.textEdited.connect(lambda *_: self.cambiato.emit())
            lay.addWidget(self.w)
            if t == "date":
                self.w.setPlaceholderText("gg/mm/aaaa")
                self.w.setMaximumWidth(140)
                b = QToolButton()
                b.setText("📅")
                b.setAutoRaise(True)
                b.clicked.connect(lambda: self._calendario(b))
                lay.addWidget(b)
                lay.addStretch()
        elif t in ("choice", "comune"):
            self.w = QComboBox()
            if t == "comune":
                self.w.setEditable(True)
                self.w.addItems([""] + (comuni or []))
                self.w.editTextChanged.connect(lambda *_: self.cambiato.emit())
            else:
                self.w.addItems(defn.get("scelte", []))
                self.w.currentIndexChanged.connect(lambda *_: self.cambiato.emit())
            self.w.setMinimumWidth(260)
            lay.addWidget(self.w)
            lay.addStretch()
        elif t == "bool":
            self.w = QCheckBox(defn["l"])
            self.w.toggled.connect(lambda *_: self.cambiato.emit())
            lay.addWidget(self.w)
        elif t == "long":
            self.w = QPlainTextEdit()
            self.w.setFixedHeight(72)
            self.w.textChanged.connect(lambda: self.cambiato.emit())
            lay.addWidget(self.w)
        elif t == "table":
            col = defn["colonne"]
            self.w = QTableWidget(defn["righe"], len(col))
            self.w.setHorizontalHeaderLabels([c[1] for c in col])
            self.w.verticalHeader().setVisible(False)
            self.w.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.w.setFixedHeight(32 + 30 * defn["righe"])
            self.w.setEditTriggers(QAbstractItemView.AllEditTriggers)
            self.w.itemChanged.connect(lambda *_: self.cambiato.emit())
            lay.addWidget(self.w)

    def _calendario(self, bottone):
        menu = QMenu(self)
        cal = QCalendarWidget()
        cal.setGridVisible(True)
        d = QDate.fromString(self.w.text(), "dd/MM/yyyy")
        if d.isValid():
            cal.setSelectedDate(d)
        act = QWidgetAction(menu)
        act.setDefaultWidget(cal)
        menu.addAction(act)

        def scelto(data):
            self.w.setText(data.toString("dd/MM/yyyy"))
            self.cambiato.emit()
            menu.close()
        cal.clicked.connect(scelto)
        menu.exec(bottone.mapToGlobal(bottone.rect().bottomLeft()))

    # valori ------------------------------------------------------------------
    def valore(self):
        t = self.t
        if t in ("text", "date"):
            return self.w.text().strip()
        if t == "choice":
            return self.w.currentText()
        if t == "comune":
            return self.w.currentText().strip()
        if t == "bool":
            return self.w.isChecked()
        if t == "long":
            return self.w.toPlainText().strip()
        if t == "table":
            out = {}
            for i in range(self.w.rowCount()):
                for j, (ck, _) in enumerate(self.defn["colonne"]):
                    it = self.w.item(i, j)
                    out[f"{i}.{ck}"] = it.text().strip() if it else ""
            return out
        return None

    def imposta(self, v):
        self.blockSignals(True)
        self.w.blockSignals(True)
        t = self.t
        if t in ("text", "date"):
            self.w.setText(str(v or ""))
        elif t == "choice":
            i = self.w.findText(str(v))
            self.w.setCurrentIndex(max(i, 0))
        elif t == "comune":
            self.w.setEditText(str(v or ""))
        elif t == "bool":
            self.w.setChecked(bool(v))
        elif t == "long":
            self.w.setPlainText(str(v or ""))
        elif t == "table":
            for i in range(self.w.rowCount()):
                for j, (ck, _) in enumerate(self.defn["colonne"]):
                    self.w.setItem(i, j, QTableWidgetItem(str((v or {}).get(f"{i}.{ck}", ""))))
        self.w.blockSignals(False)
        self.blockSignals(False)

    def segna_mancante(self, si):
        if isinstance(self.w, QLineEdit):
            self.w.setProperty("mancante", "true" if si else "false")
            self.w.style().unpolish(self.w)
            self.w.style().polish(self.w)
