import logging
from collections.abc import Sequence

from gastos_etl.models import GastoBCP
from gastos_etl.repositories.base import GastoRepository

logger = logging.getLogger(__name__)


class CompositeGastoRepository:
    """Implementa el patrón Composite para GastoRepository.

    Bajo principios SOLID:
    - OCP: Permite añadir nuevos destinos (SQL Server, Parquet, Postgres, etc.)
      sin modificar el pipeline ni los repositorios individuales.
    - LSP: Es completamente sustituible por cualquier GastoRepository.
    - Resiliencia: Si un destino falla (ej. SQL Server local caído), intenta
      persistir en los demás destinos para evitar pérdida de datos.
    """

    def __init__(self, repositories: Sequence[GastoRepository]):
        if not repositories:
            raise ValueError("CompositeGastoRepository requiere al menos un repositorio")
        self._repositories = list(repositories)

    @property
    def repositories(self) -> list[GastoRepository]:
        return self._repositories

    def exists(self, message_id: str) -> bool:
        """Retorna True si el mensaje ya existe en CUALQUIERA de los repositorios."""
        for repo in self._repositories:
            try:
                if repo.exists(message_id):
                    return True
            except Exception as exc:
                logger.warning("Error comprobando exists() en %s: %s", type(repo).__name__, exc)
        return False

    def save(self, gasto: GastoBCP) -> None:
        """Guarda en todos los repositorios configurados con tolerancia a fallos."""
        errors: list[Exception] = []
        for repo in self._repositories:
            try:
                repo.save(gasto)
            except Exception as exc:
                logger.error(
                    "Error al guardar gasto %s en %s: %s",
                    gasto.message_id,
                    type(repo).__name__,
                    exc,
                )
                errors.append(exc)

        # Si TODOS los repositorios fallaron, levantamos excepción para no perder la traza
        if len(errors) == len(self._repositories):
            raise RuntimeError(
                f"Todos los destinos del composite fallaron al guardar {gasto.message_id}: {errors}"
            )
