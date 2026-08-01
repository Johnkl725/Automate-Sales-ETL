# Levanta (o reanuda) el stack de Airflow standalone de gastos-etl.
#
# Pensado para correr sin supervision, disparado por el Task Scheduler de
# Windows al iniciar sesion (ver scripts/register_autostart_task.ps1). Es
# idempotente: se puede correr a mano las veces que se quiera.
#   - Si el contenedor no existe            -> lo crea con `podman run`.
#   - Si existe pero esta detenido          -> `podman start`.
#   - Si ya esta corriendo                  -> no hace nada.
#
# Toda la salida se registra en logs\start_airflow.log (con timestamp) para
# poder diagnosticar arranques fallidos sin tener que revisar el Task
# Scheduler manualmente.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "start_airflow.log"
$ContainerName = "gastos_etl_airflow"
$ImageTag = "localhost/gastos-etl-airflow:local"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

try {
    Write-Log "=== start_airflow.ps1 iniciado ==="

    # 1. Asegurar que la VM de Podman este arriba (requerido en Windows/Mac).
    $machineStatus = (podman machine list --format "{{.Name}}\t{{.Running}}" 2>&1)
    if ($machineStatus -notmatch "true") {
        Write-Log "Podman machine no esta corriendo, iniciando..."
        podman machine start 2>&1 | ForEach-Object { Write-Log "  $_" }
    } else {
        Write-Log "Podman machine ya esta corriendo."
    }

    # 2. Ver el estado actual del contenedor.
    $containerState = (podman inspect $ContainerName --format "{{.State.Status}}" 2>$null)

    if (-not $containerState) {
        Write-Log "Contenedor '$ContainerName' no existe, creandolo..."
        Push-Location $ProjectRoot
        try {
            $env:MSYS_NO_PATHCONV = "1"
            podman run -d `
                --name $ContainerName `
                --restart unless-stopped `
                --env-file .env `
                -e AIRFLOW__CORE__LOAD_EXAMPLES=false `
                -e AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags `
                -e PYTHONPATH=/opt/airflow/src `
                -e DUCKDB_PATH=/opt/airflow/data/gastos.duckdb `
                -e CHECKPOINT_PATH=/opt/airflow/data/checkpoint.json `
                -e TZ=America/Lima `
                -v "${ProjectRoot}\dags:/opt/airflow/dags:Z" `
                -v "${ProjectRoot}\src:/opt/airflow/src:Z" `
                -v "${ProjectRoot}\data:/opt/airflow/data:Z" `
                -v airflow_home:/opt/airflow `
                -p 8080:8080 `
                $ImageTag standalone 2>&1 | ForEach-Object { Write-Log "  $_" }
        } finally {
            Pop-Location
        }
    } elseif ($containerState -eq "running") {
        Write-Log "Contenedor '$ContainerName' ya esta corriendo, nada que hacer."
    } else {
        Write-Log "Contenedor '$ContainerName' existe pero esta '$containerState', arrancandolo..."
        podman start $ContainerName 2>&1 | ForEach-Object { Write-Log "  $_" }
    }

    Write-Log "=== start_airflow.ps1 finalizado OK ==="
} catch {
    Write-Log "ERROR: $_"
    exit 1
}
