import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.exceptions import ParsingError
from gastos_etl.models import RawEmail
from gastos_etl.parsers.bcp_pago_servicio_parser import BCPPagoServicioParser

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture_email(message_id: str = "<pago123@mail.gmail.com>") -> RawEmail:
    html = (FIXTURES / "sample_email_bcp_pago_servicio.html").read_text(encoding="utf-8")
    return RawEmail(
        message_id=message_id,
        subject="ENVIO AUTOMATICO - CONSTANCIA DE PAGO DE SERVICIO - BANCA MOVIL BCP",
        sender="BCP Notificaciones <notificaciones@notificacionesbcp.com.pe>",
        received_at=datetime(2026, 7, 15, 9, 30),
        body_html=html,
    )


def test_can_parse_matches_sender_and_subject():
    parser = BCPPagoServicioParser()
    assert parser.can_parse(_load_fixture_email())


def test_can_parse_rejects_other_subjects():
    parser = BCPPagoServicioParser()
    raw = _load_fixture_email().model_copy(update={"subject": "Realizaste un consumo"})
    assert not parser.can_parse(raw)


def test_parse_extracts_empresa_y_monto_total():
    parser = BCPPagoServicioParser()
    gasto = parser.parse(_load_fixture_email())

    assert gasto.monto == Decimal("120.50")
    assert gasto.moneda == "PEN"
    assert gasto.tipo == "pago_servicio"
    assert gasto.comercio == "LUZ DEL SUR"
    assert gasto.fecha_consumo.strftime("%d/%m/%Y %H:%M") == "15/07/2026 09:30"


def test_parse_raises_parsing_error_when_monto_total_missing():
    parser = BCPPagoServicioParser()
    raw = _load_fixture_email().model_copy(
        update={"body_html": "<html><body>Empresa: LUZ DEL SUR</body></html>"}
    )
    with pytest.raises(ParsingError):
        parser.parse(raw)
