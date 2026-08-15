# © 2026 Martín Viera. Todos los derechos reservados.

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
from dxl import proveedores_ia  # noqa: E402
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


def test_archivos_corruptos_avisan_en_vez_de_reventar(tmp_path):
    """Un .pbit/.bim corrupto o a medio escribir cae en `advertencias`, no
    en un traceback crudo (BadZipFile/JSONDecodeError sin traducir)."""
    roto_pbit = tmp_path / "roto.pbit"
    roto_pbit.write_bytes(b"esto no es un zip")
    cargado = modmod.cargar(roto_pbit)
    assert cargado["modelo"] is None and cargado["layout"] is None
    assert cargado["advertencias"]
    assert cargado["formato"] == "pbit"

    roto_bim = tmp_path / "roto.bim"
    roto_bim.write_text("{esto no es json valido", encoding="utf-8")
    cargado = modmod.cargar(roto_bim)
    assert cargado["modelo"] is None
    assert cargado["advertencias"]
    assert cargado["formato"] == "bim"


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


def test_toda_regla_del_analizador_habla_los_tres_idiomas(cat):
    """Ninguna regla puede quedar en español cuando la app está en otro idioma.

    Es exactamente el defecto que tenía la pestaña Analizador: los títulos y
    las explicaciones eran cadenas en español dentro de `analizador.py`, así
    que en inglés y en portugués se veían los menús traducidos y los hallazgos
    no. Este test recorre TODAS las reglas —no las que dispara el modelo de
    prueba— para que agregar una regla sin sus tres idiomas rompa acá.
    """
    import re as _re
    from dxl.i18n import IDIOMAS, T

    fuente = (Path(__file__).resolve().parents[1] / "dxl" / "analizador.py"
              ).read_text(encoding="utf-8")
    reglas = sorted(set(_re.findall(r'_h\("(R\d\d)"', fuente)))
    assert len(reglas) >= 15, f"esperaba las 16 reglas, encontré {reglas}"

    for rid in reglas:
        for sufijo in ("", "_detalle", "_arreglo"):
            clave = f"regla_{rid}{sufijo}"
            assert clave in T, f"falta la clave {clave} en i18n"
            for idi in IDIOMAS:
                assert T[clave].get(idi), f"{clave} no tiene {idi}"

    # Y que salga distinto en cada idioma: una clave copiada del español a los
    # tres campos pasaría el chequeo de arriba sin traducir nada.
    hallazgos = analizador.analizar(cat)
    titulos = {idi: analizador.describir(hallazgos[0], idi)["titulo"]
               for idi in IDIOMAS}
    assert titulos["es"] != titulos["en"], titulos


def test_los_datos_de_la_regla_se_interpolan_en_los_tres_idiomas():
    """R04 y R05 nombran la tabla o la medida culpable DENTRO del texto.

    Se arma el hallazgo a mano en vez de buscarlo en un modelo: lo que se
    prueba es la plantilla, y atarlo a que tal modelo dispare tal regla hace
    que el test se caiga por un motivo que no tiene nada que ver.
    """
    from dxl.i18n import IDIOMAS

    casos = [("R04", {"tabla": "v_fact_ventas"}, "v_fact_ventas"),
             ("R05", {"medida": "Ventas netas"}, "Ventas netas")]
    for rid, datos, esperado in casos:
        h = {"regla": rid, "severidad": "media", "objeto": "[x]",
             "auto": False, "datos": datos}
        for idi in IDIOMAS:
            detalle = analizador.describir(h, idi)["detalle"]
            assert esperado in detalle, f"{rid}/{idi}: {detalle}"
            assert "{" not in detalle, f"{rid}/{idi} quedó sin interpolar"


def test_el_motor_no_deja_texto_en_espanol_en_otro_idioma(cat):
    """Guardia contra la fuga que tenían analizador, explicador y generador.

    No alcanza con que la clave exista en los tres idiomas: lo que se escapaba
    era texto escrito a mano en el módulo, que ninguna tabla de traducción
    cubre. Acá se compara la salida REAL en español contra la inglesa; si
    alguien vuelve a hardcodear una frase, las dos salen iguales y esto rompe.
    """
    from dxl import explicador

    dax = "CALCULATE ( SUM ( Ventas[Importe] ), ALL ( Ventas ) )"
    es = explicador.explicar(dax, idioma="es")
    en = explicador.explicar(dax, idioma="en")
    assert es["resumen"] != en["resumen"]
    assert es["pasos"] != en["pasos"]
    assert es["nivel_txt"] != en["nivel_txt"] or es["nivel"] == "basico"
    assert es["funciones"][0]["descripcion"] != en["funciones"][0]["descripcion"]
    assert es["funciones"][0]["categoria"] == en["funciones"][0]["categoria"], \
        "la categoría es una clave: no se traduce"

    hallazgos = analizador.analizar(cat)
    assert (analizador.describir(hallazgos[0], "es")["detalle"]
            != analizador.describir(hallazgos[0], "en")["detalle"])

    from dxl import generador
    r_es = generador.generar("promedio de costo", cat, idioma="es")
    r_en = generador.generar("promedio de costo", cat, idioma="en")
    assert r_es["ok"] and r_en["ok"]
    assert r_es["nombre"] != r_en["nombre"], \
        f"el nombre de la medida no varía con el idioma: {r_es['nombre']!r}"
    assert r_es["explicacion"] != r_en["explicacion"]

    r_es_error = generador.generar("promedio de columnainexistente", cat,
                                   idioma="es")
    r_en_error = generador.generar("promedio de columnainexistente", cat,
                                   idioma="en")
    assert not r_es_error["ok"] and not r_en_error["ok"]
    assert r_es_error["advertencias"] != r_en_error["advertencias"], \
        f"el error del generador no se tradujo: {r_es_error['advertencias']!r}"

    errores_es = catalogo.validar_referencias(
        "SUM ( Fantasma[NoExiste] )", cat, idioma="es")
    errores_en = catalogo.validar_referencias(
        "SUM ( Fantasma[NoExiste] )", cat, idioma="en")
    assert errores_es and errores_en
    assert errores_es != errores_en, \
        f"validar_referencias no tradujo: {errores_es!r}"


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
    # El sustantivo puede ir antes o después de «distintos»: las dos formas
    # son el mismo pedido. La variante «X distintos» estuvo rota hasta que la
    # encontró el end-to-end por MCP.
    for pedido in ("cantidad de clientes distintos", "clientes distintos",
                   "distintos clientes", "clientes únicos"):
        r = generador.generar(pedido, cat)
        assert r["ok"], f"«{pedido}»: {r['advertencias']}"
        assert "DISTINCTCOUNT" in r["dax"], pedido
        assert catalogo.validar_referencias(r["dax"], cat) == []


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


def test_no_secuestra_una_medida_por_una_palabra_suelta(cat):
    """
    Una medida se reutiliza cuando el pedido la NOMBRA, no cuando su nombre
    contiene la palabra. Con el umbral flojo original, pedir «importe» con un
    «% del total · Importe» en el modelo generaba TOTALYTD de un porcentaje:
    DAX válido, resultado sin sentido.
    """
    modelo_con_ruido, _ = transformador.agregar_medida(
        modelo_juguete(), "% del total · Importe",
        "DIVIDE ( SUM ( Ventas[Importe] ), 1 )", formato="0.0 %")
    cat2 = catalogo.Catalogo.desde_modelo(modelo_con_ruido)

    assert cat2.buscar_medida("importe") is None
    r = generador.generar("importe acumulado del año", cat2)
    assert r["ok"]
    assert "% del total" not in r["dax"], r["dax"]
    assert "SUM ( Ventas[Importe] )" in r["dax"]

    # Pero nombrarla completa sí la reutiliza, y los separadores no importan.
    for alias in ("% del total · Importe", "% del total - importe",
                  "del total importe"):
        encontrada = cat2.buscar_medida(alias)
        assert encontrada and encontrada["nombre"] == "% del total · Importe", alias

    # Un nombre que solo comparte el prefijo NO alcanza: con «Importe YTD» en
    # el modelo, pedir «importe» tiene que seguir yendo a la columna.
    modelo_ytd, _ = transformador.agregar_medida(
        modelo_juguete(), "Importe YTD",
        "TOTALYTD ( SUM ( Ventas[Importe] ), Calendario[Fecha] )")
    cat3 = catalogo.Catalogo.desde_modelo(modelo_ytd)
    assert cat3.buscar_medida("importe") is None
    r3 = generador.generar("importe vs año anterior", cat3)
    assert r3["ok"] and "[Importe YTD]" not in r3["dax"], r3["dax"]


def test_medida_de_conteo_se_llama_por_lo_que_cuenta(cat):
    """Contar Ventas[IdCliente] es contar clientes, no «IdCliente»."""
    r = generador.generar("clientes distintos", cat)
    assert r["ok"]
    assert r["nombre"] == "Clientes distintos", r["nombre"]
    assert "DISTINCTCOUNT ( Ventas[IdCliente] )" in r["dax"]


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
    # La config MCP en sí vive en proveedores_ia.py (soporta varios agentes:
    # Claude, ChatGPT/Codex, Copilot, Gemini) — herramientas.py tenía una
    # copia vieja, de un solo agente, que nada en producción usaba.
    cfg = proveedores_ia.config_mcp("claude", ".")
    assert cfg["mcpServers"]["powerbi-remote"]["url"] == \
        proveedores_ia.MCP_REMOTO_POWERBI
    assert "mv-dax-lab" in cfg["mcpServers"]


def test_config_mcp_trae_powerbi_y_fabric_por_separado():
    """Son dos servidores distintos, no el mismo con otra ruta.

    `…/mcp/powerbi` trabaja sobre modelos semánticos y DAX; `…/mcp/core` sobre
    el tenant —workspaces, items, permisos—. Publicar desde la app necesita
    saber a qué workspace va, y eso lo contesta core. Si alguien "simplifica"
    dejando uno solo, se pierde la mitad.
    """
    cfg = proveedores_ia.config_mcp("claude", ".")["mcpServers"]
    assert cfg["fabric-core"]["url"] == proveedores_ia.MCP_REMOTO_FABRIC
    assert cfg["fabric-core"]["url"].endswith("/mcp/core")
    assert cfg["powerbi-remote"]["url"].endswith("/mcp/powerbi")
    assert cfg["fabric-core"]["url"] != cfg["powerbi-remote"]["url"]
    # Los dos remotos son HTTP con OAuth de Entra ID, no procesos locales.
    for nombre in ("powerbi-remote", "fabric-core"):
        assert cfg[nombre]["type"] == "http", f"{nombre} no es remoto"
        assert "command" not in cfg[nombre]


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


def test_mcp_respeta_la_licencia_y_no_pisa_archivos(tmp_path, monkeypatch):
    """El server MCP tiene el mismo candado que la app: sin licencia vigente,
    generar_dax y exportar quedan cerrados (estuvieron abiertos del todo,
    sin chequear licencia.evaluar() en ningún lado). Y exportar no pisa un
    archivo que ya existe salvo que se lo pidan a propósito."""
    import time as _time
    from dxl import licencia
    import servidor as srv

    monkeypatch.setenv("MVDAXLAB_DATOS", str(tmp_path))
    monkeypatch.delenv("MVDAX_EDICION", raising=False)
    monkeypatch.setenv("MVDAXLAB_EDICION_ARCHIVO", str(tmp_path / "no-hay"))
    licencia.guardar_estado({"demo_inicio": _time.time() - 8 * 86400})
    assert not licencia.evaluar().activa, "la demo tiene que estar vencida"

    bim = tmp_path / "j2.bim"
    bim.write_text(json.dumps(modelo_juguete()), encoding="utf-8")
    r = srv.atender({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                     "params": {"name": "cargar_modelo",
                                "arguments": {"ruta": str(bim)}}})
    assert not r["result"].get("isError"), "cargar_modelo queda siempre abierto"

    r = srv.atender({"jsonrpc": "2.0", "id": 11, "method": "tools/call",
                     "params": {"name": "generar_dax",
                                "arguments": {"pedido": "total de importe",
                                              "aplicar": True}}})
    assert r["result"].get("isError"), \
        "generar_dax se ejecutó sin licencia vigente"

    r = srv.atender({"jsonrpc": "2.0", "id": 12, "method": "tools/call",
                     "params": {"name": "exportar",
                                "arguments": {"destino":
                                              str(tmp_path / "no.pbit")}}})
    assert r["result"].get("isError"), \
        "exportar se ejecutó sin licencia vigente"
    assert not (tmp_path / "no.pbit").exists()

    # Con licencia vigente, exportar sí funciona — pero no pisa un archivo
    # que ya existe salvo que se lo digan explícitamente.
    licencia.guardar_estado({"demo_inicio": _time.time()})
    destino = tmp_path / "salida2.pbit"
    destino.write_bytes(b"lo que sea, ya existe")
    r = srv.atender({"jsonrpc": "2.0", "id": 13, "method": "tools/call",
                     "params": {"name": "exportar",
                                "arguments": {"destino": str(destino)}}})
    assert r["result"].get("isError"), \
        "exportar pisó un archivo existente sin que se lo pidieran"
    assert destino.read_bytes() == b"lo que sea, ya existe"

    r = srv.atender({"jsonrpc": "2.0", "id": 14, "method": "tools/call",
                     "params": {"name": "exportar",
                                "arguments": {"destino": str(destino),
                                              "sobrescribir": True}}})
    assert not r["result"].get("isError")
    assert destino.read_bytes() != b"lo que sea, ya existe"
