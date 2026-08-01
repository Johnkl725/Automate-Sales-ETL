"""Consultas rapidas sobre data/gastos.duckdb.

Uso:
    python scripts/query_gastos.py resumen        # totales por mes
    python scripts/query_gastos.py comercios       # top comercios por gasto
    python scripts/query_gastos.py ultimos [N]      # ultimos N movimientos (default 20)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb

from gastos_etl.config import get_settings

_QUERIES = {
    "resumen": """
        SELECT strftime(fecha_consumo, '%Y-%m') AS mes,
               moneda,
               COUNT(*) AS movimientos,
               SUM(monto) AS total
        FROM gastos
        GROUP BY mes, moneda
        ORDER BY mes DESC
    """,
    "comercios": """
        SELECT comercio, moneda, COUNT(*) AS movimientos, SUM(monto) AS total
        FROM gastos
        WHERE comercio IS NOT NULL
        GROUP BY comercio, moneda
        ORDER BY total DESC
        LIMIT 20
    """,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("resumen", "comercios", "ultimos"):
        print(__doc__)
        sys.exit(1)

    comando = sys.argv[1]
    settings = get_settings()
    con = duckdb.connect(settings.duckdb_path, read_only=True)

    if comando == "ultimos":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        rows = con.execute(
            "SELECT fecha_consumo, monto, moneda, tipo, comercio "
            "FROM gastos ORDER BY fecha_consumo DESC LIMIT ?",
            [n],
        ).fetchall()
    else:
        rows = con.execute(_QUERIES[comando]).fetchall()

    cols = [d[0] for d in con.description]
    print("\t".join(cols))
    for row in rows:
        print("\t".join(str(v) for v in row))


if __name__ == "__main__":
    main()
