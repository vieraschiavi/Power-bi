#!/usr/bin/env python3
# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Servidor MCP propio (stdio, sin dependencias).

Expone el motor de la plataforma a cualquier agente de IA que hable MCP
(Claude Code, Claude Desktop, VS Code): cargar un modelo, resumirlo,
analizarlo, generar y explicar DAX, agregar medidas y exportar a .pbit/PBIP.

Complementa —no reemplaza— a los MCP oficiales de Microsoft:
  · remoto:  https://api.fabric.microsoft.com/v1/mcp/powerbi  (Entra ID)
  · local:   powerbi-modeling-mcp (contra Power BI Desktop, Windows)
Este servidor trabaja sobre ARCHIVOS (.pbit/.bim/PBIP), así que corre en
cualquier sistema y no necesita Desktop ni credenciales.

Protocolo: JSON-RPC 2.0 por stdio, mensajes delimitados por línea.
Uso directo:  python daxlingo/mcp/servidor.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dxl import MARCA, __version__  # noqa: E402
from dxl import analizador, catalogo, explicador, generador  # noqa: E402
from dxl import licencia  # noqa: E402
from dxl import modelo as modmod  # noqa: E402
from dxl import tablero, transformador  # noqa: E402
from dxl.i18n import IDIOMA_DEFECTO, t as traducir  # noqa: E402

# Estado del servidor: el modelo cargado en la sesión.
ESTADO: dict = {"cargado": None}

HERRAMIENTAS = [
    {
        "name": "cargar_modelo",
        "description": "Carga un archivo de Power BI (.pbit, .pbix, .bim o "
                       "carpeta/archivo PBIP) y lo deja activo en la sesión. "
                       "Devuelve el resumen del catálogo.",
        "inputSchema": {"type": "object",
                        "properties": {"ruta": {"type": "string"}},
                        "required": ["ruta"]},
    },
    {
        "name": "resumen_modelo",
        "description": "Resumen del modelo activo: tablas, columnas, medidas "
                       "y relaciones.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "analizar_modelo",
        "description": "Corre el analizador de buenas prácticas sobre el "
                       "modelo activo y devuelve los hallazgos y el puntaje "
                       "de salud.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "generar_dax",
        "description": "Genera una medida DAX desde un pedido en lenguaje "
                       "natural, validada contra el modelo activo. "
                       "aplicar=true la agrega al modelo. Requiere licencia "
                       "vigente (edición demo vencida: bloqueado).",
        "inputSchema": {"type": "object",
                        "properties": {"pedido": {"type": "string"},
                                       "aplicar": {"type": "boolean"},
                                       "idioma": {"type": "string",
                                                  "enum": ["es", "en", "pt"]}},
                        "required": ["pedido"]},
    },
    {
        "name": "explicar_dax",
        "description": "Explica una expresión DAX: qué calcula, funciones, "
                       "referencias y nivel.",
        "inputSchema": {"type": "object",
                        "properties": {"dax": {"type": "string"},
                                       "idioma": {"type": "string",
                                                  "enum": ["es", "en", "pt"]}},
                        "required": ["dax"]},
    },
    {
        "name": "exportar",
        "description": "Exporta el modelo activo (con tablero automático) a "
                       ".pbit o PBIP en la ruta indicada. No pisa un archivo "
                       "existente salvo sobrescribir=true. Requiere licencia "
                       "vigente.",
        "inputSchema": {"type": "object",
                        "properties": {"destino": {"type": "string"},
                                       "formato": {"type": "string",
                                                   "enum": ["pbit", "pbip"]},
                                       "sobrescribir": {"type": "boolean"},
                                       "idioma": {"type": "string",
                                                  "enum": ["es", "en", "pt"]}},
                        "required": ["destino"]},
    },
]


def _texto(contenido: str) -> dict:
    return {"content": [{"type": "text", "text": contenido}]}


def _cat() -> catalogo.Catalogo:
    cargado = ESTADO.get("cargado")
    if not cargado or not cargado.get("modelo"):
        raise ValueError("No hay modelo cargado: usá cargar_modelo primero.")
    return catalogo.Catalogo.desde_modelo(cargado["modelo"])


def ejecutar_herramienta(nombre: str, args: dict) -> dict:
    if nombre == "cargar_modelo":
        cargado = modmod.cargar(args["ruta"])
        ESTADO["cargado"] = cargado
        if cargado["modelo"]:
            cat = catalogo.Catalogo.desde_modelo(cargado["modelo"])
        elif cargado["layout"]:
            cat = catalogo.Catalogo.desde_layout(cargado["layout"])
        else:
            return _texto("No se pudo leer el archivo: "
                          + "; ".join(cargado["advertencias"]))
        salida = {"formato": cargado["formato"], "resumen": cat.resumen(),
                  "advertencias": cargado["advertencias"]}
        return _texto(json.dumps(salida, ensure_ascii=False, indent=2))

    if nombre == "resumen_modelo":
        cat = _cat()
        detalle = {"resumen": cat.resumen(),
                   "tablas": [{"nombre": t["nombre"],
                               "columnas": [c["nombre"] for c in t["columnas"]],
                               "medidas": [m["nombre"] for m in t["medidas"]]}
                              for t in cat.tablas if not t["interna"]],
                   "relaciones": cat.relaciones}
        return _texto(json.dumps(detalle, ensure_ascii=False, indent=2))

    if nombre == "analizar_modelo":
        cat = _cat()
        hallazgos = analizador.analizar(cat)
        salida = {"puntaje_salud": analizador.puntaje(hallazgos),
                  "hallazgos": hallazgos}
        return _texto(json.dumps(salida, ensure_ascii=False, indent=2))

    if nombre == "generar_dax":
        # Mismo criterio que `app.py:gate("generar")`: la pestaña entera de
        # generación DAX está detrás de la licencia, no solo el botón de
        # agregar la medida al modelo.
        idioma_pedido = args.get("idioma", IDIOMA_DEFECTO)
        if not licencia.evaluar().permite("generar"):
            raise ValueError(traducir("lic_bloqueado", idioma_pedido))
        cat = _cat()
        r = generador.generar(args["pedido"], cat, idioma=idioma_pedido)
        if r["ok"] and args.get("aplicar"):
            nuevo, cambios = transformador.agregar_medida(
                ESTADO["cargado"]["modelo"], r["nombre"], r["dax"],
                formato=r["formato"], descripcion=r["explicacion"],
                idioma=idioma_pedido)
            ESTADO["cargado"]["modelo"] = nuevo
            r["aplicado"] = cambios
        return _texto(json.dumps(r, ensure_ascii=False, indent=2))

    if nombre == "explicar_dax":
        cat = None
        try:
            cat = _cat()
        except ValueError:
            pass
        # El agente puede pedir el idioma; si no, el del producto.
        r = explicador.explicar(args["dax"], cat,
                                idioma=args.get("idioma", IDIOMA_DEFECTO))
        return _texto(json.dumps(r, ensure_ascii=False, indent=2))

    if nombre == "exportar":
        idioma_pedido = args.get("idioma", IDIOMA_DEFECTO)
        if not licencia.evaluar().permite("exportar"):
            raise ValueError(traducir("lic_bloqueado", idioma_pedido))
        cargado = ESTADO.get("cargado")
        if not cargado or not cargado.get("modelo"):
            raise ValueError("No hay modelo cargado.")
        cat = _cat()
        layout = cargado.get("layout")
        if layout is None and cat.medidas():
            layout = tablero.disenar_auto(cat, titulo=cat.nombre or "Tablero")
        destino = Path(args["destino"])
        # Un cliente MCP comprometido o con un prompt inyectado no tiene por
        # qué poder pisar un archivo cualquiera del disco (p. ej. un
        # ~/.bashrc) solo con pedirle a `exportar` esa ruta como destino. La
        # carga de modelos SÍ necesita poder apuntar a cualquier .pbit del
        # usuario —es de solo lectura y modelo.cargar() ya rechaza lo que no
        # sea un formato Power BI reconocido—, pero escribir es distinto:
        # por defecto no se pisa un archivo que ya existe.
        if destino.exists() and not args.get("sobrescribir"):
            raise ValueError(
                f"Ya existe un archivo en «{destino}». Pasá "
                "sobrescribir=true si es a propósito.")
        if args.get("formato", "pbit") == "pbip":
            ruta = modmod.exportar_pbip(cargado["modelo"], layout,
                                        destino.parent, destino.stem)
        else:
            ruta = modmod.exportar_pbit(
                cargado["modelo"], layout, destino,
                # Igual que en la app: sin el DataMashup el modelo exportado
                # pierde las consultas de Power Query del archivo original.
                datamashup=cargado.get("datamashup"))
        return _texto(f"Exportado: {ruta}")

    raise ValueError(f"Herramienta desconocida: {nombre}")


# ==========================================================================
# JSON-RPC / MCP
# ==========================================================================
def atender(peticion: dict) -> dict | None:
    """Atiende un mensaje JSON-RPC. Devuelve la respuesta o None (notif.)."""
    metodo = peticion.get("method", "")
    pid = peticion.get("id")

    if metodo == "initialize":
        resultado = {
            "protocolVersion": peticion.get("params", {}).get(
                "protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": MARCA, "version": __version__},
        }
    elif metodo == "tools/list":
        resultado = {"tools": HERRAMIENTAS}
    elif metodo == "tools/call":
        params = peticion.get("params", {})
        try:
            resultado = ejecutar_herramienta(params.get("name", ""),
                                             params.get("arguments", {}))
        except Exception as exc:  # el agente recibe el error como contenido
            resultado = {"content": [{"type": "text",
                                      "text": f"Error: {exc}"}],
                         "isError": True}
    elif metodo == "ping":
        resultado = {}
    elif metodo.startswith("notifications/") or pid is None:
        return None
    else:
        return {"jsonrpc": "2.0", "id": pid,
                "error": {"code": -32601, "message": f"Método no soportado: "
                                                     f"{metodo}"}}
    return {"jsonrpc": "2.0", "id": pid, "result": resultado}


def principal() -> None:
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            peticion = json.loads(linea)
        except ValueError:
            continue
        respuesta = atender(peticion)
        if respuesta is not None:
            sys.stdout.write(json.dumps(respuesta, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    principal()
