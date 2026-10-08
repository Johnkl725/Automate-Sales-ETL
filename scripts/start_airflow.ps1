# Levanta (o reanuda) el stack completo de gastos-etl: SQL Server (destino
# del modelo estrella) + Airflow standalone, en la red Podman compartida
# "gastos-etl-net" para que Airflow pueda resolver "gastos_etl_mssql" por
# nombre de contenedor.
#
# Pensado para correr sin supervision, disparado por el Task Scheduler de
# Windows al iniciar sesion (ver scripts/register_autostart_task.ps1). Es
# idempotente: se puede correr a mano las veces que se quiera.
#   - Si un contenedor no existe            -> lo crea con `podman run`.
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
$NetworkName = "gastos-etl-net"
$MssqlContainerName = "gastos_etl_mssql"
$AirflowContainerName = "gastos_etl_airflow"
$ImageTag = "localhost/gastos-etl-airflow:local"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# Write-Log, Invoke-Podman, Ensure-PodmanMachineRunning, Ensure-PodmanNetwork
# y Get-ContainerState viven en PodmanHelpers.ps1 (compartido con futuros
# scripts de arranque de contenedores) -- dot-source comparte este scope,
# asi que ven $LogFile sin necesidad de pasarla como parametro.
. "$PSScriptRoot\PodmanHelpers.ps1"

function Read-EnvValue {
    # Lee una variable puntual de .env sin exportarla al proceso -- solo
    # para armar la password de SA que pasa a "podman run -e".
    param([string]$Key)
    $envFile = Join-Path $ProjectRoot ".env"
    $line = Get-Content $envFile | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return $line.Substring($Key.Length + 1)
}

try {
    Write-Log "=== start_airflow.ps1 iniciado ==="

    Ensure-PodmanMachineRunning
    Ensure-PodmanNetwork -NetworkName $NetworkName

    # 1. SQL Server (modelo estrella) -- tiene que estar arriba antes que
    # Airflow, porque el pipeline escribe ahi en cada corrida.
    $mssqlState = Get-ContainerState -ContainerName $MssqlContainerName
    if (-not $mssqlState) {
        Write-Log "Contenedor '$MssqlContainerName' no existe, creandolo..."
        $saPassword = Read-EnvValue -Key "MSSQL_SA_PASSWORD"
        if (-not $saPassword) {
            throw "MSSQL_SA_PASSWORD no esta definida en .env"
        }
        $mssqlRunArgs = @(
            "run", "-d",
            "--name", $MssqlContainerName,
            "--restart", "unless-stopped",
            "--network", $NetworkName,
            "-e", "ACCEPT_EULA=Y",
            "-e", "MSSQL_PID=Express",
            "-e", "MSSQL_SA_PASSWORD=$saPassword",
            "-e", "TZ=America/Lima",
            "-v", "mssql_data:/var/opt/mssql",
            # 14330 en el host, no 1433: esta maquina ya tiene un SQL
            # Server nativo (sqlservr.exe) ocupando el 1433 (ver .env,
            # MSSQL_PORT). Dentro de la red de Podman el contenedor sigue
            # escuchando en su puerto real 1433, sin cambios.
            "-p", "14330:1433",
            "mcr.microsoft.com/mssql/server:2022-latest"
        )
        $result = Invoke-Podman $mssqlRunArgs
        if ($result.ExitCode -ne 0) {
            throw "podman run (mssql) termino con exit code $($result.ExitCode)"
        }
    } elseif ($mssqlState -eq "running") {
        Write-Log "Contenedor '$MssqlContainerName' ya esta corriendo, nada que hacer."
    } else {
        Write-Log "Contenedor '$MssqlContainerName' existe pero esta '$mssqlState', arrancandolo..."
        $result = Invoke-Podman @("start", $MssqlContainerName)
        if ($result.ExitCode -ne 0) {
            throw "podman start (mssql) termino con exit code $($result.ExitCode)"
        }
    }

    # 2. Airflow.
    $airflowState = Get-ContainerState -ContainerName $AirflowContainerName

    if (-not $airflowState) {
        Write-Log "Contenedor '$AirflowContainerName' no existe, creandolo..."
        Push-Location $ProjectRoot
        try {
            $env:MSYS_NO_PATHCONV = "1"
            $runArgs = @(
                "run", "-d",
                "--name", $AirflowContainerName,
                "--restart", "unless-stopped",
                "--network", $NetworkName,
                "--env-file", ".env",
                "-e", "AIRFLOW__CORE__LOAD_EXAMPLES=false",
                "-e", "AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags",
                "-e", "PYTHONPATH=/opt/airflow/src",
                "-e", "CHECKPOINT_PATH=/opt/airflow/data/checkpoint.json",
                # localhost del .env es para scripts corridos en Windows;
                # dentro del contenedor, SQL Server se resuelve por el
                # nombre del contenedor en la red compartida.
                "-e", "MSSQL_HOST=$MssqlContainerName",
                # Puerto INTERNO real del contenedor (1433), no el 14330
                # publicado en el host -- container-a-container no pasa
                # por el port mapping. .env trae 14330 como default (para
                # scripts corridos en Windows), hay que pisarlo aqui.
                "-e", "MSSQL_PORT=1433",
                "-e", "MSSQL_ODBC_DRIVER=ODBC Driver 18 for SQL Server",
                "-e", "TZ=America/Lima",
                "-v", "${ProjectRoot}\dags:/opt/airflow/dags:Z",
                "-v", "${ProjectRoot}\src:/opt/airflow/src:Z",
                "-v", "${ProjectRoot}\data:/opt/airflow/data:Z",
                "-v", "airflow_home:/opt/airflow",
                "-p", "8080:8080",
                $ImageTag, "standalone"
            )
            $result = Invoke-Podman $runArgs
            if ($result.ExitCode -ne 0) {
                throw "podman run (airflow) termino con exit code $($result.ExitCode)"
            }
        } finally {
            Pop-Location
        }
    } elseif ($airflowState -eq "running") {
        Write-Log "Contenedor '$AirflowContainerName' ya esta corriendo, nada que hacer."
    } else {
        Write-Log "Contenedor '$AirflowContainerName' existe pero esta '$airflowState', arrancandolo..."
        $result = Invoke-Podman @("start", $AirflowContainerName)
        if ($result.ExitCode -ne 0) {
            throw "podman start (airflow) termino con exit code $($result.ExitCode)"
        }
    }

    Write-Log "=== start_airflow.ps1 finalizado OK ==="
} catch {
    Write-Log "ERROR: $_"
    exit 1
}
