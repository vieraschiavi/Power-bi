# © 2026 Martín Viera. Todos los derechos reservados.

"""
PASO 1 — Simulación de los sistemas origen de Farma Demo.

Genera datos "crudos" como salen de la realidad, no como nos gustaría que salieran:
ERP de facturación, panel de auditoría (IQVIA-like), CRM de ofertas comerciales,
WMS/TMS de logística y el maestro de productos.

Los defectos NO son un accidente: están inyectados a propósito (duplicados,
nulos, códigos inconsistentes, fechas como texto, un mes faltante de una filial)
para que el paso 2 —el trabajo de Data Steward— tenga algo real que resolver.

Salida: data/raw/*.csv|parquet

Uso:  python src/01_generar_dataset.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as cfg

rng = np.random.default_rng(cfg.SEED)


# ==========================================================================
# Helpers
# ==========================================================================
def _meses(inicio: str, fin: str) -> pd.DatetimeIndex:
    return pd.date_range(inicio, fin, freq="MS")


def _logit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


MESES = _meses(cfg.FECHA_INICIO, cfg.FECHA_FIN)
N_MESES = len(MESES)


# ==========================================================================
# 1. Maestro de filiales
# ==========================================================================
def gen_filiales() -> pd.DataFrame:
    df = pd.DataFrame(
        cfg.FILIALES,
        columns=["cod_filial", "pais", "region", "moneda", "factor_tamano", "madurez"],
    )
    df["id_filial"] = np.arange(1, len(df) + 1)
    df["sla_entrega_dias"] = df["region"].map(cfg.SLA_ENTREGA)
    return df


# ==========================================================================
# 2. Maestro de productos (con jerarquía ATC — la dimensión estándar de farma)
# ==========================================================================
FORMAS = ["Comprimido", "Cápsula", "Solución inyectable", "Jarabe", "Crema", "Ampolla"]


def gen_productos() -> pd.DataFrame:
    n = cfg.N_PRODUCTOS
    atc1 = rng.choice(list(cfg.ATC1.keys()), n, p=[0.16, 0.17, 0.17, 0.08, 0.13, 0.17, 0.12])
    forma = rng.choice(FORMAS, n, p=[0.36, 0.18, 0.14, 0.12, 0.10, 0.10])

    # La cadena de frío es la variable que después explica gran parte de las devoluciones
    cadena_frio = (
        ((atc1 == "L") & (rng.random(n) < 0.90))
        | (np.isin(atc1, ["J", "N"]) & (rng.random(n) < 0.25))
        | (rng.random(n) < 0.08)
    )

    tipo_venta = np.where(
        np.isin(atc1, ["A", "M", "R"]) & (rng.random(n) < 0.45), "OTC", "Ético (Rx)"
    )

    # Precio de lista en USD; el costo estándar define el margen unitario
    base = rng.lognormal(mean=2.35, sigma=0.85, size=n)
    precio_lista = np.round(np.clip(base, 1.2, 480), 2)
    margen_pct = np.clip(rng.normal(0.52, 0.13, n), 0.15, 0.82)
    costo_std = np.round(precio_lista * (1 - margen_pct), 2)

    ciclo = rng.choice(
        ["Lanzamiento", "Crecimiento", "Madurez", "Declive"], n, p=[0.08, 0.22, 0.52, 0.18]
    )
    vida_util_meses = np.where(cadena_frio, rng.integers(12, 25, n), rng.integers(24, 49, n))

    df = pd.DataFrame(
        {
            "id_producto": np.arange(1, n + 1),
            "sku": [f"ADM-{i:04d}" for i in range(1, n + 1)],
            "marca": [f"Farma Demo {chr(65 + (i % 26))}{i:03d}" for i in range(1, n + 1)],
            "atc1": atc1,
            "atc1_desc": [cfg.ATC1[a] for a in atc1],
            "atc3": [f"{a}{rng.integers(1, 10)}{chr(65 + rng.integers(0, 8))}" for a in atc1],
            "forma_farmaceutica": forma,
            "presentacion": [
                f"x{c} {u}"
                for c, u in zip(
                    rng.choice([10, 14, 20, 28, 30, 60, 100], n),
                    rng.choice(["comp", "cáps", "ml", "amp", "g"], n),
                )
            ],
            "tipo_venta": tipo_venta,
            "cadena_frio": cadena_frio,
            "ciclo_vida": ciclo,
            "vida_util_meses": vida_util_meses,
            "precio_lista_usd": precio_lista,
            "costo_std_usd": costo_std,
            # Popularidad: distribución de Pareto — 20% de SKU explican ~70% del volumen
            "peso_demanda": rng.pareto(1.4, n) + 0.15,
            # Elasticidad precio real (latente). El motor de IA la va a *estimar*, no leerla.
            "elasticidad_real": -np.clip(rng.normal(1.5, 0.55, n), 0.35, 3.4),
        }
    )
    df["peso_demanda"] = df["peso_demanda"] / df["peso_demanda"].sum()

    # DEFECTO INYECTADO (validez): 4% de costos estándar sin cargar
    faltantes = rng.choice(df.index, size=int(0.04 * n), replace=False)
    df.loc[faltantes, "costo_std_usd"] = np.nan
    return df


# ==========================================================================
# 3. Maestro de clientes
# ==========================================================================
def gen_clientes(filiales: pd.DataFrame) -> pd.DataFrame:
    n = cfg.N_CLIENTES
    p_filial = filiales["factor_tamano"] / filiales["factor_tamano"].sum()
    id_filial = rng.choice(filiales["id_filial"], n, p=p_filial)

    canal = rng.choice(cfg.CANALES, n, p=[0.14, 0.22, 0.52, 0.12])
    seg = rng.choice(cfg.SEGMENTOS_CLIENTE, n, p=[0.16, 0.32, 0.52])

    # Potencial de compra: escala por canal y segmento
    escala_canal = pd.Series(canal).map(
        {"Distribuidor": 6.0, "Farmacia Cadena": 3.0, "Institucional": 2.4, "Farmacia Independiente": 1.0}
    ).to_numpy()
    escala_seg = pd.Series(seg).map({"A": 3.2, "B": 1.5, "C": 0.6}).to_numpy()

    df = pd.DataFrame(
        {
            "id_cliente": np.arange(1, n + 1),
            "cod_cliente": [f"CLI{i:05d}" for i in range(1, n + 1)],
            "razon_social": [f"Cliente Farma {i:04d} S.A." for i in range(1, n + 1)],
            "id_filial": id_filial,
            "canal": canal,
            "segmento": seg,
            "potencial": np.round(escala_canal * escala_seg * rng.lognormal(0, 0.35, n), 3),
            "antiguedad_meses": rng.integers(3, 180, n),
            # Propensión latente a devolver: algunos clientes gestionan peor su stock
            "propension_devolucion": np.clip(rng.beta(2.2, 12, n), 0.005, 0.35),
            # Sensibilidad al precio: NO es puro azar. Una farmacia independiente
            # negocia distinto que una cadena, y un cliente A tiene condiciones
            # base mejores y por eso reacciona menos a un descuento puntual.
            # Parte es explicable por canal/segmento y parte es idiosincrática.
            "sensibilidad_precio": np.clip(
                pd.Series(canal).map({
                    "Farmacia Independiente": 1.28, "Farmacia Cadena": 0.95,
                    "Distribuidor": 0.85, "Institucional": 1.08,
                }).to_numpy()
                * pd.Series(seg).map({"A": 0.82, "B": 1.00, "C": 1.18}).to_numpy()
                * rng.lognormal(0, 0.16, n),
                0.25, 2.2,
            ),
            "id_representante": rng.integers(1, cfg.N_REPRESENTANTES + 1, n),
        }
    )

    # DEFECTO INYECTADO (consistencia): códigos con espacios y mayúsculas mezcladas
    sucios = rng.choice(df.index, size=int(0.03 * n), replace=False)
    df.loc[sucios, "cod_cliente"] = df.loc[sucios, "cod_cliente"].str.lower().radd("  ").add(" ")
    return df


# ==========================================================================
# 4. Fuerza de ventas y depósitos
# ==========================================================================
def gen_representantes(filiales: pd.DataFrame) -> pd.DataFrame:
    n = cfg.N_REPRESENTANTES
    return pd.DataFrame(
        {
            "id_representante": np.arange(1, n + 1),
            "nombre_rep": [f"Representante {i:03d}" for i in range(1, n + 1)],
            "supervisor": [f"Supervisor {1 + (i % 9):02d}" for i in range(1, n + 1)],
            "linea_promocion": rng.choice(["Cardio-Metabólica", "Respiratoria", "Oncología", "General"], n),
            # Productividad latente: mueve la aceptación de ofertas
            "productividad": np.clip(rng.normal(1.0, 0.22, n), 0.45, 1.7),
        }
    )


def gen_depositos(filiales: pd.DataFrame) -> pd.DataFrame:
    n = cfg.N_DEPOSITOS
    idf = rng.choice(filiales["id_filial"], n)
    return pd.DataFrame(
        {
            "id_deposito": np.arange(1, n + 1),
            "nombre_deposito": [f"CD {c}-{i}" for i, c in enumerate(
                filiales.set_index("id_filial").loc[idf, "cod_filial"].to_numpy(), start=1)],
            "id_filial": idf,
            "tiene_camara_frio": rng.random(n) < 0.6,
            "capacidad_pallets": rng.integers(400, 3200, n),
        }
    )


TRANSPORTISTAS = [
    # (id, nombre, confiabilidad 0-1, control de frío)
    (1, "TransAndes Log", 0.93, True),
    (2, "RutaSur Cargas", 0.88, True),
    (3, "Expreso Regional", 0.78, False),
    (4, "LatamPharma Cold", 0.96, True),
    (5, "Flota Propia Farma Demo", 0.91, True),
    (6, "Courier Local", 0.71, False),
]


def gen_transportistas() -> pd.DataFrame:
    return pd.DataFrame(
        TRANSPORTISTAS, columns=["id_transportista", "transportista", "confiabilidad", "control_frio"]
    )


# ==========================================================================
# 5. Tipo de cambio mensual (el clásico origen de discusiones entre filiales)
# ==========================================================================
def gen_tipo_cambio(filiales: pd.DataFrame) -> pd.DataFrame:
    filas = []
    base = {"UYU": 39, "ARS": 900, "CLP": 950, "PYG": 7400, "PEN": 3.75, "COP": 4200, "USD": 1, "MXN": 17.5}
    for mon, b in base.items():
        # deriva + ruido; ARS con inflación fuerte para que el ajuste importe
        drift = 0.055 if mon == "ARS" else 0.004
        serie = b * np.cumprod(1 + rng.normal(drift, 0.012, N_MESES))
        for m, v in zip(MESES, serie):
            filas.append((m.date(), mon, round(float(v), 6)))
    return pd.DataFrame(filas, columns=["fecha_mes", "moneda", "tc_a_usd"])


# ==========================================================================
# 6. Ofertas comerciales (CRM) — target de clasificación: ¿la aceptó el cliente?
# ==========================================================================
def gen_ofertas(clientes, productos, filiales, reps) -> pd.DataFrame:
    """
    Cada mes, Excelencia Comercial arma campañas: a un subconjunto de
    cliente x producto se le ofrece una condición comercial.
    La aceptación depende de variables observables (descuento, estacionalidad,
    sobrestock, segmento, rep) más ruido. Eso es lo que el modelo debe aprender.
    """
    cli = clientes.set_index("id_cliente")
    prod = productos.set_index("id_producto")
    rep_prod = reps.set_index("id_representante")["productividad"]

    filas = []
    tipos = np.array([t[0] for t in cfg.TIPOS_OFERTA])
    dto_medio = {t[0]: t[2] for t in cfg.TIPOS_OFERTA}

    for mi, mes in enumerate(MESES):
        # Cantidad de ofertas del mes: crece en meses de cierre de trimestre
        cierre_trim = mes.month in (3, 6, 9, 12)
        n_of = int(rng.normal(2100 if cierre_trim else 1500, 120))

        id_cli = rng.choice(clientes["id_cliente"], n_of, p=(clientes["potencial"] / clientes["potencial"].sum()))
        id_pro = rng.choice(productos["id_producto"], n_of, p=productos["peso_demanda"])

        tipo = rng.choice(tipos, n_of, p=[0.38, 0.24, 0.14, 0.16, 0.08])
        dto_base = np.array([dto_medio[t] for t in tipo])
        descuento = np.clip(dto_base * rng.lognormal(0, 0.45, n_of), 0.01, 0.45)

        atc = prod.loc[id_pro, "atc1"].to_numpy()
        est = np.array([cfg.ESTACIONALIDAD[a][mes.month - 1] for a in atc])

        seg = cli.loc[id_cli, "segmento"].to_numpy()
        canal = cli.loc[id_cli, "canal"].to_numpy()
        sens = cli.loc[id_cli, "sensibilidad_precio"].to_numpy()
        prodv = rep_prod.loc[cli.loc[id_cli, "id_representante"].to_numpy()].to_numpy()
        ciclo = prod.loc[id_pro, "ciclo_vida"].to_numpy()

        # Cobertura de stock del cliente al momento de la oferta (días).
        # Alta cobertura => menos ganas de comprar más.
        cobertura = np.clip(rng.gamma(4.0, 12.0, n_of), 2, 220)

        # ---- proceso generador de la aceptación (latente) ----
        z = (
            -1.10
            + 17.0 * descuento * sens                      # el descuento manda, ponderado por sensibilidad
            + 2.60 * (est - 1.0)                            # producto en temporada => entra mejor
            + 0.75 * (seg == "A") + 0.20 * (seg == "B")
            + 0.90 * (prodv - 1.0)                          # calidad del representante
            - 0.020 * cobertura                             # ya tiene stock => no compra
            + 0.45 * (canal == "Distribuidor")
            - 0.35 * (canal == "Farmacia Independiente")
            + 0.55 * ((tipo == "FIN") & (canal == "Institucional"))
            + 0.40 * (tipo == "BON")
            + 0.50 * (ciclo == "Lanzamiento")
            - 0.65 * (ciclo == "Declive")
            + 0.25 * cierre_trim
            + rng.normal(0, 0.26, n_of)                     # ruido irreducible
        )
        p_real = _logit(z)
        aceptada = (rng.random(n_of) < p_real).astype(int)

        unidades_of = np.round(np.clip(rng.lognormal(3.1, 0.85, n_of), 1, 6000)).astype(int)

        filas.append(
            pd.DataFrame(
                {
                    "id_oferta": 0,
                    "fecha_oferta": mes + pd.to_timedelta(rng.integers(0, 26, n_of), unit="D"),
                    "id_cliente": id_cli,
                    "id_producto": id_pro,
                    "tipo_oferta": tipo,
                    "descuento_pct": np.round(descuento, 4),
                    "unidades_ofertadas": unidades_of,
                    "cobertura_cliente_dias": np.round(cobertura, 1),
                    "aceptada": aceptada,
                    # SOLO para medir el techo teórico del problema (AUC oráculo).
                    # Jamás se usa como feature: es información que en la
                    # realidad no existe.
                    "_p_real": np.round(p_real, 6),
                }
            )
        )

    df = pd.concat(filas, ignore_index=True)
    df["id_oferta"] = np.arange(1, len(df) + 1)
    return df


# ==========================================================================
# 7. Sell-in (ERP de facturación) + devoluciones + despachos
# ==========================================================================
def gen_sellin(clientes, productos, filiales, ofertas, depositos, transportistas):
    """
    Genera las líneas de factura. De cada línea nacen:
      - el despacho (con su OTIF y lead time)  -> tablero Logística
      - eventualmente la devolución            -> target ML de devoluciones
    """
    cli = clientes.set_index("id_cliente")
    prod = productos.set_index("id_producto")
    filial_reg = filiales.set_index("id_filial")["region"]
    filial_sla = filiales.set_index("id_filial")["sla_entrega_dias"]
    filial_mad = filiales.set_index("id_filial")["madurez"]
    dep_por_filial = depositos.groupby("id_filial")["id_deposito"].apply(list).to_dict()
    tr_conf = transportistas.set_index("id_transportista")["confiabilidad"]
    tr_frio = transportistas.set_index("id_transportista")["control_frio"]

    # Efecto estructural de filial sobre devoluciones: proceso AR(1).
    # No es ruido — es la realidad de que un problema logístico (un operador
    # flojo, un depósito con mal manejo de frío) dura meses y se corrige de a
    # poco. Es LO QUE HACE que la serie mensual sea proyectable.
    n_fil = len(filiales) + 1
    efecto_fil = np.zeros((n_fil, N_MESES))
    phi, sigma = 0.90, 0.13
    for f in range(1, n_fil):
        e = rng.normal(0, sigma / np.sqrt(1 - phi**2))
        for t in range(N_MESES):
            e = phi * e + rng.normal(0, sigma)
            efecto_fil[f, t] = e

    # Ofertas aceptadas: se convierten en líneas con descuento
    of_ok = ofertas[ofertas["aceptada"] == 1].copy()
    of_ok["anio_mes"] = of_ok["fecha_oferta"].dt.to_period("M")

    bloques = []
    for mi, mes in enumerate(MESES):
        # --- cuántas líneas compra cada cliente este mes ---
        lam = cli["potencial"].to_numpy() * 3.4
        n_lineas = rng.poisson(np.clip(lam, 0.6, 120))
        activos = n_lineas > 0
        if activos.sum() == 0:
            continue
        id_cli = np.repeat(cli.index.to_numpy()[activos], n_lineas[activos])
        n = len(id_cli)

        id_pro = rng.choice(productos["id_producto"], n, p=productos["peso_demanda"])
        idf = cli.loc[id_cli, "id_filial"].to_numpy()
        atc = prod.loc[id_pro, "atc1"].to_numpy()
        est = np.array([cfg.ESTACIONALIDAD[a][mes.month - 1] for a in atc])
        mad = filial_mad.loc[idf].to_numpy()

        # crecimiento de la compañía + estacionalidad + madurez de filial
        tendencia = 1.0 + 0.0055 * mi
        unidades = np.round(
            np.clip(
                rng.lognormal(2.7, 0.95, n)
                * est
                * tendencia
                * mad
                * cli.loc[id_cli, "potencial"].to_numpy() ** 0.30,
                1,
                20000,
            )
        ).astype(int)

        precio_lista = prod.loc[id_pro, "precio_lista_usd"].to_numpy()
        costo = prod.loc[id_pro, "costo_std_usd"].fillna(prod["costo_std_usd"].median()).to_numpy()

        # --- descuento: ofertas aceptadas del mes + descuento comercial de base ---
        descuento = np.clip(rng.beta(1.6, 16, n), 0, 0.30)
        id_oferta = np.zeros(n, dtype=int)
        tipo_oferta = np.array(["SIN"] * n, dtype=object)

        of_mes = of_ok[of_ok["anio_mes"] == mes.to_period("M")]
        if len(of_mes):
            clave_linea = pd.MultiIndex.from_arrays([id_cli, id_pro])
            of_idx = of_mes.drop_duplicates(subset=["id_cliente", "id_producto"]).set_index(
                ["id_cliente", "id_producto"]
            )
            hit = clave_linea.isin(of_idx.index)
            if hit.any():
                sub = of_idx.reindex(clave_linea[hit])
                descuento[hit] = sub["descuento_pct"].to_numpy()
                id_oferta[hit] = sub["id_oferta"].to_numpy()
                tipo_oferta[hit] = sub["tipo_oferta"].to_numpy()

        precio_neto = np.round(precio_lista * (1 - descuento), 4)

        # RESPUESTA DE LA DEMANDA AL PRECIO.
        # q = q_base · (P/P_lista)^ε  con ε = elasticidad del SKU.
        # Es lo que después el paso 5 va a *recuperar* con una regresión
        # log-log. Si el precio no moviera la demanda acá, cualquier
        # elasticidad estimada aguas abajo sería ruido puro.
        elast = prod.loc[id_pro, "elasticidad_real"].to_numpy()
        unidades = np.round(unidades * (1 - descuento) ** elast).astype(int)

        # Carga de canal: por ENCIMA de la respuesta de precio, las
        # bonificaciones y combos empujan stock al cliente más allá de lo que
        # va a consumir. De ahí salen las devoluciones por exceso.
        carga = np.isin(tipo_oferta, ["BON", "COM"])
        if carga.any():
            unidades[carga] = np.round(
                unidades[carga] * rng.uniform(1.15, 1.75, carga.sum())
            ).astype(int)
        unidades = np.clip(unidades, 1, 60000)
        importe = np.round(precio_neto * unidades, 2)

        # --- logística ---
        id_dep = np.array([rng.choice(dep_por_filial.get(f, [1])) for f in idf])
        id_tr = rng.choice(transportistas["id_transportista"], n, p=[0.2, 0.18, 0.14, 0.16, 0.22, 0.10])
        sla = filial_sla.loc[idf].to_numpy()
        conf = tr_conf.loc[id_tr].to_numpy()
        # lead time objetivo ≈ 0.7 × SLA; los transportistas poco confiables se van de rango
        lead_time = np.round(
            np.clip(rng.gamma(6.0, sla / 9.0) * (1.55 - 0.55 * conf), 0.5, 40), 1
        )
        entrega_completa = rng.random(n) < (0.93 + 0.06 * conf)
        otif = ((lead_time <= sla) & entrega_completa).astype(int)

        # vida útil restante del lote al despacho (días)
        # Vida útil remanente al despacho. La cola corta (lotes viejos que salen
        # del depósito para no vencer) es justamente donde nacen las devoluciones.
        vida_total = prod.loc[id_pro, "vida_util_meses"].to_numpy() * 30
        vida_rel = rng.beta(2.0, 2.6, n)
        dias_a_vencer = np.round(np.clip(vida_total * vida_rel, 20, 1500)).astype(int)

        frio = prod.loc[id_pro, "cadena_frio"].to_numpy()
        frio_ok = tr_frio.loc[id_tr].to_numpy()

        # --- probabilidad de devolución (proceso generador latente) ---
        p50_unid = np.median(unidades)
        z = (
            -5.40
            + 2.30 * (frio & ~frio_ok)                           # frío sin control de frío
            + 0.95 * (lead_time > sla)                            # entrega fuera de SLA
            + 1.55 * (dias_a_vencer < cfg.VIDA_UTIL_ALERTA)       # lote corto (umbral)
            + 2.10 * (1 - vida_rel)                               # …y su efecto continuo
            + 1.15 * np.isin(tipo_oferta, ["BON", "COM"])         # carga de canal por oferta
            + 0.80 * (unidades > 2.2 * p50_unid)                  # pedido desproporcionado
            + 4.00 * cli.loc[id_cli, "propension_devolucion"].to_numpy()
            + 0.55 * (1 - otif)
            - 0.45 * (cli.loc[id_cli, "segmento"].to_numpy() == "A")
            + 0.30 * (est > 1.15)                                 # picos de temporada => sobrepedido
            + efecto_fil[idf, mi]                                 # estado logístico de la filial
            + rng.normal(0, 0.22, n)                              # ruido irreducible
        )
        p_dev = _logit(z)
        devuelta = rng.random(n) < p_dev
        unidades_dev = np.where(
            devuelta, np.ceil(unidades * np.clip(rng.beta(2.0, 3.0, n), 0.05, 1.0)), 0
        ).astype(int)

        motivos_cod = np.array([m[0] for m in cfg.MOTIVOS_DEVOLUCION])
        # el motivo se correlaciona con la causa dominante (no es aleatorio puro)
        motivo = np.where(
            devuelta & (frio & ~frio_ok), "FRI",
            np.where(devuelta & (dias_a_vencer < cfg.VIDA_UTIL_ALERTA), "VTO",
            np.where(devuelta & np.isin(tipo_oferta, ["BON", "COM"]), "EXC",
            np.where(devuelta & (otif == 0), "ERR",
                     rng.choice(motivos_cod, n, p=[m[2] for m in cfg.MOTIVOS_DEVOLUCION])))),
        )
        motivo = np.where(devuelta, motivo, "")

        dia = rng.integers(0, min(28, pd.Period(mes, "M").days_in_month), n)
        bloques.append(
            pd.DataFrame(
                {
                    "fecha": mes + pd.to_timedelta(dia, unit="D"),
                    "id_cliente": id_cli,
                    "id_producto": id_pro,
                    "id_filial": idf,
                    "id_deposito": id_dep,
                    "id_transportista": id_tr,
                    "id_oferta": id_oferta,
                    "tipo_oferta": tipo_oferta,
                    "unidades": unidades,
                    "precio_lista_usd": precio_lista,
                    "descuento_pct": np.round(descuento, 4),
                    "precio_neto_usd": precio_neto,
                    "importe_usd": importe,
                    "costo_total_usd": np.round(costo * unidades, 2),
                    "lead_time_dias": lead_time,
                    "sla_dias": sla,
                    "entrega_completa": entrega_completa.astype(int),
                    "otif": otif,
                    "dias_a_vencer": dias_a_vencer,
                    "devuelta": devuelta.astype(int),
                    "_p_real": np.round(p_dev, 6),   # solo para el AUC oráculo
                    "unidades_devueltas": unidades_dev,
                    "motivo_devolucion": motivo,
                }
            )
        )

    df = pd.concat(bloques, ignore_index=True)
    df.insert(0, "id_linea", np.arange(1, len(df) + 1))
    df["importe_devuelto_usd"] = np.round(df["precio_neto_usd"] * df["unidades_devueltas"], 2)
    return df


# ==========================================================================
# 8. Sell-out (panel de auditoría tipo IQVIA) — llega mensual y con desfasaje
# ==========================================================================
def gen_sellout(sellin: pd.DataFrame, productos, filiales) -> pd.DataFrame:
    base = (
        sellin.assign(anio_mes=sellin["fecha"].dt.to_period("M"))
        .groupby(["anio_mes", "id_filial", "id_producto"], as_index=False)
        .agg(unidades_sellin=("unidades", "sum"), importe_sellin=("importe_usd", "sum"))
    )
    n = len(base)
    # El sell-out es la demanda real: sigue al sell-in pero suavizado y desfasado
    ratio = np.clip(rng.normal(0.93, 0.13, n), 0.45, 1.45)
    base["unidades_sellout"] = np.round(base["unidades_sellin"] * ratio).astype(int)
    base["importe_sellout"] = np.round(base["importe_sellin"] * ratio * rng.normal(1.32, 0.05, n), 2)

    # Mercado total de la clase terapéutica (denominador del market share)
    base["unidades_mercado"] = np.round(
        base["unidades_sellout"] / np.clip(rng.beta(2.5, 6.0, n), 0.03, 0.65)
    ).astype(int)
    base["importe_mercado"] = np.round(
        base["importe_sellout"] / np.clip(rng.beta(2.5, 6.0, n), 0.03, 0.65), 2
    )
    base["fecha_mes"] = base["anio_mes"].dt.to_timestamp()
    base = base.drop(columns=["anio_mes", "unidades_sellin", "importe_sellin"])

    # DEFECTO INYECTADO (completitud): la filial PY no reportó un mes
    py = filiales.loc[filiales["cod_filial"] == "PY", "id_filial"].iloc[0]
    falta = (base["id_filial"] == py) & (base["fecha_mes"] == pd.Timestamp("2025-04-01"))
    base = base[~falta].copy()
    return base


# ==========================================================================
# 9. Objetivos comerciales
# ==========================================================================
def gen_objetivos(sellin: pd.DataFrame) -> pd.DataFrame:
    real = (
        sellin.assign(fecha_mes=sellin["fecha"].values.astype("datetime64[M]"))
        .groupby(["fecha_mes", "id_filial", "id_producto"], as_index=False)
        .agg(importe=("importe_usd", "sum"), unidades=("unidades", "sum"))
    )
    n = len(real)
    factor = np.clip(rng.normal(1.06, 0.16, n), 0.72, 1.65)
    real["objetivo_importe_usd"] = np.round(real["importe"] * factor, 2)
    real["objetivo_unidades"] = np.round(real["unidades"] * factor).astype(int)
    return real.drop(columns=["importe", "unidades"])


# ==========================================================================
# 10. Stock por depósito (snapshot mensual) — tablero Logística
# ==========================================================================
def gen_stock(sellin: pd.DataFrame, productos, depositos) -> pd.DataFrame:
    dem = (
        sellin.assign(fecha_mes=sellin["fecha"].values.astype("datetime64[M]"))
        .groupby(["fecha_mes", "id_deposito", "id_producto"], as_index=False)
        .agg(unidades_mes=("unidades", "sum"))
    )
    n = len(dem)
    cobertura_obj = np.clip(rng.gamma(3.2, 22.0, n), 4, 260)  # días de cobertura reales
    dem["stock_unidades"] = np.round(dem["unidades_mes"] / 30.0 * cobertura_obj).astype(int)
    dem["dias_cobertura"] = np.round(cobertura_obj, 1)
    dem["stock_en_transito"] = np.round(dem["stock_unidades"] * rng.beta(1.5, 9, n)).astype(int)

    prod = productos.set_index("id_producto")
    vida = prod.loc[dem["id_producto"], "vida_util_meses"].to_numpy() * 30
    dem["dias_a_vencer_promedio"] = np.round(np.clip(vida * rng.beta(4.0, 2.2, n), 15, 1500)).astype(int)
    dem["unidades_por_vencer_180d"] = np.where(
        dem["dias_a_vencer_promedio"] < cfg.VIDA_UTIL_ALERTA,
        np.round(dem["stock_unidades"] * rng.uniform(0.15, 0.9, n)).astype(int),
        0,
    )
    costo = prod.loc[dem["id_producto"], "costo_std_usd"].fillna(prod["costo_std_usd"].median()).to_numpy()
    dem["valor_stock_usd"] = np.round(dem["stock_unidades"] * costo, 2)
    return dem


# ==========================================================================
# 10-bis. El ERP factura en moneda local — el origen nunca entrega USD
# ==========================================================================
def a_moneda_local(sellin: pd.DataFrame, filiales, tc) -> pd.DataFrame:
    df = sellin.copy()
    df["fecha_mes"] = df["fecha"].values.astype("datetime64[M]")
    mon = filiales.set_index("id_filial")["moneda"]
    df["moneda"] = mon.loc[df["id_filial"]].to_numpy()

    tcx = tc.copy()
    tcx["fecha_mes"] = pd.to_datetime(tcx["fecha_mes"])
    df = df.merge(tcx, on=["fecha_mes", "moneda"], how="left")

    for col_usd, col_loc in [
        ("importe_usd", "importe_local"),
        ("costo_total_usd", "costo_total_local"),
        ("precio_neto_usd", "precio_neto_local"),
        ("precio_lista_usd", "precio_lista_local"),
        ("importe_devuelto_usd", "importe_devuelto_local"),
    ]:
        df[col_loc] = np.round(df[col_usd] * df["tc_a_usd"], 2)

    return df.drop(
        columns=[
            "fecha_mes", "tc_a_usd",
            "importe_usd", "costo_total_usd", "precio_neto_usd",
            "precio_lista_usd", "importe_devuelto_usd",
        ]
    )


# ==========================================================================
# 11. Inyección de defectos de calidad en el hecho principal
# ==========================================================================
def ensuciar_sellin(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reproduce lo que pasa de verdad en una carga multi-filial:
      - unicidad:  reprocesos que duplican líneas
      - validez:   importes negativos que en realidad son notas de crédito
      - exactitud: unidades cargadas con un cero de más
      - formato:   la fecha llega como texto en dos formatos distintos
    """
    out = df.copy()

    dup = out.sample(frac=0.008, random_state=cfg.SEED)
    out = pd.concat([out, dup], ignore_index=True)

    idx_neg = out.sample(frac=0.004, random_state=cfg.SEED + 1).index
    out.loc[idx_neg, ["unidades", "importe_local"]] *= -1

    idx_fat = out.sample(frac=0.0015, random_state=cfg.SEED + 2).index
    out.loc[idx_fat, "unidades"] *= 10

    idx_nul = out.sample(frac=0.006, random_state=cfg.SEED + 3).index
    out.loc[idx_nul, "id_transportista"] = np.nan

    # fecha como texto, dos formatos conviviendo (el clásico de la carga manual)
    fecha_txt = out["fecha"].dt.strftime("%Y-%m-%d")
    mixto = out.sample(frac=0.25, random_state=cfg.SEED + 4).index
    fecha_txt.loc[mixto] = out.loc[mixto, "fecha"].dt.strftime("%d/%m/%Y")
    out["fecha"] = fecha_txt

    return out.sample(frac=1.0, random_state=cfg.SEED + 5).reset_index(drop=True)


# ==========================================================================
# Main
# ==========================================================================
def main() -> None:
    print("PASO 1 · Generando sistemas origen simulados de Farma Demo")
    filiales = gen_filiales()
    productos = gen_productos()
    clientes = gen_clientes(filiales)
    reps = gen_representantes(filiales)
    depositos = gen_depositos(filiales)
    transportistas = gen_transportistas()
    tc = gen_tipo_cambio(filiales)

    print("  · ofertas comerciales (CRM)…")
    ofertas = gen_ofertas(clientes, productos, filiales, reps)

    print("  · sell-in + logística + devoluciones (ERP/WMS/TMS)…")
    sellin = gen_sellin(clientes, productos, filiales, ofertas, depositos, transportistas)

    print("  · sell-out panel de auditoría…")
    sellout = gen_sellout(sellin, productos, filiales)
    objetivos = gen_objetivos(sellin)
    stock = gen_stock(sellin, productos, depositos)

    # El ERP de cada filial factura en SU moneda. El origen NO entrega USD:
    # normalizar a moneda de reporte es trabajo del ETL (paso 2).
    print("  · pasando el sell-in a moneda local de cada filial…")
    sellin = a_moneda_local(sellin, filiales, tc)

    print("  · inyectando defectos de calidad en el hecho principal…")
    sellin_raw = ensuciar_sellin(sellin)

    salidas = {
        "dim_filial": filiales,
        "dim_producto": productos,
        "dim_cliente": clientes,
        "dim_representante": reps,
        "dim_deposito": depositos,
        "dim_transportista": transportistas,
        "tipo_cambio": tc,
        "ofertas": ofertas,
        "sellin": sellin_raw,
        "sellout": sellout,
        "objetivos": objetivos,
        "stock": stock,
    }
    for nombre, df in salidas.items():
        df.to_parquet(cfg.RAW / f"{nombre}.parquet", index=False)
        print(f"    {nombre:<20} {len(df):>9,} filas")

    # una muestra en CSV para poder mirarla sin Python
    sellin_raw.head(500).to_csv(cfg.RAW / "_muestra_sellin.csv", index=False)
    print(f"\n  OK → {cfg.RAW}")


if __name__ == "__main__":
    main()
