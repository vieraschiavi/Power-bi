"""
MV DAX Lab · Puente entre el DAX Overlay (capturas de pantalla) y la app.

El overlay corre como proceso aparte en el escritorio (F9 captura toda la
pantalla, Shift+F9 un rectángulo, Ctrl+F9 abre una consulta escrita) y manda
la pregunta a Claude. Este módulo es el contrato entre ambos mundos:

  · El overlay DEJA cada resultado en una bandeja (archivos JSON en una
    carpeta del usuario). Sin sockets ni servidores: dos procesos, un
    directorio — funciona igual en Windows, Linux o Mac.
  · La app principal (pestaña «Asistente de pantalla») LEE la bandeja,
    muestra la explicación paso a paso y, si la respuesta trae DAX,
    la EJECUTA sobre el modelo cargado: agrega la medida o columna
    calculada, corre la transformación, arma el tablero.

También vive acá el parser respuesta-IA → acción ejecutable, que es lógica
pura y por eso testeable sin pantalla ni API.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path


def carpeta_bandeja() -> Path:
    """Carpeta compartida overlay ↔ app. Configurable por entorno."""
    base = os.environ.get("MVDAXLAB_BANDEJA", "")
    ruta = Path(base) if base else Path.home() / ".mvdaxlab" / "bandeja"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


# ==========================================================================
# Escritura (la usa el overlay)
# ==========================================================================
def depositar(pregunta: str, respuesta: str, origen: str = "overlay",
              carpeta: Path | None = None) -> Path:
    """Deja un resultado en la bandeja para que la app lo levante."""
    carpeta = carpeta or carpeta_bandeja()
    item = {
        "id": uuid.uuid4().hex[:12],
        "cuando": time.strftime("%Y-%m-%d %H:%M:%S"),
        "origen": origen,           # 'overlay' | 'captura' | 'consulta'
        "pregunta": pregunta,
        "respuesta": respuesta,
        "acciones": extraer_acciones(respuesta),
        "estado": "pendiente",
    }
    destino = carpeta / f"{int(time.time())}_{item['id']}.json"
    destino.write_text(json.dumps(item, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    return destino


# ==========================================================================
# Lectura (la usa la app)
# ==========================================================================
def pendientes(carpeta: Path | None = None) -> list[dict]:
    carpeta = carpeta or carpeta_bandeja()
    items = []
    for archivo in sorted(carpeta.glob("*.json")):
        try:
            item = json.loads(archivo.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        item["_archivo"] = str(archivo)
        items.append(item)
    return items


def marcar(archivo: str | Path, estado: str) -> None:
    """estado: 'aplicado' | 'descartado'. Se conserva como historial."""
    archivo = Path(archivo)
    if not archivo.exists():
        return
    item = json.loads(archivo.read_text(encoding="utf-8"))
    item["estado"] = estado
    archivo.write_text(json.dumps(item, indent=2, ensure_ascii=False),
                       encoding="utf-8")


def limpiar(carpeta: Path | None = None, solo_resueltos: bool = True) -> int:
    carpeta = carpeta or carpeta_bandeja()
    n = 0
    for archivo in carpeta.glob("*.json"):
        try:
            item = json.loads(archivo.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            item = {}
        if not solo_resueltos or item.get("estado") != "pendiente":
            archivo.unlink(missing_ok=True)
            n += 1
    return n


# ==========================================================================
# Parser: respuesta de la IA → acciones ejecutables sobre el modelo
# ==========================================================================
RE_BLOQUE = re.compile(r"```(?:dax|DAX)?\s*\n(.*?)```", re.DOTALL)
RE_DEF_MEDIDA = re.compile(
    r"^\s*(?:MEASURE\s+'?[\w ]+'?\s*)?\[?([^\[\]=\n]{1,80}?)\]?\s*[:=]=?\s*(.+)$",
    re.DOTALL)


def extraer_acciones(respuesta: str) -> list[dict]:
    """
    Busca en la respuesta de la IA bloques de código DAX y los convierte en
    acciones aplicables: {'tipo': 'medida'|'columna_calculada'|'dax_suelto',
    'nombre', 'dax'}. Conservador a propósito: si el bloque no se entiende,
    va como 'dax_suelto' para que el usuario decida.
    """
    acciones = []
    texto = respuesta or ""
    for bloque in RE_BLOQUE.findall(texto):
        bloque = bloque.strip()
        if not bloque:
            continue
        # ¿Columna calculada? La IA suele anunciarla en el texto cercano.
        es_columna = bool(re.search(r"columna calculada", texto, re.IGNORECASE)
                          and len(RE_BLOQUE.findall(texto)) == 1)
        m = RE_DEF_MEDIDA.match(bloque)
        if m and "\n" not in m.group(1) and not bloque.upper().startswith(
                ("EVALUATE", "DEFINE", "VAR ", "RETURN")):
            nombre = m.group(1).strip().strip("'\"")
            dax = m.group(2).strip()
            acciones.append({
                "tipo": "columna_calculada" if es_columna else "medida",
                "nombre": nombre,
                "dax": dax,
            })
        else:
            acciones.append({"tipo": "dax_suelto", "nombre": "",
                             "dax": bloque})
    return acciones


def aplicar_accion(modelo: dict, accion: dict, tabla: str = "") -> tuple[dict, list[str]]:
    """
    Ejecuta una acción de la bandeja sobre el modelo TMSL cargado.
    Devuelve (modelo_nuevo, cambios). Lanza ValueError si no es aplicable.
    """
    from . import transformador

    tipo = accion.get("tipo")
    if tipo == "medida":
        return transformador.agregar_medida(
            modelo, accion["nombre"], accion["dax"],
            descripcion="Generada por el Asistente de pantalla (DAX Overlay)",
            tabla=tabla)
    if tipo == "columna_calculada":
        return agregar_columna_calculada(
            modelo, tabla, accion["nombre"], accion["dax"])
    raise ValueError(
        "Este bloque DAX no es una medida ni una columna calculada con "
        "nombre; copialo a mano donde corresponda.")


def agregar_columna_calculada(modelo: dict, tabla: str, nombre: str,
                              dax: str) -> tuple[dict, list[str]]:
    """Agrega una columna calculada a la tabla indicada."""
    import copy

    from .catalogo import _norm
    from .modelo import expr_lineas

    if not tabla:
        raise ValueError("Indicá en qué tabla va la columna calculada.")
    modelo = copy.deepcopy(modelo)
    tablas = modelo.get("model", modelo).get("tables", [])
    destino = next((t for t in tablas
                    if _norm(t.get("name", "")) == _norm(tabla)), None)
    if destino is None:
        raise ValueError(f"La tabla «{tabla}» no existe en el modelo.")
    if any(_norm(c.get("name", "")) == _norm(nombre)
           for c in destino.get("columns", [])):
        raise ValueError(f"Ya existe la columna {tabla}[{nombre}].")
    destino.setdefault("columns", []).append({
        "name": nombre,
        "dataType": "double",
        "type": "calculated",
        "isDataTypeInferred": True,
        "expression": expr_lineas(dax),
        "summarizeBy": "none",
    })
    return modelo, [f"Columna calculada {tabla}[{nombre}] agregada"]
