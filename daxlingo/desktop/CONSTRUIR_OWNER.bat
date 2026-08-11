@echo off
REM ===========================================================================
REM  MV DAX Lab - construir el instalador de la edicion OWNER
REM
REM  Produce  dist-instalador\MV-DAX-Lab-OWNER-Setup-1.0.0.exe
REM
REM  La edicion OWNER abre todo sin pedir ninguna clave y sin vencimiento. Se
REM  instala con su propio icono y su propio identificador, asi que convive en
REM  la misma PC con la version que le vendes al cliente: podes tener las dos
REM  abiertas para mostrar una demo sin cerrar la tuya.
REM
REM  ---------------------------------------------------------------------
REM  ESTE .EXE NO SE PUBLICA. El repositorio es PUBLICO: subirlo a un
REM  release, a la web o a un artifact de CI regala el producto entero. Se
REM  construye aca, en tu maquina, y se queda aca.
REM  ---------------------------------------------------------------------
REM ===========================================================================

setlocal
cd /d "%~dp0"
title MV DAX Lab - construir edicion OWNER

where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Falta Node.js.
    echo      Descargalo de https://nodejs.org  ^(version LTS^) y volve a
    echo      hacer doble clic en este archivo.
    echo.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo.
    echo   Instalando dependencias por unica vez. Tarda unos minutos.
    echo.
    call npm install
    if errorlevel 1 (
        echo  [X] Fallo npm install.
        pause
        exit /b 1
    )
)

echo.
echo  ============================================================
echo   Construyendo MV DAX Lab - edicion OWNER
echo  ============================================================
echo.

call node scripts/build-instaladores.js owner
if errorlevel 1 (
    echo.
    echo  [X] La construccion fallo. El detalle esta mas arriba.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Listo
echo  ============================================================
echo.
echo   El instalador quedo en:
echo     %~dp0dist-instalador\
echo.
echo   Ejecutalo y vas a poder elegir la carpeta, y te deja el acceso
echo   en el escritorio y en el menu Inicio. Abre sin pedir clave.
echo.
echo   Recorda: no lo subas a ningun lado.
echo.
pause
endlocal
