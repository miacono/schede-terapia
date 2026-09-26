@echo off
rem Avvia l'editor delle schede terapia (Windows).
rem Al primo avvio prepara l'ambiente Python; poi apre il browser sull'editor.
cd /d "%~dp0"
set PORT=8000

rem Preparazione al primo avvio.
if not exist "venv\Scripts\pythonw.exe" (
    echo Preparazione dell'ambiente in corso...
    py -3 -m venv venv || python -m venv venv || goto errore
    "venv\Scripts\python.exe" -m pip install -r requirements.txt || goto errore
)

rem Avvio senza finestra console. src\editor.py sposta i dati in data\ se servono,
rem crea data\utenti.json dal template al primo avvio e apre il browser.
rem Per chiudere il programma usare il pulsante Esci nella pagina.
start "" "venv\Scripts\pythonw.exe" src\editor.py --port %PORT%
exit /b 0

:errore
echo.
echo Errore durante la preparazione dell'ambiente.
echo Servono Python 3.9 o successivo e una connessione a internet.
pause
exit /b 1
