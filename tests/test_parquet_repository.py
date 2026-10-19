from datetime import datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from gastos_etl.models import GastoBCP
from gastos_etl.repositories.parquet_repository import ParquetGastoRepository


@pytest.fixture
def sample_gasto() -> GastoBCP:
    return GastoBCP(
        message_id="msg_test_parquet_001",
        monto=Decimal("150.50"),
        moneda="PEN",
        tipo="consumo_tarjeta",
        categoria="Supermercado",
        comercio="PLAZA VEA MIRAFLORES",
        fecha_consumo=datetime(2026, 10, 19, 14, 30, 0),
        procesado_en=datetime(2026, 10, 19, 14, 35, 0),
    )


def test_parquet_repository_saves_and_partitions_hive(tmp_path: Path, sample_gasto: GastoBCP):
    repo = ParquetGastoRepository(base_path=str(tmp_path))

    # Al inicio no debe existir
    assert repo.exists(sample_gasto.message_id) is False

    # Guardar gasto
    repo.save(sample_gasto)

    # Verificar que existe
    assert repo.exists(sample_gasto.message_id) is True

    # Verificar estructura Hive partition: year=2026/month=10/gastos.parquet
    expected_partition = tmp_path / "year=2026" / "month=10" / "gastos.parquet"
    assert expected_partition.exists()

    # Verificar contenido con DuckDB usando fetchall() nativo (sin requerir pandas)
    con = duckdb.connect()
    rows = con.execute("SELECT message_id, monto, categoria, comercio, year, month FROM read_parquet(?)", [str(expected_partition)]).fetchall()
    assert len(rows) == 1
    msg_id, monto, cat, com, yr, mo = rows[0]
    assert msg_id == "msg_test_parquet_001"
    assert monto == 150.50
    assert cat == "Supermercado"
    assert com == "PLAZA VEA MIRAFLORES"
    assert yr == 2026
    assert mo == 10


def test_parquet_repository_idempotency(tmp_path: Path, sample_gasto: GastoBCP):
    repo = ParquetGastoRepository(base_path=str(tmp_path))

    repo.save(sample_gasto)
    # Intentar guardar el mismo gasto una segunda vez
    repo.save(sample_gasto)

    expected_partition = tmp_path / "year=2026" / "month=10" / "gastos.parquet"
    con = duckdb.connect()
    rows = con.execute("SELECT message_id FROM read_parquet(?)", [str(expected_partition)]).fetchall()
    # No debe duplicar filas
    assert len(rows) == 1


def test_parquet_repository_appends_different_expenses(tmp_path: Path, sample_gasto: GastoBCP):
    repo = ParquetGastoRepository(base_path=str(tmp_path))
    repo.save(sample_gasto)

    segundo_gasto = GastoBCP(
        message_id="msg_test_parquet_002",
        monto=Decimal("25.00"),
        moneda="PEN",
        tipo="yape",
        categoria="Restaurante",
        comercio="Bembos",
        fecha_consumo=datetime(2026, 10, 20, 12, 0, 0),
        procesado_en=datetime(2026, 10, 20, 12, 5, 0),
    )
    repo.save(segundo_gasto)

    expected_partition = tmp_path / "year=2026" / "month=10" / "gastos.parquet"
    con = duckdb.connect()
    rows = con.execute("SELECT message_id FROM read_parquet(?)", [str(expected_partition)]).fetchall()
    assert len(rows) == 2
    msg_ids = {r[0] for r in rows}
    assert msg_ids == {"msg_test_parquet_001", "msg_test_parquet_002"}
