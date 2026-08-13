# © 2026 Martín Viera. Todos los derechos reservados.

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


# Paleta de la marca, en un solo lugar: la usan la app, el capturador y el
# video. Que el navy del video sea el mismo navy de la app no es cosmético —
# es lo que hace que el prospecto reconozca el producto cuando lo abre.
NAVY, NAVY2, AMBAR, TINTA, APAGADO = ("#081527", "#0c2137", "#f2b441",
                                      "#eaf1fb", "#9db0c8")


def tema_streamlit() -> dict:
    """Variables de entorno que fijan el tema oscuro al arrancar Streamlit.

    Streamlit lee `.streamlit/config.toml` **del directorio actual**, así que
    el archivo del repo no sirve cuando la app arranca desde otro lado: el
    capturador, el .bat del cliente, el Electron, o un `streamlit run` a mano.
    En ese caso quedaba el tema claro por defecto (texto oscuro, primario rojo)
    contra el fondo navy que el CSS pinta igual: texto invisible. Estas
    variables viajan con el proceso y no dependen de dónde se lo lance.
    """
    return {
        "STREAMLIT_THEME_BASE": "dark",
        "STREAMLIT_THEME_PRIMARY_COLOR": AMBAR,
        "STREAMLIT_THEME_BACKGROUND_COLOR": NAVY,
        "STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR": NAVY2,
        "STREAMLIT_THEME_TEXT_COLOR": TINTA,
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "STREAMLIT_CLIENT_TOOLBAR_MODE": "minimal",
    }
