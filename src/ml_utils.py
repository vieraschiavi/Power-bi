"""
Utilidades compartidas de Machine Learning.

Dos cosas que definen si un modelo sirve o es humo:

  1. VALIDACIÓN TEMPORAL (walk-forward). Un random split en datos con tiempo
     mezcla el futuro con el pasado y devuelve métricas que después no se
     reproducen en producción. Acá: train / valid / holdout ordenados por fecha.

  2. FEATURES POINT-IN-TIME. Toda variable histórica se calcula con información
     estrictamente ANTERIOR al mes que se predice (expanding + shift(1)).
     Si un feature "sabe" el resultado del propio mes, el AUC sube y el modelo
     no sirve para nada. Eso es leakage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


# --------------------------------------------------------------------------
# Features históricos sin leakage
# --------------------------------------------------------------------------
def tasa_historica(
    df: pd.DataFrame,
    clave: str | list[str],
    target: str,
    col_mes: str = "anio_mes",
    prior: float | None = None,
    alpha: float = 30.0,
) -> pd.Series:
    """
    Tasa histórica del target por `clave`, usando SOLO meses anteriores.

    Suavizado bayesiano hacia la media global (`prior`) con peso `alpha`:
    una clave con 3 observaciones no puede tener tasa 100%.

    Devuelve una Serie alineada al índice de `df`.
    """
    claves = [clave] if isinstance(clave, str) else list(clave)
    prior = float(df[target].mean()) if prior is None else prior

    agg = (
        df.groupby(claves + [col_mes], observed=True)[target]
        .agg(["sum", "count"])
        .reset_index()
        .sort_values(col_mes)
    )
    # acumulado hasta el mes ANTERIOR (shift dentro de cada clave)
    agg[["sum_acum", "cnt_acum"]] = (
        agg.groupby(claves, observed=True)[["sum", "count"]].cumsum()
    )
    agg[["sum_prev", "cnt_prev"]] = (
        agg.groupby(claves, observed=True)[["sum_acum", "cnt_acum"]].shift(1)
    )
    agg["tasa_prev"] = (agg["sum_prev"].fillna(0) + prior * alpha) / (
        agg["cnt_prev"].fillna(0) + alpha
    )

    llave = df[claves + [col_mes]].merge(
        agg[claves + [col_mes, "tasa_prev"]], on=claves + [col_mes], how="left"
    )
    return pd.Series(llave["tasa_prev"].fillna(prior).to_numpy(), index=df.index)


def tasa_reciente(
    df: pd.DataFrame,
    clave: str | list[str],
    target: str,
    col_mes: str = "anio_mes",
    ventana: int = 3,
    alpha: float = 30.0,
) -> pd.Series:
    """
    Igual que `tasa_historica` pero con ventana móvil de los últimos `ventana`
    meses (siempre anteriores al mes evaluado).

    Cuándo usar cuál: si el efecto es estable (un SKU frágil es frágil siempre)
    sirve la media expandida. Si el efecto DERIVA en el tiempo —el estado
    logístico de una filial, que mejora o empeora por temporadas— la media de
    toda la historia diluye la señal y hay que mirar los últimos meses.
    """
    claves = [clave] if isinstance(clave, str) else list(clave)
    prior = float(df[target].mean())

    agg = (
        df.groupby(claves + [col_mes], observed=True)[target]
        .agg(["sum", "count"]).reset_index().sort_values(col_mes)
    )
    g = agg.groupby(claves, observed=True)[["sum", "count"]]
    roll = g.rolling(ventana, min_periods=1).sum().reset_index(drop=True)
    agg[["s_roll", "c_roll"]] = roll.to_numpy()
    agg[["s_prev", "c_prev"]] = agg.groupby(claves, observed=True)[["s_roll", "c_roll"]].shift(1)
    agg["tasa_prev"] = (agg["s_prev"].fillna(0) + prior * alpha) / (
        agg["c_prev"].fillna(0) + alpha
    )

    llave = df[claves + [col_mes]].merge(
        agg[claves + [col_mes, "tasa_prev"]], on=claves + [col_mes], how="left"
    )
    return pd.Series(llave["tasa_prev"].fillna(prior).to_numpy(), index=df.index)


def volumen_historico(
    df: pd.DataFrame, clave: str | list[str], valor: str, col_mes: str = "anio_mes"
) -> pd.Series:
    """Promedio histórico de `valor` por clave, solo con meses anteriores."""
    claves = [clave] if isinstance(clave, str) else list(clave)
    agg = (
        df.groupby(claves + [col_mes], observed=True)[valor]
        .agg(["sum", "count"]).reset_index().sort_values(col_mes)
    )
    agg[["s", "c"]] = agg.groupby(claves, observed=True)[["sum", "count"]].cumsum()
    agg[["sp", "cp"]] = agg.groupby(claves, observed=True)[["s", "c"]].shift(1)
    agg["media_prev"] = agg["sp"] / agg["cp"]
    llave = df[claves + [col_mes]].merge(
        agg[claves + [col_mes, "media_prev"]], on=claves + [col_mes], how="left"
    )
    return pd.Series(
        llave["media_prev"].fillna(df[valor].median()).to_numpy(), index=df.index
    )


# --------------------------------------------------------------------------
# Split temporal
# --------------------------------------------------------------------------
def split_temporal(df: pd.DataFrame, col_fecha: str, corte_train: str, corte_valid: str):
    """train ≤ corte_train < valid ≤ corte_valid < holdout"""
    f = pd.to_datetime(df[col_fecha])
    tr = df[f <= corte_train]
    va = df[(f > corte_train) & (f <= corte_valid)]
    ho = df[f > corte_valid]
    return tr, va, ho


# --------------------------------------------------------------------------
# Métricas de clasificación
# --------------------------------------------------------------------------
def metricas_clasificacion(y_true, y_prob, umbral: float) -> dict:
    y_pred = (np.asarray(y_prob) >= umbral).astype(int)
    y_true = np.asarray(y_true)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y_true)),
        "positivos_reales": int(y_true.sum()),
        "tasa_base": round(float(y_true.mean()), 4),
        "umbral": round(float(umbral), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "brier": round(float(brier_score_loss(y_true, y_prob)), 5),
        "lift_vs_azar": round(
            float(precision_score(y_true, y_pred, zero_division=0) / max(y_true.mean(), 1e-9)), 2
        ),
        "matriz": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        **captura_por_decil(y_true, y_prob),
    }


def captura_por_decil(y_true, y_prob) -> dict:
    """
    La métrica que de verdad entiende un comité: si reviso solo el 10% (o 20%)
    de mayor riesgo, ¿qué porcentaje de los casos reales estoy tocando?

    Es la traducción operativa del modelo: no "AUC 0.87" sino "con revisar
    1 de cada 10 pedidos, evito 4 de cada 10 devoluciones".
    """
    y_true = np.asarray(y_true)
    orden = np.argsort(-np.asarray(y_prob))
    yt = y_true[orden]
    total = max(yt.sum(), 1)
    out = {}
    for pct in (10, 20, 30):
        k = max(int(len(yt) * pct / 100), 1)
        out[f"captura_top{pct}pct"] = round(float(yt[:k].sum() / total), 4)
        out[f"lift_top{pct}pct"] = round(float((yt[:k].mean()) / max(y_true.mean(), 1e-9)), 2)
    return out


def elegir_umbral(y_true, y_prob, criterio: str = "f1", costo_fn: float = 5.0,
                  costo_fp: float = 1.0) -> float:
    """
    El umbral NO se elige en el holdout: se elige en validación.

    - 'f1'    : equilibrio genérico entre precision y recall
    - 'costo' : minimiza costo esperado. En devoluciones, un falso negativo
                (una devolución que no anticipé) cuesta bastante más que un
                falso positivo (revisar un pedido que estaba bien).
    """
    y_true = np.asarray(y_true)
    grilla = np.linspace(0.02, 0.90, 89)
    mejor, mejor_val = 0.5, -np.inf
    for u in grilla:
        y_pred = (y_prob >= u).astype(int)
        if criterio == "f1":
            val = f1_score(y_true, y_pred, zero_division=0)
        else:
            fn = ((y_true == 1) & (y_pred == 0)).sum()
            fp = ((y_true == 0) & (y_pred == 1)).sum()
            val = -(costo_fn * fn + costo_fp * fp)
        if val > mejor_val:
            mejor, mejor_val = u, val
    return float(mejor)


# --------------------------------------------------------------------------
# Métricas de forecast mensual
# --------------------------------------------------------------------------
def wmape(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    d = np.abs(y_true).sum()
    return float(np.abs(y_true - y_pred).sum() / d) if d else np.nan


def metricas_forecast(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = y_pred - y_true
    return {
        "n_periodos": int(len(y_true)),
        "wmape": round(wmape(y_true, y_pred), 4),
        "precision_forecast": round(1 - wmape(y_true, y_pred), 4),
        "mae": round(float(np.abs(err).mean()), 4),
        "rmse": round(float(np.sqrt((err ** 2).mean())), 4),
        "sesgo_pct": round(float(err.sum() / max(np.abs(y_true).sum(), 1e-9)), 4),
    }


# --------------------------------------------------------------------------
# Importancia por permutación (explicabilidad honesta, sin dependencias extra)
# --------------------------------------------------------------------------
def importancia_permutacion(modelo, X: pd.DataFrame, y, metrica=roc_auc_score,
                            n_repeticiones: int = 3, semilla: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    base = metrica(y, modelo.predict_proba(X)[:, 1])
    filas = []
    for col in X.columns:
        caidas = []
        for _ in range(n_repeticiones):
            Xp = X.copy()
            Xp[col] = rng.permutation(Xp[col].to_numpy())
            caidas.append(base - metrica(y, modelo.predict_proba(Xp)[:, 1]))
        filas.append({"feature": col, "importancia": float(np.mean(caidas)),
                      "desvio": float(np.std(caidas))})
    return (
        pd.DataFrame(filas)
        .sort_values("importancia", ascending=False)
        .reset_index(drop=True)
    )
