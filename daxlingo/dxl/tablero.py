# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Generador de tableros: del modelo a un reporte con visuales,
slicers (filtros) y navegación, listo para exportar como .pbit o PBIP.

El layout es el formato interno de Power BI Desktop: cada visual necesita su
`prototypeQuery` (la consulta semántica) y sus proyecciones en el rol correcto
del tipo de visual — con el rol equivocado el visual se dibuja vacío, sin
error, que es lo peor. La técnica está heredada y probada del generador de
los tableros del proyecto original de este repo
(powerbi/generar_pbit.py).
"""
from __future__ import annotations

import json
import re
import unicodedata
import uuid

from .catalogo import Catalogo

ANCHO, ALTO = 1280, 720
MARGEN = 20
FILA_NAV, ALTO_NAV = 4, 32
FILA_TITULO = 44
FILA_SLICER, ALTO_SLICER = 100, 32
FILA_KPI, ALTO_KPI = 136, 96
FILA_CONTENIDO = 244

# (rol de la categoría, rol de las medidas) por tipo de visual.
ROLES = {
    "card": (None, "Values"),
    "multiRowCard": (None, "Values"),
    "tableEx": ("Values", "Values"),
    "matrix": ("Rows", "Values"),
    "clusteredBarChart": ("Category", "Y"),
    "clusteredColumnChart": ("Category", "Y"),
    "lineChart": ("Category", "Y"),
    "areaChart": ("Category", "Y"),
    "donutChart": ("Category", "Y"),
    "pieChart": ("Category", "Y"),
    "slicer": ("Values", "Values"),
}


def _slug(titulo: str) -> str:
    """Nombre estable de sección: los botones de navegación referencian por
    nombre, así que tiene que ser determinístico entre regeneraciones."""
    limpio = "".join(
        c if c.isalnum() else "_"
        for c in unicodedata.normalize("NFKD", titulo)
        .encode("ascii", "ignore").decode())
    return "s" + re.sub(r"_+", "_", limpio).strip("_").lower()


def _medida_ref(tabla: str, nombre: str, alias: str = "m") -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Source": alias}},
                        "Property": nombre},
            "Name": f"{tabla}.{nombre}"}


def _columna_ref(tabla: str, col: str, alias: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Source": alias}},
                       "Property": col},
            "Name": f"{tabla}.{col}"}


def visual(tipo: str, x: int, y: int, w: int, h: int, *,
           medidas: list[tuple[str, str]] | None = None,
           categoria: tuple[str, str] | None = None,
           titulo: str | None = None, z: int = 0) -> dict:
    """
    Un visualContainer. `medidas` son pares (tabla, nombre_medida) — la tabla
    es la que aloja la medida en el modelo, no una tabla fija.
    """
    medidas = medidas or []
    rol_cat, rol_med = ROLES.get(tipo, ("Category", "Y"))
    from_, select, proyecciones = [], [], {}

    if categoria and rol_cat:
        tabla, col = categoria
        from_.append({"Name": "c", "Entity": tabla, "Type": 0})
        select.append(_columna_ref(tabla, col, "c"))
        proyecciones.setdefault(rol_cat, []).append(
            {"queryRef": f"{tabla}.{col}"})

    alias_por_tabla: dict[str, str] = {}
    for i, (tabla, nombre) in enumerate(medidas):
        alias = alias_por_tabla.get(tabla)
        if alias is None:
            alias = f"m{len(alias_por_tabla)}"
            alias_por_tabla[tabla] = alias
            from_.append({"Name": alias, "Entity": tabla, "Type": 0})
        select.append(_medida_ref(tabla, nombre, alias))
        proyecciones.setdefault(rol_med, []).append(
            {"queryRef": f"{tabla}.{nombre}"})

    objetos = {}
    if titulo:
        objetos["title"] = [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "text": {"expr": {"Literal": {"Value": f"'{titulo}'"}}},
            "fontSize": {"expr": {"Literal": {"Value": "11D"}}},
        }}]

    conf = {
        "name": uuid.uuid4().hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": tipo,
            "projections": proyecciones,
            "prototypeQuery": {"Version": 2, "From": from_, "Select": select},
            "drillFilterOtherVisuals": True,
            "objects": objetos,
        },
    }
    return {"x": x, "y": y, "z": z, "width": w, "height": h,
            "config": json.dumps(conf, ensure_ascii=False)}


def texto(x: int, y: int, w: int, h: int, contenido: str,
          tamano: int = 12, z: int = 0) -> dict:
    conf = {
        "name": uuid.uuid4().hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "textbox",
            "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {"paragraphs": [{
                "textRuns": [{"value": contenido,
                              "textStyle": {"fontSize": f"{tamano}px"}}]
            }]}}]},
        },
    }
    return {"x": x, "y": y, "z": z, "width": w, "height": h,
            "config": json.dumps(conf, ensure_ascii=False)}


def slicer(x: int, y: int, w: int, h: int, tabla: str, columna: str,
           titulo: str) -> dict:
    """Segmentación: filtra todos los visuales de la página."""
    conf = {
        "name": uuid.uuid5(uuid.NAMESPACE_DNS,
                           f"sl{tabla}{columna}{x}{y}").hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 50,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "slicer",
            "projections": {"Values": [{"queryRef": f"{tabla}.{columna}"}]},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "c", "Entity": tabla, "Type": 0}],
                "Select": [_columna_ref(tabla, columna, "c")],
            },
            "objects": {
                "header": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{titulo}'"}}},
                }}],
            },
            "drillFilterOtherVisuals": True,
        },
    }
    return {"x": x, "y": y, "z": 50, "width": w, "height": h,
            "config": json.dumps(conf, ensure_ascii=False)}


def boton_navegacion(x, y, w, h, etiqueta: str, destino: str,
                     activo: bool = False) -> dict:
    """Botón con acción PageNavigation real hacia otra página del reporte."""
    def lit(v):
        return {"expr": {"Literal": {"Value": v}}}

    fondo = "'#081527'" if activo else "'#FFFFFF'"
    letra = "'#F2B441'" if activo else "'#081527'"
    conf = {
        "name": uuid.uuid5(uuid.NAMESPACE_DNS,
                           f"btn{destino}{etiqueta}{x}").hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 100,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "actionButton",
            "objects": {
                "icon": [{"properties": {"shapeType": lit("'blank'")},
                          "selector": {"id": "default"}}],
                "text": [{"properties": {
                    "show": lit("true"), "text": lit(f"'{etiqueta}'"),
                    "fontSize": lit("10D"),
                    "fontColor": {"solid": {"color": lit(letra)}},
                    "bold": lit("true" if activo else "false"),
                }, "selector": {"id": "default"}}],
                "fill": [{"properties": {
                    "show": lit("true"),
                    "fillColor": {"solid": {"color": lit(fondo)}},
                    "transparency": lit("0D"),
                }, "selector": {"id": "default"}}],
                "outline": [{"properties": {
                    "show": lit("true"),
                    "lineColor": {"solid": {"color": lit("'#081527'")}},
                    "weight": lit("1D"),
                }, "selector": {"id": "default"}}],
            },
            "vcObjects": {"visualLink": [{"properties": {
                "show": lit("true"),
                "type": lit("'PageNavigation'"),
                "navigationSection": lit(f"'{destino}'"),
            }}]},
            "drillFilterOtherVisuals": True,
        },
    }
    return {"x": x, "y": y, "z": 100, "width": w, "height": h,
            "config": json.dumps(conf, ensure_ascii=False)}


def pagina(nombre: str, visuales: list[dict], ordinal: int) -> dict:
    return {
        "name": _slug(nombre),
        "displayName": nombre,
        "displayOption": 1,
        "width": ANCHO,
        "height": ALTO,
        "ordinal": ordinal,
        "visualContainers": visuales,
        "config": json.dumps({}),
        "filters": "[]",
    }


def envolver_layout(secciones: list[dict]) -> dict:
    return {
        "id": 0,
        "resourcePackages": [{"resourcePackage": {
            "name": "SharedResources", "type": 2,
            "items": [{"type": 202, "path": "BaseThemes/CY24SU10.json",
                       "name": "CY24SU10"}],
        }}],
        "sections": secciones,
        "config": json.dumps({
            "version": "5.43",
            "themeCollection": {"baseTheme": {
                "name": "CY24SU10", "version": "5.55", "type": 2}},
            "activeSectionIndex": 0,
            "defaultDrillFilterOtherVisuals": True,
            "settings": {"useNewFilterPaneExperience": True,
                         "allowChangeFilterTypes": True},
        }, ensure_ascii=False),
        "layoutOptimization": 0,
    }


# ==========================================================================
# Diseño automático
# ==========================================================================
def disenar_auto(cat: Catalogo, medidas_sel: list[str] | None = None,
                 titulo: str = "Tablero") -> dict:
    """
    Arma un tablero de dos páginas a partir del catálogo:

      · Resumen — KPIs (hasta 5 medidas), evolución temporal, barras y dona
        por las dos primeras dimensiones de texto, con fila de slicers.
      · Detalle — matriz dimensión × medidas + tabla, mismos slicers.

    `medidas_sel`: nombres de medidas a usar (si no, toma las primeras 5).
    Devuelve el layout listo para `modelo.exportar_pbit` / `exportar_pbip`.
    """
    todas = cat.medidas()
    if not todas:
        raise ValueError("El modelo no tiene medidas: generá alguna primero "
                         "(pestaña Generar DAX) o cargá otro modelo.")
    por_nombre = {m["nombre"]: m for m in todas}
    elegidas = [por_nombre[n] for n in (medidas_sel or []) if n in por_nombre] \
        or todas[:5]
    elegidas = elegidas[:5]
    pares = [(m["tabla"], m["nombre"]) for m in elegidas]

    dims = _dimensiones(cat, maximo=3)
    fecha = cat.columna_fecha()

    titulos = ["01 · Resumen", "02 · Detalle"]
    secciones = [
        _pagina_resumen(titulos, titulo, pares, dims, fecha),
        _pagina_detalle(titulos, titulo, pares, dims),
    ]
    return envolver_layout(secciones)


def _dimensiones(cat: Catalogo, maximo: int = 3) -> list[tuple[str, str]]:
    """Columnas de texto visibles y de baja sospecha de clave: dimensiones."""
    out = []
    for tabla, c in cat.columnas(solo_visibles=True):
        if c["tipo"] != "string":
            continue
        if re.search(r"(^id[_ ]|[_ ]id$|^id$|codigo|code)", c["nombre"],
                     re.IGNORECASE):
            continue
        out.append((tabla, c["nombre"]))
        if len(out) >= maximo:
            break
    return out


def _fila_slicers(dims: list[tuple[str, str]],
                  fecha: tuple[str, str] | None) -> list[dict]:
    cortes = list(dims[:2])
    if fecha:
        cortes.append(fecha)
    if not cortes:
        return []
    ancho = (ANCHO - 2 * MARGEN - 10 * (len(cortes) - 1)) // len(cortes)
    return [slicer(MARGEN + i * (ancho + 10), FILA_SLICER, ancho, ALTO_SLICER,
                   t, c, c)
            for i, (t, c) in enumerate(cortes)]


def _kpis(pares: list[tuple[str, str]]) -> list[dict]:
    ancho = (ANCHO - 2 * MARGEN - 12 * (len(pares) - 1)) // len(pares)
    return [visual("card", MARGEN + i * (ancho + 12), FILA_KPI, ancho,
                   ALTO_KPI, medidas=[p], titulo=p[1])
            for i, p in enumerate(pares)]


def _barra_nav(titulos: list[str], actual: str) -> list[dict]:
    ancho = min(190, (ANCHO - 2 * MARGEN) // max(len(titulos), 1) - 6)
    return [boton_navegacion(MARGEN + i * (ancho + 6), FILA_NAV, ancho,
                             ALTO_NAV, t, _slug(t), activo=(t == actual))
            for i, t in enumerate(titulos)]


def _encabezado(titulo: str, subtitulo: str) -> list[dict]:
    return [texto(MARGEN, FILA_TITULO, 760, 30, titulo, 18),
            texto(MARGEN, FILA_TITULO + 28, 760, 24, subtitulo, 10)]


def _pagina_resumen(titulos, titulo, pares, dims, fecha) -> dict:
    visuales = (_barra_nav(titulos, titulos[0])
                + _encabezado(titulo, "Generado por MV DAX Lab")
                + _fila_slicers(dims, fecha)
                + _kpis(pares))
    y0, alto_libre = FILA_CONTENIDO, ALTO - FILA_CONTENIDO - MARGEN
    mitad = (ANCHO - 2 * MARGEN - 12) // 2
    principal = pares[0]

    if fecha:
        visuales.append(visual(
            "lineChart", MARGEN, y0, ANCHO - 2 * MARGEN, alto_libre // 2 - 6,
            medidas=[principal], categoria=fecha,
            titulo=f"{principal[1]} en el tiempo"))
        y1 = y0 + alto_libre // 2 + 6
        alto_abajo = alto_libre // 2 - 6
    else:
        y1, alto_abajo = y0, alto_libre

    if dims:
        visuales.append(visual(
            "clusteredBarChart", MARGEN, y1, mitad, alto_abajo,
            medidas=[principal], categoria=dims[0],
            titulo=f"{principal[1]} por {dims[0][1]}"))
    if len(dims) > 1:
        visuales.append(visual(
            "donutChart", MARGEN + mitad + 12, y1, mitad, alto_abajo,
            medidas=[principal], categoria=dims[1],
            titulo=f"{principal[1]} por {dims[1][1]}"))
    elif not dims and not fecha:
        visuales.append(texto(
            MARGEN, y1, ANCHO - 2 * MARGEN, 60,
            "El modelo no tiene dimensiones de texto visibles para graficar; "
            "quedan los KPI.", 11))
    return pagina(titulos[0], visuales, 0)


def _pagina_detalle(titulos, titulo, pares, dims) -> dict:
    visuales = (_barra_nav(titulos, titulos[1])
                + _encabezado(f"{titulo} · Detalle",
                              "Matriz de medidas por dimensión")
                + _fila_slicers(dims, None))
    y0 = FILA_KPI
    alto_libre = ALTO - y0 - MARGEN
    if dims:
        visuales.append(visual(
            "matrix", MARGEN, y0, ANCHO - 2 * MARGEN, alto_libre,
            medidas=pares, categoria=dims[0],
            titulo=f"Medidas por {dims[0][1]}"))
    else:
        visuales.append(visual(
            "multiRowCard", MARGEN, y0, ANCHO - 2 * MARGEN, alto_libre,
            medidas=pares, titulo="Medidas"))
    return pagina(titulos[1], visuales, 1)
