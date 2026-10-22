"""Sincroniza los archivos Parquet del Data Lake hacia SQL Server.

Uso:
    python scripts/sync_parquet_to_sqlserver.py [--parquet-path ./data/datalake]

Lee todos los archivos .parquet particionados por año/mes en el Data Lake
(descargados o actualizados desde GitHub Actions) y los inserta de forma
idempotente en el modelo estrella de SQL Server (dim_tiempo, dim_comercio, fact_gastos).
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.config import get_settings
from gastos_etl.repositories.factory import is_sqlserver_available
from gastos_etl.sync import sync_parquet_to_sqlserver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sync_parquet_to_sqlserver")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza Parquet Data Lake a SQL Server")
    parser.add_argument(
        "--parquet-path",
        type=str,
        default="./data/datalake",
        help="Ruta a la carpeta del Data Lake de Parquet (default: ./data/datalake)",
    )
    args = parser.parse_args()

    settings = get_settings()

    logger.info("Comprobando conectividad con SQL Server (%s:%s)...", settings.mssql_host, settings.mssql_port)
    if not is_sqlserver_available(settings):
        logger.error(
            "No se pudo conectar a SQL Server en %s:%s. "
            "Asegúrate de que el contenedor de SQL Server esté corriendo "
            "(ej. ejecutando powershell scripts/start_airflow.ps1).",
            settings.mssql_host,
            settings.mssql_port,
        )
        sys.exit(1)

    result = sync_parquet_to_sqlserver(settings, parquet_dir=args.parquet_path)

    print("\n" + "=" * 50)
    print("RESUMEN DE SINCRONIZACIÓN (PARQUET -> SQL SERVER)")
    print("=" * 50)
    print(f"Total en Parquet:   {result.total_encontrados}")
    print(f"Nuevos Insertados:  {result.insertados}")
    print(f"Omitidos (previos): {result.omitidos}")
    print(f"Fallidos:           {result.fallidos}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
