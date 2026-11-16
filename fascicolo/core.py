"""Logica di Fascicolo: archivio pratiche, dati, mappature e compilazione PDF."""
import json
import os
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
SOTTOCARTELLE = ["Moduli", "Elaborati", "Allegati", "Consegne", "Ricevute"]


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


# --------------------------------------------------------------------------- config

def carica_config():
    cfg = leggi_json(CONFIG_FILE, {})
    cfg.setdefault("archivio", str(Path.home() / "Documents" / "Pratiche"))
    return cfg


def salva_config(cfg):
    scrivi_json(CONFIG_FILE, cfg)


# --------------------------------------------------------------------------- pratica

class Pratica:
    def __init__(self, cartella, dati=None):
        self.cartella = Path(cartella)
        self.dati = dati if dati is not None else leggi_json(self.cartella / FILE_PRATICA, {})
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
        self.valori[key] = val

    @property
    def nome(self):
        return self.valori.get("pratica.nome") or self.cartella.name

    def salva(self):
        self.dati["_modificata"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        scrivi_json(self.cartella / FILE_PRATICA, self.dati)

    def registra_modulo(self, mod_id, file_out, importato=False):
        info = {"file": str(Path(file_out).name), "data": datetime.now().strftime("%d/%m/%Y %H:%M")}
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

    def nuova(self, nome, comune=""):
        anno = datetime.now().year
        esistenti = [p.name for p in self.radice.iterdir() if p.is_dir()]
        n = 1 + sum(1 for e in esistenti if e.startswith(f"{anno}-"))
        cartella = self.radice / _slug(f"{anno}-{n:03d} {nome}")
        cartella.mkdir()
        for s in SOTTOCARTELLE:
            (cartella / s).mkdir()
        p = Pratica(cartella, {"_valori": {"pratica.nome": nome, "pratica.comune": comune,
                                           "immobile.comune": comune}})
        p.salva()
        return p

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

    @property
    def id(self):
        return self.pdf.stem

    @property
    def titolo(self):
        return self.map.get("titolo") or self.pdf.stem.replace("_", " ")

    @property
    def mappato(self):
        return bool(self.map.get("campi"))

    @property
    def gruppo(self):
        return self.map.get("gruppo", "")


def elenco_moduli(archivio=None):
    mapp = {}
    for d in [MAPPATURE_DIR] + ([archivio.cartella_mappature()] if archivio else []):
        for f in sorted(Path(d).glob("*.json")):
            m = leggi_json(f, {})
            if m.get("modulo"):
                mapp[m["modulo"]] = (m, f)
    out = []
    for pdf in sorted(MODULI_DIR.glob("*.pdf")):
        m, f = mapp.get(pdf.name, (None, None))
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
    if out.exists():  # tieni la versione precedente
        old = pratica.cartella / "Moduli" / "_precedenti"
        old.mkdir(exist_ok=True)
        shutil.copy2(out, old / f"{modulo.id}_{datetime.now():%Y%m%d-%H%M%S}.pdf")


def genera(pratica, modulo):
    """Compila il modulo. Se esiste già una versione compilata, i campi che il programma
    non gestisce (scelte tecniche, spunte fatte a mano nel PDF…) vengono conservati."""
    out = pratica.cartella / "Moduli" / f"{modulo.id}.pdf"
    conserva = None
    if out.exists():
        regole = modulo.map.get("campi", {})
        try:
            conserva = {k: v for k, v in leggi_valori(out).items() if k not in regole}
        except Exception:
            conserva = None
    _archivia_precedente(pratica, modulo, out)
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


def riconosci_modulo(pdf, moduli):
    """Trova a quale modello corrisponde un PDF compilato confrontando i nomi dei campi."""
    try:
        pagine, nomi = firma_campi(pdf)
    except Exception:
        return None, 0.0
    if not nomi:
        return None, 0.0
    migliore, punteggio = None, 0.0
    for m in moduli:
        try:
            pg, nm = firma_campi(m.pdf)
        except Exception:
            continue
        if not nm or pg != pagine:
            continue
        s = len(nomi & nm) / len(nomi | nm)
        if s > punteggio:
            migliore, punteggio = m, s
    return (migliore, punteggio) if punteggio >= 0.9 else (None, punteggio)


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
        elif str(v).strip() != str(attuale or "").strip():
            out.append((k, attuale, v))
    ordine = list(CAMPI.keys())
    return sorted(out, key=lambda x: ordine.index(x[0]) if x[0] in ordine else 9999)


def importa_modulo(pratica, modulo, pdf):
    """Copia un modulo compilato fuori dal programma nella cartella Moduli della pratica."""
    out = pratica.cartella / "Moduli" / f"{modulo.id}.pdf"
    if Path(pdf).resolve() != out.resolve():
        _archivia_precedente(pratica, modulo, out)
        shutil.copy2(pdf, out)
    pratica.registra_modulo(modulo.id, out, importato=True)
    pratica.salva()
    return out


def moduli_modificati(pratica):
    """Moduli della pratica il cui PDF è stato salvato fuori dal programma dopo l'ultima lettura."""
    out = []
    for mod_id, info in pratica.dati.get("_moduli", {}).items():
        f = pratica.cartella / "Moduli" / info.get("file", f"{mod_id}.pdf")
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
        f = pratica.cartella / "Moduli" / info.get("file", f"{mod_id}.pdf")
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
