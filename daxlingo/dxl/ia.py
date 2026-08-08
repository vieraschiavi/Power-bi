"""
MV DAX Lab · Usos de alto nivel de la IA.

El transporte multi-proveedor vive en `proveedores_ia.py`; acá quedan los
prompts y las funciones de dominio (opinión sobre el modelo, resolución de
una consulta con el catálogo como contexto). Se mantiene `consultar()` como
alias para que el resto del código no dependa del módulo de transporte.
"""
from __future__ import annotations

from .proveedores_ia import (  # noqa: F401 — reexportado a propósito
    AGENTES_MCP, MCP_REMOTO_POWERBI, PROVEEDOR_DEFECTO, PROVEEDORES,
    clave_de, config_mcp, config_mcp_texto, consultar, hay_clave,
    modelo_defecto, modelos_de, necesita_clave, probar_conexion,
)

SISTEMA_DAX = (
    "Sos un experto senior en Power BI: DAX, modelado tabular, Power Query "
    "(M), visualización y Microsoft Fabric. Respondés claro y al grano, en el "
    "idioma en el que te escriben. Cuando te piden una medida o una columna "
    "calculada, primero explicás paso a paso por qué la expresión es esa "
    "—qué hace el contexto de filtro— y después devolvés el DAX en un bloque "
    "```dax con el formato «Nombre = expresión». Si es columna calculada lo "
    "decís explícitamente y aclarás la tabla. Nunca inventás columnas: si "
    "falta información del modelo, lo decís. Cerrás siempre con una línea "
    "«Siguiente paso:» concreta."
)


def analizar_modelo_ia(resumen_catalogo: str, hallazgos: list[dict],
                       proveedor: str = PROVEEDOR_DEFECTO, modelo: str = "",
                       api_key: str | None = None, endpoint: str = "") -> str:
    """Opinión de consultor sobre el modelo: prioriza hallazgos y sugiere."""
    texto_hallazgos = "\n".join(
        f"- [{h['severidad']}] {h['regla']}: {h['objeto']} — {h['detalle']}"
        for h in hallazgos[:30]) or "(sin hallazgos)"
    pregunta = (
        "Catálogo del modelo:\n" + resumen_catalogo +
        "\n\nHallazgos del analizador de buenas prácticas:\n" +
        texto_hallazgos +
        "\n\nComo consultor senior: 1) ¿qué 3 cosas arreglarías primero y por "
        "qué?, 2) ¿qué medidas típicas le faltan a este modelo?, 3) ¿algún "
        "riesgo de resultados incorrectos (no solo estética)?")
    return consultar([{"role": "user", "content": pregunta}],
                     sistema=SISTEMA_DAX, proveedor=proveedor, modelo=modelo,
                     api_key=api_key, endpoint=endpoint)


def resolver_consulta(pregunta: str, contexto_catalogo: str = "",
                      proveedor: str = PROVEEDOR_DEFECTO, modelo: str = "",
                      api_key: str | None = None, endpoint: str = "") -> str:
    """Consulta libre con el catálogo del modelo como contexto."""
    contenido = (f"{contexto_catalogo}\n\n{pregunta}" if contexto_catalogo
                 else pregunta)
    return consultar([{"role": "user", "content": contenido}],
                     sistema=SISTEMA_DAX, proveedor=proveedor, modelo=modelo,
                     api_key=api_key, endpoint=endpoint)
