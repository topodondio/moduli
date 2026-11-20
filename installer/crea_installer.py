"""Crea dist/Modulo-Setup-<versione>.exe, l'installer per Windows.

Funziona da Linux, macOS o Windows: scarica un Python per Windows già pronto
(python-build-standalone), ci mette dentro PySide6 e PyMuPDF per Windows (da PyPI) e il
programma, poi crea l'installer con NSIS (makensis: `apt install nsis`, `brew install nsis`
oppure https://nsis.sourceforge.io su Windows).

    python installer/crea_installer.py
"""
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
BUILD = RADICE / "build"
APP = BUILD / "Fascicolo"
CACHE = BUILD / "cache"
PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20241206/"
              "cpython-3.12.8%2B20241206-x86_64-pc-windows-msvc-install_only.tar.gz")
PACCHETTI = ["PySide6-Essentials==6.12.0", "shiboken6==6.12.0", "pymupdf==2.1"]
QT_TENGO = r"Qt(Core|Gui|Widgets|Network|PrintSupport|OpenGL|DBus)\b"


def versione():
    t = (RADICE / "fascicolo" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"(.+?)"', t).group(1)


def scarica(url, dest):
    if dest.exists():
        return dest
    print("scarico", url)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.rename(dest)
    return dest


def python_windows():
    arch = scarica(PYTHON_URL, CACHE / "python-win.tar.gz")
    with tarfile.open(arch) as t:
        t.extractall(APP)  # crea APP/python
    py = APP / "python"
    # alleggerisco: niente file di debug, test, tkinter, idle
    for f in py.rglob("*.pdb"):
        f.unlink()
    for d in ["include", "libs", "tcl", "Scripts", "Lib/test", "Lib/idlelib", "Lib/tkinter", "Lib/turtledemo",
              "Lib/ensurepip", "Lib/lib2to3", "Lib/pydoc_data"]:
        shutil.rmtree(py / d, ignore_errors=True)
    for pat in ("_tkinter*", "tcl*", "tk*"):
        for f in (py / "DLLs").glob(pat):
            f.unlink()
    return py


def librerie(py):
    ruote = CACHE / "wheels"
    ruote.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sys.executable, "-m", "pip", "download", "--quiet", "--only-binary=:all:",
                           "--platform", "win_amd64", "--python-version", "3.12", "--implementation", "cp",
                           "--no-deps", "-d", str(ruote), *PACCHETTI])
    sp = py / "Lib" / "site-packages"
    for w in sorted(ruote.glob("*.whl")):
        with zipfile.ZipFile(w) as z:
            z.extractall(sp)
    # PySide6: tolgo strumenti e moduli Qt che il programma non usa
    ps = sp / "PySide6"
    for f in ps.glob("*.exe"):
        f.unlink()
    for d in ["include", "typesystems", "glue", "examples", "scripts", "metatypes", "qml", "resources"]:
        shutil.rmtree(ps / d, ignore_errors=True)
    tr = ps / "translations"
    if tr.exists():
        for f in tr.iterdir():
            if not re.match(r"qt(base)?_it\.qm$", f.name):
                f.unlink()
    for f in list(ps.glob("Qt*.pyd")) + list(ps.glob("Qt*.pyi")):
        if f.suffix == ".pyi" or not re.match(QT_TENGO, f.name):
            f.unlink()
    for f in ps.glob("Qt6*.dll"):
        nome = f.name[3:]  # "Qt6Widgets.dll" -> "Widgets.dll"
        if not re.match(r"(Core|Gui|Widgets|Network|PrintSupport|OpenGL|DBus|Svg)\.dll$", nome):
            f.unlink()
    for f in ps.glob("pyside6qml*.dll"):
        f.unlink()
    for d in ["designer", "qmltooling", "sqldrivers", "vectorimageformats"]:
        shutil.rmtree(ps / "plugins" / d, ignore_errors=True)
    # plugin che dipendono da librerie Qt tolte: li tolgo anche loro
    presenti = {f.name.lower() for f in ps.glob("*.dll")}
    for f in (ps / "plugins").rglob("*.dll"):
        servono = {m.decode().lower() for m in re.findall(rb"Qt6\w+\.dll", f.read_bytes(), re.I)}
        if servono - presenti:
            f.unlink()


def programma():
    for d in ["fascicolo", "moduli", "mappature", "assets"]:
        shutil.copytree(RADICE / d, APP / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in ["Fascicolo.pyw", "README.md", "requirements.txt"]:
        shutil.copy2(RADICE / f, APP / f)
    (APP / "installato.txt").write_text("Modulo installato con il programma di installazione.\n", encoding="utf-8")


def main():
    v = versione()
    shutil.rmtree(APP, ignore_errors=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    (RADICE / "dist").mkdir(exist_ok=True)
    py = python_windows()
    librerie(py)
    programma()
    makensis = shutil.which("makensis") or r"C:\Program Files (x86)\NSIS\makensis.exe"
    subprocess.check_call([makensis, "-V2", f"-DVERSIONE={v}", f"-DORIGINE={APP}",
                           f"-DUSCITA={RADICE / 'dist'}", f"-DICONA={RADICE / 'assets' / 'fascicolo.ico'}",
                           str(RADICE / "installer" / "Fascicolo.nsi")])
    out = RADICE / "dist" / f"Modulo-Setup-{v}.exe"
    print(f"\nPronto: {out}  ({out.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
