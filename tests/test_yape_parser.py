import pytest
from datetime import datetime, timezone
from pathlib import Path

from gastos_etl.models import RawEmail
from gastos_etl.parsers.yape_parser import YapeParser
from gastos_etl.exceptions import ParsingError

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_email_yape.html"

@pytest.fixture
def yape_parser():
    return YapeParser()

@pytest.fixture
def raw_yape_email():
    html_content = FIXTURE_PATH.read_text(encoding="utf-8")
    return RawEmail(
        message_id="msg-yape-123",
        subject="¡Yapeaste exitosamente!",
        sender="yape@bcp.com.pe",
        received_at=datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc),
        body_html=html_content,
        body_text=None,
    )

def test_can_parse_yape(yape_parser, raw_yape_email):
    assert yape_parser.can_parse(raw_yape_email)

def test_parse_yape_monto_comercio(yape_parser, raw_yape_email):
    gasto = yape_parser.parse(raw_yape_email)
    
    assert float(gasto.monto) == 45.50
    assert gasto.tipo == "yape"
    assert gasto.comercio == "MARIA DEL CARMEN SILVA"
    # Basic date validation (could be naive or aware depending on strptime)
    assert gasto.fecha_consumo.year == 2026
    assert gasto.fecha_consumo.month == 10
    assert gasto.fecha_consumo.day == 8
