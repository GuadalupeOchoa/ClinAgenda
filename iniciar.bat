@echo off
REM Inicia ClinAgenda. Deje esta ventana abierta mientras se usa el sistema.
cd /d "%~dp0"
echo Iniciando ClinAgenda... abra http://localhost:5000 en el navegador.
echo Para apagar el sistema cierre esta ventana.
start "" http://localhost:5000
venv\Scripts\python.exe app.py
pause
