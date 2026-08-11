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
        assert set(servidores) == {"powerbi-remote", "powerbi-modeling",
                                   "mv-dax-lab"}
        assert servidores["powerbi-remote"]["url"] == \
            proveedores_ia.MCP_REMOTO_POWERBI
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
        if archivo in permitidos or "node_modules" in archivo.parts \
                or "dist" in archivo.parts or "tests" in archivo.parts \
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
