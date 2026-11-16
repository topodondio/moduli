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
1. **Comuni e consegne** (barra a sinistra): inserisci i comuni con PEC/email, modalità di
   consegna e numero di copie cartacee.
2. **Nuova pratica**: crea la cartella `ANNO-NNN Nome` con Moduli, Elaborati, Allegati,
   Consegne, Ricevute.
3. **Dati pratica**: compila quello che sai; si salva da solo. Progettisti, imprese e
   titolari ricorrenti si salvano in **rubrica** e si richiamano con un clic.
4. **Moduli › Compila**: il programma chiede solo i dati che mancano a quel modulo, li salva
   nella pratica e genera il PDF in `Moduli/`. Il modulo successivo li trova già.
   Se correggi un dato, **Ricompila tutti** aggiorna i moduli già fatti (le versioni vecchie
   vanno in `Moduli/_precedenti`).
5. **Consegna**: scegli i file, il programma li copia in `Consegne/<data>` con il testo del
   messaggio e, per PEC/PEO, apre una nuova mail già indirizzata. Firma digitalmente i PDF
   prima di allegarli.

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
