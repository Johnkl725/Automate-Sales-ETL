import logging
import os

from gastos_etl.config import Settings
from gastos_etl.repositories.base import GastoRepository
from gastos_etl.repositories.composite_repository import CompositeGastoRepository
from gastos_etl.repositories.parquet_repository import ParquetGastoRepository
from gastos_etl.repositories.sqlserver_repository import SqlServerGastoRepository

logger = logging.getLogger(__name__)


def is_sqlserver_available(settings: Settings, timeout_seconds: int = 2) -> bool:
    """Verifica si la instancia de SQL Server responde rápidamente."""
    try:
        import pyodbc

        conn_str = f"{settings.mssql_connection_string}Connection Timeout={timeout_seconds};"
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
    except Exception as exc:
        logger.debug("Healthcheck SQL Server no exitoso: %s", exc)
        return False


def create_parquet_repository(settings: Settings) -> ParquetGastoRepository:
    """Instancia el repositorio Parquet según la configuración local o R2."""
    if settings.is_r2_configured:
        logger.info(
            "Configurando ParquetGastoRepository con Cloudflare R2 (bucket=%s)",
            settings.r2_bucket,
        )
        return ParquetGastoRepository(
            r2_account_id=settings.r2_account_id,
            r2_access_key_id=settings.r2_access_key_id,
            r2_secret_access_key=settings.r2_secret_access_key,
            r2_bucket=settings.r2_bucket,
        )
    logger.info(
        "Configurando ParquetGastoRepository en Data Lake local (%s)",
        settings.parquet_path,
    )
    return ParquetGastoRepository(base_path=settings.parquet_path)


def create_repository(settings: Settings) -> GastoRepository:
    """Factory inteligente para instanciar el repositorio adecuado.

    Bajo principios SOLID:
    - SRP: Responsable único de resolver la estrategia de persistencia según el entorno.
    - OCP: Desacopla la lógica de creación del código del pipeline.
    - Resiliencia: Si SQL Server está caído en local, recurre a Parquet para no perder datos.
    """
    sink_mode = (settings.storage_sink or "auto").lower().strip()
    is_github_actions = (
        os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"
    )
    execution_context = os.getenv("EXECUTION_CONTEXT", "unknown")

    logger.info(
        "Resolviendo repositorio: sink_mode=%s, is_github_actions=%s, context=%s",
        sink_mode,
        is_github_actions,
        execution_context,
    )

    if sink_mode == "parquet":
        return create_parquet_repository(settings)

    if sink_mode == "mssql":
        return SqlServerGastoRepository(settings)

    if sink_mode == "both":
        sql_repo = SqlServerGastoRepository(settings)
        parquet_repo = create_parquet_repository(settings)
        return CompositeGastoRepository([sql_repo, parquet_repo])

    # --- Modo "auto" (Detección inteligente de entorno) ---
    if is_github_actions:
        logger.info(
            "Entorno detectado: GitHub Actions (Cloud Runner). "
            "SQL Server local no disponible en runner. Usando ParquetGastoRepository."
        )
        return create_parquet_repository(settings)

    # Entorno local (PC personal o contenedor Docker/Airflow)
    logger.info("Entorno detectado: Ejecución local. Verificando conectividad a SQL Server...")
    if is_sqlserver_available(settings):
        logger.info("Conexión a SQL Server exitosa.")
        sql_repo = SqlServerGastoRepository(settings)
        # Si además tiene configurado Cloudflare R2, guardar en ambos para replicar en la nube
        if settings.is_r2_configured:
            logger.info("Cloudflare R2 detectado en local. Replicando a SQL Server y Parquet R2.")
            parquet_repo = create_parquet_repository(settings)
            return CompositeGastoRepository([sql_repo, parquet_repo])
        return sql_repo

    logger.warning(
        "SQL Server no responde en %s:%s. "
        "Activando fallback automático a ParquetGastoRepository para garantizar tolerancia a fallos.",
        settings.mssql_host,
        settings.mssql_port,
    )
    return create_parquet_repository(settings)
