import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import duckdb

from gastos_etl.config import Settings
from gastos_etl.models import GastoBCP
from gastos_etl.repositories.base import GastoRepository
from gastos_etl.repositories.sqlserver_repository import SqlServerGastoRepository

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    total_encontrados: int = 0
    insertados: int = 0
    omitidos: int = 0
    fallidos: int = 0


def sync_parquet_to_sqlserver(
    settings: Settings,
    parquet_dir: Path | str = "./data/datalake",
    repo: GastoRepository | None = None,
) -> SyncResult:
    """Lee archivos Parquet del Data Lake y los sincroniza hacia SQL Server.

    Idempotente: Si el gasto ya existe en SQL Server (fact_gastos), lo omite.
    Si no existe, resuelve las dimensiones y lo inserta.
    """
    path = Path(parquet_dir)
    result = SyncResult()

    parquet_files = list(path.glob("**/*.parquet"))
    if not parquet_files:
        logger.info("No se encontraron archivos Parquet en %s para sincronizar.", path)
        return result

    if repo is None:
        repo = SqlServerGastoRepository(settings)

    glob_pattern = str(path / "**" / "*.parquet")
    logger.info("Consultando Parquet con DuckDB desde %s...", glob_pattern)

    with duckdb.connect() as con:
        rows = con.execute(
            """
            SELECT message_id, monto, moneda, tipo, categoria, comercio, fecha_consumo, procesado_en
            FROM read_parquet(?, hive_partitioning=false)
            """,
            [glob_pattern],
        ).fetchall()

    result.total_encontrados = len(rows)
    logger.info("Total de transacciones encontradas en Parquet: %d", result.total_encontrados)

    for row in rows:
        message_id = str(row[0])
        try:
            if repo.exists(message_id):
                result.omitidos += 1
                continue

            gasto = GastoBCP(
                message_id=message_id,
                monto=Decimal(str(row[1])),
                moneda=str(row[2]),
                tipo=str(row[3]),
                categoria=str(row[4]),
                comercio=str(row[5]) if row[5] else None,
                fecha_consumo=row[6],
                procesado_en=row[7],
            )
            repo.save(gasto)
            result.insertados += 1
        except Exception as exc:
            logger.error("Error al sincronizar gasto %s: %s", message_id, exc)
            result.fallidos += 1

    logger.info(
        "Sincronización finalizada: total=%d, insertados=%d, omitidos=%d, fallidos=%d",
        result.total_encontrados,
        result.insertados,
        result.omitidos,
        result.fallidos,
    )
    return result
