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

from dxl import LEMA, MARCA, __version__, sitio  # noqa: E402
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
    gap:2px; border-bottom:1px solid #1d3149;
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
        st.rerun()

    icono = {"owner": "👑", "licencia": "✅", "demo": "🕒",
             "vencida": "🔒"}[ESTADO_LIC.motivo]
    st.markdown(f"**{_('lic_edicion')}:** {icono} `{ESTADO_LIC.edicion}`")
    if ESTADO_LIC.motivo == "demo":
        st.caption(f"{_('lic_dias')}: **{ESTADO_LIC.dias_restantes}**")
    elif ESTADO_LIC.motivo == "vencida":
        st.caption("🔒 " + _("lic_vencida"))
    st.caption(f"v{__version__}")


# ==========================================================================
# Header
# ==========================================================================
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
                            use_container_width=True, hide_index=True)
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
        st.graphviz_chart("\n".join(lineas), use_container_width=True)
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
            with st.expander(f"{icono} {g['regla']}{sufijo}"):
                st.markdown(f"**{_('por_que_importa')}:** {g['detalle']}")
                st.markdown(f"**{_('como_se_arregla')}:** {g['arreglo']}")
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
                    st.session_state.cargado["modelo"], hallazgos)
                aplicar_modelo(nuevo, cambios)
                st.success(f"{len(cambios)} {_('cambios_aplicados')}")
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
                            descripcion=r["explicacion"])
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
        e = explicador.explicar(expresion, cat, nombre)
        st.markdown(f"<div class='dxl-caja'><b>{e['resumen']}</b> · "
                    f"{_('exp_nivel')} {e['nivel']}</div>",
                    unsafe_allow_html=True)
        for paso in e["pasos"]:
            st.markdown(f"- {paso}")
        if e["funciones"]:
            st.dataframe([{_("exp_funcion"): f["nombre"],
                           _("exp_que_hace"): f["descripcion"],
                           _("exp_categoria"): f["categoria"]}
                          for f in e["funciones"]],
                         use_container_width=True, hide_index=True)
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
                            cargado["modelo"], actual, nuevo_nombre)
                        aplicar_modelo(nuevo, cambios)
                        st.success(" · ".join(cambios))
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            st.markdown(f"**{_('tr_tabla_medidas')}**")
            if st.button(_("tr_btn_concentrar")):
                nuevo, cambios = transformador.crear_tabla_medidas(
                    cargado["modelo"])
                aplicar_modelo(nuevo, cambios)
                st.success(" · ".join(cambios) or _("nada_que_mover"))
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
                    st.success(" · ".join(cambios))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.markdown(f"**{_('tr_formatos')}**")
            if st.button(_("tr_btn_formatos")):
                nuevo, c_1 = transformador.asignar_formatos(cargado["modelo"])
                nuevo, c_2 = transformador.ocultar_claves(nuevo)
                aplicar_modelo(nuevo, c_1 + c_2)
                st.success(f"{len(c_1) + len(c_2)} {_('cambios_aplicados')}")
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
                    descripcion=f"Generado por {MARCA}")
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
                            st.success(" · ".join(cambios))
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
                        st.success(v["detalle"])
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
    for etapa in ("01 · Crear", "02 · Operar", "03 · Modelar",
                  "04 · Industrializar", "05 · Escalar con IA"):
        grupo = [h for h in herramientas.HERRAMIENTAS if h["etapa"] == etapa]
        st.markdown(f"#### {etapa}")
        cols = st.columns(len(grupo))
        for col, h in zip(cols, grupo):
            with col:
                ruta = herramientas.detectar(h)
                estado_txt = (f"🟢 {_('he_detectada')}" if ruta
                              else f"⚪ {_('he_no_detectada')}")
                st.markdown(f"**{h['nombre']}**  \n{h['descripcion']}  \n"
                            f"{estado_txt}  \n[{_('he_sitio')}]({h['url']})")
                st.caption(h["integracion"])

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**{_('he_para_daxstudio')}**")
        if cat and cat.medidas():
            tmp = Path(tempfile.mkdtemp(prefix="dxl_dax_"))
            ruta = herramientas.exportar_medidas_dax(cat, tmp / "medidas.dax")
            st.download_button("⬇️ medidas.dax", ruta.read_text("utf-8"),
                               file_name="medidas.dax")
        else:
            st.caption(_("he_carga_medidas"))
    with c2:
        st.markdown(f"**{_('he_para_tabular')}**")
        cargado = st.session_state.cargado
        if cargado and cargado.get("modelo"):
            st.download_button(
                "⬇️ model.bim",
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
        st.download_button(f"⬇️ {archivo}",
                           proveedores_ia.config_mcp_texto(agente, "."),
                           file_name=Path(archivo).name)
        st.caption(_("he_mcp_nota"))


# ==========================================================================
# 🔑 Licencia
# ==========================================================================
with tab_lic:
    st.subheader(_("lic_titulo"))
    c1, c2, c3 = st.columns(3)
    c1.metric(_("lic_edicion"), ESTADO_LIC.edicion)
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
            st.success(_("lic_activada"))
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
