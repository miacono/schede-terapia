@echo off
rem Avvia l'editor delle schede terapia (Windows).
rem Al primo avvio prepara l'ambiente Python; poi apre il browser sull'editor.
cd /d "%~dp0"
set PORT=8000
set URL=http://127.0.0.1:%PORT%

rem 1) L'editor e' gia' acceso? Apri solo il browser.
curl.exe -s -f -o nul %URL%/api/utenti && (
    start "" %URL%
    exit /b 0
)

rem 2) La porta e' occupata da un altro programma? Avvisa.
netstat -ano -p tcp | findstr /R /C:":%PORT% *0\.0\.0\.0:0" >nul && (
    echo La porta %PORT% e' usata da un altro programma.
    echo Chiudilo, oppure cambia il valore di PORT in questo file.
    pause
    exit /b 1
)

rem 3) Preparazione al primo avvio.
if not exist venv\Scripts\python.exe (
    echo Preparazione dell'ambiente in corso...
    py -3 -m venv venv || goto errore
    venv\Scripts\python.exe -m pip install -r requirements.txt || goto errore
)
if not exist utenti.json copy utenti.json.template utenti.json >nul

rem 4) Avvio senza finestra console. Il browser lo apre editor.py.
rem    Per chiudere il programma usare il pulsante Esci nella pagina.
start "" venv\Scripts\pythonw.exe editor.py --port %PORT%
exit /b 0

:errore
echo.
echo Errore durante la preparazione dell'ambiente.
echo Servono Python 3.9 o successivo e una connessione a internet.
pause
exit /b 1
