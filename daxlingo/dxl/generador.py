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
             "las", "un", "una", "para", "me")
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
            proveedor: str = PROVEEDOR_DEFECTO, modelo_ia: str = "",
            endpoint: str = "") -> dict:
    """
    Devuelve:
      nombre, dax, formato, explicacion, metodo ('reglas'|'ia'),
      advertencias (list), ok (bool)
    """
    pedido = (pedido or "").strip()
    if not pedido:
        return _error("Escribí qué medida querés: p. ej. «total de ventas», "
                      "«% del total por país», «ventas vs año anterior».")
    if not cat.tablas:
        return _error("Primero cargá un modelo: el generador solo escribe DAX "
                      "sobre columnas que existen.")

    resultado = _con_reglas(pedido, cat)
    if resultado is not None:
        return resultado

    if hay_clave(proveedor, api_key):
        try:
            return _con_ia(pedido, cat, api_key, proveedor, modelo_ia,
                           endpoint)
        except Exception as exc:  # red caída, clave inválida, etc.
            return _error(
                f"El motor de reglas no reconoció el patrón y la IA falló: "
                f"{exc}. Reformulá el pedido (p. ej. «total de <columna>»).")
    return _error(
        "No reconocí el patrón del pedido. Probá con: total / promedio / "
        "máximo / mínimo / conteo distinto de <columna>, «% del total por "
        "<dimensión>», «<columna> acumulado del año», «<columna> vs año "
        "anterior», «media móvil 3 meses de <columna>», «ranking de "
        "<dimensión> por <columna>». Con una ANTHROPIC_API_KEY configurada, "
        "también entiendo pedidos libres con la IA que elijas (Claude, "
        "ChatGPT, Gemini, Copilot…).")


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


def _con_reglas(pedido: str, cat: Catalogo) -> dict | None:
    texto = _limpiar_pedido(pedido)

    for detector in (_regla_ranking, _regla_top_n, _regla_pct_total,
                     _regla_ytd, _regla_vs_anio_anterior, _regla_media_movil,
                     _regla_conteo_distinto, _regla_conteo, _regla_promedio,
                     _regla_extremos, _regla_suma):
        r = detector(texto, cat)
        if r is not None:
            return r
    return None


def _base_agregada(texto: str, cat: Catalogo) -> tuple[str, str, str] | None:
    """
    Para patrones compuestos: resuelve la parte «de X» como medida existente
    o como SUM(columna numérica). Devuelve (nombre_base, dax_base, objetivo).
    """
    med = cat.buscar_medida(texto)
    if med:
        return (med["nombre"], f"[{med['nombre']}]", med["nombre"])
    col = cat.buscar_columna(texto, solo_numericas=True)
    if col:
        tabla, c = col
        return (c["nombre"], f"SUM ( {_col_ref(tabla, c['nombre'])} )",
                c["nombre"])
    return None


def _dimension(texto: str, cat: Catalogo) -> tuple[str, dict] | None:
    return cat.buscar_columna(texto)


# --- patrones -------------------------------------------------------------
def _regla_suma(texto: str, cat: Catalogo) -> dict | None:
    m = re.search(r"(?:total|suma|sumar|sumatoria)\s*(.*)", texto)
    if not m:
        return None
    objetivo = m.group(1) or texto
    col = cat.buscar_columna(objetivo, solo_numericas=True)
    if not col:
        return _error(f"No encontré una columna numérica que se parezca a "
                      f"«{objetivo.strip() or texto}» en el modelo.")
    tabla, c = col
    nombre = f"Total {_titulo(c['nombre'])}"
    dax = f"SUM ( {_col_ref(tabla, c['nombre'])} )"
    return _exito(nombre, dax, "#,0",
                  f"Suma la columna {tabla}[{c['nombre']}] en el contexto "
                  "del visual: cada celda/fila del reporte filtra qué filas "
                  "entran en la suma.")


def _regla_promedio(texto: str, cat: Catalogo) -> dict | None:
    m = re.search(r"(?:promedio|media|average)\s*(.*)", texto)
    if not m or "movil" in texto:
        return None
    col = cat.buscar_columna(m.group(1) or texto, solo_numericas=True)
    if not col:
        return _error(f"No encontré una columna numérica para promediar en "
                      f"«{texto}».")
    tabla, c = col
    return _exito(f"Promedio {_titulo(c['nombre'])}",
                  f"AVERAGE ( {_col_ref(tabla, c['nombre'])} )", "#,0.00",
                  f"Promedia {tabla}[{c['nombre']}] sobre las filas visibles.")


def _regla_extremos(texto: str, cat: Catalogo) -> dict | None:
    m = re.search(r"(maximo|minimo|mayor|menor)\s*(.*)", texto)
    if not m:
        return None
    es_max = m.group(1) in ("maximo", "mayor")
    col = cat.buscar_columna(m.group(2) or texto, solo_numericas=True)
    if not col:
        return None
    tabla, c = col
    fn = "MAX" if es_max else "MIN"
    return _exito(f"{'Máximo' if es_max else 'Mínimo'} {_titulo(c['nombre'])}",
                  f"{fn} ( {_col_ref(tabla, c['nombre'])} )", "#,0",
                  f"{fn} devuelve el {'mayor' if es_max else 'menor'} valor "
                  f"visible de {tabla}[{c['nombre']}].")


def _regla_conteo_distinto(texto: str, cat: Catalogo) -> dict | None:
    if not re.search(r"\b(distintos?|unicos?|diferentes)\b", texto):
        return None
    # El sustantivo puede ir antes o después de la palabra clave —«clientes
    # distintos» y «distintos clientes» son el mismo pedido—, así que en vez
    # de adivinar la posición se saca el ruido y queda el objetivo.
    objetivo = _sin(texto, "distintos", "distintas", "distinto", "distinta",
                    "unicos", "unicas", "unico", "unica", "diferentes",
                    "diferente", "conteo", "cantidad", "numero", "cuantos",
                    "cuantas", "valores")
    col = cat.buscar_columna(objetivo or texto)
    if not col:
        return _error(f"No encontré la columna a contar en «{texto}».")
    tabla, c = col
    return _exito(f"{_nombre_de_entidad(cat, tabla, c['nombre'])} distintos",
                  f"DISTINCTCOUNT ( {_col_ref(tabla, c['nombre'])} )", "#,0",
                  f"Cuenta los valores únicos de {tabla}[{c['nombre']}] en el "
                  "contexto del visual — el mismo cliente diez veces cuenta 1.")


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


def _regla_conteo(texto: str, cat: Catalogo) -> dict | None:
    m = re.search(r"(?:conteo|cantidad|numero|cuantos|cuantas|filas)\s*(.*)",
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
    return _exito(f"Filas de {t['nombre']}", f"COUNTROWS ( {ref} )", "#,0",
                  f"Cuenta las filas visibles de la tabla {t['nombre']}.")


def _regla_pct_total(texto: str, cat: Catalogo) -> dict | None:
    if not re.search(r"(%|porcentaje|porciento|participacion|peso)\s*"
                     r"(del|sobre el|del gran)?\s*total", texto) \
            and "% del total" not in texto:
        return None
    resto = _sin(texto, "porcentaje del total", "% del total", "porcentaje",
                 "participacion", "peso", "sobre el total", "del total",
                 "total", "%", "por")
    base = _base_agregada(resto, cat) if resto else None
    if not base:
        # sin objetivo explícito: primera columna numérica visible
        numericas = [p for p in cat.columnas(solo_visibles=True)
                     if p[1]["tipo"] in ("int64", "double", "decimal",
                                         "currency")]
        if not numericas:
            return _error("No encontré sobre qué columna calcular el % del "
                          "total.")
        tabla, c = numericas[0]
        base = (c["nombre"], f"SUM ( {_col_ref(tabla, c['nombre'])} )",
                c["nombre"])
    nombre_base, dax_base, _ = base
    refs = re.findall(r"'?([\w ]+?)'?\[", dax_base)
    quitar = (f"ALLSELECTED ( {_tabla_ref(refs[0].strip())} )" if refs
              else "ALLSELECTED ()")
    dax = (f"DIVIDE (\n    {dax_base},\n"
           f"    CALCULATE ( {dax_base}, {quitar} )\n)")
    return _exito(
        f"% del total · {_titulo(nombre_base)}", dax, "0.0 %",
        "Divide el valor del contexto actual por el mismo valor sin los "
        "filtros del visual (ALLSELECTED respeta los slicers): eso es la "
        "participación sobre el total. DIVIDE evita el error ante total 0.")


def _regla_ytd(texto: str, cat: Catalogo) -> dict | None:
    if not re.search(r"\b(ytd|acumulado)\b", texto):
        return None
    fecha = cat.columna_fecha()
    if not fecha:
        return _error("Para un acumulado del año necesito una tabla de "
                      "calendario en el modelo, y no encontré ninguna.")
    resto = _sin(texto, "acumulado del ano", "acumulado anual", "acumulado",
                 "ytd", "ano")
    base = _base_agregada(resto, cat)
    if not base:
        return _error(f"No encontré qué acumular en «{texto}».")
    nombre_base, dax_base, _ = base
    dax = (f"TOTALYTD (\n    {dax_base},\n"
           f"    {_col_ref(fecha[0], fecha[1])}\n)")
    return _exito(
        f"{_titulo(nombre_base)} YTD", dax, "#,0",
        f"TOTALYTD acumula {nombre_base} desde el 1 de enero hasta la fecha "
        f"del contexto, usando el calendario {fecha[0]}[{fecha[1]}].")


def _regla_vs_anio_anterior(texto: str, cat: Catalogo) -> dict | None:
    if not re.search(r"(vs|versus|contra|variacion|crecimiento|yoy)\s*"
                     r".*(ano anterior|ano pasado|interanual|yoy)", texto) \
            and not re.search(r"\b(yoy|interanual)\b", texto):
        return None
    fecha = cat.columna_fecha()
    if not fecha:
        return _error("Para comparar contra el año anterior necesito una "
                      "tabla de calendario, y no encontré ninguna.")
    resto = _sin(texto, "vs ano anterior", "contra ano anterior",
                 "vs ano pasado", "variacion", "crecimiento", "interanual",
                 "yoy", "vs", "versus", "contra", "ano anterior",
                 "ano pasado")
    base = _base_agregada(resto, cat)
    if not base:
        return _error(f"No encontré qué comparar en «{texto}».")
    nombre_base, dax_base, _ = base
    fref = _col_ref(fecha[0], fecha[1])
    dax = (f"VAR Actual = {dax_base}\n"
           f"VAR Anterior =\n"
           f"    CALCULATE ( {dax_base}, SAMEPERIODLASTYEAR ( {fref} ) )\n"
           f"RETURN\n"
           f"    DIVIDE ( Actual - Anterior, Anterior )")
    return _exito(
        f"{_titulo(nombre_base)} · var. % vs AA", dax, "+0.0 %;-0.0 %",
        "Calcula el valor actual y el del mismo período del año anterior "
        "(SAMEPERIODLASTYEAR desplaza el calendario), y devuelve la "
        "variación relativa con división segura.")


def _regla_media_movil(texto: str, cat: Catalogo) -> dict | None:
    m = re.search(r"(?:media|promedio)\s*movil\s*(?:de\s*)?(\d+)?\s*"
                  r"(?:meses|mes)?\s*(.*)", texto)
    if not m:
        return None
    meses = int(m.group(1) or 3)
    fecha = cat.columna_fecha()
    if not fecha:
        return _error("Para una media móvil necesito una tabla de calendario "
                      "en el modelo.")
    base = _base_agregada(m.group(2) or texto, cat)
    if not base:
        return _error(f"No encontré qué promediar en «{texto}».")
    nombre_base, dax_base, _ = base
    fref = _col_ref(fecha[0], fecha[1])
    dax = (f"AVERAGEX (\n"
           f"    DATESINPERIOD ( {fref}, LASTDATE ( {fref} ), -{meses}, MONTH ),\n"
           f"    CALCULATE ( {dax_base} )\n)")
    return _exito(
        f"{_titulo(nombre_base)} · media móvil {meses}m", dax, "#,0",
        f"DATESINPERIOD arma la ventana de los últimos {meses} meses y "
        "AVERAGEX promedia el valor mensual dentro de ella — suaviza la "
        "serie sin perder la punta.")


def _regla_ranking(texto: str, cat: Catalogo) -> dict | None:
    m = re.search(r"(?:ranking|posicion|puesto)\s*(?:de\s*)?(.*?)"
                  r"(?:\s+por\s+(.*))?$", texto)
    if not m or not texto.startswith(("ranking", "posicion", "puesto")):
        return None
    dim = _dimension(m.group(1) or "", cat)
    base = _base_agregada(m.group(2) or m.group(1) or texto, cat)
    if not dim or not base:
        return _error("Para un ranking necesito la dimensión y la métrica: "
                      "«ranking de <columna> por <métrica>».")
    (tabla_d, col_d), (nombre_base, dax_base, _) = dim, base
    dref = _col_ref(tabla_d, col_d["nombre"])
    dax = (f"RANKX (\n    ALLSELECTED ( {dref} ),\n"
           f"    CALCULATE ( {dax_base} ),\n    ,\n    DESC,\n    DENSE\n)")
    return _exito(
        f"Ranking {_titulo(col_d['nombre'])} por {nombre_base}", dax, "#,0",
        f"RANKX ordena todos los valores visibles de {tabla_d}"
        f"[{col_d['nombre']}] por {nombre_base} descendente y devuelve la "
        "posición del valor del contexto actual.")


def _regla_top_n(texto: str, cat: Catalogo) -> dict | None:
    m = re.search(r"top\s*(\d+)\s*(?:de\s*)?(.*?)(?:\s+por\s+(.*))?$", texto)
    if not m:
        return None
    n = int(m.group(1))
    dim = _dimension(m.group(2) or "", cat)
    base = _base_agregada(m.group(3) or m.group(2) or texto, cat)
    if not dim or not base:
        return _error(f"Para un top {n} necesito dimensión y métrica: "
                      f"«top {n} <columna> por <métrica>».")
    (tabla_d, col_d), (nombre_base, dax_base, _) = dim, base
    dref = _col_ref(tabla_d, col_d["nombre"])
    dax = (f"CALCULATE (\n    {dax_base},\n"
           f"    KEEPFILTERS (\n"
           f"        TOPN ( {n}, ALLSELECTED ( {dref} ), "
           f"CALCULATE ( {dax_base} ), DESC )\n    )\n)")
    return _exito(
        f"{_titulo(nombre_base)} · top {n} {col_d['nombre']}", dax, "#,0",
        f"TOPN elige los {n} valores de {tabla_d}[{col_d['nombre']}] con "
        f"mayor {nombre_base}; KEEPFILTERS los aplica como filtro sin pisar "
        "los del visual.")


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


def _con_ia(pedido: str, cat: Catalogo, api_key: str | None, proveedor: str,
            modelo_ia: str, endpoint: str = "") -> dict:
    """
    Pide la medida al proveedor de IA elegido y valida la respuesta contra el
    catálogo: una referencia inexistente descarta la medida entera.
    """
    prompt = (
        "Sos un experto en DAX. Este es el catálogo REAL del modelo:\n\n"
        f"{_catalogo_para_prompt(cat)}\n\n"
        f"Pedido del usuario: {pedido}\n\n"
        "Respondé SOLO un JSON con las claves: nombre (nombre de la medida), "
        "dax (la expresión, sin «Medida =» adelante), formato (formatString "
        "de Power BI) y explicacion (1-3 frases, en el idioma del pedido). "
        "Usá únicamente tablas, columnas y medidas del catálogo; si el pedido "
        "nombra algo que no existe, devolvé {\"error\": \"...\"} explicando "
        "qué falta."
    )
    texto = consultar([{"role": "user", "content": prompt}],
                      proveedor=proveedor, modelo=modelo_ia, api_key=api_key,
                      max_tokens=1024, endpoint=endpoint)
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        raise ValueError("la IA no devolvió JSON")
    salida = json.loads(m.group(0))
    if "error" in salida:
        return _error(f"IA: {salida['error']}")

    errores = validar_referencias(salida.get("dax", ""), cat)
    if errores:
        return _error("La IA propuso referencias que no existen en el modelo "
                      "(descartado): " + "; ".join(errores))
    return _exito(salida.get("nombre", "Medida IA"), salida.get("dax", ""),
                  salida.get("formato", "#,0"),
                  salida.get("explicacion", ""), metodo="ia")
