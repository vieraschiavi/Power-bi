"""
MV DAX Lab · Cliente de IA (Claude) compartido por toda la plataforma.

BYOK: la clave sale de ANTHROPIC_API_KEY (entorno) o de la Configuración de
la app; nunca se guarda en el repo. El modelo es elegible por el usuario y
hay cadena de fallback: si el primero está saturado se prueba el siguiente,
con reintentos y espera creciente — mismo criterio que el overlay: un error
de saturación se reintenta, una clave mala no (esperar no la arregla).

Sin la clave, todo lo demás de la plataforma funciona igual (motor de reglas,
analizador, explicador, export). La IA es aditiva, nunca bloqueante.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

# Modelos ofrecidos en la app, del más capaz al más económico. El primero de
# la lista elegida es el principal; los siguientes son fallback.
MODELOS_CLAUDE = [
    ("claude-opus-5", "Opus 5 — máxima calidad"),
    ("claude-sonnet-5", "Sonnet 5 — equilibrio calidad/costo"),
    ("claude-haiku-4-5-20251001", "Haiku 4.5 — rápido y económico"),
]
MODELO_DEFECTO = "claude-sonnet-5"
REINTENTOS_SATURADO = 2
ESPERA_BASE_S = 3


def clave_api(explicita: str | None = None) -> str:
    return (explicita or os.environ.get("ANTHROPIC_API_KEY", "")).strip()


def hay_clave(explicita: str | None = None) -> bool:
    return bool(clave_api(explicita))


def _llamar(modelo: str, mensajes: list[dict], sistema: str, api_key: str,
            max_tokens: int = 2048) -> str:
    cuerpo = json.dumps({
        "model": modelo,
        "max_tokens": max_tokens,
        "system": sistema,
        "messages": mensajes,
    }).encode()
    peticion = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=cuerpo,
        headers={"content-type": "application/json",
                 "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"},
    )
    with urllib.request.urlopen(peticion, timeout=120) as resp:
        datos = json.loads(resp.read())
    return "".join(b.get("text", "") for b in datos.get("content", []))


def _es_saturacion(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (429, 500, 502, 503, 529)
    return isinstance(exc, (urllib.error.URLError, TimeoutError))


def consultar(mensajes: list[dict], sistema: str = "",
              modelo: str = MODELO_DEFECTO, api_key: str | None = None,
              max_tokens: int = 2048,
              en_progreso=None) -> str:
    """
    Llama a Claude con fallback de modelos y reintentos ante saturación.
    `en_progreso(texto)` — callback opcional para informar reintentos.
    """
    clave = clave_api(api_key)
    if not clave:
        raise RuntimeError(
            "Falta la API key de Anthropic. Configurala en la pestaña "
            "Configuración o exportá ANTHROPIC_API_KEY.")

    cadena = [modelo] + [m for m, _ in MODELOS_CLAUDE if m != modelo]
    ultimo_error: Exception | None = None
    for candidato in cadena:
        for intento in range(REINTENTOS_SATURADO + 1):
            try:
                return _llamar(candidato, mensajes, sistema, clave, max_tokens)
            except Exception as exc:  # noqa: BLE001 — decidimos por tipo abajo
                ultimo_error = exc
                if not _es_saturacion(exc):
                    raise  # clave mala / request inválido: reintentar no ayuda
                if intento < REINTENTOS_SATURADO:
                    espera = ESPERA_BASE_S * (intento + 1)
                    if en_progreso:
                        en_progreso(f"[{candidato} saturado, reintento "
                                    f"{intento + 1}/{REINTENTOS_SATURADO} "
                                    f"en {espera}s…]")
                    time.sleep(espera)
        if en_progreso:
            en_progreso(f"[{candidato} sigue sin responder → probando el "
                        "siguiente modelo]")
    raise RuntimeError(f"Ningún modelo respondió: {ultimo_error}")


# ==========================================================================
# Usos de alto nivel
# ==========================================================================
SISTEMA_DAX = (
    "Sos un experto en Power BI, DAX, modelado tabular y Microsoft Fabric. "
    "Respondés en español rioplatense, claro y al grano. Cuando te piden una "
    "medida o columna calculada devolvés el DAX en un bloque de código y "
    "explicás paso a paso por qué la expresión es esa. Nunca inventás "
    "columnas: si falta información del modelo, lo decís."
)


def analizar_modelo_ia(resumen_catalogo: str, hallazgos: list[dict],
                       modelo: str = MODELO_DEFECTO,
                       api_key: str | None = None) -> str:
    """Opinión de Claude sobre el modelo: prioriza los hallazgos y sugiere."""
    texto_hallazgos = "\n".join(
        f"- [{h['severidad']}] {h['regla']}: {h['objeto']} — {h['detalle']}"
        for h in hallazgos[:30]) or "(sin hallazgos)"
    pregunta = (
        "Catálogo del modelo:\n" + resumen_catalogo +
        "\n\nHallazgos del analizador de buenas prácticas:\n" +
        texto_hallazgos +
        "\n\nComo consultor senior: 1) ¿qué 3 cosas arreglarías primero y "
        "por qué?, 2) ¿qué medidas típicas le faltan a este modelo?, "
        "3) ¿algún riesgo de resultados incorrectos (no solo estética)?")
    return consultar([{"role": "user", "content": pregunta}],
                     sistema=SISTEMA_DAX, modelo=modelo, api_key=api_key)
