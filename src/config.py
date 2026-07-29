"""
Configuración compartida del proyecto Adium Pharma — Excelencia Comercial.

Un solo lugar donde viven rutas, semillas y parámetros de negocio.
Todos los scripts numerados (01..05) importan de acá.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"        # simulación de sistemas origen (ERP, panel, WMS)
STAGE = DATA / "stage"    # datos limpios / tipificados
STAR = DATA / "star"      # modelo estrella listo para Power BI
ML = DATA / "ml"          # datasets de features, scorings y métricas
OUT = DATA / "out"        # entregables (reportes de calidad, recomendaciones)

for _p in (RAW, STAGE, STAR, ML, OUT):
    _p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Reproducibilidad
# --------------------------------------------------------------------------
SEED = 20260729

# --------------------------------------------------------------------------
# Ventana temporal
# --------------------------------------------------------------------------
FECHA_INICIO = "2024-01-01"
FECHA_FIN = "2025-12-31"

# Corte walk-forward: se entrena con <= CORTE_TRAIN, se valida en CORTE_VALID,
# y el holdout puro (nunca visto durante el tuning) es lo posterior.
CORTE_TRAIN = "2025-06-30"
CORTE_VALID = "2025-09-30"   # valid = (CORTE_TRAIN, CORTE_VALID]
# holdout = (CORTE_VALID, FECHA_FIN]

# --------------------------------------------------------------------------
# Estructura comercial
# --------------------------------------------------------------------------
FILIALES = [
    # (código, país, región, moneda, factor de tamaño, madurez)
    ("UY", "Uruguay",  "Cono Sur", "UYU", 0.35, 1.00),
    ("AR", "Argentina", "Cono Sur", "ARS", 1.30, 0.95),
    ("CL", "Chile",     "Cono Sur", "CLP", 0.90, 1.05),
    ("PY", "Paraguay",  "Cono Sur", "PYG", 0.30, 0.90),
    ("PE", "Perú",      "Andina",   "PEN", 0.95, 0.98),
    ("CO", "Colombia",  "Andina",   "COP", 1.20, 1.02),
    ("EC", "Ecuador",   "Andina",   "USD", 0.55, 0.92),
    ("MX", "México",    "Norte",    "MXN", 1.60, 1.08),
]

CANALES = ["Distribuidor", "Farmacia Cadena", "Farmacia Independiente", "Institucional"]
SEGMENTOS_CLIENTE = ["A", "B", "C"]          # A = top, C = cola larga

# Clasificación ATC nivel 1 (subconjunto realista para un laboratorio LATAM)
ATC1 = {
    "A": "Aparato digestivo y metabolismo",
    "C": "Sistema cardiovascular",
    "J": "Antiinfecciosos vía general",
    "L": "Agentes antineoplásicos",
    "M": "Sistema musculoesquelético",
    "N": "Sistema nervioso",
    "R": "Sistema respiratorio",
}

# Estacionalidad por ATC1: índice multiplicativo mes 1..12.
# Respiratorio y antiinfecciosos pican en invierno del hemisferio sur (jun-ago).
ESTACIONALIDAD = {
    "R": [0.80, 0.82, 0.92, 1.05, 1.25, 1.45, 1.50, 1.35, 1.10, 0.92, 0.82, 0.78],
    "J": [0.85, 0.86, 0.95, 1.05, 1.20, 1.35, 1.38, 1.28, 1.08, 0.95, 0.88, 0.83],
    "N": [1.05, 0.95, 1.00, 1.02, 1.00, 0.98, 0.98, 1.00, 1.02, 1.04, 1.02, 0.95],
    "C": [1.00, 0.98, 1.02, 1.00, 1.01, 1.00, 1.00, 1.00, 1.01, 1.02, 1.00, 0.96],
    "A": [1.02, 0.96, 1.00, 1.00, 1.00, 0.99, 0.99, 1.00, 1.01, 1.03, 1.05, 1.10],
    "M": [0.95, 0.94, 1.00, 1.03, 1.05, 1.08, 1.08, 1.05, 1.02, 1.00, 0.97, 0.90],
    "L": [1.00, 1.00, 1.01, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 0.99],
}

# --------------------------------------------------------------------------
# Parámetros de negocio (reglas canónicas — las mismas que replica el SQL)
# --------------------------------------------------------------------------
N_PRODUCTOS = 120
N_CLIENTES = 900
N_REPRESENTANTES = 70
N_DEPOSITOS = 10

# Tipos de oferta comercial vigentes
TIPOS_OFERTA = [
    # (código, nombre, descuento medio, costo relativo, apto para)
    ("DTO", "Descuento directo %",      0.12, 1.00),
    ("BON", "Bonificación en producto", 0.10, 0.72),  # cuesta el costo, no el precio
    ("REB", "Rebate por volumen",       0.07, 1.00),
    ("COM", "Combo multiproducto",      0.15, 0.85),
    ("FIN", "Plazo extendido de pago",  0.04, 0.35),
]

# Motivos de devolución (con su peso relativo base)
MOTIVOS_DEVOLUCION = [
    ("VTO", "Próximo a vencer",            0.26, "Comercial"),
    ("FRI", "Ruptura de cadena de frío",   0.11, "Logística"),
    ("AVE", "Producto averiado",           0.15, "Logística"),
    ("ERR", "Error de pedido / picking",   0.18, "Logística"),
    ("EXC", "Exceso de stock del cliente", 0.20, "Comercial"),
    ("CAL", "Reclamo de calidad",          0.04, "Calidad"),
    ("ADM", "Diferencia administrativa",   0.06, "Administración"),
]

# SLA logístico por región (días hábiles objetivo de entrega)
SLA_ENTREGA = {"Cono Sur": 3, "Andina": 5, "Norte": 4}

# Umbrales de negocio usados en tablero y en el motor de IA
DOH_MIN = 30      # días de cobertura mínimos deseados
DOH_MAX = 90      # por encima → sobrestock, candidato a oferta
VIDA_UTIL_ALERTA = 180  # días a vencimiento por debajo de los cuales el lote es crítico

# --------------------------------------------------------------------------
# Paleta corporativa (misma en Power BI, en Python y en la documentación)
# --------------------------------------------------------------------------
PALETA = {
    "primario": "#0B3C5D",
    "secundario": "#1D7874",
    "acento": "#F2A65A",
    "ok": "#2E8B57",
    "alerta": "#E4A020",
    "riesgo": "#C1443C",
    "neutro": "#5A6B7B",
    "fondo": "#F5F7FA",
}
