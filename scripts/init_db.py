"""Crea el schema de DuckDB si no existe. Uso: python scripts/init_db.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.config import get_settings
from gastos_etl.repositories.duckdb_repository import DuckDBGastoRepository

if __name__ == "__main__":
    settings = get_settings()
    Path(settings.duckdb_path).parent.mkdir(parents=True, exist_ok=True)
    DuckDBGastoRepository(settings.duckdb_path)
    print(f"Schema listo en {settings.duckdb_path}")
