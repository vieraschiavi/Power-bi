@echo off
REM ===========================================================================
REM  MV DAX Lab - pasar ESTA instalacion a la edicion OWNER
REM
REM  Dejalo en la misma carpeta que "MV DAX Lab.exe" y hace doble clic. Deja
REM  el programa abierto entero: sin clave, sin prueba de 7 dias y sin ninguna
REM  funcion trabada.
REM
REM  No reinstala ni descarga nada: reescribe el sello de edicion que el
REM  programa lee al arrancar. Tarda un segundo y es reversible:
REM      DESBLOQUEAR_OWNER.bat /revertir
REM
REM  ---------------------------------------------------------------------
REM  NO REPARTAS ESTE ARCHIVO. Convierte cualquier copia instalada en la
REM  version completa. Es tu llave maestra, no parte del producto.
REM  ---------------------------------------------------------------------
REM ===========================================================================

setlocal
cd /d "%~dp0"
title MV DAX Lab - edicion OWNER

REM --- 1. Encontrar la instalacion -------------------------------------------
REM  Lo normal es que este .bat este al lado del .exe. Si se corre desde otro
REM  lado, se buscan las rutas donde NSIS instala por usuario (perMachine:
REM  false, o sea sin permisos de administrador).
set "APP="
if exist "%~dp0resources\app\dxl\licencia.py" set "APP=%~dp0"

if not defined APP (
  for %%D in ("MV DAX Lab" "MV DAX Lab OWNER" "MV DAX Lab DEMO") do (
    if not defined APP if exist "%LOCALAPPDATA%\Programs\%%~D\resources\app\dxl\licencia.py" (
      set "APP=%LOCALAPPDATA%\Programs\%%~D\"
    )
  )
)

if not defined APP (
    echo.
    echo  [X] No encontre una instalacion de MV DAX Lab.
    echo.
    echo      Copia este archivo a la carpeta donde esta "MV DAX Lab.exe"
    echo      y volve a hacer doble clic. Si no sabes cual es: boton derecho
    echo      sobre el acceso directo del escritorio y "Abrir ubicacion del
    echo      archivo".
    echo.
    pause
    exit /b 1
)

REM --- 2. Python --------------------------------------------------------------
REM  El programa YA trae su propio Python en resources\runtime: si el .exe
REM  arranca, este interprete existe. Se usa ese antes que ninguno del
REM  sistema, asi el .bat funciona en una PC que no tiene Python instalado.
set "PY="
if exist "%APP%resources\runtime\python.exe" set "PY=%APP%resources\runtime\python.exe"
if not defined PY ( py -3 --version >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python --version >nul 2>&1 && set "PY=python" )

if not defined PY (
    echo  [X] No encontre Python, ni el que trae el programa
    echo      ^(%APP%resources\runtime\python.exe^) ni uno del sistema.
    pause
    exit /b 1
)

set "SELLADOR=%~dp0scripts\sellar_edicion.py"
if not exist "%SELLADOR%" set "SELLADOR=%APP%resources\app\..\scripts\sellar_edicion.py"
if not exist "%SELLADOR%" (
    echo  [X] Falta scripts\sellar_edicion.py junto a este .bat.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   MV DAX Lab - edicion OWNER
echo  ============================================================
echo.
echo   Instalacion: %APP%
echo.

if /i "%~1"=="/revertir" (
    %PY% "%SELLADOR%" "%APP%." --revertir
    if errorlevel 1 ( pause & exit /b 1 )
    echo.
    echo   La instalacion volvio a su edicion original.
    echo.
    pause
    exit /b 0
)

%PY% "%SELLADOR%" "%APP%." --edicion owner
if errorlevel 1 (
    echo.
    echo  [X] No se pudo escribir el sello.
    echo      Cerra MV DAX Lab si esta abierto y proba de nuevo.
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Listo
echo  ============================================================
echo.
echo   Abri MV DAX Lab: en la barra de la izquierda tiene que decir
echo   "Edicion: owner". Todo desbloqueado, sin clave y sin vencimiento.
echo.
echo   Para volver a la edicion original:
echo     DESBLOQUEAR_OWNER.bat /revertir
echo.
pause
endlocal
