@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul || (echo Python non trovato: installalo da python.org & pause & exit /b)
python -c "import PySide6, pymupdf" 2>nul || python -m pip install -r requirements.txt
start "" pythonw Fascicolo.pyw
