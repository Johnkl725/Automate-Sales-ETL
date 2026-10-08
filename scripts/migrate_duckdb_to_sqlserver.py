"""Migracion one-time: copia todas las filas de data/gastos.duckdb (el
historico congelado) al modelo estrella en SQL Server. Reusa
SqlServerGastoRepository.save() -- el mismo codigo que usara el DAG en
adelante -- para no duplicar la logica de get-or-create de dimensiones.

Uso: python scripts/migrate_duckdb_to_sqlserver.py

Idempotente: si se corre dos veces, la segunda vez no duplica nada (el
INSERT ... WHERE NOT EXISTS de SqlServerGastoRepository.save() ya lo
garantiza)."""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.config import get_settings
from gastos_etl.models import GastoBCP
from gastos_etl.repositories.sqlserver_repository import SqlServerGastoRepository


def main() -> None:
    settings = get_settings()

    conn = duckdb.connect(settings.duckdb_path, read_only=True)
    rows = conn.execute(
        "SELECT message_id, monto, moneda, tipo, comercio, fecha_consumo, procesado_en FROM gastos"
    ).fetchall()
    conn.close()

    print(f"Leidas {len(rows)} filas de {settings.duckdb_path}")

    repo = SqlServerGastoRepository(settings)

    migrados = 0
    for message_id, monto, moneda, tipo, comercio, fecha_consumo, procesado_en in rows:
        ya_existia = repo.exists(message_id)
        gasto = GastoBCP(
            message_id=message_id,
            monto=monto,
            moneda=moneda,
            tipo=tipo,
            comercio=comercio,
            fecha_consumo=fecha_consumo,
            procesado_en=procesado_en,
        )
        repo.save(gasto)
        if not ya_existia:
            migrados += 1

    with repo._connect() as sql_conn:
        (total,) = sql_conn.cursor().execute("SELECT COUNT(*) FROM fact_gastos").fetchone()

    print(f"Migrados {migrados} gastos nuevos. fact_gastos ahora tiene {total} filas totales.")
    if total < len(rows):
        print(
            f"ADVERTENCIA: fact_gastos ({total}) tiene menos filas que el DuckDB origen ({len(rows)})."
        )


if __name__ == "__main__":
    main()
