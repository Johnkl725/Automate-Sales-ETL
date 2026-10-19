import os
from unittest.mock import patch

import pytest

from gastos_etl.config import Settings
from gastos_etl.repositories.composite_repository import CompositeGastoRepository
from gastos_etl.repositories.factory import create_repository
from gastos_etl.repositories.parquet_repository import ParquetGastoRepository
from gastos_etl.repositories.sqlserver_repository import SqlServerGastoRepository


@pytest.fixture(autouse=True)
def mock_sqlserver_init():
    with patch.object(SqlServerGastoRepository, "__init__", return_value=None):
        yield


@pytest.fixture
def base_settings() -> Settings:
    return Settings(
        imap_user="test@example.com",
        imap_app_password="secretpassword",
        mssql_host="127.0.0.1",
        mssql_database="GastosBCP",
        storage_sink="auto",
    )


def test_factory_explicit_parquet(base_settings: Settings):
    base_settings.storage_sink = "parquet"
    repo = create_repository(base_settings)
    assert isinstance(repo, ParquetGastoRepository)


def test_factory_explicit_mssql(base_settings: Settings):
    base_settings.storage_sink = "mssql"
    repo = create_repository(base_settings)
    assert isinstance(repo, SqlServerGastoRepository)


def test_factory_explicit_both(base_settings: Settings):
    base_settings.storage_sink = "both"
    repo = create_repository(base_settings)
    assert isinstance(repo, CompositeGastoRepository)
    assert len(repo.repositories) == 2


def test_factory_auto_mode_github_actions_detects_cloud_runner(base_settings: Settings, monkeypatch):
    base_settings.storage_sink = "auto"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    with patch("gastos_etl.repositories.factory.is_sqlserver_available") as mock_health:
        repo = create_repository(base_settings)
        # En GitHub Actions no debe ni intentar conectar a SQL Server local
        mock_health.assert_not_called()
        assert isinstance(repo, ParquetGastoRepository)


def test_factory_auto_mode_local_sqlserver_available(base_settings: Settings, monkeypatch):
    base_settings.storage_sink = "auto"
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)

    with patch("gastos_etl.repositories.factory.is_sqlserver_available", return_value=True):
        repo = create_repository(base_settings)
        assert isinstance(repo, SqlServerGastoRepository)


def test_factory_auto_mode_local_sqlserver_fails_triggers_resilient_fallback(
    base_settings: Settings, monkeypatch
):
    base_settings.storage_sink = "auto"
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)

    with patch("gastos_etl.repositories.factory.is_sqlserver_available", return_value=False):
        repo = create_repository(base_settings)
        # Debe hacer fallback a Parquet para no perder transacciones
        assert isinstance(repo, ParquetGastoRepository)


def test_factory_auto_mode_local_with_r2_configured_returns_composite(
    base_settings: Settings, monkeypatch
):
    base_settings.storage_sink = "auto"
    base_settings.r2_account_id = "acc123"
    base_settings.r2_access_key_id = "key123"
    base_settings.r2_secret_access_key = "sec123"
    base_settings.r2_bucket = "my-lakehouse"

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)

    with patch("gastos_etl.repositories.factory.is_sqlserver_available", return_value=True):
        repo = create_repository(base_settings)
        assert isinstance(repo, CompositeGastoRepository)
        assert any(isinstance(r, SqlServerGastoRepository) for r in repo.repositories)
        assert any(isinstance(r, ParquetGastoRepository) for r in repo.repositories)
