import logging

import duckdb

from gastos_etl.models import GastoBCP

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gastos (
    message_id    VARCHAR PRIMARY KEY,
    monto         DECIMAL(12, 2) NOT NULL,
    moneda        VARCHAR NOT NULL,
    tipo          VARCHAR DEFAULT 'consumo_tarjeta',
    comercio      VARCHAR,
    fecha_consumo TIMESTAMP NOT NULL,
    procesado_en  TIMESTAMP NOT NULL
);
"""

# Migraciones idempotentes. Bases creadas antes de soportar "pago_servicio"
# tenian tarjeta_ultimos_digitos NOT NULL y no tenian "tipo"; bases mas
# viejas aun tenian tarjeta_ultimos_digitos como columna -- se elimina por
# completo: no se debe persistir ningun dato de tarjeta (DAC).
_MIGRATIONS = [
    "ALTER TABLE gastos ALTER COLUMN tarjeta_ultimos_digitos DROP NOT NULL",
    "ALTER TABLE gastos ADD COLUMN IF NOT EXISTS tipo VARCHAR DEFAULT 'consumo_tarjeta'",
    "ALTER TABLE gastos DROP COLUMN IF EXISTS tarjeta_ultimos_digitos",
]


class DuckDBGastoRepository:
    """Persistencia de GastoBCP en DuckDB, idempotente por message_id."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            for migration in _MIGRATIONS:
                try:
                    conn.execute(migration)
                except duckdb.Error:
                    pass  # ya aplicada (columna ya nullable / ya existe)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self._db_path)

    def exists(self, message_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM gastos WHERE message_id = ? LIMIT 1", [message_id]
            ).fetchone()
            return row is not None

    def save(self, gasto: GastoBCP) -> None:
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO gastos
                        (message_id, monto, moneda, tipo, comercio, fecha_consumo, procesado_en)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (message_id) DO NOTHING
                    """,
                    [
                        gasto.message_id,
                        gasto.monto,
                        gasto.moneda,
                        gasto.tipo,
                        gasto.comercio,
                        gasto.fecha_consumo,
                        gasto.procesado_en,
                    ],
                )
            except duckdb.ConstraintException:
                logger.info("Gasto %s ya existia, se omite (idempotencia)", gasto.message_id)
