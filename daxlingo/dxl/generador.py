"""
MV DAX Lab · Generador NL→DAX: de un pedido en español (o inglés) a una medida.

Dos motores, en cadena:

  1. Motor de reglas (siempre disponible, sin red): reconoce los patrones de
     medida más pedidos — total, promedio, conteo distinto, % del total, YTD,
     variación contra el año anterior, media móvil, ranking, top N — y los
     ancla a columnas REALES del modelo con búsqueda difusa. Si el pedido
     nombra algo que no existe, lo dice; no inventa.

  2. Claude (opcional, BYOK): si hay ANTHROPIC_API_KEY, pedidos más libres se
     resuelven con IA. La respuesta se valida contra el catálogo igual que la
     del motor de reglas — una referencia inexistente descarta la medida.

La salida siempre incluye el DAX, un formato sugerido y la explicación de por
qué la expresión es esa.
"""
from __future__ import annotations

import json
import re

from .i18n import IDIOMA_DEFECTO, t as traducir
from .catalogo import Catalogo, _norm, validar_referencias
from .proveedores_ia import PROVEEDOR_DEFECTO, consultar, hay_clave


def _tabla_ref(tabla: str) -> str:
    """En DAX solo hacen falta comillas si el nombre no es un identificador."""
    return f"'{tabla}'" if re.search(r"[^A-Za-z0-9_]", tabla) else tabla


def _col_ref(tabla: str, columna: str) -> str:
    return f"{_tabla_ref(tabla)}[{columna}]"


def _limpiar_pedido(pedido: str) -> str:
    ruido = ("una medida", "medida", "crear", "creá", "crea", "generar",
             "generá", "genera", "calcular", "calculá", "calcula", "quiero",
             "necesito", "dame", "hacer", "hace", "haz", "que", "por favor",
             "de la", "del", "de los", "de las", "de", "el", "la", "los",
             "las", "un", "una", "para", "me",
             # inglés / portugués: sin esto, «the total of sales» entra al
             # motor con «the» y «of» pegados y ningún patrón encaja.
             "a", "an", "the", "of", "for", "i", "want", "need", "give",
             "show", "create", "make", "calculate", "measure", "please",
             "uma", "um", "os", "as", "do", "da", "dos", "das", "criar",
             "calcular", "quero", "preciso", "medida", "por favor")
    texto = _norm(pedido)
    palabras = [p for p in texto.split() if p not in ruido]
    return " ".join(palabras)


def _sin(texto: str, *frases: str) -> str:
    """Saca las frases del texto normalizado, para aislar el objetivo."""
    for f in frases:
        texto = texto.replace(f, " ")
    return re.sub(r"\s+", " ", texto).strip()


# ==========================================================================
# Motor de reglas
# ==========================================================================
def generar(pedido: str, cat: Catalogo, api_key: str | None = None,
            idioma: str = IDIOMA_DEFECTO,
            proveedor: str = PROVEEDOR_DEFECTO, modelo_ia: str = "",
            endpoint: str = "") -> dict:
    """
    Devuelve:
      nombre, dax, formato, explicacion, metodo ('reglas'|'ia'),
      advertencias (list), ok (bool)
    """
    pedido = (pedido or "").strip()
    if not pedido:
        return _error(traducir("gen_vacio", idioma))
    if not cat.tablas:
        return _error(traducir("gen_sin_modelo", idioma))

    resultado = _con_reglas(pedido, cat, idioma)
    if resultado is not None:
        return resultado

    if hay_clave(proveedor, api_key):
        try:
            return _con_ia(pedido, cat, api_key, proveedor, modelo_ia,
                           endpoint, idioma)
        except Exception as exc:  # red caída, clave inválida, etc.
            return _error(
                traducir("gen_sin_patron", idioma).format(motivo=exc))
    return _error(traducir("gen_sin_reconocer", idioma))


def _error(msg: str) -> dict:
    return {"ok": False, "nombre": "", "dax": "", "formato": "",
            "explicacion": "", "metodo": "reglas", "advertencias": [msg]}


def _exito(nombre, dax, formato, explicacion, metodo="reglas",
           advertencias=None) -> dict:
    return {"ok": True, "nombre": nombre, "dax": dax, "formato": formato,
            "explicacion": explicacion, "metodo": metodo,
            "advertencias": advertencias or []}


def _titulo(texto: str) -> str:
    texto = texto.strip()
    return texto[:1].upper() + texto[1:] if texto else texto


def _con_reglas(pedido: str, cat: Catalogo,
                idioma: str = IDIOMA_DEFECTO) -> dict | None:
    texto = _limpiar_pedido(pedido)

    for detector in (_regla_ranking, _regla_top_n, _regla_pct_total,
                     _regla_ytd, _regla_vs_anio_anterior, _regla_media_movil,
                     _regla_conteo_distinto, _regla_conteo, _regla_promedio,
                     _regla_extremos, _regla_suma):
        r = detector(texto, cat, idioma)
        if r is not None:
            return r
    return None


def _base_agregada(texto: str, cat: Catalogo) -> tuple[str, str, str] | None:
    """
    Para patrones compuestos: resuelve la parte «de X» como medida existente
    o como SUM(columna numérica). Devuelve (nombre_base, dax_base, objetivo).
    """
    candidatas = cat.buscar_medidas(texto)
    if candidatas:
        med = candidatas[0]
        return (med["nombre"], f"[{med['nombre']}]", med["nombre"])
    col = cat.buscar_columna(texto, solo_numericas=True)
    if col:
        tabla, c = col
        return (c["nombre"], f"SUM ( {_col_ref(tabla, c['nombre'])} )",
                c["nombre"])
    return None


def _nota_ambiguedad(texto: str, cat: Catalogo,
                     idioma: str = IDIOMA_DEFECTO) -> str:
    """Si el pedido encajaba en varias medidas, decir cuál se usó y qué otras
    había. Elegir en silencio entre «Ventas Brutas USD» y «Ventas Netas USD»
    es exactamente cómo se entrega un número que nadie revisa."""
    candidatas = cat.buscar_medidas(texto)
    if len(candidatas) < 2:
        return ""
    otras = ", ".join(f"[{m['nombre']}]" for m in candidatas[1:4])
    return " " + traducir("genx_ambiguo", idioma).format(
        elegida=f"[{candidatas[0]['nombre']}]", otras=otras)


# Columnas numéricas que NO son sumables aunque el tipo diga que sí: años,
# meses, días, códigos y claves. Sumar la columna Año da un número enorme y
# perfectamente inútil, y era lo que salía al pedir «% del total» sin decir de
# qué — la primera columna numérica del modelo suele ser el Año del calendario.
_NO_SUMABLES = re.compile(
    r"^(a[nñ]o|anio|year|mes|month|dia|day|trimestre|quarter|semana|week|"
    r"n?ro|numero|number|codigo|code|key|clave|.*_?id|id_?.*)$", re.I)


def _base_por_defecto(cat: Catalogo) -> tuple[str, str, str] | None:
    """Sobre qué calcular cuando el pedido no lo dice.

    Una medida del modelo primero: alguien la definió a propósito y siempre
    significa algo. Recién después una columna numérica, y saltando las que no
    se suman.
    """
    medidas = cat.medidas()
    if medidas:
        m = medidas[0]
        return (m["nombre"], f"[{m['nombre']}]", m["nombre"])
    for tabla, c in cat.columnas(solo_visibles=True):
        if c["tipo"] in ("int64", "double", "decimal", "currency") \
                and not _NO_SUMABLES.match(c["nombre"]):
            return (c["nombre"], f"SUM ( {_col_ref(tabla, c['nombre'])} )",
                    c["nombre"])
    return None


def _sin_articulo(texto: str) -> str:
    """Saca el «de» que sobra en «total de ventas».

    No se puede hacer en la normalización general: hay medidas que se llaman
    «% del total · Importe», y ahí el «del» es parte del nombre — el test de
    no-secuestro depende de que se conserve.
    """
    return re.sub(r"^\s*(?:de|del|de la|de los|of|the|da|do|dos|das)\s+", "",
                  texto.strip())


def _dimension(texto: str, cat: Catalogo) -> tuple[str, dict] | None:
    return cat.buscar_columna(texto)


# --- patrones -------------------------------------------------------------
def _regla_suma(texto: str, cat: Catalogo,
                idioma: str = IDIOMA_DEFECTO) -> dict | None:
    m = re.search(r"(?:total|suma|sumar|sumatoria|sum|soma|somar)\s*(.*)", texto)
    if not m:
        return None
    objetivo = _sin_articulo(m.group(1) or texto)
    col = cat.buscar_columna(objetivo, solo_numericas=True)
    if not col:
        # Antes de rendirse: «total de ventas» en un modelo que ya tiene
        # [Ventas Brutas USD] no es un error, es esa medida. Sumar una medida
        # no tiene sentido, así que se devuelve la medida tal cual.
        med = cat.buscar_medida(objetivo)
        if med:
            return _exito(
                med["nombre"], f"[{med['nombre']}]", med.get("formato") or "#,0",
        traducir("genx_ya_existe", idioma).format(medida=med["nombre"]))
        return _error(traducir("genx_sin_columna_suma", idioma).format(
            objetivo=objetivo.strip() or texto))
    tabla, c = col
    nombre = traducir("genx_nombre_total", idioma).format(
        col=_titulo(c["nombre"]))
    dax = f"SUM ( {_col_ref(tabla, c['nombre'])} )"
    return _exito(nombre, dax, "#,0",
        traducir("genx_suma", idioma).format(col=f"{tabla}[{c['nombre']}]")
        + _nota_ambiguedad(objetivo, cat, idioma))


def _regla_promedio(texto: str, cat: Catalogo,
                    idioma: str = IDIOMA_DEFECTO) -> dict | None:
    m = re.search(r"(?:promedio|media|average|avg|media de)\s*(.*)", texto)
    if not m or "movil" in texto:
        return None
    col = cat.buscar_columna(m.group(1) or texto, solo_numericas=True)
    if not col:
        return _error(
            traducir("genx_sin_columna_promedio", idioma).format(texto=texto))
    tabla, c = col
    return _exito(traducir("genx_nombre_promedio", idioma).format(
                      col=_titulo(c["nombre"])),
                  f"AVERAGE ( {_col_ref(tabla, c['nombre'])} )", "#,0.00",
                  traducir("genx_promedio", idioma).format(
                          col=f"{tabla}[{c['nombre']}]"))


def _regla_extremos(texto: str, cat: Catalogo,
                    idioma: str = IDIOMA_DEFECTO) -> dict | None:
    m = re.search(r"(maximo|minimo|mayor|menor|max|min|maximum|minimum|maior|menor)\s*(.*)", texto)
    if not m:
        return None
    es_max = m.group(1) in ("maximo", "mayor")
    col = cat.buscar_columna(m.group(2) or texto, solo_numericas=True)
    if not col:
        return None
    tabla, c = col
    fn = "MAX" if es_max else "MIN"
    clave_nombre = "genx_nombre_maximo" if es_max else "genx_nombre_minimo"
    return _exito(traducir(clave_nombre, idioma).format(
                      col=_titulo(c["nombre"])),
                  f"{fn} ( {_col_ref(tabla, c['nombre'])} )", "#,0",
                  traducir("genx_minmax", idioma).format(
                      fn=fn,
                      extremo=traducir("genx_mayor" if es_max else "genx_menor",
                                       idioma),
                      col=f"{tabla}[{c['nombre']}]"))


def _regla_conteo_distinto(texto: str, cat: Catalogo,
                           idioma: str = IDIOMA_DEFECTO) -> dict | None:
    if not re.search(r"\b(distintos?|unicos?|diferentes|distinct|unique|distintas?|unicas?)\b", texto):
        return None
    # El sustantivo puede ir antes o después de la palabra clave —«clientes
    # distintos» y «distintos clientes» son el mismo pedido—, así que en vez
    # de adivinar la posición se saca el ruido y queda el objetivo.
    objetivo = _sin(texto, "distintos", "distintas", "distinto", "distinta",
                    "unicos", "unicas", "unico", "unica", "diferentes",
                    "diferente", "conteo", "cantidad", "numero", "cuantos",
                    "cuantas", "valores", "distinct", "unique", "count",
                    "quantidade", "quantos", "quantas", "values")
    col = cat.buscar_columna(objetivo or texto)
    if not col:
        return _error(
            traducir("genx_sin_columna_conteo", idioma).format(texto=texto))
    tabla, c = col
    return _exito(
        traducir("genx_nombre_distintos", idioma).format(
            entidad=_nombre_de_entidad(cat, tabla, c["nombre"])),
        f"DISTINCTCOUNT ( {_col_ref(tabla, c['nombre'])} )", "#,0",
        traducir("genx_distintos", idioma).format(col=f"{tabla}[{c['nombre']}]"))


def _nombre_de_entidad(cat: Catalogo, tabla: str, columna: str) -> str:
    """
    Nombre legible para una medida sobre una columna clave. Contar
    Ventas[IdCliente] es contar CLIENTES: la medida tiene que llamarse por lo
    que cuenta, no por la columna técnica. Si la columna apunta a otra tabla,
    se usa el nombre de esa tabla; si no, se le saca el prefijo «Id».
    """
    for r in cat.relaciones:
        if (_norm(r["desde_tabla"]), _norm(r["desde_col"])) == (_norm(tabla),
                                                                _norm(columna)):
            return _titulo(r["hacia_tabla"])
    limpio = re.sub(r"^id[_ ]?", "", columna, flags=re.IGNORECASE).strip()
    return _titulo(limpio or columna)


def _regla_conteo(texto: str, cat: Catalogo,
                  idioma: str = IDIOMA_DEFECTO) -> dict | None:
    m = re.search(r"(?:conteo|cantidad|numero|cuantos|cuantas|filas|count|rows|quantidade|quantos|quantas|linhas)\s*(.*)",
                  texto)
    if not m:
        return None
    objetivo = (m.group(1) or "").strip()
    t = cat.tabla(objetivo) if objetivo else None
    if not t and objetivo:
        col = cat.buscar_columna(objetivo)
        if col:
            t = cat.tabla(col[0])
    if not t:
        return None
    ref = f"'{t['nombre']}'" if re.search(r"[^A-Za-z0-9_]", t["nombre"]) \
        else t["nombre"]
    return _exito(
        traducir("genx_nombre_filas", idioma).format(tabla=t["nombre"]),
        f"COUNTROWS ( {ref} )", "#,0",
        traducir("genx_filas", idioma).format(tabla=t["nombre"]))


def _regla_pct_total(texto: str, cat: Catalogo,
                     idioma: str = IDIOMA_DEFECTO) -> dict | None:
    if not re.search(r"(%|porcentaje|porciento|participacion|peso|percent|percentage|share|percentual|participacao)\s*"
                     r"(del|sobre el|del gran|of|of the|do|sobre o)?\s*(total|grand total)", texto) \
            and "% del total" not in texto:
        return None
    resto = _sin(texto, "porcentaje del total", "% del total", "porcentaje",
                 "percentage of total", "percent of total", "grand total",
                 "participacion", "participacao", "percentual", "share",
                 "percent", "peso", "sobre el total", "del total", "sobre o",
                 "total", "%", "por")
    base = _base_agregada(resto, cat) if resto else None
    if not base:
        base = _base_por_defecto(cat)
        if not base:
            return _error(traducir("genx_sin_base_pct", idioma))
    nombre_base, dax_base, _ = base
    refs = re.findall(r"'?([\w ]+?)'?\[", dax_base)
    quitar = (f"ALLSELECTED ( {_tabla_ref(refs[0].strip())} )" if refs
              else "ALLSELECTED ()")
    dax = (f"DIVIDE (\n    {dax_base},\n"
           f"    CALCULATE ( {dax_base}, {quitar} )\n)")
    return _exito(
        traducir("genx_nombre_pct_total", idioma).format(
            base=_titulo(nombre_base)),
        dax, "0.0 %",
        traducir("genx_pct_total", idioma))


def _regla_ytd(texto: str, cat: Catalogo,
               idioma: str = IDIOMA_DEFECTO) -> dict | None:
    if not re.search(r"\b(ytd|acumulado|acumulada|year to date|running total)\b", texto):
        return None
    fecha = cat.columna_fecha()
    if not fecha:
        return _error(traducir("genx_sin_calendario_ytd", idioma))
    resto = _sin(texto, "acumulado del ano", "acumulado anual", "acumulado",
                 "acumulada", "year to date", "running total", "ytd", "ano")
    base = _base_agregada(resto, cat)
    if not base:
        return _error(traducir("genx_sin_base_ytd", idioma).format(texto=texto))
    nombre_base, dax_base, _ = base
    dax = (f"TOTALYTD (\n    {dax_base},\n"
           f"    {_col_ref(fecha[0], fecha[1])}\n)")
    return _exito(
        traducir("genx_nombre_ytd", idioma).format(base=_titulo(nombre_base)),
        dax, "#,0",
        traducir("genx_ytd", idioma).format(base=nombre_base, calendario=f"{fecha[0]}[{fecha[1]}]"))


def _regla_vs_anio_anterior(texto: str, cat: Catalogo,
                            idioma: str = IDIOMA_DEFECTO) -> dict | None:
    if not re.search(r"(vs|versus|contra|variacion|crecimiento|yoy|growth|change|variacao)\s*"
                     r".*(ano anterior|ano pasado|interanual|yoy|last year|previous year|prior year|ano passado)", texto) \
            and not re.search(r"\b(yoy|interanual|year over year|year on year)\b", texto):
        return None
    fecha = cat.columna_fecha()
    if not fecha:
        return _error(traducir("genx_sin_calendario_aa", idioma))
    # Las frases largas primero: sacar «vs» antes que «vs last year» dejaría
    # «last year» suelto pegado al objetivo, y la búsqueda difusa termina
    # eligiendo cualquier columna que se le parezca —así «Ventas Brutas USD vs
    # last year» devolvía la variación de «Días a vencer x línea».
    resto = _sin(texto, "vs ano anterior", "contra ano anterior",
                 "vs ano pasado", "year over year", "year on year",
                 "previous year", "prior year", "last year", "ano passado",
                 "variacion", "variacao", "crecimiento", "growth", "change",
                 "interanual", "yoy", "vs", "versus", "contra",
                 "ano anterior", "ano pasado")
    base = _base_agregada(resto, cat)
    if not base:
        return _error(traducir("genx_sin_base_aa", idioma).format(texto=texto))
    nombre_base, dax_base, _ = base
    fref = _col_ref(fecha[0], fecha[1])
    dax = (f"VAR Actual = {dax_base}\n"
           f"VAR Anterior =\n"
           f"    CALCULATE ( {dax_base}, SAMEPERIODLASTYEAR ( {fref} ) )\n"
           f"RETURN\n"
           f"    DIVIDE ( Actual - Anterior, Anterior )")
    return _exito(
        traducir("genx_nombre_vs_aa", idioma).format(base=_titulo(nombre_base)),
        dax, "+0.0 %;-0.0 %",
        traducir("genx_vs_aa", idioma) + _nota_ambiguedad(resto, cat, idioma))


def _regla_media_movil(texto: str, cat: Catalogo,
                       idioma: str = IDIOMA_DEFECTO) -> dict | None:
    m = re.search(r"(?:media|promedio|moving|rolling)\s*(?:movil|average|movel)\s*(?:de\s*)?(\d+)?\s*"
                  r"(?:meses|mes|months|month|meses)?\s*(?:de\s+|of\s+)?(.*)", texto)
    if not m:
        return None
    meses = int(m.group(1) or 3)
    fecha = cat.columna_fecha()
    if not fecha:
        return _error(traducir("genx_sin_calendario_mm", idioma))
    base = _base_agregada(m.group(2) or texto, cat)
    if not base:
        return _error(traducir("genx_sin_base_mm", idioma).format(texto=texto))
    nombre_base, dax_base, _ = base
    fref = _col_ref(fecha[0], fecha[1])
    dax = (f"AVERAGEX (\n"
           f"    DATESINPERIOD ( {fref}, LASTDATE ( {fref} ), -{meses}, MONTH ),\n"
           f"    CALCULATE ( {dax_base} )\n)")
    return _exito(
        traducir("genx_nombre_media_movil", idioma).format(
            base=_titulo(nombre_base), meses=meses),
        dax, "#,0",
        traducir("genx_media_movil", idioma).format(meses=meses))


def _regla_ranking(texto: str, cat: Catalogo,
                   idioma: str = IDIOMA_DEFECTO) -> dict | None:
    m = re.search(r"(?:ranking|posicion|puesto|rank|posicao)\s*(?:de\s*|of\s*)?(.*?)"
                  r"(?:\s+(?:por|by)\s+(.*))?$", texto)
    if not m or not texto.startswith(
            ("ranking", "posicion", "puesto", "rank", "posicao")):
        return None
    dim = _dimension(m.group(1) or "", cat)
    base = _base_agregada(m.group(2) or m.group(1) or texto, cat)
    if not dim or not base:
        return _error(traducir("genx_sin_ranking", idioma))
    (tabla_d, col_d), (nombre_base, dax_base, _) = dim, base
    dref = _col_ref(tabla_d, col_d["nombre"])
    dax = (f"RANKX (\n    ALLSELECTED ( {dref} ),\n"
           f"    CALCULATE ( {dax_base} ),\n    ,\n    DESC,\n    DENSE\n)")
    return _exito(
        traducir("genx_nombre_ranking", idioma).format(
            col=_titulo(col_d["nombre"]), base=nombre_base),
        dax, "#,0",
        traducir("genx_ranking", idioma).format(col=f"{tabla_d}[{col_d['nombre']}]", base=nombre_base))


def _regla_top_n(texto: str, cat: Catalogo,
                 idioma: str = IDIOMA_DEFECTO) -> dict | None:
    m = re.search(r"top\s*(\d+)\s*(?:de\s*)?(.*?)(?:\s+(?:por|by)\s+(.*))?$",
                 texto)
    if not m:
        return None
    n = int(m.group(1))
    dim = _dimension(m.group(2) or "", cat)
    base = _base_agregada(m.group(3) or m.group(2) or texto, cat)
    if not dim or not base:
        return _error(traducir("genx_sin_topn", idioma).format(n=n))
    (tabla_d, col_d), (nombre_base, dax_base, _) = dim, base
    dref = _col_ref(tabla_d, col_d["nombre"])
    dax = (f"CALCULATE (\n    {dax_base},\n"
           f"    KEEPFILTERS (\n"
           f"        TOPN ( {n}, ALLSELECTED ( {dref} ), "
           f"CALCULATE ( {dax_base} ), DESC )\n    )\n)")
    return _exito(
        traducir("genx_nombre_topn", idioma).format(
            base=_titulo(nombre_base), n=n, col=col_d["nombre"]),
        dax, "#,0",
        traducir("genx_topn", idioma).format(n=n, col=f"{tabla_d}[{col_d['nombre']}]", base=nombre_base))


# ==========================================================================
# Motor con IA (opcional, BYOK)
# ==========================================================================
def _catalogo_para_prompt(cat: Catalogo, maximo: int = 4000) -> str:
    lineas = []
    for t in cat.tablas:
        if t["interna"]:
            continue
        cols = ", ".join(f"{c['nombre']} ({c['tipo']})"
                         for c in t["columnas"] if not c["oculta"])
        lineas.append(f"Tabla '{t['nombre']}': {cols}")
        for m1 in t["medidas"]:
            lineas.append(f"  Medida [{m1['nombre']}]")
    texto = "\n".join(lineas)
    return texto[:maximo]


_IDIOMA_NOMBRE = {"es": "español", "en": "English", "pt": "português"}


def _con_ia(pedido: str, cat: Catalogo, api_key: str | None, proveedor: str,
            modelo_ia: str, endpoint: str = "",
            idioma: str = IDIOMA_DEFECTO) -> dict:
    """
    Pide la medida al proveedor de IA elegido y valida la respuesta contra el
    catálogo: una referencia inexistente descarta la medida entera.
    """
    nombre_idioma = _IDIOMA_NOMBRE.get(idioma, _IDIOMA_NOMBRE[IDIOMA_DEFECTO])
    prompt = (
        "Sos un experto en DAX. Este es el catálogo REAL del modelo:\n\n"
        f"{_catalogo_para_prompt(cat)}\n\n"
        f"Pedido del usuario: {pedido}\n\n"
        "Respondé SOLO un JSON con las claves: nombre (nombre de la medida), "
        "dax (la expresión, sin «Medida =» adelante), formato (formatString "
        f"de Power BI) y explicacion (1-3 frases, en {nombre_idioma}). "
        "Usá únicamente tablas, columnas y medidas del catálogo; si el pedido "
        "nombra algo que no existe, devolvé {\"error\": \"...\"} explicando "
        "qué falta."
    )
    texto = consultar([{"role": "user", "content": prompt}],
                      proveedor=proveedor, modelo=modelo_ia, api_key=api_key,
                      max_tokens=1024, endpoint=endpoint)
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        raise ValueError(traducir("genx_ia_sin_json", idioma))
    salida = json.loads(m.group(0))
    if "error" in salida:
        return _error(traducir("genx_ia_error", idioma).format(
            error=salida["error"]))

    errores = validar_referencias(salida.get("dax", ""), cat)
    if errores:
        return _error(traducir("genx_ia_referencias_invalidas", idioma).format(
            detalle="; ".join(errores)))
    return _exito(salida.get("nombre", "Medida IA"), salida.get("dax", ""),
                  salida.get("formato", "#,0"),
                  salida.get("explicacion", ""), metodo="ia")
