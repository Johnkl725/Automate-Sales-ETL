@echo off
setlocal

:: =======================================================================
:: GASTOS-ETL - Local Pipeline Execution Runner
:: =======================================================================
:: Este script ejecuta el pipeline de ingesta desde tu PC local.
:: Marca la variable EXECUTION_CONTEXT=local_pc para que el Factory
:: sepa que la ejecución proviene de tu máquina.
::
:: Uso:
::   run_pipeline.bat                (ejecución normal incremental)
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

:: Ejecutar el script Python pasando los argumentos recibidos
"%PYTHON_EXE%" scripts\run_local.py %*
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo [EXITO] Pipeline finalizado correctamente.
) else (
    echo [ERROR] Pipeline finalizado con codigo de error %EXIT_CODE%.
)

exit /b %EXIT_CODE%
