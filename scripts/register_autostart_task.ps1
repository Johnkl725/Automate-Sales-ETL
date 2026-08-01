# Registra una tarea en el Task Scheduler de Windows que ejecuta
# start_airflow.ps1 cada vez que el usuario inicia sesion. Con esto, el
# stack de Airflow (webserver + scheduler) queda corriendo en background
# apenas prendes la PC, sin necesidad de acordarte de levantarlo a mano.
#
# Se puede correr las veces que se quiera: si la tarea ya existe, la
# reemplaza (Register-ScheduledTask -Force) en vez de duplicarla.
#
# Requiere PowerShell con permisos de administrador la PRIMERA vez que se
# registra la tarea (Register-ScheduledTask lo exige). Correrlo asi:
#   powershell -ExecutionPolicy Bypass -File scripts\register_autostart_task.ps1

$ErrorActionPreference = "Stop"

$TaskName = "gastos-etl-airflow-autostart"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $ProjectRoot "scripts\start_airflow.ps1"

if (-not (Test-Path $StartScript)) {
    throw "No se encontro $StartScript"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""

# Se dispara al iniciar sesion del usuario actual. Se agrega un retraso de
# 30s para dar tiempo a que Windows termine de levantar red/servicios antes
# de que Podman intente arrancar la VM.
$trigger = New-ScheduledTaskTrigger -AtLogOn
$trigger.Delay = "PT30S"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Levanta el stack de Airflow (gastos-etl) al iniciar sesion." `
    -Force | Out-Null

Write-Host "Tarea '$TaskName' registrada. Se disparara 30s despues de cada inicio de sesion."
Write-Host "Verificar con: Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
