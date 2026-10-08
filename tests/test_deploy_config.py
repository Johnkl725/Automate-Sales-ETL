"""Guardas de regresion sobre la configuracion de despliegue del stack de
Airflow (docker-compose, script de arranque, tarea de autoarranque de
Windows y el schedule del DAG).

No requieren Podman/Windows instalados: son chequeos esteticos sobre los
archivos de config, pensados para detectar que alguien cambie, por ejemplo,
el nombre del contenedor en un lugar y se le olvide en otro -- exactamente
el tipo de desincronizacion silenciosa que causo que el DAG nunca se
disparara solo (ver README, seccion "Autoarranque").
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.airflow.yaml"
START_SCRIPT = PROJECT_ROOT / "scripts" / "start_airflow.ps1"
PODMAN_HELPERS_FILE = PROJECT_ROOT / "scripts" / "PodmanHelpers.ps1"
REGISTER_TASK_SCRIPT = PROJECT_ROOT / "scripts" / "register_autostart_task.ps1"
DAG_FILE = PROJECT_ROOT / "dags" / "gastos_bcp_dag.py"

CONTAINER_NAME = "gastos_etl_airflow"
MSSQL_CONTAINER_NAME = "gastos_etl_mssql"
IMAGE_TAG = "localhost/gastos-etl-airflow:local"


def test_docker_compose_defines_standalone_service_on_8080():
    config = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    service = config["services"]["airflow"]

    assert service["container_name"] == CONTAINER_NAME
    assert service["command"] == "standalone"
    assert "8080:8080" in service["ports"]
    assert service["restart"] == "unless-stopped"


def test_docker_compose_mounts_dags_src_and_data():
    config = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    volumes = config["services"]["airflow"]["volumes"]
    mounted = {v.split(":")[1] for v in volumes if ":" in v}

    assert "/opt/airflow/dags" in mounted
    assert "/opt/airflow/src" in mounted
    assert "/opt/airflow/data" in mounted


def test_start_script_dot_sources_podman_helpers():
    content = START_SCRIPT.read_text(encoding="utf-8")
    assert 'PodmanHelpers.ps1' in content
    assert PODMAN_HELPERS_FILE.exists()


def test_start_script_manages_both_containers_by_name_and_image():
    content = START_SCRIPT.read_text(encoding="utf-8")

    assert f'$AirflowContainerName = "{CONTAINER_NAME}"' in content
    assert f'$MssqlContainerName = "{MSSQL_CONTAINER_NAME}"' in content
    assert f'$ImageTag = "{IMAGE_TAG}"' in content
    # Debe cubrir los 3 estados posibles de cada contenedor: no existe, parado, corriendo.
    assert '"run", "-d"' in content
    assert '@("start", $AirflowContainerName)' in content
    assert '@("start", $MssqlContainerName)' in content
    assert "ya esta corriendo" in content


def test_start_script_publishes_mssql_on_nonstandard_host_port():
    """Guarda de regresion del bug real del 2026-08-21: publicar SQL
    Server en el puerto estandar 1433 del host choco con una instancia
    nativa de SQL Server ya instalada en Windows en ese mismo puerto --
    las conexiones desde el host caian en el SQL Server equivocado
    (login rechazado con credenciales que parecian correctas). El
    contenedor se publica en 14330 en el host; container-a-container
    (Airflow -> SQL Server) sigue usando el puerto interno real 1433, sin
    pasar por ese mapeo.
    """
    content = START_SCRIPT.read_text(encoding="utf-8")

    assert '"-p", "14330:1433"' in content
    assert '"-e", "MSSQL_PORT=1433"' in content


def test_start_script_joins_shared_network_for_airflow_to_reach_mssql():
    content = START_SCRIPT.read_text(encoding="utf-8")

    assert '$NetworkName = "gastos-etl-net"' in content
    assert "Ensure-PodmanNetwork" in content
    assert '"--network", $NetworkName' in content
    assert "MSSQL_HOST=$MssqlContainerName" in content


def test_podman_helpers_does_not_match_array_against_string_for_machine_status():
    """Guarda de regresion del bug real del 2026-08-01: `$array -notmatch
    "true"` sobre la salida multilinea de `podman machine list` no es un
    booleano (filtra el array), asi que el chequeo de "esta corriendo la
    VM?" daba siempre falso positivo de "no esta corriendo" -- la tarea de
    autoarranque se disparaba a las 8am pero nunca levantaba el
    contenedor. El fix usa `-contains` sobre una columna aislada de
    valores exactos ("true"/"false"), que si es un booleano real.
    """
    # Solo se chequean lineas de codigo ejecutable (no comentarios), porque
    # el comentario que explica el bug menciona "-notmatch" a proposito.
    code_lines = [
        line for line in PODMAN_HELPERS_FILE.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    ]
    code = "\n".join(code_lines)

    assert "-notmatch" not in code
    assert "-contains" in code


def test_podman_helpers_starts_machine_by_resolved_name_not_default():
    """Guarda de regresion: `podman machine start` sin argumento apunta al
    nombre fijo "podman-machine-default", que no existe si la VM tiene
    otro nombre (ej. "podmanmachine") -- el script debe resolver el nombre
    real antes de arrancarla.
    """
    content = PODMAN_HELPERS_FILE.read_text(encoding="utf-8")

    assert 'podman machine list --format "{{.Name}}"' in content
    assert '@("machine", "start", $machineName)' in content


def test_podman_helpers_does_not_let_stderr_warnings_abort_podman_calls():
    """Guarda de regresion del bug real del 2026-08-02: con
    $ErrorActionPreference = "Stop" a nivel global, cualquier linea que
    podman escriba a stderr -- incluida una advertencia cosmetica de WSL
    ("your NxN screen size is bogus, expect trouble") sin relacion con
    ningun fallo real -- se convertia en un NativeCommandError que
    abortaba el script antes de levantar el contenedor. El fix: las
    llamadas a podman corren con $ErrorActionPreference = "Continue" y el
    exito/fallo se decide por $LASTEXITCODE, no por la mera presencia de
    texto en stderr.
    """
    content = PODMAN_HELPERS_FILE.read_text(encoding="utf-8")

    assert "function Invoke-Podman" in content
    assert '$ErrorActionPreference = "Continue"' in content
    assert "$LASTEXITCODE" in content


def test_start_script_is_idempotent_no_hardcoded_absolute_user_path():
    content = START_SCRIPT.read_text(encoding="utf-8")

    # El script debe resolver la ruta del proyecto de forma relativa a si
    # mismo ($PSScriptRoot), no depender de una ruta absoluta hardcodeada
    # que se rompa si el repo se clona en otra maquina/carpeta.
    assert "$PSScriptRoot" in content
    assert "C:\\Users\\" not in content


def test_register_autostart_task_triggers_at_logon_and_points_to_start_script():
    content = REGISTER_TASK_SCRIPT.read_text(encoding="utf-8")

    assert "New-ScheduledTaskTrigger -AtLogOn" in content
    assert "start_airflow.ps1" in content
    assert "-Force" in content  # idempotente: re-registrar no debe duplicar la tarea


def test_dag_schedule_is_8am_lima_time():
    content = DAG_FILE.read_text(encoding="utf-8")

    schedule_match = re.search(r'schedule\s*=\s*"([^"]+)"', content)
    assert schedule_match, "No se encontro el cron schedule en el DAG"
    assert schedule_match.group(1) == "0 8 * * *"

    assert 'pendulum.timezone("America/Lima")' in content


def test_dag_has_notification_callbacks_for_success_failure_and_retry():
    content = DAG_FILE.read_text(encoding="utf-8")

    assert "on_success_callback=_notify_success" in content
    assert "on_failure_callback=_notify_failure" in content
    assert "on_retry_callback=_notify_retry" in content
    assert "execution_timeout=" in content
