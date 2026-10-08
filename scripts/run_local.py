"""Ejecuta el pipeline sin Airflow, para debug rapido.

Uso:
    python scripts/run_local.py [--since-days N] [--force]

Mantiene un checkpoint en disco (CHECKPOINT_PATH) con la fecha del
ultimo run exitoso, para no reprocesar todo el historial cada vez.
Usa --force para ignorar el checkpoint y re-escanear --since-days dias
(util despues de agregar un parser nuevo, para que tambien capture el
historial de ese tipo de correo).

Escribe en SQL Server (ver .env MSSQL_*). Requiere el ODBC Driver 18 for
SQL Server instalado en Windows (instalador de Microsoft), ademas del
contenedor gastos_etl_mssql corriendo (scripts/start_airflow.ps1 lo
levanta junto con Airflow).
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.config import get_settings
from gastos_etl.parsers.bcp_debito_parser import BCPDebitoParser
from gastos_etl.parsers.bcp_pago_servicio_parser import BCPPagoServicioParser
from gastos_etl.pipeline import GastoETLPipeline
from gastos_etl.repositories.sqlserver_repository import SqlServerGastoRepository
from gastos_etl.sources.imap_source import ImapEmailSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_local")


def _load_checkpoint(path: Path, default_days: int, force: bool) -> datetime:
    if not force and path.exists():
        data = json.loads(path.read_text())
        return datetime.fromisoformat(data["last_run"])
    return datetime.utcnow() - timedelta(days=default_days)


def _save_checkpoint(path: Path, when: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_run": when.isoformat()}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-days", type=int, default=30, help="Ventana inicial si no hay checkpoint")
    parser.add_argument(
        "--force", action="store_true", help="Ignora el checkpoint y re-escanea --since-days dias"
    )
    args = parser.parse_args()

    settings = get_settings()
    checkpoint_path = Path(settings.checkpoint_path)
    since = _load_checkpoint(checkpoint_path, args.since_days, args.force)
    logger.info("Buscando correos desde %s", since.isoformat())

    from gastos_etl.sources.imap_source import SearchProfile

    source = ImapEmailSource(
        host=settings.imap_host,
        port=settings.imap_port,
        user=settings.imap_user,
        app_password=settings.imap_app_password,
        mailbox=settings.imap_mailbox,
        search_profiles=[
            SearchProfile(
                sender_filter=settings.bcp_sender,
                subject_hints=settings.bcp_subject_hints_list,
            ),
            SearchProfile(
                sender_filter="yape@bcp.com.pe",
                subject_hints=["Yape", "Yapeaste"],
            )
        ],
        processed_label=settings.imap_processed_label,
    )
    repo = SqlServerGastoRepository(settings)
    from gastos_etl.parsers.yape_parser import YapeParser
    from gastos_etl.categorizers.rule_based import RuleBasedCategorizer
    
    pipeline = GastoETLPipeline(
        source=source,
        parsers=[BCPDebitoParser(), BCPPagoServicioParser(), YapeParser()],
        repo=repo,
        categorizer=RuleBasedCategorizer(),
    )

    run_started_at = datetime.utcnow()
    result = pipeline.run(since=since)
    _save_checkpoint(checkpoint_path, run_started_at)

    logger.info(
        "Listo. procesados=%d omitidos=%d fallidos=%d",
        result.procesados,
        result.omitidos,
        result.fallidos,
    )


if __name__ == "__main__":
    main()
