"""
MV DAX Lab · Explicador de expresiones DAX en español.

Sin IA y sin red: tokeniza la expresión, reconoce las funciones contra una
base de conocimiento propia y arma una explicación estructurada — qué calcula,
qué funciones usa, qué referencia y qué tan compleja es. Si hay API key de
Anthropic configurada, el generador puede enriquecer esto; el explicador base
funciona siempre.
"""
from __future__ import annotations

import re

from .catalogo import Catalogo, referencias_dax

# Base de conocimiento: función → (qué hace, categoría)
FUNCIONES: dict[str, tuple[str, str]] = {
    "SUM": ("suma los valores de una columna", "agregación"),
    "SUMX": ("recorre la tabla fila por fila, evalúa la expresión y suma los resultados", "iterador"),
    "AVERAGE": ("promedia los valores de una columna", "agregación"),
    "AVERAGEX": ("recorre la tabla fila por fila y promedia la expresión evaluada", "iterador"),
    "MIN": ("devuelve el mínimo de una columna", "agregación"),
    "MAX": ("devuelve el máximo de una columna", "agregación"),
    "MINX": ("mínimo de una expresión evaluada fila por fila", "iterador"),
    "MAXX": ("máximo de una expresión evaluada fila por fila", "iterador"),
    "COUNT": ("cuenta los valores no vacíos de una columna", "agregación"),
    "COUNTROWS": ("cuenta las filas de una tabla", "agregación"),
    "COUNTX": ("cuenta evaluando una expresión fila por fila", "iterador"),
    "DISTINCTCOUNT": ("cuenta los valores distintos de una columna", "agregación"),
    "CALCULATE": ("evalúa la expresión CAMBIANDO el contexto de filtro con los filtros que se le pasan", "contexto"),
    "CALCULATETABLE": ("como CALCULATE pero devuelve una tabla", "contexto"),
    "FILTER": ("devuelve las filas de la tabla que cumplen la condición", "tabla"),
    "ALL": ("quita los filtros de la tabla o columna indicada", "contexto"),
    "ALLEXCEPT": ("quita todos los filtros salvo los de las columnas indicadas", "contexto"),
    "ALLSELECTED": ("quita los filtros internos del visual pero respeta los slicers", "contexto"),
    "REMOVEFILTERS": ("quita filtros — versión moderna y legible de ALL", "contexto"),
    "KEEPFILTERS": ("agrega el filtro sin pisar los existentes (intersección)", "contexto"),
    "VALUES": ("devuelve los valores visibles (distintos) de una columna en el contexto actual", "tabla"),
    "DISTINCT": ("devuelve los valores distintos de una columna", "tabla"),
    "SELECTEDVALUE": ("devuelve el valor si hay UNO solo visible; si no, el alternativo", "contexto"),
    "HASONEVALUE": ("verdadero si la columna tiene un único valor visible", "contexto"),
    "ISFILTERED": ("verdadero si la columna está siendo filtrada", "contexto"),
    "DIVIDE": ("divide de forma segura: ante denominador 0 o BLANK devuelve BLANK (o el alternativo)", "matemática"),
    "IF": ("evalúa una condición y devuelve una de dos ramas", "lógica"),
    "SWITCH": ("compara contra varios casos y devuelve la rama que coincide", "lógica"),
    "AND": ("verdadero si ambas condiciones lo son", "lógica"),
    "OR": ("verdadero si alguna condición lo es", "lógica"),
    "NOT": ("invierte la condición", "lógica"),
    "COALESCE": ("devuelve el primer valor no BLANK de la lista", "lógica"),
    "ISBLANK": ("verdadero si el valor es BLANK", "lógica"),
    "BLANK": ("devuelve el valor vacío BLANK", "lógica"),
    "TOTALYTD": ("acumula la expresión desde el inicio del año hasta la fecha del contexto", "tiempo"),
    "TOTALQTD": ("acumula desde el inicio del trimestre", "tiempo"),
    "TOTALMTD": ("acumula desde el inicio del mes", "tiempo"),
    "SAMEPERIODLASTYEAR": ("desplaza las fechas del contexto un año hacia atrás", "tiempo"),
    "DATEADD": ("desplaza las fechas del contexto el intervalo indicado", "tiempo"),
    "DATESINPERIOD": ("devuelve las fechas de un período móvil que termina en la fecha dada", "tiempo"),
    "DATESYTD": ("las fechas desde el inicio del año hasta la actual", "tiempo"),
    "PREVIOUSMONTH": ("las fechas del mes anterior completo", "tiempo"),
    "LASTDATE": ("la última fecha visible en el contexto", "tiempo"),
    "FIRSTDATE": ("la primera fecha visible en el contexto", "tiempo"),
    "EOMONTH": ("el fin de mes de una fecha, con corrimiento opcional", "tiempo"),
    "TODAY": ("la fecha de hoy", "tiempo"),
    "RANKX": ("posición de cada elemento al ordenar la tabla por la expresión", "ranking"),
    "TOPN": ("las N filas con mayor valor de la expresión", "ranking"),
    "RELATED": ("trae el valor desde el lado «uno» de la relación", "relación"),
    "RELATEDTABLE": ("las filas relacionadas desde el lado «muchos»", "relación"),
    "USERELATIONSHIP": ("activa una relación inactiva solo dentro de este cálculo", "relación"),
    "CROSSFILTER": ("cambia la dirección del filtro de una relación solo en este cálculo", "relación"),
    "TREATAS": ("aplica los valores de una tabla como filtro sobre otras columnas", "relación"),
    "LOOKUPVALUE": ("busca un valor en otra tabla por igualdad de claves", "relación"),
    "SUMMARIZE": ("agrupa una tabla por columnas", "tabla"),
    "ADDCOLUMNS": ("agrega columnas calculadas a una tabla en memoria", "tabla"),
    "SELECTCOLUMNS": ("proyecta columnas de una tabla", "tabla"),
    "UNION": ("apila dos tablas", "tabla"),
    "CONCATENATEX": ("concatena textos evaluados fila por fila", "texto"),
    "FORMAT": ("convierte un valor a texto con formato", "texto"),
    "VAR": ("define una variable: se evalúa una vez y se reutiliza", "estructura"),
    "RETURN": ("devuelve el resultado final usando las variables definidas", "estructura"),
}

RE_FUNCION = re.compile(r"\b([A-Z][A-Z0-9\.]{1,30})\s*\(")
RE_VAR = re.compile(r"\bVAR\s+(\w+)\s*=", re.IGNORECASE)


def _funciones_usadas(expr: str) -> list[str]:
    sin_strings = re.sub(r'"[^"]*"', '""', expr)
    vistas, orden = set(), []
    for m in RE_FUNCION.finditer(sin_strings.upper()):
        f = m.group(1)
        if f not in vistas:
            vistas.add(f)
            orden.append(f)
    if re.search(r"\bVAR\b", sin_strings, re.IGNORECASE):
        orden.insert(0, "VAR")
    return orden


def _profundidad(expr: str) -> int:
    nivel = maximo = 0
    for ch in expr:
        if ch == "(":
            nivel += 1
            maximo = max(maximo, nivel)
        elif ch == ")":
            nivel = max(0, nivel - 1)
    return maximo


def explicar(expresion: str, cat: Catalogo | None = None,
             nombre: str = "") -> dict:
    """
    Explica una expresión DAX. Devuelve:
      resumen      una frase con lo que la medida calcula
      pasos        lectura guiada (variables, contexto, agregación)
      funciones    [{nombre, descripcion, categoria}]
      referencias  {columnas, medidas} + faltantes si hay catálogo
      nivel        'básico' | 'intermedio' | 'avanzado'
    """
    expr = (expresion or "").strip()
    if not expr:
        return {"resumen": "Expresión vacía.", "pasos": [], "funciones": [],
                "referencias": {"columnas": [], "medidas": []},
                "nivel": "básico", "faltantes": []}

    usadas = _funciones_usadas(expr)
    detalle = [{"nombre": f,
                "descripcion": FUNCIONES.get(f, ("función DAX", ""))[0],
                "categoria": FUNCIONES.get(f, ("", "otra"))[1]}
               for f in usadas]
    refs = referencias_dax(expr)
    faltantes = []
    if cat is not None and not cat.parcial:
        from .catalogo import validar_referencias
        faltantes = validar_referencias(expr, cat)

    pasos = _narrar(expr, usadas, refs)
    nivel = _nivel(usadas, expr)
    resumen = _resumen(expr, usadas, refs, nombre)
    return {"resumen": resumen, "pasos": pasos, "funciones": detalle,
            "referencias": refs, "nivel": nivel, "faltantes": faltantes}


def _resumen(expr: str, usadas: list[str], refs: dict, nombre: str) -> str:
    quien = f"La medida [{nombre}]" if nombre else "La expresión"
    cats = {FUNCIONES.get(f, ("", ""))[1] for f in usadas}
    col = f"{refs['columnas'][0][0]}[{refs['columnas'][0][1]}]" \
        if refs["columnas"] else ""

    if "tiempo" in cats and "CALCULATE" in usadas:
        return (f"{quien} calcula un valor con inteligencia de tiempo: "
                "desplaza o acumula el período del contexto antes de agregar.")
    if "TOTALYTD" in usadas:
        return f"{quien} acumula el valor desde el inicio del año."
    if "RANKX" in usadas:
        return f"{quien} calcula una posición en un ranking."
    if "DIVIDE" in usadas:
        return f"{quien} calcula un cociente con división segura."
    if "CALCULATE" in usadas:
        return (f"{quien} agrega un valor modificando antes el contexto de "
                "filtro (eso es CALCULATE: cambia sobre qué filas se calcula).")
    if usadas and usadas[0] in FUNCIONES:
        base = FUNCIONES[usadas[0]][0]
        return f"{quien} {base}{f' sobre {col}' if col else ''}."
    return f"{quien} evalúa una expresión aritmética simple."


def _narrar(expr: str, usadas: list[str], refs: dict) -> list[str]:
    pasos = []
    variables = RE_VAR.findall(expr)
    if variables:
        pasos.append(
            f"Define {len(variables)} variable(s) ({', '.join(variables[:4])}"
            f"{'…' if len(variables) > 4 else ''}): cada una se evalúa una "
            "sola vez y congela su valor — más rápido y más legible.")
    if "CALCULATE" in usadas:
        pasos.append(
            "CALCULATE cambia el contexto de filtro: los filtros que recibe "
            "reemplazan (o intersecan, con KEEPFILTERS) a los del visual "
            "antes de evaluar la expresión.")
    iteradores = [f for f in usadas
                  if FUNCIONES.get(f, ("", ""))[1] == "iterador"]
    if iteradores:
        pasos.append(
            f"{', '.join(iteradores)} recorre(n) la tabla fila por fila: el "
            "costo crece con la cantidad de filas visibles.")
    tiempo = [f for f in usadas if FUNCIONES.get(f, ("", ""))[1] == "tiempo"]
    if tiempo:
        pasos.append(
            f"Inteligencia de tiempo ({', '.join(tiempo)}): necesita una "
            "tabla de calendario continua y marcada como tabla de fechas "
            "para dar resultados correctos.")
    if refs["medidas"]:
        pasos.append(
            "Reutiliza medidas existentes ("
            + ", ".join(f"[{m}]" for m in refs["medidas"][:4])
            + "): el cambio en la medida base se propaga solo.")
    if not pasos:
        pasos.append("Agregación directa sobre el contexto del visual, sin "
                     "modificar filtros.")
    return pasos


def _nivel(usadas: list[str], expr: str) -> str:
    cats = {FUNCIONES.get(f, ("", ""))[1] for f in usadas}
    avanzadas = {"contexto", "tiempo", "ranking", "relación"} & cats
    if _profundidad(expr) >= 4 or len(avanzadas) >= 2 or "VAR" in usadas:
        return "avanzado"
    if avanzadas or len(usadas) >= 3:
        return "intermedio"
    return "básico"
