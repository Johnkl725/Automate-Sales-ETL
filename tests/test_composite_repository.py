from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from gastos_etl.models import GastoBCP
from gastos_etl.repositories.composite_repository import CompositeGastoRepository


@pytest.fixture
def sample_gasto() -> GastoBCP:
    return GastoBCP(
        message_id="msg_composite_001",
        monto=Decimal("80.00"),
        moneda="PEN",
        tipo="consumo_tarjeta",
        categoria="Servicios",
        comercio="Sedapal",
        fecha_consumo=datetime(2026, 10, 19, 10, 0, 0),
    )


def test_composite_repository_save_calls_all_children(sample_gasto: GastoBCP):
    mock_repo1 = MagicMock()
    mock_repo2 = MagicMock()

    composite = CompositeGastoRepository([mock_repo1, mock_repo2])
    composite.save(sample_gasto)

    mock_repo1.save.assert_called_once_with(sample_gasto)
    mock_repo2.save.assert_called_once_with(sample_gasto)


def test_composite_repository_exists_returns_true_if_any_child_has_it():
    mock_repo1 = MagicMock()
    mock_repo1.exists.return_value = False

    mock_repo2 = MagicMock()
    mock_repo2.exists.return_value = True

    composite = CompositeGastoRepository([mock_repo1, mock_repo2])
    assert composite.exists("msg_composite_001") is True


def test_composite_repository_exists_returns_false_if_no_child_has_it():
    mock_repo1 = MagicMock()
    mock_repo1.exists.return_value = False

    mock_repo2 = MagicMock()
    mock_repo2.exists.return_value = False

    composite = CompositeGastoRepository([mock_repo1, mock_repo2])
    assert composite.exists("msg_composite_999") is False


def test_composite_repository_fault_tolerance_one_fails_other_succeeds(sample_gasto: GastoBCP):
    mock_repo_failing = MagicMock()
    mock_repo_failing.save.side_effect = ConnectionError("SQL Server connection timeout")

    mock_repo_working = MagicMock()

    composite = CompositeGastoRepository([mock_repo_failing, mock_repo_working])
    # No debe propagar la excepción si al menos uno logró guardar (resiliencia)
    composite.save(sample_gasto)

    mock_repo_working.save.assert_called_once_with(sample_gasto)


def test_composite_repository_raises_if_all_fail(sample_gasto: GastoBCP):
    mock_repo1 = MagicMock()
    mock_repo1.save.side_effect = ConnectionError("Down 1")

    mock_repo2 = MagicMock()
    mock_repo2.save.side_effect = ConnectionError("Down 2")

    composite = CompositeGastoRepository([mock_repo1, mock_repo2])
    with pytest.raises(RuntimeError):
        composite.save(sample_gasto)
