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

REM ---------------------------------------------------------------------
REM  En que disco trabajar. Por defecto, el mismo donde esta este proyecto:
REM  la carpeta .cache-build de aca al lado. NO se usa la carpeta por
REM  defecto de electron-builder (C:\Users\...\AppData\Local) porque el
REM  Electron de 111 MB y sus reintentos llenan el disco del sistema y el
REM  build muere con "Espacio en disco insuficiente".
REM
REM  Para mandarla a otro disco, cualquiera de las dos:
REM      CONSTRUIR_OWNER.bat E:\mv-cache
REM      set MVDAX_BUILD_CACHE=E:\mv-cache
REM ---------------------------------------------------------------------
set "CACHE=%~1"
if not defined CACHE set "CACHE=%MVDAX_BUILD_CACHE%"

echo.
echo  ============================================================
echo   Construyendo MV DAX Lab - edicion OWNER
echo  ============================================================
echo.
if defined CACHE (
    echo   Disco de trabajo: %CACHE%
) else (
    echo   Disco de trabajo: %~dp0.cache-build
    echo   ^(para usar otro: CONSTRUIR_OWNER.bat E:\mv-cache^)
)

call node scripts/build-instaladores.js owner %CACHE%
if errorlevel 1 (
    echo.
    echo  [X] La construccion fallo. El detalle esta mas arriba.
    echo.
    echo   Las dos fallas mas comunes y como salir de cada una:
    echo.
    echo   - "Espacio en disco insuficiente"
    echo       Liberá espacio, o mandá la cache a otro disco:
    echo         CONSTRUIR_OWNER.bat E:\mv-cache
    echo.
    echo   - "Cannot create symbolic link" / "no dispone de un privilegio"
    echo       Prendé el Modo desarrollador de Windows
    echo       ^(Configuracion ^> Privacidad y seguridad ^> Para
    echo        desarrolladores^), o hace clic derecho en este archivo y
    echo       elegí "Ejecutar como administrador".
    echo.
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
