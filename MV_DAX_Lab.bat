@echo off
REM ===========================================================================
REM  MV DAX Lab - arranque sin instalar nada
REM
REM  Doble clic y listo. Esta es la via para las empresas que bloquean la
REM  ejecucion de .exe: no instala nada en el sistema, no toca el registro y
REM  no pide permisos de administrador. Todo vive en una carpeta del usuario
REM  que se puede borrar a mano.
REM
REM  La otra via es el instalador .exe (menu Inicio, icono en el escritorio,
REM  desinstalador). Las dos abren exactamente el mismo programa.
REM ===========================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"
title MV DAX Lab

set "APP=daxlingo"
if not exist "%APP%\app\app.py" set "APP=."
if not exist "%APP%\app\app.py" (
    echo.
    echo  [X] No encuentro el programa junto a este archivo.
    echo      Este .bat tiene que quedar en la misma carpeta que "app".
    echo.
    pause
    exit /b 1
)

REM --- 1. Python -------------------------------------------------------------
REM  El lanzador "py" es el que instala python.org y el que sobrevive a que
REM  el PATH este roto, que en una PC corporativa es lo normal.
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY ( python --version >nul 2>&1 && set "PY=python" )
if not defined PY ( python3 --version >nul 2>&1 && set "PY=python3" )

if not defined PY (
    echo.
    echo  ============================================================
    echo   Falta Python 3
    echo  ============================================================
    echo.
    echo   MV DAX Lab necesita Python 3.10 o superior.
    echo.
    echo   1. Descargalo de  https://www.python.org/downloads/
    echo   2. En el instalador, marca "Add Python to PATH"
    echo   3. Volve a hacer doble clic en este archivo
    echo.
    echo   No hace falta ser administrador: alcanza con la instalacion
    echo   "solo para mi usuario".
    echo.
    pause
    exit /b 1
)

REM --- 2. Entorno propio -----------------------------------------------------
REM  En %LOCALAPPDATA% y no junto al programa: la carpeta puede estar en una
REM  unidad de red de solo lectura, y ahi un venv no se puede crear.
set "BASE=%LOCALAPPDATA%\MV DAX Lab"
set "VENV=%BASE%\venv"
set "MARCA=%VENV%\.dependencias-listas"

if not exist "%VENV%\Scripts\python.exe" (
    echo.
    echo   Preparando el entorno por unica vez. Tarda un par de minutos.
    echo.
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo  [X] No se pudo crear el entorno en "%VENV%".
        pause
        exit /b 1
    )
)

set "PYW=%VENV%\Scripts\python.exe"

if not exist "%MARCA%" (
    echo   Instalando dependencias...
    "%PYW%" -m pip install --upgrade pip --quiet
    "%PYW%" -m pip install -r "%APP%\requirements.txt" --quiet
    if errorlevel 1 (
        echo.
        echo  [X] Fallo la instalacion de dependencias.
        echo      Suele ser el proxy de la empresa. Proba:
        echo      "%PYW%" -m pip install -r "%APP%\requirements.txt"
        echo.
        pause
        exit /b 1
    )
    echo listo> "%MARCA%"
)

REM --- 3. Tema y datos -------------------------------------------------------
REM  El tema va por variable de entorno y no por .streamlit\config.toml:
REM  Streamlit lee ese archivo del directorio actual, y desde otra carpeta
REM  quedaria el tema claro por defecto sobre el fondo oscuro de la app, con
REM  el texto ilegible.
set "STREAMLIT_THEME_BASE=dark"
set "STREAMLIT_THEME_PRIMARY_COLOR=#f2b441"
set "STREAMLIT_THEME_BACKGROUND_COLOR=#081527"
set "STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR=#0c2137"
set "STREAMLIT_THEME_TEXT_COLOR=#eaf1fb"
set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"
set "STREAMLIT_CLIENT_TOOLBAR_MODE=minimal"
set "STREAMLIT_SERVER_HEADLESS=false"
set "STREAMLIT_SERVER_PORT=8747"
set "MVDAXLAB_DATOS=%BASE%\datos"

REM  La edicion (owner / profesional / demo) sale de edicion.json, el mismo
REM  archivo que hornea el instalador. Sin el, el programa arranca en demo.
if exist "%~dp0edicion.json" set "MVDAXLAB_EDICION_ARCHIVO=%~dp0edicion.json"

echo.
echo  ============================================================
echo   MV DAX Lab
echo   Tu modelo de Power BI, explicado, corregido y exportado.
echo  ============================================================
echo.
echo   Abriendo en  http://localhost:8747
echo   Para cerrar el programa: cerra esta ventana negra.
echo.

"%PYW%" -m streamlit run "%APP%\app\app.py"

if errorlevel 1 (
    echo.
    echo  [X] El programa termino con error. La linea de arriba dice por que.
    pause
)
endlocal
