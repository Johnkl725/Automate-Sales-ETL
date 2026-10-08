# Helpers compartidos para scripts de arranque de contenedores Podman
# (start_airflow.ps1, start_mssql.ps1). Se usa con dot-source:
#   . "$PSScriptRoot\PodmanHelpers.ps1"
# Dot-source comparte el scope del script que llama, asi que estas
# funciones ven la $LogFile que el caller ya haya definido -- no hace
# falta pasarla como parametro en cada llamada a Write-Log.
#
# Extraido de start_airflow.ps1 despues de dos bugs reales encontrados en
# la misma semana (2026-08-01 y 2026-08-02) en la logica de "esta la VM de
# Podman corriendo": mantenerla en un solo lugar evita que un tercer
# script (ej. el de SQL Server) reintroduzca los mismos bugs por copy-paste.

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

# Corre un comando nativo (podman) SIN dejar que el $ErrorActionPreference
# global convierta su salida de stderr en una excepcion terminante.
#
# OJO (bug real del 2026-08-02): con $ErrorActionPreference = "Stop" a nivel
# global, cualquier linea que un ejecutable nativo escriba a stderr -- por
# ejemplo la advertencia cosmetica de WSL "your NxN screen size is bogus,
# expect trouble", que no indica ningun fallo real -- se envuelve en un
# NativeCommandError y aborta el script entero antes de llegar a levantar
# el contenedor. La forma correcta de detectar un fallo real de un
# ejecutable nativo es su exit code ($LASTEXITCODE), no la mera presencia
# de texto en stderr. Por eso esta funcion baja el ErrorActionPreference a
# "Continue" solo mientras corre el comando nativo, y decide exito/fallo
# explicitamente con el exit code.
function Invoke-Podman {
    param([string[]]$Arguments)
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $lines = @()
    try {
        & podman @Arguments 2>&1 | ForEach-Object {
            Write-Log "  $_"
            $lines += "$_"
        }
        return @{ ExitCode = $LASTEXITCODE; Output = $lines }
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

# Asegura que la VM de Podman este corriendo (requerido en Windows/Mac).
# Lanza una excepcion si no logra dejarla corriendo.
#
# OJO: `podman machine list` en PowerShell devuelve un ARRAY de lineas (una
# por fila), no un string. `$array -notmatch "x"` sobre un array NO es un
# booleano: filtra el array y devuelve las lineas que NO matchean -- la
# fila de encabezado ("NAME ... RUNNING") nunca contiene "true", asi que
# ese array de "no matches" nunca queda vacio y un `if` sobre el resultado
# se evalua SIEMPRE como true (array no vacio = truthy), sin importar el
# estado real de la VM. Por eso se usa `-contains` sobre una columna
# aislada, que si compara valores exactos y devuelve un booleano real.
#
# Ademas, `podman machine start` sin argumento apunta al nombre por
# defecto "podman-machine-default" -- si la VM tiene otro nombre (como
# "podmanmachine" en esta maquina), falla con "VM does not exist" en vez
# de arrancar la que existe. Por eso se resuelve el nombre real de la
# primera maquina configurada y se pasa explicito.
function Ensure-PodmanMachineRunning {
    $runningFlags = @(podman machine list --format "{{.Running}}" 2>&1)
    $isRunning = $runningFlags -contains "true"

    if ($isRunning) {
        Write-Log "Podman machine ya esta corriendo."
        return
    }

    $machineName = (podman machine list --format "{{.Name}}" 2>&1 | Select-Object -First 1)
    if (-not $machineName) {
        throw "No hay ninguna maquina de Podman configurada (podman machine list vacio). Correr 'podman machine init' primero."
    }
    Write-Log "Podman machine '$machineName' no esta corriendo, iniciando..."
    $result = Invoke-Podman @("machine", "start", $machineName)
    # `podman machine list` puede reportar un estado obsoleto justo
    # despues de un arranque previo (confirmado con WSL: la VM ya estaba
    # corriendo de verdad aunque el list decia "false") -- por eso
    # "already running" se trata como exito, no como fallo real.
    $yaCorriaDeVerdad = ($result.Output -join "`n") -match "already running"
    if ($result.ExitCode -ne 0 -and -not $yaCorriaDeVerdad) {
        throw "podman machine start '$machineName' termino con exit code $($result.ExitCode)"
    }
}

# Crea la red compartida entre contenedores si no existe (idempotente).
# Usa Invoke-Podman (no una llamada directa a `podman`) para no repetir el
# bug de $ErrorActionPreference = "Stop" + stderr de una linea nativa.
function Ensure-PodmanNetwork {
    param([string]$NetworkName)
    $checkResult = Invoke-Podman @("network", "exists", $NetworkName)
    $exists = ($checkResult.ExitCode -eq 0)
    if ($exists) {
        Write-Log "Red '$NetworkName' ya existe."
        return
    }
    Write-Log "Red '$NetworkName' no existe, creandola..."
    $result = Invoke-Podman @("network", "create", $NetworkName)
    if ($result.ExitCode -ne 0) {
        throw "podman network create '$NetworkName' termino con exit code $($result.ExitCode)"
    }
}

# Devuelve el estado del contenedor ("running", "exited", etc.) o $null si
# no existe. Via Invoke-Podman (no `2>$null` directo) por la misma razon
# que el resto: no arriesgarse a que $ErrorActionPreference = "Stop"
# convierta el exit code no-cero de "no existe" en una excepcion.
function Get-ContainerState {
    param([string]$ContainerName)
    $result = Invoke-Podman @("inspect", $ContainerName, "--format", "{{.State.Status}}")
    if ($result.ExitCode -ne 0) {
        return $null
    }
    return ($result.Output -join "").Trim()
}
