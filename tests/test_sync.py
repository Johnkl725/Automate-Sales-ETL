from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gastos_etl.config import Settings
from gastos_etl.models import GastoBCP
from gastos_etl.repositories.parquet_repository import ParquetGastoRepository
from gastos_etl.sync import sync_parquet_to_sqlserver


@pytest.fixture
def base_settings() -> Settings:
    return Settings(
        imap_user="test@example.com",
        imap_app_password="secretpassword",
        mssql_host="127.0.0.1",
        mssql_database="GastosBCP",
        storage_sink="auto",
    )


@pytest.fixture
def sample_gastos() -> list[GastoBCP]:
    return [
        GastoBCP(
            message_id="msg_sync_001",
            monto=Decimal("45.00"),
            moneda="PEN",
            tipo="consumo_tarjeta",
            categoria="Supermercado",
            comercio="Tottus",
            fecha_consumo=datetime(2026, 10, 20, 10, 0, 0),
        ),
        GastoBCP(
            message_id="msg_sync_002",
            monto=Decimal("15.50"),
            moneda="PEN",
            tipo="yape",
            categoria="Restaurante",
            comercio="Panaderia San Antonio",
            fecha_consumo=datetime(2026, 10, 21, 15, 30, 0),
        ),
    ]


def test_sync_parquet_empty_dir(base_settings: Settings, tmp_path: Path):
    mock_repo = MagicMock()
    result = sync_parquet_to_sqlserver(base_settings, parquet_dir=tmp_path, repo=mock_repo)

    assert result.total_encontrados == 0
    assert result.insertados == 0
    mock_repo.save.assert_not_called()


def test_sync_parquet_inserts_new_records(
    base_settings: Settings, tmp_path: Path, sample_gastos: list[GastoBCP]
):
    # Generar archivos parquet de prueba usando ParquetGastoRepository
    parquet_repo = ParquetGastoRepository(base_path=str(tmp_path))
    for gasto in sample_gastos:
        parquet_repo.save(gasto)

    mock_repo = MagicMock()
    mock_repo.exists.return_value = False

    result = sync_parquet_to_sqlserver(base_settings, parquet_dir=tmp_path, repo=mock_repo)

    assert result.total_encontrados == 2
    assert result.insertados == 2
    assert result.omitidos == 0
    assert result.fallidos == 0
    assert mock_repo.save.call_count == 2


def test_sync_parquet_skips_existing_records(
    base_settings: Settings, tmp_path: Path, sample_gastos: list[GastoBCP]
):
    parquet_repo = ParquetGastoRepository(base_path=str(tmp_path))
    for gasto in sample_gastos:
        parquet_repo.save(gasto)

    mock_repo = MagicMock()
    mock_repo.exists.return_value = True

    result = sync_parquet_to_sqlserver(base_settings, parquet_dir=tmp_path, repo=mock_repo)

    assert result.total_encontrados == 2
    assert result.insertados == 0
    assert result.omitidos == 2
    mock_repo.save.assert_not_called()


def test_sync_parquet_handles_individual_errors(
    base_settings: Settings, tmp_path: Path, sample_gastos: list[GastoBCP]
):
    parquet_repo = ParquetGastoRepository(base_path=str(tmp_path))
    for gasto in sample_gastos:
        parquet_repo.save(gasto)

    mock_repo = MagicMock()
    mock_repo.exists.return_value = False
    mock_repo.save.side_effect = RuntimeError("DB write error")

    result = sync_parquet_to_sqlserver(base_settings, parquet_dir=tmp_path, repo=mock_repo)

    assert result.total_encontrados == 2
    assert result.fallidos == 2
    assert result.insertados == 0
