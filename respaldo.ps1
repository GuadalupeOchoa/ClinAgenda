# ==============================================================
#  ClinAgenda - Respaldo de la base de datos
#  Uso:      powershell -ExecutionPolicy Bypass -File .\respaldo.ps1
#  Restaurar: pg_restore -U postgres -d ClinAgenda --clean respaldos\<archivo>.dump
#  Recomendado: programarlo a diario con el Programador de tareas de Windows
#  y copiar la carpeta "respaldos" a un disco externo o a la nube.
# ==============================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Leer configuracion del .env
$cfg = @{}
Get-Content ".\.env" | Where-Object { $_ -match "^\s*([A-Z_]+)=(.*)$" } |
    ForEach-Object { $cfg[$Matches[1]] = $Matches[2].Trim() }

$pgDump = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\pg_dump.exe" -ErrorAction SilentlyContinue |
          Sort-Object FullName -Descending | Select-Object -First 1
if (-not $pgDump) { Write-Host "No se encontro pg_dump.exe" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force ".\respaldos" | Out-Null
$archivo = ".\respaldos\ClinAgenda_$(Get-Date -Format 'yyyyMMdd_HHmm').dump"

$env:PGPASSWORD = $cfg["DB_PASSWORD"]
& $pgDump.FullName -h $cfg["DB_HOST"] -p $cfg["DB_PORT"] -U $cfg["DB_USER"] -F c -f $archivo $cfg["DB_NAME"]
Remove-Item Env:\PGPASSWORD

# Conservar solo los ultimos 30 respaldos
Get-ChildItem ".\respaldos\*.dump" | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 | Remove-Item

Write-Host "Respaldo creado: $archivo" -ForegroundColor Green
