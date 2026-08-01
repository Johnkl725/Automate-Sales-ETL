import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gastos_etl.models import GastoBCP, RawEmail
from gastos_etl.pipeline import GastoETLPipeline


class FakeSource:
    def __init__(self, emails: list[RawEmail]):
        self._emails = emails
        self.marked: list[str] = []

    def fetch_unprocessed(self, since):
        return self._emails

    def mark_processed(self, message_id: str) -> None:
        self.marked.append(message_id)


class FakeParser:
    def can_parse(self, raw: RawEmail) -> bool:
        return True

    def parse(self, raw: RawEmail) -> GastoBCP:
        return GastoBCP(
            message_id=raw.message_id,
            monto=Decimal("10.00"),
            fecha_consumo=raw.received_at,
        )


class FakeRepo:
    def __init__(self):
        self.saved: list[GastoBCP] = []

    def exists(self, message_id: str) -> bool:
        return any(g.message_id == message_id for g in self.saved)

    def save(self, gasto: GastoBCP) -> None:
        self.saved.append(gasto)


def _raw(message_id: str) -> RawEmail:
    return RawEmail(
        message_id=message_id,
        subject="Realizaste un consumo",
        sender="notificacionesbcp.com.pe",
        received_at=datetime(2026, 7, 29, 12, 0),
        body_text="irrelevante para el fake parser",
    )


def test_pipeline_saves_new_emails_and_marks_processed():
    source = FakeSource([_raw("m1"), _raw("m2")])
    repo = FakeRepo()
    pipeline = GastoETLPipeline(source=source, parsers=[FakeParser()], repo=repo)

    result = pipeline.run(since=datetime(2026, 1, 1))

    assert result.procesados == 2
    assert result.omitidos == 0
    assert result.fallidos == 0
    assert {g.message_id for g in repo.saved} == {"m1", "m2"}
    assert set(source.marked) == {"m1", "m2"}


def test_pipeline_skips_already_existing_message_id():
    repo = FakeRepo()
    repo.save(
        GastoBCP(message_id="m1", monto=Decimal("5.00"), fecha_consumo=datetime(2026, 1, 1))
    )
    source = FakeSource([_raw("m1")])
    pipeline = GastoETLPipeline(source=source, parsers=[FakeParser()], repo=repo)

    result = pipeline.run(since=datetime(2026, 1, 1))

    assert result.procesados == 0
    assert result.omitidos == 1
    assert len(repo.saved) == 1
