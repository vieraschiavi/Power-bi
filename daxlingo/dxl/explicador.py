# © 2026 Martín Viera. Todos los derechos reservados.

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
from .i18n import IDIOMA_DEFECTO, t as traducir

# Base de conocimiento: función DAX → categoría.
#
# La DESCRIPCIÓN no vive acá: está en i18n como `fn_<FUNCION>`, y la
# categoría como `catfn_<categoria>`. Antes las descripciones eran
# cadenas en español en este archivo, así que la pestaña Explicador
# contestaba en español aunque la app estuviera en inglés o portugués.
#
# La categoría es una CLAVE, no un texto: `_nivel()` y `_narrar()`
# comparan contra ella, así que va sin acentos y no se traduce acá.
FUNCIONES: dict[str, str] = {
    "SUM": "agregacion",
    "SUMX": "iterador",
    "AVERAGE": "agregacion",
    "AVERAGEX": "iterador",
    "MIN": "agregacion",
    "MAX": "agregacion",
    "MINX": "iterador",
    "MAXX": "iterador",
    "COUNT": "agregacion",
    "COUNTROWS": "agregacion",
    "COUNTX": "iterador",
    "DISTINCTCOUNT": "agregacion",
    "CALCULATE": "contexto",
    "CALCULATETABLE": "contexto",
    "FILTER": "tabla",
    "ALL": "contexto",
    "ALLEXCEPT": "contexto",
    "ALLSELECTED": "contexto",
    "REMOVEFILTERS": "contexto",
    "KEEPFILTERS": "contexto",
    "VALUES": "tabla",
    "DISTINCT": "tabla",
    "SELECTEDVALUE": "contexto",
    "HASONEVALUE": "contexto",
    "ISFILTERED": "contexto",
    "DIVIDE": "matematica",
    "IF": "logica",
    "SWITCH": "logica",
    "AND": "logica",
    "OR": "logica",
    "NOT": "logica",
    "COALESCE": "logica",
    "ISBLANK": "logica",
    "BLANK": "logica",
    "TOTALYTD": "tiempo",
    "TOTALQTD": "tiempo",
    "TOTALMTD": "tiempo",
    "SAMEPERIODLASTYEAR": "tiempo",
    "DATEADD": "tiempo",
    "DATESINPERIOD": "tiempo",
    "DATESYTD": "tiempo",
    "PREVIOUSMONTH": "tiempo",
    "LASTDATE": "tiempo",
    "FIRSTDATE": "tiempo",
    "EOMONTH": "tiempo",
    "TODAY": "tiempo",
    "RANKX": "ranking",
    "TOPN": "ranking",
    "RELATED": "relacion",
    "RELATEDTABLE": "relacion",
    "USERELATIONSHIP": "relacion",
    "CROSSFILTER": "relacion",
    "TREATAS": "relacion",
    "LOOKUPVALUE": "relacion",
    "SUMMARIZE": "tabla",
    "ADDCOLUMNS": "tabla",
    "SELECTCOLUMNS": "tabla",
    "UNION": "tabla",
    "CONCATENATEX": "texto",
    "FORMAT": "texto",
    "VAR": "estructura",
    "RETURN": "estructura",
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
             nombre: str = "", idioma: str = IDIOMA_DEFECTO) -> dict:
    """
    Explica una expresión DAX. Devuelve:
      resumen      una frase con lo que la medida calcula
      pasos        lectura guiada (variables, contexto, agregación)
      funciones    [{nombre, descripcion, categoria}]
      referencias  {columnas, medidas} + faltantes si hay catálogo
      nivel        'basico' | 'intermedio' | 'avanzado' (CLAVE, no texto)
      nivel_txt    el nivel ya traducido, que es lo que se muestra
    """
    expr = (expresion or "").strip()
    if not expr:
        return {"resumen": traducir("exp_vacia", idioma), "pasos": [],
                "funciones": [],
                "referencias": {"columnas": [], "medidas": []},
                "nivel": "basico",
                "nivel_txt": traducir("nivel_basico", idioma),
                "faltantes": []}

    usadas = _funciones_usadas(expr)
    detalle = [{"nombre": f,
                "descripcion": (traducir(f"fn_{f}", idioma)
                                if f in FUNCIONES
                                else traducir("exp_fn_desconocida", idioma)),
                "categoria": FUNCIONES.get(f, "otra"),
                "categoria_txt": traducir(
                    f"catfn_{FUNCIONES.get(f, 'otra')}", idioma)}
               for f in usadas]
    refs = referencias_dax(expr)
    faltantes = []
    if cat is not None and not cat.parcial:
        from .catalogo import validar_referencias
        faltantes = validar_referencias(expr, cat, idioma)

    pasos = _narrar(expr, usadas, refs, idioma)
    nivel = _nivel(usadas, expr)
    resumen = _resumen(expr, usadas, refs, nombre, idioma)
    return {"resumen": resumen, "pasos": pasos, "funciones": detalle,
            "referencias": refs, "nivel": nivel,
            "nivel_txt": traducir(f"nivel_{nivel}", idioma),
            "faltantes": faltantes}


def _resumen(expr: str, usadas: list[str], refs: dict, nombre: str,
             idioma: str) -> str:
    quien = (traducir("exp_quien_medida", idioma).format(nombre=nombre)
             if nombre else traducir("exp_quien_expresion", idioma))
    cats = {FUNCIONES.get(f, "") for f in usadas}
    col = f"{refs['columnas'][0][0]}[{refs['columnas'][0][1]}]" \
        if refs["columnas"] else ""

    if "tiempo" in cats and "CALCULATE" in usadas:
        return traducir("exp_res_tiempo", idioma).format(quien=quien)
    if "TOTALYTD" in usadas:
        return traducir("exp_res_ytd", idioma).format(quien=quien)
    if "RANKX" in usadas:
        return traducir("exp_res_rank", idioma).format(quien=quien)
    if "DIVIDE" in usadas:
        return traducir("exp_res_divide", idioma).format(quien=quien)
    if "CALCULATE" in usadas:
        return traducir("exp_res_calculate", idioma).format(quien=quien)
    if usadas and usadas[0] in FUNCIONES:
        sobre = (traducir("exp_sobre", idioma).format(col=col) if col else "")
        return traducir("exp_res_base", idioma).format(
            quien=quien, base=traducir(f"fn_{usadas[0]}", idioma), sobre=sobre)
    return traducir("exp_res_simple", idioma).format(quien=quien)


def _narrar(expr: str, usadas: list[str], refs: dict,
            idioma: str) -> list[str]:
    pasos = []
    variables = RE_VAR.findall(expr)
    if variables:
        pasos.append(traducir("exp_paso_var", idioma).format(
            n=len(variables), lista=", ".join(variables[:4]),
            mas="…" if len(variables) > 4 else ""))
    if "CALCULATE" in usadas:
        pasos.append(traducir("exp_paso_calculate", idioma))
    iteradores = [f for f in usadas if FUNCIONES.get(f) == "iterador"]
    if iteradores:
        pasos.append(traducir("exp_paso_iterador", idioma).format(
            lista=", ".join(iteradores)))
    tiempo = [f for f in usadas if FUNCIONES.get(f) == "tiempo"]
    if tiempo:
        pasos.append(traducir("exp_paso_tiempo", idioma).format(
            lista=", ".join(tiempo)))
    if refs["medidas"]:
        pasos.append(traducir("exp_paso_medidas", idioma).format(
            lista=", ".join(f"[{m}]" for m in refs["medidas"][:4])))
    if not pasos:
        pasos.append(traducir("exp_paso_directo", idioma))
    return pasos


def _nivel(usadas: list[str], expr: str) -> str:
    cats = {FUNCIONES.get(f, "") for f in usadas}
    avanzadas = {"contexto", "tiempo", "ranking", "relacion"} & cats
    if _profundidad(expr) >= 4 or len(avanzadas) >= 2 or "VAR" in usadas:
        return "avanzado"
    if avanzadas or len(usadas) >= 3:
        return "intermedio"
    return "basico"
