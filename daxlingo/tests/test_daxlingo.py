"""
MV DAX Lab · Suite de tests del motor.

Cubre: carga/escritura .pbit y PBIP (ida y vuelta), catálogo (búsqueda
difusa, referencias), analizador (reglas + arreglos automáticos), explicador,
generador NL→DAX (patrones y anti-alucinación), transformaciones, tablero,
academia (normalización y verificación), bandeja del asistente, payloads de
Fabric y servidor MCP. Sin red: todo local y determinístico.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "mcp"))

from dxl import analizador, asistente, catalogo, ejercicios  # noqa: E402
from dxl import explicador, fabric, generador, herramientas  # noqa: E402
from dxl import modelo as modmod  # noqa: E402
from dxl import tablero, transformador  # noqa: E402


# ==========================================================================
# Modelo de juguete: estrella mínima con defectos inyectados a propósito
# ==========================================================================
def modelo_juguete() -> dict:
    return {
        "name": "Juguete",
        "compatibilityLevel": 1567,
        "model": {
            "culture": "es-ES",
            "tables": [
                {
                    "name": "Ventas",
                    "columns": [
                        {"name": "Fecha", "dataType": "dateTime",
                         "sourceColumn": "Fecha"},
                        {"name": "IdCliente", "dataType": "int64",
                         "sourceColumn": "IdCliente"},
                        {"name": "Importe", "dataType": "double",
                         "sourceColumn": "Importe"},
                        {"name": "Costo", "dataType": "double",
                         "sourceColumn": "Costo"},
                        {"name": "Margen", "dataType": "double",
                         "type": "calculated",
                         "expression": "Ventas[Importe] - Ventas[Costo]"},
                    ],
                    "partitions": [{"name": "Ventas", "mode": "import",
                                    "source": {"type": "m",
                                               "expression": ["let", "in x"]}}],
                    "measures": [
                        {"name": "Total Ventas",
                         "expression": "SUM ( Ventas[Importe] )",
                         "formatString": "#,0"},
                        {"name": "Margen %",
                         "expression": "( SUM ( Ventas[Importe] ) - SUM ( "
                                       "Ventas[Costo] ) ) / SUM ( "
                                       "Ventas[Importe] )"},
                    ],
                },
                {
                    "name": "Clientes",
                    "columns": [
                        {"name": "IdCliente", "dataType": "int64",
                         "sourceColumn": "IdCliente"},
                        {"name": "Pais", "dataType": "string",
                         "sourceColumn": "Pais"},
                    ],
                    "partitions": [{"name": "Clientes", "mode": "import",
                                    "source": {"type": "m",
                                               "expression": "let in x"}}],
                },
                {
                    "name": "Calendario",
                    "dataCategory": "Time",
                    "columns": [
                        {"name": "Fecha", "dataType": "dateTime",
                         "isKey": True, "sourceColumn": "Fecha"},
                        {"name": "AnioMes", "dataType": "string",
                         "sourceColumn": "AnioMes"},
                    ],
                    "partitions": [{"name": "Calendario", "mode": "import",
                                    "source": {"type": "m",
                                               "expression": "let in x"}}],
                },
                {
                    "name": "Suelta",
                    "columns": [{"name": "Cosa", "dataType": "string",
                                 "sourceColumn": "Cosa"}],
                    "partitions": [{"name": "Suelta", "mode": "import",
                                    "source": {"type": "m",
                                               "expression": "let in x"}}],
                },
            ],
            "relationships": [
                {"name": "r1", "fromTable": "Ventas",
                 "fromColumn": "IdCliente", "toTable": "Clientes",
                 "toColumn": "IdCliente",
                 "crossFilteringBehavior": "bothDirections"},
                {"name": "r2", "fromTable": "Ventas", "fromColumn": "Fecha",
                 "toTable": "Calendario", "toColumn": "Fecha"},
            ],
        },
    }


@pytest.fixture()
def cat() -> catalogo.Catalogo:
    return catalogo.Catalogo.desde_modelo(modelo_juguete())


# ==========================================================================
# modelo.py — carga y escritura
# ==========================================================================
def test_pbit_ida_y_vuelta(tmp_path, cat):
    layout = tablero.disenar_auto(cat, titulo="Prueba")
    destino = tmp_path / "prueba.pbit"
    modmod.exportar_pbit(modelo_juguete(), layout, destino)
    assert destino.exists()

    cargado = modmod.cargar(destino)
    assert cargado["formato"] == "pbit"
    assert cargado["modelo"]["name"] == "Juguete"
    cat2 = catalogo.Catalogo.desde_modelo(cargado["modelo"])
    assert cat2.resumen()["tablas"] == 4
    assert cat2.resumen()["medidas"] == 2
    assert len(cargado["layout"]["sections"]) == 2


def test_pbip_ida_y_vuelta(tmp_path, cat):
    layout = tablero.disenar_auto(cat, titulo="Prueba")
    pbip = modmod.exportar_pbip(modelo_juguete(), layout, tmp_path, "Demo")
    assert pbip.name == "Demo.pbip"
    assert (tmp_path / "Demo.SemanticModel" / "model.bim").exists()
    assert (tmp_path / "Demo.Report" / "report.json").exists()

    cargado = modmod.cargar(pbip)
    assert cargado["formato"] == "pbip"
    assert cargado["modelo"]["name"] == "Juguete"
    assert cargado["layout"] is not None


def test_bim_directo(tmp_path):
    ruta = tmp_path / "m.bim"
    ruta.write_text(json.dumps(modelo_juguete()), encoding="utf-8")
    cargado = modmod.cargar(ruta)
    assert cargado["formato"] == "bim"
    assert cargado["modelo"]["model"]["tables"]


def test_pbix_sin_modelo_avisa(tmp_path, cat):
    """Un .pbix con DataModel binario: layout sí, modelo no, con aviso."""
    import zipfile
    layout = tablero.disenar_auto(cat, titulo="Prueba")
    ruta = tmp_path / "x.pbix"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("DataModel", b"\x00\x01binario-propietario")
        z.writestr("Report/Layout",
                   b"\xff\xfe" + json.dumps(layout).encode("utf-16-le"))
    cargado = modmod.cargar(ruta)
    assert cargado["modelo"] is None
    assert cargado["layout"] is not None
    assert any("propietario" in a for a in cargado["advertencias"])
    parcial = catalogo.Catalogo.desde_layout(cargado["layout"])
    assert parcial.parcial
    assert parcial.tablas  # extrajo entidades de los prototypeQuery


def test_modelo_demo_viaja_con_el_producto():
    """
    El demo tiene que estar DENTRO del paquete: la landing lo promete y el
    instalador no lleva la carpeta powerbi/ del repo.
    """
    demo = RAIZ / "datos" / "demo" / "modelo_demo.bim"
    assert demo.exists(), "Falta datos/demo/modelo_demo.bim"
    cargado = modmod.cargar(demo)
    cat2 = catalogo.Catalogo.desde_modelo(cargado["modelo"])
    r = cat2.resumen()
    assert r["tablas"] >= 15
    assert r["medidas"] >= 100


# ==========================================================================
# catalogo.py
# ==========================================================================
def test_busqueda_difusa(cat):
    tabla, col = cat.buscar_columna("importe")
    assert (tabla, col["nombre"]) == ("Ventas", "Importe")
    # con acento y mayúsculas
    tabla, col = cat.buscar_columna("PAÍS")
    assert (tabla, col["nombre"]) == ("Clientes", "Pais")
    assert cat.buscar_columna("inexistente_total") is None


def test_tabla_fechas(cat):
    assert cat.tabla_fechas()["nombre"] == "Calendario"
    assert cat.columna_fecha() == ("Calendario", "Fecha")


def test_referencias_y_validacion(cat):
    refs = catalogo.referencias_dax(
        "CALCULATE ( SUM ( Ventas[Importe] ), ALL ( Clientes ) ) + [Margen %]")
    assert ("Ventas", "Importe") in refs["columnas"]
    assert "Margen %" in refs["medidas"]
    errores = catalogo.validar_referencias(
        "SUM ( Fantasma[NoExiste] )", cat)
    assert errores and "Fantasma" in errores[0]
    assert catalogo.validar_referencias("SUM ( Ventas[Importe] )", cat) == []


# ==========================================================================
# analizador.py
# ==========================================================================
def test_analizador_detecta_defectos(cat):
    hallazgos = analizador.analizar(cat)
    reglas = {h["regla"].split(" ·")[0] for h in hallazgos}
    assert "R01" in reglas   # división con /
    assert "R02" in reglas   # medida sin formato
    assert "R07" in reglas   # columna calculada
    assert "R09" in reglas   # relación bidireccional
    assert "R12" in reglas   # tabla suelta
    assert 0 <= analizador.puntaje(hallazgos) < 100


def test_arreglos_automaticos(cat):
    hallazgos = analizador.analizar(cat)
    nuevo, cambios = transformador.aplicar_arreglos(modelo_juguete(),
                                                    hallazgos)
    assert cambios
    cat2 = catalogo.Catalogo.desde_modelo(nuevo)
    margen = cat2.medida("Margen %")
    assert "DIVIDE" in margen["expresion"]
    assert margen["formato"]  # formato asignado
    hallazgos2 = analizador.analizar(cat2)
    assert analizador.puntaje(hallazgos2) > analizador.puntaje(hallazgos)


# ==========================================================================
# explicador.py
# ==========================================================================
def test_explicador_calculate(cat):
    e = explicador.explicar(
        "CALCULATE ( SUM ( Ventas[Importe] ), "
        "SAMEPERIODLASTYEAR ( Calendario[Fecha] ) )", cat)
    nombres = {f["nombre"] for f in e["funciones"]}
    assert {"CALCULATE", "SUM", "SAMEPERIODLASTYEAR"} <= nombres
    assert e["nivel"] in ("intermedio", "avanzado")
    assert any("contexto" in p.lower() for p in e["pasos"])
    assert e["faltantes"] == []


def test_explicador_detecta_faltantes(cat):
    e = explicador.explicar("SUM ( Nada[Nada] )", cat)
    assert e["faltantes"]


# ==========================================================================
# generador.py — patrones y anti-alucinación
# ==========================================================================
def test_generar_suma(cat):
    r = generador.generar("total de importe", cat)
    assert r["ok"] and r["dax"] == "SUM ( Ventas[Importe] )"
    assert catalogo.validar_referencias(r["dax"], cat) == []


def test_generar_distintos(cat):
    r = generador.generar("cantidad de clientes distintos", cat)
    assert r["ok"] and "DISTINCTCOUNT" in r["dax"]


def test_generar_pct_total(cat):
    r = generador.generar("% del total de importe", cat)
    assert r["ok"] and "DIVIDE" in r["dax"] and "ALLSELECTED" in r["dax"]


def test_generar_ytd(cat):
    r = generador.generar("importe acumulado del año", cat)
    assert r["ok"] and "TOTALYTD" in r["dax"]
    assert "Calendario" in r["dax"]


def test_generar_yoy(cat):
    r = generador.generar("importe vs año anterior", cat)
    assert r["ok"] and "SAMEPERIODLASTYEAR" in r["dax"]
    assert "DIVIDE" in r["dax"]


def test_generar_media_movil(cat):
    r = generador.generar("media móvil de 6 meses de importe", cat)
    assert r["ok"] and "DATESINPERIOD" in r["dax"] and "-6" in r["dax"]


def test_generar_ranking(cat):
    r = generador.generar("ranking de país por importe", cat)
    assert r["ok"] and "RANKX" in r["dax"]


def test_generar_no_inventa(cat):
    r = generador.generar("total de facturación galáctica", cat)
    assert not r["ok"]
    assert r["advertencias"]


def test_generar_reusa_medidas(cat):
    r = generador.generar("total ventas acumulado del año", cat)
    assert r["ok"] and "[Total Ventas]" in r["dax"]


# ==========================================================================
# transformador.py
# ==========================================================================
def test_agregar_y_renombrar_medida(cat):
    m0 = modelo_juguete()
    m1, _ = transformador.agregar_medida(m0, "Ventas YTD",
                                         "TOTALYTD ( [Total Ventas], "
                                         "Calendario[Fecha] )",
                                         formato="#,0")
    with pytest.raises(ValueError):
        transformador.agregar_medida(m1, "Ventas YTD", "1")
    m2, cambios = transformador.renombrar_medida(m1, "Total Ventas",
                                                 "Ventas Totales")
    cat2 = catalogo.Catalogo.desde_modelo(m2)
    ytd = cat2.medida("Ventas YTD")
    assert "[Ventas Totales]" in ytd["expresion"]
    assert any("referencia" in c for c in cambios)


def test_eliminar_medida_protegida():
    m0 = modelo_juguete()
    m1, _ = transformador.agregar_medida(
        m0, "Doble", "[Total Ventas] * 2")
    with pytest.raises(ValueError, match="referenciada"):
        transformador.eliminar_medida(m1, "Total Ventas")
    m2, cambios = transformador.eliminar_medida(m1, "Doble")
    assert catalogo.Catalogo.desde_modelo(m2).medida("Doble") is None


def test_crear_tabla_medidas():
    nuevo, cambios = transformador.crear_tabla_medidas(modelo_juguete())
    cat2 = catalogo.Catalogo.desde_modelo(nuevo)
    t = cat2.tabla("_Medidas")
    assert t is not None and len(t["medidas"]) == 2


def test_ocultar_claves():
    nuevo, cambios = transformador.ocultar_claves(modelo_juguete())
    cat2 = catalogo.Catalogo.desde_modelo(nuevo)
    ventas = cat2.tabla("Ventas")
    idc = next(c for c in ventas["columnas"] if c["nombre"] == "IdCliente")
    assert idc["oculta"]


# ==========================================================================
# tablero.py
# ==========================================================================
def test_tablero_estructura(cat):
    layout = tablero.disenar_auto(cat, titulo="Demo")
    assert len(layout["sections"]) == 2
    resumen = layout["sections"][0]
    tipos = []
    for vc in resumen["visualContainers"]:
        conf = json.loads(vc["config"])
        sv = conf.get("singleVisual", {})
        tipos.append(sv.get("visualType"))
        if sv.get("visualType") not in ("textbox", "actionButton"):
            assert sv.get("prototypeQuery"), \
                f"visual {sv.get('visualType')} sin prototypeQuery"
    assert "slicer" in tipos          # filtros
    assert "card" in tipos            # KPIs
    assert "lineChart" in tipos       # evolución (hay calendario)
    assert "actionButton" in tipos    # navegación


def test_tablero_sin_medidas_falla():
    m = modelo_juguete()
    for t in m["model"]["tables"]:
        t.pop("measures", None)
    sin = catalogo.Catalogo.desde_modelo(m)
    with pytest.raises(ValueError):
        tablero.disenar_auto(sin)


# ==========================================================================
# ejercicios.py — Academia
# ==========================================================================
def test_banco_ejercicios_valido():
    banco = ejercicios.cargar_ejercicios()
    assert len(banco) >= 15
    ids = [e["id"] for e in banco]
    assert len(ids) == len(set(ids))
    for e in banco:
        assert e["solucion"] and e["enunciado"] and e["xp"] > 0


def test_verificacion_tolerante():
    banco = ejercicios.cargar_ejercicios()
    e1 = next(e for e in banco if e["id"] == "N1-01")
    # espacios, mayúsculas y comillas de tabla distintas: igual correcto
    assert ejercicios.verificar(e1, "sum('Ventas'[Importe])")["correcto"]
    assert ejercicios.verificar(e1, "SUM ( Ventas[Importe] )")["correcto"]
    assert not ejercicios.verificar(e1, "SUM ( Ventas[Costo] )")["correcto"]
    # la incorrecta con función equivocada da pista de la esperada
    v = ejercicios.verificar(e1, "AVERAGE ( Ventas[Importe] )")
    assert "SUM" in v["detalle"]


def test_verificacion_por_patron():
    banco = ejercicios.cargar_ejercicios()
    e = next(x for x in banco if x["id"] == "N3-03")
    variante = ("VAR a = SUM ( Ventas[Importe] ) "
                "VAR b = CALCULATE ( SUM ( Ventas[Importe] ), "
                "SAMEPERIODLASTYEAR ( Calendario[Fecha] ) ) "
                "RETURN DIVIDE ( a - b, b )")
    assert ejercicios.verificar(e, variante)["correcto"]


def test_niveles_xp():
    assert ejercicios.nivel_por_xp(0).endswith("Novato")
    assert ejercicios.nivel_por_xp(700).endswith("Maestro DAX")
    assert ejercicios.proximo_nivel(0)[1] == 100


# ==========================================================================
# asistente.py — bandeja y parser de acciones
# ==========================================================================
def test_extraer_acciones_medida():
    respuesta = ("Explicación paso a paso...\n"
                 "```dax\nVentas YTD = TOTALYTD ( SUM ( Ventas[Importe] ), "
                 "Calendario[Fecha] )\n```\nSiguiente paso: agregala.")
    acciones = asistente.extraer_acciones(respuesta)
    assert acciones[0]["tipo"] == "medida"
    assert acciones[0]["nombre"] == "Ventas YTD"
    assert acciones[0]["dax"].startswith("TOTALYTD")


def test_extraer_acciones_columna():
    respuesta = ("Es una columna calculada para la tabla Ventas:\n"
                 "```dax\nMargen Unitario = Ventas[Importe] - "
                 "Ventas[Costo]\n```")
    acciones = asistente.extraer_acciones(respuesta)
    assert acciones[0]["tipo"] == "columna_calculada"


def test_bandeja_ciclo_completo(tmp_path):
    archivo = asistente.depositar(
        "total ventas ytd",
        "```dax\nX = SUM ( Ventas[Importe] )\n```", carpeta=tmp_path)
    items = asistente.pendientes(tmp_path)
    assert len(items) == 1 and items[0]["estado"] == "pendiente"
    nuevo, cambios = asistente.aplicar_accion(
        modelo_juguete(), items[0]["acciones"][0])
    assert catalogo.Catalogo.desde_modelo(nuevo).medida("X")
    asistente.marcar(archivo, "aplicado")
    assert asistente.pendientes(tmp_path)[0]["estado"] == "aplicado"
    assert asistente.limpiar(tmp_path) == 1


def test_columna_calculada():
    nuevo, cambios = asistente.agregar_columna_calculada(
        modelo_juguete(), "Ventas", "Neto", "Ventas[Importe] * 0.78")
    cat2 = catalogo.Catalogo.desde_modelo(nuevo)
    assert any(c["nombre"] == "Neto" and c["calculada"]
               for c in cat2.tabla("Ventas")["columnas"])
    with pytest.raises(ValueError):
        asistente.agregar_columna_calculada(nuevo, "NoExiste", "Y", "1")


# ==========================================================================
# fabric.py — payloads (sin red)
# ==========================================================================
def test_payload_fabric():
    import base64
    p = fabric.payload_modelo_semantico("Demo", modelo_juguete())
    assert p["type"] == "SemanticModel"
    parte = next(x for x in p["definition"]["parts"]
                 if x["path"] == "model.bim")
    decodificado = json.loads(base64.b64decode(parte["payload"]))
    assert decodificado["name"] == "Juguete"
    r = fabric.payload_reporte("Demo", {"sections": []}, "abc-123")
    assert r["definition"]["format"] == "PBIR-Legacy"


# ==========================================================================
# herramientas.py
# ==========================================================================
def test_herramientas_registro():
    claves = {h["clave"] for h in herramientas.HERRAMIENTAS}
    assert {"desktop", "bravo", "daxstudio", "tabulareditor", "almtoolkit",
            "vscode", "fabric", "mcp"} <= claves
    cfg = herramientas.config_mcp(".")
    assert cfg["mcpServers"]["powerbi-remote"]["url"] == \
        herramientas.MCP_REMOTO_POWERBI
    assert "mv-dax-lab" in cfg["mcpServers"]


def test_exportar_medidas_dax(tmp_path, cat):
    ruta = herramientas.exportar_medidas_dax(cat, tmp_path / "m.dax")
    texto = ruta.read_text("utf-8")
    assert "[Total Ventas] :=" in texto


# ==========================================================================
# Servidor MCP
# ==========================================================================
def test_mcp_flujo(tmp_path):
    import servidor as srv

    r = srv.atender({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {}})
    assert r["result"]["serverInfo"]["name"]

    r = srv.atender({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    nombres = {t["name"] for t in r["result"]["tools"]}
    assert {"cargar_modelo", "analizar_modelo", "generar_dax",
            "explicar_dax", "exportar"} <= nombres

    bim = tmp_path / "j.bim"
    bim.write_text(json.dumps(modelo_juguete()), encoding="utf-8")
    r = srv.atender({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "cargar_modelo",
                                "arguments": {"ruta": str(bim)}}})
    assert not r["result"].get("isError")

    r = srv.atender({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                     "params": {"name": "generar_dax",
                                "arguments": {"pedido": "total de importe",
                                              "aplicar": True}}})
    salida = json.loads(r["result"]["content"][0]["text"])
    assert salida["ok"] and salida.get("aplicado")

    destino = tmp_path / "salida.pbit"
    r = srv.atender({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                     "params": {"name": "exportar",
                                "arguments": {"destino": str(destino)}}})
    assert destino.exists()

    # notificación: no responde
    assert srv.atender({"jsonrpc": "2.0",
                        "method": "notifications/initialized"}) is None
