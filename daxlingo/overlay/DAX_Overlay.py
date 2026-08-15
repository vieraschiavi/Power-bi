#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · DAX Overlay — resolvé Power BI sin salir de la pantalla.

Adaptación para DAX/Power BI del SQL Overlay del autor: capturás lo que estás
mirando (un visual roto, una medida con error, un modelo, un enunciado) y la
respuesta aparece flotando sobre esa misma pantalla, explicada paso a paso.

  Atajos
  ------
  F9            captura TODA la pantalla y la resuelve
  Shift + F9    seleccionás un RECTÁNGULO con el mouse y resuelve eso
  Ctrl + F9     abre una ventana para ESCRIBIR la consulta (sin captura)
  Ctrl+Shift+M  limpia la memoria de capturas previas
  Esc           cierra la ventana flotante

  Integración con la app principal
  --------------------------------
  Cada respuesta se deposita también en la bandeja de MV DAX Lab
  (~/.mvdaxlab/bandeja). En la pestaña «Asistente de pantalla» de la app,
  las medidas y columnas calculadas que la IA propuso se aplican con un
  clic al modelo cargado — y de ahí a .pbit/PBIP/Fabric.

  Requisitos:  pip install anthropic pynput pillow
  API key:     ANTHROPIC_API_KEY en el entorno (o pegala al iniciar).
  Modelos:     MODELOS define la cadena principal → fallback; editable.
"""
from __future__ import annotations

import os
import sys
import threading
import time

# ==========================================================================
# Configuración
# ==========================================================================
# Cadena de modelos: el primero es el principal; si se satura o falla por
# límite de uso, se cae al siguiente. Editá a gusto (p. ej. poné primero
# claude-haiku-4-5-20251001 si te importa más el costo que la profundidad).
MODELOS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001"]

REINTENTOS_POR_MODELO = 2      # reintentos ante saturación (3s, 6s)
MEMORIA_ACTIVADA = True        # manda capturas previas como contexto
MEMORIA_MAX_CAPTURAS = 2
MEMORIA_MINUTOS_VIGENCIA = 20
MAX_TOKENS = 3000

SYSTEM_PROMPT = """Sos un experto senior en Power BI: DAX, modelado tabular, \
Power Query (M), visualización y Microsoft Fabric. Te llega una captura de \
pantalla o una consulta escrita. Identificá solo de qué se trata y respondé \
en español rioplatense:

1) Si es un pedido de MEDIDA o COLUMNA CALCULADA: primero la explicación \
paso a paso (por qué la expresión es esa, qué hace el contexto de filtro), \
después el DAX final en un bloque ```dax con el formato Nombre = expresión. \
Si es columna calculada, decilo explícitamente ("columna calculada") y \
aclará la tabla.
2) Si es un ERROR (barra amarilla, medida rota, visual vacío): qué lo causa \
y el fix concreto, con el DAX/M corregido en bloque de código.
3) Si es una pregunta de MODELADO (relaciones, estrella, rendimiento): el \
diagnóstico y los pasos accionables, en orden.
4) Si piden KPIs/tablero: qué medidas armar (cada una en bloque ```dax) y \
qué visual usar para cada una.

Nunca inventes columnas que no se ven: si falta información, decí qué falta. \
Cerrá siempre con una línea "Siguiente paso:" concreta."""

USER_PROMPT = "Resolvé lo que hay en esta captura de Power BI."


# ==========================================================================
# Dependencias con aviso claro
# ==========================================================================
def _abortar_falta_lib(nombre: str, paquete: str) -> None:
    print(f"Falta la librería {nombre}. Instalala con:  pip install {paquete}")
    sys.exit(1)


try:
    from PIL import ImageGrab
except ImportError:
    _abortar_falta_lib("pillow", "pillow")
try:
    from pynput import keyboard as pk
except ImportError:
    _abortar_falta_lib("pynput", "pynput")
try:
    import anthropic
except ImportError:
    _abortar_falta_lib("anthropic", "anthropic")

# Estos imports van DESPUÉS de los chequeos de dependencias de arriba a
# propósito: si falta `pynput` o `anthropic`, el script corta con un mensaje
# que dice qué instalar, en vez de reventar más abajo con un ImportError
# críptico. Mover estos imports al tope no cambiaría nada funcional, pero sí
# el orden en que el usuario ve el error.
import base64  # noqa: E402
import io  # noqa: E402
import tkinter as tk  # noqa: E402

# El puente con la app principal es opcional: si el paquete dxl está al lado
# (repo completo), cada respuesta va también a la bandeja compartida.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.abspath(__file__)), ".."))
    from dxl import asistente as _bandeja
except Exception:  # instalación suelta del overlay: sigue sin bandeja
    _bandeja = None


def log(msg: str) -> None:
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


# ==========================================================================
# Memoria de capturas previas
# ==========================================================================
class Memoria:
    def __init__(self) -> None:
        self._items: list[tuple[float, str]] = []  # (cuando, b64)

    def agregar(self, b64: str) -> None:
        if not MEMORIA_ACTIVADA:
            return
        self._depurar()
        self._items.append((time.time(), b64))
        self._items = self._items[-MEMORIA_MAX_CAPTURAS:]

    def vigentes(self) -> list[str]:
        self._depurar()
        return [b64 for _, b64 in self._items]

    def limpiar(self) -> int:
        n = len(self._items)
        self._items = []
        return n

    def _depurar(self) -> None:
        limite = time.time() - MEMORIA_MINUTOS_VIGENCIA * 60
        antes = len(self._items)
        self._items = [(t, b) for t, b in self._items if t >= limite]
        if antes and not self._items:
            log("Memoria: limpiada por antigüedad.")


MEMORIA = Memoria()


# ==========================================================================
# Captura
# ==========================================================================
def capturar_pantalla_completa() -> str | None:
    try:
        try:
            img = ImageGrab.grab(all_screens=True)
        except TypeError:
            img = ImageGrab.grab()
    except Exception as e:
        log(f"Error capturando la pantalla: {e}")
        return None
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def capturar_region() -> str | None:
    """Selector de rectángulo: ventana transparente sobre toda la pantalla."""
    seleccion = {}

    raiz = tk.Tk()
    raiz.attributes("-fullscreen", True)
    raiz.attributes("-alpha", 0.25)
    raiz.configure(bg="black")
    raiz.attributes("-topmost", True)
    lienzo = tk.Canvas(raiz, cursor="cross", bg="grey11")
    lienzo.pack(fill="both", expand=True)
    rect = [None]

    def inicio(ev):
        seleccion["x0"], seleccion["y0"] = ev.x_root, ev.y_root
        rect[0] = lienzo.create_rectangle(ev.x, ev.y, ev.x, ev.y,
                                          outline="#f2b441", width=2)

    def arrastre(ev):
        if rect[0]:
            x0 = seleccion["x0"] - raiz.winfo_rootx()
            y0 = seleccion["y0"] - raiz.winfo_rooty()
            lienzo.coords(rect[0], x0, y0, ev.x, ev.y)

    def fin(ev):
        seleccion["x1"], seleccion["y1"] = ev.x_root, ev.y_root
        raiz.destroy()

    lienzo.bind("<ButtonPress-1>", inicio)
    lienzo.bind("<B1-Motion>", arrastre)
    lienzo.bind("<ButtonRelease-1>", fin)
    raiz.bind("<Escape>", lambda e: raiz.destroy())
    raiz.mainloop()

    if "x1" not in seleccion:
        return None
    x0, x1 = sorted((seleccion["x0"], seleccion["x1"]))
    y0, y1 = sorted((seleccion["y0"], seleccion["y1"]))
    if x1 - x0 < 10 or y1 - y0 < 10:
        log("Región demasiado chica; cancelado.")
        return None
    try:
        img = ImageGrab.grab(bbox=(x0, y0, x1, y1))
    except Exception as e:
        log(f"Error capturando la región: {e}")
        return None
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ==========================================================================
# Llamada a Claude con fallback
# ==========================================================================
def _es_saturacion(exc: Exception) -> bool:
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 529)
    return isinstance(exc, anthropic.APIConnectionError)


def resolver(b64: str | None, texto: str | None, ventana) -> str | None:
    """Manda captura y/o texto a Claude, streameando a la ventana."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        ventana.agregar("\nFalta ANTHROPIC_API_KEY en el entorno.\n")
        return None
    client = anthropic.Anthropic(api_key=api_key)

    contenido: list[dict] = []
    previas = MEMORIA.vigentes() if b64 else []
    if previas:
        ventana.agregar(f"[ con {len(previas)} ejercicio(s) anterior(es) "
                        "en memoria ]\n")
        contenido.append({"type": "text", "text":
                          f"CONTEXTO: primero {len(previas)} captura(s) de "
                          "consultas anteriores ya resueltas, por si esta "
                          "se refiere a ellas. La ÚLTIMA imagen es la "
                          "consulta actual."})
        for p in previas:
            contenido.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/png", "data": p}})
    if b64:
        contenido.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/png", "data": b64}})
    contenido.append({"type": "text", "text": texto or USER_PROMPT})

    for i, modelo in enumerate(MODELOS):
        for intento in range(REINTENTOS_POR_MODELO + 1):
            try:
                partes: list[str] = []
                with client.messages.stream(
                        model=modelo, max_tokens=MAX_TOKENS,
                        system=SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": contenido}],
                ) as flujo:
                    for trozo in flujo.text_stream:
                        partes.append(trozo)
                        ventana.agregar(trozo)
                if b64:
                    MEMORIA.agregar(b64)
                return "".join(partes)
            except Exception as exc:
                if not _es_saturacion(exc):
                    ventana.agregar(f"\nError real ({modelo}): {exc}\n")
                    return None
                if intento < REINTENTOS_POR_MODELO:
                    espera = 3 * (intento + 1)
                    ventana.agregar(f"\n[ {modelo} saturado, reintento "
                                    f"{intento + 1}/{REINTENTOS_POR_MODELO} "
                                    f"en {espera}s... ]\n")
                    time.sleep(espera)
        if i < len(MODELOS) - 1:
            ventana.agregar(f"\n[ {modelo} sigue sin responder → probando "
                            f"con {MODELOS[i + 1]} ]\n")
    ventana.agregar("\nNingún modelo respondió. Probá de nuevo en un rato.\n")
    return None


# ==========================================================================
# Ventana flotante
# ==========================================================================
class Ventana:
    def __init__(self) -> None:
        self.raiz = tk.Tk()
        self.raiz.title("MV DAX Lab · Overlay")
        self.raiz.attributes("-topmost", True)
        self.raiz.geometry("520x420+40+40")
        self.raiz.configure(bg="#081527")
        self.texto = tk.Text(self.raiz, wrap="word", bg="#0c2137",
                             fg="#eaf1fb", insertbackground="#f2b441",
                             font=("Consolas", 10), relief="flat",
                             padx=10, pady=8)
        self.texto.pack(fill="both", expand=True)
        barra = tk.Frame(self.raiz, bg="#081527")
        barra.pack(fill="x")
        tk.Button(barra, text="Copiar DAX", command=self.copiar_dax,
                  bg="#f2b441", fg="#1c1305", relief="flat",
                  font=("Segoe UI", 9, "bold")).pack(side="left",
                                                     padx=6, pady=5)
        tk.Button(barra, text="Cerrar (Esc)", command=self.raiz.destroy,
                  bg="#1d3149", fg="#eaf1fb",
                  relief="flat").pack(side="right", padx=6, pady=5)
        self.raiz.bind("<Escape>", lambda e: self.raiz.destroy())

    def agregar(self, trozo: str) -> None:
        def _hacer():
            self.texto.insert("end", trozo)
            self.texto.see("end")
        try:
            self.raiz.after(0, _hacer)
        except tk.TclError:
            pass

    def copiar_dax(self) -> None:
        contenido = self.texto.get("1.0", "end")
        import re
        bloques = re.findall(r"```(?:dax|DAX)?\s*\n(.*?)```",
                             contenido, re.DOTALL)
        elegido = ("\n\n".join(b.strip() for b in bloques)
                   if bloques else contenido.strip())
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(elegido)


def ventana_consulta() -> str | None:
    """Ctrl+F9: consulta escrita, sin captura."""
    resultado = {}
    raiz = tk.Tk()
    raiz.title("MV DAX Lab · Consulta escrita")
    raiz.attributes("-topmost", True)
    raiz.geometry("560x220+60+60")
    raiz.configure(bg="#081527")
    tk.Label(raiz, text="¿Qué necesitás de Power BI / DAX / M / Fabric?",
             bg="#081527", fg="#f2b441",
             font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=6)
    caja = tk.Text(raiz, height=6, wrap="word", bg="#0c2137", fg="#eaf1fb",
                   insertbackground="#f2b441", font=("Segoe UI", 10),
                   relief="flat", padx=8, pady=6)
    caja.pack(fill="both", expand=True, padx=10)
    caja.focus_set()

    def enviar(_ev=None):
        resultado["texto"] = caja.get("1.0", "end").strip()
        raiz.destroy()

    tk.Button(raiz, text="Resolver (Ctrl+Enter)", command=enviar,
              bg="#f2b441", fg="#1c1305", relief="flat",
              font=("Segoe UI", 9, "bold")).pack(pady=6)
    raiz.bind("<Control-Return>", enviar)
    raiz.bind("<Escape>", lambda e: raiz.destroy())
    raiz.mainloop()
    return resultado.get("texto") or None


# ==========================================================================
# Orquestación
# ==========================================================================
_OCUPADO = threading.Lock()


def _procesar(b64: str | None, texto: str | None, origen: str) -> None:
    if not _OCUPADO.acquire(blocking=False):
        log("Ya hay una consulta en curso.")
        return
    try:
        ventana = Ventana()

        def trabajo():
            respuesta = resolver(b64, texto, ventana)
            if respuesta and _bandeja is not None:
                try:
                    _bandeja.depositar(texto or "(captura de pantalla)",
                                       respuesta, origen=origen)
                    ventana.agregar("\n\n[ Enviado a la bandeja de MV DAX "
                                    "Lab: aplicalo desde la pestaña "
                                    "«Asistente de pantalla» ]\n")
                except Exception as e:
                    log(f"No se pudo depositar en la bandeja: {e}")

        threading.Thread(target=trabajo, daemon=True).start()
        ventana.raiz.mainloop()
    finally:
        _OCUPADO.release()


def al_f9() -> None:
    log("F9 → captura de pantalla completa")
    b64 = capturar_pantalla_completa()
    if b64:
        _procesar(b64, None, "captura")


def al_shift_f9() -> None:
    log("Shift+F9 → selección de región")
    b64 = capturar_region()
    if b64:
        _procesar(b64, None, "captura")


def al_ctrl_f9() -> None:
    log("Ctrl+F9 → consulta escrita")
    texto = ventana_consulta()
    if texto:
        _procesar(None, texto, "consulta")


def al_limpiar_memoria() -> None:
    n = MEMORIA.limpiar()
    log(f"Memoria limpiada ({n} captura(s)).")


def principal() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        try:
            clave = input("Pegá tu ANTHROPIC_API_KEY: ").strip()
        except EOFError:
            clave = ""
        if clave:
            os.environ["ANTHROPIC_API_KEY"] = clave
        else:
            print("Sin API key no puedo resolver. Salgo.")
            return

    log("MV DAX Lab Overlay corriendo.")
    log("  F9 = pantalla completa · Shift+F9 = región · "
        "Ctrl+F9 = consulta escrita · Ctrl+Shift+M = limpiar memoria")
    with pk.GlobalHotKeys({
        "<f9>": al_f9,
        "<shift>+<f9>": al_shift_f9,
        "<ctrl>+<f9>": al_ctrl_f9,
        "<ctrl>+<shift>+m": al_limpiar_memoria,
    }) as atajos:
        atajos.join()


if __name__ == "__main__":
    principal()
