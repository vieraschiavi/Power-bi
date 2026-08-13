#!/usr/bin/env python3
# © 2026 Martín Viera. Todos los derechos reservados.

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

from dxl import licencia, tema_streamlit  # noqa: E402
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

    # Las capturas se toman sobre una instalación LICENCIADA, no sobre la
    # edición owner. Antes iban con `MVDAX_EDICION=owner` para que ninguna
    # función quedara tapada por el cartel de licencia — el efecto secundario
    # era que la web y el video mostraban «Edición: 👑 owner», que es la copia
    # del dueño y no la que compra nadie. Se firma una licencia perpetua con
    # un secreto de usar y tirar: el estado que sale en pantalla es
    # exactamente el de un cliente que pagó — `profesional`, sin vencimiento
    # y con todo abierto.
    secreto = "capturas-" + os.urandom(8).hex()
    (datos / "estado.json").write_text(
        json.dumps({"prefs": {"idioma": idioma},
                    "licencia": licencia.firmar({"plan": "perpetua"}, secreto)}),
        encoding="utf-8")

    puerto = puerto_libre()
    entorno = {**os.environ,
               "MVDAXLAB_DATOS": str(datos),
               "MVDAXLAB_BANDEJA": str(datos / "bandeja"),
               "MVDAX_LICENSE_SECRET": secreto,
               # El tema por variable de entorno, no por config.toml:
               # Streamlit solo lee `.streamlit/config.toml` del directorio
               # actual, y acá se arranca desde donde sea. Sin esto el marco
               # sale con el tema claro por defecto.
               **tema_streamlit()}
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


# Qué escribir en cada pestaña antes de la foto. Una captura de un formulario
# vacío no vende nada: la pestaña estrella —NL→DAX— salía con un input en
# blanco. Acá se maneja la app como la manejaría alguien mostrándola, y la
# foto sale con el resultado puesto.
#
# El pedido va en el idioma de la captura, PERO nombrando una medida que
# existe: el modelo de ejemplo tiene los nombres en español, así que pedir
# «sales» en inglés no encuentra nada y la captura de venta sale con un error.
# Lo que se muestra trilingüe es el patrón («vs last year», «vs ano anterior»),
# que es lo que el motor entiende en los tres idiomas.
PEDIDOS = {"es": "ventas vs año anterior",
           "en": "Unidades vs last year",
           "pt": "Unidades vs ano anterior"}
CONSULTA_OVERLAY = {
    "es": "¿por qué el total del año no coincide con la suma de los meses?",
    "en": "why doesn't the year total match the sum of the months?",
    "pt": "por que o total do ano não bate com a soma dos meses?"}


def guionar(pagina, slug: str, idioma: str) -> None:
    """Deja cada pestaña mostrando un resultado, no un formulario vacío.

    Cada paso va en su propio try: si un guion deja de encajar porque cambió
    un widget, se pierde ese resultado en la captura —no las 14 capturas.
    """
    # Streamlit deja en el DOM el contenido de TODAS las pestañas, no solo la
    # abierta: un `get_by_role` global agarra el widget de cualquier otra y
    # toca lo que no debe —así se cambió una preferencia y la tanda siguiente
    # se fue al pasto. Todo se busca dentro del panel visible.
    panel = pagina.locator('[role="tabpanel"]:visible').first

    def escribir(clave_placeholder: str, texto: str) -> bool:
        campo = panel.get_by_placeholder(t(clave_placeholder, idioma))
        if not campo.count():
            return False
        campo.first.fill(texto)
        campo.first.press("Enter")
        return True

    try:
        if slug == "generar":
            if escribir("gen_ejemplos", PEDIDOS[idioma]):
                pagina.wait_for_timeout(3000)

        elif slug == "explicador":
            # La segunda opción del selector es la primera medida real del
            # modelo: elegirla muestra la explicación paso a paso, que es lo
            # que se vende, en vez de un textarea vacío.
            sel = panel.get_by_role("combobox")
            if sel.count():
                sel.first.click()
                pagina.wait_for_timeout(700)
                # baseweb pinta las opciones como div[role=option], no como
                # <li>: con el selector de más no cerraba nunca y el desplegable
                # quedaba abierto tapando la barra de pestañas — de ahí que las
                # 8 capturas siguientes salieran «sin pestaña».
                opciones = pagina.locator('[role="option"]')
                if opciones.count() > 1:
                    opciones.nth(1).click()
                    pagina.wait_for_timeout(2500)
                else:
                    pagina.keyboard.press("Escape")

        elif slug == "overlay":
            # Sin API key el botón contesta «falta la clave», así que acá solo
            # se deja la consulta escrita: se ve para qué sirve la pestaña sin
            # mostrar un error en la foto de venta.
            escribir("ov_placeholder", CONSULTA_OVERLAY[idioma])
            pagina.wait_for_timeout(1200)

        elif slug == "exportar":
            boton = panel.get_by_role("button", name=t("ex_btn_pbit", idioma))
            if boton.count():
                boton.first.click()
                pagina.wait_for_timeout(4000)
    except Exception as exc:      # noqa: BLE001 — un guion roto no frena la tanda
        print(f"  · guion «{slug}» sin efecto: {exc}")


def recortar(archivo: Path, margen: int = 28) -> None:
    """Corta el fondo vacío que queda debajo del contenido.

    Una pestaña corta —la Guía, la Licencia— deja media pantalla de navy
    liso. En la galería de la web todas las tarjetas tienen el mismo alto, así
    que esa mitad vacía empuja el contenido real hacia arriba y la captura se
    ve descentrada. Recortando hasta la última fila con contenido, el
    contenido queda centrado en su tarjeta.

    Se compara contra el color de la esquina inferior derecha (fondo puro) con
    una tolerancia: el fondo es un degradado, no un color plano, así que una
    comparación exacta no recorta nada.
    """
    from PIL import Image

    with Image.open(archivo) as img:
        img = img.convert("RGB")
        ancho, alto = img.size
        pixeles = img.load()
        fondo = pixeles[ancho - 4, alto - 4]
        limite = alto
        for y in range(alto - 1, 0, -1):
            fila_vacia = True
            # Muestreo cada 8 px: barrer 3360 columnas por fila multiplica el
            # tiempo por nada — un elemento visible siempre es más ancho.
            for x in range(0, ancho, 8):
                p = pixeles[x, y]
                if (abs(p[0] - fondo[0]) + abs(p[1] - fondo[1])
                        + abs(p[2] - fondo[2])) > 24:
                    fila_vacia = False
                    break
            if not fila_vacia:
                limite = min(alto, y + margen)
                break
        # Un piso razonable: sin esto, una pestaña casi vacía daría una tira
        # de 100 px que en la galería se ve como un error, no como una captura.
        limite = max(limite, int(alto * 0.42))
        if limite < alto:
            img.crop((0, 0, ancho, limite)).save(archivo)


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
                    # Cualquier desplegable que haya quedado abierto tapa la
                    # barra de pestañas y arruina de acá en adelante.
                    pagina.keyboard.press("Escape")
                    pagina.wait_for_timeout(250)
                    pestana = pagina.get_by_role("tab", name=etiqueta)
                    if not pestana.count():
                        print(f"  ! sin pestaña «{etiqueta}»")
                        continue
                    pestana.first.click()
                    pagina.wait_for_timeout(2500)
                    guionar(pagina, slug, idioma)
                    archivo = destino / f"{slug}.png"
                    pagina.screenshot(path=str(archivo))
                    recortar(archivo)
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
