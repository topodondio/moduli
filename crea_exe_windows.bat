@echo off
rem Crea dist\Fascicolo\Fascicolo.exe (programma autonomo, non serve Python sugli altri PC)
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name Fascicolo ^
  --add-data "moduli;moduli" --add-data "mappature;mappature" Fascicolo.pyw
echo.
echo Fatto: dist\Fascicolo\Fascicolo.exe
pause
