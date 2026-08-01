import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.exceptions import ParsingError
from gastos_etl.models import RawEmail
from gastos_etl.parsers.bcp_debito_parser import BCPDebitoParser
from gastos_etl.sources.imap_source import ImapEmailSource

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture_email(message_id: str = "<abc123@mail.gmail.com>") -> RawEmail:
    html = (FIXTURES / "sample_email_bcp.html").read_text(encoding="utf-8")
    return RawEmail(
        message_id=message_id,
        subject="Realizaste un consumo",
        sender="BCP <notificaciones@notificacionesbcp.com.pe>",
        received_at=datetime(2026, 7, 29, 20, 15),
        body_html=html,
    )


def test_can_parse_matches_sender_and_subject():
    parser = BCPDebitoParser()
    assert parser.can_parse(_load_fixture_email())


def test_can_parse_rejects_other_senders():
    parser = BCPDebitoParser()
    raw = _load_fixture_email()
    raw = raw.model_copy(update={"sender": "otro@banco.com"})
    assert not parser.can_parse(raw)


def test_parse_extracts_expected_fields():
    parser = BCPDebitoParser()
    gasto = parser.parse(_load_fixture_email())

    assert gasto.monto == Decimal("25.00")
    assert gasto.moneda == "PEN"
    assert gasto.comercio == "COMERCIO SAC"
    assert gasto.fecha_consumo.strftime("%d/%m/%Y %H:%M") == "30/07/2026 18:59"


def test_parse_raises_parsing_error_when_amount_missing():
    parser = BCPDebitoParser()
    raw = _load_fixture_email().model_copy(
        update={"body_html": "<html><body>Sin monto aqui</body></html>"}
    )
    with pytest.raises(ParsingError):
        parser.parse(raw)


def test_parse_real_bcp_eml():
    """Regression contra un .eml real exportado de Gmail (quoted-printable,
    subject con encoded-word partido en varias lineas, tarjeta sin espacios)."""
    raw_bytes = (FIXTURES / "sample_email_bcp_real.eml").read_bytes()
    raw = ImapEmailSource._to_raw_email(raw_bytes)

    parser = BCPDebitoParser()
    assert parser.can_parse(raw)

    gasto = parser.parse(raw)
    assert gasto.monto == Decimal("25.00")
    assert gasto.moneda == "PEN"
    assert gasto.comercio == "PLIN-WALTER GAUDENCIO S"
    assert gasto.fecha_consumo.strftime("%d/%m/%Y %H:%M") == "30/07/2026 18:59"
    assert not hasattr(gasto, "tarjeta_ultimos_digitos")
