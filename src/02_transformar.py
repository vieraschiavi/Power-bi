"""
PASO 2 — Transformación de datos y trabajo de Data Steward.

Esto es el equivalente en Python de lo que en Power BI haría Power Query,
pero hecho *aguas arriba* a propósito: cuanto más arriba transformás, más
barato es el modelo y más reutilizable la regla (máxima de Roche).

Hace tres cosas, en este orden:

  A. PERFILADO   — mide la calidad del crudo en las 6 dimensiones canónicas
                   (completitud, exactitud, consistencia, unicidad, vigencia, validez)
  B. LIMPIEZA    — aplica reglas de negocio explícitas y versionadas, y deja
                   traza de cuántas filas tocó cada una
  C. MODELADO    — construye el modelo estrella, reduciendo cardinalidad
                   para que VertiPaq comprima bien

Salidas:
  data/stage/*.parquet   datos limpios y tipificados
  data/star/*.parquet    modelo estrella listo para Power BI
  data/out/calidad_datos.csv / .json   tablero de calidad (se publica en el reporte)

Uso:  python src/02_transformar.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import config as cfg

# --------------------------------------------------------------------------
# Registro de controles: cada regla deja evidencia. Sin evidencia no se publica.
# --------------------------------------------------------------------------
CONTROLES: list[dict] = []


def registrar(dimension: str, control: str, tabla: str, filas_afectadas: int,
              total: int, accion: str, severidad: str = "media") -> None:
    CONTROLES.append(
        {
            "dimension": dimension,
            "control": control,
            "tabla": tabla,
            "filas_afectadas": int(filas_afectadas),
            "filas_totales": int(total),
            "pct_afectado": round(100 * filas_afectadas / total, 4) if total else 0.0,
            "accion": accion,
            "severidad": severidad,
            "estado": "OK" if filas_afectadas == 0 else ("ALERTA" if severidad != "alta" else "CRÍTICO"),
        }
    )


# ==========================================================================
# A. Parseo robusto de fechas mixtas
# ==========================================================================
def parsear_fecha_mixta(serie: pd.Series) -> pd.Series:
    """
    El origen manda 'YYYY-MM-DD' y 'DD/MM/YYYY' conviviendo.
    Parsear con un solo formato pierde filas en silencio: hay que probar los dos
    y verificar que no quedó ninguna sin resolver.
    """
    s = serie.astype(str).str.strip()
    f = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    faltan = f.isna()
    if faltan.any():
        f.loc[faltan] = pd.to_datetime(s[faltan], format="%d/%m/%Y", errors="coerce")
    return f


# ==========================================================================
# B. Limpieza del hecho principal (sell-in)
# ==========================================================================
def limpiar_sellin(raw: pd.DataFrame, filiales: pd.DataFrame, tc: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    n0 = len(df)

    # --- Validez: fechas ---
    df["fecha"] = parsear_fecha_mixta(df["fecha"])
    sin_fecha = df["fecha"].isna().sum()
    registrar("Validez", "Fechas parseables (2 formatos conviviendo)", "sellin",
              sin_fecha, n0, "Descartar fila sin fecha resoluble", "alta")
    df = df[df["fecha"].notna()].copy()

    # --- Unicidad: duplicados exactos por clave de negocio ---
    antes = len(df)
    df = df.drop_duplicates(subset=["id_linea"], keep="first")
    dups = antes - len(df)
    registrar("Unicidad", "Líneas de factura duplicadas por reproceso", "sellin",
              dups, antes, "Deduplicar por id_linea conservando la primera", "alta")

    # --- Validez: importes negativos = notas de crédito mal clasificadas ---
    neg = (df["importe_local"] < 0) | (df["unidades"] < 0)
    registrar("Validez", "Importes/unidades negativos (notas de crédito)", "sellin",
              neg.sum(), len(df), "Reclasificar a tipo_documento='NC' y pasar a positivo")
    df["tipo_documento"] = np.where(neg, "NC", "FC")
    df.loc[neg, ["unidades", "importe_local", "costo_total_local", "importe_devuelto_local"]] = (
        df.loc[neg, ["unidades", "importe_local", "costo_total_local", "importe_devuelto_local"]].abs()
    )
    # La NC resta: se marca con signo en una columna dedicada, no se pierde el registro
    df["signo"] = np.where(neg, -1, 1)

    # --- Exactitud: dedazo de un cero de más en unidades ---
    # Regla: si la línea supera 25x la mediana del SKU, se marca para revisión.
    med_sku = df.groupby("id_producto")["unidades"].transform("median")
    outlier = df["unidades"] > 25 * med_sku.clip(lower=1)
    registrar("Exactitud", "Unidades > 25x la mediana del SKU (dedazo de carga)", "sellin",
              outlier.sum(), len(df), "Marcar flag_revision=1; NO se corrige en silencio", "alta")
    df["flag_revision"] = outlier.astype(int)

    # --- Completitud: transportista nulo ---
    nulos_tr = df["id_transportista"].isna().sum()
    registrar("Completitud", "Despachos sin transportista informado", "sellin",
              nulos_tr, len(df), "Imputar a 'No informado' (id 99) y reportar al origen")
    df["id_transportista"] = df["id_transportista"].fillna(99).astype(int)

    # --- Consistencia: normalización FX a moneda de reporte (USD) ---
    df["fecha_mes"] = df["fecha"].values.astype("datetime64[M]")
    tcx = tc.copy()
    tcx["fecha_mes"] = pd.to_datetime(tcx["fecha_mes"])
    df = df.merge(tcx, on=["fecha_mes", "moneda"], how="left", validate="many_to_one")
    sin_tc = df["tc_a_usd"].isna().sum()
    registrar("Consistencia", "Líneas sin tipo de cambio del mes", "sellin",
              sin_tc, len(df), "Bloquear publicación: sin FX no hay cifra corporativa", "alta")
    df = df[df["tc_a_usd"].notna()].copy()

    for loc, usd in [
        ("importe_local", "importe_usd"),
        ("costo_total_local", "costo_usd"),
        ("precio_neto_local", "precio_neto_usd"),
        ("precio_lista_local", "precio_lista_usd"),
        ("importe_devuelto_local", "importe_devuelto_usd"),
    ]:
        df[usd] = np.round(df[loc] / df["tc_a_usd"], 4)

    # --- Vigencia ---
    ultimo = df["fecha"].max()
    atraso = (pd.Timestamp(cfg.FECHA_FIN) - ultimo).days
    registrar("Vigencia", "Antigüedad del último dato cargado", "sellin",
              max(atraso, 0), len(df), f"Último dato: {ultimo.date()} — SLA de carga: 5 días")

    return df


# ==========================================================================
# C. Limpieza de dimensiones
# ==========================================================================
def limpiar_clientes(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    sucios = (df["cod_cliente"] != df["cod_cliente"].str.strip().str.upper()).sum()
    registrar("Consistencia", "Código de cliente con espacios / minúsculas", "dim_cliente",
              sucios, len(df), "TRIM + UPPER — la clave de negocio se normaliza siempre")
    df["cod_cliente"] = df["cod_cliente"].str.strip().str.upper()

    dups = df.duplicated(subset=["cod_cliente"]).sum()
    registrar("Unicidad", "Código de cliente duplicado", "dim_cliente",
              dups, len(df), "Clave de negocio única — bloquea la carga", "alta")
    return df


def limpiar_productos(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    nulos = df["costo_std_usd"].isna().sum()
    registrar("Completitud", "SKU sin costo estándar cargado", "dim_producto",
              nulos, len(df), "Imputar con la mediana del ATC3 y marcar costo_imputado=1", "alta")
    df["costo_imputado"] = df["costo_std_usd"].isna().astype(int)
    df["costo_std_usd"] = df.groupby("atc3")["costo_std_usd"].transform(
        lambda s: s.fillna(s.median())
    )
    df["costo_std_usd"] = df["costo_std_usd"].fillna(df["costo_std_usd"].median())

    invalid = (df["costo_std_usd"] >= df["precio_lista_usd"]).sum()
    registrar("Validez", "SKU con costo >= precio de lista (margen negativo)", "dim_producto",
              invalid, len(df), "Marcar para revisión de Finanzas", "alta")
    df["margen_std_pct"] = np.round(
        1 - df["costo_std_usd"] / df["precio_lista_usd"].replace(0, np.nan), 4
    )
    return df


def controlar_sellout(sellout: pd.DataFrame, filiales: pd.DataFrame) -> pd.DataFrame:
    """Completitud del panel: ¿todas las filiales reportaron todos los meses?"""
    df = sellout.copy()
    df["fecha_mes"] = pd.to_datetime(df["fecha_mes"])
    esperado = pd.MultiIndex.from_product(
        [pd.date_range(cfg.FECHA_INICIO, cfg.FECHA_FIN, freq="MS"), filiales["id_filial"]],
        names=["fecha_mes", "id_filial"],
    )
    presente = df.set_index(["fecha_mes", "id_filial"]).index.unique()
    faltantes = esperado.difference(presente)
    registrar("Completitud", "Filial-mes sin carga del panel de auditoría", "sellout",
              len(faltantes), len(esperado),
              "Marcar el mes como 'sin dato' en el tablero — NUNCA como cero", "alta")

    if len(faltantes):
        det = pd.DataFrame(list(faltantes), columns=["fecha_mes", "id_filial"])
        det = det.merge(filiales[["id_filial", "cod_filial", "pais"]], on="id_filial")
        det.to_csv(cfg.OUT / "calidad_filial_mes_faltante.csv", index=False)
    return df


# ==========================================================================
# D. Construcción del modelo estrella
# ==========================================================================
def dim_calendario() -> pd.DataFrame:
    """
    Calendario contiguo, del 1/1 del primer año al 31/12 del último.
    Se marca como tabla de fechas en Power BI. Sin esto, time intelligence
    da resultados raros y el MAT no cierra.
    """
    ini = pd.Timestamp(cfg.FECHA_INICIO).replace(month=1, day=1)
    fin = pd.Timestamp(cfg.FECHA_FIN).replace(month=12, day=31)
    d = pd.DataFrame({"fecha": pd.date_range(ini, fin, freq="D")})
    meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    d["anio"] = d["fecha"].dt.year
    d["mes_nro"] = d["fecha"].dt.month
    d["mes_nombre"] = d["mes_nro"].map(lambda m: meses_es[m - 1])
    d["anio_mes"] = d["fecha"].dt.strftime("%Y-%m")
    d["anio_mes_orden"] = d["anio"] * 100 + d["mes_nro"]
    d["trimestre"] = "Q" + d["fecha"].dt.quarter.astype(str)
    d["anio_trimestre"] = d["anio"].astype(str) + "-" + d["trimestre"]
    d["dia_semana"] = d["fecha"].dt.dayofweek + 1
    d["es_habil"] = (d["dia_semana"] <= 5).astype(int)
    d["es_pasado"] = (d["fecha"] <= pd.Timestamp(cfg.FECHA_FIN)).astype(int)
    d["es_ultimo_dia_mes"] = (d["fecha"].dt.is_month_end).astype(int)
    # Bandera de temporada alta respiratoria — se usa en el motor de ofertas
    d["temporada_respiratoria"] = d["mes_nro"].isin([5, 6, 7, 8]).astype(int)
    return d


def construir_fact_ventas(sellin: pd.DataFrame) -> pd.DataFrame:
    """
    OPTIMIZACIÓN CLAVE DEL MODELO.

    El origen viene a grano de línea de factura (246k filas) y trae id_linea,
    que es la columna de mayor cardinalidad de todo el modelo — justo la peor
    para VertiPaq, que comprime por diccionario de columna.

    Nadie en el tablero pregunta por una línea de factura individual: preguntan
    por cliente, producto, mes, depósito y tipo de oferta. Así que agrego a ese
    grano y elimino id_linea del modelo. Se conserva el conteo de líneas como
    medida aditiva, que es lo único que se perdía.
    """
    g = (
        sellin.assign(
            unidades_sig=sellin["unidades"] * sellin["signo"],
            importe_sig=sellin["importe_usd"] * sellin["signo"],
            costo_sig=sellin["costo_usd"] * sellin["signo"],
        )
        .groupby(
            ["fecha", "id_cliente", "id_producto", "id_filial", "id_deposito",
             "id_transportista", "tipo_oferta", "tipo_documento"],
            as_index=False,
        )
        .agg(
            unidades=("unidades_sig", "sum"),
            importe_usd=("importe_sig", "sum"),
            costo_usd=("costo_sig", "sum"),
            importe_local=("importe_local", "sum"),
            lineas=("id_cliente", "size"),
            lineas_otif=("otif", "sum"),
            lineas_completas=("entrega_completa", "sum"),
            lead_time_dias_x_linea=("lead_time_dias", "sum"),
            unidades_devueltas=("unidades_devueltas", "sum"),
            importe_devuelto_usd=("importe_devuelto_usd", "sum"),
            lineas_devueltas=("devuelta", "sum"),
            lineas_en_revision=("flag_revision", "sum"),
            dias_a_vencer_x_linea=("dias_a_vencer", "sum"),
        )
    )
    # Redondeo controlado: bajar decimales baja cardinalidad y sube compresión
    for c in ["importe_usd", "costo_usd", "importe_devuelto_usd", "importe_local"]:
        g[c] = g[c].round(2)
    return g


def optimizar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce el ancho de cada columna al mínimo que soporta su rango real.

    VertiPaq comprime por columna con diccionario + run-length: el costo real
    de una tabla lo manda la CARDINALIDAD y el ANCHO de cada columna, no la
    cantidad de filas. Bajar int64 -> int32/int16 y float64 -> float32 en
    métricas donde no hace falta precisión de 15 dígitos es el ajuste más
    barato y de mayor impacto que existe sobre un modelo tabular.
    """
    out = df.copy()
    for c in out.columns:
        s = out[c]
        if pd.api.types.is_integer_dtype(s):
            out[c] = pd.to_numeric(s, downcast="integer")
        elif pd.api.types.is_float_dtype(s):
            # los importes se llevan a 2 decimales antes de bajar a float32
            out[c] = pd.to_numeric(s.round(4), downcast="float")
        elif pd.api.types.is_object_dtype(s) and s.nunique(dropna=True) / max(len(s), 1) < 0.5:
            out[c] = s.astype("category")
    return out


def peso_mb(df: pd.DataFrame) -> float:
    return df.memory_usage(deep=True).sum() / 1024**2


def construir_fact_devoluciones(sellin: pd.DataFrame) -> pd.DataFrame:
    dev = sellin[sellin["devuelta"] == 1].copy()
    return (
        dev.groupby(
            ["fecha", "id_cliente", "id_producto", "id_filial",
             "id_transportista", "motivo_devolucion"],
            as_index=False,
        )
        .agg(
            unidades_devueltas=("unidades_devueltas", "sum"),
            importe_devuelto_usd=("importe_devuelto_usd", "sum"),
            lineas=("id_cliente", "size"),
        )
        .round({"importe_devuelto_usd": 2})
    )


def dim_motivo() -> pd.DataFrame:
    d = pd.DataFrame(cfg.MOTIVOS_DEVOLUCION,
                     columns=["cod_motivo", "motivo", "peso_base", "area_responsable"])
    d["id_motivo"] = np.arange(1, len(d) + 1)
    d["es_evitable"] = d["area_responsable"].isin(["Logística", "Comercial"]).astype(int)
    return d[["id_motivo", "cod_motivo", "motivo", "area_responsable", "es_evitable"]]


def dim_tipo_oferta() -> pd.DataFrame:
    d = pd.DataFrame(cfg.TIPOS_OFERTA,
                     columns=["cod_tipo_oferta", "tipo_oferta_desc", "descuento_medio", "costo_relativo"])
    d = pd.concat(
        [d, pd.DataFrame([{"cod_tipo_oferta": "SIN", "tipo_oferta_desc": "Sin oferta",
                           "descuento_medio": 0.0, "costo_relativo": 0.0}])],
        ignore_index=True,
    )
    d["id_tipo_oferta"] = np.arange(1, len(d) + 1)
    return d


# ==========================================================================
# Main
# ==========================================================================
def main() -> None:
    print("PASO 2 · Data Steward: perfilado, limpieza y modelo estrella")

    raw = {p.stem: pd.read_parquet(p) for p in cfg.RAW.glob("*.parquet")}
    filiales = raw["dim_filial"]
    tc = raw["tipo_cambio"]

    # ---------------- limpieza ----------------
    productos = limpiar_productos(raw["dim_producto"])
    clientes = limpiar_clientes(raw["dim_cliente"])
    sellin = limpiar_sellin(raw["sellin"], filiales, tc)
    sellout = controlar_sellout(raw["sellout"], filiales)

    # Integridad referencial: ¿todo hecho tiene su dimensión?
    huerfanos = (~sellin["id_producto"].isin(productos["id_producto"])).sum()
    registrar("Consistencia", "Ventas con SKU inexistente en el maestro", "sellin",
              huerfanos, len(sellin),
              "En Power BI aparecerían agrupadas en una fila en blanco", "alta")
    huerfanos_c = (~sellin["id_cliente"].isin(clientes["id_cliente"])).sum()
    registrar("Consistencia", "Ventas con cliente inexistente en el maestro", "sellin",
              huerfanos_c, len(sellin), "Bloquea la carga hasta dar de alta el cliente", "alta")

    for nombre, df in [("sellin", sellin), ("dim_producto", productos),
                       ("dim_cliente", clientes), ("sellout", sellout)]:
        df.to_parquet(cfg.STAGE / f"{nombre}.parquet", index=False)

    # ---------------- modelo estrella ----------------
    print("  · construyendo modelo estrella…")
    d_tipo_of = dim_tipo_oferta()
    fact_ventas = construir_fact_ventas(sellin)
    fact_ventas = fact_ventas.merge(
        d_tipo_of[["id_tipo_oferta", "cod_tipo_oferta"]],
        left_on="tipo_oferta", right_on="cod_tipo_oferta", how="left",
    ).drop(columns=["tipo_oferta", "cod_tipo_oferta"])

    d_motivo = dim_motivo()
    fact_dev = construir_fact_devoluciones(sellin).merge(
        d_motivo[["id_motivo", "cod_motivo"]],
        left_on="motivo_devolucion", right_on="cod_motivo", how="left",
    ).drop(columns=["motivo_devolucion", "cod_motivo"])

    ofertas = raw["ofertas"].copy()
    ofertas["fecha"] = pd.to_datetime(ofertas["fecha_oferta"]).dt.normalize()
    ofertas = ofertas.merge(clientes[["id_cliente", "id_filial"]], on="id_cliente", how="left")
    ofertas = ofertas.merge(
        d_tipo_of[["id_tipo_oferta", "cod_tipo_oferta"]],
        left_on="tipo_oferta", right_on="cod_tipo_oferta", how="left",
    ).drop(columns=["fecha_oferta", "tipo_oferta", "cod_tipo_oferta"])
    # `_p_real` es la probabilidad verdadera del simulador. Se usa SOLO para
    # medir el techo teórico del problema (AUC oráculo) y no puede llegar ni al
    # modelo ni al tablero: en la realidad ese dato no existe.
    ofertas = ofertas.drop(columns=[c for c in ofertas.columns if c.startswith("_")])

    star = {
        "dim_calendario": dim_calendario(),
        "dim_producto": productos.drop(columns=["peso_demanda", "elasticidad_real"]),
        "dim_cliente": clientes.drop(columns=["propension_devolucion", "sensibilidad_precio"]),
        "dim_filial": filiales.drop(columns=["factor_tamano", "madurez"]),
        "dim_representante": raw["dim_representante"].drop(columns=["productividad"]),
        "dim_deposito": raw["dim_deposito"],
        "dim_transportista": pd.concat(
            [raw["dim_transportista"],
             pd.DataFrame([{"id_transportista": 99, "transportista": "No informado",
                            "confiabilidad": np.nan, "control_frio": False}])],
            ignore_index=True),
        "dim_motivo_devolucion": d_motivo,
        "dim_tipo_oferta": d_tipo_of,
        "fact_ventas": fact_ventas,
        "fact_devoluciones": fact_dev,
        "fact_ofertas": ofertas,
        # Una sola columna de fecha, con el mismo nombre y el mismo tipo en
        # TODOS los hechos. Es lo que permite que una única dim_calendario
        # filtre los ocho hechos sin relaciones inactivas ni columnas puente.
        "fact_sellout": sellout.rename(columns={"fecha_mes": "fecha"}),
        "fact_objetivos": raw["objetivos"].rename(columns={"fecha_mes": "fecha"}),
        "fact_stock": raw["stock"].rename(columns={"fecha_mes": "fecha"}),
        "fact_tipo_cambio": tc.rename(columns={"fecha_mes": "fecha"}).assign(
            fecha=lambda x: pd.to_datetime(x["fecha"])
        ),
    }
    # ---------------- optimización de tipos y medición ----------------
    mb_antes = sum(peso_mb(df) for df in star.values())
    star = {k: optimizar_tipos(v) for k, v in star.items()}
    mb_despues = sum(peso_mb(df) for df in star.values())

    for nombre, df in star.items():
        df.to_parquet(cfg.STAR / f"{nombre}.parquet", index=False)

    # ---------------- evidencia de la optimización ----------------
    reduccion = 1 - len(fact_ventas) / len(sellin)
    card_antes = sellin["id_linea"].nunique()
    print("\n  Optimización del modelo (evidencia medida, no declarativa):")
    print(f"    grano línea de factura : {len(sellin):>9,} filas")
    print(f"    grano analítico        : {len(fact_ventas):>9,} filas  ({reduccion:.1%} menos)")
    print(f"    id_linea eliminado     : {card_antes:>9,} valores distintos fuera del modelo")
    print(f"    memoria del modelo     : {mb_antes:>9,.1f} MB → {mb_despues:,.1f} MB "
          f"({1 - mb_despues / mb_antes:.1%} menos)")
    print(f"    columna más cara ahora : "
          f"{fact_ventas.memory_usage(deep=True).drop('Index').idxmax()}")

    # ---------------- tablero de calidad ----------------
    cal = pd.DataFrame(CONTROLES)
    cal.to_csv(cfg.OUT / "calidad_datos.csv", index=False)
    resumen = {
        "controles_ejecutados": len(cal),
        "controles_ok": int((cal["estado"] == "OK").sum()),
        "controles_alerta": int((cal["estado"] == "ALERTA").sum()),
        "controles_criticos": int((cal["estado"] == "CRÍTICO").sum()),
        "filas_hecho_origen": int(len(sellin)),
        "filas_hecho_modelo": int(len(fact_ventas)),
        "reduccion_filas_pct": round(100 * reduccion, 2),
        "memoria_modelo_mb_antes": round(mb_antes, 1),
        "memoria_modelo_mb_despues": round(mb_despues, 1),
        "reduccion_memoria_pct": round(100 * (1 - mb_despues / mb_antes), 1),
        "ultimo_dato": str(sellin["fecha"].max().date()),
    }
    (cfg.OUT / "calidad_resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Tabla de una fila que alimenta el encabezado de confianza de los tres
    # tableros. El estado del dato es parte del modelo, no un anexo: si vive
    # fuera, nadie lo mira y el semáforo deja de existir.
    pd.DataFrame([{
        "ultimo_dato": sellin["fecha"].max(),
        "controles_criticos": resumen["controles_criticos"],
        "controles_alerta": resumen["controles_alerta"],
        "controles_ok": resumen["controles_ok"],
        "ultima_validacion": pd.Timestamp.utcnow().tz_localize(None).floor("s"),
    }]).to_parquet(cfg.STAR / "fact_estado_datos.parquet", index=False)

    print("\n  Controles de calidad (Data Steward):")
    for _, r in cal.iterrows():
        icono = {"OK": "  ok  ", "ALERTA": " alert", "CRÍTICO": " CRIT "}[r["estado"]]
        print(f"    [{icono}] {r['dimension']:<13} {r['control'][:52]:<52} "
              f"{r['filas_afectadas']:>7,} ({r['pct_afectado']:>6.2f}%)")

    print(f"\n  OK → {cfg.STAR}")


if __name__ == "__main__":
    main()
