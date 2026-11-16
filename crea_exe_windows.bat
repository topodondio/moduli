@echo off
rem Crea il programma (dist\Fascicolo\Fascicolo.exe) e, se c'è Inno Setup 6, l'installer in dist\.
rem Di solito non serve: l'installer lo crea GitHub da solo quando si pubblica una nuova versione.
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name Fascicolo --icon assets\fascicolo.ico ^
  --add-data "moduli;moduli" --add-data "mappature;mappature" --add-data "assets;assets" Fascicolo.pyw
for /f "tokens=2 delims==" %%v in ('findstr __version__ fascicolo\__init__.py') do set VER=%%~v
set VER=%VER:"=%
set VER=%VER: =%
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=%VER% installer\Fascicolo.iss
)
pause
