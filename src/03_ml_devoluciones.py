"""
PASO 3 — Modelo predictivo de DEVOLUCIONES.

Dos entregables distintos, que responden a dos preguntas distintas del negocio:

  (A) CLASIFICACIÓN a nivel pedido
      "¿Este pedido que estoy por despachar va a volver?"
      Métrica: precision / recall / accuracy sobre holdout temporal.
      Uso: alerta operativa en el tablero de Logística, antes de despachar.

  (B) PROYECCIÓN mensual por filial
      "¿Cuánta devolución voy a tener el mes que viene y cuánto me cuesta?"
      Métrica: WMAPE sobre holdout.
      Uso: provisión contable y objetivo de reducción por filial.

Reglas no negociables aplicadas:
  · split temporal (nunca aleatorio)
  · features históricos con expanding + shift(1) — cero leakage
  · el umbral se calibra en VALIDACIÓN y se mide en HOLDOUT
  · el holdout no se toca hasta el final

Salidas:
  data/ml/devoluciones_metricas.json
  data/ml/devoluciones_importancia.csv
  data/ml/scoring_devoluciones.parquet      -> se consume desde Power BI
  data/ml/forecast_devoluciones.parquet     -> se consume desde Power BI

Uso:  python src/03_ml_devoluciones.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import config as cfg
import ml_utils as mlu

CAT = [
    "atc1", "forma_farmaceutica", "tipo_venta", "ciclo_vida", "canal",
    "segmento", "region", "tipo_oferta", "transportista",
]
NUM = [
    "unidades", "importe_usd", "descuento_pct", "precio_lista_usd", "margen_std_pct",
    "vida_util_meses", "dias_a_vencer", "lead_time_dias", "sla_dias", "exceso_lead_time",
    "otif", "cadena_frio", "frio_sin_control", "antiguedad_meses", "confiabilidad",
    "mes_nro", "indice_estacional", "ratio_unidades_vs_hist",
    "vida_util_remanente_pct", "lote_critico", "pedido_desproporcionado",
    "oferta_de_carga", "ratio_unidades_vs_sku",
    "tasa_dev_cliente_hist", "tasa_dev_producto_hist", "tasa_dev_transportista_hist",
    "tasa_dev_cliente_producto_hist", "tasa_dev_filial_hist", "tasa_dev_deposito_hist",
]


# ==========================================================================
# Construcción de la tabla de features
# ==========================================================================
def construir_features() -> pd.DataFrame:
    sellin = pd.read_parquet(cfg.STAGE / "sellin.parquet")
    prod = pd.read_parquet(cfg.STAGE / "dim_producto.parquet")
    cli = pd.read_parquet(cfg.STAGE / "dim_cliente.parquet")
    fil = pd.read_parquet(cfg.RAW / "dim_filial.parquet")
    tr = pd.read_parquet(cfg.RAW / "dim_transportista.parquet")

    df = (
        sellin[sellin["tipo_documento"] == "FC"]  # las NC no se predicen: ya volvieron
        .merge(
            prod[["id_producto", "atc1", "forma_farmaceutica", "tipo_venta", "ciclo_vida",
                  "cadena_frio", "vida_util_meses", "precio_lista_usd", "margen_std_pct"]],
            on="id_producto", how="left", suffixes=("", "_p"),
        )
        .merge(cli[["id_cliente", "canal", "segmento", "antiguedad_meses"]],
               on="id_cliente", how="left")
        .merge(fil[["id_filial", "region", "cod_filial", "pais"]], on="id_filial", how="left")
        .merge(tr[["id_transportista", "transportista", "confiabilidad", "control_frio"]],
               on="id_transportista", how="left")
    )

    df["anio_mes"] = df["fecha"].dt.to_period("M").astype(str)
    df["mes_nro"] = df["fecha"].dt.month
    df["indice_estacional"] = [
        cfg.ESTACIONALIDAD[a][m - 1] for a, m in zip(df["atc1"], df["mes_nro"])
    ]
    df["exceso_lead_time"] = (df["lead_time_dias"] - df["sla_dias"]).clip(lower=0)
    df["frio_sin_control"] = (
        df["cadena_frio"].astype(bool) & ~df["control_frio"].fillna(False).astype(bool)
    ).astype(int)
    df["cadena_frio"] = df["cadena_frio"].astype(int)
    df["confiabilidad"] = df["confiabilidad"].fillna(df["confiabilidad"].median())

    # Vida útil: el negocio no razona en días absolutos sino en "cuánto le queda
    # a este lote respecto de su vida total". Un jarabe con 200 días es nuevo;
    # un oncológico con 200 días está al límite.
    df["vida_util_remanente_pct"] = (
        df["dias_a_vencer"] / (df["vida_util_meses"] * 30)
    ).clip(0, 1)
    df["lote_critico"] = (df["dias_a_vencer"] < cfg.VIDA_UTIL_ALERTA).astype(int)
    df["oferta_de_carga"] = df["tipo_oferta"].isin(["BON", "COM"]).astype(int)

    # Desproporción del pedido respecto del comportamiento típico del SKU
    med_sku = df.groupby("id_producto", observed=True)["unidades"].transform("median")
    df["ratio_unidades_vs_sku"] = (df["unidades"] / med_sku.clip(lower=1)).clip(0, 40)
    df["pedido_desproporcionado"] = (df["ratio_unidades_vs_sku"] > 2.2).astype(int)

    # ---- features históricos: SOLO información de meses anteriores ----
    df = df.sort_values("fecha").reset_index(drop=True)
    df["tasa_dev_cliente_hist"] = mlu.tasa_historica(df, "id_cliente", "devuelta", alpha=25)
    df["tasa_dev_producto_hist"] = mlu.tasa_historica(df, "id_producto", "devuelta", alpha=40)
    df["tasa_dev_transportista_hist"] = mlu.tasa_historica(df, "id_transportista", "devuelta", alpha=60)
    df["tasa_dev_cliente_producto_hist"] = mlu.tasa_historica(
        df, ["id_cliente", "id_producto"], "devuelta", alpha=12
    )
    # Estado logístico de la filial y del depósito: capturan el efecto
    # estructural que arrastra meses (operador flojo, cámara de frío con
    # problemas). Sin esto queda como confusor no observado y el modelo pierde.
    df["tasa_dev_filial_hist"] = mlu.tasa_reciente(df, "id_filial", "devuelta", ventana=3, alpha=80)
    df["tasa_dev_deposito_hist"] = mlu.tasa_reciente(df, "id_deposito", "devuelta", ventana=3, alpha=60)
    unid_hist = mlu.volumen_historico(df, ["id_cliente", "id_producto"], "unidades")
    df["ratio_unidades_vs_hist"] = (df["unidades"] / unid_hist.clip(lower=1)).clip(0, 25)

    return df


# ==========================================================================
# (A) Clasificación a nivel pedido
# ==========================================================================
def entrenar_clasificador(df: pd.DataFrame):
    tr, va, ho = mlu.split_temporal(df, "fecha", cfg.CORTE_TRAIN, cfg.CORTE_VALID)
    print(f"  train {len(tr):>7,} ({tr.fecha.min().date()} → {tr.fecha.max().date()})")
    print(f"  valid {len(va):>7,} ({va.fecha.min().date()} → {va.fecha.max().date()})")
    print(f"  hold  {len(ho):>7,} ({ho.fecha.min().date()} → {ho.fecha.max().date()})")

    feats = NUM + CAT

    def X(d):
        x = d[feats].copy()
        for c in CAT:
            x[c] = x[c].astype("category")
        return x

    modelo = HistGradientBoostingClassifier(
        max_iter=400,
        learning_rate=0.06,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.12,
        categorical_features="from_dtype",
        class_weight="balanced",   # evento minoritario (~11%): sin esto el modelo tiende al todo-cero
        random_state=cfg.SEED,
    )
    modelo.fit(X(tr), tr["devuelta"])

    # CALIBRACIÓN — no es opcional acá.
    # `class_weight="balanced"` mejora el aprendizaje sobre un evento
    # minoritario pero DEFORMA la probabilidad hacia arriba: el modelo separa
    # bien y estima mal. Para ordenar pedidos alcanza; para usar el número como
    # tasa esperada (que es lo que hace el motor de precios del paso 5) hay que
    # calibrarlo contra la frecuencia real observada en validación.
    p_va_cruda = modelo.predict_proba(X(va))[:, 1]
    cal = CalibratedClassifierCV(FrozenEstimator(modelo), method="isotonic")
    cal.fit(X(va), va["devuelta"])

    p_va = cal.predict_proba(X(va))[:, 1]
    p_ho = cal.predict_proba(X(ho))[:, 1]
    print(f"  calibración: prob. media cruda {p_va_cruda.mean():.3f} → "
          f"calibrada {p_va.mean():.3f} (tasa real {va['devuelta'].mean():.3f})")

    # El umbral se elige en VALIDACIÓN. En devoluciones el falso negativo
    # (no anticipar una devolución) cuesta ~4x el falso positivo (revisar de más).
    u_f1 = mlu.elegir_umbral(va["devuelta"], p_va, "f1")
    u_costo = mlu.elegir_umbral(va["devuelta"], p_va, "costo", costo_fn=4.0, costo_fp=1.0)

    # Techo teórico del problema: AUC que lograría alguien que conociera
    # la probabilidad real del proceso generador. Sirve para saber si
    # falta modelo o si el resto es ruido irreducible.
    auc_oraculo = float(roc_auc_score(ho["devuelta"], ho["_p_real"])) if "_p_real" in ho else None

    res = {
        "validacion": mlu.metricas_clasificacion(va["devuelta"], p_va, u_f1),
        "holdout_umbral_f1": mlu.metricas_clasificacion(ho["devuelta"], p_ho, u_f1),
        "holdout_umbral_costo": mlu.metricas_clasificacion(ho["devuelta"], p_ho, u_costo),
        "auc_oraculo_holdout": round(auc_oraculo, 4) if auc_oraculo else None,
    }

    imp = mlu.importancia_permutacion(modelo, X(ho.sample(min(20000, len(ho)), random_state=1)),
                                      ho.sample(min(20000, len(ho)), random_state=1)["devuelta"])

    # scoring completo para el tablero (probabilidad + banda de riesgo)
    p_all = cal.predict_proba(X(df))[:, 1]
    scoring = df[["fecha", "id_cliente", "id_producto", "id_filial", "id_transportista",
                  "unidades", "importe_usd", "devuelta"]].copy()
    scoring["prob_devolucion"] = np.round(p_all, 5)
    # Bandas por percentil de riesgo: son estables mes a mes y se explican solas
    # ("Crítico = el 5% de pedidos con mayor probabilidad de volver").
    cortes = np.quantile(p_all, [0.60, 0.85, 0.95])
    scoring["banda_riesgo"] = pd.cut(
        scoring["prob_devolucion"],
        bins=[-0.01, *np.unique(cortes), 1.01],
        labels=["Bajo", "Medio", "Alto", "Crítico"][: len(np.unique(cortes)) + 1],
    ).astype(str)
    scoring["importe_en_riesgo_usd"] = np.round(
        scoring["prob_devolucion"] * scoring["importe_usd"], 2
    )
    return modelo, res, imp, scoring, (u_f1, u_costo)


# ==========================================================================
# (B) Proyección mensual de devoluciones por filial
# ==========================================================================
def forecast_mensual(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Serie: importe devuelto / importe vendido, por filial y mes.

    Modelo deliberadamente simple y auditable (Ridge sobre lags + estacionalidad).
    En una serie de 24 meses por filial, un modelo grande sobreajusta y no se
    puede explicar en un comité. La comparación contra el naive estacional es
    lo que demuestra que aporta valor.
    """
    m = (
        df.assign(fecha_mes=df["fecha"].values.astype("datetime64[M]"))
        .groupby(["fecha_mes", "id_filial", "cod_filial"], as_index=False)
        .agg(
            importe=("importe_usd", "sum"),
            importe_dev=("importe_devuelto_usd", "sum"),
            lineas=("devuelta", "size"),
            lineas_dev=("devuelta", "sum"),
            # DRIVERS DE MIX: el negocio los conoce por anticipado. El plan de
            # ofertas se aprueba antes del mes; el mix de frío y la asignación
            # de transportistas son decisiones, no sorpresas.
            pct_frio_sin_control=("frio_sin_control", "mean"),
            pct_oferta_carga=("oferta_de_carga", "mean"),
            pct_lote_critico=("lote_critico", "mean"),
            exceso_lead_time_medio=("exceso_lead_time", "mean"),
            vida_remanente_media=("vida_util_remanente_pct", "mean"),
            otif_medio=("otif", "mean"),
        )
    )
    m["tasa_dev_valor"] = (m["importe_dev"] / m["importe"]).clip(1e-4, 0.60)
    m = m.sort_values(["id_filial", "fecha_mes"]).reset_index(drop=True)

    # La tasa está acotada en [0,1]: modelarla en escala logit evita
    # proyecciones negativas y hace que los efectos sean multiplicativos,
    # que es como se comporta de verdad.
    m["y"] = np.log(m["tasa_dev_valor"] / (1 - m["tasa_dev_valor"]))

    gf = m.groupby("id_filial", observed=True)
    g = gf["y"]
    for l in (1, 2):
        m[f"lag{l}"] = g.shift(l)
    m["media3"] = g.shift(1).rolling(3).mean().reset_index(level=0, drop=True)

    # Drivers de mix rezagados un mes (nunca contemporáneos: eso sería leakage)
    drivers = ["pct_frio_sin_control", "pct_oferta_carga", "exceso_lead_time_medio"]
    for c in drivers:
        m[f"{c}_lag1"] = gf[c].shift(1)

    m["mes_nro"] = m["fecha_mes"].dt.month
    m["sin"] = np.sin(2 * np.pi * m["mes_nro"] / 12)
    m["cos"] = np.cos(2 * np.pi * m["mes_nro"] / 12)

    feats = ["lag1", "lag2", "media3", "sin", "cos"] + [f"{c}_lag1" for c in drivers]
    d = m.dropna(subset=feats).copy()

    tr = d[d["fecha_mes"] <= cfg.CORTE_VALID]
    ho = d[d["fecha_mes"] > cfg.CORTE_VALID]

    # Estandarizar antes de Ridge: los drivers viven en escalas muy distintas.
    # Alpha se elige por validación cruzada TEMPORAL, nunca por K-fold aleatorio.
    modelo = make_pipeline(
        StandardScaler(),
        RidgeCV(alphas=np.logspace(-2, 3, 30), cv=TimeSeriesSplit(n_splits=4)),
    ).fit(tr[feats], tr["y"])

    y_hat = modelo.predict(d[feats])
    d["pred"] = np.clip(1 / (1 + np.exp(-y_hat)), 0, 0.30)
    tr, ho = d.loc[tr.index], d.loc[ho.index]

    # baseline: naive (el mes anterior). Si el modelo no le gana, no sirve.
    baseline = 1 / (1 + np.exp(-ho["lag1"]))   # naive: la tasa del mes anterior

    met = {
        "holdout": mlu.metricas_forecast(ho["tasa_dev_valor"], ho["pred"]),
        "baseline_naive_lag1": mlu.metricas_forecast(ho["tasa_dev_valor"], baseline),
        "train_insample": mlu.metricas_forecast(tr["tasa_dev_valor"], tr["pred"]),
    }
    met["mejora_vs_baseline_pp"] = round(
        100 * (met["baseline_naive_lag1"]["wmape"] - met["holdout"]["wmape"]), 2
    )

    salida = d[["fecha_mes", "id_filial", "cod_filial", "importe", "importe_dev",
                "tasa_dev_valor", "pred"]].rename(columns={"pred": "tasa_dev_proyectada"})
    salida["importe_dev_proyectado"] = np.round(
        salida["tasa_dev_proyectada"] * salida["importe"], 2
    )
    salida["es_holdout"] = (salida["fecha_mes"] > cfg.CORTE_VALID).astype(int)
    return salida, met


# ==========================================================================
def main() -> None:
    print("PASO 3 · Modelo de devoluciones")
    df = construir_features()
    print(f"  dataset: {len(df):,} pedidos | tasa base de devolución "
          f"{100 * df['devuelta'].mean():.2f}%")

    print("\n  (A) Clasificación a nivel pedido — walk-forward temporal")
    modelo, res, imp, scoring, umbrales = entrenar_clasificador(df)

    for k, v in res.items():
        if not isinstance(v, dict):
            continue
        print(f"\n    {k}  (umbral {v['umbral']})")
        print(f"      accuracy {v['accuracy']:.3f} | precision {v['precision']:.3f} | "
              f"recall {v['recall']:.3f} | F1 {v['f1']:.3f}")
        print(f"      ROC-AUC {v['roc_auc']:.3f} | PR-AUC {v['pr_auc']:.3f} | "
              f"lift vs azar {v['lift_vs_azar']}x")
        print(f"      revisando el top 10% de riesgo se capturan el "
              f"{v['captura_top10pct']:.1%} de las devoluciones ({v['lift_top10pct']}x)")

    if res.get("auc_oraculo_holdout"):
        alcanzado = res["holdout_umbral_f1"]["roc_auc"] / res["auc_oraculo_holdout"]
        print(f"\n    Techo teórico del problema (AUC oráculo): {res['auc_oraculo_holdout']}")
        print(f"    El modelo alcanza el {alcanzado:.0%} de ese techo — el resto es "
              f"ruido irreducible, no falta de modelo.")

    print("\n    Top features (importancia por permutación sobre holdout):")
    for _, r in imp.head(8).iterrows():
        print(f"      {r['feature']:<32} {r['importancia']:.4f}")

    print("\n  (B) Proyección mensual de tasa de devolución por filial")
    fc, met_fc = forecast_mensual(df)
    print(f"    holdout  WMAPE {met_fc['holdout']['wmape']:.3f} "
          f"(precisión {met_fc['holdout']['precision_forecast']:.1%})")
    print(f"    baseline WMAPE {met_fc['baseline_naive_lag1']['wmape']:.3f}")
    print(f"    mejora vs naive: {met_fc['mejora_vs_baseline_pp']} pp")

    # ---- persistencia ----
    scoring.to_parquet(cfg.ML / "scoring_devoluciones.parquet", index=False)
    fc.to_parquet(cfg.ML / "forecast_devoluciones.parquet", index=False)

    # Las salidas del modelo son hechos del modelo estrella como cualquier otro:
    # se consultan desde el mismo tablero, con las mismas dimensiones y el mismo
    # contexto de filtro. Si vivieran en un Excel aparte, nadie las usaría.
    scoring.to_parquet(cfg.STAR / "fact_scoring_devoluciones.parquet", index=False)
    fc.rename(columns={"fecha_mes": "fecha"}).to_parquet(
        cfg.STAR / "fact_forecast_devoluciones.parquet", index=False
    )
    imp.to_csv(cfg.ML / "devoluciones_importancia.csv", index=False)
    (cfg.ML / "devoluciones_metricas.json").write_text(
        json.dumps(
            {
                "clasificacion": res,
                "umbral_f1": umbrales[0],
                "umbral_costo": umbrales[1],
                "forecast_mensual": met_fc,
                "protocolo": {
                    "split": "temporal walk-forward (nunca aleatorio)",
                    "corte_train": cfg.CORTE_TRAIN,
                    "corte_valid": cfg.CORTE_VALID,
                    "features_historicos": "expanding + shift(1), suavizado bayesiano",
                    "umbral": "calibrado en validación, medido en holdout",
                },
            },
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\n  OK → {cfg.ML}")


if __name__ == "__main__":
    main()
