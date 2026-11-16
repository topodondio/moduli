"""Lettura dei moduli dinamici del portale (PDF XFA creati con Adobe LiveCycle Designer).

Questi PDF non hanno campi compilabili normali: i dati stanno in un file XML ("datasets")
dentro il PDF, con lo schema sygest comune a tutti i moduli del portale. Qui li leggiamo
e li trasformiamo nei dati della pratica. La scrittura non è possibile: si compilano in Acrobat.
"""
import re
import xml.etree.ElementTree as ET

import pymupdf

NS = "{http://schemas.sygest.it/}"

TIPI = {
    "dom_permcostr_e_provv_sanatoria": ("Domanda di permesso di costruire / sanatoria", "Permesso di costruire"),
    "com_inizio_lavori": ("Comunicazione di inizio lavori", None),
    "dich_ultimazione_lavori": ("Dichiarazione di ultimazione lavori", None),
    "mod_cila": ("CILA", "CILA"),
    "mod_op_lib": ("Comunicazione opere libere", "Comunicazione opere libere"),
    "mod_scagi": ("SCAGI – agibilità", None),
    "mod_10_ccee": ("Certificato di conformità di edifici esistenti", None),
    "mod_11_dci": ("Deposito dichiarazione di conformità impianti", None),
}

TITOLI_PROF = ["ING.", "ARCH.", "GEOM.", "DOTT.", "P.I.", "PER. IND.", "PER.IND.", "DOTT. ING.", "DOTT. ARCH.",
               "ING", "ARCH", "GEOM"]
TOPONIMI = ["VIA", "VIALE", "PIAZZA", "LOCALITÀ", "LOCALITA'", "LOCALITA", "LARGO", "CORSO", "VICOLO", "STRADA", "FRAZIONE"]


def leggi_datasets(pdf):
    """XML dei dati XFA, oppure None se il PDF non è un modulo XFA."""
    doc = pymupdf.open(pdf)
    try:
        af = doc.xref_get_key(doc.pdf_catalog(), "AcroForm")
        if af[0] != "xref":
            return None
        xfa = doc.xref_get_key(int(af[1].split()[0]), "XFA")
        if xfa[0] == "array":
            for nome, ref in re.findall(r"\((.*?)\)\s*(\d+) 0 R", xfa[1]):
                if nome == "datasets":
                    return doc.xref_stream(int(ref))
        elif xfa[0] == "xref":
            dati = doc.xref_stream(int(xfa[1].split()[0])) or b""
            m = re.search(rb"<xfa:datasets.*?</xfa:datasets>", dati, re.S)
            return m.group(0) if m else None
    except Exception:
        return None
    finally:
        doc.close()
    return None


def _t(e, path):
    if e is None:
        return ""
    x = e.find("/".join(NS + p for p in path.split("/")))
    return (x.text or "").strip() if x is not None and x.text else ""


def _titolo_case(s):
    return " ".join(w.capitalize() if not re.match(r"^[A-Z]{2}$", w) else w for w in s.split()) if s.isupper() else s


def _separa_nome(nome, cognome):
    """Il portale spesso mette 'COGNOME NOME' tutto nel campo nome."""
    titolo = ""
    n = nome.strip()
    for t in sorted(TITOLI_PROF, key=len, reverse=True):
        if n.upper().startswith(t + " "):
            titolo, n = t.lower().rstrip(".") + ".", n[len(t):].strip()
            break
    if cognome:
        return titolo, cognome.strip(), n
    parti = n.split()
    if len(parti) >= 2:
        return titolo, parti[0], " ".join(parti[1:])
    return titolo, "", n


def _via(ind, tipo=""):
    ind = ind.strip()
    if tipo:
        return tipo.capitalize(), ind
    p = ind.split(" ", 1)
    if len(p) == 2 and p[0].upper() in TOPONIMI:
        return p[0].capitalize(), p[1]
    return "", ind


def tipo_documento(radice):
    d = radice.find(".//" + NS + "dichiarazione")
    if d is None:
        return None, None
    for sez, (titolo, titolo_pratica) in TIPI.items():
        if _t(d, f"{sez}/form_fundamental/hash"):
            return titolo, titolo_pratica
    return "Modulo del portale", None


def estrai(pdf):
    """Ritorna (descrizione del documento, {chiave: valore}) oppure (None, {}) se non è XFA."""
    xml = leggi_datasets(pdf)
    if not xml:
        return None, {}
    try:
        radice = ET.fromstring(xml)
    except ET.ParseError:
        return None, {}
    d = radice.find(".//" + NS + "dichiarazione")
    if d is None:
        return None, {}
    titolo, titolo_pratica = tipo_documento(radice)
    p = {}

    def metti(k, v, comune=False):
        v = (v or "").strip()
        if v:
            p[k] = _titolo_case(v) if comune else v

    metti("pratica.comune", _t(d, "anagrafica_comune/nome"), True)
    metti("pratica.oggetto", _t(d, "intervento/descrizione") or _t(d, "intervento/Descrizione_gen_intervento"))
    if titolo_pratica:
        p["lavori.titolo_tipo"] = titolo_pratica

    # titolare ------------------------------------------------------------------
    t = d.find(NS + "titolare")
    if t is not None:
        ragione = _t(t, "ragione_sociale")
        rif = "referente"
        _tit, cogn, nome = _separa_nome(_t(t, f"{rif}/nome"), _t(t, f"{rif}/cognome"))
        metti("titolare.cognome", cogn)
        metti("titolare.nome", nome)
        metti("titolare.cf", _t(t, f"{rif}/codice_fiscale"))
        metti("titolare.sesso", _t(t, f"{rif}/sesso")[:1].upper())
        metti("titolare.data_nascita", _t(t, f"{rif}/dati_nascita/data"))
        metti("titolare.nascita_stato", _t(t, f"{rif}/dati_nascita/stato"), True)
        metti("titolare.nascita_comune", _t(t, f"{rif}/dati_nascita/luogo") or _t(t, f"{rif}/dati_nascita/comune"), True)
        metti("titolare.nascita_prov", _t(t, f"{rif}/dati_nascita/provincia"))
        dug, via = _via(_t(t, f"{rif}/residenza/indirizzo"), _t(t, f"{rif}/residenza/tipo"))
        metti("titolare.res_dug", dug)
        metti("titolare.res_via", via)
        metti("titolare.res_civico", _t(t, f"{rif}/residenza/numero_civico"))
        metti("titolare.res_comune", _t(t, f"{rif}/residenza/comune"), True)
        metti("titolare.res_prov", _t(t, f"{rif}/residenza/provincia"))
        metti("titolare.res_cap", _t(t, f"{rif}/residenza/cap"))
        metti("titolare.email", _t(t, f"{rif}/contatti/emailPEC") or _t(t, f"{rif}/contatti/email"))
        metti("titolare.tel", _t(t, f"{rif}/contatti/cellulare") or _t(t, f"{rif}/contatti/telefono"))
        if ragione:
            p["titolare.tipo"] = "Società"
            metti("titolare.carica", _t(t, "in_qualita_di"))
            metti("societa.denominazione", ragione)
            metti("societa.cf", _t(t, "codice_fiscale"))
            metti("societa.piva", _t(t, "partita_iva"))
            dug, via = _via(_t(t, "sede_legale/indirizzo"), _t(t, "sede_legale/tipo"))
            metti("societa.sede_dug", dug)
            metti("societa.sede_via", via)
            metti("societa.sede_civico", _t(t, "sede_legale/numero_civico"))
            metti("societa.sede_comune", _t(t, "sede_legale/comune"), True)
            metti("societa.sede_prov", _t(t, "sede_legale/provincia"))
            metti("societa.sede_cap", _t(t, "sede_legale/cap"))
            metti("societa.pec", _t(t, "contatti/emailPEC"))
            metti("societa.tel", _t(t, "contatti/telefono"))
        elif cogn or nome:
            p["titolare.tipo"] = "Persona"
        if _t(t, "chk_titolare_altro_diritto") == "1":
            p["titolarita.tipo"] = "Titolare di altro diritto reale"
        elif _t(t, "chk_titolare_diritto_contr") == "1":
            p["titolarita.tipo"] = "Titolare di diritto contrattuale"
        metti("titolarita.desc", _t(t, "titolare_altro_diritto"))

    # tecnici --------------------------------------------------------------------
    for sez, chiave in (("Progettista", "progettista"), ("DirettoreLavori", "dl")):
        e = d.find(NS + sez)
        if e is None or not (_t(e, "Nome") or _t(e, "Cognome")):
            continue
        tit, cogn, nome = _separa_nome(_t(e, "Nome"), _t(e, "Cognome"))
        metti(f"{chiave}.titolo", tit)
        metti(f"{chiave}.cognome", cogn)
        metti(f"{chiave}.nome", nome)
        metti(f"{chiave}.cf", _t(e, "Codicefiscale"))
        metti(f"{chiave}.sesso", _t(e, "Sesso")[:1].upper())
        metti(f"{chiave}.data_nascita", _t(e, "Nascita/Data"))
        metti(f"{chiave}.nascita_comune", _t(e, "Nascita/Luogo"), True)
        metti(f"{chiave}.nascita_prov", _t(e, "Nascita/Provincia"))
        metti(f"{chiave}.nascita_stato", _t(e, "Nascita/Paese"), True)
        dug, via = _via(_t(e, "Residenza/Indirizzo"))
        metti(f"{chiave}.res_dug", dug)
        metti(f"{chiave}.res_via", via)
        metti(f"{chiave}.res_civico", _t(e, "Residenza/Ncivico"))
        metti(f"{chiave}.res_comune", _t(e, "Residenza/Comune"), True)
        metti(f"{chiave}.res_cap", _t(e, "Residenza/CAP"))
        metti(f"{chiave}.res_prov", _t(e, "Residenza/Provincia"))
        metti(f"{chiave}.studio_via", _t(e, "sede_operativa/indirizzo"))
        metti(f"{chiave}.studio_civico", _t(e, "sede_operativa/numero_civico"))
        metti(f"{chiave}.studio_comune", _t(e, "sede_operativa/comune"), True)
        metti(f"{chiave}.studio_prov", _t(e, "sede_operativa/provincia"))
        metti(f"{chiave}.studio_cap", _t(e, "sede_operativa/cap"))
        metti(f"{chiave}.albo", _t(e, "albo_ordine/nome"))
        metti(f"{chiave}.albo_di", _t(e, "albo_ordine/provincia"), True)
        metti(f"{chiave}.albo_n", _t(e, "albo_ordine/numero"))
        metti(f"{chiave}.tel", _t(e, "Telefono"))
        metti(f"{chiave}.cell", _t(e, "Cellulare"))
        metti(f"{chiave}.fax", _t(e, "fax"))
        metti(f"{chiave}.pec", _t(e, "e-mailPEC"))
        if chiave == "progettista" and _t(e, "chk_incaricato_dl") == "1":
            p["progettista.anche_dl"] = True
    if any(k.startswith("dl.") for k in p):
        p["dl.uguale"] = False

    # impresa --------------------------------------------------------------------
    i = d.find(NS + "impresa_esecutrice")
    if i is not None and _t(i, "ragione_sociale"):
        metti("impresa.denominazione", _t(i, "ragione_sociale"))
        metti("impresa.cf_piva", _t(i, "partita_iva") or _t(i, "codice_fiscale"))
        metti("impresa.sede_via", _t(i, "sede_legale/indirizzo"))
        metti("impresa.sede_civico", _t(i, "sede_legale/numero_civico"))
        metti("impresa.sede_comune", _t(i, "sede_legale/comune"), True)
        metti("impresa.sede_prov", _t(i, "sede_legale/provincia"))
        metti("impresa.sede_cap", _t(i, "sede_legale/cap"))
        metti("impresa.pec", _t(i, "contatti/emailPEC"))
        metti("impresa.tel", _t(i, "contatti/telefono"))
        _x, cogn, nome = _separa_nome(_t(i, "sez1_rappresentanza/Nome"), _t(i, "sez1_rappresentanza/Cognome"))
        metti("impresa.lr_cognome", cogn)
        metti("impresa.lr_nome", nome)
        metti("impresa.lr_cf", _t(i, "sez1_rappresentanza/Codicefiscale"))
        metti("impresa.lr_nato_il", _t(i, "sez1_rappresentanza/Nascita/Data"))
        metti("impresa.lr_nato_a", _t(i, "sez1_rappresentanza/Nascita/Luogo"), True)
        metti("impresa.lr_nato_prov", _t(i, "sez1_rappresentanza/Nascita/Provincia"))
        metti("impresa.lr_cell", _t(i, "sez1_rappresentanza/Cellulare"))
        metti("impresa.lr_email", _t(i, "sez1_rappresentanza/e-mail"))

    # immobile --------------------------------------------------------------------
    u = "intervento/localizzazione/ubicazione"
    ind = _t(d, f"{u}/indirizzo")
    if _t(d, f"{u}/tipo") and ind:
        ind = f"{_t(d, f'{u}/tipo').capitalize()} {ind}"
    metti("immobile.via", _titolo_case(ind) if ind else "")
    metti("immobile.civico", _t(d, f"{u}/numero_civico"))
    metti("immobile.comune", _t(d, f"{u}/comune"), True)
    metti("immobile.cap", _t(d, f"{u}/cap"))
    metti("immobile.prov", _t(d, f"{u}/provincia"))
    righe = []
    for base in ("intervento/localizzazione", "intervento"):
        loc = d.find("/".join(NS + x for x in base.split("/")))
        if loc is None:
            continue
        for tag, col in (("particelle_edificabili", "ped"), ("particelle_fondiarie", "pf")):
            for e in loc.findall(NS + tag):
                num = _t(e, "numero")
                if num:
                    r = {col: num, "cc": _titolo_case(_t(e, "cc")), "pm": _t(e, "pm"), "sub": _t(e, "subalterno")}
                    if r not in righe:
                        righe.append(r)
    for n, r in enumerate(righe[:5]):
        for col, v in r.items():
            if v:
                p[f"immobile.particelle.{n}.{col}"] = v
    metti("immobile.zona_prg", _t(d, "dichiarazioni_progettista/PRG_vigente/zona"))
    metti("immobile.zona_prg_adottato", _t(d, "dichiarazioni_progettista/PRG_adottato/zona"))

    # contributo di costruzione (solo se il portale lo indica chiaramente) ---------------
    if _t(d, "attesta/contrib_costr_interventi_sogg_contrib") == "1":
        p["pdc.contributo"] = "Soggetto - si invierà la ricevuta di pagamento"
    elif _t(d, "attesta/contrib_costr_interventi_nonsogg_contrib") == "1":
        p["pdc.contributo"] = "Non soggetto (nessun aumento del carico urbanistico)"
    return titolo, p
