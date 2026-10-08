import logging

import pyodbc

from gastos_etl.models import GastoBCP

logger = logging.getLogger(__name__)

# Statements ejecutados uno por uno via pyodbc (sin "GO" -- eso es un
# separador de batch de sqlcmd/SSMS, pyodbc no lo entiende). Reflejan
# exactamente sql/schema_star.sql; si se toca uno hay que tocar el otro.
_CREATE_DATABASE = """
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'GastosBCP')
BEGIN
    CREATE DATABASE GastosBCP;
END
"""

_CREATE_DIM_TIEMPO = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_tiempo')
BEGIN
    CREATE TABLE dim_tiempo (
        fecha_id        INT PRIMARY KEY,
        fecha           DATE NOT NULL UNIQUE,
        anio            SMALLINT NOT NULL,
        mes             TINYINT NOT NULL,
        mes_nombre      VARCHAR(20) NOT NULL,
        trimestre       TINYINT NOT NULL,
        dia             TINYINT NOT NULL,
        dia_semana_nombre VARCHAR(20) NOT NULL,
        es_fin_semana   BIT NOT NULL,
        semana_anio     TINYINT NOT NULL
    );
END
"""

_POBLAR_DIM_TIEMPO = """
IF NOT EXISTS (SELECT * FROM dim_tiempo)
BEGIN
    ;WITH fechas AS (
        SELECT CAST('2024-01-01' AS DATE) AS fecha
        UNION ALL
        SELECT DATEADD(DAY, 1, fecha)
        FROM fechas
        WHERE fecha < '2032-12-31'
    )
    INSERT INTO dim_tiempo
        (fecha_id, fecha, anio, mes, mes_nombre, trimestre, dia, dia_semana_nombre, es_fin_semana, semana_anio)
    SELECT
        CAST(FORMAT(fecha, 'yyyyMMdd') AS INT),
        fecha,
        YEAR(fecha),
        MONTH(fecha),
        DATENAME(MONTH, fecha),
        DATEPART(QUARTER, fecha),
        DAY(fecha),
        DATENAME(WEEKDAY, fecha),
        CASE WHEN DATENAME(WEEKDAY, fecha) IN ('Saturday', 'Sunday') THEN 1 ELSE 0 END,
        DATEPART(WEEK, fecha)
    FROM fechas
    OPTION (MAXRECURSION 0);
END
"""

_CREATE_DIM_TIPO = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_tipo')
BEGIN
    CREATE TABLE dim_tipo (
        tipo_id          TINYINT PRIMARY KEY,
        tipo_codigo      VARCHAR(30) NOT NULL UNIQUE,
        tipo_descripcion VARCHAR(60) NOT NULL
    );

    INSERT INTO dim_tipo (tipo_id, tipo_codigo, tipo_descripcion) VALUES
        (1, 'consumo_tarjeta', 'Consumo con tarjeta'),
        (2, 'pago_servicio', 'Pago de servicio'),
        (3, 'yape', 'Transferencia Yape');
END
"""

_CREATE_DIM_COMERCIO = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_comercio')
BEGIN
    CREATE TABLE dim_comercio (
        comercio_id     INT IDENTITY(1,1) PRIMARY KEY,
        nombre_comercio VARCHAR(200) NOT NULL UNIQUE,
        categoria       VARCHAR(50) NOT NULL DEFAULT 'Otros',
        -- Columna de auditoria (cuando se dio de alta el comercio). NO es
        -- SCD Type 2 -- nombre_comercio es la unica columna y a la vez la
        -- clave natural del get-or-create, no hay un segundo atributo
        -- mutable cuyo historial haya que versionar. Si algun dia se
        -- agrega un atributo que SI cambie con el tiempo (categoria,
        -- ciudad...), ahi si se justifica evaluar SCD2.
        fecha_alta      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
"""

# Migracion idempotente: dim_comercio pudo haberse creado antes de que
# fecha_alta existiera (bases ya migradas). Mismo patron que
# duckdb_repository.py: IF NOT EXISTS sobre sys.columns en vez de asumir
# que la tabla siempre nace con el schema mas reciente.
_MIGRAR_FECHA_ALTA = """
IF NOT EXISTS (
    SELECT * FROM sys.columns
    WHERE object_id = OBJECT_ID('dim_comercio') AND name = 'fecha_alta'
)
BEGIN
    ALTER TABLE dim_comercio ADD fecha_alta DATETIME2 NOT NULL DEFAULT SYSDATETIME();
END
"""

_MIGRAR_CATEGORIA = """
IF NOT EXISTS (
    SELECT * FROM sys.columns
    WHERE object_id = OBJECT_ID('dim_comercio') AND name = 'categoria'
)
BEGIN
    ALTER TABLE dim_comercio ADD categoria VARCHAR(50) NOT NULL DEFAULT 'Otros';
END
"""

_CREATE_FACT_GASTOS = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'fact_gastos')
BEGIN
    CREATE TABLE fact_gastos (
        gasto_id        BIGINT IDENTITY(1,1) PRIMARY KEY,
        message_id      VARCHAR(300) NOT NULL UNIQUE,
        fecha_id        INT NOT NULL REFERENCES dim_tiempo(fecha_id),
        comercio_id     INT NOT NULL REFERENCES dim_comercio(comercio_id),
        tipo_id         TINYINT NOT NULL REFERENCES dim_tipo(tipo_id),
        monto           DECIMAL(12, 2) NOT NULL,
        moneda          CHAR(3) NOT NULL DEFAULT 'PEN',
        fecha_consumo   DATETIME2 NOT NULL,
        procesado_en    DATETIME2 NOT NULL
    );

    CREATE INDEX ix_fact_gastos_fecha_id ON fact_gastos(fecha_id);
    CREATE INDEX ix_fact_gastos_comercio_id ON fact_gastos(comercio_id);
END
"""

_SCHEMA_STATEMENTS = [
    _CREATE_DIM_TIEMPO,
    _POBLAR_DIM_TIEMPO,
    _CREATE_DIM_TIPO,
    _CREATE_DIM_COMERCIO,
    _MIGRAR_FECHA_ALTA,
    _MIGRAR_CATEGORIA,
    _CREATE_FACT_GASTOS,
]

# tipo_codigo -> tipo_id, seedeado por _CREATE_DIM_TIPO. Fijo en memoria:
# son solo 2 valores conocidos, no vale la pena una query por fila.
_TIPO_IDS = {"consumo_tarjeta": 1, "pago_servicio": 2, "yape": 3}


class SqlServerGastoRepository:
    """Persistencia de GastoBCP en el modelo estrella de SQL Server,
    idempotente por message_id (igual que DuckDBGastoRepository)."""

    def __init__(self, settings):
        self._settings = settings
        self._ensure_database()
        with self._connect() as conn:
            cursor = conn.cursor()
            for statement in _SCHEMA_STATEMENTS:
                cursor.execute(statement)
            conn.commit()

    def _ensure_database(self) -> None:
        # No se puede conectar a "GastosBCP" antes de crearla, y
        # CREATE DATABASE no corre dentro de una transaccion explicita ->
        # se conecta primero a "master" con autocommit.
        master_conn_str = self._settings.mssql_connection_string.replace(
            f"Database={self._settings.mssql_database};", "Database=master;"
        )
        conn = pyodbc.connect(master_conn_str, autocommit=True)
        try:
            conn.cursor().execute(_CREATE_DATABASE)
        finally:
            conn.close()

    def _connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self._settings.mssql_connection_string)

    def _get_or_create_comercio_id(self, cursor, nombre_comercio: str, categoria: str) -> int:
        nombre = nombre_comercio or "(sin comercio)"
        
        # En caso de que el comercio ya exista, se le podria actualizar la categoria
        # o simplemente retornarlo. Aqui solo lo retornamos.
        row = cursor.execute(
            "SELECT comercio_id FROM dim_comercio WHERE nombre_comercio = ?", nombre
        ).fetchone()
        if row:
            # Opcional: Actualizar la categoria si la anterior era 'Otros'
            cursor.execute(
                "UPDATE dim_comercio SET categoria = ? WHERE comercio_id = ? AND categoria = 'Otros' AND ? != 'Otros'",
                categoria, row[0], categoria
            )
            return row[0]

        cursor.execute(
            "INSERT INTO dim_comercio (nombre_comercio, categoria) OUTPUT INSERTED.comercio_id VALUES (?, ?)",
            nombre, categoria
        )
        return cursor.fetchone()[0]

    def exists(self, message_id: str) -> bool:
        with self._connect() as conn:
            row = conn.cursor().execute(
                "SELECT 1 FROM fact_gastos WHERE message_id = ?", message_id
            ).fetchone()
            return row is not None

    def save(self, gasto: GastoBCP) -> None:
        fecha_id = int(gasto.fecha_consumo.strftime("%Y%m%d"))
        tipo_id = _TIPO_IDS[gasto.tipo]

        with self._connect() as conn:
            cursor = conn.cursor()
            comercio_id = self._get_or_create_comercio_id(cursor, gasto.comercio, gasto.categoria)

            cursor.execute(
                """
                INSERT INTO fact_gastos
                    (message_id, fecha_id, comercio_id, tipo_id, monto, moneda, fecha_consumo, procesado_en)
                SELECT ?, ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM fact_gastos WHERE message_id = ?)
                """,
                [
                    gasto.message_id,
                    fecha_id,
                    comercio_id,
                    tipo_id,
                    gasto.monto,
                    gasto.moneda,
                    gasto.fecha_consumo,
                    gasto.procesado_en,
                    gasto.message_id,
                ],
            )
            if cursor.rowcount == 0:
                logger.info("Gasto %s ya existia, se omite (idempotencia)", gasto.message_id)
            conn.commit()
