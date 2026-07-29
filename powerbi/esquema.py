"""
Contrato del modelo semántico: nombres, tipos y relaciones.

Este archivo es el MISMO contrato que declara `sql/04_vistas_semanticas.sql`,
expresado en Python para poder generar el modelo de Power BI desde acá.

Regla que ordena todo: lo que el usuario final lee en el panel de campos tiene
que decir exactamente lo que es. Nada de `id_`, nada de `fact_`, nada de
abreviaturas del sistema origen. Un nombre ambiguo de métrica es la causa raíz
de la mitad de las discusiones de comité.

Las columnas técnicas (las claves) se cargan igual —el modelo las necesita para
relacionar— pero van OCULTAS. Un panel de campos limpio es parte del trabajo.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# Tipos de datos tabulares admitidos: int64 | double | string | dateTime | boolean
# --------------------------------------------------------------------------

# (columna_parquet, nombre_visible, tipo, oculta)
TABLAS: dict[str, dict] = {

    # ================= DIMENSIONES =================

    "v_dim_calendario": {
        "origen": "dim_calendario",
        "tipo": "dimension",
        "esCalendario": True,
        "columnas": [
            ("fecha",                  "Fecha",                  "dateTime", False),
            ("anio",                   "Año",                    "int64",    False),
            ("mes_nro",                "Mes N°",                 "int64",    True),
            ("mes_nombre",             "Mes",                    "string",   False),
            ("anio_mes",               "Año-Mes",                "string",   False),
            ("anio_mes_orden",         "Año-Mes orden",          "int64",    True),
            ("trimestre",              "Trimestre",              "string",   False),
            ("anio_trimestre",         "Año-Trimestre",          "string",   False),
            ("es_habil",               "Es día hábil",           "int64",    False),
            ("es_pasado",              "Es pasado",              "int64",    True),
            ("temporada_respiratoria", "Temporada respiratoria", "int64",    False),
        ],
        # Sort by column: sin esto, "Abr" aparece antes que "Ene" y nadie
        # entiende el gráfico.
        "orden": {"Mes": "Mes N°", "Año-Mes": "Año-Mes orden"},
        "jerarquias": {"Calendario": ["Año", "Trimestre", "Mes"]},
    },

    "v_dim_producto": {
        "origen": "dim_producto",
        "tipo": "dimension",
        "columnas": [
            ("id_producto",        "Id producto",             "int64",  True),
            ("sku",                "SKU",                     "string", False),
            ("marca",              "Marca",                   "string", False),
            ("atc1",               "ATC1",                    "string", False),
            ("atc1_desc",          "Clase terapéutica",       "string", False),
            ("atc3",               "ATC3",                    "string", False),
            ("forma_farmaceutica", "Forma farmacéutica",      "string", False),
            ("presentacion",       "Presentación",            "string", False),
            ("tipo_venta",         "Tipo de venta",           "string", False),
            ("ciclo_vida",         "Ciclo de vida",           "string", False),
            ("vida_util_meses",    "Vida útil (meses)",       "int64",  False),
            ("precio_lista_usd",   "Precio de lista USD",     "double", False),
            ("costo_std_usd",      "Costo estándar USD",      "double", False),
            ("margen_std_pct",     "Margen estándar %",       "double", False),
            # Derivadas en M: el negocio no lee booleanos, lee etiquetas.
            (None, "Condición de conservación", "string", False),
            (None, "Origen del costo",          "string", False),
        ],
        "jerarquias": {"Producto": ["Clase terapéutica", "ATC3", "Marca", "SKU"]},
    },

    "v_dim_cliente": {
        "origen": "dim_cliente",
        "tipo": "dimension",
        "columnas": [
            ("id_cliente",       "Id cliente",           "int64",  True),
            ("id_filial",        "Id filial cliente",    "int64",  True),
            ("cod_cliente",      "Código cliente",       "string", False),
            ("razon_social",     "Cliente",              "string", False),
            ("canal",            "Canal",                "string", False),
            ("segmento",         "Segmento",             "string", False),
            ("antiguedad_meses", "Antigüedad (meses)",   "int64",  False),
            # Aplanadas desde dim_representante: es exactamente la
            # desnormalización que pide un esquema estrella.
            (None, "Representante",      "string", False),
            (None, "Supervisor",         "string", False),
            (None, "Línea de promoción", "string", False),
        ],
        "jerarquias": {"Estructura comercial": ["Canal", "Segmento", "Cliente"]},
    },

    "v_dim_filial": {
        "origen": "dim_filial",
        "tipo": "dimension",
        "columnas": [
            ("id_filial",        "Id filial",           "int64",  True),
            ("cod_filial",       "Filial",              "string", False),
            ("pais",             "País",                "string", False),
            ("region",           "Región",              "string", False),
            ("moneda",           "Moneda local",        "string", False),
            ("sla_entrega_dias", "SLA entrega (días)",  "int64",  False),
        ],
        "jerarquias": {"Geografía": ["Región", "País"]},
    },

    "v_dim_deposito": {
        "origen": "dim_deposito",
        "tipo": "dimension",
        "columnas": [
            ("id_deposito",       "Id depósito",         "int64",  True),
            ("nombre_deposito",   "Depósito",            "string", False),
            ("id_filial",         "Id filial depósito",  "int64",  True),
            ("capacidad_pallets", "Capacidad (pallets)", "int64",  False),
            (None, "Capacidad de frío", "string", False),
        ],
    },

    "v_dim_transportista": {
        "origen": "dim_transportista",
        "tipo": "dimension",
        "columnas": [
            ("id_transportista", "Id transportista",         "int64",  True),
            ("transportista",    "Transportista",            "string", False),
            ("confiabilidad",    "Confiabilidad histórica",  "double", False),
            (None, "Control de temperatura", "string", False),
        ],
    },

    "v_dim_motivo_devolucion": {
        "origen": "dim_motivo_devolucion",
        "tipo": "dimension",
        "columnas": [
            ("id_motivo",        "Id motivo",            "int64",  True),
            ("cod_motivo",       "Código motivo",        "string", False),
            ("motivo",           "Motivo de devolución", "string", False),
            ("area_responsable", "Área responsable",     "string", False),
            (None, "Evitabilidad", "string", False),
        ],
    },

    "v_dim_tipo_oferta": {
        "origen": "dim_tipo_oferta",
        "tipo": "dimension",
        "columnas": [
            ("id_tipo_oferta",   "Id tipo oferta",  "int64",  True),
            ("cod_tipo_oferta",  "Código",          "string", False),
            ("tipo_oferta_desc", "Tipo de oferta",  "string", False),
            ("costo_relativo",   "Costo relativo",  "double", False),
        ],
    },

    # ================= HECHOS =================

    "v_fact_ventas": {
        "origen": "fact_ventas",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                  "Fecha",                    "dateTime", True),
            ("id_cliente",             "Id cliente",               "int64",  True),
            ("id_producto",            "Id producto",              "int64",  True),
            ("id_filial",              "Id filial",                "int64",  True),
            ("id_deposito",            "Id depósito",              "int64",  True),
            ("id_transportista",       "Id transportista",         "int64",  True),
            ("id_tipo_oferta",         "Id tipo oferta",           "int64",  True),
            ("tipo_documento",         "Tipo documento",           "string", False),
            ("unidades",               "Unidades",                 "int64",  True),
            ("importe_usd",            "Importe USD",              "double", True),
            ("costo_usd",              "Costo USD",                "double", True),
            ("importe_local",          "Importe moneda local",     "double", True),
            ("lineas",                 "Líneas",                   "int64",  True),
            ("lineas_otif",            "Líneas OTIF",              "int64",  True),
            ("lineas_completas",       "Líneas completas",         "int64",  True),
            ("lead_time_dias_x_linea", "Lead time x línea",        "double", True),
            ("unidades_devueltas",     "Unidades devueltas",       "int64",  True),
            ("importe_devuelto_usd",   "Importe devuelto USD",     "double", True),
            ("lineas_devueltas",       "Líneas devueltas",         "int64",  True),
            ("lineas_en_revision",     "Líneas en revisión",       "int64",  True),
            ("dias_a_vencer_x_linea",  "Días a vencer x línea",    "double", True),
            # +1 factura / −1 nota de crédito. Como columna y no como filtro
            # dentro de cada medida: así la regla vive en un solo lugar.
            (None, "Signo", "int64", True),
        ],
    },

    "v_fact_devoluciones": {
        "origen": "fact_devoluciones",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                "Fecha",                 "dateTime", True),
            ("id_cliente",           "Id cliente",            "int64",  True),
            ("id_producto",          "Id producto",           "int64",  True),
            ("id_filial",            "Id filial",             "int64",  True),
            ("id_transportista",     "Id transportista",      "int64",  True),
            ("id_motivo",            "Id motivo",             "int64",  True),
            ("unidades_devueltas",   "Unidades devueltas",    "int64",  True),
            ("importe_devuelto_usd", "Importe devuelto USD",  "double", True),
            ("lineas",               "Líneas devueltas",      "int64",  True),
        ],
    },

    "v_fact_ofertas": {
        "origen": "fact_ofertas",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                  "Fecha",                        "dateTime", True),
            ("id_cliente",             "Id cliente",                   "int64",  True),
            ("id_producto",            "Id producto",                  "int64",  True),
            ("id_filial",              "Id filial",                    "int64",  True),
            ("id_tipo_oferta",         "Id tipo oferta",               "int64",  True),
            ("descuento_pct",          "Descuento %",                  "double", True),
            ("unidades_ofertadas",     "Unidades ofertadas",           "int64",  True),
            ("cobertura_cliente_dias", "Cobertura del cliente (días)", "double", True),
            ("aceptada",               "Aceptada",                     "int64",  True),
            (None, "Ofertas", "int64", True),
        ],
    },

    "v_fact_sellout": {
        "origen": "fact_sellout",
        "tipo": "hecho",
        "columnas": [
            ("fecha",            "Fecha",                  "dateTime", True),
            ("id_filial",        "Id filial",              "int64",  True),
            ("id_producto",      "Id producto",            "int64",  True),
            ("unidades_sellout", "Unidades sell-out",      "int64",  True),
            ("importe_sellout",  "Importe sell-out USD",   "double", True),
            ("unidades_mercado", "Unidades mercado",       "int64",  True),
            ("importe_mercado",  "Importe mercado USD",    "double", True),
        ],
    },

    "v_fact_objetivos": {
        "origen": "fact_objetivos",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                "Fecha",              "dateTime", True),
            ("id_filial",            "Id filial",          "int64",  True),
            ("id_producto",          "Id producto",        "int64",  True),
            ("objetivo_importe_usd", "Objetivo USD",       "double", True),
            ("objetivo_unidades",    "Objetivo unidades",  "int64",  True),
        ],
    },

    "v_fact_stock": {
        "origen": "fact_stock",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                    "Fecha",                     "dateTime", True),
            ("id_deposito",              "Id depósito",               "int64",  True),
            ("id_producto",              "Id producto",               "int64",  True),
            ("stock_unidades",           "Stock unidades",            "int64",  True),
            ("valor_stock_usd",          "Valor de stock USD",        "double", True),
            ("stock_en_transito",        "Stock en tránsito",         "int64",  True),
            ("unidades_por_vencer_180d", "Unidades por vencer 180d",  "int64",  True),
            ("dias_a_vencer_promedio",   "Días a vencer promedio",    "int64",  True),
            ("unidades_mes",             "Consumo del mes",           "int64",  True),
            # Numerador del promedio ponderado. Promediar promedios da mal en
            # cuanto se cambia el nivel de agregación.
            (None, "Cobertura x stock", "double", True),
        ],
    },

    "v_fact_scoring_devoluciones": {
        "origen": "fact_scoring_devoluciones",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                 "Fecha",                       "dateTime", True),
            ("id_cliente",            "Id cliente",                  "int64",  True),
            ("id_producto",           "Id producto",                 "int64",  True),
            ("id_filial",             "Id filial",                   "int64",  True),
            ("id_transportista",      "Id transportista",            "int64",  True),
            ("unidades",              "Unidades",                    "int64",  True),
            ("importe_usd",           "Importe USD",                 "double", True),
            ("devuelta",              "Devuelta real",               "int64",  True),
            ("prob_devolucion",       "Probabilidad de devolución",  "double", True),
            ("banda_riesgo",          "Banda de riesgo",             "string", False),
            ("importe_en_riesgo_usd", "Importe en riesgo USD",       "double", True),
        ],
    },

    "v_fact_recomendaciones": {
        "origen": "fact_recomendaciones",
        "tipo": "hecho",
        "columnas": [
            ("mes_objetivo",               "Mes objetivo",                    "string", False),
            ("id_filial",                  "Id filial",                       "int64",  True),
            ("id_producto",                "Id producto",                     "int64",  True),
            ("canal",                      "Canal recomendado",               "string", False),
            ("segmento",                   "Segmento recomendado",            "string", False),
            ("rank_segmento",              "Ranking en el segmento",          "int64",  False),
            ("sku",                        "SKU recomendado",                 "string", False),
            ("marca",                      "Marca recomendada",               "string", False),
            ("descuento_pct",              "Descuento recomendado",           "double", True),
            ("precio_neto",                "Precio neto recomendado",         "double", True),
            ("margen_unitario",            "Margen unitario USD",             "double", True),
            ("elasticidad",                "Elasticidad estimada",            "double", True),
            ("nivel_estimacion",           "Nivel de estimación",             "string", False),
            ("indice_estacional",          "Índice estacional",               "double", True),
            ("aporte_margen_pct",          "Aporte al margen de la filial",   "double", True),
            ("dias_cobertura",             "Días de cobertura",               "double", True),
            ("unidades_por_vencer",        "Unidades por vencer",             "double", True),
            ("demanda_esperada",           "Demanda esperada",                "double", True),
            ("prob_aceptacion",            "Probabilidad de aceptación",      "double", True),
            ("riesgo_devolucion",          "Riesgo de devolución",            "double", True),
            ("margen_esperado_usd",        "Margen esperado USD",             "double", True),
            ("valor_rescate_usd",          "Valor de stock rescatado USD",    "double", True),
            ("ganancia_vs_sin_oferta_usd", "Ganancia vs no ofertar USD",      "double", True),
            ("justificativo",              "Justificativo",                   "string", False),
            (None, "Confianza de la recomendación", "string", False),
        ],
    },

    "v_forecast_devoluciones": {
        "origen": "fact_forecast_devoluciones",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                    "Fecha",                    "dateTime", True),
            ("id_filial",                "Id filial",                "int64",  True),
            ("tasa_dev_valor",           "Tasa dev real",            "double", True),
            ("tasa_dev_proyectada",      "Tasa dev proyectada",      "double", True),
            ("importe_dev",              "Importe dev real",         "double", True),
            ("importe_dev_proyectado",   "Importe dev proyectado",   "double", True),
            ("es_holdout",               "Es holdout",               "int64",  True),
        ],
    },

    "v_forecast_ofertas": {
        "origen": "fact_forecast_ofertas",
        "tipo": "hecho",
        "columnas": [
            ("fecha",                     "Fecha",                       "dateTime", True),
            ("id_filial",                 "Id filial",                   "int64",  True),
            ("inversion_usd",             "Inversión USD",               "double", True),
            ("inversion_proyectada_usd",  "Inversión proyectada USD",    "double", True),
            ("ofertas",                   "Ofertas del mes",             "int64",  True),
            ("aceptadas",                 "Aceptadas del mes",           "int64",  True),
            ("es_holdout",                "Es holdout",                  "int64",  True),
        ],
    },

    "v_estado_datos": {
        "origen": "fact_estado_datos",
        "tipo": "servicio",
        "columnas": [
            ("ultimo_dato",        "Último dato",          "dateTime", False),
            ("controles_criticos", "Controles críticos",   "int64",    True),
            ("controles_alerta",   "Controles en alerta",  "int64",    True),
            ("controles_ok",       "Controles OK",         "int64",    True),
            ("ultima_validacion",  "Última validación",    "dateTime", False),
        ],
    },
}


# --------------------------------------------------------------------------
# Columnas derivadas en Power Query (M).
# Se calculan al cargar, no en DAX: transformar lo más arriba posible.
# --------------------------------------------------------------------------
DERIVADAS: dict[str, list[tuple[str, str, str]]] = {
    # tabla: [(nombre visible, expresión M sobre [_], tipo M)]
    "v_dim_producto": [
        ("Condición de conservación",
         'if [cadena_frio] then "Cadena de frío" else "Temperatura ambiente"', "type text"),
        ("Origen del costo",
         'if [costo_imputado] = 1 then "Costo imputado" else "Costo real"', "type text"),
    ],
    "v_dim_deposito": [
        ("Capacidad de frío",
         'if [tiene_camara_frio] then "Con cámara de frío" else "Sin cámara de frío"', "type text"),
    ],
    "v_dim_transportista": [
        ("Control de temperatura",
         'if [control_frio] then "Con control de frío" else "Sin control de frío"', "type text"),
    ],
    "v_dim_motivo_devolucion": [
        ("Evitabilidad",
         'if [es_evitable] = 1 then "Evitable" else "No evitable"', "type text"),
    ],
    "v_fact_ventas": [
        ("Signo", 'if [tipo_documento] = "NC" then -1 else 1', "Int64.Type"),
    ],
    "v_fact_ofertas": [
        ("Ofertas", "1", "Int64.Type"),
    ],
    "v_fact_stock": [
        ("Cobertura x stock",
         "[dias_cobertura] * [stock_unidades]", "type number"),
    ],
    "v_fact_recomendaciones": [
        ("Confianza de la recomendación",
         'if [en_borde_de_soporte] = 1 then "Requiere test controlado" '
         'else "Dentro de evidencia histórica"', "type text"),
    ],
}

# Tablas que se aplanan dentro de otra (desnormalización de estrella)
APLANAR = {
    "v_dim_cliente": {
        "tabla": "dim_representante",
        "clave": "id_representante",
        "columnas": {
            "nombre_rep": "Representante",
            "supervisor": "Supervisor",
            "linea_promocion": "Línea de promoción",
        },
    },
}


# --------------------------------------------------------------------------
# Relaciones — todas 1:muchos, dirección simple, ninguna bidireccional.
# (tabla_1, columna_1, tabla_muchos, columna_muchos)
# --------------------------------------------------------------------------
RELACIONES: list[tuple[str, str, str, str]] = []

_HECHOS_CON_FECHA = [
    "v_fact_ventas", "v_fact_devoluciones", "v_fact_ofertas", "v_fact_sellout",
    "v_fact_objetivos", "v_fact_stock", "v_fact_scoring_devoluciones",
    "v_forecast_devoluciones", "v_forecast_ofertas",
]
for _h in _HECHOS_CON_FECHA:
    RELACIONES.append(("v_dim_calendario", "Fecha", _h, "Fecha"))

_POR_DIMENSION = {
    "v_dim_producto": ("Id producto", [
        "v_fact_ventas", "v_fact_devoluciones", "v_fact_ofertas", "v_fact_sellout",
        "v_fact_objetivos", "v_fact_stock", "v_fact_scoring_devoluciones",
        "v_fact_recomendaciones",
    ]),
    "v_dim_cliente": ("Id cliente", [
        "v_fact_ventas", "v_fact_devoluciones", "v_fact_ofertas",
        "v_fact_scoring_devoluciones",
    ]),
    "v_dim_filial": ("Id filial", [
        "v_fact_ventas", "v_fact_devoluciones", "v_fact_ofertas", "v_fact_sellout",
        "v_fact_objetivos", "v_fact_scoring_devoluciones", "v_fact_recomendaciones",
        "v_forecast_devoluciones", "v_forecast_ofertas",
    ]),
    "v_dim_deposito": ("Id depósito", ["v_fact_ventas", "v_fact_stock"]),
    "v_dim_transportista": ("Id transportista", [
        "v_fact_ventas", "v_fact_devoluciones", "v_fact_scoring_devoluciones",
    ]),
    "v_dim_tipo_oferta": ("Id tipo oferta", ["v_fact_ventas", "v_fact_ofertas"]),
    "v_dim_motivo_devolucion": ("Id motivo", ["v_fact_devoluciones"]),
}
for _dim, (_col, _hechos) in _POR_DIMENSION.items():
    for _h in _hechos:
        RELACIONES.append((_dim, _col, _h, _col))


# --------------------------------------------------------------------------
# Formatos. Consistentes en los tres tableros: importes sin decimales,
# porcentajes con un decimal, variaciones en pp con un decimal.
# --------------------------------------------------------------------------
def formato_de(nombre: str) -> str | None:
    n = nombre.lower()
    if n.startswith(("semáforo", "estado", "alerta", "título", "lectura", "titular",
                     "justificativo", "nota", "origen de", "motivo principal",
                     "encabezado")):
        return None                      # medidas de texto
    if "pp" in n.split() or n.endswith(" pp"):
        return "#,0.0"
    if "%" in nombre:
        return "0.0%"
    if n.startswith("precisión") or n.startswith("captura") or n.startswith("roi"):
        return "0.0%"
    if "usd" in n or n.startswith("objetivo") or n.startswith("gap"):
        return "#,0"
    if n.startswith(("días", "lead time", "sla", "exceso")):
        return "#,0.0"
    if n.startswith(("ofertas", "líneas", "unidades", "pedidos", "recomendaciones",
                     "sku que", "stock unidades")):
        return "#,0"
    if n.startswith("probabilidad") or n.startswith("descuento recomendado"):
        return "0.0%"
    return "#,0.00"


# --------------------------------------------------------------------------
# Páginas de cada tablero. Definen qué .pbit se genera.
# --------------------------------------------------------------------------
#
# Los TRES archivos llevan la biblioteca DAX COMPLETA, no solo la de su tablero.
#
# Es deliberado y es el punto central de la arquitectura: no son tres modelos
# semánticos distintos, es el mismo modelo con tres reportes encima. Por eso
# "Ventas Netas USD" significa exactamente lo mismo en los tres, el
# drill-through entre tableros conserva el contexto de filtro, y una página de
# VAR puede mostrar la tasa de devolución sin duplicar la definición.
#
# En producción esto se publica UNA vez como modelo semántico compartido y los
# tres reportes se conectan por Live Connection. Acá van completos en cada
# archivo para que cada .pbit se pueda abrir suelto.
#
BIBLIOTECA_DAX = [
    "00_medidas_base.dax",
    "01_var_ventas.dax",
    "02_ofertas.dax",
    "03_logistica.dax",
]

TABLEROS = {
    "VAR": {"titulo": "Adium · VAR — Ventas, Análisis y Rentabilidad",
            "dax": BIBLIOTECA_DAX},
    "Ofertas": {"titulo": "Adium · Ofertas — Política comercial y recomendación de IA",
                "dax": BIBLIOTECA_DAX},
    "Logistica": {"titulo": "Adium · Logística — Nivel de servicio, devoluciones y riesgo",
                  "dax": BIBLIOTECA_DAX},
}
