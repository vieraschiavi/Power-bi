#!/usr/bin/env python3
"""
MV DAX Lab · Arranque de la versión portable (sin instalar).

La otra mitad de la distribución. El instalador `.exe` (Electron) deja la app
con su ventana, su icono y su desinstalador; esto es la misma app corriendo en
el navegador desde una carpeta que se copia y se borra — para el que no puede
instalar programas en su PC de trabajo, que en empresas es la mayoría.

Por qué la lógica vive acá y no en el .bat
------------------------------------------
Un .bat con lógica no se puede probar en ningún lado que no sea Windows, y en
este proyecto se desarrolla en Linux: terminaría entregado sin ejecutar nunca.
Acá está todo lo que puede fallar —elegir puerto, sellar la edición, esperar a
que Streamlit levante, abrir el navegador— y tiene tests. El `.bat` sólo busca
un Python y llama a este archivo.

Uso:
    python lanzador.py              # elige puerto y abre el navegador
    python lanzador.py --puerto 8791
    python lanzador.py --sin-navegador
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# El runtime embebido de Windows, cuando la salida va por pipe (doble clic con
# stdout redirigido, o un paso de CI), usa cp1252 en vez de UTF-8 — y este
# archivo imprime tildes y guiones largos. Sin esto, la primera vez que algo
# no-ASCII llega a print() el script muere con UnicodeEncodeError antes de
# hacer nada. Pasó de verdad: reventó `empaquetar-portable.py` en el runner
# de Windows con el «▶» del primer print.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RAIZ = Path(__file__).resolve().parent
ESPERA_MAX = 120          # segundos que se le da a Streamlit para responder


def puerto_libre(preferido: int = 0) -> int:
    """Un puerto que esté libre. Con `preferido`, lo usa si se puede.

    Se prueba el preferido y se cae a uno que da el sistema: dos copias
    abiertas a la vez —la demo y la del dueño, por ejemplo— no pueden pelear
    por el mismo número.
    """
    if preferido:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", preferido))
                return preferido
            except OSError:
                pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def carpeta_datos() -> Path:
    """Dónde guardar licencia y preferencias.

    Junto a la carpeta portable, no en el perfil del usuario: el sentido de lo
    portable es que se copia a un pendrive y sigue funcionando con su licencia
    puesta. Si la carpeta es de sólo lectura se cae al perfil.
    """
    local = RAIZ / "datos-usuario"
    try:
        local.mkdir(parents=True, exist_ok=True)
        prueba = local / ".escritura"
        prueba.write_text("ok", encoding="utf-8")
        prueba.unlink()
        return local
    except OSError:
        base = Path(os.environ.get("APPDATA") or Path.home())
        alterna = base / "MV DAX Lab"
        alterna.mkdir(parents=True, exist_ok=True)
        return alterna


def sello() -> Path | None:
    """El `edicion.json` del paquete, si viaja con él."""
    for cand in (RAIZ / "edicion.json", RAIZ / "app" / "edicion.json"):
        if cand.exists():
            return cand
    return None


def entorno() -> dict[str, str]:
    datos = carpeta_datos()
    env = {**os.environ,
           "MVDAXLAB_DATOS": str(datos),
           "MVDAXLAB_BANDEJA": str(datos / "bandeja"),
           "PYTHONIOENCODING": "utf-8",
           "PYTHONUNBUFFERED": "1"}
    marca = sello()
    if marca:
        # El mismo nombre que lee dxl/licencia.py. Con el sello puesto, la
        # edición NO la decide la variable de entorno: una copia vendida no se
        # convierte en owner poniendo MVDAX_EDICION desde afuera.
        env["MVDAXLAB_EDICION_ARCHIVO"] = str(marca)
    return env


def esperar(puerto: int, proceso: subprocess.Popen,
            limite: int = ESPERA_MAX) -> bool:
    """Sondea el puerto hasta que Streamlit contesta. False si se rindió.

    Mira también si el proceso murió: sin eso, una app que falla al importar
    dejaba al usuario dos minutos delante de «Iniciando…» sin ninguna pista.
    """
    for _ in range(limite):
        if proceso.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{puerto}",
                                        timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


def arrancar(puerto: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(RAIZ / "app" / "app.py"),
         "--server.port", str(puerto),
         "--server.address", "127.0.0.1",
         "--server.headless", "true",
         "--browser.gatherUsageStats", "false",
         "--global.developmentMode", "false"],
        cwd=str(RAIZ), env=entorno(),
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--puerto", type=int, default=8791,
                    help="puerto preferido; si está ocupado se usa otro")
    ap.add_argument("--sin-navegador", action="store_true")
    ap.add_argument("--espera", type=int, default=ESPERA_MAX)
    a = ap.parse_args()

    if not (RAIZ / "app" / "app.py").exists():
        print("  [X] Falta app/app.py: el paquete está incompleto.")
        return 1

    puerto = puerto_libre(a.puerto)
    url = f"http://127.0.0.1:{puerto}"
    print(f"\n  MV DAX Lab — arrancando en {url}")
    print("  (esta ventana tiene que quedar abierta; cerrala para salir)\n")

    proceso = arrancar(puerto)
    if not esperar(puerto, proceso, a.espera):
        if proceso.poll() is not None:
            print("  [X] El motor se cerró solo al arrancar.")
            print("      Suele ser una dependencia que falta: probá")
            print("      pip install -r requirements-app.txt")
        else:
            print(f"  [X] No respondió en {a.espera} s.")
            proceso.terminate()
        return 1

    print(f"  Listo. Abrí {url} si el navegador no se abrió solo.")
    if not a.sin_navegador:
        webbrowser.open(url)
    try:
        proceso.wait()
    except KeyboardInterrupt:
        proceso.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
