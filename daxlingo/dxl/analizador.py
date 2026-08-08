"""
MV DAX Lab · Analizador de buenas prácticas del modelo.

Reglas al estilo Best Practice Analyzer (Tabular Editor / Bravo), elegidas por
impacto real: rendimiento, corrección de resultados y mantenibilidad. Cada
hallazgo dice QUÉ objeto, POR QUÉ importa y CÓMO se arregla; las marcadas
`auto=True` las aplica `transformador.py` sin intervención manual.
"""
from __future__ import annotations

import re

from .catalogo import Catalogo, _norm

SEVERIDADES = ("alta", "media", "baja")


def _h(regla: str, severidad: str, objeto: str, detalle: str,
       arreglo: str, auto: bool = False) -> dict:
    return {"regla": regla, "severidad": severidad, "objeto": objeto,
            "detalle": detalle, "arreglo": arreglo, "auto": auto}


# --------------------------------------------------------------------------
RE_DIVISION = re.compile(r"[\w\)\]]\s*/\s*[\w\(\[']")
RE_IFERROR = re.compile(r"\bIFERROR\s*\(", re.IGNORECASE)
RE_FILTER_TABLA = re.compile(r"\bFILTER\s*\(\s*'?([A-Za-z_][\w ]*)'?\s*,",
                             re.IGNORECASE)
RE_VALUES_ESCALAR = re.compile(r"\bIF\s*\(\s*HASONEVALUE", re.IGNORECASE)


def analizar(cat: Catalogo) -> list[dict]:
    """Corre todas las reglas y devuelve los hallazgos ordenados por severidad."""
    hallazgos: list[dict] = []
    if cat.parcial:
        hallazgos.append(_h(
            "R00 · Catálogo parcial", "media", "(modelo)",
            "Este catálogo salió del layout de un .pbix: solo se ve lo que los "
            "visuales usan, no el modelo completo.",
            "Exportá el archivo como .pbit o PBIP desde Power BI Desktop para "
            "el análisis completo."))
        return hallazgos

    hallazgos += _reglas_medidas(cat)
    hallazgos += _reglas_columnas(cat)
    hallazgos += _reglas_relaciones(cat)
    hallazgos += _reglas_modelo(cat)

    orden = {s: i for i, s in enumerate(SEVERIDADES)}
    hallazgos.sort(key=lambda x: (orden.get(x["severidad"], 9), x["regla"]))
    return hallazgos


# --------------------------------------------------------------------------
def _reglas_medidas(cat: Catalogo) -> list[dict]:
    out = []
    vistas: dict[str, str] = {}
    for m in cat.medidas():
        nombre, expr = m["nombre"], m["expresion"]
        objeto = f"[{nombre}]"

        if RE_DIVISION.search(expr):
            out.append(_h(
                "R01 · División con «/»", "alta", objeto,
                "Una división con «/» revienta con dividendo 0 o BLANK y "
                "muestra infinito o error en el visual.",
                "Usar DIVIDE(numerador, denominador): devuelve BLANK ante "
                "cero, sin costo extra.", auto=True))

        if not m["formato"]:
            out.append(_h(
                "R02 · Medida sin formato", "media", objeto,
                "Sin formatString, cada visual muestra el número como quiere: "
                "decimales de más, sin separador de miles, porcentajes crudos.",
                "Asignar un formato explícito (#,0 · #,0.00 · 0.0 %).",
                auto=True))

        if RE_IFERROR.search(expr):
            out.append(_h(
                "R03 · IFERROR en medida", "media", objeto,
                "IFERROR fuerza al motor a evaluar fila por fila esperando el "
                "error: caro y esconde problemas de datos.",
                "Prevenir el error (DIVIDE, buscar el caso borde) en vez de "
                "taparlo."))

        mfil = RE_FILTER_TABLA.search(expr)
        if mfil and cat.tabla(mfil.group(1)):
            out.append(_h(
                "R04 · FILTER sobre tabla entera", "media", objeto,
                f"FILTER('{mfil.group(1)}', …) materializa la tabla completa "
                "dentro de CALCULATE cuando un filtro de columna alcanza.",
                "Filtrar la columna (Tabla[Col] = valor) o usar "
                "KEEPFILTERS(VALUES(Tabla[Col]))."))

        clave = re.sub(r"\s+", " ", expr).strip().lower()
        if clave and clave in vistas:
            out.append(_h(
                "R05 · Medida duplicada", "baja", objeto,
                f"Tiene exactamente la misma expresión que [{vistas[clave]}].",
                "Dejar una sola y referenciarla desde la otra si hace falta "
                "el alias."))
        elif clave:
            vistas[clave] = nombre

        if nombre != nombre.strip():
            out.append(_h(
                "R06 · Espacios en el nombre", "baja", objeto,
                "El nombre empieza o termina con espacios: invisible en el "
                "panel y fuente de referencias rotas.",
                "Renombrar sin espacios en los bordes."))
    return out


def _reglas_columnas(cat: Catalogo) -> list[dict]:
    out = []
    lados_muchos = {(_norm(r["desde_tabla"]), _norm(r["desde_col"]))
                    for r in cat.relaciones}
    for t in cat.tablas:
        if t["interna"]:
            continue
        for c in t["columnas"]:
            objeto = f"{t['nombre']}[{c['nombre']}]"
            if c["calculada"]:
                out.append(_h(
                    "R07 · Columna calculada", "media", objeto,
                    "Las columnas calculadas se materializan en el modelo y "
                    "no se comprimen tan bien como las nativas; casi siempre "
                    "hay una versión en Power Query o una medida.",
                    "Mover el cálculo a Power Query (mejor compresión) o "
                    "convertirlo en medida si es agregable."))
            es_clave = ((_norm(t["nombre"]), _norm(c["nombre"])) in lados_muchos
                        or re.search(r"(^id[_ ]|[_ ]id$|^id$)",
                                     _norm(c["nombre"])))
            if es_clave and not c["oculta"] and (
                    (_norm(t["nombre"]), _norm(c["nombre"])) in lados_muchos):
                out.append(_h(
                    "R08 · Clave foránea visible", "baja", objeto,
                    "Las columnas que solo existen para relacionar tablas "
                    "confunden en el panel de campos y tientan a sumarlas.",
                    "Ocultarla (isHidden). El filtro sigue funcionando igual.",
                    auto=True))
    return out


def _reglas_relaciones(cat: Catalogo) -> list[dict]:
    out = []
    for r in cat.relaciones:
        objeto = (f"{r['desde_tabla']}[{r['desde_col']}] → "
                  f"{r['hacia_tabla']}[{r['hacia_col']}]")
        if r["bidireccional"]:
            out.append(_h(
                "R09 · Relación bidireccional", "alta", objeto,
                "El filtro cruzado en ambas direcciones genera ambigüedad de "
                "caminos y resultados que cambian según el visual.",
                "Volver a dirección simple y resolver el caso puntual con "
                "CROSSFILTER dentro de la medida que lo necesite."))
        if r["muchos_a_muchos"]:
            out.append(_h(
                "R10 · Relación muchos a muchos", "alta", objeto,
                "Las relaciones N:N ocultan duplicados en las claves y "
                "degradan el rendimiento del motor.",
                "Interponer una tabla puente con la clave única (esquema "
                "estrella)."))
        if not r["activa"]:
            out.append(_h(
                "R11 · Relación inactiva", "baja", objeto,
                "Está definida pero apagada: solo actúa vía USERELATIONSHIP.",
                "Confirmar que alguna medida la usa; si no, eliminarla."))
    return out


def _reglas_modelo(cat: Catalogo) -> list[dict]:
    out = []
    visibles = [t for t in cat.tablas if not t["interna"]]

    conectadas = set()
    for r in cat.relaciones:
        conectadas.add(_norm(r["desde_tabla"]))
        conectadas.add(_norm(r["hacia_tabla"]))
    for t in visibles:
        solo_medidas = t["medidas"] and all(
            c["oculta"] for c in t["columnas"]) or not t["columnas"]
        if len(visibles) > 1 and _norm(t["nombre"]) not in conectadas \
                and not solo_medidas:
            out.append(_h(
                "R12 · Tabla sin relaciones", "media", t["nombre"],
                "No participa de ninguna relación: sus filtros no viajan a "
                "ninguna otra tabla.",
                "Relacionarla al modelo o, si es tabla auxiliar, ocultarla."))

    if any(t["interna"] for t in cat.tablas):
        out.append(_h(
            "R13 · Auto date/time activo", "media", "(modelo)",
            "Power BI creó tablas de calendario ocultas por cada columna de "
            "fecha (LocalDateTable_*): infla el modelo y duplica lógica.",
            "Desactivar Auto date/time y usar una única tabla de calendario "
            "marcada como tabla de fechas."))

    if not cat.tabla_fechas() and any(
            c["tipo"] == "dateTime" for t in visibles for c in t["columnas"]):
        out.append(_h(
            "R14 · Sin tabla de calendario", "media", "(modelo)",
            "Hay columnas de fecha pero ninguna tabla de calendario marcada: "
            "la inteligencia de tiempo (YTD, año anterior) puede devolver "
            "resultados incorrectos sin avisar.",
            "Crear una tabla de calendario continua y marcarla como tabla de "
            "fechas."))

    con_medidas = [t["nombre"] for t in visibles
                   if t["medidas"] and any(not c["oculta"] for c in t["columnas"])]
    if len(con_medidas) >= 2:
        out.append(_h(
            "R15 · Medidas dispersas", "baja", ", ".join(con_medidas[:5]),
            "Las medidas viven repartidas en tablas de datos; el panel de "
            "campos mezcla modelo y cálculos.",
            "Concentrarlas en una tabla de medidas dedicada.", auto=True))
    return out


def puntaje(hallazgos: list[dict]) -> int:
    """Salud del modelo 0-100: resta por severidad, con piso en 0."""
    pesos = {"alta": 12, "media": 5, "baja": 2}
    return max(0, 100 - sum(pesos.get(h["severidad"], 2) for h in hallazgos))
