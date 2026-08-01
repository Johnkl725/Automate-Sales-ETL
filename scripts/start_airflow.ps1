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
    #
    # OJO: `podman machine list` en PowerShell devuelve un ARRAY de lineas
    # (una por fila), no un string. `$array -notmatch "x"` sobre un array
    # NO es un booleano: filtra el array y devuelve las lineas que NO
    # matchean -- la fila de encabezado ("NAME ... RUNNING") nunca contiene
    # "true", asi que ese array de "no matches" nunca queda vacio y el
    # `if` de abajo se evalua SIEMPRE como true (array no vacio = truthy),
    # sin importar el estado real de la VM. Por eso hay que usar
    # `-contains` sobre una columna aislada, que si compara valores exactos
    # y devuelve un booleano real.
    #
    # Ademas, `podman machine start` sin argumento apunta al nombre por
    # defecto "podman-machine-default" -- si la VM tiene otro nombre (como
    # "podmanmachine" en esta maquina), falla con "VM does not exist" en
    # vez de arrancar la que existe. Por eso se resuelve el nombre real de
    # la primera maquina configurada y se pasa explicito.
    $runningFlags = @(podman machine list --format "{{.Running}}" 2>&1)
    $isRunning = $runningFlags -contains "true"

    if (-not $isRunning) {
        $machineName = (podman machine list --format "{{.Name}}" 2>&1 | Select-Object -First 1)
        if (-not $machineName) {
            throw "No hay ninguna maquina de Podman configurada (podman machine list vacio). Correr 'podman machine init' primero."
        }
        Write-Log "Podman machine '$machineName' no esta corriendo, iniciando..."
        podman machine start $machineName 2>&1 | ForEach-Object { Write-Log "  $_" }
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
