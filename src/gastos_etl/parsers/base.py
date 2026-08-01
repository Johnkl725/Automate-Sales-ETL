from typing import Protocol

from gastos_etl.models import GastoBCP, RawEmail


class EmailParser(Protocol):
    def can_parse(self, raw: RawEmail) -> bool:
        """True si este parser sabe interpretar el formato del correo."""
        ...

    def parse(self, raw: RawEmail) -> GastoBCP:
        """Extrae el gasto. Debe lanzar ParsingError si algo no calza."""
        ...
