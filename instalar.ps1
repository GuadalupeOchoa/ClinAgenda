# ==============================================================
#  ClinAgenda - Instalador para un equipo Windows NUEVO
#  Ejecutar en PowerShell COMO ADMINISTRADOR, dentro de la carpeta del proyecto:
#     powershell -ExecutionPolicy Bypass -File .\instalar.ps1
#  Instala: Python 3.12, PostgreSQL 17, Git (con winget), dependencias
#  de Python, crea el archivo .env y la base de datos ClinAgenda.
# ==============================================================
param(
    [string]$ClaveBD = ""
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Paso($texto) { Write-Host "`n==> $texto" -ForegroundColor Cyan }

function Actualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

if (-not $ClaveBD) {
    $seg = Read-Host "Clave para el usuario 'postgres' de la base de datos" -AsSecureString
    $ClaveBD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seg))
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "No se encontro 'winget'. Instale 'App Installer' desde Microsoft Store y vuelva a ejecutar." -ForegroundColor Red
    exit 1
}
$wingetArgs = @("-e", "--silent", "--accept-package-agreements", "--accept-source-agreements")

# 1. Python
Paso "Python 3.12"
# En Windows nuevo "python" puede ser solo un acceso a Microsoft Store: se verifica la version real
$tienePython = $false
try { $tienePython = [bool]((& python --version 2>&1) -match "Python 3\.\d+") } catch {}
if (-not $tienePython) {
    winget install Python.Python.3.12 --scope machine @wingetArgs
    Actualizar-Path
} else { Write-Host "Python ya esta instalado: $(python --version)" }

# 2. PostgreSQL
Paso "PostgreSQL 17"
if (-not (Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue)) {
    winget install PostgreSQL.PostgreSQL.17 @wingetArgs --override "--mode unattended --unattendedmodeui none --superpassword `"$ClaveBD`" --serverport 5432"
    Actualizar-Path
} else { Write-Host "PostgreSQL ya esta instalado (servicio encontrado)." }

# 3. Git (necesario para trabajar con GitHub)
Paso "Git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install Git.Git @wingetArgs
    Actualizar-Path
} else { Write-Host "Git ya esta instalado." }

# 4. Entorno virtual y dependencias
Paso "Entorno virtual de Python y dependencias"
# Si la carpeta venv se copio desde otra computadora, apunta al Python de esa maquina y no sirve:
# se detecta probando si arranca, y en ese caso se borra y se crea de nuevo.
$venvSirve = $false
if (Test-Path ".\venv\Scripts\python.exe") {
    try { & .\venv\Scripts\python.exe -c "import sys" 2>$null; $venvSirve = ($LASTEXITCODE -eq 0) } catch {}
}
if (-not $venvSirve) {
    if (Test-Path ".\venv") {
        Write-Host "La carpeta venv no funciona en este equipo (se copio de otro). Se crea de nuevo..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force ".\venv"
    }
    python -m venv venv
}
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 5. Archivo .env (no se sube a GitHub)
Paso "Archivo de configuracion .env"
if (-not (Test-Path ".\.env")) {
    $secreto = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
    (Get-Content ".\.env.example") `
        -replace "^DB_PASSWORD=.*", "DB_PASSWORD=$ClaveBD" `
        -replace "^SECRET_KEY=.*", "SECRET_KEY=$secreto" |
        Set-Content ".\.env" -Encoding ascii
    Write-Host ".env creado."
} else { Write-Host ".env ya existe, no se modifica." }

# 6. Base de datos
Paso "Creando base de datos ClinAgenda"
.\venv\Scripts\python.exe init_db.py

Write-Host "`nINSTALACION TERMINADA." -ForegroundColor Green
Write-Host "Para abrir el sistema haga doble clic en 'iniciar.bat' y entre a http://localhost:5000"
