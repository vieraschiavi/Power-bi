@echo off
REM ===========================================================================
REM  ADIUM PHARMA — Armado de los tres tableros, de punta a punta
REM
REM  Doble clic y listo. Hace todo lo que se puede automatizar:
REM    1. verifica Python
REM    2. instala las dependencias
REM    3. genera el dataset, el modelo estrella y los modelos de ML
REM    4. valida que las cuatro capas del modelo estén sincronizadas
REM    5. regenera los tres .pbit con la ruta de datos de ESTA maquina
REM    6. abre el primero en Power BI Desktop
REM
REM  El unico paso manual que queda es Archivo -> Guardar como -> .pbix, y no es
REM  por pereza: el binario .pbix solo lo puede escribir Power BI Desktop.
REM ===========================================================================

setlocal enabledelayedexpansion
REM Este .bat vive en powerbi/ pero trabaja sobre la raiz del repo: se movio
REM aca para que la raiz sea inequivocamente MV DAX Lab, el producto. Quien
REM haga doble clic en la raiz tiene que abrir el producto, no este pipeline.
cd /d "%~dp0.."

echo.
echo  ============================================================
echo   ADIUM PHARMA - Excelencia Comercial Corporativo
echo   Armado de los tableros VAR, Ofertas y Logistica
echo  ============================================================
echo.

REM --- 1. Python -------------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo  [X] No se encontro Python en el PATH.
    echo      Instalalo desde https://www.python.org/downloads/
    echo      y marca "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [1/6] Python %PYVER% encontrado

REM --- 2. Dependencias -------------------------------------------------------
echo  [2/6] Instalando dependencias...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo  [X] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

REM --- 3. Pipeline -----------------------------------------------------------
echo  [3/6] Generando dataset, modelo estrella y modelos de ML...
echo        (toma alrededor de un minuto y medio)
python src\run_all.py
if errorlevel 1 (
    echo  [X] Fallo el pipeline. El detalle esta arriba.
    pause
    exit /b 1
)

REM --- 4. Validacion del contrato -------------------------------------------
REM  Corta aca si el modelo no esta sincronizado. Un tablero que carga con el
REM  contrato roto no falla: muestra otro numero, que es mucho peor.
echo  [4/6] Validando que las cuatro capas del modelo coincidan...
python powerbi\validar_contrato.py
if errorlevel 1 (
    echo  [X] El modelo no esta sincronizado. No se generan los archivos.
    pause
    exit /b 1
)

REM --- 5. Archivos de Power BI ----------------------------------------------
echo  [5/6] Generando los .pbit con la ruta de datos de esta maquina...
python powerbi\generar_pbit.py --ruta "%~dp0data\star"
if errorlevel 1 (
    echo  [X] Fallo la generacion de los archivos.
    pause
    exit /b 1
)

REM --- 6. Abrir --------------------------------------------------------------
echo.
echo  ============================================================
echo   LISTO
echo  ============================================================
echo.
echo   Carpeta de datos (por si Power BI la pide):
echo   %~dp0data\star
echo.
echo   En Power BI Desktop:
echo     1. Confirma el parametro RutaDatos (ya viene con la ruta correcta)
echo     2. Cargar
echo     3. Ver -^> Temas -^> Buscar temas -^> powerbi\tema_adium.json
echo     4. Archivo -^> Guardar como -^> Adium_VAR.pbix
echo.
echo   Los otros dos estan en powerbi\archivos\
echo.

choice /c SN /n /m "  Abrir el tablero VAR ahora? (S/N) "
if errorlevel 2 goto fin
start "" "%~dp0powerbi\archivos\Adium_VAR.pbit"

:fin
echo.
pause
endlocal
