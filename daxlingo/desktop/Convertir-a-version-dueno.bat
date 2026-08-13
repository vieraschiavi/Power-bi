@echo off
REM ===========================================================================
REM  MV DAX Lab - pasar ESTA instalacion a la edicion OWNER
REM
REM  Doble clic desde donde sea. El .bat BUSCA SOLO donde quedo instalado el
REM  programa: no hace falta copiarlo a la carpeta de la app ni saber la ruta.
REM  Deja el programa abierto entero: sin clave, sin prueba de 7 dias y sin
REM  ninguna funcion trabada.
REM
REM  No reinstala ni descarga nada: reescribe el sello de edicion que el
REM  programa lee al arrancar. Tarda un segundo y es reversible:
REM      Convertir-a-version-dueno.bat /revertir
REM
REM  Si tenes varias ediciones instaladas a la vez (cliente, demo, owner), las
REM  lista y te deja elegir cual convertir.
REM
REM  ---------------------------------------------------------------------
REM  NO REPARTAS ESTE ARCHIVO. Convierte cualquier copia instalada en la
REM  version completa. Es tu llave maestra, no parte del producto.
REM  ---------------------------------------------------------------------
REM ===========================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"
title MV DAX Lab - edicion OWNER

set "MARCA=resources\app\dxl\licencia.py"
set "TOTAL=0"

REM ===========================================================================
REM  1. Encontrar la instalacion
REM ===========================================================================
REM  Cuatro vias, de la mas barata a la mas cara. La del registro es la que
REM  importa: el instalador deja ELEGIR la carpeta (allowToChangeInstallation-
REM  Directory), asi que una lista de rutas fijas falla apenas alguien instala
REM  en D:\Programas o en cualquier otro lado. NSIS anota la ruta real al
REM  registrar la app en "Agregar o quitar programas", y de ahi la sacamos.

REM --- via 1: al lado de este .bat (lo mas rapido si esta junto al .exe) -----
if exist "%~dp0%MARCA%" call :agregar "%~dp0"

REM --- via 2: el registro de Windows ----------------------------------------
REM  perMachine:false => la app se registra en HKCU. Igual se miran las tres
REM  ramas de "Agregar o quitar programas" por si alguna vez se instalo para
REM  todos los usuarios: usuario, maquina, y la de 32 bits en un Windows de 64
REM  (WOW6432Node), que es donde cae un paquete x86 y no aparece en la otra.
REM  Se recorren las claves, se filtra por DisplayName y se lee InstallLocation.
call :buscarEnRegistro "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall"
call :buscarEnRegistro "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall"
call :buscarEnRegistro "HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"

REM --- via 3: las rutas por defecto de NSIS ----------------------------------
REM  Red de seguridad para una instalacion cuya entrada de registro se haya
REM  borrado a mano.
REM
REM  Los Archivos de programa se copian a variables ANTES del bloque: el
REM  nombre real de la de 32 bits trae parentesis y, escrita adentro de un
REM  bloque `( ... )`, cmd la toma como el cierre del bloque y el .bat muere
REM  con un error de sintaxis.
set "PF64=%ProgramFiles%"
set "PF32=%ProgramFiles(x86)%"
for %%D in ("MV DAX Lab" "MV DAX Lab OWNER" "MV DAX Lab DEMO") do (
    call :agregar "%LOCALAPPDATA%\Programs\%%~D\"
    call :agregar "!PF64!\%%~D\"
    call :agregar "!PF32!\%%~D\"
)

REM --- via 4: el acceso directo del escritorio -------------------------------
REM  Ultimo recurso: si el .lnk existe, su destino apunta al .exe instalado.
if "%TOTAL%"=="0" call :buscarEnAccesoDirecto

if "%TOTAL%"=="0" (
    echo.
    echo  ============================================================
    echo   No encontre ninguna instalacion de MV DAX Lab
    echo  ============================================================
    echo.
    echo   Se busco:
    echo     - en esta misma carpeta
    echo     - en el registro de Windows ^(HKCU y HKLM^)
    echo     - en %%LOCALAPPDATA%%\Programs, Archivos de programa
    echo     - en el acceso directo del escritorio
    echo.
    echo   Instala primero MV DAX Lab con el .exe y volve a correr esto.
    echo.
    pause
    exit /b 1
)

REM --- elegir, si hay mas de una --------------------------------------------
if %TOTAL% GTR 1 (
    echo.
    echo  ============================================================
    echo   Hay %TOTAL% instalaciones de MV DAX Lab
    echo  ============================================================
    echo.
    for /l %%I in (1,1,%TOTAL%) do echo    %%I^) !RUTA%%I!
    echo.
    set /p "ELEGIDA=Cual convertir? (1-%TOTAL%, Enter = 1): "
    if not defined ELEGIDA set "ELEGIDA=1"
) else (
    set "ELEGIDA=1"
)

REM  Un numero fuera de rango o cualquier cosa que no sea un numero cae en la
REM  primera: es preferible convertir la que se encontro primero a explotar.
set "APP=!RUTA%ELEGIDA%!"
if not defined APP set "APP=%RUTA1%"

REM ===========================================================================
REM  2. Python
REM ===========================================================================
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

REM ===========================================================================
REM  3. El sellador
REM ===========================================================================
REM  Puede venir junto a este .bat o dentro del paquete instalado. Se prueban
REM  las dos ubicaciones para que el .bat sirva suelto y tambien copiado
REM  adentro de la instalacion.
set "SELLADOR=%~dp0scripts\sellar_edicion.py"
if not exist "%SELLADOR%" set "SELLADOR=%APP%scripts\sellar_edicion.py"
if not exist "%SELLADOR%" set "SELLADOR=%APP%resources\app\..\scripts\sellar_edicion.py"
if not exist "%SELLADOR%" (
    echo  [X] Falta scripts\sellar_edicion.py.
    echo      Tiene que estar junto a este .bat o dentro de la instalacion.
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
echo     Convertir-a-version-dueno.bat /revertir
echo.
pause
endlocal
exit /b 0


REM ===========================================================================
REM  Subrutinas
REM ===========================================================================

REM --- :agregar <carpeta> ----------------------------------------------------
REM  Suma una carpeta a la lista si tiene el producto adentro y no estaba ya.
REM  Sin el chequeo de duplicados, la instalacion por defecto aparece dos veces
REM  (una por el registro y otra por la ruta fija) y el menu queda absurdo.
:agregar
set "CAND=%~1"
if "%CAND%"=="" exit /b 0
if not "%CAND:~-1%"=="\" set "CAND=%CAND%\"
if not exist "%CAND%%MARCA%" exit /b 0
for /l %%I in (1,1,%TOTAL%) do (
    if /i "!RUTA%%I!"=="%CAND%" exit /b 0
)
set /a TOTAL+=1
set "RUTA%TOTAL%=%CAND%"
exit /b 0

REM --- :buscarEnRegistro <clave raiz de desinstalacion> ---------------------
REM  Recorre las entradas de "Agregar o quitar programas" y se queda con las
REM  que son de MV DAX Lab. La ruta sale de InstallLocation; si esa esta vacia
REM  (pasa con algunos paquetes), se usa la carpeta del DisplayIcon, que
REM  instalador.nsh apunta al .exe instalado.
:buscarEnRegistro
set "RAIZ=%~1"
for /f "delims=" %%K in ('reg query "%RAIZ%" 2^>nul') do (
    set "NOMBRE="
    for /f "tokens=2,*" %%A in ('reg query "%%K" /v DisplayName 2^>nul ^| findstr /i /c:"DisplayName"') do set "NOMBRE=%%B"
    if defined NOMBRE (
        echo !NOMBRE! | findstr /i /c:"MV DAX Lab" >nul && (
            set "HALLADA="
            for /f "tokens=2,*" %%C in ('reg query "%%K" /v InstallLocation 2^>nul ^| findstr /i /c:"InstallLocation"') do set "HALLADA=%%D"
            REM  InstallLocation puede venir vacia. El DisplayIcon que escribe
            REM  instalador.nsh apunta al .exe instalado, asi que su carpeta
            REM  es la misma instalacion.
            if not defined HALLADA (
                for /f "tokens=2,*" %%E in ('reg query "%%K" /v DisplayIcon 2^>nul ^| findstr /i /c:"DisplayIcon"') do (
                    for %%P in ("%%F") do set "HALLADA=%%~dpP"
                )
            )
            if defined HALLADA call :agregar "!HALLADA!"
        )
    )
)
exit /b 0

REM --- :buscarEnAccesoDirecto ------------------------------------------------
REM  Lee el destino del .lnk del escritorio con PowerShell. Solo se llega aca
REM  si todo lo anterior fallo, asi que el costo de arrancar PowerShell esta
REM  justificado.
:buscarEnAccesoDirecto
for %%E in ("%USERPROFILE%\Desktop" "%PUBLIC%\Desktop") do (
    if exist "%%~E\MV DAX Lab.lnk" (
        for /f "delims=" %%T in ('powershell -NoProfile -Command ^
            "(New-Object -ComObject WScript.Shell).CreateShortcut('%%~E\MV DAX Lab.lnk').TargetPath" 2^>nul') do (
            for %%P in ("%%T") do call :agregar "%%~dpP"
        )
    )
)
exit /b 0
