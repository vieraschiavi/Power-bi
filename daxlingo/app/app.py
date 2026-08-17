# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Dashboard principal (Streamlit), trilingüe ES/EN/PT.

Una sola app con todo el ciclo: cargar un modelo de Power BI (.pbit / PBIP /
.bim / .pbix), entenderlo, auditarlo, mejorarlo (transformaciones y NL→DAX
con anti-alucinación), practicar (Academia DAX) y exportarlo de vuelta a
.pbit/PBIP con tablero, filtros y navegación — o publicarlo en Fabric.

Correr:  streamlit run daxlingo/app/app.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dxl import MARCA, __version__, sitio  # noqa: E402
from dxl import analizador, asistente, catalogo, ejercicios  # noqa: E402
from dxl import explicador, fabric, generador, herramientas, ia  # noqa: E402
from dxl import licencia as lic  # noqa: E402
from dxl import modelo as modmod  # noqa: E402
from dxl import proveedores_ia, tablero, transformador  # noqa: E402
from dxl.i18n import IDIOMAS, NOMBRES_IDIOMA, t  # noqa: E402

NAVY, NAVY2, AMBAR, TINTA, APAGADO = ("#081527", "#0c2137", "#f2b441",
                                      "#eaf1fb", "#9db0c8")

st.set_page_config(page_title=f"{MARCA} · DAX + Power BI + Fabric",
                   page_icon="🟨", layout="wide")

# Íconos de las 14 pestañas, en el orden de `st.tabs(...)`. Trazo de línea,
# mismo grosor y misma caja: un sistema, no una bolsa de emojis. Van como
# máscara CSS —ver el bloque de estilos— así el color lo pone la hoja de
# estilos y no la fuente de emojis del sistema operativo.
def _svg(cuerpo: str) -> str:
    """Un SVG de línea listo para embeber como máscara en CSS.

    Se usan comillas simples adentro y se escapan `<`, `>` y `#`: dentro de
    un `url("data:image/svg+xml;utf8,...")` esos caracteres cortan el valor y
    la regla entera se descarta en silencio.
    """
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
           "fill='none' stroke='black' stroke-width='2' "
           f"stroke-linecap='round' stroke-linejoin='round'>{cuerpo}</svg>")
    return svg.replace("<", "%3C").replace(">", "%3E").replace("#", "%23")


ICONOS_TABS = [
    _svg("<circle cx='12' cy='12' r='9'/><path d='M9.1 9a3 3 0 015.8 1c0 2-3 "
         "2.5-3 4'/><path d='M12 17.5v.01'/>"),                   # Guía
    _svg("<path d='M12 3v12M7 11l5 5 5-5M4 21h16'/>"),            # Modelo
    _svg("<circle cx='6' cy='6' r='2.5'/><circle cx='18' cy='6' r='2.5'/>"
         "<circle cx='12' cy='18' r='2.5'/><path d='M8 7.5l3 8M16 7.5l-3 8'/>"),
    _svg("<path d='M3 12h4l2.5-7 4 14L16 12h5'/>"),               # Analizador
    _svg("<path d='M12 3l1.9 4.6 4.6 1.9-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6"
         "-1.9z'/><path d='M18 16l.9 2.1 2.1.9-2.1.9L18 22l-.9-2.1-2.1-.9 "
         "2.1-.9z'/>"),                                           # Generar DAX
    _svg("<path d='M4 5h6a2 2 0 012 2v12a2 2 0 00-2-2H4zM20 5h-6a2 2 0 "
         "00-2 2v12a2 2 0 012-2h6z'/>"),                          # Explicador
    _svg("<path d='M4 8h11M4 16h7'/><path d='M17 5l4 3-4 3M13 13l4 3-4 3'/>"),
    _svg("<path d='M4 20V10M10 20V4M16 20v-7M22 20H2'/>"),        # Exportar
    _svg("<path d='M12 3l8 4.5v9L12 21l-8-4.5v-9z'/><path d='M12 12l8-4.5M12 "
         "12v9M12 12L4 7.5'/>"),                                  # Fabric
    _svg("<rect x='3' y='4' width='18' height='13' rx='2'/><path d='M8 21h8'/>"
         "<path d='M9 10.5l2 2 4-4'/>"),                          # Asistente
    _svg("<path d='M12 4L2 9l10 5 10-5z'/><path d='M6 11.5V17c0 1.7 2.7 3 6 "
         "3s6-1.3 6-3v-5.5'/>"),                                  # Academia
    _svg("<path d='M14.5 6.5a4 4 0 105 5L21 13l-8 8-4-4 8-8z'/>"
         "<path d='M7 13l-4 4 4 4 2-2'/>"),                       # Herramientas
    _svg("<circle cx='8' cy='12' r='4'/><path d='M12 12h9M18 12v3M15 12v2'/>"),
    _svg("<circle cx='12' cy='12' r='3'/><path d='M12 2v3M12 19v3M2 12h3M19 "
         "12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2'/>"),        # Configuración
]

# El CSS pinta el fondo oscuro sí o sí, así que TAMBIÉN tiene que pintar cada
# color de texto. Streamlit solo lee `.streamlit/config.toml` desde el
# directorio actual: si la app arranca desde otra carpeta —el capturador, el
# .bat del cliente, `streamlit run` a mano— el tema no carga, queda el claro
# por defecto (texto #31333F, primario rojo #FF4B4B) y el resultado es texto
# oscuro sobre fondo oscuro: ilegible. Depender del config para la
# legibilidad era el bug. Acá no se hereda nada.
st.markdown(f"""<style>
.stApp {{ background: linear-gradient(180deg,{NAVY} 0%,#0a1a30 100%);
    color:{TINTA}; }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp div,
.stMarkdown, [data-testid="stMarkdownContainer"] {{ color:{TINTA}; }}
h1,h2,h3,h4,h5,h6 {{ color:{TINTA} !important; }}
small, .stCaption, [data-testid="stCaptionContainer"] {{ color:{APAGADO} !important; }}

section[data-testid="stSidebar"] {{ background:{NAVY2};
    border-right:1px solid #1d3149; }}
section[data-testid="stSidebar"] * {{ color:{TINTA}; }}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] small {{ color:{APAGADO} !important; }}

[data-testid="stMetric"] {{ background:{NAVY2}; border:1px solid #1d3149;
    border-radius:14px; padding:14px 16px;
    box-shadow:0 2px 10px rgba(0,0,0,.35); }}
[data-testid="stMetricValue"] {{ color:{AMBAR} !important; font-weight:700; }}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{
    color:{APAGADO} !important; }}

/* Controles: sin esto los inputs salen blancos con texto blanco. */
.stSelectbox div[data-baseweb="select"] > div, .stTextInput input,
.stTextArea textarea, .stNumberInput input, div[data-baseweb="popover"] li {{
    background:#12294a !important; color:{TINTA} !important;
    border-color:#24405f !important; }}
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background:{AMBAR}; }}

/* El primario del tema claro es rojo: acá manda el ámbar de la marca. */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
    background:{NAVY2}; color:{TINTA}; border:1px solid #24405f;
    border-radius:9px; font-weight:600; }}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color:{AMBAR}; color:{AMBAR}; }}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {{
    background:{AMBAR}; color:#1c1305; border:0; }}
.stButton > button[kind="primary"]:hover {{ background:#ffc95c; color:#1c1305; }}

.dxl-badge {{ background:{AMBAR}; color:#1c1305; border-radius:20px;
    padding:2px 12px; font-weight:700; font-size:0.8rem; }}
.dxl-caja {{ background:{NAVY2}; border-left:4px solid {AMBAR};
    border-radius:8px; padding:12px 16px; margin:8px 0; color:{TINTA}; }}
.dxl-ok {{ border-left-color:#00c896; }}
.dxl-mal {{ border-left-color:#c1443c; }}

/* --- Pestaña Herramientas -------------------------------------------
   Tarjetas con ícono SVG y una píldora de estado. Antes cada herramienta
   era una línea de texto con un emoji de círculo (🟢/⚪) como semáforo:
   el círculo blanco se leía igual para "no está instalada" que para "esto
   es una web y no se instala", y los emojis se ven distintos en cada
   sistema. Un punto CSS se ve igual en todos lados y el color lo elige el
   estado, no el font del sistema. */
.dxl-h {{ background:{NAVY2}; border:1px solid #1d3149; border-radius:12px;
    padding:14px 16px; height:100%; transition:border-color .15s ease; }}
.dxl-h:hover {{ border-color:{AMBAR}; }}
.dxl-h-top {{ display:flex; align-items:center; gap:10px; margin-bottom:6px; }}
.dxl-h-ico {{ flex:0 0 34px; width:34px; height:34px; border-radius:9px;
    background:#12283f; display:flex; align-items:center; justify-content:center; }}
.dxl-h-ico svg {{ width:18px; height:18px; stroke:{AMBAR}; fill:none;
    stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }}
.dxl-h-nom {{ font-weight:650; color:{TINTA}; line-height:1.25; font-size:.95rem; }}
.dxl-h-desc {{ color:{APAGADO}; font-size:.82rem; margin:0 0 10px; }}
.dxl-h-pill {{ display:inline-flex; align-items:center; gap:6px;
    font-size:.74rem; padding:3px 10px; border-radius:20px;
    border:1px solid #24405f; background:#0f2135; color:{APAGADO}; }}
.dxl-h-pt {{ width:7px; height:7px; border-radius:50%; background:{APAGADO}; }}
.dxl-h-si .dxl-h-pt {{ background:#00c896; }}
.dxl-h-si {{ color:#7fe3c4; border-color:#1c5745; }}
.dxl-h-no .dxl-h-pt {{ background:#c1443c; }}
.dxl-h-info .dxl-h-pt {{ background:#4a9bd6; }}
.dxl-h-info {{ color:#9ecdf0; border-color:#1e4460; }}
.dxl-h-int {{ color:{APAGADO}; font-size:.78rem; margin-top:10px;
    padding-top:10px; border-top:1px solid #1d3149; line-height:1.45; }}
.dxl-h-link {{ color:{AMBAR}; font-size:.78rem; text-decoration:none;
    margin-left:10px; }}
.dxl-h-link:hover {{ text-decoration:underline; }}
.dxl-etapa {{ display:flex; align-items:center; gap:10px; margin:22px 0 10px; }}
.dxl-etapa-n {{ font-family:ui-monospace,monospace; font-size:.72rem;
    color:#0a1a2e; background:{AMBAR}; padding:2px 8px; border-radius:5px;
    font-weight:700; }}
.dxl-etapa-t {{ color:{TINTA}; font-weight:600; font-size:1rem; }}
.dxl-etapa-l {{ flex:1; height:1px; background:#1d3149; }}

/* --- Íconos de las pestañas ------------------------------------------
   Las 14 pestañas tenían un emoji cada una: ❓ 📥 🕸️ 🩺 🤖 📖 🔧 📊 🟪 🖥️
   🎓 🛠️ 🔑 ⚙️. Mezclaban caretas, instrumental médico y cuadrados de color
   —no eran un sistema— y encima cada sistema operativo los dibuja distinto:
   lo que en Windows es plano, en Mac es 3D y en Android otra cosa. En un
   producto que se vende, esa barra es lo primero que se ve.

   Streamlit no acepta HTML en el label de una pestaña, así que el ícono va
   por CSS: un SVG embebido como máscara, con el color de la marca. Se ve
   idéntico en todos lados, acompaña el estado activo y no depende de la
   fuente de emojis del sistema. El orden es el de `st.tabs(...)`. */
.stTabs [data-testid="stTab"] p::before,
.stTabs button[role="tab"] p::before {{
    content:""; display:inline-block; width:16px; height:16px;
    margin-right:8px; vertical-align:-3px;
    background-color:{APAGADO};
    -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat;
    -webkit-mask-position:center; mask-position:center;
    -webkit-mask-size:contain; mask-size:contain; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p::before,
.stTabs button[role="tab"][aria-selected="true"] p::before {{
    background-color:{AMBAR}; }}
{"".join(
    f'.stTabs [role="tablist"] > *:nth-child({i}) p::before {{'
    f'-webkit-mask-image:url("data:image/svg+xml;utf8,{svg}");'
    f'mask-image:url("data:image/svg+xml;utf8,{svg}"); }}'
    for i, svg in enumerate(ICONOS_TABS, start=1))}
code, .stCode code {{ color:{AMBAR}; }}
pre, .stCode {{ background:#0a1b30 !important; border:1px solid #1d3149;
    border-radius:10px; }}

/* Las 14 pestañas se envuelven en varias filas en vez de esconderse detrás de
   una flecha de desborde: en una pantalla angosta, la mitad del producto
   quedaba invisible salvo que supieras que había que scrollear la barra. */
/* Las 14 pestañas entran en varias filas en vez de esconderse detrás de una
   flecha de desborde: en una pantalla angosta la mitad del producto quedaba
   invisible salvo que supieras que la barra scrollea. Se apunta por rol y por
   atributo porque el nombre interno cambia entre versiones de Streamlit. */
.stTabs div[role="tablist"], .stTabs [data-baseweb="tab-list"] {{
    gap:6px 18px; border-bottom:1px solid #1d3149;
    flex-wrap:wrap !important; overflow:visible !important;
    scrollbar-width:none; }}
.stTabs div[role="tablist"]::-webkit-scrollbar {{ display:none; }}
.stTabs [data-baseweb="tab-border"] {{ display:none; }}
.stTabs [data-baseweb="tab"] {{ color:{APAGADO} !important; }}
.stTabs [data-baseweb="tab"] * {{ color:inherit !important; }}
.stTabs [data-baseweb="tab"]:hover {{ color:{TINTA} !important; }}
.stTabs [aria-selected="true"], .stTabs [aria-selected="true"] * {{
    color:{AMBAR} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:{AMBAR}; }}

[data-testid="stExpander"] {{ border:1px solid #1d3149; border-radius:10px;
    background:{NAVY2}; }}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {{
    color:{TINTA} !important; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ color:{TINTA}; }}

/* La barra de Streamlit (Deploy, menú de la nube) no es parte del producto:
   fuera. Sin esto queda una franja blanca arriba de una app oscura. */
header[data-testid="stHeader"] {{ background:transparent; height:0; }}
[data-testid="stToolbar"], [data-testid="stDecoration"] {{ display:none; }}
.block-container {{ padding-top:1.6rem; }}
</style>""", unsafe_allow_html=True)


# ==========================================================================
# Estado de sesión
# ==========================================================================
def _estado(clave, defecto):
    if clave not in st.session_state:
        st.session_state[clave] = defecto
    return st.session_state[clave]


_estado("cargado", None)
_estado("historial", [])
_estado("xp", 0)
_estado("resueltos", set())
_estado("api_key", "")
_estado("endpoint", "")
_estado("idioma", lic.preferencia("idioma", "es"))
_estado("proveedor", lic.preferencia("proveedor", proveedores_ia.PROVEEDOR_DEFECTO))
_estado("modelo_ia", lic.preferencia(
    "modelo_ia", proveedores_ia.modelo_defecto(st.session_state.proveedor)))

IDIOMA = st.session_state.idioma
ESTADO_LIC = lic.evaluar()


def _(clave: str) -> str:
    return t(clave, IDIOMA)


def modelo_demo() -> Path | None:
    """
    El modelo demo que se distribuye con el producto: `datos/demo/`, que es lo
    que el instalador lleva adentro.

    Desde el repo de desarrollo también sirve cualquier PBIP que haya en
    `powerbi/archivos/`, que es de donde salió. Se busca por patrón y no por
    nombre a propósito: el producto no nombra ninguna empresa, ni siquiera en
    una ruta de respaldo que el cliente podría ver en un mensaje de error.
    """
    empaquetado = RAIZ / "datos" / "demo" / "modelo_demo.bim"
    if empaquetado.exists():
        return empaquetado
    fuentes = sorted((RAIZ.parent / "powerbi" / "archivos")
                     .glob("*.SemanticModel/model.bim"))
    return fuentes[0] if fuentes else None


def cat_actual() -> catalogo.Catalogo | None:
    cargado = st.session_state.cargado
    if not cargado:
        return None
    if cargado.get("modelo"):
        return catalogo.Catalogo.desde_modelo(cargado["modelo"])
    if cargado.get("layout"):
        return catalogo.Catalogo.desde_layout(cargado["layout"])
    return None


def aplicar_modelo(nuevo: dict, cambios: list[str]) -> None:
    st.session_state.cargado["modelo"] = nuevo
    st.session_state.historial.extend(cambios)


def _flash(mensaje: str, tipo: str = "success") -> None:
    """Guarda un mensaje para mostrarlo recién en el próximo render.

    `st.rerun()` corta la ejecución actual ahí mismo — un `st.success(...)`
    seguido de `st.rerun()` nunca llega a pintarse, así que el mensaje de
    confirmación desaparecía sin que nadie lo viera. Guardarlo acá y
    mostrarlo al principio del render siguiente es lo único que lo hace
    sobrevivir al rerun que refresca el estado.
    """
    st.session_state["_flash"] = (tipo, mensaje)


def _mostrar_flash() -> None:
    pendiente = st.session_state.pop("_flash", None)
    if pendiente:
        tipo, mensaje = pendiente
        getattr(st, tipo)(mensaje)


def gate(funcion: str) -> bool:
    """True si la edición/licencia habilita la función; si no, avisa."""
    if ESTADO_LIC.permite(funcion):
        return True
    st.markdown(f"<div class='dxl-caja dxl-mal'>🔒 {_('lic_bloqueado')}</div>",
                unsafe_allow_html=True)
    return False


# ==========================================================================
# Barra lateral: idioma + licencia
# ==========================================================================
with st.sidebar:
    st.markdown(f"### 🟨 {MARCA}")
    nuevo_idioma = st.selectbox(
        _("idioma"), IDIOMAS, index=IDIOMAS.index(IDIOMA),
        format_func=lambda i: NOMBRES_IDIOMA[i])
    if nuevo_idioma != IDIOMA:
        st.session_state.idioma = nuevo_idioma
        lic.guardar_preferencia("idioma", nuevo_idioma)
        # `historial` guarda los cambios ya traducidos al idioma de cuando
        # pasaron, no la clave — mostrar entradas viejas junto a las nuevas
        # dejaría un historial mitad en un idioma, mitad en otro. Es «cambios
        # de esta sesión»: al cambiar de idioma, arranca de nuevo.
        st.session_state.historial = []
        st.rerun()

    icono = {"owner": "👑", "licencia": "✅", "demo": "🕒",
             "vencida": "🔒"}[ESTADO_LIC.motivo]
    st.markdown(f"**{_('lic_edicion')}:** {icono} "
                f"`{_('edicion_' + ESTADO_LIC.edicion)}`")
    if ESTADO_LIC.motivo == "demo":
        st.caption(f"{_('lic_dias')}: **{ESTADO_LIC.dias_restantes}**")
    elif ESTADO_LIC.motivo == "vencida":
        st.caption("🔒 " + _("lic_vencida"))
    st.caption(f"v{__version__}")


# ==========================================================================
# Header
# ==========================================================================
_mostrar_flash()

izq, der = st.columns([0.65, 0.35])
with izq:
    st.markdown(f"# 🟨 {MARCA} <span class='dxl-badge'>DAX · Power BI · "
                f"Fabric</span>", unsafe_allow_html=True)
    st.caption(_("lema"))
with der:
    cat = cat_actual()
    if cat:
        r = cat.resumen()
        c1, c2, c3 = st.columns(3)
        c1.metric(_("tablas"), r["tablas"])
        c2.metric(_("medidas"), r["medidas"])
        c3.metric(_("relaciones"), r["relaciones"])
    else:
        st.markdown(f"<div class='dxl-caja'>{_('sin_modelo')}</div>",
                    unsafe_allow_html=True)

(tab_guia, tab_modelo, tab_rel, tab_analisis, tab_generar, tab_explicar,
 tab_transformar, tab_exportar, tab_fabric, tab_overlay, tab_academia,
 tab_tools, tab_lic, tab_config) = st.tabs([
     _("tab_guia"), _("tab_modelo"), _("tab_relaciones"), _("tab_analizador"),
     _("tab_generar"), _("tab_explicar"), _("tab_transformar"),
     _("tab_exportar"), _("tab_fabric"), _("tab_overlay"), _("tab_academia"),
     _("tab_herramientas"), _("tab_licencia"), _("tab_config")])


# ==========================================================================
# ❓ Guía
# ==========================================================================
with tab_guia:
    st.subheader(_("guia_titulo"))
    st.markdown(_("guia_ciclo"))
    st.markdown(_("guia_pasos"))
    st.info(_("guia_demo"))


# ==========================================================================
# 📥 Modelo
# ==========================================================================
with tab_modelo:
    st.subheader(_("cargar_modelo"))
    col_a, col_b = st.columns([0.55, 0.45])
    with col_a:
        subida = st.file_uploader(_("arrastra"),
                                  type=["pbit", "pbix", "bim", "json", "zip"])
        if subida is not None and st.button(_("btn_cargar"), type="primary"):
            tmp = Path(tempfile.mkdtemp(prefix="dxl_"))
            destino = tmp / subida.name
            destino.write_bytes(subida.getvalue())
            try:
                if destino.suffix.lower() == ".zip":
                    with zipfile.ZipFile(destino) as z:
                        z.extractall(tmp / "pbip")
                    st.session_state.cargado = modmod.cargar(tmp / "pbip")
                else:
                    st.session_state.cargado = modmod.cargar(destino)
                st.session_state.historial = []
                st.rerun()
            except Exception as exc:
                st.error(f"{_('no_se_pudo_cargar')}: {exc}")
    with col_b:
        st.markdown(f"**{_('modelo_demo')}**")
        demo = modelo_demo()
        if demo and st.button(_("btn_demo")):
            st.session_state.cargado = modmod.cargar(demo)
            st.session_state.historial = []
            st.rerun()

    cargado = st.session_state.cargado
    if cargado:
        for adv in cargado.get("advertencias", []):
            st.warning(adv)
        cat = cat_actual()
        if cat:
            r = cat.resumen()
            parcial = f" · {_('catalogo_parcial')}" if r["parcial"] else ""
            st.markdown(
                f"<div class='dxl-caja dxl-ok'>✅ <b>{cargado['formato']}</b> · "
                f"{r['tablas']} {_('tablas').lower()} · {r['columnas']} "
                f"{_('columnas').lower()} · {r['medidas']} "
                f"{_('medidas').lower()} · {r['relaciones']} "
                f"{_('relaciones').lower()}{parcial}</div>",
                unsafe_allow_html=True)
            for tb in cat.tablas:
                if tb["interna"]:
                    continue
                with st.expander(f"📋 {tb['nombre']} — {len(tb['columnas'])} "
                                 f"{_('columnas').lower()} · "
                                 f"{len(tb['medidas'])} {_('medidas').lower()}"):
                    if tb["columnas"]:
                        st.dataframe(
                            [{_("columna"): c["nombre"], _("tipo"): c["tipo"],
                              _("oculta"): "✔" if c["oculta"] else "",
                              _("calculada"): "✔" if c["calculada"] else ""}
                             for c in tb["columnas"]],
                            width="stretch", hide_index=True)
                    for m in tb["medidas"]:
                        st.markdown(f"**[{m['nombre']}]** "
                                    f"`{m['formato'] or _('sin_formato')}`")
                        st.code(m["expresion"], language="sql")
        if st.session_state.historial:
            st.markdown(f"**{_('cambios_sesion')}**")
            for c in st.session_state.historial:
                st.markdown(f"- {c}")


# ==========================================================================
# 🕸️ Relaciones
# ==========================================================================
with tab_rel:
    st.subheader(_("mapa_modelo"))
    cat = cat_actual()
    if not cat:
        st.info(_("carga_primero"))
    elif not cat.relaciones:
        st.warning(_("sin_relaciones"))
    else:
        lineas = ["digraph modelo {",
                  '  rankdir=LR; bgcolor="transparent";',
                  '  node [shape=box, style="rounded,filled", '
                  f'fillcolor="{NAVY2}", fontcolor="{TINTA}", '
                  f'color="{AMBAR}", fontname="Helvetica"];',
                  f'  edge [color="{APAGADO}", fontcolor="{APAGADO}", '
                  'fontsize=10];']
        fechas = (cat.tabla_fechas() or {}).get("nombre")
        for tb in cat.tablas:
            if tb["interna"]:
                continue
            extra = ' fillcolor="#1d3149"' if tb["nombre"] == fechas else ""
            lineas.append(f'  "{tb["nombre"]}" [label="{tb["nombre"]}\\n'
                          f'{len(tb["columnas"])} col · '
                          f'{len(tb["medidas"])} med"{extra}];')
        for r in cat.relaciones:
            estilo = []
            if r["bidireccional"]:
                estilo.append('dir=both color="#c1443c"')
            if not r["activa"]:
                estilo.append("style=dashed")
            attrs = (" [" + " ".join(estilo) + "]") if estilo else ""
            lineas.append(f'  "{r["desde_tabla"]}" -> "{r["hacia_tabla"]}"'
                          f'{attrs};')
        lineas.append("}")
        st.graphviz_chart("\n".join(lineas), width="stretch")
        st.caption(_("leyenda_grafo"))


# ==========================================================================
# 🩺 Analizador
# ==========================================================================
with tab_analisis:
    st.subheader(_("buenas_practicas"))
    cat = cat_actual()
    if not cat:
        st.info(_("carga_primero"))
    else:
        hallazgos = analizador.analizar(cat)
        grupos = analizador.agrupar(hallazgos)
        c1, c2, c3 = st.columns(3)
        c1.metric(_("salud"), f"{analizador.puntaje(hallazgos)}/100")
        c2.metric(_("hallazgos"), len(hallazgos))
        c3.metric(_("arreglables"), sum(1 for h in hallazgos if h["auto"]))
        for g in grupos:
            icono = {"alta": "🔴", "media": "🟡", "baja": "🔵"}[g["severidad"]]
            cuantos = len(g["objetos"])
            sufijo = f" · {cuantos}×" if cuantos > 1 else f" — {g['objetos'][0]}"
            txt = analizador.describir(g, IDIOMA)
            with st.expander(f"{icono} {txt['titulo']}{sufijo}"):
                st.markdown(f"**{_('por_que_importa')}:** {txt['detalle']}")
                st.markdown(f"**{_('como_se_arregla')}:** {txt['arreglo']}")
                if g["auto"]:
                    st.markdown(f"✅ *{_('arreglable_auto')}*")
                if cuantos > 1:
                    st.code("\n".join(g["objetos"][:40])
                            + ("\n…" if cuantos > 40 else ""))
        if any(h["auto"] for h in hallazgos) and \
                st.session_state.cargado.get("modelo"):
            if st.button(_("btn_arreglar"), type="primary") and \
                    gate("transformar"):
                nuevo, cambios = transformador.aplicar_arreglos(
                    st.session_state.cargado["modelo"], hallazgos, IDIOMA)
                aplicar_modelo(nuevo, cambios)
                _flash(f"{len(cambios)} {_('cambios_aplicados')}")
                st.rerun()

        prov = st.session_state.proveedor
        if proveedores_ia.hay_clave(prov, st.session_state.api_key):
            if st.button(_("opinion_ia")):
                with st.spinner(_("consultando")):
                    try:
                        st.markdown(ia.analizar_modelo_ia(
                            generador._catalogo_para_prompt(cat), hallazgos,
                            proveedor=prov, modelo=st.session_state.modelo_ia,
                            api_key=st.session_state.api_key,
                            endpoint=st.session_state.endpoint))
                    except Exception as exc:
                        st.error(str(exc))
        else:
            st.caption(_("sin_clave_opinion"))


# ==========================================================================
# 🤖 Generar DAX
# ==========================================================================
with tab_generar:
    st.subheader(_("gen_titulo"))
    cat = cat_actual()
    if not cat:
        st.info(_("carga_primero"))
    elif gate("generar"):
        pedido = st.text_input(_("gen_pregunta"), placeholder=_("gen_ejemplos"))
        if pedido:
            r = generador.generar(
                pedido, cat, api_key=st.session_state.api_key or None,
                idioma=IDIOMA,
                proveedor=st.session_state.proveedor,
                modelo_ia=st.session_state.modelo_ia,
                endpoint=st.session_state.endpoint)
            if r["ok"]:
                st.markdown(
                    f"<div class='dxl-caja dxl-ok'><b>[{r['nombre']}]</b> · "
                    f"{_('formato')} <code>{r['formato']}</code> · "
                    f"{_('gen_motor')}: {r['metodo']}</div>",
                    unsafe_allow_html=True)
                st.code(r["dax"], language="sql")
                st.markdown(f"**{_('gen_porque')}:** {r['explicacion']}")
                if st.session_state.cargado.get("modelo") and \
                        st.button(_("gen_agregar")):
                    try:
                        nuevo, cambios = transformador.agregar_medida(
                            st.session_state.cargado["modelo"], r["nombre"],
                            r["dax"], formato=r["formato"],
                            descripcion=r["explicacion"], idioma=IDIOMA)
                        aplicar_modelo(nuevo, cambios)
                        st.success(cambios[0])
                    except ValueError as exc:
                        st.error(str(exc))
            else:
                for adv in r["advertencias"]:
                    st.markdown(f"<div class='dxl-caja dxl-mal'>{adv}</div>",
                                unsafe_allow_html=True)


# ==========================================================================
# 📖 Explicador
# ==========================================================================
with tab_explicar:
    st.subheader(_("exp_titulo"))
    cat = cat_actual()
    opciones = [_("exp_pegar")]
    medidas_cat = cat.medidas() if cat else []
    opciones += [f"[{m['nombre']}]" for m in medidas_cat]
    eleccion = st.selectbox(_("exp_selector"), opciones)
    if eleccion != opciones[0]:
        m = medidas_cat[opciones.index(eleccion) - 1]
        expresion, nombre = m["expresion"], m["nombre"]
        st.code(expresion, language="sql")
    else:
        nombre = ""
        expresion = st.text_area(_("exp_expresion"), height=140,
                                 placeholder="CALCULATE ( SUM ( … ) )")
    if expresion.strip():
        e = explicador.explicar(expresion, cat, nombre, IDIOMA)
        st.markdown(f"<div class='dxl-caja'><b>{e['resumen']}</b> · "
                    f"{_('exp_nivel')} {e['nivel_txt']}</div>",
                    unsafe_allow_html=True)
        for paso in e["pasos"]:
            st.markdown(f"- {paso}")
        if e["funciones"]:
            st.dataframe([{_("exp_funcion"): f["nombre"],
                           _("exp_que_hace"): f["descripcion"],
                           _("exp_categoria"): f["categoria_txt"]}
                          for f in e["funciones"]],
                         width="stretch", hide_index=True)
        for falta in e["faltantes"]:
            st.error(falta)


# ==========================================================================
# 🔧 Transformar
# ==========================================================================
with tab_transformar:
    st.subheader(_("tr_titulo"))
    cargado = st.session_state.cargado
    cat = cat_actual()
    if not cargado or not cargado.get("modelo"):
        st.info(_("tr_necesito_completo"))
    elif gate("transformar"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{_('tr_renombrar')}**")
            nombres = [m["nombre"] for m in cat.medidas()]
            if nombres:
                actual = st.selectbox(_("tr_medida"), nombres, key="ren_sel")
                nuevo_nombre = st.text_input(_("tr_nuevo_nombre"),
                                             key="ren_txt")
                if nuevo_nombre and st.button(_("tr_btn_renombrar")):
                    try:
                        nuevo, cambios = transformador.renombrar_medida(
                            cargado["modelo"], actual, nuevo_nombre,
                            idioma=IDIOMA)
                        aplicar_modelo(nuevo, cambios)
                        _flash(" · ".join(cambios))
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            st.markdown(f"**{_('tr_tabla_medidas')}**")
            if st.button(_("tr_btn_concentrar")):
                nuevo, cambios = transformador.crear_tabla_medidas(
                    cargado["modelo"], idioma=IDIOMA)
                aplicar_modelo(nuevo, cambios)
                _flash(" · ".join(cambios) or _("nada_que_mover"))
                st.rerun()
        with c2:
            st.markdown(f"**{_('tr_col_calculada')}**")
            tablas_visibles = [tb["nombre"] for tb in cat.tablas
                               if not tb["interna"]]
            t_sel = st.selectbox(_("tr_tabla"), tablas_visibles, key="cc_tabla")
            cc_nombre = st.text_input(_("tr_nombre_col"), key="cc_nom")
            cc_dax = st.text_area(_("exp_expresion"), key="cc_dax", height=90,
                                  placeholder="Ventas[Importe] - Ventas[Costo]")
            if cc_nombre and cc_dax and st.button(_("tr_btn_agregar_col")):
                try:
                    nuevo, cambios = asistente.agregar_columna_calculada(
                        cargado["modelo"], t_sel, cc_nombre, cc_dax)
                    aplicar_modelo(nuevo, cambios)
                    _flash(" · ".join(cambios))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.markdown(f"**{_('tr_formatos')}**")
            if st.button(_("tr_btn_formatos")):
                nuevo, c_1 = transformador.asignar_formatos(
                    cargado["modelo"], idioma=IDIOMA)
                nuevo, c_2 = transformador.ocultar_claves(nuevo, idioma=IDIOMA)
                aplicar_modelo(nuevo, c_1 + c_2)
                _flash(f"{len(c_1) + len(c_2)} {_('cambios_aplicados')}")
                st.rerun()


# ==========================================================================
# 📊 Exportar
# ==========================================================================
with tab_exportar:
    st.subheader(_("ex_titulo"))
    cargado = st.session_state.cargado
    cat = cat_actual()
    if not cargado or not cargado.get("modelo"):
        st.info(_("tr_necesito_completo"))
    elif gate("exportar"):
        nombre_out = st.text_input(_("ex_nombre"),
                                   value=(cat.nombre or "MV_DAX_Lab"))
        medidas_disp = [m["nombre"] for m in cat.medidas()]
        sel = st.multiselect(_("ex_medidas"), medidas_disp, max_selections=5)
        usar_tablero = st.checkbox(_("ex_generar_tablero"), value=True)
        conservar = st.checkbox(_("ex_conservar"), value=not usar_tablero)

        layout = None
        if usar_tablero and medidas_disp:
            try:
                layout = tablero.disenar_auto(cat, sel or None,
                                              titulo=nombre_out)
            except ValueError as exc:
                st.warning(str(exc))
        if layout is None and conservar:
            layout = cargado.get("layout")

        c1, c2 = st.columns(2)
        with c1:
            if st.button(_("ex_btn_pbit"), type="primary"):
                tmp = Path(tempfile.mkdtemp(prefix="dxl_out_"))
                ruta = modmod.exportar_pbit(
                    cargado["modelo"], layout, tmp / f"{nombre_out}.pbit",
                    descripcion=f"Generado por {MARCA}",
                    # Las consultas de Power Query del archivo original: sin
                    # esto el modelo exportado queda sin origen de datos.
                    datamashup=cargado.get("datamashup"))
                st.download_button(f"{_('ex_descargar')} {ruta.name}",
                                   ruta.read_bytes(), file_name=ruta.name)
                st.caption(_("ex_nota_pbit"))
        with c2:
            if st.button(_("ex_btn_pbip")):
                tmp = Path(tempfile.mkdtemp(prefix="dxl_out_"))
                modmod.exportar_pbip(cargado["modelo"], layout, tmp,
                                     nombre_out)
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in tmp.rglob("*"):
                        if f.is_file():
                            z.write(f, f.relative_to(tmp))
                st.download_button(f"{_('ex_descargar')} {nombre_out}_pbip.zip",
                                   buf.getvalue(),
                                   file_name=f"{nombre_out}_pbip.zip")
                st.caption(_("ex_nota_pbip"))


# ==========================================================================
# 🟪 Fabric
# ==========================================================================
with tab_fabric:
    st.subheader(_("fab_titulo"))
    cargado = st.session_state.cargado
    st.markdown(fabric.GUIA_GIT)
    if cargado and cargado.get("modelo") and gate("fabric"):
        token = st.text_input(_("fab_token"), type="password")
        if token:
            try:
                ws = fabric.listar_workspaces(token)
                if ws:
                    elegido = st.selectbox(
                        _("fab_workspace"), ws,
                        format_func=lambda w: w["nombre"] or w["id"])
                    nombre_fab = st.text_input(
                        _("fab_nombre_item"),
                        value=cat_actual().nombre or "MV_DAX_Lab")
                    if st.button(_("fab_btn"), type="primary"):
                        with st.spinner(_("fab_publicando")):
                            r = fabric.publicar(
                                elegido["id"], nombre_fab, cargado["modelo"],
                                cargado.get("layout"), token)
                        st.success(f"✅ {r['modelo_semantico']}"
                                   + (f" · {r['reporte']}" if r["reporte"]
                                      else ""))
            except Exception as exc:
                st.error(f"{_('fab_error')}: {exc}")
    st.caption(_("fab_mcp_nota"))


# ==========================================================================
# 🖥️ Asistente de pantalla
# ==========================================================================
with tab_overlay:
    st.subheader(_("ov_titulo"))
    st.markdown(f"""
| {_('ov_atajo')} | {_('ov_que_hace')} |
|---|---|
| **F9** | {_('ov_f9')} |
| **Shift + F9** | {_('ov_shift_f9')} |
| **Ctrl + F9** | {_('ov_ctrl_f9')} |
| Ctrl+Shift+M | {_('ov_limpiar_mem')} |

```bash
pip install anthropic pynput pillow
python daxlingo/overlay/DAX_Overlay.py
```

{_('ov_explica')}
""")
    if gate("overlay"):
        consulta_directa = st.text_area(_("ov_escribir"), height=80,
                                        placeholder=_("ov_placeholder"))
        if consulta_directa and st.button(_("ov_btn_resolver")):
            prov = st.session_state.proveedor
            if not proveedores_ia.hay_clave(prov, st.session_state.api_key):
                st.error(_("sin_clave_opinion"))
            else:
                with st.spinner(_("consultando")):
                    try:
                        cat = cat_actual()
                        contexto = (generador._catalogo_para_prompt(cat)
                                    if cat else "")
                        respuesta = ia.resolver_consulta(
                            consulta_directa, contexto, proveedor=prov,
                            modelo=st.session_state.modelo_ia,
                            api_key=st.session_state.api_key,
                            endpoint=st.session_state.endpoint)
                        asistente.depositar(consulta_directa, respuesta,
                                            origen="consulta")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    st.markdown("---")
    st.markdown(f"**{_('ov_bandeja')}**")
    items = asistente.pendientes()
    if not items:
        st.caption(_("ov_vacia"))
    for item in reversed(items[-10:]):
        estado_icono = {"pendiente": "🟡", "aplicado": "✅",
                        "descartado": "⚪"}.get(item["estado"], "🟡")
        with st.expander(f"{estado_icono} {item['cuando']} · "
                         f"{item['pregunta'][:70]}"):
            st.markdown(item["respuesta"])
            aplicables = [a for a in item.get("acciones", [])
                          if a["tipo"] in ("medida", "columna_calculada")]
            if aplicables and st.session_state.cargado \
                    and st.session_state.cargado.get("modelo") \
                    and item["estado"] == "pendiente":
                cat = cat_actual()
                tablas_visibles = [tb["nombre"] for tb in cat.tablas
                                   if not tb["interna"]]
                for i, a in enumerate(aplicables):
                    st.code(f"{a['nombre']} = {a['dax']}", language="sql")
                    t_destino = ""
                    if a["tipo"] == "columna_calculada":
                        t_destino = st.selectbox(
                            _("ov_tabla_destino"), tablas_visibles,
                            key=f"bd_{item['id']}_{i}")
                    if st.button(f"{_('ov_aplicar')} «{a['nombre']}»",
                                 key=f"ap_{item['id']}_{i}"):
                        try:
                            nuevo, cambios = asistente.aplicar_accion(
                                st.session_state.cargado["modelo"], a,
                                tabla=t_destino)
                            aplicar_modelo(nuevo, cambios)
                            asistente.marcar(item["_archivo"], "aplicado")
                            _flash(" · ".join(cambios))
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
            if item["estado"] == "pendiente" and \
                    st.button(_("ov_descartar"), key=f"de_{item['id']}"):
                asistente.marcar(item["_archivo"], "descartado")
                st.rerun()
    if items and st.button(_("ov_limpiar")):
        asistente.limpiar()
        st.rerun()


# ==========================================================================
# 🎓 Academia DAX
# ==========================================================================
with tab_academia:
    st.subheader(_("ac_titulo"))
    banco = ejercicios.cargar_ejercicios()
    xp = st.session_state.xp
    c1, c2, c3 = st.columns(3)
    c1.metric("XP", xp)
    c2.metric(_("ac_nivel"), ejercicios.nivel_por_xp(xp))
    prox = ejercicios.proximo_nivel(xp)
    c3.metric(_("ac_proximo"),
              f"{_('ac_faltan')} {prox[1]} XP" if prox else _("ac_maximo"))

    datos_banco = json.loads(
        ejercicios.RUTA_EJERCICIOS.read_text(encoding="utf-8"))
    with st.expander(_("ac_modelo_practica")):
        mp = datos_banco["modelo_practica"]
        for tbl, cols in mp["tablas"].items():
            st.markdown(f"**{tbl}**: {', '.join(cols)}")
        st.markdown(f"**{_('relaciones')}:** " + " · ".join(mp["relaciones"]))

    for nivel in sorted({e["nivel"] for e in banco}):
        st.markdown(f"### {_('ac_nivel')} {nivel}")
        for e in [x for x in banco if x["nivel"] == nivel]:
            hecho = e["id"] in st.session_state.resueltos
            with st.expander(("✅ " if hecho else "▫️ ")
                             + f"{e['id']} · {e['titulo']} (+{e['xp']} XP)"):
                st.markdown(e["enunciado"])
                respuesta = st.text_area(_("ac_tu_dax"), key=f"ej_{e['id']}",
                                         height=80)
                cols = st.columns([0.2, 0.2, 0.6])
                if cols[0].button(_("ac_verificar"), key=f"v_{e['id']}"):
                    v = ejercicios.verificar(e, respuesta)
                    if v["correcto"]:
                        if not hecho:
                            st.session_state.xp += e["xp"]
                            st.session_state.resueltos.add(e["id"])
                        _flash(v["detalle"])
                        st.rerun()
                    else:
                        st.error(v["detalle"])
                if cols[1].button(_("ac_pista"), key=f"p_{e['id']}"):
                    st.info(e.get("pista", _("ac_sin_pista")))


# ==========================================================================
# 🛠️ Herramientas
# ==========================================================================
with tab_tools:
    st.subheader(_("he_titulo"))
    cat = cat_actual()

    # Íconos de línea, uno por herramienta. Se dibujan con el mismo trazo y el
    # ámbar de la marca, así la grilla se lee como un sistema y no como una
    # bolsa de emojis — que además cambian de forma en cada sistema operativo.
    _ICONOS = {
        "desktop": "<rect x='3' y='4' width='18' height='13' rx='2'/>"
                   "<path d='M8 21h8M12 17v4'/>",
        "powerquery": "<path d='M4 7h16M4 12h10M4 17h6'/>"
                      "<path d='M17 14l3 3-3 3'/>",
        "service": "<circle cx='12' cy='12' r='9'/>"
                   "<path d='M3 12h18M12 3a15 15 0 010 18a15 15 0 010-18'/>",
        "bravo": "<path d='M12 3l2.6 5.6 6.4.9-4.6 4.4 1.1 6.1L12 17l-5.5 3 "
                 "1.1-6.1L3 9.5l6.4-.9z'/>",
        "daxstudio": "<path d='M4 6l5 6-5 6M12 18h8'/>",
        "tabulareditor": "<rect x='3' y='4' width='18' height='16' rx='2'/>"
                         "<path d='M3 9h18M9 9v11'/>",
        "almtoolkit": "<path d='M7 4v10M17 10v10'/>"
                      "<circle cx='7' cy='17' r='3'/><circle cx='17' cy='7' r='3'/>",
        "vscode": "<path d='M8 6l-5 6 5 6M16 6l5 6-5 6'/>",
        "fabric": "<path d='M12 3l8 4.5v9L12 21l-8-4.5v-9z'/>"
                  "<path d='M12 12l8-4.5M12 12v9M12 12L4 7.5'/>",
        "mcp": "<circle cx='12' cy='12' r='3'/>"
               "<path d='M12 3v4M12 17v4M3 12h4M17 12h4'/>",
    }
    # Cada nivel de estado con su clase y su etiqueta. Reemplaza el semáforo
    # de dos posiciones, que mentía en seis de las diez herramientas.
    _NIVELES = {
        "instalada": ("dxl-h-si", "he_instalada"),
        "falta": ("dxl-h-no", "he_falta"),
        "web": ("dxl-h-info", "he_web"),
        "incluida": ("dxl-h-si", "he_incluida"),
        "lista": ("dxl-h-info", "he_lista"),
        "sin_soporte": ("", "he_sin_soporte"),
    }

    _estados = herramientas.estados()
    _disponibles = sum(1 for e in _estados.values()
                       if e["nivel"] in ("instalada", "incluida", "web", "lista"))
    st.caption(_("he_resumen").format(n=_disponibles, total=len(_estados)))

    for etapa in ("01 · Crear", "02 · Operar", "03 · Modelar",
                  "04 · Industrializar", "05 · Escalar con IA"):
        grupo = [h for h in herramientas.HERRAMIENTAS if h["etapa"] == etapa]
        # OJO: no usar `_` como descarte acá — es la función de traducción de
        # todo el módulo, y pisarla rompe cada llamada posterior de la pestaña.
        _num, _sep, _tit = etapa.partition(" · ")
        st.markdown(
            f"<div class='dxl-etapa'><span class='dxl-etapa-n'>{_num}</span>"
            f"<span class='dxl-etapa-t'>{_tit}</span>"
            f"<span class='dxl-etapa-l'></span></div>",
            unsafe_allow_html=True)
        cols = st.columns(len(grupo))
        for col, h in zip(cols, grupo):
            with col:
                e = _estados[h["clave"]]
                clase, clave_txt = _NIVELES[e["nivel"]]
                ico = _ICONOS.get(h["clave"], "<circle cx='12' cy='12' r='8'/>")
                # La ruta detectada va en el title: sirve para confirmar cuál
                # de dos instalaciones encontró, sin ensuciar la tarjeta.
                titulo = f" title='{e['detalle']}'" if e.get("detalle") else ""
                st.markdown(
                    f"<div class='dxl-h'>"
                    f"<div class='dxl-h-top'>"
                    f"<span class='dxl-h-ico'><svg viewBox='0 0 24 24'>{ico}</svg></span>"
                    f"<span class='dxl-h-nom'>{h['nombre']}</span></div>"
                    f"<p class='dxl-h-desc'>{h['descripcion']}</p>"
                    f"<span class='dxl-h-pill {clase}'{titulo}>"
                    f"<span class='dxl-h-pt'></span>{_(clave_txt)}</span>"
                    f"<a class='dxl-h-link' href='{h['url']}' target='_blank'>"
                    f"{_('he_abrir')} →</a>"
                    f"<div class='dxl-h-int'>{h['integracion']}</div>"
                    f"</div>",
                    unsafe_allow_html=True)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**{_('he_para_daxstudio')}**")
        if cat and cat.medidas():
            st.download_button(f"{_('he_descargar')} · medidas.dax",
                               herramientas.texto_medidas_dax(cat),
                               file_name="medidas.dax")
        else:
            st.caption(_("he_carga_medidas"))
    with c2:
        st.markdown(f"**{_('he_para_tabular')}**")
        cargado = st.session_state.cargado
        if cargado and cargado.get("modelo"):
            st.download_button(
                f"{_('he_descargar')} · model.bim",
                json.dumps(cargado["modelo"], indent=2, ensure_ascii=False),
                file_name="model.bim")
        else:
            st.caption(_("tr_necesito_completo"))
    with c3:
        st.markdown(f"**{_('he_para_mcp')}**")
        agente = st.selectbox(
            "Agente", list(proveedores_ia.AGENTES_MCP),
            format_func=lambda a: proveedores_ia.AGENTES_MCP[a]["nombre"],
            key="mcp_agente_tools")
        archivo = proveedores_ia.AGENTES_MCP[agente]["archivo"]
        st.download_button(f"{_('he_descargar')} · {archivo}",
                           proveedores_ia.config_mcp_texto(agente, "."),
                           file_name=Path(archivo).name)
        st.caption(_("he_mcp_nota"))


# ==========================================================================
# 🔑 Licencia
# ==========================================================================
with tab_lic:
    st.subheader(_("lic_titulo"))
    c1, c2, c3 = st.columns(3)
    c1.metric(_("lic_edicion"), _("edicion_" + ESTADO_LIC.edicion))
    c2.metric(_("lic_estado"),
              _("lic_activa") if ESTADO_LIC.activa else _("lic_vencida"))
    c3.metric(_("lic_dias"),
              ESTADO_LIC.dias_restantes if ESTADO_LIC.dias_restantes
              is not None else "∞")

    if ESTADO_LIC.motivo == "owner":
        st.markdown(f"<div class='dxl-caja dxl-ok'>👑 {_('lic_owner')}</div>",
                    unsafe_allow_html=True)
    elif ESTADO_LIC.motivo == "demo":
        st.markdown(f"<div class='dxl-caja'>🕒 {_('lic_demo_activa')}</div>",
                    unsafe_allow_html=True)
    elif ESTADO_LIC.motivo == "vencida":
        st.markdown(f"<div class='dxl-caja dxl-mal'>🔒 "
                    f"{_('lic_demo_vencida')}</div>", unsafe_allow_html=True)
    else:
        email = ESTADO_LIC.payload.get("email") or "—"
        es_mensual = ESTADO_LIC.payload.get("plan") == "mensual"
        st.markdown(f"<div class='dxl-caja dxl-ok'>✅ "
                    f"{_('lic_activa')} · {email}</div>",
                    unsafe_allow_html=True)
        st.caption(_("lic_mensual") if es_mensual else _("lic_perpetua"))
        if es_mensual:
            # El enlace lleva el id de la suscripción, así que renovar es
            # abrirlo y copiar: no hay que buscar el correo de la compra.
            sub = ESTADO_LIC.payload.get("sub", "")
            url = sitio("/descarga.html") + (
                f"?preapproval_id={sub}" if sub else "")
            if (ESTADO_LIC.dias_restantes or 99) <= 7:
                st.warning(_("lic_por_vencer"))
            st.link_button(f"🔄 {_('lic_renovar')}", url)

    clave = st.text_input(_("lic_pegar"), type="password")
    col_a, col_b = st.columns(2)
    if clave and col_a.button(_("lic_activar"), type="primary"):
        try:
            lic.activar(clave)
            _flash(_("lic_activada"))
            st.rerun()
        except ValueError:
            st.error(_("lic_invalida"))
    col_b.link_button(f"🛒 {_('lic_comprar')}", sitio("/#precios"))


# ==========================================================================
# ⚙️ Configuración
# ==========================================================================
with tab_config:
    st.subheader(_("cfg_titulo"))
    st.markdown(f"**{_('cfg_ia')}**")

    claves_prov = list(proveedores_ia.PROVEEDORES)
    prov = st.selectbox(
        _("cfg_proveedor"), claves_prov,
        index=claves_prov.index(st.session_state.proveedor),
        format_func=lambda p: proveedores_ia.PROVEEDORES[p]["nombre"])
    if prov != st.session_state.proveedor:
        st.session_state.proveedor = prov
        st.session_state.modelo_ia = proveedores_ia.modelo_defecto(prov)
        lic.guardar_preferencia("proveedor", prov)
        st.rerun()

    modelos = proveedores_ia.modelos_de(prov)
    if modelos:
        ids = [m for m, _lbl in modelos]
        indice = ids.index(st.session_state.modelo_ia) \
            if st.session_state.modelo_ia in ids else 0
        elegido = st.selectbox(_("cfg_modelo"), ids, index=indice,
                               format_func=lambda m: dict(modelos)[m])
        if elegido != st.session_state.modelo_ia:
            st.session_state.modelo_ia = elegido
            lic.guardar_preferencia("modelo_ia", elegido)

    cfg_prov = proveedores_ia.PROVEEDORES[prov]
    if proveedores_ia.necesita_clave(prov):
        st.session_state.api_key = st.text_input(
            _("cfg_clave"), value=st.session_state.api_key, type="password",
            help=f"{cfg_prov['env']} · {cfg_prov['doc']}")
    if cfg_prov.get("necesita_endpoint"):
        st.session_state.endpoint = st.text_input(
            "Endpoint (https://<recurso>.openai.azure.com)",
            value=st.session_state.endpoint)

    if st.button(_("cfg_probar")):
        with st.spinner(_("consultando")):
            try:
                proveedores_ia.probar_conexion(
                    prov, st.session_state.modelo_ia,
                    st.session_state.api_key, st.session_state.endpoint)
                st.success(f"✅ {_('cfg_ok')}")
            except Exception as exc:
                st.error(str(exc))
    st.caption(_("cfg_nota_ia"))

    st.markdown("---")
    st.markdown(f"**{_('cfg_mcp')}**")
    agente_cfg = st.selectbox(
        "Agente", list(proveedores_ia.AGENTES_MCP),
        format_func=lambda a: proveedores_ia.AGENTES_MCP[a]["nombre"],
        key="mcp_agente_config")
    info_agente = proveedores_ia.AGENTES_MCP[agente_cfg]
    st.code(proveedores_ia.config_mcp_texto(agente_cfg, "."), language="json")
    st.caption(f"📄 `{info_agente['archivo']}` · {_('cfg_mcp_nota')}")

    st.markdown("---")
    st.markdown(f"**{_('cfg_bandeja')}:** `{asistente.carpeta_bandeja()}`")
    if st.session_state.historial:
        st.markdown(f"**{_('cfg_historial')}**")
        for c in st.session_state.historial:
            st.markdown(f"- {c}")
