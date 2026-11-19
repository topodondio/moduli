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
    v = (x.text or "").strip() if x is not None and x.text else ""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)  # le date XFA sono AAAA-MM-GG
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else v


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

    # campi dei singoli moduli 2022 ----------------------------------------------------------
    for path, k in SPECIFICI:
        metti(k, _t(d, path), k in ("immobile.destinazione",) and False)
    for base, chiave, nomi in TECNICI:
        n = nomi or _TEC_STD
        e = d.find("/".join(NS + x for x in base.split("/")))
        if e is None or not _t(e, n["nome"]):
            continue
        tit, cogn, nome = _separa_nome(_t(e, n["nome"]), "")
        for k, val in ((f"{chiave}.cognome", cogn), (f"{chiave}.nome", nome), (f"{chiave}.titolo", tit),
                       (f"{chiave}.cf", _t(e, n["cf"])), (f"{chiave}.albo", _t(e, n["albo"])),
                       (f"{chiave}.albo_n", _t(e, n["albo_n"])), (f"{chiave}.pec", _t(e, n["pec"]))):
            if val and k not in p:
                p[k] = val
    # inizio lavori 2022: sottoscrivente / legale rappresentante -> titolare
    e_s = d.find("/".join(NS + q for q in "com_inizio_lavori/sottoscrivente".split("/")))
    e_l = d.find("/".join(NS + q for q in "com_inizio_lavori/legale_rappresentante".split("/")))
    pers = e_l if e_l is not None and _t(e_l, "Nome") else e_s
    if pers is not None and _t(pers, "Nome") and "titolare.cognome" not in p:
        if pers is e_l and _t(e_s, "Nome"):
            p.setdefault("titolare.tipo", "Società")
            for k, q in (("societa.denominazione", "Nome"), ("societa.cf", "Codicefiscale"),
                         ("societa.piva", "PIVAsottoscritto"), ("societa.sede_comune", "Residenza/Comune"),
                         ("societa.sede_civico", "Residenza/Ncivico"), ("societa.sede_cap", "Residenza/CAP")):
                if _t(e_s, q):
                    p.setdefault(k, _t(e_s, q))
        _tit, cogn, nome = _separa_nome(_t(pers, "Nome"), "")
        for k, val in (("titolare.cognome", cogn), ("titolare.nome", nome), ("titolare.cf", _t(pers, "Codicefiscale")),
                       ("titolare.data_nascita", _t(pers, "Nascita/Data")),
                       ("titolare.nascita_comune", _t(pers, "Nascita/Luogo")),
                       ("titolare.res_comune", _t(pers, "Residenza/Comune")),
                       ("titolare.res_civico", _t(pers, "Residenza/Ncivico")),
                       ("titolare.res_cap", _t(pers, "Residenza/CAP")), ("titolare.tel", _t(pers, "Residenza/Telefono"))):
            if val:
                p.setdefault(k, val)
    if any(k.startswith("dl.") and k != "dl.uguale" for k in p):
        # il DL è «diverso dal progettista» solo se nel modulo ci sono entrambi e non coincidono
        if p.get("progettista.cognome") and p.get("dl.cognome"):
            p["dl.uguale"] = (p["progettista.cognome"].lower() == p["dl.cognome"].lower()
                              and str(p.get("progettista.nome", "")).lower() == str(p.get("dl.nome", "")).lower())
        else:
            p.pop("dl.uguale", None)

    # contributo di costruzione (solo se il portale lo indica chiaramente) ---------------
    if _t(d, "attesta/contrib_costr_interventi_sogg_contrib") == "1":
        p["pdc.contributo"] = "Soggetto - si invierà la ricevuta di pagamento"
    elif _t(d, "attesta/contrib_costr_interventi_nonsogg_contrib") == "1":
        p["pdc.contributo"] = "Non soggetto (nessun aumento del carico urbanistico)"
    return titolo, p


# =========================================================================== scrittura

NS_XFA = "http://www.xfa.org/schema/xfa-data/1.0/"
NS_DD = "http://ns.adobe.com/data-description/"
NS_SYG = "http://schemas.sygest.it/"


def _pacchetti(doc):
    af = doc.xref_get_key(doc.pdf_catalog(), "AcroForm")
    if af[0] != "xref":
        return {}
    xfa = doc.xref_get_key(int(af[1].split()[0]), "XFA")
    if xfa[0] != "array":
        return {}
    return {n: int(r) for n, r in re.findall(r"\((.*?)\)\s*(\d+) 0 R", xfa[1])}


class Legati(set):
    """Insieme dei percorsi collegati; .date = quelli che il modulo tratta come date (AAAA-MM-GG)."""
    date = frozenset()


def _data_iso(v):
    m = re.fullmatch(r"\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*", str(v))
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else v


def campi_legati(pdf):
    """Percorsi (relativi a 'dichiarazione') dei campi che il modulo mostra davvero.
    Segue i collegamenti del modello XFA, anche quelli relativi al sottomodulo che li contiene."""
    doc = pymupdf.open(pdf)
    try:
        p = _pacchetti(doc)
        if "template" not in p:
            return set()
        t = doc.xref_stream(p["template"])
    finally:
        doc.close()
    try:
        radice = ET.fromstring(t)
    except ET.ParseError:
        testo = t.decode("utf-8", "replace")
        return Legati(r.replace(".", "/") for r in re.findall(r'ref="\$\.dichiarazione\.([^"\[]+)"', testo))
    out = Legati()
    date = set()

    def locale(e):
        return e.tag.rsplit("}", 1)[-1]

    def percorso(ctx, ref):
        ref = re.sub(r"\[[^\]]*\]", "", ref)
        if ref.startswith("$record."):
            parti = ref[8:].split(".")
        elif ref.startswith("$."):
            parti = ctx + ref[2:].split(".")
        elif ref.startswith("$"):
            return None
        else:
            parti = ctx + ref.split(".")
        return [x for x in parti if x]

    def visita(e, ctx):
        for c in e:
            tipo = locale(c)
            if tipo not in ("subform", "subformSet", "field", "exclGroup", "area", "pageSet", "pageArea"):
                visita(c, ctx) if tipo in ("proto",) else None
                continue
            nuovo = ctx
            e_data = False
            for b in c:
                if locale(b) == "bind" and b.get("match") == "dataRef" and b.get("ref"):
                    pp = percorso(ctx, b.get("ref"))
                    if pp is not None:
                        nuovo = pp
                    e_data = any(locale(q) == "picture" and (q.text or "").startswith("date{") for q in b)
            if tipo in ("field",) or (tipo == "exclGroup" and nuovo is not ctx):
                if nuovo is not ctx and nuovo and nuovo[0] == "dichiarazione":
                    out.add("/".join(nuovo[1:]))
                    if e_data:
                        date.add("/".join(nuovo[1:]))
                if tipo == "field":
                    continue
            visita(c, nuovo)

    visita(radice, [])
    out.date = frozenset(date)
    return out


def _nome_completo(pratica, sez, titolo=False):
    parti = [pratica.get(f"{sez}.titolo") if titolo else "", pratica.get(f"{sez}.cognome"), pratica.get(f"{sez}.nome")]
    return " ".join(str(x).strip() for x in parti if str(x or "").strip())


def _via_completa(pratica, sez, pref):
    return " ".join(str(x).strip() for x in (pratica.get(f"{sez}.{pref}_dug"), pratica.get(f"{sez}.{pref}_via"))
                    if str(x or "").strip())


def valori_da_scrivere(pratica, legati):
    """{percorso: valore} con i dati della pratica, solo per i campi presenti nel modulo."""
    g = pratica.get
    v = {}

    def metti(path, val):
        if path in legati and val not in (None, ""):
            v[path] = str(val)

    metti("anagrafica_comune/nome", str(g("pratica.comune") or "").upper())
    metti("intervento/descrizione", g("pratica.oggetto"))
    # titolare (se è una società, la persona è il legale rappresentante)
    r = "titolare/referente"
    if f"{r}/cognome" in legati:
        metti(f"{r}/cognome", g("titolare.cognome"))
        metti(f"{r}/nome", g("titolare.nome"))
    else:
        metti(f"{r}/nome", _nome_completo(pratica, "titolare"))
    metti(f"{r}/codice_fiscale", g("titolare.cf"))
    metti(f"{r}/dati_nascita/data", g("titolare.data_nascita"))
    metti(f"{r}/dati_nascita/luogo", g("titolare.nascita_comune"))
    metti(f"{r}/dati_nascita/provincia", g("titolare.nascita_prov"))
    metti(f"{r}/dati_nascita/stato", g("titolare.nascita_stato"))
    metti(f"{r}/residenza/indirizzo", _via_completa(pratica, "titolare", "res"))
    metti(f"{r}/residenza/numero_civico", g("titolare.res_civico"))
    metti(f"{r}/residenza/comune", g("titolare.res_comune"))
    metti(f"{r}/residenza/provincia", g("titolare.res_prov"))
    metti(f"{r}/residenza/cap", g("titolare.res_cap"))
    metti(f"{r}/contatti/email", g("titolare.email"))
    metti(f"{r}/contatti/telefono", g("titolare.tel"))
    if g("titolare.tipo") == "Società":
        metti("titolare/in_qualita_di", g("titolare.carica"))
        metti("titolare/ragione_sociale", g("societa.denominazione"))
        metti("titolare/partita_iva", g("societa.piva") or g("societa.cf"))
        metti("titolare/sede_legale/indirizzo", " ".join(x for x in [_via_completa(pratica, "societa", "sede"),
                                                                    str(g("societa.sede_civico") or "")] if x))
        metti("titolare/sede_legale/comune", g("societa.sede_comune"))
        metti("titolare/contatti/emailPEC", g("societa.pec"))
        metti("titolare/contatti/telefono", g("societa.tel"))
    else:
        metti("titolare/in_qualita_di", g("titolare.qualita"))
    if g("titolarita.tipo") != "Proprietario esclusivo":
        metti("titolare/titolare_altro_diritto", g("titolarita.desc"))
    # tecnici
    for sez, chiave in (("Progettista", "progettista"), ("DirettoreLavori", "dl")):
        if f"{sez}/Cognome" in legati:
            metti(f"{sez}/Cognome", g(f"{chiave}.cognome"))
            metti(f"{sez}/Nome", g(f"{chiave}.nome"))
        else:
            metti(f"{sez}/Nome", _nome_completo(pratica, chiave, titolo=True))
        metti(f"{sez}/Codicefiscale", g(f"{chiave}.cf"))
        metti(f"{sez}/Nascita/Data", g(f"{chiave}.data_nascita"))
        metti(f"{sez}/Nascita/Luogo", g(f"{chiave}.nascita_comune"))
        metti(f"{sez}/Nascita/Provincia", g(f"{chiave}.nascita_prov"))
        metti(f"{sez}/Residenza/Indirizzo", _via_completa(pratica, chiave, "res"))
        metti(f"{sez}/Residenza/Ncivico", g(f"{chiave}.res_civico"))
        metti(f"{sez}/Residenza/Comune", g(f"{chiave}.res_comune"))
        metti(f"{sez}/Residenza/CAP", g(f"{chiave}.res_cap"))
        metti(f"{sez}/Residenza/Provincia", g(f"{chiave}.res_prov"))
        for base in ("sede_operativa", "Recapito"):
            low = base == "sede_operativa"
            metti(f"{sez}/{base}/{'indirizzo' if low else 'Indirizzo'}", g(f"{chiave}.studio_via"))
            metti(f"{sez}/{base}/{'numero_civico' if low else 'Ncivico'}", g(f"{chiave}.studio_civico"))
            metti(f"{sez}/{base}/{'comune' if low else 'Comune'}", g(f"{chiave}.studio_comune"))
            metti(f"{sez}/{base}/{'provincia' if low else 'Provincia'}", g(f"{chiave}.studio_prov"))
            metti(f"{sez}/{base}/{'cap' if low else 'CAP'}", g(f"{chiave}.studio_cap"))
        metti(f"{sez}/albo_ordine/nome", g(f"{chiave}.albo"))
        metti(f"{sez}/albo_ordine/numero", g(f"{chiave}.albo_n"))
        metti(f"{sez}/albo_ordine/provincia", g(f"{chiave}.albo_di"))
        metti(f"{sez}/Telefono", g(f"{chiave}.tel"))
        metti(f"{sez}/Cellulare", g(f"{chiave}.cell"))
        metti(f"{sez}/fax", g(f"{chiave}.fax"))
        metti(f"{sez}/e-mailPEC", g(f"{chiave}.pec"))
    if "Progettista/chk_incaricato_dl" in legati:
        v["Progettista/chk_incaricato_dl"] = "1" if g("progettista.anche_dl") else "0"
    # impresa
    metti("impresa_esecutrice/ragione_sociale", g("impresa.denominazione"))
    metti("impresa_esecutrice/codice_fiscale", g("impresa.cf_piva"))
    # immobile
    u = "intervento/localizzazione/ubicazione"
    metti(f"{u}/indirizzo", g("immobile.via"))
    metti(f"{u}/numero_civico", g("immobile.civico"))
    metti(f"{u}/comune", str(g("immobile.comune") or "").upper())
    metti(f"{u}/provincia", g("immobile.prov"))
    righe = pratica._particelle()
    ped = next((x for x in righe if x["ped"]), None)
    pf = next((x for x in righe if x["pf"]), None)
    pe = "intervento/localizzazione/particelle_edificabili"
    if ped:
        metti(f"{pe}/numero", ped["ped"])
        metti(f"{pe}/cc", str(ped["cc"]).upper())
        metti(f"{pe}/pm", ped["pm"])
        metti(f"{pe}/subalterno", ped["sub"])
    pfo = "intervento/localizzazione/particelle_fondiarie"
    if pf:
        metti(f"{pfo}/numero", pf["pf"])
        metti(f"{pfo}/cc", str(pf["cc"]).upper())
    _specifici_scrivi(pratica, legati, metti)
    return v


# campi propri dei singoli moduli 2022: (percorso, chiave della pratica) — valgono in scrittura e lettura
SPECIFICI = [
    ("com_inizio_lavori/comunica/inizio_lavori_data", "lavori.data_inizio"),
    ("com_inizio_lavori/comunica/perm_costruire_n_prot", "lavori.titolo_n"),
    ("com_inizio_lavori/comunica/perm_costruire_data", "lavori.titolo_data"),
    ("com_inizio_lavori/dichiara_e_allega/soggetto_indica_data", "lavori.notifica_data"),
    ("com_inizio_lavori/dichiara_e_allega/soggetto_indica_num", "lavori.notifica_prot"),
    ("com_inizio_lavori/imprese_lav_auton/ragione_sociale", "impresa.denominazione"),
    ("com_inizio_lavori/imprese_lav_auton/CF_PIVA", "impresa.cf_piva"),
    ("com_inizio_lavori/imprese_lav_auton/Indirizzo", "impresa.sede_via"),
    ("com_inizio_lavori/imprese_lav_auton/Ncivico", "impresa.sede_civico"),
    ("com_inizio_lavori/imprese_lav_auton/Comune", "impresa.sede_comune"),
    ("com_inizio_lavori/imprese_lav_auton/CAP", "impresa.sede_cap"),
    ("com_inizio_lavori/imprese_lav_auton/Telefono", "impresa.tel"),
    ("com_inizio_lavori/imprese_lav_auton/Fax", "impresa.fax"),
    ("com_inizio_lavori/imprese_lav_auton/e-mailPEC", "impresa.pec"),
    ("dich_ultimazione_lavori/comunica/conclusione_lavori_data", "lavori.data_fine"),
    ("mod_scagi/prot_dich_ult_lav", "lavori.fine_prot"),
    ("mod_scagi/data_dich_ult_lav", "lavori.fine_prot_data"),
    ("mod_scagi/elenco_titoli_edilizi/titolo_abilitativo", "lavori.titolo_tipo"),
    ("mod_scagi/elenco_titoli_edilizi/num_dia", "lavori.titolo_n"),
    ("mod_scagi/elenco_titoli_edilizi/data_dia", "lavori.titolo_data"),
    ("elenco_titoli_edilizi/titolo_abilitativo", "lavori.titolo_tipo"),
    ("elenco_titoli_edilizi/num_dia", "lavori.titolo_n"),
    ("elenco_titoli_edilizi/data_dia", "lavori.titolo_data"),
    ("mod_10_ccee/certifica_uso", "immobile.destinazione"),
]
# blocchi "immobile" ripetuti dentro i singoli moduli
UBICAZIONI = ["com_inizio_lavori/intervento", "mod_scagi/elenco_realta_immobiliari"]
# tecnici dentro i singoli moduli: (percorso, chiave, nomi dei sotto-campi)
TECNICI = [
    ("com_inizio_lavori/comunica/direttore_lavori", "dl",
     {"nome": "direttore_lavori/Nome", "cf": "direttore_lavori/Codicefiscale",
      "albo": "dir_lavori_albo_ordine/albo_ordine", "albo_n": "dir_lavori_albo_ordine/albo_numero",
      "albo_di": "dir_lavori_albo_ordine/albo_provincia", "via": "studio_ente_societa/Indirizzo",
      "civico": "studio_ente_societa/Ncivico", "comune": "studio_ente_societa/Comune",
      "cap": "studio_ente_societa/CAP", "tel": "studio_ente_societa/Telefono", "fax": "studio_ente_societa/Fax",
      "pec": "studio_ente_societa/e-mailPEC"}),
    ("mod_10_ccee/tecnico_abilitato", "progettista", None),
    ("mod_scagi/tecnico_abilitato", "dl", None),
]
_TEC_STD = {"nome": "Nome", "cf": "Codicefiscale", "albo": "albo_ordine/nome", "albo_n": "albo_ordine/numero",
            "albo_di": "albo_ordine/provincia", "via": "Recapito/Indirizzo", "comune": "Recapito/Comune",
            "cap": "Recapito/CAP", "tel": "Telefono", "fax": "fax", "pec": "e-mailPEC"}


def _specifici_scrivi(pratica, legati, metti):
    g = pratica.get
    for path, k in SPECIFICI:
        metti(path, g(k))
    righe = pratica._particelle()
    ped = next((x for x in righe if x["ped"]), None)
    pf = next((x for x in righe if x["pf"]), None)
    for base in UBICAZIONI:
        metti(f"{base}/ubicazione/Comune", g("immobile.comune"))
        metti(f"{base}/ubicazione/Indirizzo", g("immobile.via"))
        metti(f"{base}/ubicazione/Ncivico", g("immobile.civico"))
        metti(f"{base}/ubicazione/Scala", g("immobile.scala"))
        metti(f"{base}/ubicazione/Piano", g("immobile.piano"))
        metti(f"{base}/ubicazione/Interno", g("immobile.interno"))
        if ped:
            metti(f"{base}/particelle_edificabili/numero", ped["ped"])
            metti(f"{base}/particelle_edificabili/cc", ped["cc"])
            metti(f"{base}/particelle_edificabili/pm", ped["pm"])
            metti(f"{base}/particelle_edificabili/subalterno", ped["sub"])
        if pf:
            metti(f"{base}/particelle_fondiarie/numero", pf["pf"])
            metti(f"{base}/particelle_fondiarie/cc", pf["cc"])
    if ped:
        metti("mod_10_ccee/certifica_ped", ped["ped"])
        metti("mod_10_ccee/certifica_cc", ped["cc"])
        metti("mod_10_ccee/certifica_pm", ped["pm"])
        metti("mod_10_ccee/certifica_sub", ped["sub"])
    metti("mod_10_ccee/certifica_ubi_via", g("immobile.via"))
    metti("mod_10_ccee/certifica_ubi_civ", g("immobile.civico"))
    metti("mod_10_ccee/certifica_ubi_loc", g("immobile.comune"))
    # inizio lavori 2022 (anche dentro PdC e ultimazione): sottoscrivente e legale rappresentante
    S, L = "com_inizio_lavori/sottoscrivente", "com_inizio_lavori/legale_rappresentante"

    def persona(base, piva_campo=None):
        metti(f"{base}/Nome", _nome_completo(pratica, "titolare"))
        metti(f"{base}/Codicefiscale", g("titolare.cf"))
        metti(f"{base}/Nascita/Data", g("titolare.data_nascita"))
        metti(f"{base}/Nascita/Luogo", g("titolare.nascita_comune"))
        metti(f"{base}/Residenza/Comune", g("titolare.res_comune"))
        metti(f"{base}/Residenza/Indirizzo", _via_completa(pratica, "titolare", "res"))
        metti(f"{base}/Residenza/Ncivico", g("titolare.res_civico"))
        metti(f"{base}/Residenza/CAP", g("titolare.res_cap"))
        metti(f"{base}/Residenza/Telefono", g("titolare.tel"))
    if g("titolare.tipo") == "Società":
        metti(f"{S}/Nome", g("societa.denominazione"))
        metti(f"{S}/Codicefiscale", g("societa.cf"))
        metti(f"{S}/PIVAsottoscritto", g("societa.piva"))
        metti(f"{S}/Residenza/Comune", g("societa.sede_comune"))
        metti(f"{S}/Residenza/Indirizzo", _via_completa(pratica, "societa", "sede"))
        metti(f"{S}/Residenza/Ncivico", g("societa.sede_civico"))
        metti(f"{S}/Residenza/CAP", g("societa.sede_cap"))
        metti(f"{S}/Residenza/Telefono", g("societa.tel"))
        persona(L)
    else:
        persona(S)
    for base, chiave, nomi in TECNICI:
        n = nomi or _TEC_STD
        metti(f"{base}/{n['nome']}", _nome_completo(pratica, chiave, titolo=True))
        for campo, k in (("cf", "cf"), ("albo", "albo"), ("albo_n", "albo_n"), ("albo_di", "albo_di"),
                         ("comune", "studio_comune"), ("cap", "studio_cap"), ("tel", "tel"), ("fax", "fax"),
                         ("pec", "pec")):
            if campo in n:
                metti(f"{base}/{n[campo]}", g(f"{chiave}.{k}"))
        if "civico" in n:
            metti(f"{base}/{n['via']}", g(f"{chiave}.studio_via"))
            metti(f"{base}/{n['civico']}", g(f"{chiave}.studio_civico"))
        else:
            metti(f"{base}/{n['via']}", " ".join(str(x) for x in (g(f"{chiave}.studio_via"), g(f"{chiave}.studio_civico")) if x))


def _nodo(radice_dich, path):
    e = radice_dich
    for parte in path.split("/"):
        f = e.find(NS + parte)
        if f is None:
            f = ET.SubElement(e, NS + parte)
        e = f
    return e


def ha_diritti(pdf):
    """True se il PDF ha ancora la firma "funzioni estese di Reader" (UR3): senza, Acrobat Reader
    non permette di salvare i moduli dinamici compilati."""
    try:
        doc = pymupdf.open(pdf)
        try:
            return doc.xref_get_key(doc.pdf_catalog(), "Perms")[0] != "null"
        finally:
            doc.close()
    except Exception:
        return False


def da_ricostruire(modello, compilato):
    """Il modulo compilato ha perso i diritti di salvataggio che il modello originale ha
    (moduli fatti con Fascicolo 0.7.0–0.7.3): va rifatto dal modello conservando i dati."""
    from pathlib import Path
    return Path(compilato).exists() and ha_diritti(modello) and not ha_diritti(compilato)


def scrivi(modello, uscita, pratica):
    """Scrive i dati della pratica nel pacchetto 'datasets' del modulo del portale.
    Se `uscita` esiste già scrive lì dentro (restano i campi compilati a mano), altrimenti parte
    dal modello originale. Si salva in modo incrementale toccando solo i dati del modulo, come fa
    Acrobat Reader: la firma che permette di salvarlo in Reader resta valida.
    Ritorna (campi scritti, campi possibili)."""
    import shutil
    from pathlib import Path
    modello, uscita = Path(modello), Path(uscita)
    vecchi = None
    if uscita.exists() and modello.resolve() != uscita.resolve() and da_ricostruire(modello, uscita):
        vecchi = leggi_datasets(uscita)  # dati già scritti (anche a mano) da riportare sul modello
        shutil.copyfile(modello, uscita)
    elif not uscita.exists():
        shutil.copyfile(modello, uscita)
    legati = campi_legati(uscita)
    valori = valori_da_scrivere(pratica, legati)
    doc = pymupdf.open(uscita)
    try:
        p = _pacchetti(doc)
        for pref, uri in (("xfa", NS_XFA), ("dd", NS_DD), ("", NS_SYG)):
            ET.register_namespace(pref, uri)
        radice = ET.fromstring(vecchi if vecchi else doc.xref_stream(p["datasets"]))
        dich = radice.find(".//" + NS + "dichiarazione")
        if dich is None:
            raise ValueError("struttura dati del modulo non riconosciuta")
        for path, val in valori.items():
            _nodo(dich, path).text = _data_iso(val) if path in legati.date else val
        doc.update_stream(p["datasets"], ET.tostring(radice, encoding="utf-8"))
        doc.saveIncr()
    finally:
        doc.close()
    return len(valori), len(legati)
