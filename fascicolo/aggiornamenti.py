"""Aggiornamenti da GitHub: controlla l'ultima release di topodondio/moduli e installa il nuovo setup."""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from . import __version__

REPO = "topodondio/moduli"
PAGINA = f"https://github.com/{REPO}"
API = f"https://api.github.com/repos/{REPO}/releases/latest"


def installato():
    """True se gira il programma installato col setup, False se gira dai sorgenti Python."""
    radice = Path(__file__).resolve().parent.parent
    return bool(getattr(sys, "frozen", False)) or (radice / "installato.txt").exists()


def _numeri(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4]) or (0,)


def piu_nuova(remota, locale=__version__):
    return _numeri(remota) > _numeri(locale)


def ultima_release(timeout=8):
    """Ritorna dict(versione, note, pagina, setup, nome_setup) oppure solleva un'eccezione."""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"Fascicolo/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    setup = next((a for a in d.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
    return {"versione": (d.get("tag_name") or "").lstrip("vV"), "note": d.get("body") or "",
            "pagina": d.get("html_url") or PAGINA + "/releases",
            "setup": setup and setup.get("browser_download_url"), "nome_setup": setup and setup.get("name")}


def scarica(url, nome, avanzamento=None):
    """Scarica il setup nella cartella temporanea. avanzamento(letti, totale) facoltativo."""
    dest = Path(tempfile.gettempdir()) / (nome or "Fascicolo-Setup.exe")
    req = urllib.request.Request(url, headers={"User-Agent": f"Fascicolo/{__version__}"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        tot = int(r.headers.get("Content-Length") or 0)
        letti = 0
        while True:
            blocco = r.read(256 * 1024)
            if not blocco:
                break
            f.write(blocco)
            letti += len(blocco)
            if avanzamento:
                avanzamento(letti, tot)
    return dest


def avvia_setup(setup):
    """Prepara uno script che aspetta la chiusura VERA di Fascicolo (non un tempo fisso), poi lancia
    il setup silenzioso nella stessa cartella in cui è installato; il setup riapre il programma.
    Tutto viene annotato in %TEMP%\\fascicolo-aggiornamento.log."""
    tmp = Path(tempfile.gettempdir())
    log = tmp / "fascicolo-aggiornamento.log"
    bat = tmp / "fascicolo-aggiorna.cmd"
    pid = os.getpid()
    cartella = Path(__file__).resolve().parent.parent
    dest = f" /D={cartella}" if installato() else ""
    righe = [
        "@echo off",
        "chcp 65001 >nul",
        f'echo %date% %time% aggiornamento: attendo che Fascicolo (processo {pid}) si chiuda > "{log}"',
        "set n=0",
        ":attendi",
        f'tasklist /FI "PID eq {pid}" /NH 2>nul | find /I "python" >nul',
        "if errorlevel 1 goto installa",
        "set /a n+=1",
        "if %n% geq 90 goto installa",
        "ping -n 2 127.0.0.1 >nul",
        "goto attendi",
        ":installa",
        "ping -n 2 127.0.0.1 >nul",
        f'echo %date% %time% avvio "{setup}" /S{dest} >> "{log}"',
        f'"{setup}" /S{dest}',
        f'echo %date% %time% setup terminato, codice %errorlevel% >> "{log}"',
    ]
    bat.write_text("\r\n".join(righe) + "\r\n", encoding="utf-8")
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, close_fds=True, cwd=str(tmp),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
