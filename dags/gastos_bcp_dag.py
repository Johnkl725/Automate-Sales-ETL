"""DAG de Airflow que reusa el mismo GastoETLPipeline que scripts/run_local.py.

No requiere Google Cloud: la autenticacion es IMAP + App Password via
variables de entorno (Airflow Connections/Variables en produccion).

Se ejecuta a las 08:00 hora de Peru (America/Lima, UTC-5 fijo todo el
ano, sin horario de verano). El cron "0 8 * * *" se interpreta en la
timezone del start_date, no en UTC -- por eso start_date usa
pendulum.datetime(..., tz=LIMA_TZ) en vez de datetime.datetime plano.

Se eligio 8am (en vez de medianoche/23:59) porque el contenedor de
Airflow solo dispara si esta corriendo en ese instante exacto, y una PC
personal tipicamente esta apagada de madrugada. A las 8am, cuando el
usuario prende su equipo, el checkpoint (data/checkpoint.json) ya trae
automaticamente TODO lo pendiente desde la ultima corrida exitosa -- no
solo el dia anterior (d-1), sino tambien varios dias si la PC estuvo
apagada mas de una noche. No hace falta ninguna ventana fija de 24h.

Notificaciones por correo (a NOTIFY_EMAIL) en TODO desenlace de la tarea:
exito, fallo, timeout y cada reintento -- via SMTP de Gmail configurado
con AIRFLOW__SMTP__* (ver .env). Un timeout se reporta como fallo (Airflow
lo modela como AirflowTaskTimeout, que dispara on_failure_callback igual
que cualquier otra excepcion), pero el asunto del correo lo distingue.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowTaskTimeout
from airflow.utils.email import send_email

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

LIMA_TZ = pendulum.timezone("America/Lima")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "castilloreupoluis@gmail.com")

default_args = {
    "owner": "gastos-etl",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
}


def _notify_success(context: dict[str, Any]) -> None:
    ti = context["task_instance"]
    result = ti.xcom_pull(task_ids=ti.task_id) or {}
    logical_date = context.get("logical_date") or context.get("execution_date")

    subject = f"[gastos-etl] OK - {result.get('procesados', 0)} correo(s) nuevo(s) procesados"
    body = f"""
    <h3>Corrida diaria exitosa</h3>
    <table cellpadding="4">
      <tr><td><b>Fecha logica</b></td><td>{logical_date}</td></tr>
      <tr><td><b>Buscado desde</b></td><td>{result.get('since', '-')}</td></tr>
      <tr><td><b>Procesados</b></td><td>{result.get('procesados', 0)}</td></tr>
      <tr><td><b>Omitidos (ya existian)</b></td><td>{result.get('omitidos', 0)}</td></tr>
      <tr><td><b>Fallidos (error de parseo)</b></td><td>{result.get('fallidos', 0)}</td></tr>
    </table>
    <p><a href="{ti.log_url}">Ver logs</a></p>
    """
    send_email(to=[NOTIFY_EMAIL], subject=subject, html_content=body)


def _notify_failure(context: dict[str, Any]) -> None:
    ti = context["task_instance"]
    exception = context.get("exception")
    is_timeout = isinstance(exception, AirflowTaskTimeout)
    logical_date = context.get("logical_date") or context.get("execution_date")

    subject = f"[gastos-etl] {'TIMEOUT' if is_timeout else 'FALLO'} en la corrida diaria"
    body = f"""
    <h3>La corrida diaria {'agoto el tiempo limite' if is_timeout else 'fallo'}</h3>
    <table cellpadding="4">
      <tr><td><b>Fecha logica</b></td><td>{logical_date}</td></tr>
      <tr><td><b>Intento</b></td><td>{ti.try_number} de {ti.max_tries + 1}</td></tr>
      <tr><td><b>Error</b></td><td>{exception}</td></tr>
    </table>
    <p><a href="{ti.log_url}">Ver logs completos</a></p>
    """
    send_email(to=[NOTIFY_EMAIL], subject=subject, html_content=body)


def _notify_retry(context: dict[str, Any]) -> None:
    ti = context["task_instance"]
    exception = context.get("exception")
    logical_date = context.get("logical_date") or context.get("execution_date")

    subject = f"[gastos-etl] REINTENTO {ti.try_number}/{ti.max_tries} en la corrida diaria"
    body = f"""
    <h3>La corrida diaria fallo, Airflow va a reintentar</h3>
    <table cellpadding="4">
      <tr><td><b>Fecha logica</b></td><td>{logical_date}</td></tr>
      <tr><td><b>Intento que fallo</b></td><td>{ti.try_number} de {ti.max_tries + 1}</td></tr>
      <tr><td><b>Error</b></td><td>{exception}</td></tr>
    </table>
    <p><a href="{ti.log_url}">Ver logs</a></p>
    """
    send_email(to=[NOTIFY_EMAIL], subject=subject, html_content=body)


@dag(
    dag_id="gastos_bcp_etl",
    schedule="0 8 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz=LIMA_TZ),
    catchup=False,
    default_args=default_args,
    tags=["gastos", "bcp", "imap"],
)
def gastos_bcp_dag():
    @task(
        execution_timeout=timedelta(minutes=10),
        on_success_callback=_notify_success,
        on_failure_callback=_notify_failure,
        on_retry_callback=_notify_retry,
    )
    def run_pipeline():
        # Import diferido: solo se resuelve dentro del worker de Airflow.
        import json
        import logging
        from datetime import datetime as dt

        from gastos_etl.config import get_settings
        from gastos_etl.parsers.bcp_debito_parser import BCPDebitoParser
        from gastos_etl.parsers.bcp_pago_servicio_parser import BCPPagoServicioParser
        from gastos_etl.pipeline import GastoETLPipeline
        from gastos_etl.repositories.duckdb_repository import DuckDBGastoRepository
        from gastos_etl.sources.imap_source import ImapEmailSource

        logger = logging.getLogger("airflow.task")
        settings = get_settings()

        checkpoint_path = Path(settings.checkpoint_path)
        if checkpoint_path.exists():
            since = dt.fromisoformat(json.loads(checkpoint_path.read_text())["last_run"])
        else:
            since = dt.utcnow() - timedelta(days=1)

        source = ImapEmailSource(
            host=settings.imap_host,
            port=settings.imap_port,
            user=settings.imap_user,
            app_password=settings.imap_app_password,
            mailbox=settings.imap_mailbox,
            sender_filter=settings.bcp_sender,
            subject_hints=settings.bcp_subject_hints_list,
            processed_label=settings.imap_processed_label,
        )
        repo = DuckDBGastoRepository(settings.duckdb_path)
        pipeline = GastoETLPipeline(
            source=source,
            parsers=[BCPDebitoParser(), BCPPagoServicioParser()],
            repo=repo,
        )

        run_started_at = dt.utcnow()
        result = pipeline.run(since=since)

        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps({"last_run": run_started_at.isoformat()}))

        logger.info("procesados=%d omitidos=%d fallidos=%d", result.procesados, result.omitidos, result.fallidos)

        return {
            "procesados": result.procesados,
            "omitidos": result.omitidos,
            "fallidos": result.fallidos,
            "since": since.isoformat(),
        }

    run_pipeline()


gastos_bcp_dag()
