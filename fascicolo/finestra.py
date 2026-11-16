"""Finestra principale di Fascicolo."""
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QDir, QUrl, QFileSystemWatcher, QEvent
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QMainWindow, QDialog, QComboBox, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QTabWidget, QStackedWidget, QScrollArea, QFormLayout,
                               QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
                               QFileDialog, QTreeView, QFileSystemModel, QInputDialog, QCheckBox, QPlainTextEdit,
                               QGroupBox, QSplitter, QSizePolicy)

from . import core, xfa
from .schema import SEZIONI, CAMPI
from .widgets import Campo
from .dialoghi import NuovaPratica, DatiMancanti, Comuni, SceltaRubrica, InsegnaModulo, AggiornaDati


def bottone(testo, slot, primario=False, tip=None):
    b = QPushButton(testo)
    if primario:
        b.setObjectName("primario")
    if tip:
        b.setToolTip(tip)
    b.clicked.connect(slot)
    return b


# =========================================================================== scheda dati

class SchedaDati(QWidget):
    def __init__(self, finestra):
        super().__init__()
        self.f = finestra
        self.pratica = None
        self.widget = {}       # chiave -> Campo
        self.pagine = {}       # sezione -> widget
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)
        self.nav = QListWidget()
        self.nav.setObjectName("navSezioni")
        self.nav.setFixedWidth(210)
        lay.addWidget(self.nav)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        comuni = [c["nome"] for c in finestra.archivio.comuni()]
        for s in SEZIONI:
            self.nav.addItem(s["l"])
            self.stack.addWidget(self._pagina(s, comuni))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self._salva)

    def _pagina(self, s, comuni):
        area = QScrollArea()
        area.setWidgetResizable(True)
        cont = QWidget()
        cont.setObjectName("scheda")
        v = QVBoxLayout(cont)
        v.setContentsMargins(22, 18, 22, 18)
        h = QHBoxLayout()
        t = QLabel(s["l"])
        t.setObjectName("titoloSezione")
        h.addWidget(t)
        h.addStretch()
        if s.get("rubrica"):
            h.addWidget(bottone("Prendi dalla rubrica…", lambda _=0, s=s: self._da_rubrica(s)))
            h.addWidget(bottone("Salva in rubrica", lambda _=0, s=s: self._in_rubrica(s)))
        v.addLayout(h)
        if s["k"] == "societa":
            self.avviso_soc = QLabel("Questa sezione serve solo se nel Titolare hai scelto «Società». "
                                     "In quel caso il Titolare è il legale rappresentante.")
            self.avviso_soc.setObjectName("avviso")
            self.avviso_soc.setWordWrap(True)
            v.addWidget(self.avviso_soc)
        if s["k"] == "dl":
            self.avviso_dl = QLabel("Con «È lo stesso del progettista» attivo, i moduli usano i dati del Progettista.")
            self.avviso_dl.setObjectName("nota")
            v.addWidget(self.avviso_dl)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(9)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for c in s["campi"]:
            k = f"{s['k']}.{c['k']}"
            w = Campo(c, comuni)
            w.cambiato.connect(lambda k=k: self._cambiato(k))
            self.widget[k] = w
            if c.get("t") == "bool":
                form.addRow("", w)
            else:
                lab = QLabel(c["l"] + ("" if c.get("opz") else ""))
                lab.setObjectName("etichetta")
                lab.setWordWrap(True)
                lab.setMaximumWidth(260)
                form.addRow(lab, w)
        v.addLayout(form)
        v.addStretch()
        area.setWidget(cont)
        return area

    # ------------------------------------------------------------------ carica / salva
    def carica(self, pratica):
        self.pratica = pratica
        for k, w in self.widget.items():
            if w.t == "table":
                pre = k + "."
                w.imposta({kk[len(pre):]: vv for kk, vv in pratica.valori.items() if kk.startswith(pre)})
            else:
                w.imposta(pratica.grezzo(k))
        self._aggiorna_stato()

    def _cambiato(self, k):
        if not self.pratica:
            return
        w = self.widget[k]
        val = w.valore()
        if w.t == "table":
            for kk, vv in val.items():
                self.pratica.set(f"{k}.{kk}", vv)
        else:
            self.pratica.set(k, val)
        if k in ("titolare.tipo", "dl.uguale", "pratica.nome", "pratica.comune"):
            self._aggiorna_stato()
            self.f.aggiorna_intestazione()
        if k == "pratica.comune" and not self.pratica.valori.get("immobile.comune"):
            self.pratica.set("immobile.comune", val)
            self.widget["immobile.comune"].imposta(val)
        self.timer.start()

    def _salva(self):
        if self.pratica:
            self.pratica.salva()
            self.f.stato(f"Salvato alle {datetime.now():%H:%M:%S}")

    def salva_subito(self):
        if self.timer.isActive():
            self.timer.stop()
            self._salva()

    def _aggiorna_stato(self):
        soc = self.pratica.get("titolare.tipo") == "Società"
        self.avviso_soc.setVisible(not soc)
        for k, w in self.widget.items():
            if k.startswith("societa."):
                w.setEnabled(soc)
        uguale = bool(self.pratica.grezzo("dl.uguale"))
        for k, w in self.widget.items():
            if k.startswith("dl.") and k not in ("dl.uguale", "dl.presenta"):
                w.setEnabled(not uguale)

    def evidenzia(self, chiavi):
        for k, w in self.widget.items():
            w.segna_mancante(k in chiavi)

    def vai_a(self, chiave):
        sez = chiave.split(".")[0]
        for i, s in enumerate(SEZIONI):
            if s["k"] == sez:
                self.nav.setCurrentRow(i)
                self.widget[chiave].w.setFocus()

    # ------------------------------------------------------------------ rubrica
    def _valori_sezione(self, s):
        return {c["k"]: self.pratica.grezzo(f"{s['k']}.{c['k']}") for c in s["campi"]
                if c.get("t") != "table" and c["k"] not in ("uguale", "presenta", "anche_dl", "altri", "tipo", "qualita")}

    def _in_rubrica(self, s):
        if not self.pratica:
            return
        vals = self._valori_sezione(s)
        prop = " ".join(x for x in [vals.get("titolo", ""), vals.get("cognome", ""), vals.get("nome", "")] if x).strip() \
            or vals.get("denominazione", "")
        nome, ok = QInputDialog.getText(self, "Salva in rubrica", "Nome della voce in rubrica:", text=prop)
        if not ok or not nome.strip():
            return
        r = self.f.archivio.rubrica()
        r.setdefault(s["rubrica"], {})[nome.strip()] = vals
        self.f.archivio.salva_rubrica(r)
        self.f.stato(f"«{nome}» salvato in rubrica")

    def _da_rubrica(self, s):
        if not self.pratica:
            return
        r = self.f.archivio.rubrica()
        voci = r.get(s["rubrica"], {})
        if not voci:
            QMessageBox.information(self, "Rubrica", "La rubrica è vuota per questa categoria.\n"
                                    "Compila i dati una volta e usa «Salva in rubrica».")
            return
        d = SceltaRubrica(list(voci), f"Rubrica – {s['l']}", self)

        def elimina():
            n = d.scelto()
            if n and QMessageBox.question(d, "Rubrica", f"Eliminare «{n}» dalla rubrica?") == QMessageBox.Yes:
                voci.pop(n, None)
                self.f.archivio.salva_rubrica(r)
                d.lista.takeItem(d.lista.currentRow())
        d.elimina.clicked.connect(elimina)
        if d.exec() and d.scelto():
            for kk, vv in voci[d.scelto()].items():
                k = f"{s['k']}.{kk}"
                if k in CAMPI:
                    self.pratica.set(k, vv)
            self.pratica.salva()
            self.carica(self.pratica)
            self.f.stato(f"Dati di «{d.scelto()}» inseriti")


# =========================================================================== scheda moduli

class SceltaModulo(QDialog):
    """Elenco dei moduli disponibili, con ricerca."""

    def __init__(self, moduli, gia, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scegli il modulo da compilare")
        self.resize(560, 560)
        lay = QVBoxLayout(self)
        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca un modulo…")
        lay.addWidget(self.cerca)
        self.lista = QListWidget()
        gruppo = None
        for m in moduli:
            if m.gruppo != gruppo:
                gruppo = m.gruppo
                h = QListWidgetItem(gruppo or "Altro")
                h.setFlags(Qt.NoItemFlags)
                f = h.font()
                f.setBold(True)
                h.setFont(f)
                self.lista.addItem(h)
            it = QListWidgetItem(("    " + m.titolo) + ("   ✓ già nella pratica" if m.id in gia else ""))
            it.setData(Qt.UserRole, m.id)
            self.lista.addItem(it)
        self.lista.itemDoubleClicked.connect(lambda *_: self.accept())
        self.cerca.textChanged.connect(self._filtra)
        lay.addWidget(self.lista)
        box = QHBoxLayout()
        box.addStretch()
        b = bottone("Compila", self.accept, True)
        box.addWidget(b)
        box.addWidget(bottone("Annulla", self.reject))
        lay.addLayout(box)

    def _filtra(self, t):
        t = t.lower()
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            if it.data(Qt.UserRole):
                it.setHidden(bool(t) and t not in it.text().lower())

    def scelto(self):
        it = self.lista.currentItem()
        return it.data(Qt.UserRole) if it else None


class SchedaModuli(QWidget):
    """I moduli di questa pratica: uno per riga, con dove è salvato e i pulsanti per aprirlo o spostarlo."""

    def __init__(self, finestra):
        super().__init__()
        self.f = finestra
        self.pratica = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        h = QHBoxLayout()
        h.addWidget(bottone("+  Compila un modulo", self.nuovo, True,
                            tip="Scegli un modulo: si apre già con i dati della pratica, completalo nel PDF"))
        h.addWidget(bottone("Carica un modulo già compilato…", self.carica_compilato))
        h.addStretch()
        lay.addLayout(h)
        n = QLabel("Il modulo si apre nel tuo programma PDF già compilato con i dati della pratica: completalo e salvalo. "
                   "Fascicolo legge i dati nuovi e li usa per gli altri moduli.")
        n.setObjectName("nota")
        n.setWordWrap(True)
        lay.addWidget(n)
        area = QScrollArea()
        area.setWidgetResizable(True)
        self.contenitore = QWidget()
        self.contenitore.setObjectName("scheda")
        self.righe = QVBoxLayout(self.contenitore)
        self.righe.setContentsMargins(14, 10, 14, 10)
        self.righe.setSpacing(6)
        area.setWidget(self.contenitore)
        lay.addWidget(area, 1)
        self.vuoto = QLabel("Nessun modulo in questa pratica. Premi «Compila un modulo» per iniziare.")
        self.vuoto.setObjectName("nota")
        self.vuoto.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.vuoto)

    def _titolo(self, mod_id):
        if mod_id.startswith("xfa:"):
            return mod_id[4:] + "  (modulo del portale)"
        m = self.f._modulo_per_id(mod_id)
        return m.titolo if m else mod_id

    def carica(self, pratica):
        self.pratica = pratica
        while self.righe.count():
            it = self.righe.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        voci = list(pratica.dati.get("_moduli", {}).items())
        ordine = {m.id: m.map.get("ordine", 500) for m in core.elenco_moduli(self.f.archivio)}
        voci.sort(key=lambda kv: (ordine.get(kv[0], 900), kv[0]))
        self.vuoto.setVisible(not voci)
        for mod_id, info in voci:
            riga = QWidget()
            h = QHBoxLayout(riga)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(8)
            t = QLabel(self._titolo(mod_id))
            t.setFixedWidth(320)
            t.setWordWrap(True)
            t.setToolTip(f"Ultima modifica: {info.get('data', '')}")
            h.addWidget(t)
            f = pratica.file_modulo(mod_id)
            casella = QLineEdit(str(f))
            casella.setReadOnly(True)
            casella.setCursorPosition(0)
            casella.setToolTip(str(f))
            if not f.exists():
                casella.setProperty("mancante", "true")
                casella.setToolTip("File non trovato: " + str(f))
            h.addWidget(casella, 1)
            h.addWidget(bottone("Scegli dove salvarlo…", lambda _=0, k=mod_id: self.sposta(k)))
            h.addWidget(bottone("Apri", lambda _=0, k=mod_id: self.apri(k), True))
            self.righe.addWidget(riga)
            riga.show()
        self.righe.addStretch()
        self.righe.activate()

    # ------------------------------------------------------------------
    def nuovo(self):
        if not self.pratica:
            return
        self.f.scheda_dati.salva_subito()
        moduli = [m for m in core.elenco_moduli(self.f.archivio) if m.mappato]
        moduli.sort(key=lambda m: m.map.get("ordine", 500))
        d = SceltaModulo(moduli, set(self.pratica.dati.get("_moduli", {})), self)
        if not d.exec() or not d.scelto():
            return
        self.apri(d.scelto())

    def apri(self, mod_id):
        """Apre il modulo nel programma PDF; se non c'è ancora, o se i dati della pratica sono cambiati,
        prima lo compila (le parti scritte a mano nel PDF restano)."""
        if not self.pratica:
            return
        self.f.scheda_dati.salva_subito()
        self.f.controlla_pdf_modificati()  # prima leggo eventuali modifiche fatte nel PDF
        f = self.pratica.file_modulo(mod_id)
        m = None if mod_id.startswith("xfa:") else self.f._modulo_per_id(mod_id)
        info = self.pratica.dati.get("_moduli", {}).get(mod_id, {})
        da_fare = m is not None and (not f.exists() or
                                     float(self.pratica.dati.get("_ts_dati", 0)) > float(info.get("ts", 0)))
        if da_fare:
            try:
                f, _res = core.genera(self.pratica, m)
            except Exception as e:  # noqa – ad esempio il PDF è aperto in Acrobat
                if not f.exists():
                    QMessageBox.critical(self, "Compila", f"Non riesco a creare il modulo:\n{e}")
                    return
                self.f.stato(f"Non ho potuto aggiornare il PDF (è aperto?): lo apro com'è")
            self.f._sorveglia()
            self.carica(self.pratica)
        if not f.exists():
            QMessageBox.warning(self, "Apri", f"Il file non si trova più:\n{f}")
            return
        core.apri_con_sistema(f)
        self.f.stato(f"Aperto {f.name}: quando lo salvi, leggo i dati nuovi")

    def sposta(self, mod_id):
        attuale = self.pratica.cartella_modulo(mod_id)
        d = QFileDialog.getExistingDirectory(self, f"Dove salvare «{self._titolo(mod_id)}»",
                                             str(attuale if attuale.exists() else self.pratica.cartella))
        if not d:
            return
        try:
            nuovo = core.cambia_cartella_modulo(self.pratica, mod_id, d)
        except Exception as e:  # noqa
            QMessageBox.warning(self, "Sposta", f"Non riesco a spostare il file (forse è aperto):\n{e}")
            return
        self.f._sorveglia()
        self.carica(self.pratica)
        self.f.stato(f"Salvato in {nuovo.parent}")

    def carica_compilato(self):
        if not self.pratica:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Carica moduli già compilati", "", "PDF (*.pdf)")
        for f in files:
            self.f.importa_pdf(Path(f))
        self.carica(self.pratica)


TIPI_ALLEGATO = ["", "Carta d'identità", "Patente", "Codice fiscale / tessera sanitaria", "Passaporto",
                 "Visura catastale", "Visura tavolare", "Estratto mappa", "Atto di proprietà", "Delega / procura",
                 "Ricevuta di pagamento", "Fotografie", "Elaborato grafico", "Relazione", "Altro"]


class SchedaAllegati(QWidget):
    """Documenti da tenere con la pratica: documenti d'identità, codici fiscali, visure, foto…"""

    def __init__(self, finestra):
        super().__init__()
        self.f = finestra
        self.pratica = None
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        h = QHBoxLayout()
        h.addWidget(bottone("+  Aggiungi file…", self.aggiungi, True))
        h.addWidget(bottone("Apri", self.apri))
        h.addWidget(bottone("Togli dalla pratica", self.togli))
        h.addStretch()
        h.addWidget(bottone("Apri cartella allegati", self.apri_cartella))
        lay.addLayout(h)
        n = QLabel("Qualsiasi file (PDF, foto, Word…): carte d'identità, patenti, codici fiscali, visure, deleghe. "
                   "Puoi anche trascinarli qui. Vengono copiati nella cartella Allegati della pratica.")
        n.setObjectName("nota")
        n.setWordWrap(True)
        lay.addWidget(n)
        self.tab = QTableWidget(0, 4)
        self.tab.setHorizontalHeaderLabels(["File", "Tipo di documento", "Note", "Aggiunto il"])
        self.tab.verticalHeader().setVisible(False)
        self.tab.setSelectionBehavior(QAbstractItemView.SelectRows)
        hh = self.tab.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tab.setColumnWidth(1, 250)
        self.tab.verticalHeader().setDefaultSectionSize(36)
        self.tab.cellDoubleClicked.connect(lambda r, c: c == 0 and self.apri())
        self.tab.itemChanged.connect(self._nota_cambiata)
        lay.addWidget(self.tab, 1)

    def _cartella(self):
        d = self.pratica.cartella / "Allegati"
        d.mkdir(exist_ok=True)
        return d

    def _meta(self):
        return self.pratica.dati.setdefault("_allegati", {})

    def carica(self, pratica):
        self.pratica = pratica
        meta = self._meta()
        files = sorted([f for f in self._cartella().iterdir() if f.is_file() and not f.name.startswith(".")],
                       key=lambda f: f.name.lower())
        self.tab.blockSignals(True)
        self.tab.setRowCount(len(files))
        for r, f in enumerate(files):
            info = meta.get(f.name, {})
            it = QTableWidgetItem(f.name)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it.setData(Qt.UserRole, f.name)
            self.tab.setItem(r, 0, it)
            cb = QComboBox()
            cb.setEditable(True)
            cb.addItems(TIPI_ALLEGATO)
            cb.setEditText(info.get("tipo", ""))
            cb.currentTextChanged.connect(lambda t, n=f.name: self._imposta(n, "tipo", t))
            self.tab.setCellWidget(r, 1, cb)
            self.tab.setItem(r, 2, QTableWidgetItem(info.get("nota", "")))
            d = info.get("data") or datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y")
            it = QTableWidgetItem(d)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.tab.setItem(r, 3, it)
        self.tab.blockSignals(False)

    def _imposta(self, nome, chiave, valore):
        self._meta().setdefault(nome, {})[chiave] = valore
        self.pratica.salva()

    def _nota_cambiata(self, it):
        if it.column() == 2:
            nome = self.tab.item(it.row(), 0).data(Qt.UserRole)
            self._imposta(nome, "nota", it.text().strip())

    def _selezionati(self):
        righe = sorted({i.row() for i in self.tab.selectedIndexes()})
        return [self.tab.item(r, 0).data(Qt.UserRole) for r in righe]

    def aggiungi(self, files=None):
        if not self.pratica:
            return
        if not files:
            files, _ = QFileDialog.getOpenFileNames(self, "Aggiungi documenti alla pratica", "",
                                                    "Tutti i file (*.*);;PDF (*.pdf);;Immagini (*.jpg *.jpeg *.png *.tif *.tiff *.heic)")
        if not files:
            return
        dest = self._cartella()
        for f in files:
            src = Path(f)
            nome = src.name
            n = 2
            while (dest / nome).exists():
                nome = f"{src.stem} ({n}){src.suffix}"
                n += 1
            shutil.copy2(src, dest / nome)
            self._meta()[nome] = {"tipo": "", "nota": "", "data": datetime.now().strftime("%d/%m/%Y")}
        self.pratica.salva()
        self.carica(self.pratica)
        self.f.stato(f"Aggiunti {len(files)} allegati")

    def apri(self):
        for n in self._selezionati():
            core.apri_con_sistema(self._cartella() / n)

    def apri_cartella(self):
        if self.pratica:
            core.apri_con_sistema(self._cartella())

    def togli(self):
        sel = self._selezionati()
        if not sel:
            return
        if QMessageBox.question(self, "Togli allegati",
                                f"Togliere {len(sel)} file dalla pratica?\n"
                                "Non vengono cancellati: finiscono nella cartella Allegati/_tolti.") != QMessageBox.Yes:
            return
        cest = self._cartella() / "_tolti"
        cest.mkdir(exist_ok=True)
        for n in sel:
            try:
                shutil.move(str(self._cartella() / n), str(cest / n))
                self._meta().pop(n, None)
            except OSError as e:
                QMessageBox.warning(self, "Togli", f"{n}: {e}")
        self.pratica.salva()
        self.carica(self.pratica)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile() and Path(u.toLocalFile()).is_file()]
        if files:
            self.aggiungi(files)



# =========================================================================== finestra

class Finestra(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = core.carica_config()
        self.archivio = core.Archivio(self.cfg["archivio"])
        self.pratica = None
        self.setWindowTitle("Fascicolo – pratiche edilizie")
        self.resize(1320, 840)

        centro = QWidget()
        root = QHBoxLayout(centro)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(centro)

        # barra laterale -------------------------------------------------
        barra = QWidget()
        barra.setObjectName("barra")
        barra.setFixedWidth(280)
        bl = QVBoxLayout(barra)
        bl.setContentsMargins(14, 16, 14, 14)
        t = QLabel("Fascicolo")
        t.setObjectName("titoloApp")
        bl.addWidget(t)
        st = QLabel("Pratiche edilizie e modulistica")
        st.setObjectName("sottotitoloApp")
        bl.addWidget(st)
        bl.addSpacing(10)
        bl.addWidget(bottone("+  Nuova pratica", self.nuova, True))
        bl.addSpacing(6)
        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca pratica, comune, titolare…")
        self.cerca.textChanged.connect(self._filtra)
        bl.addWidget(self.cerca)
        self.lista = QListWidget()
        self.lista.setObjectName("listaPratiche")
        self.lista.currentItemChanged.connect(self._seleziona)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista.setWordWrap(True)
        self.lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_pratica)
        bl.addWidget(self.lista, 1)
        hp = QHBoxLayout()
        hp.setSpacing(4)
        for testo, slot, tip in (("Modifica", self.modifica_pratica, "Cambia nome e comune della pratica"),
                                 ("Duplica", self.duplica_pratica, "Crea una nuova pratica con gli stessi dati"),
                                 ("Elimina", self.elimina_pratica, "Sposta la pratica nel cestino dell'archivio")):
            b = bottone(testo, slot, tip=tip)
            b.setObjectName("piccolo")
            hp.addWidget(b)
        bl.addLayout(hp)
        bl.addSpacing(8)
        bl.addWidget(bottone("Comuni", self.comuni))
        bl.addWidget(bottone("Cartella archivio…", self.scegli_archivio))
        self.lbl_archivio = QLabel()
        self.lbl_archivio.setObjectName("sottotitoloApp")
        self.lbl_archivio.setWordWrap(True)
        bl.addWidget(self.lbl_archivio)
        root.addWidget(barra)

        # area principale -----------------------------------------------
        destra = QWidget()
        dl = QVBoxLayout(destra)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(0)
        inte = QWidget()
        inte.setObjectName("intestazione")
        il = QHBoxLayout(inte)
        il.setContentsMargins(22, 14, 22, 14)
        col = QVBoxLayout()
        self.nome = QLabel("Nessuna pratica selezionata")
        self.nome.setObjectName("nomePratica")
        self.info = QLabel("Crea una nuova pratica o selezionane una dall'elenco.")
        self.info.setObjectName("infoPratica")
        col.addWidget(self.nome)
        col.addWidget(self.info)
        il.addLayout(col, 1)
        self.b_cartella = bottone("Apri cartella", lambda: self.pratica and core.apri_con_sistema(self.pratica.cartella))
        il.addWidget(self.b_cartella)
        dl.addWidget(inte)

        self.tabs = QTabWidget()
        self.scheda_dati = SchedaDati(self)
        self.scheda_moduli = SchedaModuli(self)
        self.scheda_allegati = SchedaAllegati(self)
        self.tabs.addTab(self.scheda_dati, "Dati pratica")
        self.tabs.addTab(self.scheda_moduli, "Moduli")
        self.tabs.addTab(self.scheda_allegati, "Allegati")
        self.tabs.currentChanged.connect(self._cambio_tab)
        dl.addWidget(self.tabs, 1)
        root.addWidget(destra, 1)
        self.statusBar().showMessage("Pronto")

        self.tabs.setEnabled(False)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda *_: self.t_controllo.start())
        self.watcher.fileChanged.connect(lambda *_: self.t_controllo.start())
        self.t_controllo = QTimer(self)
        self.t_controllo.setSingleShot(True)
        self.t_controllo.setInterval(1500)
        self.t_controllo.timeout.connect(self.controlla_pdf_modificati)
        self._in_controllo = False
        self.ricarica_elenco()

    # ------------------------------------------------------------------ PDF scritti fuori dal programma
    def _sorveglia(self):
        vecchi = self.watcher.files() + self.watcher.directories()
        if vecchi:
            self.watcher.removePaths(vecchi)
        if not self.pratica:
            return
        for d in self.pratica.cartelle_in_uso():
            if d.exists():
                self.watcher.addPath(str(d))
        pdf = [str(self.pratica.file_modulo(k)) for k in self.pratica.dati.get("_moduli", {})
               if self.pratica.file_modulo(k).exists()]
        if pdf:
            self.watcher.addPaths(pdf)

    def changeEvent(self, e):
        if e.type() == QEvent.ActivationChange and self.isActiveWindow() and self.pratica:
            self.t_controllo.start(300)
        super().changeEvent(e)

    def _modulo_per_id(self, mod_id):
        for m in core.elenco_moduli(self.archivio):
            if m.id == mod_id:
                return m
        return None

    def _rivedi_dati(self, modulo, pdf, intro=None):
        """Legge un PDF compilato e propone i dati diversi. Ritorna True se ha cambiato la pratica."""
        try:
            prop = core.estrai_dati(self.pratica, modulo, core.leggi_valori(pdf))
        except Exception as e:  # noqa
            QMessageBox.warning(self, "Lettura PDF", f"Non riesco a leggere «{Path(pdf).name}»:\n{e}")
            return False
        return self._rivedi_proposte(modulo.titolo, prop, intro, escludi=modulo.id)

    def _rivedi_proposte(self, titolo, prop, intro=None, escludi=None):
        diff = core.differenze(self.pratica, prop)
        if not diff:
            self.stato(f"«{titolo}»: nessun dato nuovo da salvare")
            return False
        fatti = self.pratica.dati.get("_moduli", {})
        altri = [m for m in core.elenco_moduli(self.archivio) if m.id in fatti and m.id != escludi and m.mappato]
        d = AggiornaDati(self.pratica, diff, titolo, intro, len(altri), self)
        if not d.exec() or not d.applicati:
            return False
        self.scheda_dati.carica(self.pratica)
        self.aggiorna_intestazione()
        if d.ricompila_altri():
            errori = []
            for m in altri:
                try:
                    core.genera(self.pratica, m)
                except Exception as e:  # noqa – ad esempio il PDF è aperto in Acrobat
                    errori.append(f"{m.titolo}: {e}")
            if errori:
                QMessageBox.warning(self, "Aggiornamento moduli",
                                    "Alcuni moduli non sono stati aggiornati (forse sono aperti in un altro "
                                    "programma):\n\n" + "\n".join(errori))
        self.stato(f"Salvati {d.applicati} dati da «{titolo}»")
        return True

    def _rivedi_xfa(self, pdf, intro):
        titolo, prop = xfa.estrai(pdf)
        if titolo is None:
            return False
        return self._rivedi_proposte(f"{titolo} ({Path(pdf).name})", prop, intro)

    def controlla_pdf_modificati(self):
        if not self.pratica or self._in_controllo:
            return
        self._in_controllo = True
        try:
            for mod_id, f in core.moduli_modificati(self.pratica):
                core.segna_letto(self.pratica, mod_id)
                self.pratica.salva()
                if mod_id.startswith("xfa:"):
                    self._rivedi_xfa(f, f"Hai modificato e salvato <b>{f.name}</b> (modulo del portale). "
                                        "Questi dati sono diversi da quelli della pratica: scegli quali salvare.")
                    continue
                m = self._modulo_per_id(mod_id)
                if m and m.mappato:
                    self._rivedi_dati(m, f, f"Hai modificato e salvato il PDF <b>{m.titolo}</b>. "
                                            "Questi dati sono diversi da quelli della pratica: scegli quali salvare.")
            self._sorveglia()
            w = self.tabs.currentWidget()
            if w is not self.scheda_dati and self.pratica:
                w.carica(self.pratica)
        finally:
            self._in_controllo = False

    def importa_pdf(self, pdf):
        moduli = core.elenco_moduli(self.archivio)
        try:
            n_campi = len(core.firma_campi(pdf)[1])
        except Exception as e:  # noqa
            QMessageBox.warning(self, "Carica modulo", f"Non riesco ad aprire «{pdf.name}»:\n{e}")
            return
        m, _punteggio = core.riconosci_modulo(pdf, moduli)
        if not m and n_campi == 0 and xfa.leggi_datasets(pdf):
            titolo, _p = xfa.estrai(pdf)
            self._in_controllo = True
            try:
                _chiave, out = core.importa_xfa(self.pratica, pdf)
            finally:
                self._in_controllo = False
            self._sorveglia()
            self._rivedi_xfa(out, f"<b>{pdf.name}</b> è un modulo dinamico del portale "
                                  f"(<i>{titolo}</i>): l'ho messo nella cartella Moduli della pratica. "
                                  "Questi sono i dati che ho letto: scegli quali salvare. "
                                  "Il file resta modificabile solo con Adobe Acrobat/Reader; "
                                  "se lo correggi e lo salvi, rileggo i dati.")
            self.stato(f"«{pdf.name}» caricato come modulo del portale")
            return
        if not m and n_campi == 0:
            r = QMessageBox.question(
                self, "PDF senza campi compilabili",
                f"«{pdf.name}» non contiene campi compilabili: probabilmente è stato stampato in PDF, "
                "appiattito o firmato digitalmente, quindi i dati non si possono leggere.\n\n"
                "Vuoi copiarlo comunque negli Allegati della pratica?")
            if r == QMessageBox.Yes:
                shutil.copy2(pdf, self.pratica.cartella / "Allegati" / pdf.name)
            return
        if not m:
            # versione diversa del modulo: lascio scegliere, ordinando per campi in comune
            cand = sorted((x for x in moduli if x.mappato), key=lambda x: -core.campi_in_comune(pdf, x))
            voci = [f"{x.titolo}  ({core.campi_in_comune(pdf, x)} campi in comune)" for x in cand]
            voci.append("Nessuno: copialo negli Allegati")
            scelta, ok = QInputDialog.getItem(
                self, "Modulo non riconosciuto",
                f"«{pdf.name}» ha {n_campi} campi ma non coincide con nessun modello di Fascicolo\n"
                "(forse è una versione diversa del modulo). A quale modulo corrisponde?\n"
                "Leggerò i campi che hanno lo stesso nome.", voci, 0, False)
            if not ok:
                return
            if scelta == voci[-1]:
                shutil.copy2(pdf, self.pratica.cartella / "Allegati" / pdf.name)
                self.stato(f"«{pdf.name}» copiato negli Allegati")
                return
            m = cand[voci.index(scelta)]
        self._in_controllo = True
        try:
            out = core.importa_modulo(self.pratica, m, pdf)
        finally:
            self._in_controllo = False
        self._sorveglia()
        if m.mappato:
            self._rivedi_dati(m, out, f"Ho caricato <b>{m.titolo}</b> nella pratica. Questi sono i dati trovati "
                                      "nel PDF che mancano o sono diversi nella pratica: scegli quali salvare.")
        self.stato(f"«{pdf.name}» caricato come «{m.titolo}»")

    # ------------------------------------------------------------------
    def stato(self, msg):
        self.statusBar().showMessage(msg, 6000)

    def ricarica_elenco(self, seleziona=None):
        self.lbl_archivio.setText(str(self.archivio.radice))
        self.lista.blockSignals(True)
        self.lista.clear()
        for p in reversed(self.archivio.pratiche()):
            it = QListWidgetItem(f"{p.cartella.name}\n{p.valori.get('pratica.comune', '')}")
            it.setData(Qt.UserRole, str(p.cartella))
            tit = " ".join([p.valori.get("titolare.cognome", ""), p.valori.get("titolare.nome", ""),
                            p.valori.get("societa.denominazione", "")])
            it.setData(Qt.UserRole + 1, (p.cartella.name + " " + p.valori.get("pratica.comune", "") + " " + tit).lower())
            self.lista.addItem(it)
        self.lista.blockSignals(False)
        if seleziona:
            for i in range(self.lista.count()):
                if self.lista.item(i).data(Qt.UserRole) == str(seleziona):
                    self.lista.setCurrentRow(i)
        self._filtra(self.cerca.text())

    def _filtra(self, t):
        t = t.lower()
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            it.setHidden(bool(t) and t not in it.data(Qt.UserRole + 1))

    def _seleziona(self, it, _prev=None):
        if self.pratica:
            self.scheda_dati.salva_subito()
        if not it:
            return
        self.pratica = core.Pratica(it.data(Qt.UserRole))
        self.pratica.archivio = self.archivio
        self.tabs.setEnabled(True)
        self.scheda_dati.carica(self.pratica)
        self.scheda_dati.evidenzia(set())
        self.aggiorna_intestazione()
        self._cambio_tab(self.tabs.currentIndex())
        self._sorveglia()
        self.t_controllo.start(300)

    def aggiorna_intestazione(self):
        p = self.pratica
        if not p:
            return
        self.nome.setText(p.valori.get("pratica.nome") or p.cartella.name)
        tit = p.get("societa.denominazione") if p.get("titolare.tipo") == "Società" else \
            f"{p.get('titolare.cognome')} {p.get('titolare.nome')}".strip()
        parti = [x for x in [p.get("pratica.comune"), tit, p.cartella.name] if x]
        self.info.setText("  ·  ".join(parti))

    def _cambio_tab(self, i):
        if not self.pratica:
            return
        self.scheda_dati.salva_subito()
        w = self.tabs.widget(i)
        if w is not self.scheda_dati:
            w.carica(self.pratica)

    def nuova(self):
        d = NuovaPratica([c["nome"] for c in self.archivio.comuni()], self)
        if d.exec():
            p = self.archivio.nuova(d.nome.text().strip(), d.comune.currentText().strip())
            if d.cartella_moduli():
                core.cambia_cartella_moduli(p, d.cartella_moduli())
            self.ricarica_elenco(seleziona=p.cartella)
            self.tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------ gestione pratiche
    def _menu_pratica(self, pos):
        it = self.lista.itemAt(pos)
        if not it:
            return
        self.lista.setCurrentItem(it)
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("Modifica nome e comune…", self.modifica_pratica)
        m.addAction("Duplica…", self.duplica_pratica)
        m.addAction("Apri la cartella", lambda: self.pratica and core.apri_con_sistema(self.pratica.cartella))
        m.addSeparator()
        m.addAction("Elimina…", self.elimina_pratica)
        m.exec(self.lista.mapToGlobal(pos))

    def _comuni(self):
        return [c["nome"] for c in self.archivio.comuni()]

    def _rilascia_file(self):
        """Smette di sorvegliare i file della pratica (su Windows altrimenti non si possono spostare)."""
        self.scheda_dati.salva_subito()
        vecchi = self.watcher.files() + self.watcher.directories()
        if vecchi:
            self.watcher.removePaths(vecchi)

    def modifica_pratica(self):
        p = self.pratica
        if not p:
            return
        d = NuovaPratica(self._comuni(), self, "Modifica pratica", p.valori.get("pratica.nome", p.cartella.name),
                         p.valori.get("pratica.comune", ""), "Anche la cartella della pratica prende il nuovo nome.",
                         testo_ok="Salva")
        if not d.exec():
            return
        self._rilascia_file()
        try:
            self.archivio.modifica(p, d.nome.text().strip(), d.comune.currentText().strip())
        except OSError as e:
            QMessageBox.warning(self, "Modifica pratica",
                                f"Dati salvati, ma non riesco a rinominare la cartella (forse un file è aperto):\n{e}")
        self.ricarica_elenco(seleziona=p.cartella)

    def duplica_pratica(self):
        p = self.pratica
        if not p:
            return
        d = NuovaPratica(self._comuni(), self, "Duplica pratica", p.valori.get("pratica.nome", "") + " (copia)",
                         p.valori.get("pratica.comune", ""),
                         "Viene creata una nuova pratica con tutti i dati di questa (titolare, immobile, tecnici…).",
                         duplica=True, testo_ok="Duplica")
        if not d.exec():
            return
        self.scheda_dati.salva_subito()
        nuova = self.archivio.duplica(p, d.nome.text().strip(), d.comune.currentText().strip(),
                                      d.ck_allegati.isChecked(), d.ck_moduli.isChecked())
        self.ricarica_elenco(seleziona=nuova.cartella)
        self.stato(f"Creata la pratica «{nuova.nome}»")

    def elimina_pratica(self):
        p = self.pratica
        if not p:
            return
        fuori = [p.file_modulo(k) for k in p.dati.get("_moduli", {}) if p.cartella_propria(k)]
        extra = (f"\n\nI {len(fuori)} moduli salvati in altre cartelle (es. sul server) non vengono toccati."
                 if fuori else "")
        if QMessageBox.question(self, "Elimina pratica",
                                f"Eliminare la pratica «{p.nome}»?\n\nLa cartella viene spostata nel cestino "
                                f"dell'archivio ({self.archivio.radice / '_cestino'}), da dove puoi recuperarla."
                                + extra) != QMessageBox.Yes:
            return
        self._rilascia_file()
        try:
            self.archivio.elimina(p)
        except OSError as e:
            QMessageBox.warning(self, "Elimina pratica", f"Non riesco a spostare la cartella (forse un file è aperto):\n{e}")
            self._sorveglia()
            return
        self.pratica = None
        self.tabs.setEnabled(False)
        self.nome.setText("Nessuna pratica selezionata")
        self.info.setText("Crea una nuova pratica o selezionane una dall'elenco.")
        self.ricarica_elenco()
        if self.lista.count():
            self.lista.setCurrentRow(0)
        self.stato(f"Pratica «{p.nome}» spostata nel cestino")

    def comuni(self):
        if Comuni(self.archivio, self).exec():
            self.stato("Elenco comuni salvato")
            if self.pratica:
                self._cambio_tab(self.tabs.currentIndex())
            # aggiorna le tendine dei comuni
            nomi = [c["nome"] for c in self.archivio.comuni()]
            w = self.scheda_dati.widget["pratica.comune"].w
            cur = w.currentText()
            w.blockSignals(True)
            w.clear()
            w.addItems([""] + nomi)
            w.setEditText(cur)
            w.blockSignals(False)

    def scegli_archivio(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella dell'archivio pratiche", str(self.archivio.radice))
        if d:
            self.scheda_dati.salva_subito()
            self.cfg["archivio"] = d
            core.salva_config(self.cfg)
            self.archivio = core.Archivio(d)
            self.pratica = None
            self.tabs.setEnabled(False)
            self.ricarica_elenco()

    def closeEvent(self, e):
        self.scheda_dati.salva_subito()
        super().closeEvent(e)
