@echo off
REM ===========================================================================
REM  MV DAX Lab - version PORTABLE
REM
REM  Doble clic y listo: no instala nada, no toca el registro y no pide
REM  permisos de administrador. Copiala a un pendrive y funciona igual, con su
REM  licencia adentro (se guarda en datos-usuario\, aca al lado).
REM
REM  Es la otra mitad de la distribucion: el instalador .exe deja la app con su
REM  ventana y su desinstalador; esto es para la PC de trabajo donde no te
REM  dejan instalar programas.
REM
REM  ---------------------------------------------------------------------
REM  Este .bat es a proposito TONTO: busca un Python y llama a lanzador.py.
REM  Toda la logica que puede fallar -elegir puerto, sellar la edicion,
REM  esperar a que levante, abrir el navegador- vive en Python, que si se
REM  puede probar fuera de Windows. Un .bat con logica se entrega sin haberlo
REM  ejecutado nunca.
REM  ---------------------------------------------------------------------
REM ===========================================================================

setlocal
cd /d "%~dp0"
title MV DAX Lab

REM 1) El runtime que viaja en el paquete, si esta.
set "PY="
if exist "runtime\python.exe" set "PY=runtime\python.exe"

REM 2) Si no, el Python del sistema. `py` primero: es el lanzador oficial y
REM    resuelve la version aunque haya varias instaladas.
if not defined PY (
    py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)

if not defined PY (
    echo.
    echo  [X] No encontre Python en esta PC.
    echo.
    echo      Dos opciones:
    echo        - Instala Python 3.11 desde https://python.org
    echo          ^(tildar "Add python.exe to PATH" en la primera pantalla^)
    echo        - O usa el instalador MV-DAX-Lab-Setup.exe, que trae todo
    echo          adentro y no necesita Python.
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   MV DAX Lab - version portable
echo  ============================================================
echo.
echo   Python: %PY%
echo.

REM Primera vez: faltan las dependencias. Se instalan en el perfil del
REM usuario (--user), que no necesita administrador.
%PY% -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo   Primera vez: instalando lo que hace falta. Tarda unos minutos.
    echo.
    %PY% -m pip install --user -q -r requirements-app.txt
    if errorlevel 1 (
        echo.
        echo  [X] No se pudieron instalar las dependencias.
        echo      Revisa la conexion a internet y volve a intentar.
        echo.
        pause
        exit /b 1
    )
)

%PY% lanzador.py
if errorlevel 1 (
    echo.
    echo  [X] La aplicacion se cerro con un error. El detalle esta arriba.
    echo.
    pause
    exit /b 1
)

endlocal
