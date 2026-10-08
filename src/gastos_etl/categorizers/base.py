from typing import Protocol

class GastoCategorizer(Protocol):
    """Puerto para el motor de categorizacion de gastos."""

    def categorize(self, comercio: str | None) -> str:
        """Dado el nombre de un comercio, retorna su categoria."""
        ...
