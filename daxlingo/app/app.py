"""
MV DAX Lab · Dashboard principal (Streamlit).

Una sola app con todo el ciclo: cargar un modelo de Power BI (.pbit / PBIP /
.bim / .pbix), entenderlo (catálogo, relaciones), auditarlo (analizador de
buenas prácticas), mejorarlo (transformaciones y NL→DAX con anti-alucinación),
practicar (Academia DAX gamificada) y exportarlo de vuelta a .pbit/PBIP con
tablero, filtros y navegación — o publicarlo en Fabric.

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

from dxl import LEMA, MARCA, __version__  # noqa: E402
from dxl import analizador, asistente, catalogo, ejercicios  # noqa: E402
from dxl import explicador, fabric, generador, herramientas, ia  # noqa: E402
from dxl import modelo as modmod  # noqa: E402
from dxl import tablero, transformador  # noqa: E402

# ==========================================================================
# Página y estilo (design system Kobra: navy + ámbar)
# ==========================================================================
NAVY, NAVY2, AMBAR, TINTA, APAGADO = ("#081527", "#0c2137", "#f2b441",
                                      "#eaf1fb", "#9db0c8")

st.set_page_config(page_title=f"{MARCA} · DAX + Power BI + Fabric",
                   page_icon="🟨", layout="wide")

st.markdown(f"""<style>
.stApp {{ background: linear-gradient(180deg,{NAVY} 0%,#0a1a30 100%); }}
section[data-testid="stSidebar"] {{ background:{NAVY2}; }}
[data-testid="stMetric"] {{ background:{NAVY2}; border:1px solid #1d3149;
    border-radius:14px; padding:14px 16px;
    box-shadow:0 2px 10px rgba(0,0,0,.35); }}
[data-testid="stMetricValue"] {{ color:{AMBAR}; font-weight:700; }}
[data-testid="stMetricLabel"] {{ color:{APAGADO}; }}
h1,h2,h3 {{ color:{TINTA}; }}
.dxl-badge {{ background:{AMBAR}; color:#1c1305; border-radius:20px;
    padding:2px 12px; font-weight:700; font-size:0.8rem; }}
.dxl-caja {{ background:{NAVY2}; border-left:4px solid {AMBAR};
    border-radius:8px; padding:12px 16px; margin:8px 0; color:{TINTA}; }}
.dxl-ok {{ border-left-color:#00c896; }}
.dxl-mal {{ border-left-color:#c1443c; }}
code {{ color:{AMBAR}; }}
.stTabs [data-baseweb="tab"] {{ color:{APAGADO}; }}
.stTabs [aria-selected="true"] {{ color:{AMBAR}; }}
</style>""", unsafe_allow_html=True)


# ==========================================================================
# Estado
# ==========================================================================
def _estado(clave, defecto):
    if clave not in st.session_state:
        st.session_state[clave] = defecto
    return st.session_state[clave]


_estado("cargado", None)          # dict de modelo.cargar()
_estado("historial", [])          # log de cambios aplicados
_estado("xp", 0)
_estado("resueltos", set())
_estado("api_key", "")
_estado("modelo_ia", ia.MODELO_DEFECTO)


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


# ==========================================================================
# Header
# ==========================================================================
izq, der = st.columns([0.65, 0.35])
with izq:
    st.markdown(f"# 🟨 {MARCA} <span class='dxl-badge'>DAX · Power BI · "
                f"Fabric</span>", unsafe_allow_html=True)
    st.caption(f"{LEMA} · v{__version__}")
with der:
    cargado = st.session_state.cargado
    cat = cat_actual()
    if cat:
        r = cat.resumen()
        c1, c2, c3 = st.columns(3)
        c1.metric("Tablas", r["tablas"])
        c2.metric("Medidas", r["medidas"])
        c3.metric("Relaciones", r["relaciones"])
    else:
        st.markdown("<div class='dxl-caja'>Sin modelo cargado — empezá por "
                    "la pestaña <b>📥 Modelo</b>.</div>",
                    unsafe_allow_html=True)

(tab_guia, tab_modelo, tab_rel, tab_analisis, tab_generar, tab_explicar,
 tab_transformar, tab_exportar, tab_fabric, tab_overlay, tab_academia,
 tab_tools, tab_config) = st.tabs([
     "❓ Guía", "📥 Modelo", "🕸️ Relaciones", "🩺 Analizador",
     "🤖 Generar DAX", "📖 Explicador", "🔧 Transformar", "📊 Exportar",
     "🟪 Fabric", "🖥️ Asistente de pantalla", "🎓 Academia DAX",
     "🛠️ Herramientas", "⚙️ Configuración"])


# ==========================================================================
# ❓ Guía
# ==========================================================================
with tab_guia:
    st.subheader("El ciclo completo, verificable")
    st.markdown("""
**inspeccionar → modelar → construir → validar → verificar → exportar**

1. **📥 Modelo** — cargá un `.pbit`, un proyecto **PBIP**, un `model.bim` o
   un `.pbix` (de un `.pbix` se lee el reporte y un catálogo parcial; el
   modelo tabular viaja en un binario propietario — la app te dice cómo
   obtener el completo).
2. **🕸️ Relaciones** — el modelo dibujado: tablas, cardinalidades, calendario.
3. **🩺 Analizador** — reglas de buenas prácticas con severidad y arreglo;
   las automáticas se aplican con un clic.
4. **🤖 Generar DAX** — pedile medidas en español («% del total por país»,
   «ventas vs año anterior»). Sin API key usa el motor de reglas local;
   con tu clave de Anthropic, pedidos libres con Claude. En ambos casos la
   expresión se **valida contra el catálogo**: nada que no exista.
5. **🔧 Transformar** — renombrar con propagación, columnas calculadas,
   tabla de medidas, formatos.
6. **📊 Exportar** — de vuelta a `.pbit` (doble clic en Desktop → guardar
   como `.pbix`) o **PBIP** (Git), con **tablero automático**: KPIs,
   evolución, barras, dona, matriz y slicers.
7. **🟪 Fabric** — publicación directa por API (token BYOK) o vía
   integración Git del PBIP.
8. **🖥️ Asistente de pantalla** — el DAX Overlay captura lo que estás
   mirando (F9 / Shift+F9 / Ctrl+F9), Claude lo explica paso a paso y las
   medidas propuestas se aplican acá con un clic.
9. **🎓 Academia DAX** — practicá con ejercicios por nivel, XP y verificación
   local instantánea.
""")
    st.info("La demo carga el modelo Adium de este mismo repo (117 medidas "
            "reales) desde la pestaña **📥 Modelo** sin subir nada.")


# ==========================================================================
# 📥 Modelo
# ==========================================================================
with tab_modelo:
    st.subheader("Cargar un modelo")
    col_a, col_b = st.columns([0.55, 0.45])
    with col_a:
        subida = st.file_uploader(
            "Arrastrá un .pbit, .pbix, model.bim o un PBIP comprimido (.zip)",
            type=["pbit", "pbix", "bim", "json", "zip"])
        if subida is not None and st.button("Cargar archivo", type="primary"):
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
                st.error(f"No se pudo cargar: {exc}")
    with col_b:
        st.markdown("**Modelo demo (Adium · 117 medidas)**")
        demo = RAIZ.parent / "powerbi" / "archivos" / \
            "Adium_VAR.SemanticModel" / "model.bim"
        if demo.exists() and st.button("Cargar el modelo demo"):
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
            st.markdown(f"<div class='dxl-caja dxl-ok'>Cargado "
                        f"(<b>{cargado['formato']}</b>): {r['tablas']} "
                        f"tablas · {r['columnas']} columnas · "
                        f"{r['medidas']} medidas · {r['relaciones']} "
                        f"relaciones{' · catálogo PARCIAL' if r['parcial'] else ''}"
                        "</div>", unsafe_allow_html=True)
            for t in cat.tablas:
                if t["interna"]:
                    continue
                with st.expander(f"📋 {t['nombre']} — "
                                 f"{len(t['columnas'])} col · "
                                 f"{len(t['medidas'])} medidas"):
                    if t["columnas"]:
                        st.dataframe(
                            [{"Columna": c["nombre"], "Tipo": c["tipo"],
                              "Oculta": "sí" if c["oculta"] else "",
                              "Calculada": "sí" if c["calculada"] else ""}
                             for c in t["columnas"]],
                            use_container_width=True, hide_index=True)
                    for m in t["medidas"]:
                        st.markdown(f"**[{m['nombre']}]** "
                                    f"`{m['formato'] or 'sin formato'}`")
                        st.code(m["expresion"], language="sql")
        if st.session_state.historial:
            st.markdown("**Cambios aplicados en esta sesión:**")
            for c in st.session_state.historial:
                st.markdown(f"- {c}")


# ==========================================================================
# 🕸️ Relaciones
# ==========================================================================
with tab_rel:
    st.subheader("Mapa del modelo")
    cat = cat_actual()
    if not cat:
        st.info("Cargá un modelo primero.")
    elif not cat.relaciones:
        st.warning("El modelo no declara relaciones (o el catálogo es "
                   "parcial).")
    else:
        lineas = ["digraph modelo {",
                  '  rankdir=LR; bgcolor="transparent";',
                  '  node [shape=box, style="rounded,filled", '
                  f'fillcolor="{NAVY2}", fontcolor="{TINTA}", '
                  f'color="{AMBAR}", fontname="Helvetica"];',
                  f'  edge [color="{APAGADO}", fontcolor="{APAGADO}", '
                  'fontsize=10];']
        fechas = (cat.tabla_fechas() or {}).get("nombre")
        for t in cat.tablas:
            if t["interna"]:
                continue
            extra = ' fillcolor="#1d3149"' if t["nombre"] == fechas else ""
            lineas.append(f'  "{t["nombre"]}" [label="{t["nombre"]}\\n'
                          f'{len(t["columnas"])} col · '
                          f'{len(t["medidas"])} med"{extra}];')
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
        st.caption("Flechas: lado muchos → lado uno. Rojo doble = "
                   "bidireccional (revisar). Punteada = inactiva. "
                   "Fondo claro = tabla de calendario.")


# ==========================================================================
# 🩺 Analizador
# ==========================================================================
with tab_analisis:
    st.subheader("Buenas prácticas del modelo")
    cat = cat_actual()
    if not cat:
        st.info("Cargá un modelo primero.")
    else:
        hallazgos = analizador.analizar(cat)
        salud = analizador.puntaje(hallazgos)
        c1, c2, c3 = st.columns(3)
        c1.metric("Salud del modelo", f"{salud}/100")
        c2.metric("Hallazgos", len(hallazgos))
        c3.metric("Arreglables en 1 clic",
                  sum(1 for h in hallazgos if h["auto"]))
        for h in hallazgos:
            icono = {"alta": "🔴", "media": "🟡", "baja": "🔵"}[h["severidad"]]
            with st.expander(f"{icono} {h['regla']} — {h['objeto']}"):
                st.markdown(f"**Por qué importa:** {h['detalle']}")
                st.markdown(f"**Cómo se arregla:** {h['arreglo']}")
                if h["auto"]:
                    st.markdown("✅ *Arreglable automáticamente*")
        if any(h["auto"] for h in hallazgos) and \
                st.session_state.cargado.get("modelo"):
            if st.button("🔧 Aplicar todos los arreglos automáticos",
                         type="primary"):
                nuevo, cambios = transformador.aplicar_arreglos(
                    st.session_state.cargado["modelo"], hallazgos)
                aplicar_modelo(nuevo, cambios)
                st.success(f"{len(cambios)} cambio(s) aplicados.")
                st.rerun()

        if ia.hay_clave(st.session_state.api_key):
            if st.button("🧠 Opinión de Claude sobre este modelo"):
                with st.spinner("Consultando a Claude…"):
                    try:
                        st.markdown(ia.analizar_modelo_ia(
                            generador._catalogo_para_prompt(cat), hallazgos,
                            modelo=st.session_state.modelo_ia,
                            api_key=st.session_state.api_key))
                    except Exception as exc:
                        st.error(str(exc))
        else:
            st.caption("Con una API key de Anthropic (⚙️ Configuración) "
                       "también tenés la opinión de Claude sobre el modelo.")


# ==========================================================================
# 🤖 Generar DAX
# ==========================================================================
with tab_generar:
    st.subheader("De español a DAX, sin inventar columnas")
    cat = cat_actual()
    if not cat:
        st.info("Cargá un modelo primero.")
    else:
        pedido = st.text_input(
            "¿Qué medida necesitás?",
            placeholder="p. ej.: total de ventas · % del total · ventas vs "
                        "año anterior · media móvil 3 meses de unidades · "
                        "ranking de país por ventas")
        if pedido:
            r = generador.generar(pedido, cat,
                                  api_key=st.session_state.api_key or None,
                                  modelo_ia=st.session_state.modelo_ia)
            if r["ok"]:
                st.markdown(f"<div class='dxl-caja dxl-ok'><b>[{r['nombre']}]"
                            f"</b> · formato <code>{r['formato']}</code> · "
                            f"motor: {r['metodo']}</div>",
                            unsafe_allow_html=True)
                st.code(r["dax"], language="sql")
                st.markdown(f"**Por qué:** {r['explicacion']}")
                if st.session_state.cargado.get("modelo") and \
                        st.button("➕ Agregar esta medida al modelo"):
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
    st.subheader("Pegá DAX, salí entendiéndolo")
    cat = cat_actual()
    opciones = ["(pegar una expresión)"]
    medidas_cat = cat.medidas() if cat else []
    opciones += [f"[{m['nombre']}]" for m in medidas_cat]
    eleccion = st.selectbox("Explicar una medida del modelo o pegar DAX",
                            opciones)
    if eleccion != opciones[0]:
        m = medidas_cat[opciones.index(eleccion) - 1]
        expresion, nombre = m["expresion"], m["nombre"]
        st.code(expresion, language="sql")
    else:
        nombre = ""
        expresion = st.text_area("Expresión DAX", height=140,
                                 placeholder="CALCULATE ( SUM ( … ) )")
    if expresion.strip():
        e = explicador.explicar(expresion, cat, nombre)
        st.markdown(f"<div class='dxl-caja'><b>{e['resumen']}</b> · nivel "
                    f"{e['nivel']}</div>", unsafe_allow_html=True)
        for paso in e["pasos"]:
            st.markdown(f"- {paso}")
        if e["funciones"]:
            st.dataframe([{"Función": f["nombre"],
                           "Qué hace": f["descripcion"],
                           "Categoría": f["categoria"]}
                          for f in e["funciones"]],
                         use_container_width=True, hide_index=True)
        for falta in e["faltantes"]:
            st.error(falta)


# ==========================================================================
# 🔧 Transformar
# ==========================================================================
with tab_transformar:
    st.subheader("Transformaciones seguras (siempre sobre una copia)")
    cargado = st.session_state.cargado
    cat = cat_actual()
    if not cargado or not cargado.get("modelo"):
        st.info("Necesito el modelo completo (.pbit / PBIP / .bim).")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Renombrar medida (propaga referencias)**")
            nombres = [m["nombre"] for m in cat.medidas()]
            if nombres:
                actual = st.selectbox("Medida", nombres, key="ren_sel")
                nuevo_nombre = st.text_input("Nuevo nombre", key="ren_txt")
                if nuevo_nombre and st.button("Renombrar"):
                    try:
                        nuevo, cambios = transformador.renombrar_medida(
                            cargado["modelo"], actual, nuevo_nombre)
                        aplicar_modelo(nuevo, cambios)
                        st.success(" · ".join(cambios))
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            st.markdown("**Crear tabla de medidas**")
            if st.button("Concentrar todas las medidas en «_Medidas»"):
                nuevo, cambios = transformador.crear_tabla_medidas(
                    cargado["modelo"])
                aplicar_modelo(nuevo, cambios)
                st.success(" · ".join(cambios) or "Nada que mover.")
                st.rerun()
        with c2:
            st.markdown("**Columna calculada**")
            tablas_visibles = [t["nombre"] for t in cat.tablas
                               if not t["interna"]]
            t_sel = st.selectbox("Tabla", tablas_visibles, key="cc_tabla")
            cc_nombre = st.text_input("Nombre de la columna", key="cc_nom")
            cc_dax = st.text_area("Expresión DAX", key="cc_dax", height=90,
                                  placeholder="Ventas[Importe] - Ventas[Costo]")
            if cc_nombre and cc_dax and st.button("Agregar columna"):
                try:
                    nuevo, cambios = asistente.agregar_columna_calculada(
                        cargado["modelo"], t_sel, cc_nombre, cc_dax)
                    aplicar_modelo(nuevo, cambios)
                    st.success(" · ".join(cambios))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.markdown("**Formatos y claves**")
            if st.button("Asignar formatos faltantes + ocultar claves"):
                nuevo, c_1 = transformador.asignar_formatos(cargado["modelo"])
                nuevo, c_2 = transformador.ocultar_claves(nuevo)
                aplicar_modelo(nuevo, c_1 + c_2)
                st.success(f"{len(c_1) + len(c_2)} cambio(s).")
                st.rerun()


# ==========================================================================
# 📊 Exportar
# ==========================================================================
with tab_exportar:
    st.subheader("Exportar con tablero, filtros y navegación")
    cargado = st.session_state.cargado
    cat = cat_actual()
    if not cargado or not cargado.get("modelo"):
        st.info("Necesito el modelo completo (.pbit / PBIP / .bim).")
    else:
        nombre_out = st.text_input("Nombre del archivo",
                                   value=(cat.nombre or "MV_DAX_Lab"))
        medidas_disp = [m["nombre"] for m in cat.medidas()]
        sel = st.multiselect(
            "Medidas para el tablero automático (hasta 5; vacío = primeras 5)",
            medidas_disp, max_selections=5)
        usar_tablero = st.checkbox(
            "Generar tablero automático (KPIs + evolución + barras + dona + "
            "matriz + slicers)", value=True)
        conservar = st.checkbox(
            "Conservar el reporte original si el archivo traía uno",
            value=not usar_tablero)

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
            if st.button("⬇️ Generar .pbit", type="primary"):
                tmp = Path(tempfile.mkdtemp(prefix="dxl_out_"))
                ruta = modmod.exportar_pbit(
                    cargado["modelo"], layout, tmp / f"{nombre_out}.pbit",
                    descripcion=f"Generado por {MARCA}")
                st.download_button("Descargar " + ruta.name,
                                   ruta.read_bytes(), file_name=ruta.name)
                st.caption("Doble clic → Power BI Desktop → Archivo → "
                           "Guardar como → .pbix")
        with c2:
            if st.button("⬇️ Generar PBIP (zip)"):
                tmp = Path(tempfile.mkdtemp(prefix="dxl_out_"))
                modmod.exportar_pbip(cargado["modelo"], layout, tmp,
                                     nombre_out)
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in tmp.rglob("*"):
                        if f.is_file():
                            z.write(f, f.relative_to(tmp))
                st.download_button(f"Descargar {nombre_out}_pbip.zip",
                                   buf.getvalue(),
                                   file_name=f"{nombre_out}_pbip.zip")
                st.caption("Formato de control de versiones — y el que "
                           "entiende la integración Git de Fabric.")


# ==========================================================================
# 🟪 Fabric
# ==========================================================================
with tab_fabric:
    st.subheader("Publicar en Microsoft Fabric")
    cargado = st.session_state.cargado
    st.markdown(fabric.GUIA_GIT)
    if cargado and cargado.get("modelo"):
        token = st.text_input("Token de Fabric (no se guarda)",
                              type="password")
        if token:
            try:
                ws = fabric.listar_workspaces(token)
                if ws:
                    elegido = st.selectbox(
                        "Workspace", ws,
                        format_func=lambda w: w["nombre"] or w["id"])
                    nombre_fab = st.text_input("Nombre del ítem",
                                               value=cat_actual().nombre
                                               or "MV_DAX_Lab")
                    if st.button("🚀 Publicar en Fabric", type="primary"):
                        with st.spinner("Publicando…"):
                            r = fabric.publicar(
                                elegido["id"], nombre_fab,
                                cargado["modelo"], cargado.get("layout"),
                                token)
                        st.success(f"Modelo semántico: "
                                   f"{r['modelo_semantico']}"
                                   + (f" · Reporte: {r['reporte']}"
                                      if r["reporte"] else ""))
            except Exception as exc:
                st.error(f"Fabric respondió con error: {exc}")
    st.caption("El MCP remoto oficial de Power BI "
               f"({herramientas.MCP_REMOTO_POWERBI}) también trabaja sobre "
               "modelos ya publicados — configuralo desde 🛠️ Herramientas.")


# ==========================================================================
# 🖥️ Asistente de pantalla (DAX Overlay)
# ==========================================================================
with tab_overlay:
    st.subheader("DAX Overlay: capturá la pantalla, aplicá el resultado acá")
    st.markdown("""
El overlay corre en tu escritorio (Windows/Mac/Linux con interfaz gráfica):

| Atajo | Qué hace |
|---|---|
| **F9** | Captura **toda la pantalla** y la resuelve con Claude |
| **Shift + F9** | Seleccionás un **rectángulo** con el mouse |
| **Ctrl + F9** | Abre una ventana para **escribir la consulta** |
| Ctrl+Shift+M | Limpia la memoria de capturas previas |

```bash
pip install anthropic pynput pillow
python daxlingo/overlay/DAX_Overlay.py
```

Cada respuesta se explica **paso a paso** en la ventana flotante y queda en
la **bandeja** de abajo: si trae medidas o columnas calculadas, se aplican
al modelo cargado con un clic — y de ahí a Exportar o Fabric.
""")
    consulta_directa = st.text_area(
        "…o escribí la consulta acá mismo (sin overlay)", height=80,
        placeholder="p. ej.: necesito el margen % por categoría con "
                    "semáforo, ¿qué medidas armo?")
    if consulta_directa and st.button("Resolver con Claude"):
        if not ia.hay_clave(st.session_state.api_key):
            st.error("Configurá tu API key en ⚙️ Configuración.")
        else:
            with st.spinner("Consultando…"):
                try:
                    cat = cat_actual()
                    contexto = ("Catálogo del modelo:\n"
                                + generador._catalogo_para_prompt(cat)
                                if cat else "")
                    respuesta = ia.consultar(
                        [{"role": "user",
                          "content": f"{contexto}\n\n{consulta_directa}"}],
                        sistema=ia.SISTEMA_DAX,
                        modelo=st.session_state.modelo_ia,
                        api_key=st.session_state.api_key)
                    asistente.depositar(consulta_directa, respuesta,
                                        origen="consulta")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    st.markdown("---")
    st.markdown("**📬 Bandeja del overlay**")
    items = asistente.pendientes()
    if not items:
        st.caption("Sin resultados todavía. Usá el overlay o la consulta de "
                   "arriba.")
    for item in reversed(items[-10:]):
        estado_icono = {"pendiente": "🟡", "aplicado": "✅",
                        "descartado": "⚪"}.get(item["estado"], "🟡")
        with st.expander(f"{estado_icono} {item['cuando']} · "
                         f"{item['pregunta'][:70]}"):
            st.markdown(item["respuesta"])
            acciones = item.get("acciones", [])
            aplicables = [a for a in acciones
                          if a["tipo"] in ("medida", "columna_calculada")]
            if aplicables and st.session_state.cargado \
                    and st.session_state.cargado.get("modelo") \
                    and item["estado"] == "pendiente":
                cat = cat_actual()
                tablas_visibles = [t["nombre"] for t in cat.tablas
                                   if not t["interna"]]
                for i, a in enumerate(aplicables):
                    st.code(f"{a['nombre']} = {a['dax']}", language="sql")
                    t_destino = ""
                    if a["tipo"] == "columna_calculada":
                        t_destino = st.selectbox(
                            "Tabla destino", tablas_visibles,
                            key=f"bd_{item['id']}_{i}")
                    if st.button(f"➕ Aplicar «{a['nombre']}»",
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
                    st.button("Descartar", key=f"de_{item['id']}"):
                asistente.marcar(item["_archivo"], "descartado")
                st.rerun()
    if items and st.button("🧹 Limpiar resueltos"):
        asistente.limpiar()
        st.rerun()


# ==========================================================================
# 🎓 Academia DAX
# ==========================================================================
with tab_academia:
    st.subheader("Academia DAX — práctica con verificación instantánea")
    banco = ejercicios.cargar_ejercicios()
    xp = st.session_state.xp
    c1, c2, c3 = st.columns(3)
    c1.metric("XP", xp)
    c2.metric("Nivel", ejercicios.nivel_por_xp(xp))
    prox = ejercicios.proximo_nivel(xp)
    c3.metric("Próximo nivel", f"faltan {prox[1]} XP" if prox else "¡máximo!")

    datos_banco = json.loads(
        ejercicios.RUTA_EJERCICIOS.read_text(encoding="utf-8"))
    with st.expander("📋 El modelo de práctica (común a todos los ejercicios)"):
        mp = datos_banco["modelo_practica"]
        for tbl, cols in mp["tablas"].items():
            st.markdown(f"**{tbl}**: {', '.join(cols)}")
        st.markdown("**Relaciones:** " + " · ".join(mp["relaciones"]))

    for nivel in sorted({e["nivel"] for e in banco}):
        st.markdown(f"### Nivel {nivel}")
        for e in [x for x in banco if x["nivel"] == nivel]:
            hecho = e["id"] in st.session_state.resueltos
            with st.expander(("✅ " if hecho else "▫️ ")
                             + f"{e['id']} · {e['titulo']} (+{e['xp']} XP)"):
                st.markdown(e["enunciado"])
                respuesta = st.text_area("Tu DAX", key=f"ej_{e['id']}",
                                         height=80)
                cols = st.columns([0.2, 0.2, 0.6])
                if cols[0].button("Verificar", key=f"v_{e['id']}"):
                    v = ejercicios.verificar(e, respuesta)
                    if v["correcto"]:
                        if not hecho:
                            st.session_state.xp += e["xp"]
                            st.session_state.resueltos.add(e["id"])
                        st.success(v["detalle"])
                        st.rerun()
                    else:
                        st.error(v["detalle"])
                if cols[1].button("Pista", key=f"p_{e['id']}"):
                    st.info(e.get("pista", "Sin pista para este."))


# ==========================================================================
# 🛠️ Herramientas
# ==========================================================================
with tab_tools:
    st.subheader("El stack del analista Power BI moderno, operativo")
    cat = cat_actual()
    for etapa in ("01 · Crear", "02 · Operar", "03 · Modelar",
                  "04 · Industrializar", "05 · Escalar con IA"):
        grupo = [h for h in herramientas.HERRAMIENTAS if h["etapa"] == etapa]
        st.markdown(f"#### {etapa}")
        cols = st.columns(len(grupo))
        for col, h in zip(cols, grupo):
            with col:
                ruta = herramientas.detectar(h)
                estado_txt = (f"🟢 detectada" if ruta
                              else "⚪ no detectada acá")
                st.markdown(f"**{h['nombre']}**  \n{h['descripcion']}  \n"
                            f"{estado_txt}  \n[sitio]({h['url']})")
                st.caption(h["integracion"])

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Para DAX Studio**")
        if cat and cat.medidas():
            tmp = Path(tempfile.mkdtemp(prefix="dxl_dax_"))
            ruta = herramientas.exportar_medidas_dax(cat, tmp / "medidas.dax")
            st.download_button("⬇️ medidas.dax", ruta.read_text("utf-8"),
                               file_name="medidas.dax")
        else:
            st.caption("Cargá un modelo con medidas.")
    with c2:
        st.markdown("**Para Tabular Editor / ALM Toolkit**")
        cargado = st.session_state.cargado
        if cargado and cargado.get("modelo"):
            st.download_button(
                "⬇️ model.bim",
                json.dumps(cargado["modelo"], indent=2, ensure_ascii=False),
                file_name="model.bim")
        else:
            st.caption("Cargá el modelo completo.")
    with c3:
        st.markdown("**Para agentes de IA (MCP)**")
        st.download_button("⬇️ .mcp.json",
                           herramientas.config_mcp_texto("."),
                           file_name=".mcp.json")
        st.caption("Incluye el MCP remoto oficial de Power BI, el MCP local "
                   "de modelado y el servidor MCP de esta plataforma.")


# ==========================================================================
# ⚙️ Configuración
# ==========================================================================
with tab_config:
    st.subheader("Configuración")
    st.markdown("**IA (Claude) — opcional y BYOK**")
    st.session_state.api_key = st.text_input(
        "ANTHROPIC_API_KEY (solo esta sesión; no se guarda en disco)",
        value=st.session_state.api_key, type="password")
    st.session_state.modelo_ia = st.selectbox(
        "Modelo de Claude", [m for m, _ in ia.MODELOS_CLAUDE],
        index=[m for m, _ in ia.MODELOS_CLAUDE].index(
            st.session_state.modelo_ia),
        format_func=lambda m: dict(ia.MODELOS_CLAUDE)[m])
    st.caption("Si el modelo elegido está saturado, se cae solo al "
               "siguiente de la lista, con reintentos (3s, 6s). Sin clave, "
               "todo lo demás funciona igual: motor de reglas, analizador, "
               "explicador, export.")
    st.markdown("---")
    st.markdown(f"**Bandeja del overlay:** `{asistente.carpeta_bandeja()}`  \n"
                "Cambiala con la variable de entorno `MVDAXLAB_BANDEJA`.")
    if st.session_state.historial:
        st.markdown("**Historial de cambios de la sesión:**")
        for c in st.session_state.historial:
            st.markdown(f"- {c}")
