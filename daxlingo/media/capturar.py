#!/usr/bin/env python3
"""
MV DAX Lab · Capturas reales de la app, pestaña por pestaña y en los 3 idiomas.

No son maquetas: levanta la app de verdad, carga el modelo demo, hace clic en
cada pestaña y fotografía lo que se ve. De ahí salen las imágenes de la
landing y los cuadros del video — si una pestaña se rompe, la captura sale
rota y nos enteramos acá, no el cliente.

Uso:
    python daxlingo/media/capturar.py              # es, en, pt
    python daxlingo/media/capturar.py --idioma es  # solo uno

Requisitos: streamlit y playwright instalados; el Chromium de Playwright
disponible (en este entorno, PLAYWRIGHT_BROWSERS_PATH ya apunta a él).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dxl.i18n import IDIOMAS, t  # noqa: E402

SALIDA = RAIZ / "web" / "assets" / "img"
# 1680 de ancho para que las 14 pestañas entren sin la flecha de desborde.
ANCHO, ALTO = 1680, 960

# (slug del archivo, clave i18n de la pestaña). El slug es estable en los tres
# idiomas: la landing referencia siempre el mismo nombre de archivo.
PESTANAS = [
    ("guia", "tab_guia"),
    ("modelo", "tab_modelo"),
    ("relaciones", "tab_relaciones"),
    ("analizador", "tab_analizador"),
    ("generar", "tab_generar"),
    ("explicador", "tab_explicar"),
    ("transformar", "tab_transformar"),
    ("exportar", "tab_exportar"),
    ("fabric", "tab_fabric"),
    ("overlay", "tab_overlay"),
    ("academia", "tab_academia"),
    ("herramientas", "tab_herramientas"),
    ("licencia", "tab_licencia"),
    ("configuracion", "tab_config"),
]


def chromium_local() -> str | None:
    """
    Chromium ya instalado, si lo hay. Cuando la versión de Playwright no
    coincide con la del navegador descargado, `launch()` falla pidiendo
    `playwright install`; apuntar al binario existente evita bajar 150 MB de
    nuevo. Devolver None deja que Playwright resuelva solo.
    """
    base = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    if not base.exists():
        return None
    candidatos = sorted(base.glob("chromium-*/chrome-linux/chrome"))
    return str(candidatos[-1]) if candidatos else None


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def arrancar_app(idioma: str, datos: Path) -> tuple[subprocess.Popen, int]:
    """Levanta la app con el idioma ya elegido en el estado persistido."""
    datos.mkdir(parents=True, exist_ok=True)
    (datos / "estado.json").write_text(
        json.dumps({"prefs": {"idioma": idioma}}), encoding="utf-8")
    puerto = puerto_libre()
    entorno = {**os.environ,
               "MVDAXLAB_DATOS": str(datos),
               "MVDAXLAB_BANDEJA": str(datos / "bandeja"),
               # Edición owner: las capturas muestran la app completa, sin el
               # cartel de licencia tapando las funciones.
               "MVDAX_EDICION": "owner"}
    proceso = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(RAIZ / "app" / "app.py"),
         "--server.port", str(puerto), "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=entorno)
    return proceso, puerto


def esperar(puerto: int, intentos: int = 60) -> bool:
    import urllib.request
    for _ in range(intentos):
        try:
            with urllib.request.urlopen(f"http://localhost:{puerto}",
                                        timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def capturar_idioma(idioma: str) -> list[Path]:
    from playwright.sync_api import sync_playwright

    destino = SALIDA / idioma
    destino.mkdir(parents=True, exist_ok=True)
    datos = Path("/tmp") / f"dxl_cap_{idioma}"
    shutil.rmtree(datos, ignore_errors=True)

    proceso, puerto = arrancar_app(idioma, datos)
    hechas: list[Path] = []
    try:
        if not esperar(puerto):
            raise RuntimeError(f"la app no respondió en el puerto {puerto}")
        with sync_playwright() as p:
            navegador = p.chromium.launch(executable_path=chromium_local())
            pagina = navegador.new_page(
                viewport={"width": ANCHO, "height": ALTO},
                device_scale_factor=2)
            pagina.goto(f"http://localhost:{puerto}", wait_until="networkidle")
            pagina.wait_for_timeout(3500)

            # Cargar el modelo demo para que las capturas tengan contenido
            # real. El botón vive en la pestaña «Modelo»: hay que abrirla
            # primero — Streamlit deja las pestañas inactivas ocultas y un
            # clic sobre un elemento oculto no llega.
            pagina.get_by_role("tab", name=t("tab_modelo", idioma)) \
                  .first.click()
            pagina.wait_for_timeout(1200)
            boton = pagina.get_by_role("button", name=t("btn_demo", idioma))
            if boton.count():
                boton.first.click()
                pagina.wait_for_timeout(7000)

            for slug, clave in PESTANAS:
                etiqueta = t(clave, idioma)
                try:
                    pestana = pagina.get_by_role("tab", name=etiqueta)
                    if not pestana.count():
                        print(f"  ! sin pestaña «{etiqueta}»")
                        continue
                    pestana.first.click()
                    pagina.wait_for_timeout(2500)
                    archivo = destino / f"{slug}.png"
                    pagina.screenshot(path=str(archivo))
                    hechas.append(archivo)
                    print(f"  ✓ {idioma}/{slug}.png")
                except Exception as exc:
                    print(f"  ! {slug}: {exc}")
            navegador.close()
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proceso.kill()
    return hechas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--idioma", choices=IDIOMAS,
                    help="capturar un solo idioma (por defecto, los tres)")
    args = ap.parse_args()

    idiomas = [args.idioma] if args.idioma else list(IDIOMAS)
    total = 0
    for idioma in idiomas:
        print(f"\n▶ Capturando en «{idioma}»…")
        total += len(capturar_idioma(idioma))
    print(f"\n✅ {total} capturas en {SALIDA}")


if __name__ == "__main__":
    main()
