# Modulo – pratiche edilizie e modulistica

Programma desktop (Windows e Mac) per gestire le pratiche edilizie: scheda dati unica per
pratica, compilazione automatica dei moduli PDF provinciali, archivio per pratica e consegna
secondo le regole di ogni comune. Non usa il browser né internet.

## Installazione
Scarica **Modulo-Setup-x.y.z.exe** dall'ultima release
(https://github.com/topodondio/moduli/releases/latest) e aprilo: si installa per l'utente,
senza permessi di amministratore, con collegamento nel menu Start (e, a scelta, sul desktop).
Windows può mostrare l'avviso "PC protetto da Windows" perché il programma non è firmato:
*Ulteriori informazioni › Esegui comunque*.

**Aggiornamenti**: menu **? › Controlla aggiornamenti…**. Se c'è una versione nuova, Modulo
la scarica, si chiude, si aggiorna e si riapre; le pratiche non vengono toccate. All'avvio il
programma controlla da solo e lo segnala in basso nella barra di stato.

**Più postazioni**: al primo avvio Modulo chiede dov'è l'archivio. Scegliendo su tutti i
computer la **stessa cartella condivisa sul server**, l'elenco delle pratiche è unico per tutto
lo studio, con dati, moduli e allegati di ogni pratica. L'elenco e la pratica aperta si
aggiornano da soli ogni pochi secondi; se due persone lavorano sulla stessa pratica le
modifiche vengono unite (se cambiano lo stesso dato vale l'ultima) e in alto compare chi altro
la sta usando. Comuni, rubrica e moduli insegnati stanno nell'archivio e valgono per tutti.

**Dai sorgenti** (per sviluppo): Python 3.11+, `pip install -r requirements.txt`, poi
`python -m fascicolo` (o doppio clic su `avvia_windows.bat` / `avvia_mac.command`).
Serve Windows 10 (1903 o successivo) o Windows 11.

**Creare l'installer**: `python installer/crea_installer.py` crea
`dist/Modulo-Setup-x.y.z.exe`. Funziona anche da Linux o Mac: scarica un Python per Windows
già pronto, ci mette PySide6, PyMuPDF e il programma e crea l'installer con NSIS
(`apt install nsis`; su Windows https://nsis.sourceforge.io).

**Pubblicare una nuova versione** (così le postazioni la trovano in *? › Controlla
aggiornamenti*): cambia `__version__` in `fascicolo/__init__.py`, crea l'installer e su GitHub
fai *Releases › Draft a new release* con il tag `vX.Y.Z`, allegando il file `.exe`.
Se GitHub Actions è attivo sull'account, la release la crea da solo al push su `main`
(`.github/workflows/release.yml`).

## Come si usa
Il programma ha tre schede.

1. **Dati pratica**: i dati comuni (titolare, immobile, tecnici, impresa…). Si salvano da soli.
   Progettisti, imprese e titolari ricorrenti si salvano in **rubrica**.
2. **Moduli**: premi **Compila un modulo**, scegli il modulo e si apre nel tuo programma PDF già
   compilato con i dati della pratica. Completalo e salvalo: Modulo legge i dati nuovi e li
   usa per gli altri moduli. I moduli della pratica sono in un elenco numerato che puoi
   riordinare come vuoi tenendo premuto un modulo (sul numero o sul nome) e trascinandolo.
   Quando compili un modulo nuovo Modulo chiede dove salvarlo (cartella e nome, anche sul
   server): da lì in poi il riferimento è quel file. Ogni riga mostra dove è salvato, con
   **Apri** e **Togli**; col tasto destro puoi aprire la cartella o spostarlo.
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
Quando premi **Compila un modulo** i moduli sono divisi in tre gruppi principali:
- **Moduli 2026**: la modulistica provinciale nuova (PDF compilabili).
- **Moduli 2022**: i moduli dinamici del portale (Adobe LiveCycle/XFA), cartella `moduli/2022`.
  Modulo scrive i dati della pratica dentro il modulo e li rilegge quando lo salvi; vanno
  aperti e completati con **Adobe Acrobat o Acrobat Reader** (gli altri lettori PDF mostrano
  solo "Please wait…"). Se ricompili un modulo 2022 già fatto, i campi compilati a mano restano.
- **ISTAT / ISPAT**: i modelli statistici RE e NRE.

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
