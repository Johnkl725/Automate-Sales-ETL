from typing import Protocol

from gastos_etl.models import GastoBCP


class GastoRepository(Protocol):
    def save(self, gasto: GastoBCP) -> None:
        ...

    def exists(self, message_id: str) -> bool:
        ...
