# © 2026 Martín Viera. Todos los derechos reservados.

"""
PASO 5 — Motor de IA para recomendación de PRECIO y PRODUCTO por segmento.

Qué responde:
   "Para cada segmento comercial, ¿qué producto conviene ofertar el mes que
    viene, a qué descuento, y por qué?"

Cómo lo hace (cuatro piezas, ninguna es una caja negra):

  1. ELASTICIDAD PRECIO estimada del histórico, con regresión log-log y
     jerarquía de respaldo producto → ATC3 → ATC1 → global. Nunca se usa una
     elasticidad estimada con pocos datos: se hereda del nivel superior.

  2. PROBABILIDAD DE ACEPTACIÓN del modelo calibrado del paso 4, evaluada
     CONTRAFÁCTICAMENTE sobre una grilla de descuentos. Esto es lo que
     convierte un modelo predictivo en un modelo de decisión.

  3. OPTIMIZACIÓN del margen esperado neto sobre esa grilla, penalizando por
     riesgo de devolución (paso 3) y premiando la liberación de stock crítico.

  4. JUSTIFICATIVO en lenguaje natural, generado por reglas a partir de las
     mismas variables que entraron en la decisión. Explicable y auditable:
     un comercial puede discutir cada término.

Factores que exige el negocio y están explícitos en la función objetivo:
     · época del año  -> índice estacional por clase ATC
     · stock          -> días de cobertura y unidades por vencer
     · aporte         -> margen unitario y contribución del SKU al margen total

Salidas:
  data/out/recomendaciones_ofertas.csv        (legible, para el comercial)
  data/star/fact_recomendaciones.parquet      (para Power BI)
  data/ml/elasticidades.csv                   (auditoría del modelo de precio)

Uso:  python src/05_ia_precios.py
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

import config as cfg

GRILLA_DESCUENTO = np.round(np.arange(0.02, 0.36, 0.02), 3)
MIN_OBS_ELASTICIDAD = 60      # observaciones mínimas para creerle a una elasticidad
MES_OBJETIVO = "2026-01"      # el mes que se está planificando

# Regla de negocio, no de modelo: ninguna oferta puede dejar el margen bruto
# por debajo de este piso. Sin esta restricción el optimizador encuentra
# descuentos que "maximizan" volumen destruyendo rentabilidad, que es
# exactamente lo que el área comercial no quiere que pase.
MARGEN_MINIMO_PCT = 0.15


# ==========================================================================
# 1. Elasticidad precio
# ==========================================================================
def estimar_elasticidades(sellin: pd.DataFrame, prod: pd.DataFrame) -> pd.DataFrame:
    """
    Regresión log-log:  log(unidades) = a + e·log(precio_neto) + efectos fijos de mes

    El coeficiente `e` ES la elasticidad precio de la demanda: cuánto cambia
    porcentualmente la cantidad ante un cambio porcentual del precio.

    Dos cuidados que hacen la diferencia entre una elasticidad usable y una
    espuria:
      · controlar por mes (si no, la estacionalidad se confunde con el precio,
        porque justamente se descuenta más fuera de temporada)
      · exigir un mínimo de observaciones y de variación real de precio; si no
        hay variación de precio, no hay nada que estimar
    """
    df = sellin[(sellin["unidades"] > 0) & (sellin["precio_neto_usd"] > 0)].copy()
    df["log_q"] = np.log(df["unidades"])
    df["log_p"] = np.log(df["precio_neto_usd"])
    df["mes"] = df["fecha"].dt.month
    df = df.merge(prod[["id_producto", "atc1", "atc3"]], on="id_producto", how="left")

    def _ols_con_efectos_mes(g: pd.DataFrame) -> tuple[float, float, int]:
        """Devuelve (elasticidad, R², n). Efectos fijos de mes por dummies."""
        n = len(g)
        if n < MIN_OBS_ELASTICIDAD or g["log_p"].std() < 0.02:
            return np.nan, np.nan, n
        D = pd.get_dummies(g["mes"], prefix="m", drop_first=True, dtype=float)
        X = np.column_stack([np.ones(n), g["log_p"].to_numpy(), D.to_numpy()])
        y = g["log_q"].to_numpy()
        try:
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            return np.nan, np.nan, n
        resid = y - X @ beta
        sst = ((y - y.mean()) ** 2).sum()
        r2 = 1 - (resid ** 2).sum() / sst if sst > 0 else np.nan
        return float(beta[1]), float(r2), n

    niveles = {}
    for nivel, clave in [("producto", "id_producto"), ("atc3", "atc3"), ("atc1", "atc1")]:
        filas = []
        for k, g in df.groupby(clave, observed=True):
            e, r2, n = _ols_con_efectos_mes(g)
            filas.append({clave: k, f"elast_{nivel}": e, f"r2_{nivel}": r2, f"n_{nivel}": n})
        niveles[nivel] = pd.DataFrame(filas)

    e_global, r2_global, n_global = _ols_con_efectos_mes(df)

    out = (
        prod[["id_producto", "sku", "marca", "atc1", "atc3"]]
        .merge(niveles["producto"], on="id_producto", how="left")
        .merge(niveles["atc3"], on="atc3", how="left")
        .merge(niveles["atc1"], on="atc1", how="left")
    )
    # Jerarquía de respaldo: se usa el nivel más específico que sea creíble
    out["elasticidad"] = (
        out["elast_producto"]
        .fillna(out["elast_atc3"])
        .fillna(out["elast_atc1"])
        .fillna(e_global)
    )
    out["nivel_estimacion"] = np.select(
        [out["elast_producto"].notna(), out["elast_atc3"].notna(), out["elast_atc1"].notna()],
        ["Producto", "ATC3", "ATC1"],
        default="Global",
    )
    # Acotar a un rango económicamente sensato: una elasticidad de -12 es
    # ruido de estimación, no un hallazgo.
    out["elasticidad"] = out["elasticidad"].clip(-4.0, -0.20)
    return out


# ==========================================================================
# 2. Estado de stock y estacionalidad por producto-filial
# ==========================================================================
def estado_stock(stock: pd.DataFrame, dep: pd.DataFrame) -> pd.DataFrame:
    s = stock.merge(dep[["id_deposito", "id_filial"]], on="id_deposito", how="left")
    ultimo = s["fecha_mes"].max()
    s = s[s["fecha_mes"] == ultimo]
    return (
        s.groupby(["id_filial", "id_producto"], as_index=False)
        .agg(
            stock_unidades=("stock_unidades", "sum"),
            valor_stock_usd=("valor_stock_usd", "sum"),
            unidades_por_vencer=("unidades_por_vencer_180d", "sum"),
            dias_cobertura=("dias_cobertura", "mean"),
            dias_a_vencer=("dias_a_vencer_promedio", "mean"),
        )
    )


# ==========================================================================
# 3. Función objetivo: margen esperado neto de riesgo
# ==========================================================================
def grilla_dentro_de_soporte(descuentos_historicos: pd.Series) -> np.ndarray:
    """
    Recorta la grilla al rango donde el modelo REALMENTE vio datos.

    Un modelo de árboles extrapola pésimo: fuera del soporte devuelve el valor
    de la hoja del borde, que acá se traduce en "probabilidad de aceptación
    98%" para descuentos que nunca se ofrecieron. El optimizador entonces se
    va siempre al extremo de la grilla — y esa recomendación no es un hallazgo,
    es un artefacto.

    Regla: no proponer descuentos por encima del percentil 95 histórico.
    Si el negocio quiere explorar más allá, se hace con un test controlado,
    no con una extrapolación del modelo.
    """
    tope = float(np.percentile(descuentos_historicos, 95))
    tope = float(np.floor(tope * 50) / 50)          # redondeo a múltiplo de 0.02
    return GRILLA_DESCUENTO[GRILLA_DESCUENTO <= tope]


def evaluar_grilla(cand: pd.DataFrame, modelo_of: dict, grilla: np.ndarray) -> pd.DataFrame:
    """
    Para cada combinación segmento x producto, evalúa TODA la grilla de
    descuentos y devuelve el óptimo.

        demanda(d)   = q_base · (1-d)^elasticidad          (curva de demanda)
        p_acept(d)   = modelo calibrado del paso 4          (contrafáctico)
        margen(d)    = p_acept · demanda · (precio(1-d) - costo)
        objetivo(d)  = margen(d) · (1 - riesgo_devolución) + valor_liberación_stock

    El término de riesgo no es cosmético: una oferta agresiva sobre un lote
    corto genera venta hoy y devolución en 60 días. Sin ese término, el
    optimizador recomienda exactamente las ofertas que después vuelven.
    """
    modelo, feats, cats = modelo_of["modelo"], modelo_of["features"], modelo_of["cat"]

    marcos = []
    for d in grilla:
        m = cand.copy()
        m["descuento_pct"] = d
        m["precio_neto"] = m["precio_lista_usd"] * (1 - d)
        # Curva de demanda: q sube cuando el precio baja, según la elasticidad
        # Tope de demanda: la curva de elasticidad es local, no global.
        # Extrapolarla sin límite hace creer que un 30% de descuento
        # quintuplica el volumen, y ningún cliente tiene esa capacidad de
        # absorción. Se acota a 3x la demanda base.
        m["demanda_esperada"] = np.minimum(
            m["q_base"] * (1 - d) ** m["elasticidad"], 3.0 * m["q_base"]
        )
        m["unidades_ofertadas"] = m["demanda_esperada"].round().clip(1)
        m["valor_oferta_usd"] = m["unidades_ofertadas"] * m["precio_lista_usd"]
        m["descuento_usd"] = m["valor_oferta_usd"] * d
        m["descuento_vs_medio_tipo"] = d / 0.115   # descuento medio histórico
        marcos.append(m)

    g = pd.concat(marcos, ignore_index=True)

    X = g[feats].copy()
    for c in cats:
        X[c] = X[c].astype("category")
    g["prob_aceptacion"] = modelo.predict_proba(X)[:, 1]

    g["margen_unitario"] = g["precio_neto"] - g["costo_std_usd"]
    g["margen_pct"] = g["margen_unitario"] / g["precio_neto"]
    g["margen_esperado_usd"] = (
        g["prob_aceptacion"] * g["demanda_esperada"] * g["margen_unitario"]
    )

    # --- penalización por riesgo de devolución ---
    # Multiplicativa sobre el riesgo base del segmento-producto: los agravantes
    # ESCALAN el riesgo propio de esa combinación, no suman puntos porcentuales
    # sueltos. Un producto que devuelve 3% no pasa a devolver 60% porque el
    # lote esté corto; pasa a devolver ~6%.
    g["riesgo_devolucion"] = np.clip(
        g["riesgo_dev_base"]
        * (
            1.0
            + 1.20 * d_exceso(g["dias_cobertura"])                        # sobrestock del cliente
            + 0.90 * (g["dias_a_vencer"] < cfg.VIDA_UTIL_ALERTA)          # lote corto
            + 1.50 * g["descuento_pct"]                                    # carga de canal
        ),
        0.0, 0.60,
    )
    g["margen_neto_usd"] = g["margen_esperado_usd"] * (1 - g["riesgo_devolucion"])

    # --- valor de liberar stock crítico ---
    # Vender un lote que iba a vencer NO es solo margen: es evitar una pérdida
    # cierta. Se valoriza al costo de las unidades que se rescatan.
    g["unidades_rescatadas"] = np.minimum(
        g["prob_aceptacion"] * g["demanda_esperada"], g["unidades_por_vencer"]
    )
    g["valor_rescate_usd"] = g["unidades_rescatadas"] * g["costo_std_usd"]

    g["objetivo"] = g["margen_neto_usd"] + g["valor_rescate_usd"]

    # RESTRICCIÓN DE MARGEN: los descuentos que perforan el piso salen de la
    # grilla. No se penalizan — se descartan. Una restricción dura se explica
    # en una línea al comercial; una penalización blanda hay que defenderla.
    factible = g["margen_pct"] >= MARGEN_MINIMO_PCT
    g_factible = g[factible]

    idx = g_factible.groupby(
        ["id_filial", "canal", "segmento", "id_producto"], observed=True
    )["objetivo"].idxmax()
    optimo = g.loc[idx].copy()

    # CONTRAFÁCTICO DE REFERENCIA — "no hacer nada".
    # Ojo: NO es "una oferta al 0%". Es que el cliente siga comprando su
    # volumen habitual a precio de lista, sin campaña. Evaluar el d=0 con el
    # modelo de aceptación daría casi cero (nadie "acepta" una oferta sin
    # descuento) y sobreestimaría la ganancia de toda campaña.
    base_cols = ["id_filial", "canal", "segmento", "id_producto"]
    sin_oferta = (
        cand.assign(
            margen_unitario_lista=cand["precio_lista_usd"] - cand["costo_std_usd"],
            objetivo_sin_oferta=lambda x: (
                x["q_base"] * (x["precio_lista_usd"] - x["costo_std_usd"])
                * (1 - x["riesgo_dev_base"])
            ),
        )[base_cols + ["objetivo_sin_oferta"]]
    )
    optimo = optimo.merge(sin_oferta, on=base_cols, how="left")
    optimo["ganancia_vs_sin_oferta_usd"] = (
        optimo["objetivo"] - optimo["objetivo_sin_oferta"]
    )

    # Marca honesta: si el óptimo cae en el borde de la grilla, el verdadero
    # óptimo económico probablemente esté MÁS ALLÁ del rango históricamente
    # probado. El motor no lo extrapola — lo declara y propone un test.
    optimo["en_borde_de_soporte"] = (
        optimo["descuento_pct"] >= grilla.max() - 1e-9
    ).astype(int)
    return optimo


def d_exceso(dias_cobertura: pd.Series) -> pd.Series:
    """Exceso de cobertura normalizado: 0 si está en rango, sube si hay sobrestock."""
    return ((dias_cobertura - cfg.DOH_MAX) / cfg.DOH_MAX).clip(lower=0, upper=1.5)


# ==========================================================================
# 4. Justificativo explicable
# ==========================================================================
def redactar_justificativo(r: pd.Series) -> str:
    partes = []

    if r["indice_estacional"] >= 1.20:
        partes.append(
            f"entra en temporada alta de {cfg.ATC1[r['atc1']].lower()} "
            f"(índice {r['indice_estacional']:.2f} en {r['mes_nombre']})"
        )
    elif r["indice_estacional"] <= 0.90:
        partes.append(
            f"está fuera de temporada (índice {r['indice_estacional']:.2f}), "
            f"por eso el descuento compensa la menor demanda natural"
        )

    if r["dias_cobertura"] > cfg.DOH_MAX:
        partes.append(
            f"hay sobrestock: {r['dias_cobertura']:.0f} días de cobertura "
            f"contra un máximo deseado de {cfg.DOH_MAX}"
        )
    elif r["dias_cobertura"] < cfg.DOH_MIN:
        partes.append(
            f"ATENCIÓN: la cobertura es de solo {r['dias_cobertura']:.0f} días — "
            f"ofertar acá puede provocar quiebre de stock"
        )

    if r["unidades_por_vencer"] > 0:
        partes.append(
            f"{r['unidades_por_vencer']:,.0f} unidades vencen en menos de "
            f"{cfg.VIDA_UTIL_ALERTA} días (USD {r['valor_rescate_usd']:,.0f} rescatables)"
        )

    if r["aporte_margen_pct"] >= 0.02:
        partes.append(
            f"el SKU aporta el {r['aporte_margen_pct']:.1%} del margen de la filial "
            f"(está entre los que mueven la aguja)"
        )

    partes.append(
        f"elasticidad estimada {r['elasticidad']:.2f} (nivel {r['nivel_estimacion']}), "
        f"con margen unitario de USD {r['margen_unitario']:,.2f} "
        f"({100 * r['margen_unitario'] / r['precio_neto']:.0f}% sobre precio neto)"
    )
    partes.append(f"probabilidad de aceptación estimada {r['prob_aceptacion']:.0%}")

    if r["riesgo_devolucion"] > 0.20:
        partes.append(
            f"riesgo de devolución ALTO ({r['riesgo_devolucion']:.0%}): "
            f"condicionar la oferta a que el cliente no supere su cobertura objetivo"
        )
    else:
        partes.append(f"riesgo de devolución controlado ({r['riesgo_devolucion']:.0%})")

    cierre = (
        f"El {r['descuento_pct']:.0%} maximiza el margen esperado neto: "
        f"USD {r['objetivo']:,.0f} contra USD {r['objetivo_sin_oferta']:,.0f} sin oferta "
        f"(+USD {r['ganancia_vs_sin_oferta_usd']:,.0f})."
    )
    if r["en_borde_de_soporte"]:
        cierre += (
            " NOTA: el óptimo cae en el borde del rango de descuentos con "
            "evidencia histórica. El modelo NO extrapola más allá — si se quiere "
            "explorar un descuento mayor, corresponde un test controlado sobre "
            "un subconjunto de clientes antes de generalizar."
        )
    return "; ".join(partes).capitalize() + ". " + cierre


# ==========================================================================
def main() -> None:
    print("PASO 5 · Motor de IA — precio y producto óptimos por segmento")

    sellin = pd.read_parquet(cfg.STAGE / "sellin.parquet")
    prod = pd.read_parquet(cfg.STAGE / "dim_producto.parquet")
    cli = pd.read_parquet(cfg.STAGE / "dim_cliente.parquet")
    fil = pd.read_parquet(cfg.RAW / "dim_filial.parquet")
    stock = pd.read_parquet(cfg.RAW / "stock.parquet")
    dep = pd.read_parquet(cfg.RAW / "dim_deposito.parquet")
    modelo_of = joblib.load(cfg.ML / "modelo_ofertas.joblib")
    scoring_dev = pd.read_parquet(cfg.ML / "scoring_devoluciones.parquet")

    # ---- 1. elasticidades ----
    print("  · estimando elasticidades precio (log-log con efectos fijos de mes)…")
    elast = estimar_elasticidades(sellin, prod)
    print(f"    {(elast['nivel_estimacion'] == 'Producto').sum():>3} SKU con elasticidad propia")
    print(f"    {(elast['nivel_estimacion'] == 'ATC3').sum():>3} heredan de su ATC3")
    print(f"    {(elast['nivel_estimacion'] != 'Producto').sum():>3} usan un nivel superior "
          f"por datos insuficientes")

    # Validación contra la elasticidad real del simulador (solo auditoría)
    real = pd.read_parquet(cfg.RAW / "dim_producto.parquet")[["id_producto", "elasticidad_real"]]
    aud = elast.merge(real, on="id_producto")
    corr = aud[["elasticidad", "elasticidad_real"]].corr().iloc[0, 1]
    print(f"    correlación con la elasticidad real del simulador: {corr:.3f}")

    # ---- 2. base de candidatos: segmento x producto ----
    print("  · armando candidatos segmento × producto…")
    mes_obj = pd.Period(MES_OBJETIVO, "M")
    mes_nro = mes_obj.month
    meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    # Demanda base del segmento: promedio mensual de los últimos 6 meses
    ult6 = sellin[sellin["fecha"] >= sellin["fecha"].max() - pd.Timedelta(days=180)]
    base = (
        ult6.merge(cli[["id_cliente", "canal", "segmento"]], on="id_cliente", how="left")
        .groupby(["id_filial", "canal", "segmento", "id_producto"], as_index=False)
        .agg(unidades=("unidades", "sum"), clientes=("id_cliente", "nunique"))
    )
    base["q_base"] = (base["unidades"] / 6).clip(lower=1)
    base = base[base["clientes"] >= 3]   # sin masa crítica no hay segmento

    # APORTE DEL PRODUCTO: participación del SKU en el margen total de su
    # filial. Es lo que separa "un producto rentable" de "un producto que
    # mueve la aguja". Un SKU con 80% de margen que aporta el 0,1% del margen
    # de la filial no merece una campaña.
    margen_sku = (
        ult6.merge(prod[["id_producto", "costo_std_usd"]], on="id_producto", how="left")
        .assign(margen=lambda x: x["importe_usd"] - x["costo_std_usd"] * x["unidades"])
        .groupby(["id_filial", "id_producto"], as_index=False)["margen"].sum()
    )
    margen_sku["aporte_margen_pct"] = margen_sku["margen"] / margen_sku.groupby(
        "id_filial"
    )["margen"].transform("sum")
    margen_sku = margen_sku.drop(columns="margen")

    riesgo = (
        scoring_dev.groupby(["id_filial", "id_producto"], as_index=False)["prob_devolucion"]
        .mean().rename(columns={"prob_devolucion": "riesgo_dev_base"})
    )

    cand = (
        base.merge(prod[["id_producto", "sku", "marca", "atc1", "tipo_venta", "ciclo_vida",
                         "cadena_frio", "precio_lista_usd", "costo_std_usd",
                         "margen_std_pct"]], on="id_producto", how="left")
        .merge(elast[["id_producto", "elasticidad", "nivel_estimacion"]], on="id_producto", how="left")
        .merge(estado_stock(stock, dep), on=["id_filial", "id_producto"], how="left")
        .merge(fil[["id_filial", "cod_filial", "pais", "region"]], on="id_filial", how="left")
        .merge(riesgo, on=["id_filial", "id_producto"], how="left")
        .merge(margen_sku, on=["id_filial", "id_producto"], how="left")
    )
    cand = cand.fillna({
        "stock_unidades": 0, "unidades_por_vencer": 0,
        "dias_cobertura": cfg.DOH_MIN, "dias_a_vencer": 720,
        "riesgo_dev_base": scoring_dev["prob_devolucion"].mean(),
        "aporte_margen_pct": 0.0,
        "valor_stock_usd": 0,
    })
    cand["cadena_frio"] = cand["cadena_frio"].astype(int)
    cand["indice_estacional"] = [cfg.ESTACIONALIDAD[a][mes_nro - 1] for a in cand["atc1"]]
    cand["mes_nombre"] = meses_es[mes_nro - 1]

    # Features que el modelo de aceptación espera (constantes del escenario)
    cand["tipo_oferta"] = "DTO"
    cand["linea_promocion"] = "General"
    cand["mes_nro"] = mes_nro
    cand["en_temporada"] = (cand["indice_estacional"] > 1.10).astype(int)
    cand["cierre_trimestre"] = int(mes_nro in (3, 6, 9, 12))
    cand["antiguedad_meses"] = 60
    cand["cobertura_cliente_dias"] = cand["dias_cobertura"]
    cand["compras_previas_cliente_producto"] = cand["unidades"]
    for c, v in [("tasa_acept_cliente_hist", 0.55), ("tasa_acept_producto_hist", 0.55),
                 ("tasa_acept_rep_hist", 0.55), ("tasa_acept_tipo_hist", 0.55),
                 ("tasa_acept_cliente_reciente", 0.55)]:
        cand[c] = v

    print(f"    {len(cand):,} combinaciones segmento × producto "
          f"a evaluar")  # noqa

    # ---- 3. optimización ----
    print("  · optimizando descuento sobre la grilla (contrafácticos del modelo)…")
    grilla = grilla_dentro_de_soporte(sellin["descuento_pct"])
    print(f"    grilla acotada al soporte del modelo: "
          f"{grilla.min():.0%} a {grilla.max():.0%} ({len(grilla)} niveles)")
    opt = evaluar_grilla(cand, modelo_of, grilla)

    # ---- 4. selección y justificativo ----
    opt = opt[opt["ganancia_vs_sin_oferta_usd"] > 0].copy()
    opt["rank_segmento"] = opt.groupby(
        ["id_filial", "canal", "segmento"], observed=True
    )["objetivo"].rank(ascending=False, method="first")
    top = opt[opt["rank_segmento"] <= 5].sort_values(
        ["cod_filial", "canal", "segmento", "rank_segmento"]
    ).copy()

    print("  · redactando justificativos…")
    top["justificativo"] = top.apply(redactar_justificativo, axis=1)
    top["mes_objetivo"] = MES_OBJETIVO

    cols = [
        "mes_objetivo", "cod_filial", "pais", "canal", "segmento", "rank_segmento",
        "sku", "marca", "atc1", "tipo_venta", "ciclo_vida",
        "precio_lista_usd", "descuento_pct", "precio_neto", "margen_unitario",
        "elasticidad", "nivel_estimacion", "indice_estacional", "aporte_margen_pct",
        "dias_cobertura", "unidades_por_vencer", "demanda_esperada",
        "prob_aceptacion", "riesgo_devolucion",
        "margen_esperado_usd", "valor_rescate_usd", "objetivo",
        "objetivo_sin_oferta", "ganancia_vs_sin_oferta_usd", "en_borde_de_soporte",
        "justificativo",
        "id_filial", "id_producto",
    ]
    salida = top[cols].round(
        {"precio_lista_usd": 2, "precio_neto": 2, "margen_unitario": 2,
         "elasticidad": 3, "indice_estacional": 3, "dias_cobertura": 1,
         "aporte_margen_pct": 5,
         "demanda_esperada": 0, "prob_aceptacion": 4, "riesgo_devolucion": 4,
         "margen_esperado_usd": 2, "valor_rescate_usd": 2, "objetivo": 2,
         "objetivo_sin_oferta": 2, "ganancia_vs_sin_oferta_usd": 2}
    )

    salida.to_csv(cfg.OUT / "recomendaciones_ofertas.csv", index=False, encoding="utf-8-sig")
    salida.to_parquet(cfg.STAR / "fact_recomendaciones.parquet", index=False)
    elast.to_csv(cfg.ML / "elasticidades.csv", index=False)

    resumen = {
        "mes_objetivo": MES_OBJETIVO,
        "segmentos_cubiertos": int(
            top.groupby(["id_filial", "canal", "segmento"], observed=True).ngroups
        ),
        "recomendaciones": int(len(salida)),
        "descuento_medio_recomendado": round(float(salida["descuento_pct"].mean()), 4),
        "ganancia_total_estimada_usd": round(float(salida["ganancia_vs_sin_oferta_usd"].sum()), 2),
        "valor_stock_rescatado_usd": round(float(salida["valor_rescate_usd"].sum()), 2),
        "recomendaciones_en_borde_de_soporte": int(salida["en_borde_de_soporte"].sum()),
        "grilla_descuento_evaluada": [float(grilla.min()), float(grilla.max())],
        "correlacion_elasticidad_estimada_vs_real": round(float(corr), 4),
    }
    (cfg.OUT / "recomendaciones_resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  {resumen['recomendaciones']} recomendaciones sobre "
          f"{resumen['segmentos_cubiertos']} segmentos")
    print(f"  descuento medio recomendado: {resumen['descuento_medio_recomendado']:.1%}")
    print(f"  ganancia estimada vs no hacer nada: "
          f"USD {resumen['ganancia_total_estimada_usd']:,.0f}")
    print(f"  stock crítico rescatado: USD {resumen['valor_stock_rescatado_usd']:,.0f}")

    print("\n  Ejemplo de recomendación:")
    ej = salida.iloc[0]
    print(f"    {ej['cod_filial']} · {ej['canal']} · segmento {ej['segmento']}")
    print(f"    {ej['sku']} {ej['marca']} → descuento {ej['descuento_pct']:.0%}")
    print(f"    {ej['justificativo']}")
    print(f"\n  OK → {cfg.OUT / 'recomendaciones_ofertas.csv'}")


if __name__ == "__main__":
    main()
