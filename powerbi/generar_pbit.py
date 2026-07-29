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

import argparse
import json
import re
import unicodedata
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
SERVIDOR_DEFECTO = "localhost"
BASE_DEFECTO = "AdiumBI"
ORIGEN_DEFECTO = "Parquet"


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
    Genera la consulta M de una tabla, con DOS orígenes conmutables.

        OrigenDatos = "SQL Server"  →  las vistas star.v_* de la base
        OrigenDatos = "Parquet"     →  los archivos de data/star

    Es un parámetro, no dos versiones del archivo: se cambia en
    Inicio → Transformar datos → Administrar parámetros, sin tocar una consulta.

    Los dos caminos CONVERGEN en el mismo conjunto de columnas con nombres de
    negocio, y recién ahí siguen los pasos comunes. Esa convergencia es lo que
    permite que las 117 medidas DAX funcionen igual con cualquiera de los dos
    orígenes: el modelo semántico no se entera de dónde vino el dato.

    La rama SQL lee las VISTAS, que ya devuelven los nombres finales y las
    columnas derivadas. La rama Parquet tiene que reproducir eso en M. Por eso
    las vistas son el contrato: la lógica canónica vive en SQL y M la replica,
    no al revés.
    """
    origen = cfg["origen"]
    lineas = ["let"]

    # ---------- rama SQL Server: la vista ya viene lista ----------
    lineas.append(
        f'    FuenteSQL = () => Sql.Database(ServidorSQL, BaseSQL)'
        f'{{[Schema="star", Item="{tabla}"]}}[Data],'
    )

    # ---------- rama Parquet: hay que construir lo que la vista ya hace ----------
    lineas.append("    FuenteParquet = () =>")
    lineas.append("        let")
    lineas.append(
        f'            Crudo = Parquet.Document(File.Contents(RutaDatos & "\\{origen}.parquet")),'
    )
    paso = "Crudo"

    # aplanado de dimensiones satélite (desnormalización de estrella)
    if tabla in esq.APLANAR:
        ap = esq.APLANAR[tabla]
        cols = list(ap["columnas"])
        lineas.append(
            f'            Satelite = Parquet.Document(File.Contents(RutaDatos & "\\{ap["tabla"]}.parquet")),'
        )
        lineas.append(
            f'            Unido = Table.NestedJoin({paso}, {{"{ap["clave"]}"}}, Satelite, '
            f'{{"{ap["clave"]}"}}, "_sat", JoinKind.LeftOuter),'
        )
        lineas.append(
            '            Expandido = Table.ExpandTableColumn(Unido, "_sat", '
            + _m_lista(cols)
            + ", "
            + _m_lista([ap["columnas"][c] for c in cols])
            + "),"
        )
        paso = "Expandido"

    # columnas derivadas
    for i, d in enumerate(esq.DERIVADAS.get(tabla, [])):
        nuevo = f"Derivada{i}"
        lineas.append(
            f'            {nuevo} = Table.AddColumn({paso}, "{d["nombre"]}", '
            f'each {d["m"]}, {d["tipo_m"]}),'
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
            f"            Renombrado = Table.RenameColumns({paso}, "
            + _m_lista(renombres)
            + ")"
        )
        paso = "Renombrado"
    else:
        lineas[-1] = lineas[-1].rstrip(",")

    lineas.append("        in")
    lineas.append(f"            {paso},")

    # ---------- convergencia ----------
    lineas.append(
        '    Origen = if OrigenDatos = "SQL Server" then FuenteSQL() else FuenteParquet(),'
    )
    paso = "Origen"

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
def _parametro(nombre: str, valor: str, descripcion: str,
               permitidos: list[str] | None = None) -> dict:
    """
    Parámetro de Power Query.

    Va en `model.expressions`, no como tabla: un parámetro es un valor escalar
    reutilizable. Declarado como tabla, la concatenación de ruta no compila.
    """
    meta = 'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true'
    if permitidos:
        # Lista cerrada: el usuario elige de un desplegable en vez de tipear
        # "SQL server" y pasar media hora buscando por qué no carga.
        meta += ", AllowedValues = " + _m_lista(permitidos)
    meta += "]"
    return {
        "name": nombre,
        "kind": "m",
        "description": descripcion,
        "expression": [_m_texto(valor), "    " + meta],
        "annotations": [{"name": "PBI_ResultType", "value": "Text"}],
    }


def parametros() -> list[dict]:
    return [
        _parametro(
            "OrigenDatos", ORIGEN_DEFECTO,
            "De dónde lee el modelo. 'Parquet' usa los archivos locales que "
            "genera el pipeline; 'SQL Server' se conecta a las vistas star.v_* "
            "del data warehouse. Las 117 medidas funcionan igual con los dos.",
            ["Parquet", "SQL Server"],
        ),
        _parametro(
            "RutaDatos", RUTA_DATOS_DEFECTO,
            "Solo para OrigenDatos = 'Parquet'. Carpeta con los .parquet del "
            "modelo estrella (la que genera `python src/run_all.py`). "
            "Ruta absoluta, sin barra final.",
        ),
        _parametro(
            "ServidorSQL", SERVIDOR_DEFECTO,
            "Solo para OrigenDatos = 'SQL Server'. Instancia donde se "
            "desplegaron los scripts de sql/.",
        ),
        _parametro(
            "BaseSQL", BASE_DEFECTO,
            "Solo para OrigenDatos = 'SQL Server'. Base de datos que contiene "
            "el esquema star.",
        ),
    ]



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
            "expressions": parametros(),
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
                 "value": json.dumps([p["name"] for p in parametros()] + list(esq.TABLAS) + ["_Medidas"], ensure_ascii=False)},
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
        # Nombre determinístico, no aleatorio: los botones de navegación
        # referencian la sección por nombre. Un GUID nuevo en cada corrida
        # dejaría todos los botones apuntando al vacío.
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


# ---- composición de páginas ----------------------------------------------
#
# Ritmo vertical fijo en las tres páginas de los tres tableros. Que un KPI esté
# siempre en el mismo lugar no es estética: es lo que permite que alguien pase
# de una página a otra sin volver a buscar dónde está cada cosa.
#
#   0 –  36   barra de navegación (botones)
#  40 –  96   título, subtítulo y estado del dato
# 100 – 132   slicers
# 136 – 232   fila de KPI
# 236 – 700   análisis
#
FILA_NAV, ALTO_NAV = 4, 32
FILA_TITULO = 44
FILA_SLICER, ALTO_SLICER = 100, 32
FILA_KPI, ALTO_KPI = 136, 96
FILA_CONTENIDO = 244
MARGEN = 20


def _slug(titulo: str) -> str:
    """
    Nombre estable de sección.

    Tiene que ser determinístico: los botones de navegación referencian la
    sección por nombre, así que un GUID aleatorio en cada corrida rompería
    todos los botones en la siguiente regeneración.
    """
    limpio = "".join(
        c if c.isalnum() else "_"
        for c in unicodedata.normalize("NFKD", titulo)
        .encode("ascii", "ignore").decode()
    )
    return "s" + re.sub(r"_+", "_", limpio).strip("_").lower()


def boton_navegacion(x, y, w, h, etiqueta: str, destino: str, activo: bool = False) -> dict:
    """
    Botón que navega a otra página del reporte.

    La acción vive en `vcObjects.visualLink` con `type = PageNavigation` y el
    nombre de la sección destino. Es lo que hace que el botón realmente
    funcione al hacer clic, en vez de ser un rectángulo con texto.
    """
    def lit(v):
        return {"expr": {"Literal": {"Value": v}}}

    fondo = "'#0B3C5D'" if activo else "'#FFFFFF'"
    letra = "'#FFFFFF'" if activo else "'#0B3C5D'"

    conf = {
        "name": uuid.uuid5(uuid.NAMESPACE_DNS, f"btn{destino}{etiqueta}{x}").hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 100,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "actionButton",
            "objects": {
                "icon": [{"properties": {"shapeType": lit("'blank'")},
                          "selector": {"id": "default"}}],
                "text": [{"properties": {
                    "show": lit("true"),
                    "text": lit(f"'{etiqueta}'"),
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
                    "lineColor": {"solid": {"color": lit("'#0B3C5D'")}},
                    "weight": lit("1D"),
                }, "selector": {"id": "default"}}],
            },
            "vcObjects": {
                "visualLink": [{"properties": {
                    "show": lit("true"),
                    "type": lit("'PageNavigation'"),
                    "navigationSection": lit(f"'{destino}'"),
                }}],
            },
            "drillFilterOtherVisuals": True,
        },
    }
    return {"x": x, "y": y, "z": 100, "width": w, "height": h,
            "config": json.dumps(conf, ensure_ascii=False)}


def barra_navegacion(titulos: list[str], actual: str) -> list[dict]:
    """Los botones de todas las páginas del reporte, con la actual resaltada."""
    ancho = min(190, (ANCHO - 2 * MARGEN) // max(len(titulos), 1) - 6)
    return [
        boton_navegacion(MARGEN + i * (ancho + 6), FILA_NAV, ancho, ALTO_NAV,
                         t, _slug(t), activo=(t == actual))
        for i, t in enumerate(titulos)
    ]


def slicer(x, y, w, h, tabla: str, columna: str, titulo: str) -> dict:
    """Segmentación. Filtra todos los visuales de la página."""
    conf = {
        "name": uuid.uuid5(uuid.NAMESPACE_DNS, f"sl{tabla}{columna}{x}{y}").hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 50,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "slicer",
            "projections": {"Values": [{"queryRef": f"{tabla}.{columna}"}]},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "c", "Entity": tabla, "Type": 0}],
                "Select": [_columna(tabla, columna, "c")],
            },
            "objects": {
                "general": [{"properties": {
                    # Desplegable y no lista: en una página con 8 visuales, tres
                    # slicers en formato lista se comen la mitad del espacio.
                    "outlineColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#C9D0CC'"}}}}},
                    "outlineWeight": {"expr": {"Literal": {"Value": "1D"}}},
                }}],
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


def fila_slicers() -> list[dict]:
    """
    Los mismos tres cortes en todas las páginas, en el mismo lugar.

    Filial, período y clase terapéutica son los tres ejes por los que el
    negocio pregunta siempre. Ponerlos fijos evita que cada página invente su
    propio juego de filtros y que el usuario pierda el contexto al navegar.
    """
    ancho = (ANCHO - 2 * MARGEN - 2 * 10) // 3
    return [
        slicer(MARGEN, FILA_SLICER, ancho, ALTO_SLICER,
               "v_dim_filial", "País", "Filial"),
        slicer(MARGEN + ancho + 10, FILA_SLICER, ancho, ALTO_SLICER,
               "v_dim_calendario", "Año-Mes", "Período"),
        slicer(MARGEN + 2 * (ancho + 10), FILA_SLICER, ancho, ALTO_SLICER,
               "v_dim_producto", "Clase terapéutica", "Clase terapéutica"),
    ]


def kpis(nombres: list[str], y=FILA_KPI) -> list[dict]:
    ancho = (ANCHO - 2 * MARGEN - 12 * (len(nombres) - 1)) // len(nombres)
    return [
        visual("card", MARGEN + i * (ancho + 12), y, ancho, ALTO_KPI,
               medidas=[n], titulo=n)
        for i, n in enumerate(nombres)
    ]


def encabezado(titulo: str, subtitulo: str) -> list[dict]:
    return [
        texto(MARGEN, FILA_TITULO, 700, 30, titulo, 18),
        texto(MARGEN, FILA_TITULO + 28, 700, 24, subtitulo, 10),
        # El estado del dato va VISIBLE, no en un tooltip. Cuando el negocio ve
        # el estado del dato, empieza a cuidarlo — y un tablero que no dice
        # cuándo se actualizó es un tablero en el que no se puede confiar.
        visual("card", 740, FILA_TITULO - 4, 250, 52,
               medidas=["Encabezado de Confianza"], titulo="Calidad"),
        visual("card", 1000, FILA_TITULO - 4, 260, 52,
               medidas=["Estado de Vigencia"], titulo="Vigencia"),
    ]


def armar(titulos: list[str], actual: str, subtitulo: str,
          kpi: list[str], contenido: list[dict], ordinal: int) -> dict:
    """Compone una página completa con el ritmo vertical fijo."""
    visuales = (
        barra_navegacion(titulos, actual)
        + encabezado(actual.split(" · ", 1)[-1], subtitulo)
        + fila_slicers()
        + kpis(kpi)
        + contenido
    )
    return pagina(actual, visuales, ordinal)


# ---- páginas por tablero -------------------------------------------------

Y0 = FILA_CONTENIDO
ALTO_LIBRE = 700 - Y0


def paginas_var() -> list[dict]:
    T = ["1 · Resumen ejecutivo", "2 · Puente Precio-Volumen-Mix",
         "3 · Sell-in vs Sell-out", "4 · Detalle"]
    p = []

    p.append(armar(T, T[0],
        "Ventas netas, cumplimiento, share y margen — con el origen de la variación",
        ["Ventas Netas USD", "Var % vs AA", "Cumplimiento %",
         "Market Share Valores %", "Margen Bruto %"],
        [
            visual("lineClusteredColumnComboChart", MARGEN, Y0, 760, 280,
                   medidas=["Ventas Netas USD", "Objetivo USD"],
                   categoria=("v_dim_calendario", "Año-Mes"),
                   titulo="Ventas netas vs objetivo por mes"),
            visual("clusteredBarChart", 796, Y0, 464, 280,
                   medidas=["Ventas Netas USD"],
                   categoria=("v_dim_filial", "País"),
                   titulo="Ventas por filial"),
            visual("clusteredBarChart", MARGEN, Y0 + 292, 496, 164,
                   medidas=["Ventas Netas USD"],
                   categoria=("v_dim_producto", "Marca"),
                   titulo="Top productos"),
            visual("card", 532, Y0 + 292, 728, 164,
                   medidas=["Origen de la Variación de Share"],
                   titulo="¿Caí yo o creció el mercado?"),
        ], 0))

    p.append(armar(T, T[1],
        "De dónde viene exactamente la variación contra el año anterior",
        ["Var USD vs AA", "Efecto Volumen USD", "Efecto Precio USD",
         "Efecto Mix USD", "Control Cierre del Puente"],
        [
            visual("waterfallChart", MARGEN, Y0, 1240, 280,
                   medidas=["Var USD vs AA"],
                   categoria=("v_dim_calendario", "Año-Mes"),
                   titulo="Variación mes a mes"),
            visual("tableEx", MARGEN, Y0 + 292, 1240, 164,
                   medidas=["Efecto Volumen USD", "Efecto Precio USD",
                            "Efecto Mix USD", "Var USD vs AA"],
                   categoria=("v_dim_producto", "Clase terapéutica"),
                   titulo="Descomposición por clase terapéutica"),
        ], 1))

    p.append(armar(T, T[2],
        "La carga de canal de hoy es la devolución del mes que viene",
        ["Unidades", "Sell-out Unidades", "Brecha Sell-in vs Sell-out %",
         "Market Share Unidades %"],
        [
            visual("lineChart", MARGEN, Y0, 760, 280,
                   medidas=["Unidades", "Sell-out Unidades"],
                   categoria=("v_dim_calendario", "Año-Mes"),
                   titulo="Sell-in vs sell-out por mes"),
            visual("scatterChart", 796, Y0, 464, 280,
                   medidas=["Brecha Sell-in vs Sell-out %",
                            "Tasa de Devolución Valor %"],
                   categoria=("v_dim_producto", "SKU"),
                   titulo="Brecha de canal vs devoluciones"),
            visual("card", MARGEN, Y0 + 292, 1240, 164,
                   medidas=["Alerta de Carga de Canal"],
                   titulo="Estado del canal"),
        ], 2))

    p.append(armar(T, T[3],
        "Bajar al grano cuando un número de arriba llama la atención",
        ["Ventas Netas USD", "Unidades", "Precio Promedio USD",
         "Descuento Efectivo %", "Margen Bruto %"],
        [
            visual("tableEx", MARGEN, Y0, 1240, 456,
                   medidas=["Ventas Netas USD", "Unidades", "Precio Promedio USD",
                            "Descuento Efectivo %", "Margen Bruto %"],
                   categoria=("v_dim_cliente", "Cliente"),
                   titulo="Detalle por cliente"),
        ], 3))
    return p


def paginas_ofertas() -> list[dict]:
    T = ["1 · Retorno de la política", "2 · Recomendación de IA",
         "3 · Proyección de inversión"]
    p = []

    p.append(armar(T, T[0],
        "Cuánto cuesta el descuento y cuánto margen devuelve",
        ["Inversión Comercial USD", "Inversión sobre Ventas %",
         "Tasa de Aceptación %", "ROI de Ofertas", "Semáforo de ROI"],
        [
            visual("lineClusteredColumnComboChart", MARGEN, Y0, 760, 268,
                   medidas=["Inversión Comercial USD", "Ventas con Oferta USD"],
                   categoria=("v_dim_calendario", "Año-Mes"),
                   titulo="Inversión comercial y ventas con oferta"),
            visual("clusteredBarChart", 796, Y0, 464, 268,
                   medidas=["Margen por USD Invertido"],
                   categoria=("v_dim_tipo_oferta", "Tipo de oferta"),
                   titulo="Eficiencia por instrumento"),
            visual("clusteredColumnChart", MARGEN, Y0 + 280, 496, 130,
                   medidas=["Inversión Comercial USD"],
                   categoria=("v_dim_cliente", "Segmento"),
                   titulo="Inversión por segmento de cliente"),
            visual("tableEx", 532, Y0 + 280, 728, 130,
                   medidas=["Inversión Comercial USD", "Tasa de Aceptación %",
                            "ROI de Ofertas"],
                   categoria=("v_dim_filial", "País"),
                   titulo="Detalle por filial"),
            # La advertencia va FIJA en la página, no en un tooltip: es lo que
            # evita que alguien cite este ROI en un comité como impacto causal.
            texto(MARGEN, Y0 + 418, 1240, 38,
                  "ROI comparativo, no causal: incluye ventas que podrían haber "
                  "ocurrido sin oferta. Para medir impacto incremental hace "
                  "falta un grupo de control.", 10),
        ], 0))

    p.append(armar(T, T[1],
        "Qué ofertar, a qué precio, en qué segmento y por qué",
        ["Recomendaciones Activas", "Ganancia Estimada USD",
         "Stock Rescatado USD", "Descuento Recomendado %",
         "Recomendaciones que Requieren Test"],
        [
            visual("tableEx", MARGEN, Y0, 760, 280,
                   medidas=["Descuento Recomendado %", "Ganancia Estimada USD",
                            "Stock Rescatado USD"],
                   categoria=("v_fact_recomendaciones", "SKU recomendado"),
                   titulo="Recomendaciones por SKU"),
            visual("clusteredBarChart", 796, Y0, 464, 280,
                   medidas=["Ganancia Estimada USD"],
                   categoria=("v_fact_recomendaciones", "Segmento recomendado"),
                   titulo="Ganancia estimada por segmento"),
            # El justificativo ocupa el ancho completo a propósito: una
            # recomendación que un comercial no puede discutir es una
            # recomendación que no va a aplicar.
            visual("card", MARGEN, Y0 + 292, 1240, 164,
                   medidas=["Justificativo Seleccionado"],
                   titulo="Por qué el motor propone esta oferta"),
        ], 1))

    p.append(armar(T, T[2],
        "Cuánto va a costar la política comercial el mes que viene",
        ["Inversión Comercial USD", "Inversión Proyectada USD",
         "Desvío del Forecast %", "Precisión del Forecast %"],
        [
            visual("lineChart", MARGEN, Y0, 1240, 280,
                   medidas=["Inversión Comercial USD", "Inversión Proyectada USD"],
                   categoria=("v_dim_calendario", "Año-Mes"),
                   titulo="Inversión real vs proyectada"),
            visual("tableEx", MARGEN, Y0 + 292, 1240, 164,
                   medidas=["Inversión Comercial USD", "Inversión Proyectada USD",
                            "Desvío del Forecast %"],
                   categoria=("v_dim_filial", "País"),
                   titulo="Desvío por filial"),
        ], 2))
    return p


def paginas_logistica() -> list[dict]:
    T = ["1 · Nivel de servicio", "2 · Devoluciones",
         "3 · Riesgo predictivo", "4 · Stock y vencimientos"]
    p = []

    p.append(armar(T, T[0],
        "Entregas a tiempo y completas, y quién las está fallando",
        ["OTIF %", "Fill Rate %", "Lead Time Promedio",
         "Exceso sobre SLA", "Semáforo OTIF"],
        [
            visual("lineChart", MARGEN, Y0, 760, 280,
                   medidas=["OTIF %", "Fill Rate %"],
                   categoria=("v_dim_calendario", "Año-Mes"),
                   titulo="OTIF y fill rate por mes"),
            visual("clusteredBarChart", 796, Y0, 464, 280,
                   medidas=["OTIF %"],
                   categoria=("v_dim_transportista", "Transportista"),
                   titulo="OTIF por transportista"),
            visual("tableEx", MARGEN, Y0 + 292, 760, 164,
                   medidas=["OTIF %", "Lead Time Promedio", "Líneas Despachadas"],
                   categoria=("v_dim_filial", "País"),
                   titulo="Nivel de servicio por filial"),
            visual("card", 796, Y0 + 292, 464, 164,
                   medidas=["Alerta de Cadena de Frío"],
                   titulo="Cadena de frío"),
        ], 0))

    p.append(armar(T, T[1],
        "Cuánto vuelve, por qué motivo y cuánto de eso era evitable",
        ["Tasa de Devolución Valor %", "Var Tasa Devolución pp",
         "% Devoluciones Evitables", "Margen Perdido por Devoluciones USD"],
        [
            visual("clusteredBarChart", MARGEN, Y0, 620, 280,
                   medidas=["Importe Devuelto USD"],
                   categoria=("v_dim_motivo_devolucion", "Motivo de devolución"),
                   titulo="Devoluciones por motivo"),
            visual("clusteredColumnChart", 656, Y0, 604, 280,
                   medidas=["Importe Devuelto USD"],
                   categoria=("v_dim_motivo_devolucion", "Área responsable"),
                   titulo="Devoluciones por área responsable"),
            visual("tableEx", MARGEN, Y0 + 292, 1240, 164,
                   medidas=["Importe Devuelto USD", "Tasa de Devolución Valor %",
                            "% Devoluciones Evitables"],
                   categoria=("v_dim_filial", "País"),
                   titulo="Detalle por filial"),
        ], 1))

    p.append(armar(T, T[2],
        "Qué pedidos revisar ANTES de despachar",
        ["Pedidos en Riesgo Crítico", "Importe en Riesgo USD",
         "Probabilidad Media de Devolución", "Captura en el Top 10% de Riesgo"],
        [
            visual("clusteredColumnChart", MARGEN, Y0, 620, 280,
                   medidas=["Importe en Riesgo USD"],
                   categoria=("v_fact_scoring_devoluciones", "Banda de riesgo"),
                   titulo="Exposición por banda de riesgo"),
            # A un gerente de logística no se le comunica "AUC 0,82": se le
            # comunica cuántas devoluciones evita revisando 1 de cada 10 pedidos.
            visual("card", 656, Y0, 604, 132,
                   medidas=["Lectura del Modelo de Riesgo"],
                   titulo="Lectura operativa del modelo"),
            visual("clusteredBarChart", 656, Y0 + 144, 604, 136,
                   medidas=["Importe en Riesgo USD"],
                   categoria=("v_dim_transportista", "Transportista"),
                   titulo="Riesgo por transportista"),
            visual("tableEx", MARGEN, Y0 + 292, 1240, 164,
                   medidas=["Importe en Riesgo USD",
                            "Probabilidad Media de Devolución",
                            "Pedidos en Riesgo Crítico"],
                   categoria=("v_dim_cliente", "Cliente"),
                   titulo="Clientes con mayor exposición"),
        ], 2))

    p.append(armar(T, T[3],
        "Dónde hay sobrestock y qué está por vencer",
        ["Valor de Stock USD", "Días de Cobertura", "Unidades por Vencer",
         "Valor en Riesgo de Vencimiento USD", "Estado de Cobertura"],
        [
            visual("clusteredBarChart", MARGEN, Y0, 620, 280,
                   medidas=["Días de Cobertura"],
                   categoria=("v_dim_deposito", "Depósito"),
                   titulo="Cobertura por depósito"),
            visual("clusteredBarChart", 656, Y0, 604, 280,
                   medidas=["Valor en Riesgo de Vencimiento USD"],
                   categoria=("v_dim_producto", "SKU"),
                   titulo="Valor en riesgo de vencimiento por SKU"),
            visual("tableEx", MARGEN, Y0 + 292, 1240, 164,
                   medidas=["Stock Unidades", "Días de Cobertura",
                            "Unidades por Vencer",
                            "Valor en Riesgo de Vencimiento USD"],
                   categoria=("v_dim_producto", "Clase terapéutica"),
                   titulo="Stock por clase terapéutica"),
        ], 3))
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--ruta",
        help="Carpeta de los .parquet que queda precargada en el parámetro "
             "RutaDatos. Si se pasa, el archivo abre apuntando a la máquina "
             "donde se generó y no hay que tipear nada.",
    )
    ap.add_argument(
        "--servidor", help="Instancia de SQL Server para el parámetro ServidorSQL."
    )
    ap.add_argument("--base", help="Base de datos para el parámetro BaseSQL.")
    ap.add_argument(
        "--origen", choices=["Parquet", "SQL Server"], default=None,
        help="Origen por defecto del modelo.",
    )
    args = ap.parse_args()

    global RUTA_DATOS_DEFECTO, SERVIDOR_DEFECTO, BASE_DEFECTO, ORIGEN_DEFECTO
    if args.ruta:
        RUTA_DATOS_DEFECTO = str(Path(args.ruta)).rstrip("\\/")
    if args.servidor:
        SERVIDOR_DEFECTO = args.servidor
    if args.base:
        BASE_DEFECTO = args.base
    if args.origen:
        ORIGEN_DEFECTO = args.origen

    print("Generando archivos de Power BI para los tres tableros\n")
    print(f"  origen por defecto : {ORIGEN_DEFECTO}")
    if ORIGEN_DEFECTO == "Parquet":
        print(f"  ruta de datos      : {RUTA_DATOS_DEFECTO}")
    else:
        print(f"  servidor / base    : {SERVIDOR_DEFECTO} / {BASE_DEFECTO}")
    print()
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
