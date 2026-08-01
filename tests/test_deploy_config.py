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
REGISTER_TASK_SCRIPT = PROJECT_ROOT / "scripts" / "register_autostart_task.ps1"
DAG_FILE = PROJECT_ROOT / "dags" / "gastos_bcp_dag.py"

CONTAINER_NAME = "gastos_etl_airflow"
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


def test_start_script_exists_and_targets_same_container_and_image():
    content = START_SCRIPT.read_text(encoding="utf-8")

    assert f'$ContainerName = "{CONTAINER_NAME}"' in content
    assert f'$ImageTag = "{IMAGE_TAG}"' in content
    # Debe cubrir los 3 estados posibles del contenedor: no existe, parado, corriendo.
    assert "podman run -d" in content
    assert "podman start" in content
    assert "ya esta corriendo" in content


def test_start_script_does_not_match_array_against_string_for_machine_status():
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
        line for line in START_SCRIPT.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    ]
    code = "\n".join(code_lines)

    assert "-notmatch" not in code
    assert "-contains" in code


def test_start_script_starts_machine_by_resolved_name_not_default():
    """Guarda de regresion: `podman machine start` sin argumento apunta al
    nombre fijo "podman-machine-default", que no existe si la VM tiene
    otro nombre (ej. "podmanmachine") -- el script debe resolver el nombre
    real antes de arrancarla.
    """
    content = START_SCRIPT.read_text(encoding="utf-8")

    assert 'podman machine list --format "{{.Name}}"' in content
    assert "podman machine start $machineName" in content


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
