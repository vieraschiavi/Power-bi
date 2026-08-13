# © 2026 Martín Viera. Todos los derechos reservados.

"""
PASO 4 — Modelo predictivo de OFERTAS COMERCIALES.

  (A) CLASIFICACIÓN: "¿este cliente va a aceptar esta oferta?"
      Métrica: precision / recall / accuracy sobre holdout temporal.
      Uso: priorizar la cartera de campaña. Un representante no puede llamar a
      todos: el modelo le ordena la lista.

  (B) PROYECCIÓN mensual: unidades aceptadas e inversión comercial por filial.
      Métrica: WMAPE sobre holdout.
      Uso: presupuestar el costo de la política comercial del mes siguiente.

Diferencia importante respecto de devoluciones: acá el evento NO es raro
(~53% de aceptación en campañas dirigidas), así que accuracy sí es una métrica
informativa y no hace falta rebalancear.

Salidas:
  data/ml/ofertas_metricas.json
  data/ml/ofertas_importancia.csv
  data/ml/scoring_ofertas.parquet
  data/ml/forecast_ofertas.parquet

Uso:  python src/04_ml_ofertas.py
"""
from __future__ import annotations

import json

import joblib
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

CAT = ["tipo_oferta", "canal", "segmento", "region", "atc1", "tipo_venta",
       "ciclo_vida", "linea_promocion"]
NUM = [
    "descuento_pct", "unidades_ofertadas", "cobertura_cliente_dias",
    "precio_lista_usd", "margen_std_pct", "valor_oferta_usd", "descuento_usd",
    "antiguedad_meses", "mes_nro", "indice_estacional", "en_temporada",
    "cierre_trimestre", "cadena_frio",
    "tasa_acept_cliente_hist", "tasa_acept_producto_hist", "tasa_acept_rep_hist",
    "tasa_acept_tipo_hist", "tasa_acept_cliente_reciente",
    "descuento_vs_medio_tipo", "compras_previas_cliente_producto",
]


# ==========================================================================
def construir_features() -> pd.DataFrame:
    of = pd.read_parquet(cfg.RAW / "ofertas.parquet")
    prod = pd.read_parquet(cfg.STAGE / "dim_producto.parquet")
    cli = pd.read_parquet(cfg.STAGE / "dim_cliente.parquet")
    fil = pd.read_parquet(cfg.RAW / "dim_filial.parquet")
    rep = pd.read_parquet(cfg.RAW / "dim_representante.parquet")
    sellin = pd.read_parquet(cfg.STAGE / "sellin.parquet")

    df = (
        of.rename(columns={"fecha_oferta": "fecha"})
        .merge(cli[["id_cliente", "id_filial", "canal", "segmento",
                    "antiguedad_meses", "id_representante"]], on="id_cliente", how="left")
        .merge(prod[["id_producto", "atc1", "tipo_venta", "ciclo_vida", "cadena_frio",
                     "precio_lista_usd", "margen_std_pct"]], on="id_producto", how="left")
        .merge(fil[["id_filial", "region", "cod_filial", "pais"]], on="id_filial", how="left")
        .merge(rep[["id_representante", "linea_promocion"]], on="id_representante", how="left")
    )

    df["fecha"] = pd.to_datetime(df["fecha"])
    df["anio_mes"] = df["fecha"].dt.to_period("M").astype(str)
    df["mes_nro"] = df["fecha"].dt.month
    df["indice_estacional"] = [
        cfg.ESTACIONALIDAD[a][m - 1] for a, m in zip(df["atc1"], df["mes_nro"])
    ]
    df["en_temporada"] = (df["indice_estacional"] > 1.10).astype(int)
    df["cierre_trimestre"] = df["mes_nro"].isin([3, 6, 9, 12]).astype(int)
    df["cadena_frio"] = df["cadena_frio"].astype(int)

    # Tamaño económico de la oferta: no es lo mismo un 12% sobre un genérico
    # de USD 2 que sobre un oncológico de USD 400.
    df["valor_oferta_usd"] = df["unidades_ofertadas"] * df["precio_lista_usd"]
    df["descuento_usd"] = df["valor_oferta_usd"] * df["descuento_pct"]

    # ¿Este descuento es agresivo respecto de lo habitual para ese tipo de oferta?
    medio_tipo = df.groupby("tipo_oferta", observed=True)["descuento_pct"].transform("mean")
    df["descuento_vs_medio_tipo"] = df["descuento_pct"] / medio_tipo

    # Relación previa cliente-producto (¿ya lo compra?) — se calcula del sell-in
    compras = (
        sellin.assign(anio_mes=sellin["fecha"].dt.to_period("M").astype(str))
        .groupby(["id_cliente", "id_producto", "anio_mes"], as_index=False)["unidades"].sum()
        .sort_values("anio_mes")
    )
    compras["acum"] = compras.groupby(["id_cliente", "id_producto"])["unidades"].cumsum()
    compras["prev"] = compras.groupby(["id_cliente", "id_producto"])["acum"].shift(1).fillna(0)
    df = df.merge(
        compras[["id_cliente", "id_producto", "anio_mes", "prev"]],
        on=["id_cliente", "id_producto", "anio_mes"], how="left",
    ).rename(columns={"prev": "compras_previas_cliente_producto"})
    df["compras_previas_cliente_producto"] = df["compras_previas_cliente_producto"].fillna(0)

    # ---- históricos point-in-time ----
    df = df.sort_values("fecha").reset_index(drop=True)
    df["tasa_acept_cliente_hist"] = mlu.tasa_historica(df, "id_cliente", "aceptada", alpha=6)
    df["tasa_acept_producto_hist"] = mlu.tasa_historica(df, "id_producto", "aceptada", alpha=30)
    df["tasa_acept_rep_hist"] = mlu.tasa_historica(df, "id_representante", "aceptada", alpha=30)
    df["tasa_acept_tipo_hist"] = mlu.tasa_historica(df, "tipo_oferta", "aceptada", alpha=50)
    df["tasa_acept_cliente_reciente"] = mlu.tasa_reciente(
        df, "id_cliente", "aceptada", ventana=4, alpha=5
    )
    return df


# ==========================================================================
# (A) Clasificación de aceptación
# ==========================================================================
def entrenar_clasificador(df: pd.DataFrame):
    tr, va, ho = mlu.split_temporal(df, "fecha", cfg.CORTE_TRAIN, cfg.CORTE_VALID)
    print(f"  train {len(tr):>7,} | valid {len(va):>7,} | holdout {len(ho):>7,}")

    feats = NUM + CAT

    def X(d):
        x = d[feats].copy()
        for c in CAT:
            x[c] = x[c].astype("category")
        return x

    base = HistGradientBoostingClassifier(
        max_iter=500,
        learning_rate=0.05,
        max_leaf_nodes=31,
        min_samples_leaf=30,
        l2_regularization=0.8,
        early_stopping=True,
        validation_fraction=0.12,
        categorical_features="from_dtype",
        random_state=cfg.SEED,
    )
    base.fit(X(tr), tr["aceptada"])

    # Calibración isotónica sobre VALIDACIÓN. Importa porque la probabilidad
    # no se usa solo para ordenar: entra en el cálculo de inversión esperada
    # del motor de precios, y ahí una probabilidad mal calibrada se traduce
    # en plata mal presupuestada.
    cal = CalibratedClassifierCV(FrozenEstimator(base), method="isotonic")
    cal.fit(X(va), va["aceptada"])

    p_va = cal.predict_proba(X(va))[:, 1]
    p_ho = cal.predict_proba(X(ho))[:, 1]
    p_ho_sin_cal = base.predict_proba(X(ho))[:, 1]

    u = mlu.elegir_umbral(va["aceptada"], p_va, "f1")

    # Techo teórico del problema: AUC que lograría alguien que conociera
    # la probabilidad real del proceso generador. Sirve para saber si
    # falta modelo o si el resto es ruido irreducible.
    auc_oraculo = float(roc_auc_score(ho["aceptada"], ho["_p_real"])) if "_p_real" in ho else None

    res = {
        "validacion": mlu.metricas_clasificacion(va["aceptada"], p_va, u),
        "holdout": mlu.metricas_clasificacion(ho["aceptada"], p_ho, u),
        # Dos puntos de operación distintos, para dos usos distintos:
        #  · umbral F1  -> lista de llamados del representante (prioriza cobertura)
        #  · umbral 0.5 -> conteo esperado de aceptaciones (prioriza exactitud)
        "holdout_umbral_050": mlu.metricas_clasificacion(ho["aceptada"], p_ho, 0.5),
        "holdout_sin_calibrar": mlu.metricas_clasificacion(ho["aceptada"], p_ho_sin_cal, 0.5),
        "auc_oraculo_holdout": round(auc_oraculo, 4) if auc_oraculo else None,
    }

    muestra = ho.sample(min(15000, len(ho)), random_state=1)
    imp = mlu.importancia_permutacion(base, X(muestra), muestra["aceptada"])

    p_all = cal.predict_proba(X(df))[:, 1]
    scoring = df[["id_oferta", "fecha", "id_cliente", "id_producto", "id_filial",
                  "id_representante", "tipo_oferta", "descuento_pct",
                  "unidades_ofertadas", "valor_oferta_usd", "descuento_usd",
                  "aceptada"]].copy()
    scoring["prob_aceptacion"] = np.round(p_all, 5)
    scoring["valor_esperado_usd"] = np.round(
        p_all * scoring["valor_oferta_usd"] * (1 - scoring["descuento_pct"]), 2
    )
    scoring["prioridad"] = pd.qcut(
        scoring["prob_aceptacion"].rank(method="first"), 4,
        labels=["4 - Baja", "3 - Media", "2 - Alta", "1 - Prioritaria"],
    ).astype(str)
    return cal, res, imp, scoring, u


# ==========================================================================
# (B) Proyección mensual de la política comercial
# ==========================================================================
def forecast_mensual(df: pd.DataFrame):
    """
    Serie: unidades aceptadas e inversión comercial (descuento otorgado) por
    filial y mes. Es lo que Excelencia Comercial necesita para presupuestar.
    """
    m = (
        df.assign(fecha_mes=df["fecha"].values.astype("datetime64[M]"))
        .groupby(["fecha_mes", "id_filial", "cod_filial"], as_index=False)
        .agg(
            ofertas=("aceptada", "size"),
            aceptadas=("aceptada", "sum"),
            unidades_ofertadas=("unidades_ofertadas", "sum"),
            valor_ofertado=("valor_oferta_usd", "sum"),
            descuento_medio=("descuento_pct", "mean"),
        )
    )
    ac = (
        df[df["aceptada"] == 1]
        .assign(fecha_mes=lambda d: d["fecha"].values.astype("datetime64[M]"))
        .groupby(["fecha_mes", "id_filial"], as_index=False)
        .agg(unidades_aceptadas=("unidades_ofertadas", "sum"),
             inversion_usd=("descuento_usd", "sum"))
    )
    m = m.merge(ac, on=["fecha_mes", "id_filial"], how="left").fillna(
        {"unidades_aceptadas": 0, "inversion_usd": 0}
    )
    m = m.sort_values(["id_filial", "fecha_mes"]).reset_index(drop=True)

    # Target: inversión comercial del mes (USD de descuento efectivamente otorgado)
    m["y"] = np.log1p(m["inversion_usd"])
    gf = m.groupby("id_filial", observed=True)
    for l in (1, 2, 3):
        m[f"lag{l}"] = gf["y"].shift(l)
    m["media3"] = gf["y"].shift(1).rolling(3).mean().reset_index(level=0, drop=True)
    m["tasa_acept_lag1"] = gf.apply(
        lambda g: (g["aceptadas"] / g["ofertas"]).shift(1), include_groups=False
    ).reset_index(level=0, drop=True)
    m["valor_ofertado_log"] = np.log1p(m["valor_ofertado"])  # el plan del mes SÍ se conoce
    m["mes_nro"] = m["fecha_mes"].dt.month
    m["cierre_trim"] = m["mes_nro"].isin([3, 6, 9, 12]).astype(int)
    m["sin"] = np.sin(2 * np.pi * m["mes_nro"] / 12)
    m["cos"] = np.cos(2 * np.pi * m["mes_nro"] / 12)

    feats = ["lag1", "lag2", "lag3", "media3", "tasa_acept_lag1",
             "valor_ofertado_log", "cierre_trim", "sin", "cos"]
    d = m.dropna(subset=feats).copy()
    tr = d[d["fecha_mes"] <= cfg.CORTE_VALID]
    ho = d[d["fecha_mes"] > cfg.CORTE_VALID]

    modelo = make_pipeline(
        StandardScaler(),
        RidgeCV(alphas=np.logspace(-2, 3, 30), cv=TimeSeriesSplit(n_splits=4)),
    ).fit(tr[feats], tr["y"])

    d["inversion_proyectada_usd"] = np.expm1(modelo.predict(d[feats])).clip(0)
    tr, ho = d.loc[tr.index], d.loc[ho.index]

    met = {
        "holdout": mlu.metricas_forecast(ho["inversion_usd"], ho["inversion_proyectada_usd"]),
        "baseline_naive_lag1": mlu.metricas_forecast(
            ho["inversion_usd"], np.expm1(ho["lag1"])
        ),
        "train_insample": mlu.metricas_forecast(
            tr["inversion_usd"], tr["inversion_proyectada_usd"]
        ),
    }
    met["mejora_vs_baseline_pp"] = round(
        100 * (met["baseline_naive_lag1"]["wmape"] - met["holdout"]["wmape"]), 2
    )

    salida = d[["fecha_mes", "id_filial", "cod_filial", "ofertas", "aceptadas",
                "valor_ofertado", "inversion_usd", "inversion_proyectada_usd"]].copy()
    salida["tasa_aceptacion"] = salida["aceptadas"] / salida["ofertas"]
    salida["es_holdout"] = (salida["fecha_mes"] > cfg.CORTE_VALID).astype(int)
    return salida, met


# ==========================================================================
def main() -> None:
    print("PASO 4 · Modelo de ofertas comerciales")
    df = construir_features()
    print(f"  dataset: {len(df):,} ofertas | tasa de aceptación "
          f"{100 * df['aceptada'].mean():.1f}%")

    print("\n  (A) Clasificación de aceptación — walk-forward temporal")
    modelo, res, imp, scoring, umbral = entrenar_clasificador(df)
    for k, v in res.items():
        if not isinstance(v, dict):
            continue
        print(f"\n    {k}  (umbral {v['umbral']})")
        print(f"      accuracy {v['accuracy']:.3f} | precision {v['precision']:.3f} | "
              f"recall {v['recall']:.3f} | F1 {v['f1']:.3f}")
        print(f"      ROC-AUC {v['roc_auc']:.3f} | PR-AUC {v['pr_auc']:.3f} | "
              f"Brier {v['brier']:.4f}")
    print(f"\n    Calibración: Brier sin calibrar {res['holdout_sin_calibrar']['brier']:.4f} "
          f"→ calibrado {res['holdout']['brier']:.4f}")
    if res.get("auc_oraculo_holdout"):
        print(f"    Techo teórico (AUC oráculo): {res['auc_oraculo_holdout']} — el modelo "
              f"alcanza el {res['holdout']['roc_auc'] / res['auc_oraculo_holdout']:.0%}")

    print("\n    Top features:")
    for _, r in imp.head(8).iterrows():
        print(f"      {r['feature']:<34} {r['importancia']:.4f}")

    print("\n  (B) Proyección mensual de inversión comercial por filial")
    fc, met_fc = forecast_mensual(df)
    print(f"    holdout  WMAPE {met_fc['holdout']['wmape']:.3f} "
          f"(precisión {met_fc['holdout']['precision_forecast']:.1%})")
    print(f"    baseline WMAPE {met_fc['baseline_naive_lag1']['wmape']:.3f}  "
          f"→ mejora {met_fc['mejora_vs_baseline_pp']} pp")

    # El modelo calibrado se persiste porque el motor de IA de precios (paso 5)
    # lo necesita para evaluar contrafácticos: "¿qué pasaría si en vez de 12%
    # ofrezco 18%?". Sin el modelo no hay optimización, solo intuición.
    joblib.dump({"modelo": modelo, "features": NUM + CAT, "cat": CAT, "umbral": umbral},
                cfg.ML / "modelo_ofertas.joblib")

    scoring.to_parquet(cfg.ML / "scoring_ofertas.parquet", index=False)
    fc.to_parquet(cfg.ML / "forecast_ofertas.parquet", index=False)
    fc.rename(columns={"fecha_mes": "fecha"}).to_parquet(
        cfg.STAR / "fact_forecast_ofertas.parquet", index=False
    )
    imp.to_csv(cfg.ML / "ofertas_importancia.csv", index=False)
    (cfg.ML / "ofertas_metricas.json").write_text(
        json.dumps({"clasificacion": res, "umbral": umbral,
                    "forecast_mensual": met_fc}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  OK → {cfg.ML}")


if __name__ == "__main__":
    main()
