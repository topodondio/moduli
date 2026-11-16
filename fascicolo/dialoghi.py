"""Finestre di dialogo: nuova pratica, dati mancanti, comuni, rubrica, insegna modulo."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
                               QPushButton, QDialogButtonBox, QScrollArea, QWidget, QTableWidget, QTableWidgetItem,
                               QHeaderView, QListWidget, QListWidgetItem, QMessageBox, QInputDialog, QSpinBox,
                               QAbstractItemView)

from .schema import SEZIONI, CAMPI
from .widgets import Campo
from . import core

MODALITA = ["PEC", "PEO (email ordinaria)", "Cartaceo", "Portale SUE (online)", "Consegna a mano"]


def _bottoni(dlg, ok="OK", annulla="Annulla"):
    box = QDialogButtonBox()
    b_ok = box.addButton(ok, QDialogButtonBox.AcceptRole)
    b_ok.setObjectName("primario")
    box.addButton(annulla, QDialogButtonBox.RejectRole)
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    return box


# --------------------------------------------------------------------------- nuova pratica

class NuovaPratica(QDialog):
    def __init__(self, comuni, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuova pratica")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        f = QFormLayout()
        self.nome = QLineEdit()
        self.nome.setPlaceholderText("es. Rossi Mario - ampliamento p.ed. 123")
        self.comune = QComboBox()
        self.comune.setEditable(True)
        self.comune.addItems([""] + comuni)
        f.addRow("Nome pratica", self.nome)
        f.addRow("Comune", self.comune)
        lay.addLayout(f)
        n = QLabel("Verrà creata una cartella con le sottocartelle Moduli, Elaborati, Allegati, Consegne e Ricevute.")
        n.setObjectName("nota")
        n.setWordWrap(True)
        lay.addWidget(n)
        lay.addWidget(_bottoni(self, "Crea"))

    def accept(self):
        if not self.nome.text().strip():
            self.nome.setFocus()
            return
        super().accept()


# --------------------------------------------------------------------------- dati mancanti

class DatiMancanti(QDialog):
    """Chiede solo i dati che servono al modulo e non sono ancora nella pratica."""

    def __init__(self, pratica, chiavi, titolo_modulo, comuni, parent=None):
        super().__init__(parent)
        self.pratica = pratica
        self.setWindowTitle(f"Dati per: {titolo_modulo}")
        self.resize(620, 640)
        lay = QVBoxLayout(self)
        t = QLabel(f"Per compilare <b>{titolo_modulo}</b> mancano {len(chiavi)} dati. "
                   "Quello che inserisci qui resta salvato nella pratica e servirà anche ai moduli successivi.")
        t.setWordWrap(True)
        lay.addWidget(t)
        area = QScrollArea()
        area.setWidgetResizable(True)
        cont = QWidget()
        cont.setObjectName("scheda")
        v = QVBoxLayout(cont)
        self.campi = {}
        sez_corr = None
        form = None
        for k in chiavi:
            sez, c = CAMPI[k]
            if sez is not sez_corr:
                h = QLabel(sez["l"])
                h.setObjectName("titoloSezione")
                v.addWidget(h)
                form = QFormLayout()
                form.setLabelAlignment(Qt.AlignRight)
                v.addLayout(form)
                sez_corr = sez
            w = Campo(c, comuni)
            w.imposta(pratica.grezzo(k))
            self.campi[k] = w
            if c.get("t") == "bool":
                form.addRow("", w)
            else:
                form.addRow(c["l"], w)
        v.addStretch()
        area.setWidget(cont)
        lay.addWidget(area)
        box = QDialogButtonBox()
        b = box.addButton("Salva e compila", QDialogButtonBox.AcceptRole)
        b.setObjectName("primario")
        self.b_comunque = box.addButton("Compila lasciando vuoto", QDialogButtonBox.ActionRole)
        box.addButton("Annulla", QDialogButtonBox.RejectRole)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        self.b_comunque.clicked.connect(self.accept)
        lay.addWidget(box)

    def accept(self):
        for k, w in self.campi.items():
            val = w.valore()
            if val not in ("", None):
                self.pratica.set(k, val)
        self.pratica.salva()
        super().accept()


# --------------------------------------------------------------------------- comuni

class Comuni(QDialog):
    COL = [("nome", "Comune"), ("pec", "PEC"), ("peo", "Email ordinaria"), ("consegna", "Modalità di consegna"),
           ("copie", "Copie cartacee"), ("indirizzo", "Indirizzo ufficio tecnico"), ("note", "Note")]

    def __init__(self, archivio, parent=None):
        super().__init__(parent)
        self.archivio = archivio
        self.setWindowTitle("Comuni e modalità di consegna")
        self.resize(1050, 480)
        lay = QVBoxLayout(self)
        n = QLabel("Per ogni comune indica come vuole ricevere le pratiche. Questi dati servono alla consegna "
                   "e all'informativa privacy dei moduli (PEC del comune).")
        n.setObjectName("nota")
        n.setWordWrap(True)
        lay.addWidget(n)
        self.tab = QTableWidget(0, len(self.COL))
        self.tab.setHorizontalHeaderLabels([c[1] for c in self.COL])
        self.tab.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.verticalHeader().setVisible(False)
        for i, w in enumerate([130, 230, 190, 180, 100, 200]):
            self.tab.setColumnWidth(i, w)
        lay.addWidget(self.tab)
        for c in archivio.comuni():
            self._riga(c)
        h = QHBoxLayout()
        b = QPushButton("+ Aggiungi comune")
        b.clicked.connect(lambda: self._riga({}))
        h.addWidget(b)
        b = QPushButton("Rimuovi selezionato")
        b.clicked.connect(lambda: self.tab.removeRow(self.tab.currentRow()))
        h.addWidget(b)
        h.addStretch()
        lay.addLayout(h)
        lay.addWidget(_bottoni(self, "Salva"))

    def _riga(self, c):
        r = self.tab.rowCount()
        self.tab.insertRow(r)
        for j, (k, _) in enumerate(self.COL):
            if k == "consegna":
                cb = QComboBox()
                cb.addItems(MODALITA)
                cb.setCurrentIndex(max(0, cb.findText(c.get(k, "PEC"))))
                self.tab.setCellWidget(r, j, cb)
            elif k == "copie":
                sp = QSpinBox()
                sp.setRange(0, 10)
                sp.setValue(int(c.get(k, 0) or 0))
                self.tab.setCellWidget(r, j, sp)
            else:
                self.tab.setItem(r, j, QTableWidgetItem(str(c.get(k, ""))))

    def accept(self):
        out = []
        for r in range(self.tab.rowCount()):
            c = {}
            for j, (k, _) in enumerate(self.COL):
                w = self.tab.cellWidget(r, j)
                if isinstance(w, QComboBox):
                    c[k] = w.currentText()
                elif isinstance(w, QSpinBox):
                    c[k] = w.value()
                else:
                    it = self.tab.item(r, j)
                    c[k] = it.text().strip() if it else ""
            if c["nome"]:
                out.append(c)
        self.archivio.salva_comuni(sorted(out, key=lambda c: c["nome"].lower()))
        super().accept()


# --------------------------------------------------------------------------- rubrica

class SceltaRubrica(QDialog):
    def __init__(self, voci, titolo, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titolo)
        self.resize(420, 420)
        lay = QVBoxLayout(self)
        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca…")
        lay.addWidget(self.cerca)
        self.lista = QListWidget()
        for nome in sorted(voci, key=str.lower):
            self.lista.addItem(nome)
        self.lista.itemDoubleClicked.connect(lambda *_: self.accept())
        lay.addWidget(self.lista)
        self.cerca.textChanged.connect(self._filtra)
        self.elimina = QPushButton("Elimina dalla rubrica")
        lay.addWidget(self.elimina)
        lay.addWidget(_bottoni(self, "Usa"))

    def _filtra(self, t):
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            it.setHidden(t.lower() not in it.text().lower())

    def scelto(self):
        it = self.lista.currentItem()
        return it.text() if it else None


# --------------------------------------------------------------------------- insegna modulo

class InsegnaModulo(QDialog):
    """Collega i campi di un PDF alle voci della scheda pratica."""

    def __init__(self, modulo, moduli, archivio, parent=None):
        super().__init__(parent)
        self.modulo, self.archivio = modulo, archivio
        self.setWindowTitle(f"Insegna modulo – {modulo.pdf.name}")
        self.resize(1180, 720)
        lay = QVBoxLayout(self)
        n = QLabel("Per ogni campo del PDF scegli la voce della pratica che lo riempie. "
                   "I campi già noti da altri moduli sono proposti in automatico (in verde): controllali, "
                   "perché in questi PDF alcuni nomi sono riusati per dati diversi. "
                   "Per le caselle, in <i>Spunta se</i> scrivi il valore che la attiva (es. <i>Società</i>); "
                   "vuoto = spunta se Sì.")
        n.setWordWrap(True)
        n.setObjectName("nota")
        lay.addWidget(n)
        f = QFormLayout()
        self.titolo = QLineEdit(modulo.map.get("titolo", modulo.pdf.stem.replace("_", " ")))
        self.gruppo = QComboBox()
        self.gruppo.setEditable(True)
        self.gruppo.addItems(["Titoli edilizi", "Cantiere", "Fine lavori e agibilità", "Statistiche", "Altro"])
        self.gruppo.setEditText(modulo.map.get("gruppo", "Altro"))
        h = QHBoxLayout()
        h.addWidget(self.titolo, 3)
        h.addWidget(QLabel("Gruppo"))
        h.addWidget(self.gruppo, 1)
        f.addRow("Titolo", h)
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText("Filtra per etichetta o nome campo…")
        self.filtro.textChanged.connect(self._filtra)
        f.addRow("Cerca", self.filtro)
        lay.addLayout(f)

        campi = core.campi_pdf(modulo.pdf)
        esistenti = dict(modulo.map.get("campi", {}))
        proposte = {} if esistenti else core.suggerisci_mappatura(modulo.pdf, [m for m in moduli if m.mappato])
        self.chiavi = [""] + list(CAMPI.keys()) + ["comune.pec", "comune.peo", "comune.indirizzo"]
        etichette = {k: f"{c[0]['l']} › {c[1]['l']}" for k, c in CAMPI.items()}
        etichette.update({"comune.pec": "Comune › PEC", "comune.peo": "Comune › email", "comune.indirizzo": "Comune › indirizzo"})

        self.tab = QTableWidget(len(campi), 6)
        self.tab.setHorizontalHeaderLabels(["Pag.", "Tipo", "Testo vicino al campo", "Nome nel PDF", "Voce della pratica", "Spunta se / modello"])
        self.tab.verticalHeader().setVisible(False)
        hh = self.tab.horizontalHeader()
        for i, w in enumerate([44, 70, 330, 200, 300]):
            self.tab.setColumnWidth(i, w)
        hh.setStretchLastSection(True)
        self.tab.setSelectionMode(QAbstractItemView.NoSelection)
        self.righe = []
        noti = 0
        for r, c in enumerate(campi):
            regola = esistenti.get(c["nome"]) or proposte.get(c["nome"])
            for j, val in enumerate([str(c["pagina"]), c["tipo"], c["etichetta"], c["nome"]]):
                it = QTableWidgetItem(val)
                it.setFlags(Qt.ItemIsEnabled)
                it.setToolTip(val)
                self.tab.setItem(r, j, it)
            cb = QComboBox()
            for k in self.chiavi:
                cb.addItem(etichette.get(k, "—") if k else "— non compilare —", k)
            extra = QLineEdit()
            if regola:
                if "k" in regola and regola["k"] in self.chiavi:
                    cb.setCurrentIndex(self.chiavi.index(regola["k"]))
                if "v" in regola:
                    extra.setText(str(regola["v"]) if not isinstance(regola["v"], list) else "|".join(regola["v"]))
                if "t" in regola:
                    extra.setText(regola["t"])
                if regola.get("pieno"):
                    extra.setText("*pieno*")
                if proposte.get(c["nome"]) and not esistenti:
                    noti += 1
                    for j in range(4):
                        self.tab.item(r, j).setBackground(Qt.GlobalColor.transparent)
                    self.tab.item(r, 3).setForeground(Qt.darkGreen)
            self.tab.setCellWidget(r, 4, cb)
            self.tab.setCellWidget(r, 5, extra)
            self.righe.append((c, cb, extra, regola))
        lay.addWidget(self.tab)
        info = QLabel(f"{len(campi)} campi nel PDF · {noti} proposti automaticamente da altri moduli · "
                      "per comporre più dati in un campo scrivi un modello, es. {titolare.cognome} {titolare.nome}")
        info.setObjectName("nota")
        lay.addWidget(info)
        lay.addWidget(_bottoni(self, "Salva mappatura"))

    def _filtra(self, t):
        t = t.lower()
        for r, (c, *_rest) in enumerate(self.righe):
            self.tab.setRowHidden(r, bool(t) and t not in (c["etichetta"] + c["nome"]).lower())

    def accept(self):
        campi = {}
        for c, cb, extra, regola in self.righe:
            k = cb.currentData()
            x = extra.text().strip()
            if not k and "{" in x:
                campi[c["nome"]] = {"t": x}
                continue
            if not k:
                continue
            r = {"k": k}
            if regola and regola.get("se") and regola.get("k") == k:
                r["se"] = regola["se"]
            if x == "*pieno*":
                r["pieno"] = True
            elif x:
                if x in ("True", "False"):
                    r["v"] = x == "True"
                else:
                    r["v"] = x.split("|") if "|" in x else x
            campi[c["nome"]] = r
        dati = dict(modulo=self.modulo.pdf.name, titolo=self.titolo.text().strip(),
                    gruppo=self.gruppo.currentText().strip(), ordine=self.modulo.map.get("ordine", 500), campi=campi)
        dest = self.archivio.cartella_mappature() / (self.modulo.pdf.stem + ".json")
        core.scrivi_json(dest, dati)
        super().accept()


# --------------------------------------------------------------------------- dati letti da un PDF

def _mostra(v):
    if isinstance(v, bool):
        return "Sì" if v else "No"
    return str(v or "—")


class AggiornaDati(QDialog):
    """Mostra i dati trovati in un PDF compilato e lascia scegliere quali salvare nella pratica."""

    def __init__(self, pratica, diff, titolo_modulo, intro=None, altri_moduli=0, parent=None):
        super().__init__(parent)
        self.pratica, self.diff = pratica, diff
        self.setWindowTitle(f"Dati da: {titolo_modulo}")
        self.resize(900, 600)
        lay = QVBoxLayout(self)
        t = QLabel(intro or f"Nel PDF <b>{titolo_modulo}</b> ci sono {len(diff)} dati diversi da quelli della pratica. "
                   "Scegli quali salvare: verranno usati anche per gli altri moduli.")
        t.setWordWrap(True)
        lay.addWidget(t)
        self.tab = QTableWidget(len(diff), 4)
        self.tab.setHorizontalHeaderLabels(["Salva", "Dato", "Ora nella pratica", "Nel PDF"])
        self.tab.verticalHeader().setVisible(False)
        hh = self.tab.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self.tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for i, (k, vecchio, nuovo) in enumerate(diff):
            ck = QTableWidgetItem()
            ck.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            ck.setCheckState(Qt.Checked)
            self.tab.setItem(i, 0, ck)
            sez, c = CAMPI[k]
            self.tab.setItem(i, 1, QTableWidgetItem(f"{sez['l']} › {c['l']}"))
            it = QTableWidgetItem(_mostra(vecchio))
            it.setForeground(Qt.gray)
            self.tab.setItem(i, 2, it)
            it = QTableWidgetItem(_mostra(nuovo))
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            self.tab.setItem(i, 3, it)
        lay.addWidget(self.tab)
        h = QHBoxLayout()
        b = QPushButton("Seleziona tutto")
        b.clicked.connect(lambda: self._tutti(True))
        h.addWidget(b)
        b = QPushButton("Deseleziona tutto")
        b.clicked.connect(lambda: self._tutti(False))
        h.addWidget(b)
        h.addStretch()
        lay.addLayout(h)
        self.ricompila = None
        if altri_moduli:
            from PySide6.QtWidgets import QCheckBox
            self.ricompila = QCheckBox(f"Aggiorna anche gli altri {altri_moduli} moduli già compilati "
                                       "(le spunte e i campi scritti a mano restano)")
            self.ricompila.setChecked(True)
            lay.addWidget(self.ricompila)
        lay.addWidget(_bottoni(self, "Salva nella pratica", "Non salvare"))

    def _tutti(self, si):
        for i in range(self.tab.rowCount()):
            self.tab.item(i, 0).setCheckState(Qt.Checked if si else Qt.Unchecked)

    def accept(self):
        self.applicati = 0
        for i, (k, _v, nuovo) in enumerate(self.diff):
            if self.tab.item(i, 0).checkState() == Qt.Checked:
                self.pratica.set(k, nuovo)
                self.applicati += 1
        self.pratica.salva()
        super().accept()

    def ricompila_altri(self):
        return bool(self.ricompila and self.ricompila.isChecked())
