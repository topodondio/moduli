"""Schema della scheda pratica.

Ogni sezione ha una chiave e un elenco di campi. Ogni campo ha:
  k      chiave (unica nella sezione)
  l      etichetta mostrata
  t      tipo: text | date | choice | bool | long | table
  opz    True se facoltativo (non viene chiesto quando manca)
  def    valore predefinito
  scelte elenco valori per i campi "choice"
  rubrica  (solo sezione) nome della rubrica da cui si può pescare
"""

ITALIA = "Italia"

def _anagrafica(nascita=True, residenza=True):
    c = [
        dict(k="cognome", l="Cognome"),
        dict(k="nome", l="Nome"),
        dict(k="cf", l="Codice fiscale"),
        dict(k="sesso", l="Sesso", t="choice", scelte=["", "M", "F"]),
        dict(k="data_nascita", l="Data di nascita", t="date"),
        dict(k="cittadinanza", l="Cittadinanza", **{"def": "Italiana"}),
    ]
    if nascita:
        c += [
            dict(k="nascita_stato", l="Nato in (Stato)", **{"def": ITALIA}),
            dict(k="nascita_prov", l="Provincia di nascita"),
            dict(k="nascita_comune", l="Comune di nascita"),
        ]
    if residenza:
        c += [
            dict(k="res_stato", l="Residenza: Stato", **{"def": ITALIA}),
            dict(k="res_prov", l="Residenza: Provincia", **{"def": "TN"}),
            dict(k="res_comune", l="Residenza: Comune"),
            dict(k="res_dug", l="Toponimo (via, piazza…)", **{"def": "Via"}),
            dict(k="res_via", l="Denominazione stradale"),
            dict(k="res_civico", l="Numero civico"),
            dict(k="res_cap", l="CAP"),
        ]
    return c


def _tecnico():
    return [dict(k="titolo", l="Titolo (arch., ing., geom.…)", opz=True)] + _anagrafica() + [
        dict(k="studio_stato", l="Studio: Stato", **{"def": ITALIA}),
        dict(k="studio_prov", l="Studio: Provincia", **{"def": "TN"}),
        dict(k="studio_comune", l="Studio: Comune"),
        dict(k="studio_via", l="Studio: Via e piazza"),
        dict(k="studio_civico", l="Studio: Numero civico"),
        dict(k="studio_cap", l="Studio: CAP"),
        dict(k="albo", l="Iscritto all'ordine/collegio/albo"),
        dict(k="albo_di", l="Albo di (provincia)", **{"def": "Trento"}),
        dict(k="albo_n", l="Numero iscrizione"),
        dict(k="tel", l="Telefono", opz=True),
        dict(k="fax", l="Fax", opz=True),
        dict(k="cell", l="Cellulare", opz=True),
        dict(k="pec", l="PEC"),
    ]


SEZIONI = [
    dict(k="pratica", l="Pratica", campi=[
        dict(k="nome", l="Nome pratica (es. Rossi - ampliamento)"),
        dict(k="comune", l="Comune", t="comune"),
        dict(k="oggetto", l="Oggetto (descrizione sintetica, max 300 caratteri)", t="long"),
        dict(k="domicilio_digitale", l="Domicilio digitale INAD del dichiarante", opz=True),
        dict(k="pec_comunicazioni", l="PEC per le comunicazioni dello Sportello"),
        dict(k="data_presentazione", l="Data (presunta) di presentazione", t="date", opz=True),
        dict(k="dichiarazioni", l="Spunta le dichiarazioni obbligatorie (consapevolezza, privacy, diritti di terzi…)",
             t="bool", **{"def": True}),
        dict(k="note", l="Note", t="long", opz=True),
    ]),
    dict(k="titolare", l="Titolare / dichiarante", rubrica="persone", campi=[
        dict(k="tipo", l="Il titolare è", t="choice", scelte=["Persona", "Società"], **{"def": "Persona"}),
    ] + _anagrafica() + [
        dict(k="email", l="eMail/PEC"),
        dict(k="tel", l="Telefono", opz=True),
        dict(k="qualita", l="In qualità di", t="choice",
             scelte=["Proprietario", "Comproprietario", "Usufruttuario", "Amministratore di condominio",
                     "Legale rappresentante", "Procuratore", "Altro"], **{"def": "Proprietario"}),
        dict(k="carica", l="Carica nella società (se società)", opz=True),
    ]),
    dict(k="societa", l="Società titolare", rubrica="societa", solo_se={"titolare.tipo": "Società"}, campi=[
        dict(k="denominazione", l="Denominazione / ragione sociale"),
        dict(k="forma", l="Forma giuridica"),
        dict(k="cf", l="Codice fiscale"),
        dict(k="piva", l="Partita IVA"),
        dict(k="iscrizione", l="Registro imprese", t="choice",
             scelte=["Iscritta alla CCIAA", "Non ancora iscritta", "Non necessita di iscrizione"],
             **{"def": "Iscritta alla CCIAA"}),
        dict(k="cciaa", l="Camera di commercio di", **{"def": "Trento"}),
        dict(k="rea", l="Numero REA"),
        dict(k="rea_data", l="Data iscrizione REA", t="date"),
        dict(k="sede_stato", l="Sede: Stato", **{"def": ITALIA}),
        dict(k="sede_prov", l="Sede: Provincia", **{"def": "TN"}),
        dict(k="sede_comune", l="Sede: Comune"),
        dict(k="sede_dug", l="Sede: Toponimo", **{"def": "Via"}),
        dict(k="sede_via", l="Sede: Denominazione stradale"),
        dict(k="sede_civico", l="Sede: Numero civico"),
        dict(k="sede_cap", l="Sede: CAP"),
        dict(k="tel", l="Telefono", opz=True),
        dict(k="fax", l="Fax", opz=True),
        dict(k="pec", l="PEC"),
    ]),
    dict(k="immobile", l="Immobile", campi=[
        dict(k="comune", l="Comune"),
        dict(k="frazione", l="Frazione", opz=True),
        dict(k="prov", l="Provincia", **{"def": "TN"}),
        dict(k="cap", l="CAP"),
        dict(k="via", l="Via, viale, piazza"),
        dict(k="civico", l="Numero civico"),
        dict(k="scala", l="Scala", opz=True),
        dict(k="piano", l="Piano", opz=True),
        dict(k="interno", l="Interno", opz=True),
        dict(k="particelle", l="Dati catastali (tavolare)", t="table",
             colonne=[("pf", "P.f."), ("ped", "P.ed."), ("cc", "C.C."), ("pm", "P.m."), ("sub", "Sub.")], righe=5),
        dict(k="destinazione", l="Destinazione d'uso (residenziale, commerciale…)", **{"def": "residenziale"}),
        dict(k="zona_prg", l="Zona PRG vigente"),
        dict(k="zona_prg_adottato", l="Zona PRG adottato", opz=True),
    ]),
    dict(k="titolarita", l="Titolarità e vincoli", campi=[
        dict(k="tipo", l="Titolo del richiedente", t="choice",
             scelte=["Proprietario esclusivo", "Titolare di altro diritto reale", "Titolare di diritto contrattuale"],
             **{"def": "Proprietario esclusivo"}),
        dict(k="desc", l="Specificare (comproprietario, usufruttuario…)", opz=True),
        dict(k="altri_titolari", l="Sono presenti altri titolari", t="choice", scelte=["No", "Sì"], **{"def": "No"}),
        dict(k="parti_comuni", l="Opere su parti comuni", t="choice", scelte=[
            "Non riguardano parti comuni",
            "Condominio - senza assenso",
            "Condominio - con assenso (verbale allegato)",
            "Più proprietà non in condominio - senza assenso",
            "Più proprietà non in condominio - con assenso allegato"], **{"def": "Non riguardano parti comuni"}),
        dict(k="vincoli_lf", l="Libro fondiario", t="choice",
             scelte=["Non sussistono vincoli", "Sussistono vincoli"], **{"def": "Non sussistono vincoli"}),
    ]),
    dict(k="pdc", l="Titolo edilizio", campi=[
        dict(k="cila_tipo", l="CILA: qualificazione", t="choice", scelte=[
            "Interventi da realizzare (art. 78 bis, c. 2)", "Altro (da indicare a mano nel modulo)"],
             **{"def": "Interventi da realizzare (art. 78 bis, c. 2)"}),
        dict(k="scia_tipo", l="SCIA: qualificazione", t="choice", scelte=[
            "SCIA (art. 85 LP 15/2015)", "Variante ordinaria al permesso di costruire / SCIA",
            "Variante in corso d'opera al permesso di costruire / SCIA", "Altro (da indicare a mano nel modulo)"],
             **{"def": "SCIA (art. 85 LP 15/2015)"}),
        dict(k="tipo", l="Tipo di permesso", t="choice", scelte=[
            "Permesso di costruire", "Permesso di costruire convenzionato",
            "Variante al permesso di costruire / concessione"], **{"def": "Permesso di costruire"}),
        dict(k="variante_n", l="Variante: n. titolo originario"),
        dict(k="variante_del", l="Variante: del", t="date"),
        dict(k="contributo", l="Contributo di costruzione", t="choice", scelte=[
            "Non soggetto (nessun aumento del carico urbanistico)",
            "Soggetto - si invierà la ricevuta di pagamento",
            "Esente ai sensi dell'art. 90 LP 15/2015"], **{"def": "Soggetto - si invierà la ricevuta di pagamento"}),
        dict(k="esenzione_lettera", l="Esenzione art. 90: lettera", opz=True),
        dict(k="rateizzazione", l="Si chiede la rateizzazione del contributo", t="bool", **{"def": False}),
        dict(k="lusso", l="Classificazione", t="choice", scelte=["Non di lusso", "Di lusso (A1, A8, A9)"],
             **{"def": "Non di lusso"}),
        dict(k="impresa", l="Impresa esecutrice", t="choice", scelte=[
            "Sarà individuata prima dell'inizio lavori", "Indicata nella sezione Impresa"],
             **{"def": "Sarà individuata prima dell'inizio lavori"}),
    ]),
    dict(k="sanatoria", l="Sanatoria", campi=[
        dict(k="tipo", l="Si chiede il rilascio", t="choice", scelte=[
            "Permesso di costruire in sanatoria (art. 135, c. 1, LP 1/2008)",
            "Provvedimento di sanatoria (art. 134, c. 5, LP 1/2008)",
            "Permesso di costruire in sanatoria (art. 86 quater LP 15/2015)"],
             **{"def": "Permesso di costruire in sanatoria (art. 86 quater LP 15/2015)"}),
        dict(k="modalita", l="Opere eseguite", t="choice", scelte=["In assenza di titolo", "In difformità dal titolo"],
             **{"def": "In difformità dal titolo"}),
        dict(k="titolo", l="Titolo abilitativo (se in difformità)"),
        dict(k="titolo_n", l="Numero del titolo"),
        dict(k="titolo_data", l="Data del titolo", t="date"),
        dict(k="richiedente", l="Il richiedente è", t="choice", scelte=[
            "Responsabile dell'abuso", "Titolare del titolo edilizio", "Altro (da indicare a mano nel modulo)"],
             **{"def": "Responsabile dell'abuso"}),
    ]),
    dict(k="intervento", l="Dati tecnici", campi=[
        dict(k="costo", l="Costo dell'intervento (€)"),
        dict(k="durata", l="Durata prevista dei lavori (mesi)", opz=True),
        dict(k="sun", l="Superficie utile netta SUN (mq)", opz=True),
        dict(k="volume", l="Volume edilizio (mc)", opz=True),
        dict(k="piani", l="Numero dei piani", opz=True),
    ]),
    dict(k="diritti", l="Diritti e bollo", campi=[
        dict(k="dovuti", l="Diritti di segreteria", t="choice", scelte=["Dovuti", "Non dovuti"], **{"def": "Dovuti"}),
        dict(k="importo", l="Importo diritti (€)"),
        dict(k="pagamento", l="Pagamento", t="choice", scelte=["pagoPA / bonifico", "Conto corrente postale"],
             **{"def": "pagoPA / bonifico"}),
        dict(k="data", l="Data pagamento", t="date"),
        dict(k="iuv", l="Codice IUV / TRN", opz=True),
        dict(k="bollo", l="Imposta di bollo", t="choice",
             scelte=["Marche da bollo", "pagoPA", "Esente"], **{"def": "Marche da bollo"}),
        dict(k="marca1_n", l="Marca domanda: n. seriale"),
        dict(k="marca1_data", l="Marca domanda: data", t="date"),
        dict(k="marca2_n", l="Marca autorizzazione: n. seriale"),
        dict(k="marca2_data", l="Marca autorizzazione: data", t="date"),
    ]),
    dict(k="progettista", l="Progettista / tecnico", rubrica="tecnici", campi=[
        dict(k="presenta", l="È lui a presentare la pratica", t="bool", **{"def": True}),
        dict(k="anche_dl", l="Incaricato anche come direttore lavori", t="bool", **{"def": True}),
        dict(k="altri", l="Sono presenti altri progettisti/tecnici", t="choice", scelte=["No", "Sì"], **{"def": "No"}),
    ] + _tecnico()),
    dict(k="dl", l="Direttore lavori", rubrica="tecnici", campi=[
        dict(k="uguale", l="È lo stesso del progettista", t="bool", **{"def": True}),
        dict(k="presenta", l="È lui a presentare la pratica", t="bool", **{"def": True}),
    ] + _tecnico()),
    dict(k="impresa", l="Impresa esecutrice", rubrica="imprese", campi=[
        dict(k="denominazione", l="Denominazione"),
        dict(k="cf_piva", l="Codice fiscale / P. IVA"),
        dict(k="cciaa", l="Iscritta alla CCIAA di", **{"def": "Trento"}),
        dict(k="rea", l="Numero REA"),
        dict(k="rea_data", l="Data REA", t="date", opz=True),
        dict(k="sede_stato", l="Sede: Stato", **{"def": ITALIA}),
        dict(k="sede_prov", l="Sede: Provincia", **{"def": "TN"}),
        dict(k="sede_comune", l="Sede: Comune"),
        dict(k="sede_via", l="Sede: Via e piazza"),
        dict(k="sede_civico", l="Sede: Numero civico"),
        dict(k="sede_cap", l="Sede: CAP"),
        dict(k="tel", l="Telefono", opz=True),
        dict(k="fax", l="Fax", opz=True),
        dict(k="pec", l="PEC"),
        dict(k="lr_cognome", l="Legale rappresentante: Cognome"),
        dict(k="lr_nome", l="Legale rappresentante: Nome"),
        dict(k="lr_cf", l="Legale rappresentante: Codice fiscale"),
        dict(k="lr_nato_a", l="Legale rappresentante: Nato a"),
        dict(k="lr_nato_prov", l="Legale rappresentante: Provincia di nascita"),
        dict(k="lr_nato_stato", l="Legale rappresentante: Stato di nascita", **{"def": ITALIA}),
        dict(k="lr_nato_il", l="Legale rappresentante: Nato il", t="date"),
        dict(k="lr_cell", l="Legale rappresentante: Cellulare", opz=True),
        dict(k="lr_email", l="Legale rappresentante: eMail", opz=True),
        dict(k="cassa_sede", l="Cassa edile: sede di", opz=True),
        dict(k="cassa_impresa", l="Cassa edile: codice impresa", opz=True),
        dict(k="cassa_codice", l="Cassa edile: codice cassa", opz=True),
        dict(k="inps_sede", l="INPS: sede di", opz=True),
        dict(k="inps_matricola", l="INPS: matricola / posizione", opz=True),
        dict(k="inail_sede", l="INAIL: sede di", opz=True),
        dict(k="inail_impresa", l="INAIL: codice impresa", opz=True),
        dict(k="inail_pat", l="INAIL: posizione assicurativa territoriale", opz=True),
    ]),
    dict(k="lavori", l="Lavori e cantiere", campi=[
        dict(k="titolo_tipo", l="Titolo edilizio dei lavori", t="choice", scelte=[
            "Permesso di costruire", "SCIA", "CILA", "Comunicazione opere libere"], **{"def": "Permesso di costruire"}),
        dict(k="titolo_n", l="Numero/protocollo del titolo edilizio"),
        dict(k="titolo_data", l="Data del titolo edilizio (rilascio/presentazione)", t="date"),
        dict(k="data_inizio", l="Data di inizio lavori", t="date"),
        dict(k="esecuzione", l="Esecuzione dei lavori", t="choice",
             scelte=["Con imprese / lavoratori autonomi", "In economia"],
             **{"def": "Con imprese / lavoratori autonomi"}),
        dict(k="contributo", l="Contributo di costruzione dovuto", t="choice", scelte=["Sì", "No"], **{"def": "Sì"}),
        dict(k="sicurezza", l="D.Lgs. 81/2008", t="choice", scelte=[
            "Non ricade nel D.Lgs. 81/2008",
            "Ricade - cantiere < 200 uomini-giorno",
            "Ricade - cantiere ≥ 200 uomini-giorno"], **{"def": "Ricade - cantiere < 200 uomini-giorno"}),
        dict(k="notifica", l="Notifica preliminare", t="choice", scelte=[
            "Non soggetto a notifica", "Soggetto - notifica allegata", "Soggetto - notifica già trasmessa"],
             **{"def": "Non soggetto a notifica"}),
        dict(k="notifica_data", l="Notifica trasmessa in data", t="date", opz=True),
        dict(k="notifica_prot", l="Notifica: prot./cod. n.", opz=True),
        dict(k="data_fine", l="Data di fine lavori", t="date"),
        dict(k="fine_prot", l="Dichiarazione di ultimazione: prot. n.", opz=True),
        dict(k="fine_prot_data", l="Dichiarazione di ultimazione: del", t="date", opz=True),
        dict(k="modifica_impresa", l="Modulo Soggetti coinvolti: l'impresa indicata è", t="choice",
             scelte=["Impresa ad integrazione", "Impresa subentrante"], **{"def": "Impresa ad integrazione"}),
    ]),
]


def campi_flat():
    """Dizionario chiave_completa -> (sezione, campo)."""
    out = {}
    for s in SEZIONI:
        for c in s["campi"]:
            if c.get("t") == "table":
                for i in range(c["righe"]):
                    for ck, cl in c["colonne"]:
                        out[f"{s['k']}.{c['k']}.{i}.{ck}"] = (s, dict(k=f"{c['k']}.{i}.{ck}", l=f"{c['l']} riga {i+1} – {cl}", opz=True))
            else:
                out[f"{s['k']}.{c['k']}"] = (s, c)
    return out


CAMPI = campi_flat()
