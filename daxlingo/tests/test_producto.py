# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Tests del producto: i18n trilingüe, licencias y ediciones,
proveedores de IA, landing y video.

Lo del motor (modelo, catálogo, analizador, generador…) vive en
`test_daxlingo.py`. Acá va todo lo que hace que esto sea un producto
vendible y no una librería: que no haya textos sin traducir, que una
licencia falsa no pase, que la demo venza a los 7 días, y que la web y el
video existan de verdad en los tres idiomas.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dxl import i18n, licencia, proveedores_ia  # noqa: E402

WEB = RAIZ / "web"


# ==========================================================================
# i18n del programa
# ==========================================================================
def test_paridad_trilingue_programa():
    """Ninguna clave puede quedar sin sus tres idiomas."""
    assert i18n.faltantes() == {}, \
        f"Claves incompletas: {i18n.faltantes()}"


def test_t_cae_a_espanol_sin_romper():
    assert i18n.t("tab_modelo", "en") == "📥 Model"
    assert i18n.t("clave_que_no_existe", "es") == "clave_que_no_existe"


def test_las_pestanas_no_se_repiten_en_ningun_idioma():
    """Streamlit selecciona pestañas por etiqueta: dos iguales se pisan."""
    claves = [k for k in i18n.T if k.startswith("tab_")]
    for idioma in i18n.IDIOMAS:
        etiquetas = [i18n.t(k, idioma) for k in claves]
        assert len(etiquetas) == len(set(etiquetas)), \
            f"Pestañas duplicadas en «{idioma}»"


def test_sin_markdown_en_los_textos_que_van_a_html():
    """
    Estos textos se inyectan dentro de un <div>: los asteriscos de markdown
    saldrían literales en pantalla (nos pasó una vez, de ahí el test).
    """
    for clave in ("sin_modelo", "lic_bloqueado", "lic_owner",
                  "lic_demo_activa", "lic_demo_vencida"):
        for idioma in i18n.IDIOMAS:
            assert "**" not in i18n.t(clave, idioma), \
                f"{clave}/{idioma} lleva markdown y se renderiza como HTML"


# ==========================================================================
# Licencias
# ==========================================================================
SECRETO = "secreto-de-prueba-para-los-tests"


def test_firma_y_verificacion():
    payload = {"plan": "profesional", "equipos": 1, "pid": "1", "iat": 10}
    clave = licencia.firmar(payload, SECRETO)
    assert clave.startswith("MVDAX1.")
    assert licencia.verificar(clave, SECRETO) == payload


def test_licencia_falsa_no_pasa():
    clave = licencia.firmar({"plan": "profesional"}, SECRETO)
    assert licencia.verificar(clave, "otro-secreto") is None
    # payload cambiado, firma vieja
    pre, cuerpo, firma = clave.split(".")
    falso = licencia._b64u(json.dumps({"plan": "corporativo"}).encode())
    assert licencia.verificar(f"{pre}.{falso}.{firma}", SECRETO) is None
    for basura in ["", "cualquiera", "KOBRA1.a.b", "MVDAX1.solo.dos.partes",
                   None, 42]:
        assert licencia.verificar(basura, SECRETO) is None


def test_licencia_vencida_no_pasa():
    vieja = licencia.firmar({"plan": "profesional", "exp": 1000}, SECRETO)
    assert licencia.verificar(vieja, SECRETO) is None
    futura = licencia.firmar(
        {"plan": "profesional", "exp": time.time() + 3600}, SECRETO)
    assert licencia.verificar(futura, SECRETO)["plan"] == "profesional"


def test_misma_licencia_en_python_y_en_javascript(tmp_path):
    """
    La emite Node (api/verificar-pago.js) y la valida Python (la app). Si las
    dos implementaciones se separan, el cliente paga y la clave no le anda.
    """
    guion = tmp_path / "firmar.js"
    guion.write_text(
        f"const {{firmar}} = require({str(RAIZ / 'api' / '_licencia.js')!r});\n"
        "process.stdout.write(firmar("
        '{"plan":"profesional","equipos":1,"pid":"42","iat":1730000000}, '
        f"{SECRETO!r}));\n", encoding="utf-8")
    salida = subprocess.run([_node(), str(guion)], capture_output=True,
                            text=True, check=True).stdout.strip()

    payload = licencia.verificar(salida, SECRETO)
    assert payload is not None, "Python rechazó una licencia emitida por Node"
    assert payload["plan"] == "profesional"
    # …y al revés: la que firma Python tiene que ser byte a byte la misma.
    assert licencia.firmar(payload, SECRETO) == salida


def _node() -> str:
    from shutil import which
    node = which("node")
    if not node:
        pytest.skip("node no está disponible")
    return node


# ==========================================================================
# Ediciones y prueba de 7 días
# ==========================================================================
@pytest.fixture()
def datos(tmp_path, monkeypatch):
    monkeypatch.setenv("MVDAXLAB_DATOS", str(tmp_path))
    monkeypatch.delenv("MVDAX_EDICION", raising=False)
    monkeypatch.setenv("MVDAX_LICENSE_SECRET", SECRETO)
    # `edicion.json` del repo es el de desarrollo (demo, sin bloquear).
    monkeypatch.setenv("MVDAXLAB_EDICION_ARCHIVO", str(tmp_path / "no-hay"))
    return tmp_path


def test_secreto_vacio_en_copia_sellada_no_cae_al_publico(datos, monkeypatch):
    """Un empaquetado corrido sin MVDAX_LICENSE_SECRET deja `secreto: ""` en
    el sello. Eso NO puede caer al secreto de desarrollo: es público (está
    en el código fuente), así que cualquiera firmaría una licencia válida
    contra todas las copias con ese mismo agujero — un keygen distribuible.
    """
    monkeypatch.delenv("MVDAX_LICENSE_SECRET", raising=False)
    archivo = datos / "edicion.json"
    archivo.write_text(json.dumps(
        {"edicion": "profesional", "bloqueada": True, "secreto": ""}),
        encoding="utf-8")
    monkeypatch.setenv("MVDAXLAB_EDICION_ARCHIVO", str(archivo))

    efectivo = licencia.secreto_licencia()
    assert efectivo != "mvdaxlab-secreto-de-desarrollo-cambiar-en-el-build", \
        "el secreto público de desarrollo sigue validando copias selladas rotas"

    forjada = licencia.firmar(
        {"plan": "perpetua"}, "mvdaxlab-secreto-de-desarrollo-cambiar-en-el-build")
    estado = licencia.evaluar(forjada)
    assert estado.motivo != "licencia", \
        f"una licencia firmada con el secreto público quedó válida: {estado}"


def test_demo_arranca_con_siete_dias(datos):
    estado = licencia.evaluar()
    assert estado.edicion == "demo"
    assert estado.activa
    assert estado.dias_restantes == licencia.DIAS_DEMO


def test_demo_vence_y_deja_lo_de_lectura_abierto(datos):
    # Se simula que el primer uso fue hace 8 días.
    licencia.guardar_estado({"demo_inicio": time.time() - 8 * 86400})
    estado = licencia.evaluar()
    assert not estado.activa
    assert estado.motivo == "vencida"
    # Lo que se cierra…
    for f in ("generar", "transformar", "exportar", "fabric", "overlay"):
        assert not estado.permite(f), f
    # …y lo que queda abierto para siempre.
    for f in ("analizar", "explicar", "academia", "cargar"):
        assert estado.permite(f), f


def test_una_licencia_valida_reabre_todo(datos):
    licencia.guardar_estado({"demo_inicio": time.time() - 30 * 86400})
    assert not licencia.evaluar().activa
    clave = licencia.firmar({"plan": "profesional", "equipos": 1}, SECRETO)
    estado = licencia.activar(clave)
    assert estado.activa and estado.motivo == "licencia"
    assert all(estado.permite(f) for f in licencia.FUNCIONES_CON_LICENCIA)


def test_activar_una_clave_inventada_falla(datos):
    with pytest.raises(ValueError):
        licencia.activar("MVDAX1.falsa.firma")
    assert licencia.leer_estado().get("licencia") is None


def test_edicion_owner_no_pide_nada(datos, monkeypatch):
    monkeypatch.setenv("MVDAX_EDICION", "owner")
    estado = licencia.evaluar()
    assert estado.edicion == "owner" and estado.activa
    assert estado.dias_restantes is None
    assert all(estado.permite(f) for f in licencia.FUNCIONES_CON_LICENCIA)


def test_edicion_bloqueada_ignora_la_variable_de_entorno(datos, monkeypatch):
    """
    Es el candado del negocio: si el cliente puede poner MVDAX_EDICION=owner
    en una copia comercial, se lleva el producto entero gratis.
    """
    archivo = datos / "edicion.json"
    archivo.write_text(json.dumps({"edicion": "profesional",
                                   "bloqueada": True}), encoding="utf-8")
    monkeypatch.setenv("MVDAXLAB_EDICION_ARCHIVO", str(archivo))
    monkeypatch.setenv("MVDAX_EDICION", "owner")
    assert licencia.edicion_actual() == "profesional"


def test_el_repo_no_publica_una_edicion_owner():
    """El edicion.json commiteado tiene que ser demo y sin secreto."""
    archivo = RAIZ / "desktop" / "edicion.json"
    datos_ed = json.loads(archivo.read_text(encoding="utf-8"))
    assert datos_ed["edicion"] == "demo"
    assert not datos_ed.get("secreto"), \
        "¡Hay un secreto de licencia commiteado en desktop/edicion.json!"


# ==========================================================================
# Proveedores de IA
# ==========================================================================
def test_proveedores_declarados_completos():
    esperados = {"claude", "openai", "gemini", "copilot", "groq", "mistral",
                 "deepseek", "ollama"}
    assert esperados <= set(proveedores_ia.PROVEEDORES)
    for clave, cfg in proveedores_ia.PROVEEDORES.items():
        assert cfg["nombre"] and cfg["doc"], clave
        assert cfg["modelos"], clave
        if not cfg.get("sin_clave"):
            assert cfg["env"], clave


def test_sin_clave_avisa_en_vez_de_reventar(monkeypatch):
    for cfg in proveedores_ia.PROVEEDORES.values():
        if cfg.get("env"):
            monkeypatch.delenv(cfg["env"], raising=False)
    with pytest.raises(RuntimeError, match="API key"):
        proveedores_ia.consultar([{"role": "user", "content": "hola"}],
                                 proveedor="claude")


def test_cada_proveedor_arma_su_peticion(monkeypatch):
    """Cada API tiene su forma; un header mal puesto es un 401 silencioso."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://demo.openai.azure.com")
    for prov in proveedores_ia.PROVEEDORES:
        modelo = proveedores_ia.modelo_defecto(prov)
        pedido = proveedores_ia._peticion(
            prov, modelo, [{"role": "user", "content": "hola"}],
            "sistema", "clave-de-prueba", 100)
        cuerpo = json.loads(pedido.data)
        if prov == "claude":
            assert pedido.headers["X-api-key"] == "clave-de-prueba"
            assert cuerpo["system"] == "sistema"
        elif prov == "gemini":
            assert "key=clave-de-prueba" in pedido.full_url
            assert cuerpo["contents"][0]["parts"][0]["text"] == "hola"
        elif prov == "copilot":
            assert pedido.headers["Api-key"] == "clave-de-prueba"
            assert "/openai/deployments/" in pedido.full_url
        elif prov == "ollama":
            assert cuerpo["stream"] is False
        else:
            assert pedido.headers["Authorization"] == "Bearer clave-de-prueba"
            assert cuerpo["messages"][0]["role"] == "system"


def test_lectura_de_respuesta_por_proveedor():
    casos = {
        "claude": ({"content": [{"text": "hola"}]}, "hola"),
        "openai": ({"choices": [{"message": {"content": "hola"}}]}, "hola"),
        "gemini": ({"candidates": [{"content": {"parts": [{"text": "hola"}]}}]},
                   "hola"),
        "ollama": ({"message": {"content": "hola"}}, "hola"),
    }
    for prov, (datos_resp, esperado) in casos.items():
        assert proveedores_ia._texto_respuesta(prov, datos_resp) == esperado
    # Una respuesta vacía no debe explotar.
    assert proveedores_ia._texto_respuesta("openai", {"choices": []}) == ""


def test_config_mcp_por_agente():
    for agente, info in proveedores_ia.AGENTES_MCP.items():
        cfg = proveedores_ia.config_mcp(agente, ".")
        servidores = cfg[info["clave"]]
        assert set(servidores) == {"powerbi-remote", "fabric-core",
                                   "powerbi-modeling", "mv-dax-lab"}
        assert servidores["powerbi-remote"]["url"] == \
            proveedores_ia.MCP_REMOTO_POWERBI
        assert servidores["fabric-core"]["url"] == \
            proveedores_ia.MCP_REMOTO_FABRIC
        json.dumps(cfg)  # tiene que ser serializable tal cual


# ==========================================================================
# Landing y video
# ==========================================================================
def _textos_web() -> dict:
    """
    Lee `window.TEXTOS` de i18n.js evaluándolo en Node. Se evalúa en vez de
    parsear con regex porque el archivo es JavaScript de verdad: cualquier
    parser casero se rompería con el primer texto que lleve una llave.
    `window` no existe en Node, así que se declara antes de evaluar.
    """
    guion = ("global.window = {};\n"
             "eval(require('fs').readFileSync(process.argv[1], 'utf8'));\n"
             "process.stdout.write(JSON.stringify(window.TEXTOS));")
    salida = subprocess.run(
        [_node(), "-e", guion, str(WEB / "assets" / "i18n.js")],
        capture_output=True, text=True, check=True)
    return json.loads(salida.stdout)


def test_paridad_trilingue_landing():
    textos = _textos_web()
    assert set(textos) == set(i18n.IDIOMAS)
    base = set(textos["es"])
    for idioma in ("en", "pt"):
        faltan = base - set(textos[idioma])
        sobran = set(textos[idioma]) - base
        assert not faltan, f"Faltan en «{idioma}»: {sorted(faltan)}"
        assert not sobran, f"Sobran en «{idioma}»: {sorted(sobran)}"
        vacios = [k for k, v in textos[idioma].items() if not str(v).strip()]
        assert not vacios, f"Vacíos en «{idioma}»: {vacios}"


def test_el_html_no_referencia_claves_inexistentes():
    textos = _textos_web()
    html = (WEB / "index.html").read_text(encoding="utf-8")
    usadas = set(re.findall(r'data-i(?:-alt)?="([^"]+)"', html))
    faltan = usadas - set(textos["es"])
    assert not faltan, f"El HTML usa claves que no existen: {sorted(faltan)}"


def test_capturas_en_los_tres_idiomas():
    """La landing arma las rutas como assets/img/<idioma>/<slug>.png."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    slugs = set(re.findall(r'data-shot="([^"]+)"', html))
    assert len(slugs) >= 12, "La galería debería mostrar casi todas las pestañas"
    for idioma in i18n.IDIOMAS:
        for slug in slugs:
            imagen = WEB / "assets" / "img" / idioma / f"{slug}.png"
            assert imagen.exists(), f"Falta la captura {idioma}/{slug}.png"
            assert imagen.stat().st_size > 10_000, f"{imagen} parece vacía"


def test_video_en_los_tres_idiomas():
    for idioma in i18n.IDIOMAS:
        video = WEB / "assets" / "video" / f"demo-{idioma}.mp4"
        assert video.exists(), f"Falta el video demo-{idioma}.mp4"
        # Un MP4 real empieza con un box 'ftyp'.
        assert video.read_bytes()[4:8] == b"ftyp", f"{video} no es un MP4"
        assert video.stat().st_size > 500_000


def test_textos_del_video_trilingues():
    sys.path.insert(0, str(RAIZ / "media"))
    from build_video import GUION, VIDEO  # noqa: E402

    assert set(VIDEO) == set(i18n.IDIOMAS)
    claves_es = set(VIDEO["es"])
    for idioma in i18n.IDIOMAS:
        assert set(VIDEO[idioma]) == claves_es, f"«{idioma}» descuadrado"
        for clave, (titulo, bajada) in VIDEO[idioma].items():
            assert titulo.strip() and bajada.strip(), f"{idioma}/{clave}"
    for _slug, clave in GUION:
        assert clave in claves_es, f"El guion usa «{clave}», que no tiene texto"


def test_los_planes_de_la_web_coinciden_con_los_del_checkout():
    """Si la landing ofrece un plan que el checkout no conoce, se pierde la venta."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    planes_web = set(re.findall(r'data-plan="([^"]+)"', html))
    planes_js = (RAIZ / "api" / "_planes.js").read_text(encoding="utf-8")
    declarados = set(re.findall(r"^  (\w+): \{", planes_js, re.MULTILINE))
    assert planes_web <= declarados, \
        f"La web ofrece planes que el checkout no tiene: {planes_web - declarados}"
    assert planes_web, "La landing no tiene ningún botón de compra"


def test_un_solo_precio_dos_modalidades():
    """
    Un solo producto: las dos formas de pago desbloquean lo mismo. Si alguna
    vez alguien recorta una para empujar a la otra, este test lo frena.
    """
    planes = (RAIZ / "api" / "_planes.js").read_text(encoding="utf-8")
    claves = set(re.findall(r"^  (\w+): \{", planes, re.MULTILINE))
    assert claves == {"perpetua", "mensual"}
    assert re.search(r"perpetua:.*?usd: 99", planes, re.DOTALL)
    assert re.search(r"mensual:.*?usd: 10", planes, re.DOTALL)
    # Mismos equipos en las dos: ninguna es una versión recortada.
    equipos = re.findall(r"equipos: (\d+)", planes)
    assert len(set(equipos)) == 1, f"Las modalidades difieren en equipos: {equipos}"


def test_la_licencia_mensual_vence_y_la_perpetua_no():
    """
    El corte de la suscripción es el vencimiento de la clave. Si una mensual
    saliera sin `exp`, un mes pagado valdría para siempre.
    """
    perpetua = licencia.firmar({"plan": "perpetua", "equipos": 1}, SECRETO)
    assert licencia.verificar(perpetua, SECRETO) is not None

    ahora = time.time()
    vigente = licencia.firmar(
        {"plan": "mensual", "equipos": 1, "sub": "abc",
         "exp": ahora + 32 * 86400}, SECRETO)
    assert licencia.verificar(vigente, SECRETO)["plan"] == "mensual"

    vencida = licencia.firmar(
        {"plan": "mensual", "equipos": 1, "sub": "abc",
         "exp": ahora - 86400}, SECRETO)
    assert licencia.verificar(vencida, SECRETO) is None


def test_estado_de_una_suscripcion_vencida(datos):
    """Vencida la mensual, el programa vuelve al estado de demo agotada."""
    licencia.guardar_estado({
        "demo_inicio": time.time() - 60 * 86400,
        "licencia": licencia.firmar(
            {"plan": "mensual", "exp": time.time() - 86400}, SECRETO),
    })
    estado = licencia.evaluar()
    assert not estado.activa
    assert estado.motivo == "vencida"
    # Y lo de lectura sigue abierto, como con la demo.
    assert estado.permite("analizar") and estado.permite("academia")


def test_el_dominio_no_esta_clavado_en_el_codigo():
    """
    El sitio público sale de un solo lugar configurable (`dxl.SITIO` /
    `edicion.json`). Estuvo repetido en seis archivos apuntando a un dominio
    que ni siquiera existía todavía: cuando el deploy real tenga otro nombre,
    los botones de compra y de renovación tienen que seguirlo solos.
    """
    import dxl

    permitidos = {
        # El único default, y su espejo en Electron y en la config del build.
        RAIZ / "dxl" / "__init__.py",
        RAIZ / "desktop" / "main.cjs",
        RAIZ / "desktop" / "edicion.json",
        RAIZ / "web" / "descarga.html",   # texto de ayuda, no un enlace vivo
    }
    sospechosos = []
    for archivo in RAIZ.rglob("*"):
        if archivo.suffix not in (".py", ".js", ".jsx", ".cjs", ".html"):
            continue
        # Los tests usan hosts de mentira como dato de entrada: eso no es un
        # dominio clavado en el producto.
        # `dist*` cubre dist/, dist-instalador/ y dist-portable/: son COPIAS
        # del código que ya se revisa en su lugar de origen. La comparación
        # era exacta contra «dist» y por eso dist-portable/ colaba el default
        # de dxl/__init__.py como si fuera un dominio clavado nuevo.
        if archivo in permitidos or "node_modules" in archivo.parts \
                or any(p.startswith("dist") for p in archivo.parts) \
                or "tests" in archivo.parts \
                or archivo.name.endswith(".test.js"):
            continue
        if "vercel.app" in archivo.read_text(encoding="utf-8", errors="ignore"):
            sospechosos.append(str(archivo.relative_to(RAIZ)))
    assert not sospechosos, f"Dominio clavado en: {sospechosos}"

    assert dxl.sitio("/#precios").endswith("/#precios")
    assert "://" not in dxl.dominio()


def test_la_web_no_filtra_secretos():
    """Ni tokens de MercadoPago ni claves de IA en lo que se sirve al público."""
    sospechosos = re.compile(
        r"(APP_USR-[\w-]{10,}|sk-[A-Za-z0-9]{20,}|AIza[\w-]{20,})")
    for archivo in WEB.rglob("*"):
        if archivo.suffix.lower() in (".html", ".js", ".css", ".json"):
            texto = archivo.read_text(encoding="utf-8", errors="ignore")
            assert not sospechosos.search(texto), f"¡Secreto en {archivo}!"


# ==========================================================================
# Los ejemplos que el producto promete: tienen que andar sobre SU demo
# ==========================================================================
# El placeholder de la pestaña «Generar DAX» sugiere cinco pedidos, y la
# landing muestra uno de ellos resolviéndose en el hero. Dos no funcionaban
# contra el modelo demo que viene en la caja: el usuario abría el programa,
# copiaba el ejemplo sugerido y recibía «No encontré qué comparar». Un test
# que solo prueba el motor con un modelo de juguete no lo agarra — este corre
# los ejemplos reales contra el modelo real que se distribuye.
EJEMPLOS_DEL_PLACEHOLDER = [
    ("total de ventas", "[Ventas Brutas USD]"),
    ("% del total por país", "[Ventas Brutas USD]"),
    ("ventas vs año anterior", "SAMEPERIODLASTYEAR"),
    ("media móvil 3 meses de ventas", "DATESINPERIOD"),
    ("ranking de país por ventas", "RANKX"),
]


@pytest.fixture(scope="module")
def cat_demo():
    from dxl import catalogo, modelo as modmod
    ruta = RAIZ / "datos" / "demo" / "modelo_demo.bim"
    assert ruta.exists(), "el modelo demo tiene que viajar con el producto"
    return catalogo.Catalogo.desde_modelo(modmod.cargar(ruta)["modelo"])


@pytest.mark.parametrize("pedido,esperado", EJEMPLOS_DEL_PLACEHOLDER)
def test_los_ejemplos_sugeridos_funcionan_sobre_el_modelo_demo(
        cat_demo, pedido, esperado):
    from dxl import generador
    r = generador.generar(pedido, cat_demo)
    assert r["ok"], f"«{pedido}» falló: {r['advertencias']}"
    assert esperado in r["dax"], f"«{pedido}» → {r['dax']}"


def test_el_porcentaje_del_total_no_suma_un_ano_ni_un_id(cat_demo):
    """Sin objetivo explícito hay que caer en una medida del modelo, no en la
    primera columna numérica: esa suele ser el Año del calendario, y sumar
    años da un número enorme y perfectamente inútil."""
    from dxl import generador
    r = generador.generar("% del total", cat_demo)
    assert r["ok"]
    assert "[Año]" not in r["dax"] and "[Anio]" not in r["dax"], r["dax"]


def test_avisa_cuando_el_pedido_encajaba_en_varias_medidas(cat_demo):
    """«ventas» con Brutas y Netas en el modelo es ambiguo de verdad. Elegir
    en silencio es cómo se entrega un número que nadie revisa."""
    from dxl import generador
    r = generador.generar("ventas vs año anterior", cat_demo)
    assert r["ok"]
    assert "Ventas Netas USD" in r["explicacion"], r["explicacion"]


@pytest.mark.parametrize("pedido,esperado", [
    ("Ventas Brutas USD vs last year", "[Ventas Brutas USD]"),
    ("Unidades year to date", "TOTALYTD"),
    ("moving average 3 months Unidades", "DATESINPERIOD"),
    ("Unidades vs ano anterior", "SAMEPERIODLASTYEAR"),
    ("distinct Cliente", "DISTINCTCOUNT"),
    # «by» en vez de «por»: el conector inglés, no solo la palabra clave del
    # patrón, tiene que reconocerse — si no, «rank X by Y» le pasa Y pegado
    # a X como si fuera todo la dimensión, y termina rankeando una medida
    # contra sí misma.
    ("rank pais by ventas", "RANKX"),
    ("top 5 pais by ventas", "TOPN"),
])
def test_el_motor_de_reglas_tambien_entiende_ingles_y_portugues(
        cat_demo, pedido, esperado):
    """El producto se vende en tres idiomas: un usuario en inglés no puede
    recibir «no reconocí el patrón» con los ejemplos que la UI le sugiere."""
    from dxl import generador
    r = generador.generar(pedido, cat_demo)
    assert r["ok"], f"«{pedido}» falló: {r['advertencias']}"
    assert esperado in r["dax"], f"«{pedido}» → {r['dax']}"


def test_no_confunde_la_medida_nombrada_con_otra_parecida(cat_demo):
    """Nombrar la medida entera manda: si el pedido dice «Ventas Netas USD»,
    la variación tiene que ser de esa y no de la primera que se le parezca."""
    from dxl import generador
    r = generador.generar("Ventas Netas USD vs año anterior", cat_demo)
    assert r["ok"] and "[Ventas Netas USD]" in r["dax"], r["dax"]
    assert "[Ventas Brutas USD]" not in r["dax"], r["dax"]


# ==========================================================================
# El sello de edición dentro de una copia instalada
# ==========================================================================
def _copia_instalada(tmp_path, sello: dict | None):
    """Reproduce el árbol que deja electron-builder: resources/app/dxl/… y el
    sello donde el proceso Python pueda abrirlo de verdad."""
    import shutil
    res = tmp_path / "resources"
    destino = res / "app"
    shutil.copytree(RAIZ / "dxl", destino / "dxl",
                    ignore=shutil.ignore_patterns("__pycache__"))
    if sello is not None:
        (destino / "edicion.json").write_text(json.dumps(sello),
                                              encoding="utf-8")
    return destino


def _edicion_en(destino, tmp_path, **entorno) -> str:
    import subprocess
    guion = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(destino)!r})\n"
        f"os.environ['MVDAXLAB_DATOS'] = {str(tmp_path / 'datos')!r}\n"
        "from dxl import licencia as lic\n"
        "print(lic.edicion_actual())\n")
    r = subprocess.run([sys.executable, "-c", guion], capture_output=True,
                       text=True, env={**os.environ, **entorno})
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_una_copia_vendida_no_se_convierte_en_owner_con_una_variable(tmp_path):
    """El candado de la edición tiene que sobrevivir a MVDAX_EDICION=owner.

    Estuvo roto y no se notaba: `edicion.json` viajaba SOLO dentro de
    app.asar, que es un sistema de archivos virtual de Electron y el proceso
    Python no puede abrir. El motor caía al default («demo», sin bloquear) y
    entonces la variable de entorno mandaba: cualquiera que comprara la
    licencia profesional podía ponerse owner y llevarse el producto entero.
    """
    destino = _copia_instalada(
        tmp_path, {"edicion": "profesional", "bloqueada": True, "secreto": "s"})
    sello = destino / "edicion.json"
    assert sello.exists(), "el sello tiene que quedar donde Python lo lea"
    obtenida = _edicion_en(destino, tmp_path,
                           MVDAXLAB_EDICION_ARCHIVO=str(sello),
                           MVDAX_EDICION="owner")
    assert obtenida == "profesional", \
        f"una variable de entorno convirtió la copia vendida en {obtenida}"


def test_el_sello_empaquetado_manda_sobre_la_variable_de_entorno(tmp_path):
    """`MVDAXLAB_EDICION_ARCHIVO` es CÓMO `lanzador.py`/Electron le dicen al
    motor dónde está el sello empaquetado — no un permiso para que la
    variable apunte a un `edicion.json` cualquiera y se invente una edición.
    Si el sello empaquetado (`resources/app/edicion.json`) existe, tiene que
    ganar aunque la variable apunte a otro lado.
    """
    destino = _copia_instalada(
        tmp_path, {"edicion": "profesional", "bloqueada": True, "secreto": "s"})
    falso = tmp_path / "falso.json"
    falso.write_text(json.dumps({"edicion": "owner", "bloqueada": True}),
                     encoding="utf-8")
    obtenida = _edicion_en(destino, tmp_path, MVDAXLAB_EDICION_ARCHIVO=str(falso))
    assert obtenida == "profesional", \
        f"la variable de entorno apuntó a un sello falso y ganó: {obtenida}"


def test_el_secreto_de_licencia_tambien_esta_sellado(tmp_path):
    """El candado de la edición no alcanza si el SECRETO se puede pisar.

    `edicion_actual()` ya ignora `MVDAX_EDICION` en una copia sellada — pero
    `secreto_licencia()` seguía prefiriendo `MVDAX_LICENSE_SECRET` por
    encima del secreto horneado. Con eso alcanzaba `licencia.firmar()` +
    esa variable para fabricar una licencia «profesional» válida sobre
    cualquier copia DEMO vendida, sin tocar la edición para nada.
    """
    destino = _copia_instalada(
        tmp_path, {"edicion": "demo", "bloqueada": True,
                   "secreto": "secreto-real-del-build"})
    sello = destino / "edicion.json"
    import subprocess
    guion = (
        "import os, sys, json\n"
        f"sys.path.insert(0, {str(destino)!r})\n"
        f"os.environ['MVDAXLAB_DATOS'] = {str(tmp_path / 'datos')!r}\n"
        "from dxl import licencia as lic\n"
        "clave = lic.firmar({'plan': 'perpetua'}, os.environ['MVDAX_LICENSE_SECRET'])\n"
        "estado = lic.evaluar(clave)\n"
        "print(json.dumps({'secreto_usado': lic.secreto_licencia(),\n"
        "                  'edicion': estado.edicion, 'motivo': estado.motivo}))\n")
    r = subprocess.run(
        [sys.executable, "-c", guion], capture_output=True, text=True,
        env={**os.environ, "MVDAXLAB_EDICION_ARCHIVO": str(sello),
             "MVDAX_LICENSE_SECRET": "secreto-inventado-por-el-cliente"})
    assert r.returncode == 0, r.stderr
    resultado = json.loads(r.stdout.strip())
    assert resultado["secreto_usado"] == "secreto-real-del-build", \
        f"el secreto horneado se puede pisar con una variable: {resultado}"
    assert resultado["motivo"] != "licencia", \
        f"una licencia firmada con un secreto inventado se aceptó como válida: {resultado}"
    assert resultado["edicion"] != "profesional", \
        f"una licencia falsa convirtió la copia DEMO en profesional: {resultado}"


def test_el_empaquetado_lleva_el_sello_a_donde_python_lo_busca():
    """`extraResources` tiene que dejar edicion.json en resources/app/, que es
    `parents[1]` desde dxl/licencia.py. Si se saca, vuelve el agujero."""
    paquete = json.loads(
        (RAIZ / "desktop" / "package.json").read_text(encoding="utf-8"))
    destinos = [e.get("to") for e in paquete["build"]["extraResources"]
                if isinstance(e, dict)]
    assert "app/edicion.json" in destinos, \
        f"el sello no viaja a resources/app/: {destinos}"


def test_el_main_pasa_el_nombre_de_variable_que_el_motor_lee():
    """main.cjs exportaba MVDAX_EDICION_ARCHIVO y licencia.py lee
    MVDAXLAB_EDICION_ARCHIVO: la variable no la leía nadie."""
    main = (RAIZ / "desktop" / "main.cjs").read_text(encoding="utf-8")
    assert "MVDAXLAB_EDICION_ARCHIVO" in main
    assert "MVDAX_EDICION_ARCHIVO:" not in main, \
        "quedó el nombre viejo, que el motor ignora"


def test_lanzador_fija_mvdax_edicion_igual_que_electron(tmp_path, monkeypatch):
    """`entorno()` tiene que fijar MVDAX_EDICION a propósito, como ya hace
    `desktop/main.cjs` — no dejar pasar lo que sea que traiga el entorno del
    usuario cuando falta el sello (una carpeta portable incompleta)."""
    import lanzador

    monkeypatch.setattr(lanzador, "RAIZ", tmp_path)
    monkeypatch.setenv("MVDAX_EDICION", "owner")  # lo que el atacante puso

    # Sin sello: no hay que confiar en la variable ambiente.
    env = lanzador.entorno()
    assert env["MVDAX_EDICION"] == "demo", \
        f"sin sello, ganó la variable de entorno: {env['MVDAX_EDICION']}"
    assert "MVDAXLAB_EDICION_ARCHIVO" not in env

    # Con sello: la edición horneada manda, tanto en MVDAX_EDICION como en
    # dónde le dice a licencia.py que busque el sello real.
    (tmp_path / "edicion.json").write_text(
        json.dumps({"edicion": "profesional", "bloqueada": True,
                   "secreto": "s"}), encoding="utf-8")
    env = lanzador.entorno()
    assert env["MVDAX_EDICION"] == "profesional"
    assert env["MVDAXLAB_EDICION_ARCHIVO"] == str(tmp_path / "edicion.json")


def test_lanzador_guarda_la_salida_de_streamlit_para_diagnosticar(tmp_path,
                                                                   monkeypatch):
    """El portable no tiene consola de desarrollador: si Streamlit falla al
    arrancar, `cola_log()` tiene que devolver lo que dijo — antes se tiraba
    a DEVNULL y `MV_DAX_Lab.bat` prometía «el detalle está arriba» sin que
    hubiera ningún detalle."""
    import lanzador

    monkeypatch.setattr(lanzador, "RAIZ", tmp_path)
    monkeypatch.setenv("MVDAXLAB_DATOS", str(tmp_path / "datos"))
    assert lanzador.cola_log() == "", "sin log todavía, tiene que devolver vacío"

    lanzador.archivo_log().parent.mkdir(parents=True, exist_ok=True)
    lanzador.archivo_log().write_text(
        "ModuleNotFoundError: No module named 'streamlit'\n", encoding="utf-8")
    assert "ModuleNotFoundError" in lanzador.cola_log()


def test_el_audio_se_rehace_cuando_cambia_el_texto_del_guion(tmp_path):
    """Corregir una frase del guion tiene que regenerar ese clip.

    Antes `generar()` solo miraba si el MP3 existía, así que un cambio de texto
    no regeneraba nada: el video seguía diciendo la versión vieja y no había
    forma de notarlo salvo escuchándolo entero. Misma clase de problema que el
    video mudo — dar por bueno un artefacto viejo porque el archivo está.
    """
    sys.path.insert(0, str(RAIZ / "media"))
    import narracion

    mp3 = tmp_path / "x.mp3"
    mp3.write_bytes(b"0" * 2048)

    # Sin huella (un clip de antes de este cambio) se rehace.
    assert not narracion._al_dia(mp3, "hola")

    narracion._sellar(mp3, "hola")
    assert narracion._al_dia(mp3, "hola"), "con el mismo texto no debe rehacerse"
    assert not narracion._al_dia(mp3, "hola!"), "con otro texto TIENE que rehacerse"


def test_la_narracion_no_promete_un_numero_de_servidores_mcp_equivocado():
    """El guion dice cuántos servidores MCP se configuran; si se agrega o saca
    uno y nadie toca la locución, el video le miente al que lo mira."""
    sys.path.insert(0, str(RAIZ / "media"))
    sys.path.insert(0, str(RAIZ))
    import narracion
    from dxl import proveedores_ia

    cuantos = len(proveedores_ia.config_mcp("claude", ".")["mcpServers"])
    palabra = {3: ("tres", "three", "três"), 4: ("cuatro", "four", "quatro")}
    assert cuantos in palabra, f"agregá el número {cuantos} a este test"

    for idioma, esperada in zip(("es", "en", "pt"), palabra[cuantos]):
        frase = narracion.GUION[idioma]["herramientas"]
        assert esperada in frase.lower(), (
            f"la locución en {idioma} no dice «{esperada}» servidores MCP, "
            f"pero config_mcp devuelve {cuantos}: {frase!r}")


def test_el_bat_de_owner_busca_la_instalacion_en_el_registro():
    """El instalador deja ELEGIR la carpeta, así que el .bat de owner no puede
    depender de una lista de rutas fijas: tiene que leer del registro dónde
    quedó instalado. Antes solo miraba `%LOCALAPPDATA%\\Programs` con tres
    nombres, y cualquiera que instalara en D:\\ se quedaba sin poder
    convertirla.

    El .bat no se puede ejecutar acá (esto corre en Linux); lo que se cubre es
    que la búsqueda por registro siga existiendo y que no reaparezca el error
    de sintaxis que la rompía."""
    bat = RAIZ / "desktop" / "Convertir-a-version-dueno.bat"
    assert bat.exists(), "falta el .bat que pasa una instalación a owner"
    texto = bat.read_text(encoding="utf-8", errors="replace")

    assert "reg query" in texto.lower(), \
        "el .bat ya no consulta el registro: volvió a depender de rutas fijas"
    assert "Uninstall" in texto, \
        "no busca en las claves de desinstalación, que es donde está la ruta real"
    assert "InstallLocation" in texto, \
        "no lee InstallLocation, que es el valor con la carpeta de instalación"

    # `%ProgramFiles(x86)%` escrito adentro de un bloque `( ... )` hace que cmd
    # tome su paréntesis como el cierre del bloque y el .bat muere con un error
    # de sintaxis. Tiene que estar copiado a una variable ANTES del bloque.
    for linea in texto.splitlines():
        despojada = linea.strip()
        if despojada.startswith("REM") or despojada.startswith("::"):
            continue
        if "%ProgramFiles(x86)%" in despojada:
            assert despojada.lower().startswith('set "pf'), (
                "%ProgramFiles(x86)% solo puede usarse al asignarlo a una "
                f"variable, nunca dentro de un bloque: {despojada!r}")


def test_sellar_una_instalacion_como_owner_y_volver_atras(tmp_path):
    """`Convertir-a-version-dueno.bat` pasa una instalación a owner reescribiendo el
    sello. Tiene que dejarla sin clave ni vencimiento, conservar el secreto de
    licencias y el sitio, y poder revertirse."""
    import subprocess
    destino = _copia_instalada(
        tmp_path, {"edicion": "profesional", "bloqueada": True,
                   "secreto": "SECRETO-REAL", "sitio": "https://ejemplo"})
    instalacion = tmp_path            # contiene resources/app/…
    sello = destino / "edicion.json"
    sellador = RAIZ / "desktop" / "scripts" / "sellar_edicion.py"

    def correr(*args):
        r = subprocess.run([sys.executable, str(sellador), str(instalacion),
                            *args], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return json.loads(sello.read_text(encoding="utf-8"))

    sellado = correr("--edicion", "owner")
    assert sellado["edicion"] == "owner" and sellado["bloqueada"] is True
    assert sellado["secreto"] == "SECRETO-REAL", "se perdió el secreto"
    assert sellado["sitio"] == "https://ejemplo", "se perdió el sitio"
    # Y el motor lo tiene que ver, incluso con la variable en contra.
    assert _edicion_en(destino, tmp_path,
                       MVDAXLAB_EDICION_ARCHIVO=str(sello),
                       MVDAX_EDICION="demo") == "owner"

    restaurado = correr("--revertir")
    assert restaurado["edicion"] == "profesional"
