from datetime import datetime
from typing import Protocol

from gastos_etl.models import RawEmail


class EmailSource(Protocol):
    def fetch_unprocessed(self, since: datetime) -> list[RawEmail]:
        """Devuelve correos no marcados como procesados desde `since`."""
        ...

    def mark_processed(self, message_id: str) -> None:
        """Marca un correo como procesado (label/flag) para no releerlo."""
        ...
