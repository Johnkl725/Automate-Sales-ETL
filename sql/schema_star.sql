-- Modelo estrella de gastos-etl en SQL Server.
--
-- Documentacion de referencia -- el que realmente ejecuta esto es
-- scripts/init_sqlserver_db.py via pyodbc, statement por statement (no
-- via sqlcmd), asi que los separadores "GO" de abajo son solo para quien
-- lea/corra este archivo a mano con Azure Data Studio / SSMS / sqlcmd; el
-- script Python no los necesita ni los procesa.
--
-- Todo es idempotente (CREATE ... IF NOT EXISTS no existe en T-SQL para
-- tablas/bases, se emula con IF NOT EXISTS (SELECT ...) BEGIN ... END) asi
-- que correr esto de nuevo sobre una base ya migrada no rompe nada.

-- =============================================================
-- 1. Base de datos
-- =============================================================
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'GastosBCP')
BEGIN
    CREATE DATABASE GastosBCP;
END
GO

USE GastosBCP;
GO

-- =============================================================
-- 2. dim_tiempo -- grano dia, rango fijo pre-poblado 2024-01-01..2032-12-31
--    (~3300 filas). fecha_id es la clave inteligente yyyymmdd estandar de
--    Kimball: facil de calcular en Python sin round-trip a la base
--    (int(fecha.strftime("%Y%m%d"))).
-- =============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_tiempo')
BEGIN
    CREATE TABLE dim_tiempo (
        fecha_id        INT PRIMARY KEY,       -- yyyymmdd
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
GO

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
GO

-- =============================================================
-- 3. dim_tipo -- solo 2 valores conocidos (consumo_tarjeta / pago_servicio),
--    seed fijo. tipo_id se resuelve en Python por lookup en memoria, no
--    hace falta consultar la base por fila.
-- =============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_tipo')
BEGIN
    CREATE TABLE dim_tipo (
        tipo_id          TINYINT PRIMARY KEY,
        tipo_codigo      VARCHAR(30) NOT NULL UNIQUE,
        tipo_descripcion VARCHAR(60) NOT NULL
    );

    INSERT INTO dim_tipo (tipo_id, tipo_codigo, tipo_descripcion) VALUES
        (1, 'consumo_tarjeta', 'Consumo con tarjeta'),
        (2, 'pago_servicio', 'Pago de servicio');
END
GO

-- =============================================================
-- 4. dim_comercio -- se llena por get-or-create desde
--    SqlServerGastoRepository.save() (src/gastos_etl/repositories/sqlserver_repository.py).
--
--    NO es SCD Type 2: nombre_comercio es la unica columna y a la vez la
--    clave natural del get-or-create -- no hay un segundo atributo mutable
--    (categoria, ciudad, etc.) cuyo historial haya que versionar. Solo
--    lleva una columna de auditoria (fecha_alta). Si en el futuro se
--    agrega un atributo que SI cambie con el tiempo, ahi se justifica
--    evaluar SCD2 (vigente_desde/vigente_hasta/es_actual).
-- =============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_comercio')
BEGIN
    CREATE TABLE dim_comercio (
        comercio_id     INT IDENTITY(1,1) PRIMARY KEY,
        nombre_comercio VARCHAR(200) NOT NULL UNIQUE,
        fecha_alta      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
GO

IF NOT EXISTS (
    SELECT * FROM sys.columns
    WHERE object_id = OBJECT_ID('dim_comercio') AND name = 'fecha_alta'
)
BEGIN
    ALTER TABLE dim_comercio ADD fecha_alta DATETIME2 NOT NULL DEFAULT SYSDATETIME();
END
GO

-- =============================================================
-- 5. fact_gastos -- un hecho por email BCP procesado. Idempotente por
--    message_id (equivalente al ON CONFLICT DO NOTHING que tenia DuckDB).
-- =============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'fact_gastos')
BEGIN
    CREATE TABLE fact_gastos (
        gasto_id        BIGINT IDENTITY(1,1) PRIMARY KEY,
        message_id      VARCHAR(300) NOT NULL UNIQUE,
        fecha_id        INT NOT NULL REFERENCES dim_tiempo(fecha_id),
        comercio_id     INT NOT NULL REFERENCES dim_comercio(comercio_id),
        tipo_id         TINYINT NOT NULL REFERENCES dim_tipo(tipo_id),
        monto           DECIMAL(12, 2) NOT NULL,
        moneda          CHAR(3) NOT NULL DEFAULT 'PEN',  -- atributo degenerado, hoy 100% PEN
        fecha_consumo   DATETIME2 NOT NULL,               -- grano completo (hora incluida), no solo la fecha
        procesado_en    DATETIME2 NOT NULL
    );

    CREATE INDEX ix_fact_gastos_fecha_id ON fact_gastos(fecha_id);
    CREATE INDEX ix_fact_gastos_comercio_id ON fact_gastos(comercio_id);
END
GO
