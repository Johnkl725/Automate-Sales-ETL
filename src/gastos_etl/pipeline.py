import logging
from dataclasses import dataclass
from datetime import datetime

from gastos_etl.exceptions import NoParserAvailableError, ParsingError
from gastos_etl.parsers.base import EmailParser
from gastos_etl.repositories.base import GastoRepository
from gastos_etl.sources.base import EmailSource

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    procesados: int = 0
    omitidos: int = 0
    fallidos: int = 0


class GastoETLPipeline:
    """Orquestador. No conoce IMAP ni DuckDB, solo las interfaces (DIP)."""

    def __init__(self, source: EmailSource, parsers: list[EmailParser], repo: GastoRepository):
        self._source = source
        self._parsers = parsers
        self._repo = repo

    def _find_parser(self, raw) -> EmailParser:
        for parser in self._parsers:
            if parser.can_parse(raw):
                return parser
        raise NoParserAvailableError(raw.message_id)

    def run(self, since: datetime) -> RunResult:
        result = RunResult()
        for raw in self._source.fetch_unprocessed(since):
            if self._repo.exists(raw.message_id):
                result.omitidos += 1
                self._source.mark_processed(raw.message_id)
                continue

            try:
                parser = self._find_parser(raw)
                gasto = parser.parse(raw)
            except (ParsingError, NoParserAvailableError) as exc:
                # Fallo por-item, no tumba el batch completo.
                logger.error("No se pudo procesar %s: %s", raw.message_id, exc)
                result.fallidos += 1
                continue

            self._repo.save(gasto)
            self._source.mark_processed(raw.message_id)
            result.procesados += 1

        logger.info(
            "Run finalizado: procesados=%d omitidos=%d fallidos=%d",
            result.procesados,
            result.omitidos,
            result.fallidos,
        )
        return result
