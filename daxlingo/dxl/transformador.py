"""
MV DAX Lab · Transformaciones seguras del modelo.

Cada transformación recibe el TMSL, devuelve una COPIA modificada y la lista
de cambios aplicados — nunca muta el original ni toca el archivo de entrada.
Son los «arreglos automáticos» de las reglas del analizador, más operaciones
de edición (agregar medida, renombrar con propagación).
"""
from __future__ import annotations

import copy
import re

from .catalogo import Catalogo, _norm
from .modelo import expr_lineas, expr_texto


def _tablas(modelo: dict) -> list[dict]:
    return modelo.get("model", modelo).get("tables", [])


def _medidas(modelo: dict):
    for t in _tablas(modelo):
        for m in t.get("measures", []):
            yield t, m


# ==========================================================================
def aplicar_divide(modelo: dict) -> tuple[dict, list[str]]:
    """
    Reemplaza divisiones «a / b» simples por DIVIDE(a, b) en las medidas.
    Solo convierte los casos inequívocos (operandos simples: referencia,
    número o función cerrada); lo ambiguo se deja y se informa.
    """
    modelo = copy.deepcopy(modelo)
    cambios = []
    # Operandos que se convierten sin ambigüedad: referencia, número, función
    # con un nivel de anidado, o grupo entre paréntesis con un nivel adentro.
    operando = (r"(?:\((?:[^()]+|\([^()]*\))*\)"
                r"|'[^']+'\[[^\[\]]+\]|[A-Za-z_]\w*\[[^\[\]]+\]|\[[^\[\]]+\]"
                r"|\b[A-Z][A-Z0-9]*\s*\((?:[^()]+|\([^()]*\))*\)"
                r"|\d+(?:\.\d+)?)")
    patron = re.compile(f"({operando})\\s*/\\s*({operando})")
    for t, m in _medidas(modelo):
        expr = expr_texto(m.get("expression"))
        nuevo, n = patron.subn(r"DIVIDE ( \1, \2 )", expr)
        if n:
            m["expression"] = expr_lineas(nuevo)
            cambios.append(f"[{m['name']}]: {n} división(es) «/» → DIVIDE")
    return modelo, cambios


def asignar_formatos(modelo: dict) -> tuple[dict, list[str]]:
    """Asigna formatString a las medidas que no lo tienen, por heurística."""
    modelo = copy.deepcopy(modelo)
    cambios = []
    for t, m in _medidas(modelo):
        if m.get("formatString"):
            continue
        nombre = _norm(m.get("name", ""))
        expr = expr_texto(m.get("expression")).upper()
        if "%" in nombre or "porcentaje" in nombre or "margen" in nombre \
                or "tasa" in nombre or ("DIVIDE" in expr and "SUM" in expr
                                        and "ALLSELECTED" in expr):
            formato = "0.0 %"
        elif "COUNTROWS" in expr or "DISTINCTCOUNT" in expr \
                or "COUNT" in expr or "RANKX" in expr:
            formato = "#,0"
        elif "promedio" in nombre or "media" in nombre or "precio" in nombre \
                or "ticket" in nombre:
            formato = "#,0.00"
        else:
            formato = "#,0"
        m["formatString"] = formato
        cambios.append(f"[{m['name']}]: formato → {formato}")
    return modelo, cambios


def ocultar_claves(modelo: dict) -> tuple[dict, list[str]]:
    """Oculta las columnas que son lado «muchos» de una relación."""
    modelo = copy.deepcopy(modelo)
    cambios = []
    m = modelo.get("model", modelo)
    claves = {(_norm(r.get("fromTable", "")), _norm(r.get("fromColumn", "")))
              for r in m.get("relationships", [])}
    for t in _tablas(modelo):
        for c in t.get("columns", []):
            if (_norm(t.get("name", "")), _norm(c.get("name", ""))) in claves \
                    and not c.get("isHidden"):
                c["isHidden"] = True
                cambios.append(f"{t['name']}[{c['name']}]: oculta (clave de "
                               "relación)")
    return modelo, cambios


def crear_tabla_medidas(modelo: dict,
                        nombre: str = "_Medidas") -> tuple[dict, list[str]]:
    """
    Mueve todas las medidas a una tabla de medidas dedicada (la crea si no
    existe). El panel de campos queda con el modelo a un lado y los cálculos
    al otro.
    """
    modelo = copy.deepcopy(modelo)
    cambios = []
    tablas = _tablas(modelo)
    destino = next((t for t in tablas if t.get("name") == nombre), None)
    if destino is None:
        destino = {
            "name": nombre,
            "columns": [{
                "name": "_", "dataType": "string", "isHidden": True,
                "sourceColumn": "_", "summarizeBy": "none",
                "annotations": [{"name": "SummarizationSetBy",
                                 "value": "Automatic"}],
            }],
            "partitions": [{
                "name": nombre, "mode": "import",
                "source": {"type": "m", "expression": [
                    "let", '    Origen = #table({"_"}, {{""}})',
                    "in", "    Origen"]},
            }],
            "measures": [],
        }
        tablas.append(destino)
        cambios.append(f"Tabla de medidas «{nombre}» creada")
    destino.setdefault("measures", [])
    for t in tablas:
        if t is destino:
            continue
        movidas = t.pop("measures", [])
        if movidas:
            destino["measures"].extend(movidas)
            cambios.append(f"{len(movidas)} medida(s) movida(s) desde "
                           f"«{t['name']}»")
    return modelo, cambios


def agregar_medida(modelo: dict, nombre: str, dax: str, formato: str = "",
                   descripcion: str = "", tabla: str = "",
                   carpeta: str = "") -> tuple[dict, list[str]]:
    """
    Agrega una medida al modelo. Si no se indica tabla, usa la tabla de
    medidas (creándola si hace falta) o la primera con medidas.
    """
    modelo = copy.deepcopy(modelo)
    tablas = _tablas(modelo)
    if not tablas:
        raise ValueError("El modelo no tiene tablas.")

    for _, m in _medidas(modelo):
        if _norm(m.get("name", "")) == _norm(nombre):
            raise ValueError(f"Ya existe una medida llamada [{nombre}].")

    destino = None
    if tabla:
        destino = next((t for t in tablas
                        if _norm(t.get("name", "")) == _norm(tabla)), None)
        if destino is None:
            raise ValueError(f"La tabla «{tabla}» no existe.")
    if destino is None:
        destino = next((t for t in tablas
                        if t.get("name", "").lstrip("_").lower()
                        in ("medidas", "measures")), None)
    if destino is None:
        destino = next((t for t in tablas if t.get("measures")), tablas[0])

    medida = {"name": nombre, "expression": expr_lineas(dax)}
    if formato:
        medida["formatString"] = formato
    if descripcion:
        medida["description"] = descripcion
    if carpeta:
        medida["displayFolder"] = carpeta
    destino.setdefault("measures", []).append(medida)
    return modelo, [f"Medida [{nombre}] agregada en «{destino['name']}»"]


def renombrar_medida(modelo: dict, actual: str,
                     nuevo: str) -> tuple[dict, list[str]]:
    """Renombra una medida y propaga la referencia [actual] en el resto."""
    modelo = copy.deepcopy(modelo)
    cambios = []
    encontrada = False
    for t, m in _medidas(modelo):
        if m.get("name") == actual:
            m["name"] = nuevo
            encontrada = True
            cambios.append(f"[{actual}] → [{nuevo}]")
            break
    if not encontrada:
        raise ValueError(f"No existe la medida [{actual}].")
    patron = re.compile(r"\[" + re.escape(actual) + r"\]")
    for t, m in _medidas(modelo):
        expr = expr_texto(m.get("expression"))
        nuevo_expr, n = patron.subn(f"[{nuevo}]", expr)
        if n:
            m["expression"] = expr_lineas(nuevo_expr)
            cambios.append(f"[{m['name']}]: {n} referencia(s) actualizada(s)")
    return modelo, cambios


def eliminar_medida(modelo: dict, nombre: str) -> tuple[dict, list[str]]:
    """Elimina una medida — se niega si otra medida la referencia."""
    modelo = copy.deepcopy(modelo)
    patron = re.compile(r"\[" + re.escape(nombre) + r"\]")
    usada_por = [m["name"] for _, m in _medidas(modelo)
                 if m.get("name") != nombre
                 and patron.search(expr_texto(m.get("expression")))]
    if usada_por:
        raise ValueError(
            f"[{nombre}] está referenciada por: "
            + ", ".join(f"[{u}]" for u in usada_por)
            + ". Actualizá esas medidas antes de eliminarla.")
    for t in _tablas(modelo):
        antes = len(t.get("measures", []))
        t["measures"] = [m for m in t.get("measures", [])
                         if m.get("name") != nombre]
        if len(t["measures"]) < antes:
            return modelo, [f"Medida [{nombre}] eliminada de «{t['name']}»"]
    raise ValueError(f"No existe la medida [{nombre}].")


# ==========================================================================
def aplicar_arreglos(modelo: dict, hallazgos: list[dict]) -> tuple[dict, list[str]]:
    """
    Aplica en cadena todos los arreglos automáticos que el analizador marcó
    (`auto=True`), en orden seguro. Devuelve el modelo nuevo y el log.
    """
    cambios: list[str] = []
    reglas = {h["regla"].split(" ·")[0] for h in hallazgos if h.get("auto")}
    if "R01" in reglas:
        modelo, c = aplicar_divide(modelo)
        cambios += c
    if "R02" in reglas:
        modelo, c = asignar_formatos(modelo)
        cambios += c
    if "R08" in reglas:
        modelo, c = ocultar_claves(modelo)
        cambios += c
    if "R15" in reglas:
        modelo, c = crear_tabla_medidas(modelo)
        cambios += c
    return modelo, cambios
