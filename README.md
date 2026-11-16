# Fascicolo – pratiche edilizie e modulistica

Programma desktop (Windows e Mac) per gestire le pratiche edilizie: scheda dati unica per
pratica, compilazione automatica dei moduli PDF provinciali, archivio per pratica e consegna
secondo le regole di ogni comune. Non usa il browser né internet.

## Avvio
- **Windows**: installa Python 3.11+ da python.org (spunta "Add to PATH"), poi doppio clic su
  `avvia_windows.bat`. La prima volta installa da solo le librerie (PySide6, PyMuPDF).
- **Mac**: doppio clic su `avvia_mac.command` (la prima volta: tasto destro › Apri).
- **Exe autonomo per lo studio**: `crea_exe_windows.bat` crea `dist\Fascicolo\Fascicolo.exe`,
  da copiare sugli altri PC senza installare Python.

## Come si usa
Il programma ha tre schede.

1. **Dati pratica**: i dati comuni (titolare, immobile, tecnici, impresa…). Si salvano da soli.
   Progettisti, imprese e titolari ricorrenti si salvano in **rubrica**.
2. **Moduli**: premi **Compila un modulo**, scegli il modulo e si apre nel tuo programma PDF già
   compilato con i dati della pratica. Completalo e salvalo: Fascicolo legge i dati nuovi e li
   usa per gli altri moduli. I moduli della pratica sono in un elenco numerato che puoi
   riordinare come vuoi con le frecce ▲▼. Ogni modulo ha la sua riga con la casella che indica
   dove è salvato, il pulsante **Scegli dove salvarlo…** (anche sul server) e **Apri**.
   Se nel frattempo hai cambiato i dati della pratica, all'apertura il modulo viene aggiornato
   (le parti scritte a mano nel PDF restano). Con **Carica un modulo già compilato…** porti
   nella pratica un PDF fatto fuori dal programma, anche i vecchi moduli dinamici del portale.
3. **Allegati**: qualsiasi file da tenere con la pratica (carte d'identità, patenti, codici
   fiscali, visure, foto…). Si aggiungono col pulsante o trascinandoli; per ognuno puoi indicare
   il tipo di documento e una nota. Vanno nella cartella `Allegati` della pratica; "Togli dalla
   pratica" li sposta in `Allegati/_tolti` senza cancellarli.

**Pratiche** (barra a sinistra): sotto l'elenco ci sono **Modifica** (nome e comune; rinomina
anche la cartella), **Duplica** (nuova pratica con gli stessi dati, a scelta anche allegati e
moduli) ed **Elimina** (la pratica va in `<archivio>/_cestino`, da cui si recupera; i moduli
salvati in altre cartelle non vengono toccati). Le stesse voci sono nel menu del tasto destro.

**Comuni** (barra a sinistra): elenco dei comuni con la PEC, usata nell'informativa privacy.

## Moduli
Tutti i 17 moduli provinciali e i due modelli ISTAT (RE e NRE) sono già collegati ai dati della
pratica. Sono collegati: dichiarante (persona o società), immobile e dati catastali, titolarità,
progettista/tecnico, direttore lavori, impresa, diritti e bollo, sicurezza, date e riferimenti
del titolo, informativa privacy (nome e PEC del comune).

Restano volutamente **da compilare a mano** nel PDF:
- le scelte tecniche (tipologie di opere, asseverazioni, impianti, barriere, antincendio…);
- altri titolari, procuratore e altri tecnici oltre al progettista e al direttore lavori;
- gli allegati e le tabelle di altri atti di assenso;
- nei moduli ISTAT: zona PRG, superfici, alloggi e dati energetici.

Un modulo nuovo si aggiunge con **Aggiungi modello PDF…** e si collega da **Insegna modulo…**:
il programma propone in automatico (in verde) i campi già noti dagli altri moduli.
Le mappature fatte dall'utente si salvano in `<archivio>/_impostazioni/mappature`.

## Dove stanno i dati
- Archivio pratiche: di default `Documenti/Pratiche` (cambiabile da *Cartella archivio…*).
- Ogni pratica ha il suo `pratica.json` leggibile; comuni e rubrica in `_impostazioni/`.
