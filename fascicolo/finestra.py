"""Finestra principale di Fascicolo."""
import os
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QObject, QDir, QUrl, QFileSystemWatcher, QEvent
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QCursor, QAction
from PySide6.QtWidgets import (QMainWindow, QApplication, QToolButton, QDialog, QComboBox, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QTabWidget, QStackedWidget, QScrollArea, QFormLayout,
                               QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
                               QFileDialog, QTreeView, QFileSystemModel, QInputDialog, QCheckBox, QPlainTextEdit,
                               QGroupBox, QSplitter, QSizePolicy)

from . import core, xfa, aggiornamenti, __version__
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

ORDINE_EDIZIONI = ["2026", "2022", "ISTAT / ISPAT"]


class SceltaModulo(QDialog):
    """Moduli disponibili raggruppati: edizione (2026, 2022, ISTAT/ISPAT) › gruppo › modulo."""

    def __init__(self, moduli, gia, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        self.setWindowTitle("Scegli il modulo da compilare")
        self.resize(680, 620)
        lay = QVBoxLayout(self)
        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca un modulo…")
        lay.addWidget(self.cerca)
        self.albero = QTreeWidget()
        self.albero.setColumnCount(2)
        self.albero.setHeaderLabels(["Modulo", "Nella pratica"])
        self.albero.setObjectName("alberoModuli")
        from PySide6.QtWidgets import QHeaderView
        self.albero.header().setStretchLastSection(False)
        self.albero.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.albero.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        quante = {}
        for k in gia:
            b = core.separa_copia(k)[0]
            quante[b] = quante.get(b, 0) + 1
        edizioni = sorted({m.edizione for m in moduli},
                          key=lambda e: (ORDINE_EDIZIONI.index(e) if e in ORDINE_EDIZIONI else 99, e))
        for ed in edizioni:
            nodo_ed = QTreeWidgetItem([f"Moduli {ed}" if ed[:1].isdigit() else ed])
            f = nodo_ed.font(0)
            f.setBold(True)
            f.setPointSize(f.pointSize() + 1)
            nodo_ed.setFont(0, f)
            nodo_ed.setFlags(Qt.ItemIsEnabled)
            self.albero.addTopLevelItem(nodo_ed)
            del_ed = sorted([m for m in moduli if m.edizione == ed], key=lambda m: m.map.get("ordine", 500))
            gruppi = []
            for m in del_ed:
                if m.gruppo not in gruppi:
                    gruppi.append(m.gruppo)
            for g in gruppi:
                padre = nodo_ed
                if len(gruppi) > 1 or g:
                    padre = QTreeWidgetItem([g or "Altro"])
                    padre.setFlags(Qt.ItemIsEnabled)
                    f2 = padre.font(0)
                    f2.setBold(True)
                    padre.setFont(0, f2)
                    nodo_ed.addChild(padre)
                for m in del_ed:
                    if m.gruppo == g:
                        n = quante.get(m.id, 0)
                        it = QTreeWidgetItem([m.titolo, ("✓ già presente" + (f" ({n})" if n > 1 else "")) if n else ""])
                        if n:
                            it.setForeground(1, QColor("#2f7d6d"))
                            it.setToolTip(1, "È già nella pratica: puoi aprirlo oppure compilarne un'altra copia")
                        it.setData(0, Qt.UserRole, m.id)
                        it.setToolTip(0, m.pdf.name)
                        padre.addChild(it)
        self.albero.expandAll()
        self.albero.itemDoubleClicked.connect(lambda it, _c: it.data(0, Qt.UserRole) and self.accept())
        self.cerca.textChanged.connect(self._filtra)
        lay.addWidget(self.albero)
        box = QHBoxLayout()
        box.addStretch()
        box.addWidget(bottone("Compila", self.accept, True))
        box.addWidget(bottone("Annulla", self.reject))
        lay.addLayout(box)

    def _filtra(self, t):
        t = t.lower()

        def visita(it):
            vis = False
            for i in range(it.childCount()):
                vis = visita(it.child(i)) or vis
            if it.data(0, Qt.UserRole):
                vis = not t or t in it.text(0).lower()
            it.setHidden(not vis)
            return vis
        for i in range(self.albero.topLevelItemCount()):
            visita(self.albero.topLevelItem(i))

    def scelto(self):
        it = self.albero.currentItem()
        return it.data(0, Qt.UserRole) if it else None


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
        self.elenco = QListWidget()
        self.elenco.setObjectName("elencoModuli")
        self.elenco.setDragDropMode(QAbstractItemView.InternalMove)
        self.elenco.setDefaultDropAction(Qt.MoveAction)
        self.elenco.setSelectionMode(QAbstractItemView.SingleSelection)
        self.elenco.setDropIndicatorShown(True)
        self.elenco.setSpacing(2)
        self.elenco.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.elenco.model().rowsMoved.connect(self._spostato)
        lay.addWidget(self.elenco, 1)
        self.vuoto = QLabel("Nessun modulo in questa pratica. Premi «Compila un modulo» per iniziare.")
        self.vuoto.setObjectName("nota")
        self.vuoto.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.vuoto)

    def _titolo(self, mod_id):
        if mod_id.startswith("xfa:"):
            return mod_id[4:] + "  (modulo del portale)"
        m = self.f._modulo_per_id(mod_id)
        if not m:
            return mod_id
        return f"{m.titolo}  ·  {m.edizione}"

    def carica(self, pratica):
        self.pratica = pratica
        self.elenco.blockSignals(True)
        self.elenco.clear()
        voci = self._ordinati()
        self.vuoto.setVisible(not voci)
        mano = QCursor(Qt.OpenHandCursor)
        for pos, (mod_id, info) in enumerate(voci):
            riga = QWidget()
            h = QHBoxLayout(riga)
            h.setContentsMargins(6, 4, 8, 4)
            h.setSpacing(8)
            presa = QLabel("⠿")
            presa.setObjectName("presa")
            num = QLabel(f"{pos + 1}")
            num.setObjectName("numero")
            num.setFixedWidth(30)
            num.setAlignment(Qt.AlignCenter)
            t = QLabel(self._titolo(mod_id))
            t.setFixedWidth(330)
            t.setWordWrap(True)
            for x in (presa, num, t):
                x.setCursor(mano)
                x.setToolTip("Tieni premuto e trascina per spostarlo")
                h.addWidget(x)
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
            it = QListWidgetItem()
            it.setData(Qt.UserRole, mod_id)
            it.setSizeHint(QSize(100, max(46, riga.sizeHint().height())))
            self.elenco.addItem(it)
            self.elenco.setItemWidget(it, riga)
        self.elenco.blockSignals(False)

    def _spostato(self, *_):
        """Dopo un trascinamento: salvo il nuovo ordine e ridisegno (numeri aggiornati)."""
        if not self.pratica:
            return
        ordine = [self.elenco.item(i).data(Qt.UserRole) for i in range(self.elenco.count())]
        self.pratica.dati["_ordine_moduli"] = [k for k in ordine if k]
        self.pratica.salva()
        QTimer.singleShot(0, lambda: self.carica(self.pratica))

    def _ordinati(self):
        """Moduli della pratica nell'ordine scelto dall'utente (i nuovi vanno in fondo)."""
        moduli = self.pratica.dati.get("_moduli", {})
        salvato = self.pratica.dati.get("_ordine_moduli", [])
        ordine = [k for k in salvato if k in moduli]
        nuovi = [k for k in moduli if k not in ordine]
        if nuovi or len(ordine) != len(salvato):
            self.pratica.dati["_ordine_moduli"] = ordine + nuovi
            self.pratica.salva()
        return [(k, moduli[k]) for k in ordine + nuovi]

    # ------------------------------------------------------------------
    def nuovo(self):
        if not self.pratica:
            return
        self.f.scheda_dati.salva_subito()
        moduli = [m for m in core.elenco_moduli(self.f.archivio) if m.mappato]
        moduli.sort(key=lambda m: m.map.get("ordine", 500))
        gia = set(self.pratica.dati.get("_moduli", {}))
        d = SceltaModulo(moduli, gia, self)
        if not d.exec() or not d.scelto():
            return
        scelto = d.scelto()
        if scelto in gia:
            m = self.f._modulo_per_id(scelto)
            r = QMessageBox(self)
            r.setWindowTitle("Modulo già nella pratica")
            r.setIcon(QMessageBox.Question)
            r.setText(f"<b>{m.titolo}</b> è già nella pratica.<br><br>Vuoi aprire quello che c'è "
                      "oppure compilarne un'altra copia (ad esempio per un secondo titolare o un'altra impresa)?")
            b_apri = r.addButton("Apri quello che c'è", QMessageBox.AcceptRole)
            b_copia = r.addButton("Compila un'altra copia", QMessageBox.ActionRole)
            r.addButton("Annulla", QMessageBox.RejectRole)
            r.exec()
            if r.clickedButton() is b_copia:
                scelto = m.come_copia(core.prossima_copia(self.pratica, m)).id
            elif r.clickedButton() is not b_apri:
                return
        self.apri(scelto)

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

class _ControlloAggiornamenti(QObject):
    """Controlla GitHub in un thread separato e propone l'aggiornamento."""
    trovato = Signal(object, bool)
    errore = Signal(str, bool)

    def __init__(self, finestra):
        super().__init__(finestra)
        self.f = finestra
        self.trovato.connect(self._trovato)
        self.errore.connect(self._errore)

    def avvia(self, silenzioso):
        import threading

        def lavoro():
            try:
                self.trovato.emit(aggiornamenti.ultima_release(), silenzioso)
            except Exception as e:  # noqa – niente rete, repo privato, limiti GitHub…
                self.errore.emit(str(e), silenzioso)
        if not silenzioso:
            self.f.stato("Controllo aggiornamenti…")
        threading.Thread(target=lavoro, daemon=True).start()

    def _errore(self, msg, silenzioso):
        if silenzioso:
            return
        if "404" in msg:
            QMessageBox.information(self.f, "Aggiornamenti",
                                    "Su GitHub non c'è ancora nessuna versione pubblicata di Fascicolo.")
        else:
            QMessageBox.warning(self.f, "Aggiornamenti",
                                f"Non riesco a controllare gli aggiornamenti (manca la connessione?):\n{msg}")

    def _trovato(self, rel, silenzioso):
        if not aggiornamenti.piu_nuova(rel["versione"]):
            if not silenzioso:
                QMessageBox.information(self.f, "Aggiornamenti", f"Fascicolo {__version__} è già la versione più recente.")
            return
        if silenzioso:
            self.f.stato(f"È disponibile Fascicolo {rel['versione']}: menu ? › Controlla aggiornamenti")
            return
        note = rel["note"].strip()
        testo = (f"È disponibile <b>Fascicolo {rel['versione']}</b> (hai la {__version__}).<br><br>"
                 + (note.replace("\n", "<br>")[:1500] + "<br><br>" if note else ""))
        if not aggiornamenti.installato() or not rel["setup"]:
            testo += "Scarica il nuovo programma di installazione dalla pagina del progetto."
            if QMessageBox.question(self.f, "Aggiornamento disponibile", testo + "<br><br>Apro la pagina?") == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(rel["pagina"]))
            return
        if QMessageBox.question(self.f, "Aggiornamento disponibile",
                                testo + "Vuoi aggiornare adesso? Fascicolo si chiude, si aggiorna e si riapre "
                                        "(le pratiche non vengono toccate).") != QMessageBox.Yes:
            return
        from PySide6.QtWidgets import QProgressDialog
        prog = QProgressDialog("Scarico l'aggiornamento…", "Annulla", 0, 100, self.f)
        prog.setWindowTitle("Aggiornamento")
        prog.setWindowModality(Qt.WindowModal)
        prog.show()
        annullato = {"si": False}

        def avanz(letti, tot):
            if tot:
                prog.setValue(int(letti * 100 / tot))
            QApplication.processEvents()
            if prog.wasCanceled():
                annullato["si"] = True
                raise RuntimeError("annullato")
        try:
            setup = aggiornamenti.scarica(rel["setup"], rel["nome_setup"], avanz)
        except Exception as e:  # noqa
            prog.close()
            if not annullato["si"]:
                QMessageBox.warning(self.f, "Aggiornamento", f"Download non riuscito:\n{e}")
            return
        prog.close()
        self.f.scheda_dati.salva_subito()
        try:
            aggiornamenti.avvia_setup(setup)
        except Exception as e:  # noqa
            QMessageBox.warning(self.f, "Aggiornamento", f"Non riesco ad avviare l'installazione:\n{e}\n\n"
                                                          f"Puoi lanciarla a mano: {setup}")
            return
        # chiudo davvero (salvataggi e "pratica aperta" compresi): finché il programma è vivo
        # i suoi file sono bloccati e l'installazione non potrebbe sostituirli
        self.f.close()
        QApplication.processEvents()
        os._exit(0)


class Finestra(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = core.carica_config()
        if not self.cfg.get("archivio"):
            self.cfg["archivio"] = self._chiedi_archivio()
            core.salva_config(self.cfg)
        self.archivio = core.Archivio(self.cfg["archivio"])
        self.pratica = None
        self.setWindowTitle(f"Fascicolo {__version__} – pratiche edilizie")
        icona = core.APP_DIR / "assets" / "fascicolo.png"
        if icona.exists():
            self.setWindowIcon(QIcon(str(icona)))
        self.resize(1320, 840)
        self._menu()

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
        self.presenza = QLabel()
        self.presenza.setObjectName("avviso")
        self.presenza.setVisible(False)
        col.addWidget(self.presenza)
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
        self._impronta = None
        self.t_sync = QTimer(self)
        self.t_sync.setInterval(8000)
        self.t_sync.timeout.connect(self.sincronizza)
        self.t_sync.start()
        self.ricarica_elenco()
        self._agg = _ControlloAggiornamenti(self)
        QTimer.singleShot(4000, lambda: self._agg.avvia(silenzioso=True))

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
        base, n = core.separa_copia(mod_id)
        for m in core.elenco_moduli(self.archivio):
            if m.id == base:
                return m.come_copia(n) if n else m
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
                if m and m.tipo == "xfa":
                    self._rivedi_xfa(f, f"Hai modificato e salvato <b>{m.titolo}</b> (moduli 2022). "
                                        "Questi dati sono diversi da quelli della pratica: scegli quali salvare.")
                    continue
                if m and m.tipo == "statico":
                    continue
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
            m22 = core.riconosci_xfa(pdf, moduli)
            if m22:
                self._in_controllo = True
                try:
                    out = core.importa_modulo(self.pratica, m22, pdf)
                finally:
                    self._in_controllo = False
                self._sorveglia()
                self._rivedi_xfa(out, f"Ho caricato <b>{m22.titolo}</b> (moduli 2022) nella pratica. Questi sono i "
                                      "dati trovati nel PDF che mancano o sono diversi nella pratica: scegli quali salvare.")
                self.stato(f"«{pdf.name}» caricato come «{m22.titolo}» (2022)")
                return
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
        self._impronta = self.archivio.impronta()
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
            if it and it.data(Qt.UserRole) == str(self.pratica.cartella):
                return
            self.pratica.segna_chiusa()
        if not it:
            return
        self.pratica = core.Pratica(it.data(Qt.UserRole))
        self.pratica.segna_aperta()
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
        if p.dati.get("_modificata"):
            parti.append(f"modificata il {p.dati['_modificata']}"
                         + (f" da {p.dati['_modificata_da'].split('@')[0]}" if p.dati.get("_modificata_da") else ""))
        self.info.setText("  ·  ".join(parti))
        altri = p.aperta_da_altri()
        self.presenza.setVisible(bool(altri))
        if altri:
            self.presenza.setText("Aperta in questo momento anche da: " + ", ".join(altri)
                                  + ". Le modifiche di entrambi vengono unite; se cambiate lo stesso dato vale l'ultima.")

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
        if self.pratica:
            self.pratica.segna_chiusa()
        super().closeEvent(e)

    # ------------------------------------------------------------------ più postazioni
    def _chiedi_archivio(self):
        r = QMessageBox(self)
        r.setWindowTitle("Archivio delle pratiche")
        r.setIcon(QMessageBox.Question)
        r.setText("Dove si trova l'archivio delle pratiche?\n\n"
                  "Per avere lo stesso elenco su tutte le postazioni dello studio scegli la cartella condivisa "
                  "sul server (la stessa per tutti). Si può cambiare in ogni momento da «Cartella archivio…».")
        b_server = r.addButton("Scegli la cartella condivisa…", QMessageBox.AcceptRole)
        r.addButton("Solo su questo computer", QMessageBox.RejectRole)
        r.exec()
        if r.clickedButton() is b_server:
            d = QFileDialog.getExistingDirectory(self, "Cartella condivisa dell'archivio pratiche")
            if d:
                return d
        return core.ARCHIVIO_LOCALE

    def sincronizza(self):
        """Ogni pochi secondi: elenco pratiche e pratica aperta allineati con le altre postazioni."""
        if self._in_controllo or QApplication.activeModalWidget():
            return
        try:
            if self.archivio.impronta() != self._impronta:
                sel = self.pratica.cartella if self.pratica else None
                if sel and not sel.exists():  # rinominata o eliminata da un collega
                    self.pratica = None
                    self.tabs.setEnabled(False)
                    self.nome.setText("Nessuna pratica selezionata")
                    self.info.setText("La pratica è stata rinominata o eliminata da un'altra postazione.")
                    self.presenza.setVisible(False)
                    sel = None
                self.lista.blockSignals(True)
                self.ricarica_elenco()
                if sel:
                    for i in range(self.lista.count()):
                        if self.lista.item(i).data(Qt.UserRole) == str(sel):
                            self.lista.setCurrentRow(i)
                self.lista.blockSignals(False)
            if self.pratica:
                self.pratica.segna_aperta()
                if not self.scheda_dati.timer.isActive() and not self._sto_scrivendo() and self.pratica.sincronizza():
                    self.scheda_dati.carica(self.pratica)
                    w = self.tabs.currentWidget()
                    if w is not self.scheda_dati:
                        w.carica(self.pratica)
                    self.stato("Aggiornata con le modifiche fatte da un'altra postazione")
                self.aggiorna_intestazione()
                self.controlla_pdf_modificati()
        except OSError:
            self.stato("Archivio non raggiungibile (rete?): riprovo tra poco")

    def _sto_scrivendo(self):
        w = QApplication.focusWidget()
        return bool(w and self.scheda_dati.isAncestorOf(w) and isinstance(w, (QLineEdit, QPlainTextEdit, QComboBox)))

    # ------------------------------------------------------------------ menu ?
    def _menu(self):
        m = self.menuBar().addMenu("?")
        a = QAction("Guida", self)
        a.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(aggiornamenti.PAGINA + "#readme")))
        m.addAction(a)
        a = QAction("Controlla aggiornamenti…", self)
        a.triggered.connect(lambda: self._agg.avvia(silenzioso=False))
        m.addAction(a)
        m.addSeparator()
        a = QAction("Informazioni su Fascicolo", self)
        a.triggered.connect(self._informazioni)
        m.addAction(a)

    def _informazioni(self):
        QMessageBox.about(self, "Informazioni su Fascicolo",
                          f"<b>Fascicolo {__version__}</b><br>Pratiche edilizie e modulistica.<br><br>"
                          f"Archivio: {self.archivio.radice}<br>Postazione: {core.utente()}<br><br>"
                          f"<a href='{aggiornamenti.PAGINA}'>{aggiornamenti.PAGINA}</a>")
