"""Logica di Fascicolo: archivio pratiche, dati, mappature e compilazione PDF."""
import json
import os
import time
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pymupdf

from .schema import CAMPI, SEZIONI

APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
MODULI_DIR = APP_DIR / "moduli"
MAPPATURE_DIR = APP_DIR / "mappature"
CONFIG_FILE = Path.home() / ".fascicolo.json"

FILE_PRATICA = "pratica.json"
SOTTOCARTELLE = ["Moduli", "Allegati"]


# --------------------------------------------------------------------------- utilità

def _slug(s):
    s = re.sub(r'[<>:"/\\|?*]+', "", s).strip()
    return re.sub(r"\s+", " ", s)[:80] or "Pratica"


def oggi():
    return datetime.now().strftime("%d/%m/%Y")


def leggi_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def scrivi_json(p, dati):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def apri_con_sistema(path):
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')


def utente():
    """Nome di chi usa il programma su questa postazione (utente @ computer)."""
    import getpass
    import platform
    try:
        u = getpass.getuser()
    except Exception:
        u = "utente"
    return f"{u}@{platform.node() or 'pc'}"


# --------------------------------------------------------------------------- config

ARCHIVIO_LOCALE = str(Path.home() / "Documents" / "Pratiche")


def carica_config():
    """Impostazioni di questa postazione. 'archivio' manca al primo avvio: lo chiede l'interfaccia."""
    return leggi_json(CONFIG_FILE, {})


def salva_config(cfg):
    scrivi_json(CONFIG_FILE, cfg)


# --------------------------------------------------------------------------- pratica

def _copia(x):
    return json.loads(json.dumps(x))


def _unisci(base, mio, disco):
    """Unione a tre vie: dove ho cambiato io vince il mio valore, altrimenti quello sul disco
    (che può contenere le modifiche fatte da un collega su un'altra postazione)."""
    if isinstance(mio, dict) and isinstance(disco, dict) and isinstance(base, dict):
        out = {}
        for k in set(mio) | set(disco) | set(base):
            b, m, d = base.get(k, _MANCA), mio.get(k, _MANCA), disco.get(k, _MANCA)
            if m == b:
                v = d
            elif d == b:
                v = m
            elif isinstance(m, dict) and isinstance(d, dict):
                v = _unisci(b if isinstance(b, dict) else {}, m, d)
            else:
                v = m
            if v is not _MANCA:
                out[k] = v
        return out
    return disco if mio == base else mio


_MANCA = object()


def _mtime(p):
    try:
        return Path(p).stat().st_mtime
    except OSError:
        return 0.0


class Pratica:
    def __init__(self, cartella, dati=None):
        self.cartella = Path(cartella)
        self.dati = dati if dati is not None else leggi_json(self.cartella / FILE_PRATICA, {})
        self._base = _copia(self.dati)
        self._mtime_disco = _mtime(self.cartella / FILE_PRATICA)
        self.dati.setdefault("_valori", {})
        self.dati.setdefault("_moduli", {})
        self.dati.setdefault("_consegne", [])
        self.dati.setdefault("_creata", oggi())

    # valori -----------------------------------------------------------------
    @property
    def valori(self):
        return self.dati["_valori"]

    def grezzo(self, key):
        """Valore salvato, oppure predefinito dello schema."""
        if key in self.valori:
            return self.valori[key]
        c = CAMPI.get(key)
        if c:
            return c[1].get("def", False if c[1].get("t") == "bool" else "")
        return ""

    archivio = None  # impostato dall'interfaccia: serve per i dati del comune

    def _particelle(self):
        righe = []
        for i in range(5):
            r = {col: str(self.grezzo(f"immobile.particelle.{i}.{col}") or "").strip() for col in ("pf", "ped", "cc", "pm", "sub")}
            if any(r.values()):
                righe.append(r)
        return righe

    def _virtuale(self, key):
        """Valori calcolati dai dati della pratica (usati dai moduli ISTAT)."""
        nome = key.split(".", 1)[1]
        righe = self._particelle()
        ped = [r for r in righe if r["ped"]]
        pf = [r for r in righe if r["pf"]]
        def parti(v, i):
            p = v.split("/")
            return p[i].strip() if len(p) > i else ""
        if nome == "ped_num": return parti(ped[0]["ped"], 0) if ped else ""
        if nome == "ped_den": return parti(ped[0]["ped"], 1) if ped else ""
        if nome == "ped_pm": return ped[0]["pm"] if ped else ""
        if nome == "ped_sub": return ped[0]["sub"] if ped else ""
        if nome == "pf_num": return parti(pf[0]["pf"], 0) if pf else ""
        if nome == "pf_den": return parti(pf[0]["pf"], 1) if pf else ""
        if nome == "altre_ped":
            return ", ".join(" ".join(x for x in [r["ped"], r["pm"] and "p.m. " + r["pm"], r["sub"] and "sub " + r["sub"]] if x)
                             for r in ped[1:])
        if nome == "altre_pf": return ", ".join(r["pf"] for r in pf[1:])
        if nome == "cc": return (righe[0]["cc"] if righe else "")
        via = str(self.grezzo("immobile.via") or "").strip()
        tipi = ["piazza", "viale", "via", "località", "localita'", "largo", "frazione", "corso"]
        primo = via.split(" ", 1)[0].lower() if via else ""
        if nome == "via_tipo": return primo if primo in tipi else ""
        if nome == "via_nome": return via.split(" ", 1)[1] if primo in tipi and " " in via else via
        return ""

    def get(self, key):
        if key.startswith("calc."):
            return self._virtuale(key)
        if key.startswith("comune."):
            c = self.archivio.comune(self.grezzo("pratica.comune")) if self.archivio else None
            return (c or {}).get(key[7:], "")
        # direttore lavori uguale al progettista
        if key.startswith("dl.") and key not in ("dl.uguale", "dl.presenta") and self.grezzo("dl.uguale"):
            return self.grezzo("progettista." + key[3:])
        return self.grezzo(key)

    def set(self, key, val):
        if self.valori.get(key) != val:
            self.dati["_ts_dati"] = time.time()
        self.valori[key] = val

    # cartella dei moduli --------------------------------------------------
    @property
    def cartella_moduli(self):
        """Dove vengono salvati i moduli compilati: di default <pratica>/Moduli, ma si può cambiare."""
        v = self.dati.get("_cartella_moduli")
        p = Path(v) if v else Path("Moduli")
        if not p.is_absolute():
            p = self.cartella / p
        return p

    def imposta_cartella_moduli(self, percorso):
        v = self._relativo(percorso)
        self.dati["_cartella_moduli"] = None if v == "Moduli" else v

    def _assoluto(self, v):
        p = Path(v)
        return p if p.is_absolute() else self.cartella / p

    def _relativo(self, percorso):
        p = Path(percorso)
        try:
            return str(p.resolve().relative_to(self.cartella.resolve()))
        except ValueError:
            return str(p.resolve())

    def cartella_propria(self, mod_id):
        """Cartella scelta apposta per questo modulo, oppure None se usa quella predefinita."""
        v = self.dati.get("_cartelle_moduli", {}).get(mod_id)
        return self._assoluto(v) if v else None

    def cartella_modulo(self, mod_id):
        return self.cartella_propria(mod_id) or self.cartella_moduli

    def file_modulo(self, mod_id, nome=None):
        info = self.dati.get("_moduli", {}).get(mod_id, {})
        return self.cartella_modulo(mod_id) / (nome or info.get("file") or f"{mod_id}.pdf")

    def cartelle_in_uso(self):
        out = {self.cartella_moduli}
        for mod_id in self.dati.get("_moduli", {}):
            out.add(self.cartella_modulo(mod_id))
        return sorted(out)

    @property
    def nome(self):
        return self.valori.get("pratica.nome") or self.cartella.name

    def _sostituisci(self, nuovi):
        self.dati.clear()
        self.dati.update(nuovi)
        for k, v in (("_valori", {}), ("_moduli", {}), ("_consegne", []), ("_creata", oggi())):
            self.dati.setdefault(k, v)

    def sincronizza(self, forza=False):
        """Porta dentro le modifiche salvate da altre postazioni. Ritorna True se è cambiato qualcosa."""
        f = self.cartella / FILE_PRATICA
        mt = _mtime(f)
        if not mt or (mt == self._mtime_disco and not forza):
            return False
        disco = leggi_json(f, None)
        if disco is None or disco.get("_salvataggio") == self._base.get("_salvataggio"):
            self._mtime_disco = mt
            return False
        prima = _copia(self.dati)
        self._sostituisci(_unisci(self._base, self.dati, disco))
        self._base = _copia(disco)
        self._mtime_disco = mt
        return self.dati != prima

    def salva(self):
        self.sincronizza(forza=True)  # prima unisco eventuali modifiche dei colleghi
        self.dati["_salvataggio"] = f"{time.time():.6f}-{os.getpid()}-{utente()}"
        self.dati["_modificata"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.dati["_modificata_da"] = utente()
        scrivi_json(self.cartella / FILE_PRATICA, self.dati)
        self._base = _copia(self.dati)
        self._mtime_disco = _mtime(self.cartella / FILE_PRATICA)

    # chi ha aperta la pratica ------------------------------------------------
    def _file_presenza(self):
        nome = re.sub(r"[^\w.-]+", "_", utente())
        return self.cartella / f".in_uso_{nome}.json"

    def segna_aperta(self):
        try:
            scrivi_json(self._file_presenza(), {"utente": utente(), "ora": time.time()})
        except OSError:
            pass

    def segna_chiusa(self):
        try:
            self._file_presenza().unlink()
        except OSError:
            pass

    def aperta_da_altri(self, minuti=3):
        mio = self._file_presenza().name
        out = []
        for f in self.cartella.glob(".in_uso_*.json"):
            if f.name == mio:
                continue
            d = leggi_json(f, {})
            if time.time() - float(d.get("ora", 0)) < minuti * 60:
                out.append(d.get("utente", f.stem[8:]))
        return out

    def registra_modulo(self, mod_id, file_out, importato=False):
        info = {"file": str(Path(file_out).name), "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "ts": time.time()}
        if importato:
            info["importato"] = True
        try:
            info["mtime"] = Path(file_out).stat().st_mtime
        except OSError:
            pass
        self.dati["_moduli"][mod_id] = info


class Archivio:
    def __init__(self, radice):
        self.radice = Path(radice)
        self.radice.mkdir(parents=True, exist_ok=True)
        self.impostazioni = self.radice / "_impostazioni"
        self.impostazioni.mkdir(exist_ok=True)

    def pratiche(self):
        out = []
        for d in sorted(self.radice.iterdir()):
            if d.is_dir() and (d / FILE_PRATICA).exists():
                out.append(Pratica(d))
        return out

    def impronta(self):
        """Cambia quando un collega crea, rinomina, elimina o modifica una pratica."""
        out = []
        try:
            for d in self.radice.iterdir():
                f = d / FILE_PRATICA
                if d.is_dir() and f.exists():
                    out.append((d.name, _mtime(f)))
        except OSError:
            pass
        return tuple(sorted(out))

    def nuova(self, nome, comune=""):
        anno = datetime.now().year
        usati = {int(m.group(1)) for d in self.radice.iterdir() if d.is_dir()
                 for m in [re.match(rf"{anno}-(\d{{3}})", d.name)] if m}
        n = max(usati, default=0) + 1
        cartella = self.radice / _slug(f"{anno}-{n:03d} {nome}")
        while cartella.exists():
            n += 1
            cartella = self.radice / _slug(f"{anno}-{n:03d} {nome}")
        cartella.mkdir()
        for s in SOTTOCARTELLE:
            (cartella / s).mkdir()
        p = Pratica(cartella, {"_valori": {"pratica.nome": nome, "pratica.comune": comune,
                                           "immobile.comune": comune}})
        p.salva()
        return p

    def modifica(self, pratica, nome, comune):
        """Cambia nome e comune; rinomina anche la cartella (tenendo il numero AAAA-NNN)."""
        vecchio_comune = pratica.valori.get("pratica.comune", "")
        pratica.set("pratica.nome", nome)
        pratica.set("pratica.comune", comune)
        if not pratica.valori.get("immobile.comune") or pratica.valori.get("immobile.comune") == vecchio_comune:
            pratica.set("immobile.comune", comune)
        pratica.salva()
        m = re.match(r"^(\d{4}-\d{3})\s", pratica.cartella.name)
        nuovo_nome = _slug(f"{m.group(1)} {nome}" if m else nome)
        dest = self.radice / nuovo_nome
        if dest != pratica.cartella and not dest.exists():
            pratica.cartella.rename(dest)
            pratica.cartella = dest
        return pratica

    def duplica(self, pratica, nome, comune, allegati=False, moduli=False):
        """Nuova pratica con gli stessi dati; a richiesta copia anche allegati e moduli."""
        nuova = self.nuova(nome, comune)
        for k, v in pratica.valori.items():
            if k not in ("pratica.nome", "pratica.comune"):
                nuova.valori[k] = v
        nuova.valori["pratica.comune"] = comune
        if allegati:
            src = pratica.cartella / "Allegati"
            if src.exists():
                for f in src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, nuova.cartella / "Allegati" / f.name)
                nuova.dati["_allegati"] = json.loads(json.dumps(pratica.dati.get("_allegati", {})))
        if moduli:
            for mod_id in pratica.dati.get("_moduli", {}):
                f = pratica.file_modulo(mod_id)
                if f.exists():
                    dest = nuova.cartella / "Moduli" / f.name
                    shutil.copy2(f, dest)
                    nuova.registra_modulo(mod_id, dest)
                    if pratica.dati["_moduli"][mod_id].get("xfa"):
                        nuova.dati["_moduli"][mod_id]["xfa"] = True
            nuova.dati["_ordine_moduli"] = [k for k in pratica.dati.get("_ordine_moduli", [])
                                            if k in nuova.dati.get("_moduli", {})]
        nuova.salva()
        return nuova

    def elimina(self, pratica):
        """Non cancella: sposta la cartella della pratica in <archivio>/_cestino."""
        cestino = self.radice / "_cestino"
        cestino.mkdir(exist_ok=True)
        dest = cestino / f"{pratica.cartella.name} ({datetime.now():%Y-%m-%d %H.%M})"
        shutil.move(str(pratica.cartella), str(dest))
        return dest

    # comuni e rubrica -------------------------------------------------------
    def comuni(self):
        return leggi_json(self.impostazioni / "comuni.json", [])

    def salva_comuni(self, lst):
        scrivi_json(self.impostazioni / "comuni.json", lst)

    def comune(self, nome):
        for c in self.comuni():
            if c.get("nome", "").lower() == (nome or "").lower():
                return c
        return None

    def rubrica(self):
        return leggi_json(self.impostazioni / "rubrica.json", {})

    def salva_rubrica(self, r):
        scrivi_json(self.impostazioni / "rubrica.json", r)

    def cartella_mappature(self):
        d = self.impostazioni / "mappature"
        d.mkdir(exist_ok=True)
        return d


# --------------------------------------------------------------------------- mappature

class Modulo:
    """Un modello PDF compilabile più la sua mappatura (se esiste)."""

    def __init__(self, pdf, mappatura=None, file_mappatura=None):
        self.pdf = Path(pdf)
        self.map = mappatura or {}
        self.file_mappatura = file_mappatura
        self.copia = 0  # 0 = il modulo; 2, 3… = altre copie dello stesso modulo nella pratica

    @property
    def id(self):
        return self.pdf.stem + (f"__copia{self.copia}" if self.copia else "")

    @property
    def id_base(self):
        return self.pdf.stem

    @property
    def titolo(self):
        t = self.map.get("titolo") or self.pdf.stem.replace("_", " ")
        return f"{t} (copia {self.copia})" if self.copia else t

    def come_copia(self, n):
        m = Modulo(self.pdf, self.map, self.file_mappatura)
        m.copia = n
        return m

    @property
    def tipo(self):
        """'acroform' (moduli 2026 e ISTAT), 'xfa' (moduli dinamici 2022), 'statico' (solo da stampare)."""
        return self.map.get("tipo", "acroform")

    @property
    def mappato(self):
        return bool(self.map.get("campi")) or self.tipo in ("xfa", "statico")

    @property
    def gruppo(self):
        return self.map.get("gruppo", "")

    @property
    def edizione(self):
        return self.map.get("edizione", "Altri moduli")


def togli_modulo(pratica, mod_id):
    """Toglie un modulo dalla pratica. Il PDF non si cancella: va nella sottocartella «_tolti»
    accanto a dove era salvato. Solleva OSError se il file non si può spostare (es. aperto)."""
    f = pratica.file_modulo(mod_id)
    spostato = None
    caricato = pratica.dati.get("_moduli", {}).get(mod_id, {}).get("importato")
    if f.exists() and not caricato:  # un file caricato da te resta dov'è: tolgo solo il collegamento
        cest = f.parent / "_tolti"
        cest.mkdir(exist_ok=True)
        dest = cest / f.name
        n = 2
        while dest.exists():
            dest = cest / f"{f.stem} ({n}){f.suffix}"
            n += 1
        shutil.move(str(f), str(dest))
        spostato = dest
    pratica.dati.get("_moduli", {}).pop(mod_id, None)
    pratica.dati.get("_cartelle_moduli", {}).pop(mod_id, None)
    pratica.dati["_ordine_moduli"] = [k for k in pratica.dati.get("_ordine_moduli", []) if k != mod_id]
    pratica.salva()
    return spostato


def separa_copia(mod_id):
    """'NOME__copia3' → ('NOME', 3); 'NOME' → ('NOME', 0)."""
    m = re.match(r"^(.*)__copia(\d+)$", mod_id or "")
    return (m.group(1), int(m.group(2))) if m else (mod_id, 0)


def prossima_copia(pratica, modulo):
    """Numero della prossima copia libera di un modulo nella pratica (2, 3, …)."""
    usati = {separa_copia(k)[1] or 1 for k in pratica.dati.get("_moduli", {}) if separa_copia(k)[0] == modulo.id_base}
    n = 2
    while n in usati:
        n += 1
    return n


def elenco_moduli(archivio=None):
    mapp = {}
    for d in [MAPPATURE_DIR] + ([archivio.cartella_mappature()] if archivio else []):
        for f in sorted(Path(d).glob("*.json")):
            m = leggi_json(f, {})
            if m.get("modulo"):
                mapp[m["modulo"]] = (m, f)
    out = []
    for pdf in sorted(MODULI_DIR.rglob("*.pdf")):
        m, f = mapp.get(pdf.relative_to(MODULI_DIR).as_posix(), (None, None))
        out.append(Modulo(pdf, m, f))
    if archivio:  # moduli aggiunti dall'utente
        extra = archivio.impostazioni / "moduli"
        if extra.exists():
            for pdf in sorted(extra.glob("*.pdf")):
                m, f = mapp.get(pdf.name, (None, None))
                out.append(Modulo(pdf, m, f))
    return out


_TPL = re.compile(r"\{([a-z_]+\.[a-z0-9_.]+)\}")


def _condizione_ok(pratica, se):
    for k, v in (se or {}).items():
        val = pratica.get(k)
        attesi = v if isinstance(v, list) else [v]
        if val not in attesi:
            return False
    return True


def _chiavi_regola(r):
    if "k" in r:
        return [r["k"]]
    if "t" in r:
        return _TPL.findall(r["t"])
    return []


def _formatta(v, r):
    f = r.get("fmt")
    if f in ("mese", "anno", "mese2"):
        p = str(v or "").split("/")
        if len(p) != 3:
            return ""
        if f == "anno":
            return p[2]
        return p[1] if f == "mese2" else str(int(p[1])) if p[1].isdigit() else ""
    if "mappa" in r:
        return r["mappa"].get(str(v), "")
    return v


def _valore_testo(pratica, r):
    if "c" in r:
        return str(r["c"])
    if "t" in r:
        return re.sub(r"\s+", " ", _TPL.sub(lambda m: str(pratica.get(m.group(1)) or ""), r["t"])).strip(" -")
    v = pratica.get(r["k"])
    if isinstance(v, bool):
        return "Sì" if v else ""
    return str(_formatta(v, r) or "")


def _valore_check(pratica, r):
    if "c" in r:
        return bool(r["c"])
    if "k" not in r:
        return bool(_valore_testo(pratica, r))
    v = pratica.get(r["k"])
    if r.get("pieno"):
        return bool(str(v or "").strip())
    if "v" in r:
        attesi = r["v"] if isinstance(r["v"], list) else [r["v"]]
        return v in attesi
    return v is True or v in ("Sì", "Si", "sì", "si")


def dati_mancanti(pratica, modulo):
    """Chiavi richieste dal modulo ancora vuote (in ordine di schema)."""
    serve = set()
    for nome, r in modulo.map.get("campi", {}).items():
        if not _condizione_ok(pratica, r.get("se")):
            continue
        for k in _chiavi_regola(r):
            c = CAMPI.get(k)
            if not c or c[1].get("opz"):
                continue
            sez = c[0]
            if sez.get("solo_se") and not _condizione_ok(pratica, sez["solo_se"]):
                continue
            if k.startswith("dl.") and k not in ("dl.uguale", "dl.presenta") and pratica.get("dl.uguale"):
                k = "progettista." + k[3:]
                if CAMPI.get(k, (None, {}))[1].get("opz"):
                    continue
            v = pratica.get(k)
            if v in ("", None):
                serve.add(k)
    ordine = list(CAMPI.keys())
    return sorted(serve, key=lambda k: ordine.index(k) if k in ordine else 9999)


def compila(pratica, modulo, uscita, conserva=None):
    """Compila il PDF del modulo con i dati della pratica. Ritorna (compilati, totale).

    Il file di uscita è una copia esatta del modulo originale a cui vengono solo aggiunti
    i valori dei campi (salvataggio incrementale): il modulo non viene ricreato né riscritto."""
    Path(uscita).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(modulo.pdf, uscita)
    doc = pymupdf.open(uscita)
    regole = modulo.map.get("campi", {})
    n = 0
    for page in doc:
        for w in page.widgets():
            r = regole.get(w.field_name)
            if not r:
                if conserva and w.field_name in conserva:
                    _scrivi_valore(w, conserva[w.field_name])
                continue
            if not _condizione_ok(pratica, r.get("se")):
                val_t, val_c = "", False
            else:
                val_t, val_c = _valore_testo(pratica, r), _valore_check(pratica, r)
            try:
                if w.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON and "radio" in r:
                    voluto = r["radio"].get(str(pratica.get(r["k"]))) if _condizione_ok(pratica, r.get("se")) else None
                    if voluto is not None and str(w.on_state()) == str(voluto):
                        w.field_value = True
                        w.update()
                        par = doc.xref_get_key(w.xref, "Parent")
                        if par[0] == "xref":
                            doc.xref_set_key(int(par[1].split()[0]), "V", "/" + str(voluto))
                        n += 1
                    continue
                if w.field_type == pymupdf.PDF_WIDGET_TYPE_COMBOBOX:
                    scelta = ""
                    if val_t:
                        opz = [str(x[0] if isinstance(x, (list, tuple)) else x) for x in (w.choice_values or [])]
                        if r.get("combo") == "prefisso":
                            cand = [o for o in opz if o.lower().startswith(val_t.lower() + " -") or o.strip().lower() == val_t.lower()]
                        else:
                            cand = [o for o in opz if o.strip().lower() == val_t.strip().lower()]
                        scelta = cand[0] if cand else ""
                    w.field_value = scelta
                    w.update()
                    if scelta:
                        n += 1
                    continue
                if w.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                    w.field_value = w.on_state() if val_c else "Off"
                elif w.field_type in (pymupdf.PDF_WIDGET_TYPE_TEXT, pymupdf.PDF_WIDGET_TYPE_COMBOBOX):
                    w.field_value = val_t
                else:
                    continue
                w.update()
                if val_t or val_c:
                    n += 1
            except Exception:
                pass
    doc.saveIncr()
    doc.close()
    return n, len(regole)


def _archivia_precedente(pratica, modulo, out):
    if out.exists():  # tieni la versione precedente, nella cartella della pratica (non tra i file dell'utente)
        old = pratica.cartella_moduli / "_precedenti"
        old.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, old / f"{modulo.id}_{datetime.now():%Y%m%d-%H%M%S}.pdf")


def genera(pratica, modulo):
    """Compila il modulo. Se esiste già una versione compilata, i campi che il programma
    non gestisce (scelte tecniche, spunte fatte a mano nel PDF…) vengono conservati."""
    nome = f"{modulo.id_base} (copia {modulo.copia}).pdf" if modulo.copia else f"{modulo.id}.pdf"
    out = pratica.file_modulo(modulo.id, None if pratica.dati.get("_moduli", {}).get(modulo.id) else nome)
    out.parent.mkdir(parents=True, exist_ok=True)
    conserva = None
    if out.exists() and modulo.tipo == "acroform":
        regole = modulo.map.get("campi", {})
        try:
            conserva = {k: v for k, v in leggi_valori(out).items() if k not in regole}
        except Exception:
            conserva = None
    _archivia_precedente(pratica, modulo, out)
    if modulo.tipo == "xfa":
        from . import xfa
        # se il modulo c'è già scrivo nel PDF esistente: restano i campi compilati a mano in Acrobat
        # (se un file vecchio ha perso i diritti di salvataggio lo rifaccio dal modello con i suoi dati)
        res = xfa.scrivi(modulo.pdf, out, pratica)
        pratica.registra_modulo(modulo.id, out)
        pratica.salva()
        return out, res
    if modulo.tipo == "statico":
        shutil.copyfile(modulo.pdf, out)
        pratica.registra_modulo(modulo.id, out)
        pratica.salva()
        return out, (0, 0)
    res = compila(pratica, modulo, out, conserva)
    pratica.registra_modulo(modulo.id, out)
    pratica.salva()
    return out, res


# --------------------------------------------------------------------------- lettura dei PDF compilati

def _scrivi_valore(w, v):
    try:
        if w.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
            if v is not None and str(w.on_state()) == str(v):
                w.field_value = True
                w.update()
            return
        if w.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
            w.field_value = w.on_state() if v else "Off"
        elif w.field_type in (pymupdf.PDF_WIDGET_TYPE_TEXT, pymupdf.PDF_WIDGET_TYPE_COMBOBOX):
            w.field_value = str(v or "")
        else:
            return
        w.update()
    except Exception:
        pass


def leggi_valori(pdf):
    """Valori dei campi di un PDF: testo -> str, casella -> bool, gruppo radio -> stato scelto."""
    doc = pymupdf.open(pdf)
    out = {}
    try:
        for page in doc:
            for w in page.widgets():
                n = w.field_name
                t = w.field_type
                v = w.field_value
                if t == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                    if v not in (None, "", "Off", False) and str(v) == str(w.on_state()):
                        out[n] = str(w.on_state())
                    else:
                        out.setdefault(n, None)
                elif t == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
                    acceso = v not in (None, "", "Off", False, "false")
                    out[n] = out.get(n, False) or acceso
                elif t in (pymupdf.PDF_WIDGET_TYPE_TEXT, pymupdf.PDF_WIDGET_TYPE_COMBOBOX):
                    s = str(v or "").strip()
                    if s or n not in out:
                        out[n] = s
    finally:
        doc.close()
    return out


def firma_campi(pdf):
    doc = pymupdf.open(pdf)
    try:
        return doc.page_count, {w.field_name for p in doc for w in p.widgets()}
    finally:
        doc.close()


def riconosci_xfa(pdf, moduli):
    """Per un modulo del portale (XFA) trova il modello 2022 corrispondente confrontando i campi."""
    from . import xfa
    try:
        campi = xfa.campi_legati(pdf)
    except Exception:
        return None
    if not campi:
        return None
    migliore, punteggio = None, 0.0
    for m in moduli:
        if m.tipo != "xfa":
            continue
        try:
            nm = xfa.campi_legati(m.pdf)
        except Exception:
            continue
        s = len(campi & nm) / max(1, len(campi | nm))
        if s > punteggio:
            migliore, punteggio = m, s
    return migliore if punteggio >= 0.9 else None


def riconosci_modulo(pdf, moduli):
    """Trova a quale modello corrisponde un PDF compilato confrontando i nomi dei campi.
    Ritorna (modulo o None, quota di campi del modello presenti nel PDF)."""
    try:
        _pagine, nomi = firma_campi(pdf)
    except Exception:
        return None, 0.0
    if not nomi:
        return None, 0.0
    migliore, punteggio = None, 0.0
    for m in moduli:
        try:
            _pg, nm = firma_campi(m.pdf)
        except Exception:
            continue
        if not nm:
            continue
        comuni = len(nomi & nm)
        copertura = comuni / len(nm)          # quanti campi del modello ci sono nel PDF
        precisione = comuni / len(nomi)       # quanti campi del PDF sono del modello
        s = copertura if precisione >= 0.6 else 0
        if s > punteggio:
            migliore, punteggio = m, s
    return (migliore, punteggio) if punteggio >= 0.85 else (None, punteggio)


def campi_in_comune(pdf, modulo):
    try:
        return len(firma_campi(pdf)[1] & firma_campi(modulo.pdf)[1])
    except Exception:
        return 0


class _Sovrapposizione:
    """Pratica con dei valori proposti sopra: serve a valutare le condizioni delle regole."""
    def __init__(self, pratica, proposte):
        self.p, self.prop = pratica, proposte

    def get(self, k):
        if k in self.prop:
            return self.prop[k]
        return self.p.get(k)


def _scrivibile(k):
    return k in CAMPI and not k.startswith(("calc.", "comune."))


def estrai_dati(pratica, modulo, valori):
    """Ricava i dati della pratica dai valori di un modulo compilato (mappatura al contrario).
    Ritorna {chiave: valore}."""
    regole = modulo.map.get("campi", {})
    prop, origine = {}, {}

    def proponi(k, v, campo):
        if not _scrivibile(k):
            return
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return
        if k in prop and prop[k] != v:
            return  # il primo valore trovato vince
        prop[k] = v
        origine[k] = campo

    # 1) caselle e pulsanti: decidono le scelte (persona/società, tipo titolo…)
    for nome, r in regole.items():
        if nome not in valori or "k" not in r:
            continue
        val = valori[nome]
        k = r["k"]
        if "radio" in r:
            inv = {str(s): v for v, s in r["radio"].items()}
            if val is not None and str(val) in inv:
                proponi(k, inv[str(val)], nome)
        elif isinstance(val, bool) and not r.get("pieno"):
            if "v" in r:
                if val and not isinstance(r["v"], list):
                    proponi(k, r["v"], nome)
            else:
                tipo = CAMPI.get(k, (None, {}))[1].get("t")
                if tipo == "bool":
                    if val or k != "pratica.dichiarazioni":
                        proponi(k, bool(val), nome)
                elif val:
                    proponi(k, "Sì", nome)

    # 2) testi: valgono solo se la loro condizione è vera con le scelte appena lette
    vista = _Sovrapposizione(pratica, prop)
    for nome, r in regole.items():
        if nome not in valori or "k" not in r or isinstance(valori[nome], bool) or valori[nome] is None:
            continue
        if "radio" in r or r.get("fmt"):
            continue
        if not _condizione_ok(vista, r.get("se")):
            continue
        testo = str(valori[nome]).strip()
        if not testo:
            continue
        if "mappa" in r:
            inv = {v: k for k, v in r["mappa"].items()}
            testo = inv.get(testo, "")
        elif r.get("combo") == "prefisso" and " - " in testo:
            testo = testo.split(" - ")[0].strip()
        if testo:
            proponi(r["k"], testo, nome)
    # direttore lavori: se coincide col progettista non serve copiarlo
    dl = {k: v for k, v in prop.items() if k.startswith("dl.") and k not in ("dl.uguale", "dl.presenta")}
    if dl:
        uguali = all(str(vista.get("progettista." + k[3:]) or "").strip() == str(v).strip() for k, v in dl.items())
        if uguali:
            for k in dl:
                prop.pop(k)
        else:
            prop["dl.uguale"] = False
    return prop


def differenze(pratica, proposte):
    """[(chiave, valore attuale, valore nel PDF)] solo per i dati che cambiano."""
    out = []
    for k, v in proposte.items():
        attuale = pratica.grezzo(k)
        if isinstance(v, bool) or isinstance(attuale, bool):
            if bool(v) != bool(attuale):
                out.append((k, attuale, v))
        elif str(v).strip().lower() != str(attuale or "").strip().lower():
            out.append((k, attuale, v))
    ordine = list(CAMPI.keys())
    return sorted(out, key=lambda x: ordine.index(x[0]) if x[0] in ordine else 9999)


def _collega(pratica, mod_id, pdf):
    """Mette nella pratica il PDF così com'è, dove si trova: niente copie. La cartella del modulo
    diventa quella del file, così «Apri» e i salvataggi lavorano sull'originale."""
    pdf = Path(pdf)
    pratica.dati.setdefault("_cartelle_moduli", {})[mod_id] = pratica._relativo(pdf.parent)
    pratica.registra_modulo(mod_id, pdf, importato=True)
    pratica.salva()
    return pdf


def importa_modulo(pratica, modulo, pdf):
    """Collega alla pratica un modulo compilato fuori dal programma (il file resta l'originale)."""
    return _collega(pratica, modulo.id, pdf)


def importa_xfa(pratica, pdf):
    """Collega alla pratica un modulo dinamico del portale (XFA) non riconosciuto. Ritorna (chiave, percorso)."""
    chiave = "xfa:" + Path(pdf).name
    out = _collega(pratica, chiave, pdf)
    pratica.dati["_moduli"][chiave]["xfa"] = True
    pratica.salva()
    return chiave, out


def cambia_cartella_moduli(pratica, nuova, sposta=True):
    """Imposta una nuova cartella per i moduli della pratica; se sposta=True ci porta i moduli già fatti.
    Ritorna il numero di file spostati."""
    vecchia = pratica.cartella_moduli
    nuova = Path(nuova)
    nuova.mkdir(parents=True, exist_ok=True)
    n = 0
    if sposta and vecchia.exists() and vecchia.resolve() != nuova.resolve():
        for mod_id, info in pratica.dati.get("_moduli", {}).items():
            if pratica.cartella_propria(mod_id):
                continue
            f = vecchia / info.get("file", f"{mod_id}.pdf")
            if f.exists():
                dest = nuova / f.name
                if dest.exists():
                    old = nuova / "_precedenti"
                    old.mkdir(exist_ok=True)
                    shutil.move(str(dest), str(old / f"{dest.stem}_{datetime.now():%Y%m%d-%H%M%S}.pdf"))
                shutil.move(str(f), str(dest))
                n += 1
        prec = vecchia / "_precedenti"
        if prec.exists():
            (nuova / "_precedenti").mkdir(exist_ok=True)
            for f in prec.iterdir():
                shutil.move(str(f), str(nuova / "_precedenti" / f.name))
            try:
                prec.rmdir()
            except OSError:
                pass
    elif not sposta:
        pratica.dati["_moduli"] = {}
    pratica.imposta_cartella_moduli(nuova)
    for mod_id in list(pratica.dati.get("_moduli", {})):
        segna_letto(pratica, mod_id)
    pratica.salva()
    return n


def cambia_cartella_modulo(pratica, mod_id, nuova):
    """Sceglie una cartella solo per questo modulo (None = torna a quella predefinita).
    Se il modulo è già compilato, il PDF viene spostato. Ritorna il nuovo percorso del file."""
    vecchio = pratica.file_modulo(mod_id)
    cart = pratica.dati.setdefault("_cartelle_moduli", {})
    if nuova is None:
        cart.pop(mod_id, None)
    else:
        cart[mod_id] = pratica._relativo(nuova)
    nuovo = pratica.file_modulo(mod_id)
    if vecchio.exists() and vecchio.resolve() != nuovo.resolve():
        nuovo.parent.mkdir(parents=True, exist_ok=True)
        if nuovo.exists():
            old = nuovo.parent / "_precedenti"
            old.mkdir(exist_ok=True)
            shutil.move(str(nuovo), str(old / f"{nuovo.stem}_{datetime.now():%Y%m%d-%H%M%S}.pdf"))
        shutil.move(str(vecchio), str(nuovo))
        segna_letto(pratica, mod_id)
    pratica.salva()
    return nuovo


def moduli_modificati(pratica):
    """Moduli della pratica il cui PDF è stato salvato fuori dal programma dopo l'ultima lettura."""
    out = []
    for mod_id, info in pratica.dati.get("_moduli", {}).items():
        f = pratica.file_modulo(mod_id)
        try:
            mt = f.stat().st_mtime
        except OSError:
            continue
        if abs(mt - float(info.get("mtime", 0))) > 1:
            out.append((mod_id, f))
    return out


def segna_letto(pratica, mod_id):
    info = pratica.dati.get("_moduli", {}).get(mod_id)
    if info:
        f = pratica.file_modulo(mod_id)
        try:
            info["mtime"] = f.stat().st_mtime
        except OSError:
            pass


# --------------------------------------------------------------------------- analisi campi (per insegnare moduli)

def campi_pdf(pdf):
    """Elenco campi del PDF con pagina, tipo e testo vicino (etichetta)."""
    doc = pymupdf.open(pdf)
    out, visti = [], set()
    for pi, page in enumerate(doc):
        words = page.get_text("words")
        for w in sorted(page.widgets(), key=lambda w: (round(w.rect.y0), w.rect.x0)):
            if w.field_name in visti:
                continue
            visti.add(w.field_name)
            r = w.rect
            if w.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
                riga = [x for x in words if abs((x[1] + x[3]) / 2 - (r.y0 + r.y1) / 2) < 6 and x[0] >= r.x0 - 2]
                riga.sort(key=lambda x: x[0])
                lab = " ".join(x[4] for x in riga[:14])
            else:
                sopra = [x for x in words if r.y0 - 16 < x[3] <= r.y0 + 2 and x[2] > r.x0 - 4 and x[0] < r.x1]
                sopra.sort(key=lambda x: x[0])
                lab = " ".join(x[4] for x in sopra[:8])
                if not lab:
                    sx = [x for x in words if abs((x[1] + x[3]) / 2 - (r.y0 + r.y1) / 2) < 6 and x[2] <= r.x0 + 2]
                    sx.sort(key=lambda x: x[0])
                    lab = " ".join(x[4] for x in sx[-6:])
            out.append(dict(nome=w.field_name, pagina=pi + 1, tipo=w.field_type_string, etichetta=lab.strip()))
    doc.close()
    return out


def suggerisci_mappatura(pdf, moduli_mappati):
    """Propone regole per un nuovo modulo copiandole da moduli già mappati
    quando nome del campo ed etichetta coincidono."""
    noti = {}
    for m in moduli_mappati:
        if not m.mappato:
            continue
        try:
            ctx = {c["nome"]: c["etichetta"] for c in campi_pdf(m.pdf)}
        except Exception:
            continue
        for nome, r in m.map["campi"].items():
            noti.setdefault((nome, ctx.get(nome, "")), r)
    proposte = {}
    for c in campi_pdf(pdf):
        r = noti.get((c["nome"], c["etichetta"]))
        if r:
            proposte[c["nome"]] = r
    return proposte
