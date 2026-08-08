"""
MV DAX Lab · End-to-end real por MCP, sobre el dataset sintético.

Diferencia con `test_daxlingo.py::test_mcp_flujo`: aquel llama a `atender()`
en proceso, que prueba la lógica pero no el servidor. Acá se LEVANTA
`mcp/servidor.py` como proceso aparte y se le habla JSON-RPC por stdin/stdout,
igual que haría Claude Code, ChatGPT o Copilot. Si el servidor no arranca, si
el handshake falla o si una respuesta no es JSON por línea, esto se entera.

El ciclo que se recorre es el que promete el producto:

    generar dataset sintético → cargar el modelo → inspeccionarlo →
    auditarlo → pedir DAX en lenguaje natural y aplicarlo →
    explicar lo aplicado → exportar a .pbit → reabrir el .pbit y comprobar
    que el modelo y el tablero llegaron enteros.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dxl import catalogo  # noqa: E402
from dxl import modelo as modmod  # noqa: E402

SERVIDOR = RAIZ / "mcp" / "servidor.py"


class ClienteMCP:
    """Cliente JSON-RPC mínimo, hablando por stdio con el servidor real."""

    def __init__(self) -> None:
        self.proceso = subprocess.Popen(
            [sys.executable, str(SERVIDOR)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1)
        self._id = 0

    def llamar(self, metodo: str, params: dict | None = None) -> dict:
        self._id += 1
        peticion = {"jsonrpc": "2.0", "id": self._id, "method": metodo}
        if params is not None:
            peticion["params"] = params
        self.proceso.stdin.write(json.dumps(peticion) + "\n")
        self.proceso.stdin.flush()
        linea = self.proceso.stdout.readline()
        if not linea:
            errores = self.proceso.stderr.read()
            raise RuntimeError(f"el servidor MCP no respondió. stderr:\n{errores}")
        return json.loads(linea)

    def herramienta(self, nombre: str, argumentos: dict) -> str:
        """Llama a una tool y devuelve su texto; lanza si vino marcada error."""
        r = self.llamar("tools/call", {"name": nombre, "arguments": argumentos})
        resultado = r["result"]
        texto = resultado["content"][0]["text"]
        if resultado.get("isError"):
            raise AssertionError(f"{nombre} falló: {texto}")
        return texto

    def json_de(self, nombre: str, argumentos: dict) -> dict:
        return json.loads(self.herramienta(nombre, argumentos))

    def cerrar(self) -> None:
        try:
            self.proceso.stdin.close()
            self.proceso.wait(timeout=10)
        except Exception:
            self.proceso.kill()


@pytest.fixture()
def sintetico(tmp_path):
    """Dataset y modelo sintéticos, generados de cero en cada corrida."""
    sys.path.insert(0, str(RAIZ / "datos" / "demo"))
    from generar_sintetico import construir_modelo, generar_datos

    filas = generar_datos(tmp_path / "datos")
    bim = tmp_path / "modelo_sintetico.bim"
    bim.write_text(json.dumps(construir_modelo(), ensure_ascii=False),
                   encoding="utf-8")
    return {"bim": bim, "filas": filas, "carpeta": tmp_path}


@pytest.fixture()
def mcp():
    cliente = ClienteMCP()
    yield cliente
    cliente.cerrar()


# ==========================================================================
def test_handshake_y_catalogo_de_herramientas(mcp):
    r = mcp.llamar("initialize", {"protocolVersion": "2024-11-05"})
    assert r["result"]["serverInfo"]["name"] == "MV DAX Lab"
    assert "tools" in r["result"]["capabilities"]

    r = mcp.llamar("tools/list")
    herramientas = {t["name"]: t for t in r["result"]["tools"]}
    assert {"cargar_modelo", "resumen_modelo", "analizar_modelo",
            "generar_dax", "explicar_dax", "exportar"} <= set(herramientas)
    # Un agente necesita el schema para poder invocar: si falta, no sirve.
    for nombre, t in herramientas.items():
        assert t["description"], nombre
        assert t["inputSchema"]["type"] == "object", nombre


def test_ciclo_completo_modelado_dax_y_export(mcp, sintetico):
    """El recorrido entero que promete el producto, por MCP, de punta a punta."""
    mcp.llamar("initialize", {"protocolVersion": "2024-11-05"})

    # --- 1. cargar el modelo sintético ---------------------------------
    carga = mcp.json_de("cargar_modelo", {"ruta": str(sintetico["bim"])})
    assert carga["formato"] == "bim"
    resumen = carga["resumen"]
    assert resumen["tablas"] == 5          # Ventas, Clientes, Productos, Calendario, Notas
    assert resumen["medidas"] == 2         # Total Ventas y Margen %
    assert resumen["relaciones"] == 3
    assert resumen["tabla_fechas"] == "Calendario"

    # --- 2. inspeccionar (lo que hace un agente antes de tocar nada) ----
    detalle = mcp.json_de("resumen_modelo", {})
    tablas = {t["nombre"]: t for t in detalle["tablas"]}
    assert set(tablas) == {"Ventas", "Clientes", "Productos", "Calendario",
                           "Notas"}
    assert "Importe" in tablas["Ventas"]["columnas"]
    assert "Pais" in tablas["Clientes"]["columnas"]

    # --- 3. auditar: tiene que encontrar los defectos inyectados --------
    auditoria = mcp.json_de("analizar_modelo", {})
    reglas = {h["regla"].split(" ·")[0] for h in auditoria["hallazgos"]}
    assert "R01" in reglas, "no detectó la división con «/» de [Margen %]"
    assert "R02" in reglas, "no detectó la medida sin formato"
    assert "R09" in reglas, "no detectó la relación bidireccional"
    assert "R12" in reglas, "no detectó la tabla Notas sin relaciones"
    assert 0 < auditoria["puntaje_salud"] < 100

    # --- 4. pedir DAX en lenguaje natural y APLICARLO -------------------
    pedidos = {
        "total de cantidad": ["SUM", "Ventas[Cantidad]"],
        "clientes distintos": ["DISTINCTCOUNT"],
        "importe acumulado del año": ["TOTALYTD", "Calendario[Fecha]"],
        "importe vs año anterior": ["SAMEPERIODLASTYEAR", "DIVIDE"],
        "media móvil de 3 meses de importe": ["DATESINPERIOD", "AVERAGEX"],
        "ranking de país por importe": ["RANKX"],
        "% del total de importe": ["DIVIDE", "ALLSELECTED"],
    }
    aplicadas = []
    for pedido, fragmentos in pedidos.items():
        r = mcp.json_de("generar_dax", {"pedido": pedido, "aplicar": True})
        assert r["ok"], f"«{pedido}» no se pudo generar: {r['advertencias']}"
        for fragmento in fragmentos:
            assert fragmento in r["dax"], \
                f"«{pedido}» no usó {fragmento}:\n{r['dax']}"
        assert r["aplicado"], f"«{pedido}» no se aplicó al modelo"
        aplicadas.append(r["nombre"])

        # Cada medida nueva entra al catálogo, así que la siguiente podría
        # engancharse a ella. Pedir «importe» tiene que seguir apuntando a
        # Ventas[Importe] y NO a una medida que solo contiene esa palabra:
        # acumular un «% del total» daría un resultado absurdo con DAX
        # perfectamente válido. Es el error más caro de detectar a ojo.
        if "importe" in pedido:
            assert "% del total" not in r["dax"], (
                f"«{pedido}» se enganchó a una medida ajena en vez de a la "
                f"columna:\n{r['dax']}")

    # --- 5. el modelo quedó con las medidas nuevas ----------------------
    despues = mcp.json_de("resumen_modelo", {})
    assert despues["resumen"]["medidas"] == 2 + len(pedidos)

    # --- 6. explicar una de las medidas generadas ----------------------
    dax_yoy = next(m for t in despues["tablas"] for m in t["medidas"]
                   if "AA" in m or "año" in m.lower())
    explicacion = mcp.json_de("explicar_dax", {
        "dax": "CALCULATE ( SUM ( Ventas[Importe] ), "
               "SAMEPERIODLASTYEAR ( Calendario[Fecha] ) )"})
    assert explicacion["faltantes"] == [], \
        "el explicador marcó como inexistente algo que sí está en el modelo"
    assert explicacion["nivel"] in ("intermedio", "avanzado")
    assert dax_yoy  # la medida interanual quedó en el modelo

    # --- 7. exportar a .pbit -------------------------------------------
    destino = sintetico["carpeta"] / "salida" / "Sintetico.pbit"
    destino.parent.mkdir(parents=True, exist_ok=True)
    salida = mcp.herramienta("exportar", {"destino": str(destino),
                                          "formato": "pbit"})
    assert "Exportado" in salida
    assert destino.exists() and destino.stat().st_size > 5000

    # --- 8. reabrir el .pbit: nada se perdió en el viaje ----------------
    reabierto = modmod.cargar(destino)
    cat = catalogo.Catalogo.desde_modelo(reabierto["modelo"])
    assert cat.resumen()["medidas"] == 2 + len(pedidos)
    for nombre in aplicadas:
        assert cat.medida(nombre), f"[{nombre}] no sobrevivió al export"
    # …y el tablero llegó con sus visuales y filtros.
    secciones = reabierto["layout"]["sections"]
    assert len(secciones) == 2
    tipos = set()
    for seccion in secciones:
        for vc in seccion["visualContainers"]:
            tipos.add(json.loads(vc["config"])["singleVisual"]["visualType"])
    assert {"card", "slicer", "actionButton"} <= tipos
    assert tipos & {"lineChart", "clusteredBarChart", "matrix"}


def test_el_servidor_no_se_cae_con_pedidos_invalidos(mcp, sintetico):
    """Un agente manda cualquier cosa: el servidor tiene que seguir vivo."""
    mcp.llamar("initialize", {"protocolVersion": "2024-11-05"})

    # Herramienta inexistente.
    r = mcp.llamar("tools/call", {"name": "no_existe", "arguments": {}})
    assert r["result"]["isError"]

    # Operar sin modelo cargado.
    r = mcp.llamar("tools/call", {"name": "analizar_modelo", "arguments": {}})
    assert r["result"]["isError"]
    assert "cargar_modelo" in r["result"]["content"][0]["text"]

    # Archivo que no existe.
    r = mcp.llamar("tools/call", {"name": "cargar_modelo",
                                  "arguments": {"ruta": "/no/existe.pbit"}})
    assert r["result"]["isError"]

    # Método fuera del protocolo.
    r = mcp.llamar("metodo/inventado")
    assert r["error"]["code"] == -32601

    # Después de todo eso, el servidor sigue atendiendo.
    mcp.json_de("cargar_modelo", {"ruta": str(sintetico["bim"])})
    assert mcp.json_de("resumen_modelo", {})["resumen"]["tablas"] == 5


def test_el_agente_no_puede_inventar_columnas(mcp, sintetico):
    """
    La promesa central del producto: el DAX que sale está anclado al modelo.
    Un pedido sobre algo que no existe se rechaza, no se improvisa.
    """
    mcp.llamar("initialize", {"protocolVersion": "2024-11-05"})
    mcp.json_de("cargar_modelo", {"ruta": str(sintetico["bim"])})

    r = mcp.json_de("generar_dax", {"pedido": "total de facturación galáctica",
                                    "aplicar": True})
    assert not r["ok"]
    assert r["advertencias"]

    # Y el modelo quedó intacto: no se agregó nada a medias.
    assert mcp.json_de("resumen_modelo", {})["resumen"]["medidas"] == 2

    # El explicador también avisa cuando la expresión referencia lo que no hay.
    explicacion = mcp.json_de("explicar_dax",
                              {"dax": "SUM ( Fantasma[NoExiste] )"})
    assert explicacion["faltantes"]
