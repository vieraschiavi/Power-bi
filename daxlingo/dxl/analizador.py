# © 2026 Martín Viera. Todos los derechos reservados.

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
from .i18n import IDIOMA_DEFECTO, t as traducir

SEVERIDADES = ("alta", "media", "baja")


def _h(rid: str, severidad: str, objeto: str, auto: bool = False,
       **datos: str) -> dict:
    """Un hallazgo.

    El TEXTO no vive acá: `rid` («R04») es la clave de i18n y `datos` completa
    los huecos de la plantilla. Antes el título y la explicación eran cadenas
    en español metidas en este archivo, así que la pestaña Analizador salía en
    español aunque la app estuviera en inglés o portugués. Para leerlo en un
    idioma, `describir(h, idioma)`.
    """
    return {"regla": rid, "severidad": severidad, "objeto": objeto,
            "auto": auto, "datos": datos}


def describir(h: dict, idioma: str = IDIOMA_DEFECTO) -> dict:
    """Título, por qué importa y cómo se arregla, en el idioma pedido."""
    rid = h["regla"]
    datos = h.get("datos") or {}

    def _t(sufijo: str) -> str:
        txt = traducir(f"regla_{rid}{sufijo}", idioma)
        try:
            return txt.format(**datos)
        except (KeyError, IndexError):
            return txt          # plantilla sin hueco, o dato ausente

    return {"titulo": f"{rid} · {_t('')}",
            "detalle": _t("_detalle"), "arreglo": _t("_arreglo")}


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
        hallazgos.append(_h("R00", "media", "(modelo)"))
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
            out.append(_h("R01", "alta", objeto, auto=True))

        if not m["formato"]:
            out.append(_h("R02", "media", objeto, auto=True))

        if RE_IFERROR.search(expr):
            out.append(_h("R03", "media", objeto))

        mfil = RE_FILTER_TABLA.search(expr)
        if mfil and cat.tabla(mfil.group(1)):
            out.append(_h("R04", "media", objeto, tabla=mfil.group(1)))

        clave = re.sub(r"\s+", " ", expr).strip().lower()
        if clave and clave in vistas:
            out.append(_h("R05", "baja", objeto, medida=vistas[clave]))
        elif clave:
            vistas[clave] = nombre

        if nombre != nombre.strip():
            out.append(_h("R06", "baja", objeto))
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
                out.append(_h("R07", "media", objeto))
            es_clave = ((_norm(t["nombre"]), _norm(c["nombre"])) in lados_muchos
                        or re.search(r"(^id[_ ]|[_ ]id$|^id$)",
                                     _norm(c["nombre"])))
            if es_clave and not c["oculta"] and (
                    (_norm(t["nombre"]), _norm(c["nombre"])) in lados_muchos):
                out.append(_h("R08", "baja", objeto, auto=True))
    return out


def _reglas_relaciones(cat: Catalogo) -> list[dict]:
    out = []
    for r in cat.relaciones:
        objeto = (f"{r['desde_tabla']}[{r['desde_col']}] → "
                  f"{r['hacia_tabla']}[{r['hacia_col']}]")
        if r["bidireccional"]:
            out.append(_h("R09", "alta", objeto))
        if r["muchos_a_muchos"]:
            out.append(_h("R10", "alta", objeto))
        if not r["activa"]:
            out.append(_h("R11", "baja", objeto))
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
            out.append(_h("R12", "media", t["nombre"]))

    if any(t["interna"] for t in cat.tablas):
        out.append(_h("R13", "media", "(modelo)"))

    if not cat.tabla_fechas() and any(
            c["tipo"] == "dateTime" for t in visibles for c in t["columnas"]):
        out.append(_h("R14", "media", "(modelo)"))

    con_medidas = [t["nombre"] for t in visibles
                   if t["medidas"] and any(not c["oculta"] for c in t["columnas"])]
    if len(con_medidas) >= 2:
        out.append(_h("R15", "baja", ", ".join(con_medidas[:5]), auto=True))
    return out


_MAX_DATOS_POR_CLAVE = 5


def agrupar(hallazgos: list[dict]) -> list[dict]:
    """
    Agrupa los hallazgos por regla. Cuarenta medidas sin formato son UN
    problema con cuarenta ocurrencias, no cuarenta problemas: mostrarlos
    sueltos entierra los hallazgos graves debajo del ruido.

    `datos` se junta de TODOS los hallazgos del grupo, no solo del primero:
    si R04 agrupa filtros sobre cinco tablas distintas, el detalle tiene que
    nombrarlas a las cinco (`{tabla}` → "Ventas, Clientes, Pedidos…"), no
    solo la primera con las otras cuatro calladas debajo del «· 5×».
    """
    grupos: dict[str, dict] = {}
    valores: dict[str, dict[str, list[str]]] = {}
    for h in hallazgos:
        g = grupos.setdefault(h["regla"], {
            "regla": h["regla"], "severidad": h["severidad"],
            "datos": {}, "auto": h["auto"], "objetos": [],
        })
        g["objetos"].append(h["objeto"])
        vistos = valores.setdefault(h["regla"], {})
        for clave, valor in (h.get("datos") or {}).items():
            lista = vistos.setdefault(clave, [])
            if valor not in lista:
                lista.append(valor)
    for regla, por_clave in valores.items():
        datos = {}
        for clave, lista in por_clave.items():
            if len(lista) <= 1:
                datos[clave] = lista[0] if lista else ""
                continue
            recorte = lista[:_MAX_DATOS_POR_CLAVE]
            texto = ", ".join(recorte)
            if len(lista) > _MAX_DATOS_POR_CLAVE:
                texto += "…"
            datos[clave] = texto
        grupos[regla]["datos"] = datos
    orden = {s: i for i, s in enumerate(SEVERIDADES)}
    return sorted(grupos.values(),
                  key=lambda g: (orden.get(g["severidad"], 9), g["regla"]))


def puntaje(hallazgos: list[dict]) -> int:
    """
    Salud del modelo 0-100.

    El castigo se cuenta POR REGLA, no por ocurrencia, y se satura a 3× el
    peso: un modelo con 40 medidas sin formato tiene el mismo problema que
    uno con 5, no ocho veces peor. Sin ese tope, cualquier modelo grande y
    correcto daba 0 y la métrica dejaba de informar.
    """
    pesos = {"alta": 12, "media": 5, "baja": 2}
    castigo = 0
    for grupo in agrupar(hallazgos):
        peso = pesos.get(grupo["severidad"], 2)
        castigo += peso * min(len(grupo["objetos"]), 3)
    return max(0, 100 - castigo)
