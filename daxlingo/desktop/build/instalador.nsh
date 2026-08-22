; MV DAX Lab · Añadidos al instalador NSIS que genera electron-builder.
;
; electron-builder ya resuelve lo grueso (elegir carpeta, accesos directos,
; entrada en «Agregar o quitar programas», desinstalador). Acá va lo que la
; configuración declarativa no cubre:
;
;   1. anclar el acceso a la barra de tareas — la opción de package.json no
;      existe; se hace con el verbo de shell "taskbarpin".
;   2. borrar los datos del usuario SOLO si lo pide explícitamente, para que
;      desinstalar no se lleve licencias ni preferencias por accidente.
;   3. limpiar el rastro de una instalación que ya no está, para que SIEMPRE
;      se pueda elegir disco (ver el macro preInit, es el más importante de
;      los tres).

; --- Por qué existe preInit -------------------------------------------------
;
; Leído en el propio node_modules/app-builder-lib de este proyecto
; (templates/nsis/assistedInstaller.nsh + multiUser.nsh), no adivinado:
;
;   .onInit → initMultiUser lee InstallLocation de HKCU y de HKLM para esta
;   misma clave (Software\${APP_GUID}, una por edición). Si CUALQUIERA de
;   las dos tiene algo, asume "esto es una actualización": copia esa ruta
;   vieja a $INSTDIR y, más abajo, skipPageIfUpdated se salta la página de
;   licencia Y la de carpeta. El usuario nunca llega a ver el diálogo donde
;   podría elegir D:\ — el instalador reinstala derecho en la ruta que ya
;   tenía anotada.
;
; Para una reinstalación de verdad (la app sigue ahí, se está actualizando)
; ese comportamiento es el correcto y el esperado: no hay que volver a
; preguntar dónde instalarla. El problema es cuando la marca del registro
; quedó pero la carpeta YA NO ESTÁ — se borró a mano, quedó a medias por un
; disco sin espacio, un antivirus la puso en cuarentena — porque ahí no es
; una actualización de nada: es una marca fantasma, y sin embargo el
; instalador se comporta exactamente igual, mandando otra vez a una carpeta
; que no existe y saltándose la posibilidad de elegir otra.
;
; preInit corre ANTES de initMultiUser (es el primer hook que ofrece
; installer.nsi) y borra la marca SOLO cuando el ejecutable ya no está en la
; ruta anotada. Una instalación real y funcionando nunca pierde su "esto es
; una actualización": el chequeo es `¿existe el .exe ahí?`, no una fecha ni
; una versión.

; --- Y por qué preInit empieza con SetRegView --------------------------------
;
; Esta parte costó una corrida entera de CI (18/8): la limpieza de abajo
; estaba bien pensada y aun así el instalador reinstaló 5 de 5 veces en la
; carpeta vieja y borrada. El motivo no era la lógica, era DÓNDE miraba.
;
; installer.nsi llama a preInit en la línea 49 y a check64BitAndSetRegView
; recién en la 60 — y ese segundo macro es el que hace `SetRegView 64` en los
; builds x64. O sea que preInit corre con la vista de 32 bits todavía puesta,
; y ahí HKLM\Software está redirigido por WOW64 a HKLM\Software\WOW6432Node.
; initMultiUser (línea 70, ya con la vista en 64) lee la de verdad. Resultado:
; se leía y se borraba en un lugar donde nunca hubo nada, y la marca fantasma
; sobrevivía intacta a la limpieza.
;
; Por eso el SetRegView explícito acá arriba. Se restaura al salir: dos líneas
; después check64BitAndSetRegView la vuelve a poner en 64 igual, pero un hook
; no tiene por qué dejar efectos colaterales sobre el resto del script.

!macro preInit
  ${if} ${RunningX64}
    SetRegView 64
  ${endIf}

  ReadRegStr $0 HKCU "Software\${APP_GUID}" "InstallLocation"
  ${if} $0 != ""
    ${ifNot} ${FileExists} "$0\${APP_EXECUTABLE_FILENAME}"
      DeleteRegValue HKCU "Software\${APP_GUID}" "InstallLocation"
    ${endIf}
  ${endIf}

  ; Borrar en HKLM pide permisos de administrador. Con nsis.perMachine en
  ; true el .exe ya viene manifestado RequestExecutionLevel=admin, así que a
  ; esta altura el proceso está elevado y el borrado sí se aplica. Si algún
  ; día se volviera a perMachine:false, esto pasaría a ser best-effort: sin
  ; permisos DeleteRegValue no falla, simplemente no hace nada.
  ReadRegStr $0 HKLM "Software\${APP_GUID}" "InstallLocation"
  ${if} $0 != ""
    ${ifNot} ${FileExists} "$0\${APP_EXECUTABLE_FILENAME}"
      DeleteRegValue HKLM "Software\${APP_GUID}" "InstallLocation"
    ${endIf}
  ${endIf}

  ${if} ${RunningX64}
    SetRegView Default
  ${endIf}
!macroend

; --- customInit: no mandar la instalación a un disco sin lugar ---------------
;
; El pedido original fue "me autodirige al disco C y yo no tengo espacio ahí".
; La mitad grande de eso ya la resuelve preInit (arriba): la marca fantasma
; que se saltaba la página de carpeta. Con eso, el usuario VE el diálogo y
; puede elegir D:.
;
; Pero el valor que viene propuesto en ese diálogo sigue siendo
; $PROGRAMFILES64, o sea C:. Si C: está lleno, el que le da "Siguiente" sin
; mirar —que son casi todos— se choca contra el mismo problema.
;
; Acá se cambia SOLO ese valor propuesto, y solo cuando C: de verdad no tiene
; lugar. Con el disco del sistema sano no pasa nada: la convención de Windows
; es instalar en Archivos de programa y no hay motivo para romperla.
;
; Tres candados, para que esto nunca elija mal:
;   1. Solo si NO es una actualización (si la app ya está instalada, su
;      carpeta manda; no se la movemos por abajo).
;   2. Solo en instalación interactiva. Una silenciosa (/S) es un script, y el
;      script decide — por eso el CI, que instala con /S, no cambia en nada.
;   3. Solo unidades FIJAS (${GetDrives} "HDD"): nunca un pendrive, nunca una
;      unidad de red. Instalar ahí sería peor que quedarse sin espacio.
;
; ${GetRoot}, ${DriveSpace} y ${GetDrives} salen de FileFunc.nsh, que ya viene
; incluido por multiUser.nsh (línea 1) — o sea, disponible acá sin agregar
; nada.

; OJO CON ESTOS DOS !include: no son de adorno.
;
; electron-builder mete este archivo como CABECERA, antes de installer.nsi
; (NsisTarget.js → computeCommonInstallerScriptHeader). Y installer.nsi es
; quien incluye common.nsh (LogicLib, vía x64.nsh) y multiUser.nsh
; (FileFunc.nsh). O sea que acá arriba todavía no existe ni ${if} ni
; ${DriveSpace}.
;
; A los !macro de este archivo no les afecta —un macro se compila donde se
; INSERTA, y para entonces installer.nsi ya cargó todo—, pero una Function se
; compila donde se DEFINE. Sin estas dos líneas, mvdaxMirarUnidad no compila
; y el build del instalador se cae entero.
;
; Incluirlos dos veces no molesta: los dos headers traen su propio guard
; (!ifndef LOGICLIB / FILEFUNC_INCLUDED).
!include LogicLib.nsh
!include FileFunc.nsh

!define MVDAX_MB_NECESARIOS 3000   ; el paquete pesa ~500 MB; el resto es aire

Var mvdaxMejorUnidad
Var mvdaxMejorLibre

; Callback de ${GetDrives}: se queda con la unidad fija que más espacio libre
; tenga. $9 = letra con barra ("D:\").
Function mvdaxMirarUnidad
  Push $R2
  ${DriveSpace} "$9" "/D=F /S=M" $R2
  ${if} $R2 > $mvdaxMejorLibre
    StrCpy $mvdaxMejorLibre $R2
    StrCpy $mvdaxMejorUnidad "$9"
  ${endIf}
  Pop $R2
  ; Cadena vacía = seguir recorriendo. Va literal y no `Push $0`: $0 podría
  ; traer cualquier cosa de antes y "StopGetDrives" cortaría el recorrido.
  Push ""
FunctionEnd

; Los ${if} van anidados y no con ${andIfNot} a propósito: este archivo ya
; tiene probado que ${if}/${ifNot}/${endIf} en minúscula compilan (preInit los
; usa desde siempre), y no vale la pena estrenar una variante nueva de LogicLib
; en un script que solo se compila en el CI, en Windows.
!macro customInit
  ${ifNot} ${Silent}
    ${ifNot} ${FileExists} "$INSTDIR\${APP_EXECUTABLE_FILENAME}"
      ${GetRoot} "$INSTDIR" $R0
      ${DriveSpace} "$R0\" "/D=F /S=M" $R1

      ${if} $R1 < ${MVDAX_MB_NECESARIOS}
        StrCpy $mvdaxMejorUnidad ""
        StrCpy $mvdaxMejorLibre $R1      ; hay que SUPERAR a la del sistema
        ${GetDrives} "HDD" "mvdaxMirarUnidad"

        ${if} $mvdaxMejorUnidad != ""
          ; $mvdaxMejorUnidad viene como "D:\", y ${APP_FILENAME} es el nombre
          ; de la carpeta del producto — el mismo que usa electron-builder
          ; para armar el default en Archivos de programa.
          StrCpy $INSTDIR "$mvdaxMejorUnidad${APP_FILENAME}"
          DetailPrint "El disco $R0 tiene $R1 MB libres; se propone $INSTDIR"
        ${endIf}
      ${endIf}
    ${endIf}
  ${endIf}
!macroend

!macro customInstall
  ; Anclar a la barra de tareas (best effort: si Windows lo rechaza por
  ; política, la instalación sigue igual).
  ExecShell "taskbarpin" "$INSTDIR\${APP_EXECUTABLE_FILENAME}"

  ; Que el instalador quede registrado con su icono y editor.
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTALL_APP_KEY}" \
    "DisplayIcon" "$INSTDIR\${APP_EXECUTABLE_FILENAME}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTALL_APP_KEY}" \
    "Publisher" "MV"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTALL_APP_KEY}" \
    "URLInfoAbout" "https://power-bi-mv13.vercel.app"
!macroend

!macro customUnInstall
  ExecShell "taskbarunpin" "$INSTDIR\${APP_EXECUTABLE_FILENAME}"

  ; Los datos del usuario (licencia, preferencias, bandeja del overlay) NO se
  ; borran salvo que lo confirme: quien desinstala para reinstalar no tiene
  ; por qué perder la licencia que pagó.
  ${ifNot} ${isUpdated}
    MessageBox MB_YESNO|MB_ICONQUESTION \
      "¿Borrar también tus datos de MV DAX Lab (licencia, preferencias y bandeja)?$\n$\nSi vas a reinstalar, elegí No." \
      /SD IDNO IDYES borrarDatos IDNO conservarDatos
    borrarDatos:
      RMDir /r "$APPDATA\mv-dax-lab"
    conservarDatos:
  ${endIf}
!macroend
