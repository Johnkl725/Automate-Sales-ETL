"""Crea el modelo estrella en SQL Server si no existe. Uso:
python scripts/init_sqlserver_db.py

Requiere que el contenedor gastos_etl_mssql este corriendo y que
MSSQL_HOST/PORT/DATABASE/USER/SA_PASSWORD en .env apunten a el
(MSSQL_HOST=localhost para correr esto desde Windows)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.config import get_settings
from gastos_etl.repositories.sqlserver_repository import SqlServerGastoRepository

if __name__ == "__main__":
    settings = get_settings()
    SqlServerGastoRepository(settings)
    print(f"Schema listo en {settings.mssql_host}:{settings.mssql_port}/{settings.mssql_database}")
