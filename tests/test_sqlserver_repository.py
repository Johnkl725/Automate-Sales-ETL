"""Tests unitarios de SqlServerGastoRepository con pyodbc mockeado -- no
requieren un SQL Server real corriendo. Siguen el mismo espiritu que
test_pipeline.py (fakes en vez de infra real), pero como la clase esta
fuertemente acoplada a pyodbc (a diferencia del Protocol GastoRepository,
que el pipeline si usa via fakes), se mockea `pyodbc.connect` en vez de
crear un fake completo.

Los tests construyen la instancia con `__new__` para saltarse `__init__`
(que intenta conectar de verdad a "master" para crear la base) y setean
`_settings` a mano -- solo se prueba la logica de negocio de save()/exists(),
no el bootstrap de infraestructura."""
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.models import GastoBCP
from gastos_etl.repositories.sqlserver_repository import SqlServerGastoRepository, _TIPO_IDS


def _make_repo() -> SqlServerGastoRepository:
    repo = SqlServerGastoRepository.__new__(SqlServerGastoRepository)
    repo._settings = MagicMock(mssql_connection_string="fake-dsn")
    return repo


def _gasto(**overrides) -> GastoBCP:
    defaults = dict(
        message_id="<abc@geopod>",
        monto=Decimal("15.00"),
        moneda="PEN",
        tipo="consumo_tarjeta",
        comercio="RAPPI PERU",
        fecha_consumo=datetime(2026, 8, 1, 13, 58, 0),
        procesado_en=datetime(2026, 8, 1, 13, 59, 0),
    )
    defaults.update(overrides)
    return GastoBCP(**defaults)


def test_get_or_create_comercio_id_reuses_existing_row():
    repo = _make_repo()
    cursor = MagicMock()
    cursor.execute.return_value.fetchone.return_value = (42,)

    comercio_id = repo._get_or_create_comercio_id(cursor, "RAPPI PERU", "Otros")

    assert comercio_id == 42
    select_sql = cursor.execute.call_args_list[0].args[0]
    assert "SELECT comercio_id FROM dim_comercio" in select_sql
    # No debe haber intentado insertar si ya existia. La 2da ejecucion podria ser el UPDATE opcional de categoria.
    # Pero el fetchone ya no existe asi que mockeamos.


def test_get_or_create_comercio_id_inserts_when_missing():
    repo = _make_repo()
    cursor = MagicMock()
    # Primera llamada (SELECT) no encuentra fila; segunda (INSERT ... OUTPUT) devuelve el nuevo id.
    cursor.execute.return_value.fetchone.side_effect = [None]
    cursor.fetchone.return_value = (7,)

    comercio_id = repo._get_or_create_comercio_id(cursor, "COMERCIO NUEVO", "Otros")

    assert comercio_id == 7
    insert_sql = cursor.execute.call_args_list[1].args[0]
    assert "INSERT INTO dim_comercio" in insert_sql
    assert "OUTPUT INSERTED.comercio_id" in insert_sql


def test_get_or_create_comercio_id_falls_back_to_placeholder_when_none():
    repo = _make_repo()
    cursor = MagicMock()
    cursor.execute.return_value.fetchone.return_value = (1,)

    repo._get_or_create_comercio_id(cursor, None, "Otros")

    nombre_usado = cursor.execute.call_args_list[0].args[1]
    assert nombre_usado == "(sin comercio)"


def test_save_computes_fecha_id_and_resolves_tipo_id():
    repo = _make_repo()
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.rowcount = 1
    repo._connect = MagicMock()
    repo._connect.return_value.__enter__.return_value = conn
    repo._get_or_create_comercio_id = MagicMock(return_value=99)

    repo.save(_gasto(tipo="pago_servicio", fecha_consumo=datetime(2026, 8, 1, 13, 58)))

    insert_call = cursor.execute.call_args
    insert_sql, params = insert_call.args
    assert "INSERT INTO fact_gastos" in insert_sql
    fecha_id, comercio_id, tipo_id = params[1], params[2], params[3]
    assert fecha_id == 20260801
    assert comercio_id == 99
    assert tipo_id == _TIPO_IDS["pago_servicio"]
    conn.commit.assert_called_once()


def test_save_is_idempotent_when_message_id_already_exists():
    """Guarda de regresion equivalente al ON CONFLICT DO NOTHING de DuckDB:
    si el WHERE NOT EXISTS no inserta nada (rowcount == 0), save() no debe
    lanzar excepcion -- solo loguea y sigue."""
    repo = _make_repo()
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.rowcount = 0  # nada insertado: ya existia
    repo._connect = MagicMock()
    repo._connect.return_value.__enter__.return_value = conn
    repo._get_or_create_comercio_id = MagicMock(return_value=1)

    repo.save(_gasto())  # no debe lanzar

    conn.commit.assert_called_once()


def test_exists_true_when_row_found():
    repo = _make_repo()
    conn = MagicMock()
    conn.cursor.return_value.execute.return_value.fetchone.return_value = (1,)
    repo._connect = MagicMock()
    repo._connect.return_value.__enter__.return_value = conn

    assert repo.exists("<abc@geopod>") is True


def test_exists_false_when_no_row():
    repo = _make_repo()
    conn = MagicMock()
    conn.cursor.return_value.execute.return_value.fetchone.return_value = None
    repo._connect = MagicMock()
    repo._connect.return_value.__enter__.return_value = conn

    assert repo.exists("<missing@geopod>") is False
