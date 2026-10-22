@echo off
setlocal

:: =======================================================================
:: GASTOS-ETL - Local Pipeline Execution & Cloud Sync Runner
:: =======================================================================
:: Este script orquesta el flujo completo de datos en tu máquina:
:: 1. Sincroniza (git pull) los archivos Parquet procesados en la nube.
:: 2. Carga los nuevos registros de Parquet hacia SQL Server local.
:: 3. Procesa cualquier correo nuevo pendiente directo en local.
::
:: Uso:
::   run_pipeline.bat                (sincronización y ejecución normal)
::   run_pipeline.bat --force        (re-escanear ventana completa)
::   run_pipeline.bat --since-days 7 (escanear últimos 7 días)
:: =======================================================================

:: Cambiar al directorio raíz del proyecto (padre de \scripts)
cd /d "%~dp0\.."

set EXECUTION_CONTEXT=local_pc

echo [INFO] Iniciando Gastos-ETL en entorno local (%DATE% %TIME%)...

:: Verificar si existe el entorno virtual
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: -----------------------------------------------------------------------
:: PASO 1: Descargar los archivos Parquet actualizados por GitHub Actions
:: -----------------------------------------------------------------------
echo.
echo [PASO 1/3] Descargando actualizaciones del Data Lake desde GitHub...
git pull --rebase origin main
if %ERRORLEVEL% NEQ 0 (
    echo [AVISO] git pull no se pudo completar o no hay conexion a internet. Continuando en local...
)

:: -----------------------------------------------------------------------
:: PASO 2: Sincronizar Parquet hacia SQL Server local
:: -----------------------------------------------------------------------
echo.
echo [PASO 2/3] Sincronizando Parquet Data Lake hacia SQL Server...
"%PYTHON_EXE%" scripts\sync_parquet_to_sqlserver.py
if %ERRORLEVEL% NEQ 0 (
    echo [AVISO] Fallo la sincronizacion de Parquet a SQL Server. Revisa si SQL Server esta encendido.
)

:: -----------------------------------------------------------------------
:: PASO 3: Ejecutar ingesta local incremental de correos
:: -----------------------------------------------------------------------
echo.
echo [PASO 3/3] Ejecutando ingesta incremental de correos IMAP...
"%PYTHON_EXE%" scripts\run_local.py %*
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% EQU 0 (
    echo [EXITO] Flujo de datos completado. Tus dashboards de Power BI estan listos para actualizarse!
) else (
    echo [ERROR] Ingesta finalizada con codigo de error %EXIT_CODE%.
)

exit /b %EXIT_CODE%
