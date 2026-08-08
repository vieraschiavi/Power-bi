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
    "URLInfoAbout" "https://mvdaxlab.vercel.app"
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
