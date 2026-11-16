"""Finestra principale di Fascicolo."""
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QDir, QUrl, QFileSystemWatcher, QEvent
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QListWidget,
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

class SchedaModuli(QWidget):
    def __init__(self, finestra):
        super().__init__()
        self.f = finestra
        self.pratica = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        n = QLabel("Scegli un modulo e premi <b>Compila</b>: ti verranno chiesti solo i dati che mancano. "
                   "Puoi anche aprire il PDF e scriverci direttamente: quando lo salvi, Fascicolo legge i dati nuovi "
                   "e ti propone di aggiornarli nella pratica. Se hai già un modulo compilato, usa <b>Carica modulo compilato</b>.")
        n.setWordWrap(True)
        n.setObjectName("nota")
        lay.addWidget(n)
        hc = QHBoxLayout()
        hc.addWidget(QLabel("Cartella predefinita dei moduli:"))
        self.lbl_cartella = QLabel()
        self.lbl_cartella.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f = self.lbl_cartella.font()
        f.setBold(True)
        self.lbl_cartella.setFont(f)
        hc.addWidget(self.lbl_cartella, 1)
        hc.addWidget(bottone("Cambia…", self.cambia_cartella,
                             tip="Cartella usata dai moduli che non hanno una cartella propria"))
        hc.addWidget(bottone("Cartella dei moduli selezionati…", self.cartella_selezionati,
                             tip="Salva i moduli selezionati in una cartella diversa (puoi selezionarne più di uno)"))
        hc.addWidget(bottone("Apri cartella moduli", lambda: self.pratica and core.apri_con_sistema(self._cartella())))
        lay.addLayout(hc)
        self.tab = QTableWidget(0, 5)
        self.tab.setHorizontalHeaderLabels(["Modulo", "Gruppo", "Stato dati", "Ultima compilazione", "Cartella"])
        self.tab.verticalHeader().setVisible(False)
        self.tab.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tab.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self.tab.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, w in ((1, 140), (2, 120), (3, 140), (4, 220)):
            hh.setSectionResizeMode(i, QHeaderView.Interactive)
            self.tab.setColumnWidth(i, w)
        self.tab.doubleClicked.connect(lambda *_: self.compila())
        lay.addWidget(self.tab)
        h = QHBoxLayout()
        h.addWidget(bottone("Compila", self.compila, True))
        h.addWidget(bottone("Apri PDF", self.apri, tip="Apri il PDF per controllarlo o scriverci: i dati salvati tornano nella pratica"))
        h.addWidget(bottone("Carica modulo compilato…", self.carica_compilato,
                            tip="Porta nella pratica un modulo già compilato e ne legge i dati"))
        h.addWidget(bottone("Mostra dati mancanti", self.mostra_mancanti))
        h.addWidget(bottone("Ricompila tutti i già compilati", self.ricompila_tutti,
                            tip="Utile dopo aver corretto un dato: aggiorna tutti i moduli già generati"))
        h.addStretch()
        h.addWidget(bottone("Insegna modulo…", self.insegna, tip="Collega i campi di un PDF ai dati della pratica"))
        h.addWidget(bottone("Aggiungi modello PDF…", self.aggiungi_modello))
        lay.addLayout(h)

    def _cartella(self):
        d = self.pratica.cartella_moduli
        d.mkdir(parents=True, exist_ok=True)
        return d

    def cambia_cartella(self):
        if not self.pratica:
            return
        attuale = self.pratica.cartella_moduli
        d = QFileDialog.getExistingDirectory(self, "Cartella in cui salvare i moduli di questa pratica",
                                             str(attuale if attuale.exists() else self.pratica.cartella))
        if not d or Path(d).resolve() == attuale.resolve():
            return
        fatti = [i for i in self.pratica.dati.get("_moduli", {}).values()
                 if (attuale / i.get("file", "")).exists()]
        if fatti and QMessageBox.question(
                self, "Cambia cartella dei moduli",
                f"Sposto anche i {len(fatti)} moduli già compilati da\n{attuale}\na\n{d}?\n\n"
                "(Servono lì perché Fascicolo li possa aprire, ricompilare e rileggere.)") != QMessageBox.Yes:
            return
        try:
            n = core.cambia_cartella_moduli(self.pratica, d, sposta=True)
        except Exception as e:  # noqa – ad esempio un PDF aperto in Acrobat
            QMessageBox.warning(self, "Cambia cartella", f"Non sono riuscito a spostare tutti i moduli:\n{e}")
            return
        self.f._sorveglia()
        self.carica(self.pratica)
        self.f.stato(f"Cartella dei moduli: {d}" + (f" ({n} moduli spostati)" if n else ""))

    def carica(self, pratica):
        self.pratica = pratica
        self.lbl_cartella.setText(str(pratica.cartella_moduli))
        self.lbl_cartella.setToolTip(str(pratica.cartella_moduli))
        self.moduli = core.elenco_moduli(self.f.archivio)
        self.moduli.sort(key=lambda m: (0 if m.mappato else 1, m.map.get("ordine", 500), m.id))
        self.tab.setRowCount(len(self.moduli))
        fatti = pratica.dati.get("_moduli", {})
        for r, m in enumerate(self.moduli):
            it = QTableWidgetItem(m.titolo)
            it.setToolTip(m.pdf.name)
            self.tab.setItem(r, 0, it)
            self.tab.setItem(r, 1, QTableWidgetItem(m.gruppo or "—"))
            if not m.mappato:
                st = QTableWidgetItem("da insegnare")
                st.setForeground(Qt.gray)
            else:
                manc = core.dati_mancanti(pratica, m)
                st = QTableWidgetItem("pronto" if not manc else f"mancano {len(manc)} dati")
                st.setForeground(Qt.darkGreen if not manc else Qt.darkYellow)
            self.tab.setItem(r, 2, st)
            info = fatti.get(m.id, {})
            self.tab.setItem(r, 3, QTableWidgetItem(info.get("data", "") + ("  (caricato)" if info.get("importato") else "")))
            propria = pratica.cartella_propria(m.id)
            it = QTableWidgetItem(self._breve(propria) if propria else "predefinita")
            it.setToolTip(str(pratica.cartella_modulo(m.id)))
            if not propria:
                it.setForeground(Qt.gray)
            self.tab.setItem(r, 4, it)

    @staticmethod
    def _breve(p):
        parti = Path(p).parts
        return str(Path(*parti[-2:])) if len(parti) > 2 else str(p)

    def _selezionati(self):
        righe = sorted({i.row() for i in self.tab.selectedIndexes()})
        return [self.moduli[r] for r in righe if 0 <= r < len(self.moduli)]

    def cartella_selezionati(self):
        if not self.pratica:
            return
        sel = self._selezionati()
        if not sel:
            QMessageBox.information(self, "Cartella dei moduli", "Seleziona uno o più moduli nella tabella.")
            return
        nomi = "\n".join(f"• {m.titolo}" for m in sel[:12]) + ("\n…" if len(sel) > 12 else "")
        scelta = QMessageBox(self)
        scelta.setWindowTitle("Cartella dei moduli selezionati")
        scelta.setText(f"Dove vuoi salvare questi moduli?\n\n{nomi}")
        b_scegli = scelta.addButton("Scegli cartella…", QMessageBox.AcceptRole)
        b_pred = scelta.addButton("Usa la cartella predefinita", QMessageBox.ActionRole)
        scelta.addButton("Annulla", QMessageBox.RejectRole)
        scelta.exec()
        if scelta.clickedButton() is b_scegli:
            partenza = self.pratica.cartella_modulo(sel[0].id)
            d = QFileDialog.getExistingDirectory(self, "Cartella per i moduli selezionati",
                                                 str(partenza if partenza.exists() else self.pratica.cartella))
            if not d:
                return
            nuova = d
        elif scelta.clickedButton() is b_pred:
            nuova = None
        else:
            return
        errori, spostati = [], 0
        for m in sel:
            try:
                prima = self.pratica.file_modulo(m.id).exists()
                core.cambia_cartella_modulo(self.pratica, m.id, nuova)
                spostati += prima
            except Exception as e:  # noqa – PDF aperto in un altro programma
                errori.append(f"{m.titolo}: {e}")
        if errori:
            QMessageBox.warning(self, "Cartella dei moduli", "Alcuni moduli non sono stati spostati:\n\n" + "\n".join(errori))
        self.f._sorveglia()
        self.carica(self.pratica)
        dove = nuova or "cartella predefinita"
        self.f.stato(f"{len(sel)} moduli → {dove}" + (f" ({spostati} PDF spostati)" if spostati else ""))

    def _sel(self):
        r = self.tab.currentRow()
        return self.moduli[r] if 0 <= r < len(self.moduli) else None

    def compila(self):
        m = self._sel()
        if not m or not self.pratica:
            return
        self.f.scheda_dati.salva_subito()
        if not m.mappato:
            if QMessageBox.question(self, "Modulo da insegnare",
                                    f"«{m.titolo}» non è ancora collegato ai dati della pratica.\n"
                                    "Vuoi insegnarlo adesso?") == QMessageBox.Yes:
                self.insegna()
            return
        manc = core.dati_mancanti(self.pratica, m)
        if manc:
            d = DatiMancanti(self.pratica, manc, m.titolo, [c["nome"] for c in self.f.archivio.comuni()], self)
            if not d.exec():
                return
            self.f.scheda_dati.carica(self.pratica)
        try:
            out, (n, tot) = core.genera(self.pratica, m)
        except Exception as e:  # noqa
            QMessageBox.critical(self, "Errore", f"Non sono riuscito a compilare il modulo:\n{e}")
            return
        self.carica(self.pratica)
        self.f.stato(f"{m.titolo}: compilati {n} campi → {out.name}")
        if QMessageBox.question(self, "Modulo compilato",
                                f"«{m.titolo}» è pronto in:\n{out.parent}\n\nVuoi aprirlo per controllarlo?") == QMessageBox.Yes:
            core.apri_con_sistema(out)

    def apri(self):
        m = self._sel()
        if m and self.pratica:
            f = self.pratica.file_modulo(m.id)
            if f.exists():
                core.apri_con_sistema(f)
            else:
                QMessageBox.information(self, "Apri", "Questo modulo non è ancora stato compilato per la pratica.")

    def carica_compilato(self):
        if not self.pratica:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Carica moduli già compilati", "", "PDF (*.pdf)")
        for f in files:
            self.f.importa_pdf(Path(f))
        self.carica(self.pratica)

    def mostra_mancanti(self):
        m = self._sel()
        if not m or not m.mappato:
            return
        manc = core.dati_mancanti(self.pratica, m)
        self.f.scheda_dati.evidenzia(set(manc))
        if manc:
            self.f.tabs.setCurrentIndex(0)
            self.f.scheda_dati.vai_a(manc[0])
            self.f.stato(f"Evidenziati in arancione i {len(manc)} dati mancanti per «{m.titolo}»")
        else:
            self.f.stato("Nessun dato mancante")

    def ricompila_tutti(self):
        if not self.pratica:
            return
        self.f.scheda_dati.salva_subito()
        fatti = self.pratica.dati.get("_moduli", {})
        n = 0
        for m in self.moduli:
            if m.id in fatti and m.mappato:
                core.genera(self.pratica, m)
                n += 1
        self.carica(self.pratica)
        self.f.stato(f"Ricompilati {n} moduli (le versioni precedenti sono in Moduli/_precedenti)")

    def insegna(self):
        m = self._sel()
        if not m:
            return
        d = InsegnaModulo(m, self.moduli, self.f.archivio, self)
        if d.exec():
            self.carica(self.pratica)
            self.f.stato(f"Mappatura di «{m.titolo}» salvata")

    def aggiungi_modello(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Aggiungi modelli PDF compilabili", "", "PDF (*.pdf)")
        if not files:
            return
        dest = self.f.archivio.impostazioni / "moduli"
        dest.mkdir(exist_ok=True)
        for f in files:
            shutil.copy2(f, dest / Path(f).name)
        self.carica(self.pratica)
        self.f.stato(f"Aggiunti {len(files)} modelli: ora vanno insegnati")


# =========================================================================== scheda documenti

class SchedaDocumenti(QWidget):
    def __init__(self, finestra):
        super().__init__()
        self.f = finestra
        self.pratica = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setColumnWidth(0, 420)
        self.tree.setSortingEnabled(True)
        self.tree.doubleClicked.connect(lambda i: core.apri_con_sistema(self.model.filePath(i)))
        lay.addWidget(self.tree)
        h = QHBoxLayout()
        h.addWidget(bottone("Aggiungi file…", self.aggiungi, True))
        h.addWidget(bottone("Apri cartella della pratica", lambda: self.pratica and core.apri_con_sistema(self.pratica.cartella)))
        h.addStretch()
        lay.addLayout(h)

    def carica(self, pratica):
        self.pratica = pratica
        root = self.model.setRootPath(str(pratica.cartella))
        self.tree.setRootIndex(root)

    def aggiungi(self):
        if not self.pratica:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Aggiungi file alla pratica")
        if not files:
            return
        sotto, ok = QInputDialog.getItem(self, "Dove?", "Copia nella cartella:", core.SOTTOCARTELLE, 1, False)
        if not ok:
            return
        copiati = 0
        for f in files:
            if f.lower().endswith(".pdf") and xfa.leggi_datasets(f):
                if QMessageBox.question(self, "Modulo del portale",
                                        f"«{Path(f).name}» è un modulo compilato del portale.\n"
                                        "Vuoi caricarlo nella pratica e leggerne i dati?") == QMessageBox.Yes:
                    self.f.importa_pdf(Path(f))
                    continue
            if f.lower().endswith(".pdf"):
                m, _s = core.riconosci_modulo(f, core.elenco_moduli(self.f.archivio))
                if m and m.mappato and QMessageBox.question(
                        self, "Modulo riconosciuto",
                        f"«{Path(f).name}» è il modulo «{m.titolo}».\n"
                        "Vuoi caricarlo come modulo della pratica e leggerne i dati?") == QMessageBox.Yes:
                    self.f.importa_pdf(Path(f))
                    continue
            shutil.copy2(f, self.pratica.cartella / sotto / Path(f).name)
            copiati += 1
        self.f.stato(f"Copiati {copiati} file in {sotto}")


# =========================================================================== scheda consegna

class SchedaConsegna(QWidget):
    def __init__(self, finestra):
        super().__init__()
        self.f = finestra
        self.pratica = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        self.info = QLabel()
        self.info.setObjectName("avviso")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.RichText)
        lay.addWidget(self.info)
        split = QHBoxLayout()
        g = QGroupBox("File da consegnare")
        gv = QVBoxLayout(g)
        self.lista = QListWidget()
        gv.addWidget(self.lista)
        split.addWidget(g, 3)
        g2 = QGroupBox("Messaggio")
        gv2 = QFormLayout(g2)
        self.oggetto = QLineEdit()
        self.testo = QPlainTextEdit()
        gv2.addRow("Oggetto", self.oggetto)
        gv2.addRow("Testo", self.testo)
        split.addWidget(g2, 4)
        lay.addLayout(split, 1)
        h = QHBoxLayout()
        h.addWidget(bottone("Prepara consegna", self.prepara, True,
                            tip="Copia i file scelti in Consegne/<data> e prepara il messaggio"))
        h.addStretch()
        lay.addLayout(h)
        lay.addWidget(QLabel("Storico consegne"))
        self.storico = QListWidget()
        self.storico.setMaximumHeight(120)
        lay.addWidget(self.storico)

    def carica(self, pratica):
        self.pratica = pratica
        com = self.f.archivio.comune(pratica.get("pratica.comune")) or {}
        mod = com.get("consegna", "")
        if not com:
            self.info.setText(f"Il comune <b>{pratica.get('pratica.comune') or '(non indicato)'}</b> non è in elenco: "
                              "aggiungilo da <b>Comuni</b> per avere le regole di consegna.")
        else:
            parti = [f"<b>{com['nome']}</b> – consegna: <b>{mod}</b>"]
            if com.get("pec"):
                parti.append(f"PEC: {com['pec']}")
            if com.get("peo"):
                parti.append(f"email: {com['peo']}")
            if int(com.get("copie") or 0):
                parti.append(f"copie cartacee: <b>{com['copie']}</b>")
            if com.get("note"):
                parti.append(f"<i>{com['note']}</i>")
            self.info.setText(" · ".join(parti))
        self.lista.clear()
        visti = set()
        for k in pratica.dati.get("_moduli", {}):
            f = pratica.file_modulo(k)
            if f.exists():
                visti.add(f.resolve())
                it = QListWidgetItem(f"Moduli/{f.name}")
                it.setToolTip(str(f))
                it.setData(Qt.UserRole, str(f))
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked)
                self.lista.addItem(it)
        for sotto in ("Moduli", "Elaborati", "Allegati"):
            d = pratica.cartella_moduli if sotto == "Moduli" else pratica.cartella / sotto
            for f in sorted(d.glob("*")) if d.exists() else []:
                if f.resolve() in visti:
                    continue
                if f.is_file():
                    it = QListWidgetItem(f"{sotto}/{f.name}")
                    it.setData(Qt.UserRole, str(f))
                    it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                    it.setCheckState(Qt.Checked if sotto != "Allegati" else Qt.Unchecked)
                    self.lista.addItem(it)
        tit = pratica.get("titolare.cognome") + " " + pratica.get("titolare.nome")
        if pratica.get("titolare.tipo") == "Società":
            tit = pratica.get("societa.denominazione")
        imm = pratica.get("immobile.particelle.0.ped") and f"p.ed. {pratica.get('immobile.particelle.0.ped')}" \
            or pratica.get("immobile.particelle.0.pf") and f"p.f. {pratica.get('immobile.particelle.0.pf')}" or ""
        cc = pratica.get("immobile.particelle.0.cc")
        parti = ["Pratica edilizia", tit.strip(), f"{imm} C.C. {cc}" if imm and cc else imm]
        self.oggetto.setText(" – ".join(x for x in parti if x))
        self.testo.setPlainText(
            f"Spett.le Comune di {pratica.get('pratica.comune')},\n\n"
            f"si trasmette in allegato la documentazione relativa a: {pratica.get('pratica.oggetto')}.\n\n"
            f"Distinti saluti\n\n{pratica.get('progettista.titolo')} {pratica.get('progettista.nome')} "
            f"{pratica.get('progettista.cognome')}".strip())
        self.storico.clear()
        for c in reversed(pratica.dati.get("_consegne", [])):
            self.storico.addItem(f"{c['data']} – {c['modalita']} – {len(c['file'])} file → {c['cartella']}")

    def prepara(self):
        if not self.pratica:
            return
        files = [Path(self.lista.item(i).data(Qt.UserRole)) for i in range(self.lista.count())
                 if self.lista.item(i).checkState() == Qt.Checked]
        if not files:
            QMessageBox.information(self, "Consegna", "Seleziona almeno un file.")
            return
        com = self.f.archivio.comune(self.pratica.get("pratica.comune")) or {}
        mod = com.get("consegna", "PEC")
        nome = f"{datetime.now():%Y-%m-%d}"
        dest = self.pratica.cartella / "Consegne" / nome
        i = 2
        while dest.exists():
            dest = self.pratica.cartella / "Consegne" / f"{nome}_{i}"
            i += 1
        dest.mkdir(parents=True)
        for f in files:
            shutil.copy2(f, dest / f.name)
        destinatario = com.get("pec") if mod.startswith("PEC") else com.get("peo") or com.get("pec", "")
        (dest / "messaggio.txt").write_text(
            f"Destinatario: {destinatario}\nOggetto: {self.oggetto.text()}\n\n{self.testo.toPlainText()}\n\n"
            f"Allegati:\n" + "\n".join(f" - {f.name}" for f in files), encoding="utf-8")
        self.pratica.dati.setdefault("_consegne", []).append(
            dict(data=datetime.now().strftime("%d/%m/%Y %H:%M"), modalita=mod, cartella=dest.name,
                 file=[f.name for f in files], destinatario=destinatario))
        self.pratica.salva()
        self.carica(self.pratica)
        core.apri_con_sistema(dest)
        if mod.startswith(("PEC", "PEO")) and destinatario:
            url = "mailto:" + destinatario + "?" + urllib.parse.urlencode(
                {"subject": self.oggetto.text(), "body": self.testo.toPlainText()}, quote_via=urllib.parse.quote)
            QDesktopServices.openUrl(QUrl(url))
            QMessageBox.information(self, "Consegna pronta",
                                    "Ho aperto la cartella con i file e un nuovo messaggio nel programma di posta.\n"
                                    "Ricordati di firmare digitalmente i moduli e trascina i file come allegati.")
        elif mod == "Cartaceo":
            QMessageBox.information(self, "Consegna pronta",
                                    f"I file sono nella cartella {dest.name}.\nStampa {com.get('copie') or 1} "
                                    "copie di ciascuno per la consegna cartacea.")
        else:
            QMessageBox.information(self, "Consegna pronta", f"I file sono pronti nella cartella {dest.name}.")


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
        bl.addWidget(self.lista, 1)
        bl.addWidget(bottone("Comuni e consegne", self.comuni))
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
        self.scheda_doc = SchedaDocumenti(self)
        self.scheda_consegna = SchedaConsegna(self)
        self.tabs.addTab(self.scheda_dati, "Dati pratica")
        self.tabs.addTab(self.scheda_moduli, "Moduli")
        self.tabs.addTab(self.scheda_doc, "Documenti")
        self.tabs.addTab(self.scheda_consegna, "Consegna")
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
