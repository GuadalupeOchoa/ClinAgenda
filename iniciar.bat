@echo off
REM Inicia ClinAgenda. Deje esta ventana abierta mientras se usa el sistema.
cd /d "%~dp0"

REM Verifica que el entorno de Python sea de ESTE equipo y tenga las librerias instaladas
venv\Scripts\python.exe -c "import flask, psycopg2, dotenv" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  El sistema todavia no esta instalado en este equipo,
    echo  o la carpeta "venv" se copio desde otra computadora y no sirve aqui.
    echo.
    echo  Solucion: abra PowerShell como Administrador en esta carpeta y ejecute:
    echo      powershell -ExecutionPolicy Bypass -File .\instalar.ps1
    echo.
    pause
    exit /b 1
)

echo Iniciando ClinAgenda... abra http://localhost:5000 en el navegador.
echo Para apagar el sistema cierre esta ventana.
start "" http://localhost:5000
venv\Scripts\python.exe app.py
pause
