# Runtime de Python embebido

Esta carpeta va **vacía en el repo** y se llena antes de construir el
instalador. Es lo que hace que el cliente **no tenga que instalar Python**:
el `.exe` trae su propio intérprete.

`main.cjs` lo busca en `resources/runtime/python.exe` (Windows) o
`resources/runtime/bin/python3` (Linux/macOS). Si no lo encuentra, cae al
Python del sistema — que es lo que pasa cuando corrés desde el código.

## Cómo prepararlo (Windows, una sola vez por versión)

1. Bajá el **embeddable package** de Python 3.11 (x64) de
   <https://www.python.org/downloads/windows/> y descomprimilo acá dentro,
   de modo que quede `runtime/python.exe`.

2. Habilitá `site-packages` en el runtime embebido: abrí el archivo
   `python311._pth` y **descomentá** la línea `import site`. Sin eso, `pip`
   instala pero los paquetes no se importan.

3. Instalá pip y las dependencias del motor dentro del runtime:

   ```bat
   curl -o get-pip.py https://bootstrap.pypa.io/get-pip.py
   runtime\python.exe get-pip.py
   runtime\python.exe -m pip install -r ..\requirements.txt
   ```

4. Verificá que arranca solo:

   ```bat
   runtime\python.exe -m streamlit --version
   ```

5. Recién ahí, construí el instalador:

   ```bat
   npm run dist            :: edición cliente
   npm run ediciones       :: las tres (owner, cliente, demo)
   ```

## Por qué no está commiteado

Pesa ~180 MB con las dependencias y GitHub rechaza archivos de más de 100 MB
en el push. Además es un binario específico de plataforma: versionarlo
ensuciaría el repo sin dar nada a cambio. El instalador que se publica en el
release **sí lo lleva adentro** — el usuario final no ve nada de esto.

## Linux y macOS

No hace falta runtime embebido: se corre desde el código con
`pip install -r daxlingo/requirements.txt` y
`streamlit run daxlingo/app/app.py`, o `npm start` dentro de `desktop/`
para la ventana de Electron.
