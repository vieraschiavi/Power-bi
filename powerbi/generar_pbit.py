"""
Genera los archivos de Power BI de los tres tableros.

Produce DOS formatos, a propósito:

  1. `.pbit` (Power BI Template) — un archivo por tablero. Se abre con doble
     clic en Power BI Desktop, pide la carpeta de datos, carga y queda listo.
     Después: Archivo → Guardar como → .pbix.

  2. PBIP (Power BI Project) — carpeta con el modelo en TMSL y el reporte en
     JSON. Es el formato de control de versiones: se revisa en un diff, se
     abre con Archivo → Abrir → .pbip y también se guarda como .pbix.

¿Por qué no un .pbix directamente? Porque un .pbix lleva el modelo tabular
como un binario comprimido propietario de Analysis Services: no se puede
autorizar desde afuera de Power BI, y tampoco se puede revisar en un diff.
El .pbit y el PBIP son los dos formatos que Microsoft define justamente para
esto — y desde cualquiera de los dos, guardar como .pbix es un paso.

Lo que llevan adentro:
  · las 20 tablas del modelo estrella, con nombres de negocio
  · las relaciones, todas 1:* y de dirección simple
  · la biblioteca DAX completa, parseada de powerbi/dax/*.dax
  · formatos, columnas ocultas, orden por columna y jerarquías
  · el rol de seguridad dinámico (RLS)
  · las páginas del reporte con sus visuales

Uso:  python powerbi/generar_pbit.py
"""
from __future__ import annotations

import json
import re
import uuid
import zipfile
from pathlib import Path

import esquema as esq

RAIZ = Path(__file__).resolve().parents[1]
DAX_DIR = Path(__file__).resolve().parent / "dax"
SALIDA = Path(__file__).resolve().parent / "archivos"
SALIDA.mkdir(exist_ok=True)

# Ruta de datos que se propone al abrir el template. Es un PARÁMETRO: al abrir
# el .pbit, Power BI la pide y el usuario apunta a su propia carpeta.
#
# Ojo con el escapado: en Power Query M la barra invertida NO es carácter de
# escape (el escape es #(...)), así que la ruta va literal. Duplicarla —el
# reflejo de JSON o C— produciría una ruta inválida. El escapado a JSON lo
# hace json.dumps después, y al decodificar vuelve a una sola barra.
RUTA_DATOS_DEFECTO = r"C:\Adium\data\star"


# ==========================================================================
# 1 · Parseo de la biblioteca DAX
# ==========================================================================
PALABRAS_DAX = {
    "VAR", "RETURN", "CALCULATE", "SUMX", "IF", "SWITCH", "DIVIDE", "FILTER",
    "ADDCOLUMNS", "SUMMARIZE", "RANKX", "TOPN", "CONCATENATEX", "AVERAGEX",
    "COUNTROWS", "SUM", "AVERAGE", "MAX", "MIN", "FORMAT", "TRUE", "BLANK",
}


def parsear_dax(archivo: Path) -> list[dict]:
    """
    Extrae las medidas de un archivo .dax.

    Una medida arranca en una línea SIN indentar que contiene ` = `; todo lo
    que sigue —indentado o no— es su expresión, hasta la próxima cabecera.
    Los comentarios `//` que preceden a una medida se guardan como su
    descripción, que es lo que después se ve en el tooltip del panel de campos.
    """
    medidas: list[dict] = []
    nombre = None
    cuerpo: list[str] = []
    comentario: list[str] = []

    def cerrar():
        if nombre:
            expr = "\n".join(cuerpo).strip()
            if expr:
                medidas.append({
                    "nombre": nombre,
                    "expresion": expr,
                    "descripcion": " ".join(comentario).strip() or None,
                })

    for linea in archivo.read_text(encoding="utf-8").splitlines():
        cabecera = re.match(r"^([^\s/][^=\[\(]*?)\s*=\s*(.*)$", linea)
        # OJO con el case: la palabra clave DAX es `VAR` en mayúsculas, y hay
        # medidas que se llaman "Var % vs AA". Comparar sin distinguir
        # mayúsculas se comía seis medidas en silencio — el peor tipo de bug,
        # porque el archivo se generaba igual y fallaba recién al abrirlo.
        es_cabecera = bool(
            cabecera
            and not linea.startswith(" ")
            and cabecera.group(1).strip().split(" ")[0] not in PALABRAS_DAX
        )
        if es_cabecera:
            cerrar()
            nombre = cabecera.group(1).strip()
            resto = cabecera.group(2).strip()
            cuerpo = [resto] if resto else []
            continue

        if linea.lstrip().startswith("//"):
            if nombre is None or not cuerpo:
                comentario.append(linea.lstrip().lstrip("/").strip())
            continue

        if not linea.strip():
            if nombre and cuerpo:
                cerrar()
                nombre, cuerpo, comentario = None, [], []
            continue

        if nombre:
            cuerpo.append(linea)
        # una línea suelta sin medida abierta es prosa del encabezado: se ignora

    cerrar()
    return medidas


def cargar_medidas(archivos: list[str]) -> list[dict]:
    vistas, salida = set(), []
    for a in archivos:
        for m in parsear_dax(DAX_DIR / a):
            if m["nombre"] in vistas:
                continue
            vistas.add(m["nombre"])
            salida.append(m)
    return salida


# ==========================================================================
# 2 · Consultas M (Power Query)
# ==========================================================================
TIPO_M = {
    "int64": "Int64.Type",
    "double": "type number",
    "string": "type text",
    "dateTime": "type datetime",
    "boolean": "type logical",
}


def _m_texto(v: str) -> str:
    """Literal de texto en M: las comillas se escapan duplicándolas."""
    return '"' + v.replace('"', '""') + '"'


def _m_lista(valores) -> str:
    """
    Lista M.

    M usa LLAVES para listas, no corchetes: {"a", "b"}. Los corchetes son
    acceso a campos de registro. Serializar con json.dumps parece que funciona
    —el archivo se genera igual— y revienta recién al abrir el modelo.
    """
    partes = []
    for v in valores:
        if isinstance(v, (list, tuple)):
            partes.append(_m_lista(v))
        else:
            partes.append(_m_texto(v))
    return "{" + ", ".join(partes) + "}"


def expresion_m(tabla: str, cfg: dict) -> list[str]:
    """
    Genera la consulta M de una tabla.

    Estructura fija en cuatro pasos, siempre la misma, para que el diff entre
    versiones sea legible:
        Origen → columnas derivadas → renombrar a nombres de negocio → tipar
    """
    origen = cfg["origen"]
    lineas = [
        "let",
        f'    Origen = Parquet.Document(File.Contents(RutaDatos & "\\{origen}.parquet")),',
    ]
    paso = "Origen"

    # aplanado de dimensiones satélite (desnormalización de estrella)
    if tabla in esq.APLANAR:
        ap = esq.APLANAR[tabla]
        cols = list(ap["columnas"])
        lineas.append(
            f'    Satelite = Parquet.Document(File.Contents(RutaDatos & "\\{ap["tabla"]}.parquet")),'
        )
        lineas.append(
            f'    Unido = Table.NestedJoin({paso}, {{"{ap["clave"]}"}}, Satelite, '
            f'{{"{ap["clave"]}"}}, "_sat", JoinKind.LeftOuter),'
        )
        lineas.append(
            '    Expandido = Table.ExpandTableColumn(Unido, "_sat", '
            + _m_lista(cols)
            + ", "
            + _m_lista([ap["columnas"][c] for c in cols])
            + "),"
        )
        paso = "Expandido"

    # columnas derivadas
    for i, (nombre, expr, tipo) in enumerate(esq.DERIVADAS.get(tabla, [])):
        nuevo = f"Derivada{i}"
        lineas.append(
            f'    {nuevo} = Table.AddColumn({paso}, "{nombre}", '
            f"each {expr}, {tipo}),"
        )
        paso = nuevo

    # renombrado a nombres de negocio
    renombres = [
        [orig, visible]
        for orig, visible, _t, _o in cfg["columnas"]
        if orig is not None and orig != visible
    ]
    if renombres:
        lineas.append(
            f"    Renombrado = Table.RenameColumns({paso}, "
            + _m_lista(renombres)
            + "),"
        )
        paso = "Renombrado"

    # selección: solo lo que el modelo declara. Cada columna de más es memoria.
    visibles = [v for _o, v, _t, _oc in cfg["columnas"]]
    lineas.append(
        f"    Seleccionado = Table.SelectColumns({paso}, "
        + _m_lista(visibles)
        + "),"
    )
    # Los tipos NO son literales de texto: van como identificadores M
    # (Int64.Type, type number...), así que esta lista se arma a mano.
    cuerpo_tipos = ", ".join(
        f"{{{_m_texto(v)}, {TIPO_M[t]}}}" for _o, v, t, _oc in cfg["columnas"]
    )
    lineas.append(f"    Tipado = Table.TransformColumnTypes(Seleccionado, {{{cuerpo_tipos}}})")
    lineas.append("in")
    lineas.append("    Tipado")
    return lineas


# ==========================================================================
# 3 · Modelo TMSL
# ==========================================================================
def construir_modelo(nombre_tablero: str, medidas: list[dict]) -> dict:
    tablas = []

    for tabla, cfg in esq.TABLAS.items():
        columnas = []
        for _orig, visible, tipo, oculta in cfg["columnas"]:
            col = {
                "name": visible,
                "dataType": tipo,
                "sourceColumn": visible,
                "summarizeBy": "none",
                "annotations": [{"name": "SummarizationSetBy", "value": "User"}],
            }
            if oculta:
                col["isHidden"] = True
            if tipo == "dateTime":
                col["formatString"] = "yyyy-mm-dd"
            if cfg.get("orden", {}).get(visible):
                col["sortByColumn"] = cfg["orden"][visible]
            columnas.append(col)

        t = {
            "name": tabla,
            "columns": columnas,
            "partitions": [{
                "name": tabla,
                "mode": "import",
                "source": {"type": "m", "expression": expresion_m(tabla, cfg)},
            }],
        }
        if cfg.get("esCalendario"):
            # Marcar como tabla de fechas. Sin esto, la inteligencia de tiempo
            # puede devolver resultados incorrectos sin avisar.
            t["dataCategory"] = "Time"
            for c in t["columns"]:
                if c["name"] == "Fecha":
                    c["isKey"] = True
        if cfg.get("jerarquias"):
            t["hierarchies"] = [
                {
                    "name": h,
                    "levels": [
                        {"name": n, "ordinal": i, "column": n}
                        for i, n in enumerate(niveles)
                    ],
                }
                for h, niveles in cfg["jerarquias"].items()
            ]
        tablas.append(t)

    # Tabla de medidas: vacía a propósito, para que el panel de campos separe
    # el modelo de los cálculos.
    tablas.append({
        "name": "_Medidas",
        "columns": [{
            "name": "_",
            "dataType": "string",
            "isHidden": True,
            "sourceColumn": "_",
            "summarizeBy": "none",
            "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}],
        }],
        "partitions": [{
            "name": "_Medidas",
            "mode": "import",
            "source": {
                "type": "m",
                "expression": [
                    "let",
                    '    Origen = #table({"_"}, {{""}})',
                    "in",
                    "    Origen",
                ],
            },
        }],
        "measures": [
            {
                k: v for k, v in {
                    "name": m["nombre"],
                    "expression": m["expresion"].split("\n"),
                    "formatString": esq.formato_de(m["nombre"]),
                    "description": m["descripcion"],
                    "displayFolder": carpeta_de(m["nombre"]),
                }.items() if v is not None
            }
            for m in medidas
        ],
    })

    relaciones = [
        {
            "name": f"{t1}-{t2}-{c2}",
            "fromTable": t2, "fromColumn": c2,      # lado muchos
            "toTable": t1, "toColumn": c1,          # lado uno
            "crossFilteringBehavior": "oneDirection",
        }
        for t1, c1, t2, c2 in esq.RELACIONES
    ]

    return {
        "name": nombre_tablero,
        "compatibilityLevel": 1567,
        "model": {
            "culture": "es-ES",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "es-ES",
            # Parámetro de Power Query. Va en `expressions`, NO como tabla:
            # un parámetro es un valor escalar reutilizable, y es lo que hace
            # que el template sea portable — al abrirlo, Power BI lo pide.
            "expressions": [{
                "name": "RutaDatos",
                "kind": "m",
                "description": "Carpeta que contiene los .parquet del modelo estrella "
                               "(la que genera `python src/run_all.py`).",
                "expression": [
                    f'"{RUTA_DATOS_DEFECTO}"',
                    '    meta [IsParameterQuery=true, Type="Text", '
                    "IsParameterQueryRequired=true]",
                ],
                "annotations": [{"name": "PBI_NavigationStepName", "value": "Navegación"},
                                {"name": "PBI_ResultType", "value": "Text"}],
            }],
            "tables": tablas,
            "relationships": relaciones,
            "roles": [{
                # RLS dinámico: un solo rol para todas las filiales.
                # Un rol por país no escala y hay que mantenerlo a mano.
                "name": "Filial",
                "modelPermission": "read",
                "tablePermissions": [{
                    "name": "v_dim_filial",
                    "filterExpression":
                        "-- Reemplazar por la tabla puente Seguridad(Email, Id filial)\n"
                        "-- publicada en el workspace:\n"
                        "-- v_dim_filial[Id filial] IN\n"
                        "--     CALCULATETABLE ( VALUES ( Seguridad[Id filial] ),\n"
                        "--         Seguridad[Email] = USERPRINCIPALNAME () )\n"
                        "TRUE ()",
                }],
            }],
            "annotations": [
                {"name": "PBI_QueryOrder",
                 "value": json.dumps(["RutaDatos"] + list(esq.TABLAS) + ["_Medidas"], ensure_ascii=False)},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }


def carpeta_de(nombre: str) -> str | None:
    """Agrupa las medidas en carpetas del panel de campos."""
    n = nombre.lower()
    if n.startswith(("semáforo", "estado", "alerta", "encabezado", "último dato",
                     "días de atraso", "ventas en revisión", "título", "lectura",
                     "titular", "nota metodológica", "justificativo",
                     "control cierre", "origen de la variación",
                     "motivo principal")):
        return "00 · Contexto y gobierno"
    if "efecto" in n or "puente" in n:
        return "03 · Puente Precio-Volumen-Mix"
    if "share" in n or "mercado" in n or "sell-out" in n or "sell-in" in n:
        return "02 · Mercado y sell-out"
    if any(k in n for k in ("oferta", "inversión", "roi", "aceptación",
                            "recomend", "descuento recomendado", "brecha vs")):
        return "05 · Ofertas e IA"
    if any(k in n for k in ("otif", "lead time", "devoluc", "stock", "cobertura",
                            "vencer", "riesgo", "fill rate", "entregas")):
        return "06 · Logística y riesgo"
    if any(k in n for k in ("objetivo", "cumplimiento", "gap")):
        return "04 · Objetivo"
    if any(k in n for k in ("mat", "aa", "ytd", "ma3")):
        return "01 · Tiempo"
    return "01 · Ventas y margen"


# ==========================================================================
# 4 · Reporte (layout)
# ==========================================================================
ANCHO, ALTO = 1280, 720
PALETA = ["#0B3C5D", "#1D7874", "#F2A65A", "#2E8B57", "#C1443C", "#5A6B7B",
          "#8C6D3F", "#3C6E9F"]


def _medida(nombre: str) -> dict:
    return {
        "Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": nombre},
        "Name": f"_Medidas.{nombre}",
    }


def _columna(tabla: str, col: str, alias: str) -> dict:
    return {
        "Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": col},
        "Name": f"{tabla}.{col}",
    }


# Cada tipo de visual espera sus campos en roles con nombre propio. Si el rol
# no coincide, el visual se dibuja vacío — sin error, que es lo peor.
# (rol de la categoría, rol de las medidas)
ROLES = {
    "card":                            (None,       "Values"),
    "multiRowCard":                    (None,       "Values"),
    "tableEx":                         ("Values",   "Values"),
    "matrix":                          ("Rows",     "Values"),
    "clusteredBarChart":               ("Category", "Y"),
    "clusteredColumnChart":            ("Category", "Y"),
    "columnChart":                     ("Category", "Y"),
    "barChart":                        ("Category", "Y"),
    "lineChart":                       ("Category", "Y"),
    "areaChart":                       ("Category", "Y"),
    "lineClusteredColumnComboChart":   ("Category", "Y"),
    "waterfallChart":                  ("Category", "Y"),
    "scatterChart":                    ("Category", "X"),
    "donutChart":                      ("Category", "Y"),
    "pieChart":                        ("Category", "Y"),
    "slicer":                          ("Values",   "Values"),
}


def visual(tipo, x, y, w, h, *, medidas=None, categoria=None, serie=None,
           titulo=None, z=0) -> dict:
    """
    Construye un visualContainer del layout de Power BI.

    `prototypeQuery` es obligatorio: es la consulta semántica que el visual
    ejecuta. Sin ella el visual se dibuja vacío.
    """
    medidas = medidas or []
    rol_cat, rol_med = ROLES.get(tipo, ("Category", "Y"))
    from_ = []
    select = []
    proyecciones: dict[str, list] = {}

    if categoria and rol_cat:
        tabla, col = categoria
        from_.append({"Name": "c", "Entity": tabla, "Type": 0})
        select.append(_columna(tabla, col, "c"))
        proyecciones.setdefault(rol_cat, []).append({"queryRef": f"{tabla}.{col}"})

    if serie:
        tabla, col = serie
        from_.append({"Name": "s", "Entity": tabla, "Type": 0})
        select.append(_columna(tabla, col, "s"))
        proyecciones.setdefault("Series", []).append({"queryRef": f"{tabla}.{col}"})

    if medidas:
        from_.append({"Name": "m", "Entity": "_Medidas", "Type": 0})
        for i, nm in enumerate(medidas):
            select.append(_medida(nm))
            # El scatter necesita X e Y en ejes distintos: la primera medida
            # va al eje X y la segunda al Y.
            rol = "Y" if (tipo == "scatterChart" and i == 1) else rol_med
            proyecciones.setdefault(rol, []).append({"queryRef": f"_Medidas.{nm}"})

    objetos = {}
    if titulo:
        objetos["title"] = [{
            "properties": {
                "show": {"expr": {"Literal": {"Value": "true"}}},
                "text": {"expr": {"Literal": {"Value": f"'{titulo}'"}}},
                "fontSize": {"expr": {"Literal": {"Value": "11D"}}},
            }
        }]

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


def texto(x, y, w, h, contenido: str, tamano=12, z=0) -> dict:
    """Cuadro de texto — se usa para las notas metodológicas fijas."""
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


def pagina(nombre: str, visuales: list[dict], ordinal: int) -> dict:
    return {
        "name": uuid.uuid4().hex[:20],
        "displayName": nombre,
        "displayOption": 1,
        "width": ANCHO,
        "height": ALTO,
        "ordinal": ordinal,
        "visualContainers": visuales,
        "config": json.dumps({}),
        "filters": "[]",
    }


# ---- páginas por tablero -------------------------------------------------

FILA_KPI = 78
ALTO_KPI = 96


def kpis(nombres: list[str], y=FILA_KPI) -> list[dict]:
    ancho = (ANCHO - 40 - 12 * (len(nombres) - 1)) // len(nombres)
    return [
        visual("card", 20 + i * (ancho + 12), y, ancho, ALTO_KPI,
               medidas=[n], titulo=n)
        for i, n in enumerate(nombres)
    ]


def encabezado(titulo: str, subtitulo: str) -> list[dict]:
    return [
        texto(20, 14, 760, 54, titulo, 20),
        texto(800, 20, 460, 46,
              "Estado del dato: ver medidas Encabezado de Confianza y Estado de Vigencia", 10),
        texto(20, 52, 760, 24, subtitulo, 11),
    ]


def paginas_var() -> list[dict]:
    p = []
    v = encabezado("VAR · Resumen ejecutivo",
                   "Ventas netas, cumplimiento, share y margen — con el origen de la variación")
    v += kpis(["Ventas Netas USD", "Var % vs AA", "Cumplimiento %",
               "Market Share Valores %", "Margen Bruto %"])
    v += [
        visual("lineClusteredColumnComboChart", 20, 190, 760, 300,
               medidas=["Ventas Netas USD", "Objetivo USD"],
               categoria=("v_dim_calendario", "Año-Mes"),
               titulo="Ventas netas vs objetivo por mes"),
        visual("clusteredBarChart", 796, 190, 464, 300,
               medidas=["Ventas Netas USD"],
               categoria=("v_dim_filial", "País"),
               titulo="Ventas por filial"),
        visual("clusteredBarChart", 20, 502, 496, 198,
               medidas=["Ventas Netas USD"],
               categoria=("v_dim_producto", "Marca"),
               titulo="Top productos"),
        visual("tableEx", 532, 502, 728, 198,
               medidas=["Ventas Netas USD", "Var % vs AA", "Cumplimiento %",
                        "Market Share Valores %", "Var Share pp"],
               categoria=("v_dim_filial", "País"),
               titulo="Detalle por filial"),
    ]
    p.append(pagina("1 · Resumen ejecutivo", v, 0))

    v = encabezado("VAR · Puente Precio – Volumen – Mix",
                   "De dónde viene exactamente la variación contra el año anterior")
    v += kpis(["Var USD vs AA", "Efecto Volumen USD", "Efecto Precio USD",
               "Efecto Mix USD", "Control Cierre del Puente"])
    v += [
        visual("waterfallChart", 20, 190, 1240, 300,
               medidas=["Var USD vs AA"],
               categoria=("v_dim_calendario", "Año-Mes"),
               titulo="Variación mes a mes"),
        visual("tableEx", 20, 502, 1240, 198,
               medidas=["Efecto Volumen USD", "Efecto Precio USD", "Efecto Mix USD",
                        "Var USD vs AA"],
               categoria=("v_dim_producto", "Clase terapéutica"),
               titulo="Descomposición por clase terapéutica"),
    ]
    p.append(pagina("2 · Puente Precio-Volumen-Mix", v, 1))

    v = encabezado("VAR · Sell-in vs Sell-out",
                   "La carga de canal de hoy es la devolución del mes que viene")
    v += kpis(["Unidades", "Sell-out Unidades", "Brecha Sell-in vs Sell-out %",
               "Market Share Unidades %"])
    v += [
        visual("lineChart", 20, 190, 760, 300,
               medidas=["Unidades", "Sell-out Unidades"],
               categoria=("v_dim_calendario", "Año-Mes"),
               titulo="Sell-in vs sell-out por mes"),
        visual("scatterChart", 796, 190, 464, 300,
               medidas=["Brecha Sell-in vs Sell-out %", "Tasa de Devolución Valor %"],
               categoria=("v_dim_producto", "SKU"),
               titulo="Brecha de canal vs devoluciones"),
        visual("tableEx", 20, 502, 1240, 198,
               medidas=["Unidades", "Sell-out Unidades",
                        "Brecha Sell-in vs Sell-out %", "Alerta de Carga de Canal"],
               categoria=("v_dim_filial", "País"),
               titulo="Estado del canal por filial"),
    ]
    p.append(pagina("3 · Sell-in vs Sell-out", v, 2))
    return p


def paginas_ofertas() -> list[dict]:
    p = []
    v = encabezado("Ofertas · Retorno de la política comercial",
                   "Cuánto cuesta el descuento y cuánto margen devuelve")
    v += kpis(["Inversión Comercial USD", "Inversión sobre Ventas %",
               "Tasa de Aceptación %", "ROI de Ofertas", "Semáforo de ROI"])
    v += [
        visual("lineClusteredColumnComboChart", 20, 190, 760, 300,
               medidas=["Inversión Comercial USD", "Ventas con Oferta USD"],
               categoria=("v_dim_calendario", "Año-Mes"),
               titulo="Inversión comercial y ventas con oferta"),
        visual("clusteredBarChart", 796, 190, 464, 300,
               medidas=["Margen por USD Invertido"],
               categoria=("v_dim_tipo_oferta", "Tipo de oferta"),
               titulo="Eficiencia por instrumento"),
        visual("clusteredColumnChart", 20, 502, 496, 148,
               medidas=["Inversión Comercial USD"],
               categoria=("v_dim_cliente", "Segmento"),
               titulo="Inversión por segmento de cliente"),
        visual("tableEx", 532, 502, 728, 148,
               medidas=["Inversión Comercial USD", "Tasa de Aceptación %",
                        "ROI de Ofertas"],
               categoria=("v_dim_filial", "País"),
               titulo="Detalle por filial"),
        texto(20, 658, 1240, 44,
              "ROI comparativo, no causal: incluye ventas que podrían haber "
              "ocurrido sin oferta. Para medir impacto incremental hace falta "
              "un grupo de control.", 10),
    ]
    p.append(pagina("1 · Retorno de la política", v, 0))

    v = encabezado("Ofertas · Recomendación del motor de IA",
                   "Qué ofertar, a qué precio, en qué segmento y por qué")
    v += kpis(["Recomendaciones Activas", "Ganancia Estimada USD",
               "Stock Rescatado USD", "Descuento Recomendado %",
               "Recomendaciones que Requieren Test"])
    v += [
        visual("tableEx", 20, 190, 760, 320,
               medidas=["Descuento Recomendado %", "Ganancia Estimada USD",
                        "Stock Rescatado USD"],
               categoria=("v_fact_recomendaciones", "SKU recomendado"),
               titulo="Recomendaciones por SKU"),
        visual("clusteredBarChart", 796, 190, 464, 320,
               medidas=["Ganancia Estimada USD"],
               categoria=("v_fact_recomendaciones", "Segmento recomendado"),
               titulo="Ganancia estimada por segmento"),
        visual("card", 20, 522, 1240, 180,
               medidas=["Justificativo Seleccionado"],
               titulo="Por qué el motor propone esta oferta"),
    ]
    p.append(pagina("2 · Recomendación de IA", v, 1))

    v = encabezado("Ofertas · Proyección de inversión",
                   "Cuánto va a costar la política comercial el mes que viene")
    v += kpis(["Inversión Comercial USD", "Inversión Proyectada USD",
               "Desvío del Forecast %", "Precisión del Forecast %"])
    v += [
        visual("lineChart", 20, 190, 1240, 320,
               medidas=["Inversión Comercial USD", "Inversión Proyectada USD"],
               categoria=("v_dim_calendario", "Año-Mes"),
               titulo="Inversión real vs proyectada"),
        visual("tableEx", 20, 522, 1240, 180,
               medidas=["Inversión Comercial USD", "Inversión Proyectada USD",
                        "Desvío del Forecast %"],
               categoria=("v_dim_filial", "País"),
               titulo="Desvío por filial"),
    ]
    p.append(pagina("3 · Proyección de inversión", v, 2))
    return p


def paginas_logistica() -> list[dict]:
    p = []
    v = encabezado("Logística · Nivel de servicio",
                   "Entregas a tiempo y completas, y quién las está fallando")
    v += kpis(["OTIF %", "Fill Rate %", "Lead Time Promedio",
               "Exceso sobre SLA", "Semáforo OTIF"])
    v += [
        visual("lineChart", 20, 190, 760, 300,
               medidas=["OTIF %", "Fill Rate %"],
               categoria=("v_dim_calendario", "Año-Mes"),
               titulo="OTIF y fill rate por mes"),
        visual("clusteredBarChart", 796, 190, 464, 300,
               medidas=["OTIF %"],
               categoria=("v_dim_transportista", "Transportista"),
               titulo="OTIF por transportista"),
        visual("tableEx", 20, 502, 760, 150,
               medidas=["OTIF %", "Lead Time Promedio", "Líneas Despachadas"],
               categoria=("v_dim_filial", "País"),
               titulo="Nivel de servicio por filial"),
        visual("card", 796, 502, 464, 150,
               medidas=["Alerta de Cadena de Frío"],
               titulo="Cadena de frío"),
    ]
    p.append(pagina("1 · Nivel de servicio", v, 0))

    v = encabezado("Logística · Devoluciones",
                   "Cuánto vuelve, por qué motivo y cuánto de eso era evitable")
    v += kpis(["Tasa de Devolución Valor %", "Var Tasa Devolución pp",
               "% Devoluciones Evitables", "Margen Perdido por Devoluciones USD"])
    v += [
        visual("clusteredBarChart", 20, 190, 620, 300,
               medidas=["Importe Devuelto USD"],
               categoria=("v_dim_motivo_devolucion", "Motivo de devolución"),
               titulo="Devoluciones por motivo"),
        visual("clusteredColumnChart", 656, 190, 604, 300,
               medidas=["Importe Devuelto USD"],
               categoria=("v_dim_motivo_devolucion", "Área responsable"),
               titulo="Devoluciones por área responsable"),
        visual("tableEx", 20, 502, 1240, 200,
               medidas=["Importe Devuelto USD", "Tasa de Devolución Valor %",
                        "% Devoluciones Evitables"],
               categoria=("v_dim_filial", "País"),
               titulo="Detalle por filial"),
    ]
    p.append(pagina("2 · Devoluciones", v, 1))

    v = encabezado("Logística · Riesgo predictivo",
                   "Qué pedidos revisar ANTES de despachar")
    v += kpis(["Pedidos en Riesgo Crítico", "Importe en Riesgo USD",
               "Probabilidad Media de Devolución",
               "Captura en el Top 10% de Riesgo"])
    v += [
        visual("clusteredColumnChart", 20, 190, 620, 300,
               medidas=["Importe en Riesgo USD"],
               categoria=("v_fact_scoring_devoluciones", "Banda de riesgo"),
               titulo="Exposición por banda de riesgo"),
        visual("card", 656, 190, 604, 140,
               medidas=["Lectura del Modelo de Riesgo"],
               titulo="Lectura operativa del modelo"),
        visual("clusteredBarChart", 656, 342, 604, 148,
               medidas=["Importe en Riesgo USD"],
               categoria=("v_dim_transportista", "Transportista"),
               titulo="Riesgo por transportista"),
        visual("tableEx", 20, 502, 1240, 200,
               medidas=["Importe en Riesgo USD", "Probabilidad Media de Devolución",
                        "Pedidos en Riesgo Crítico"],
               categoria=("v_dim_cliente", "Cliente"),
               titulo="Clientes con mayor exposición"),
    ]
    p.append(pagina("3 · Riesgo predictivo", v, 2))

    v = encabezado("Logística · Stock y vencimientos",
                   "Dónde hay sobrestock y qué está por vencer")
    v += kpis(["Valor de Stock USD", "Días de Cobertura", "Unidades por Vencer",
               "Valor en Riesgo de Vencimiento USD", "Estado de Cobertura"])
    v += [
        visual("clusteredBarChart", 20, 190, 620, 300,
               medidas=["Días de Cobertura"],
               categoria=("v_dim_deposito", "Depósito"),
               titulo="Cobertura por depósito"),
        visual("clusteredBarChart", 656, 190, 604, 300,
               medidas=["Valor en Riesgo de Vencimiento USD"],
               categoria=("v_dim_producto", "SKU"),
               titulo="Valor en riesgo de vencimiento por SKU"),
        visual("tableEx", 20, 502, 1240, 200,
               medidas=["Stock Unidades", "Días de Cobertura", "Unidades por Vencer",
                        "Valor en Riesgo de Vencimiento USD", "Estado de Cobertura"],
               categoria=("v_dim_producto", "Clase terapéutica"),
               titulo="Stock por clase terapéutica"),
    ]
    p.append(pagina("4 · Stock y vencimientos", v, 3))
    return p


PAGINAS = {"VAR": paginas_var, "Ofertas": paginas_ofertas, "Logistica": paginas_logistica}


def construir_layout(tablero: str) -> dict:
    return {
        "id": 0,
        "resourcePackages": [],
        "sections": PAGINAS[tablero](),
        # Configuración mínima a propósito: no se fija tema ni versión de
        # esquema, para no depender de qué build de Desktop abra el archivo.
        "config": json.dumps({
            "activeSectionIndex": 0,
            "defaultDrillFilterOtherVisuals": True,
        }),
        "layoutOptimization": 0,
    }


# ==========================================================================
# 5 · Escritura de archivos
# ==========================================================================
def _u16(texto_json: str) -> bytes:
    """Las partes internas de un .pbit van en UTF-16 LE con BOM."""
    return b"\xff\xfe" + texto_json.encode("utf-16-le")


CONTENT_TYPES = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="json" ContentType="" />'
    '<Override PartName="/Version" ContentType="" />'
    '<Override PartName="/Report/Layout" ContentType="" />'
    '<Override PartName="/Settings" ContentType="" />'
    '<Override PartName="/Metadata" ContentType="" />'
    '<Override PartName="/DataModelSchema" ContentType="" />'
    "</Types>"
)


def escribir_pbit(tablero: str, modelo: dict, layout: dict) -> Path:
    destino = SALIDA / f"Adium_{tablero}.pbit"
    metadata = {
        "Version": 3,
        "AutoCreatedRelationships": [],
        "FileDescription": esq.TABLEROS[tablero]["titulo"],
        "CreatedFrom": "Cloud",
    }
    settings = {"Version": 4, "ReportSettings": {"UseStylableVisualContainerHeader": True}}

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("Version", _u16("1.28"))
        z.writestr("DataModelSchema", _u16(json.dumps(modelo, ensure_ascii=False)))
        z.writestr("Report/Layout", _u16(json.dumps(layout, ensure_ascii=False)))
        z.writestr("Settings", _u16(json.dumps(settings, ensure_ascii=False)))
        z.writestr("Metadata", _u16(json.dumps(metadata, ensure_ascii=False)))
    return destino


def escribir_pbip(tablero: str, modelo: dict, layout: dict) -> Path:
    base = SALIDA / f"Adium_{tablero}"
    sm = base.parent / f"Adium_{tablero}.SemanticModel"
    rp = base.parent / f"Adium_{tablero}.Report"
    sm.mkdir(exist_ok=True)
    rp.mkdir(exist_ok=True)

    def esc(p: Path, obj):
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

    esc(sm / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": f"Adium_{tablero}"},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"sm{tablero}"))},
    })
    esc(sm / "definition.pbism", {"version": "1.0", "settings": {}})
    esc(sm / "model.bim", modelo)

    esc(rp / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": f"Adium_{tablero}"},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"rp{tablero}"))},
    })
    esc(rp / "definition.pbir", {
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../Adium_{tablero}.SemanticModel"}},
    })
    esc(rp / "report.json", layout)

    pbip = base.with_suffix(".pbip")
    esc(pbip, {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"Adium_{tablero}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    return pbip


# ==========================================================================
def main() -> None:
    print("Generando archivos de Power BI para los tres tableros\n")
    for tablero, cfg in esq.TABLEROS.items():
        medidas = cargar_medidas(cfg["dax"])
        modelo = construir_modelo(f"Adium_{tablero}", medidas)
        layout = construir_layout(tablero)

        pbit = escribir_pbit(tablero, modelo, layout)
        pbip = escribir_pbip(tablero, modelo, layout)

        n_tablas = len(modelo["model"]["tables"])
        n_rel = len(modelo["model"]["relationships"])
        n_pag = len(layout["sections"])
        n_vis = sum(len(s["visualContainers"]) for s in layout["sections"])
        print(f"  {tablero:<10} {len(medidas):>3} medidas · {n_tablas} tablas · "
              f"{n_rel} relaciones · {n_pag} páginas · {n_vis} visuales")
        print(f"             {pbit.name}  ({pbit.stat().st_size / 1024:.0f} KB)")
        print(f"             {pbip.name}  (+ carpetas .SemanticModel y .Report)")

    print(f"\n  OK → {SALIDA}")
    print("  Abrí el .pbit con doble clic, confirmá la carpeta de datos,")
    print("  y después Archivo → Guardar como → .pbix")


if __name__ == "__main__":
    main()
