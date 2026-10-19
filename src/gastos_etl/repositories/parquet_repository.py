import logging
import os
from pathlib import Path
from typing import Any

import duckdb

from gastos_etl.models import GastoBCP

logger = logging.getLogger(__name__)


class ParquetGastoRepository:
    """Persistencia de GastoBCP en formato Parquet (Data Lake / Cloud Storage).

    Implementa el protocolo GastoRepository bajo principios SOLID:
    - SRP: Responsable exclusivo de persistir y consultar datos en formato columnar Parquet.
    - OCP/LSP: Intercambiable con SqlServerGastoRepository sin alterar el pipeline.
    - Soporta almacenamiento local particionado por Hive (year=YYYY/month=MM/)
      y Cloud Storage S3-compatible (Cloudflare R2 / AWS S3) via DuckDB httpfs.
    """

    def __init__(
        self,
        base_path: str = "./data/datalake",
        r2_account_id: str | None = None,
        r2_access_key_id: str | None = None,
        r2_secret_access_key: str | None = None,
        r2_bucket: str | None = None,
    ):
        self.r2_bucket = r2_bucket
        self.is_cloud = bool(
            r2_bucket and r2_account_id and r2_access_key_id and r2_secret_access_key
        )

        if self.is_cloud:
            self.base_path = f"s3://{r2_bucket}/gastos"
            self.r2_endpoint = f"{r2_account_id}.r2.cloudflarestorage.com"
            self.r2_access_key_id = r2_access_key_id
            self.r2_secret_access_key = r2_secret_access_key
            self.local_dir: Path | None = None
        else:
            self.local_dir = Path(base_path)
            self.local_dir.mkdir(parents=True, exist_ok=True)
            self.base_path = str(self.local_dir.resolve())
            self.r2_endpoint = None
            self.r2_access_key_id = None
            self.r2_secret_access_key = None

        self._seen_in_memory: set[str] = set()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect()
        if self.is_cloud:
            con.execute("INSTALL httpfs; LOAD httpfs;")
            con.execute(f"SET s3_endpoint = '{self.r2_endpoint}';")
            con.execute(f"SET s3_access_key_id = '{self.r2_access_key_id}';")
            con.execute(f"SET s3_secret_access_key = '{self.r2_secret_access_key}';")
            con.execute("SET s3_region = 'auto';")
            con.execute("SET s3_url_style = 'path';")
            con.execute("SET s3_use_ssl = true;")
        return con

    def _get_partition_path(self, gasto: GastoBCP) -> tuple[str, str]:
        """Retorna (directorio_particion, ruta_archivo_parquet)."""
        year = gasto.fecha_consumo.year
        month = f"{gasto.fecha_consumo.month:02d}"

        if self.is_cloud:
            part_dir = f"{self.base_path}/year={year}/month={month}"
            file_path = f"{part_dir}/gastos_{year}_{month}.parquet"
            return part_dir, file_path

        part_dir = self.local_dir / f"year={year}" / f"month={month}"
        part_dir.mkdir(parents=True, exist_ok=True)
        file_path = part_dir / "gastos.parquet"
        return str(part_dir), str(file_path)

    def exists(self, message_id: str) -> bool:
        if message_id in self._seen_in_memory:
            return True

        if not self.is_cloud:
            parquet_files = list(self.local_dir.glob("**/*.parquet"))
            if not parquet_files:
                return False
            glob_path = str(self.local_dir / "**" / "*.parquet")
        else:
            glob_path = f"{self.base_path}/**/*.parquet"

        try:
            with self._get_connection() as con:
                row = con.execute(
                    "SELECT 1 FROM read_parquet(?, hive_partitioning=false) WHERE message_id = ? LIMIT 1",
                    [glob_path, message_id],
                ).fetchone()
                if row is not None:
                    self._seen_in_memory.add(message_id)
                    return True
                return False
        except Exception as exc:
            # Si no hay archivos en el bucket o directorio, duckdb lanzará IO error
            err_msg = str(exc).lower()
            if "no files found" in err_msg or "cannot find" in err_msg or "not found" in err_msg:
                return False
            logger.warning("Error consultando Parquet en exists(%s): %s", message_id, exc)
            return False

    def save(self, gasto: GastoBCP) -> None:
        if self.exists(gasto.message_id):
            logger.info("Gasto %s ya existe en Parquet, omitiendo.", gasto.message_id)
            return

        part_dir, file_path = self._get_partition_path(gasto)
        monto_float = float(gasto.monto)

        with self._get_connection() as con:
            con.execute(
                """
                CREATE TEMP TABLE new_gasto (
                    message_id VARCHAR,
                    monto DOUBLE,
                    moneda VARCHAR,
                    tipo VARCHAR,
                    categoria VARCHAR,
                    comercio VARCHAR,
                    fecha_consumo TIMESTAMP,
                    procesado_en TIMESTAMP,
                    year INTEGER,
                    month INTEGER
                )
                """
            )
            con.execute(
                """
                INSERT INTO new_gasto VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    gasto.message_id,
                    monto_float,
                    gasto.moneda,
                    gasto.tipo,
                    gasto.categoria,
                    gasto.comercio or "Desconocido",
                    gasto.fecha_consumo,
                    gasto.procesado_en,
                    gasto.fecha_consumo.year,
                    gasto.fecha_consumo.month,
                ],
            )

            file_exists = False
            if not self.is_cloud:
                file_exists = Path(file_path).exists()
            else:
                try:
                    res = con.execute("SELECT 1 FROM read_parquet(?) LIMIT 1", [file_path]).fetchone()
                    file_exists = res is not None
                except Exception:
                    file_exists = False

            if file_exists:
                con.execute(
                    f"""
                    CREATE TEMP TABLE combined AS
                    SELECT * FROM read_parquet(?)
                    UNION ALL
                    SELECT * FROM new_gasto
                    """,
                    [file_path],
                )
                source_table = "combined"
            else:
                source_table = "new_gasto"

            if not self.is_cloud:
                temp_output = f"{file_path}.tmp"
                con.execute(f"COPY {source_table} TO '{temp_output}' (FORMAT PARQUET)")
                if os.path.exists(file_path):
                    os.replace(temp_output, file_path)
                else:
                    os.rename(temp_output, file_path)
            else:
                con.execute(f"COPY {source_table} TO '{file_path}' (FORMAT PARQUET)")

            self._seen_in_memory.add(gasto.message_id)
            logger.info("Gasto %s persistido en %s", gasto.message_id, file_path)
