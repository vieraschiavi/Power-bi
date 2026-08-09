"""
MV DAX Lab · Motor de análisis, generación y exportación de modelos de Power BI.

El paquete se importa sin levantar Streamlit ni red: cada módulo es utilizable
desde tests, desde la app o desde el servidor MCP.
"""

import os

__version__ = "0.1.0"

MARCA = "MV DAX Lab"
LEMA = "Tu modelo de Power BI, explicado, corregido y exportado."

# Sitio público del producto. El valor por defecto es el nombre que se pensó
# reservar, pero hasta que el deploy exista NO hay ninguna garantía de que
# apunte a algo: por eso vive acá y no repetido por el código. Cuando
# publiques, poné el dominio real en MVDAXLAB_SITIO (o en `sitio` dentro de
# desktop/edicion.json) y toda la app —botones de compra, renovación de la
# suscripción, menú de escritorio, cierre del video— pasa a apuntar ahí.
SITIO = os.environ.get("MVDAXLAB_SITIO", "https://power-bi-mv13.vercel.app").rstrip("/")


def sitio(ruta: str = "") -> str:
    """URL absoluta del sitio: sitio('/#precios') → 'https://…/#precios'."""
    return SITIO + (ruta if ruta.startswith(("/", "#")) else "/" + ruta) \
        if ruta else SITIO


def dominio() -> str:
    """El sitio sin esquema, para mostrarlo como texto."""
    return SITIO.split("://", 1)[-1]
