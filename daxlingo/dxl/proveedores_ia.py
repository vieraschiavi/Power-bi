"""
MV DAX Lab · Multi-proveedor de IA (BYOK) y configuración MCP por agente.

Un solo `consultar()` para todos: Claude (Anthropic), ChatGPT (OpenAI),
Gemini (Google), Copilot (Azure OpenAI / GitHub Models), Groq, Mistral,
DeepSeek y Ollama local. Cada proveedor difiere en endpoint, headers y forma
del JSON; acá se normaliza a mensajes `{"role", "content"}` y respuesta de
texto plano.

Reglas de la casa:
  · Las claves son del usuario y viven en memoria de la sesión o en el
    entorno. Nunca se escriben en el repo ni se mandan a ningún lado que no
    sea el proveedor elegido.
  · La IA es aditiva: sin ninguna clave, el motor de reglas, el analizador,
    el explicador, la academia y el export funcionan igual.
  · Ante saturación se reintenta y se cae al siguiente modelo del proveedor;
    ante una clave inválida NO se reintenta (esperar no la arregla).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

REINTENTOS = 2
ESPERA_BASE_S = 3

# proveedor -> configuración. `modelos` va del más capaz al más económico:
# el primero es el principal y los siguientes son la cadena de fallback.
PROVEEDORES: dict[str, dict] = {
    "claude": {
        "nombre": "Claude (Anthropic)",
        "env": "ANTHROPIC_API_KEY",
        "url": "https://api.anthropic.com/v1/messages",
        "doc": "https://console.anthropic.com/settings/keys",
        "modelos": [
            ("claude-opus-5", "Opus 5 — máxima calidad"),
            ("claude-sonnet-5", "Sonnet 5 — equilibrio calidad/costo"),
            ("claude-haiku-4-5-20251001", "Haiku 4.5 — rápido y económico"),
        ],
    },
    "openai": {
        "nombre": "ChatGPT (OpenAI)",
        "env": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1/chat/completions",
        "doc": "https://platform.openai.com/api-keys",
        "modelos": [
            ("gpt-5", "GPT-5"),
            ("gpt-5-mini", "GPT-5 mini — económico"),
            ("gpt-4.1", "GPT-4.1"),
        ],
    },
    "gemini": {
        "nombre": "Gemini (Google)",
        "env": "GEMINI_API_KEY",
        "url": "https://generativelanguage.googleapis.com/v1beta/models",
        "doc": "https://aistudio.google.com/app/apikey",
        "modelos": [
            ("gemini-2.5-pro", "Gemini 2.5 Pro"),
            ("gemini-2.5-flash", "Gemini 2.5 Flash — rápido"),
        ],
    },
    "copilot": {
        "nombre": "Copilot / Azure OpenAI",
        "env": "AZURE_OPENAI_API_KEY",
        # El endpoint es propio de cada recurso de Azure: se completa con
        # AZURE_OPENAI_ENDPOINT (o el campo del formulario).
        "url": "",
        "doc": "https://learn.microsoft.com/azure/ai-services/openai/",
        "modelos": [
            ("gpt-5", "GPT-5 (deployment)"),
            ("gpt-4.1", "GPT-4.1 (deployment)"),
        ],
        "necesita_endpoint": True,
    },
    "groq": {
        "nombre": "Groq",
        "env": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "doc": "https://console.groq.com/keys",
        "modelos": [("llama-3.3-70b-versatile", "Llama 3.3 70B")],
    },
    "mistral": {
        "nombre": "Mistral",
        "env": "MISTRAL_API_KEY",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "doc": "https://console.mistral.ai/api-keys/",
        "modelos": [("mistral-large-latest", "Mistral Large")],
    },
    "deepseek": {
        "nombre": "DeepSeek",
        "env": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/chat/completions",
        "doc": "https://platform.deepseek.com/api_keys",
        "modelos": [("deepseek-chat", "DeepSeek Chat")],
    },
    "ollama": {
        "nombre": "Ollama (local, sin clave)",
        "env": "",
        "url": "http://localhost:11434/api/chat",
        "doc": "https://ollama.com",
        "modelos": [("llama3.1", "Llama 3.1 local"),
                    ("qwen2.5-coder", "Qwen2.5 Coder local")],
        "sin_clave": True,
    },
}

PROVEEDOR_DEFECTO = "claude"


def modelos_de(proveedor: str) -> list[tuple[str, str]]:
    return PROVEEDORES.get(proveedor, {}).get("modelos", [])


def modelo_defecto(proveedor: str) -> str:
    modelos = modelos_de(proveedor)
    return modelos[0][0] if modelos else ""


def clave_de(proveedor: str, explicita: str | None = None) -> str:
    if explicita:
        return explicita.strip()
    env = PROVEEDORES.get(proveedor, {}).get("env", "")
    return os.environ.get(env, "").strip() if env else ""


def necesita_clave(proveedor: str) -> bool:
    return not PROVEEDORES.get(proveedor, {}).get("sin_clave", False)


def hay_clave(proveedor: str, explicita: str | None = None) -> bool:
    if not necesita_clave(proveedor):
        return True
    return bool(clave_de(proveedor, explicita))


# ==========================================================================
# Armado de la petición por proveedor
# ==========================================================================
def _peticion(proveedor: str, modelo: str, mensajes: list[dict], sistema: str,
              api_key: str, max_tokens: int,
              endpoint: str = "") -> urllib.request.Request:
    cfg = PROVEEDORES[proveedor]

    if proveedor == "claude":
        cuerpo = {"model": modelo, "max_tokens": max_tokens,
                  "messages": mensajes}
        if sistema:
            cuerpo["system"] = sistema
        return urllib.request.Request(
            cfg["url"], data=json.dumps(cuerpo).encode(),
            headers={"content-type": "application/json",
                     "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"})

    if proveedor == "gemini":
        url = (f"{cfg['url']}/{modelo}:generateContent?key={api_key}")
        contenidos = [{"role": ("model" if m["role"] == "assistant"
                                else "user"),
                       "parts": [{"text": m["content"]}]}
                      for m in mensajes]
        cuerpo = {"contents": contenidos,
                  "generationConfig": {"maxOutputTokens": max_tokens}}
        if sistema:
            cuerpo["systemInstruction"] = {"parts": [{"text": sistema}]}
        return urllib.request.Request(
            url, data=json.dumps(cuerpo).encode(),
            headers={"content-type": "application/json"})

    if proveedor == "ollama":
        msgs = ([{"role": "system", "content": sistema}] if sistema else []) \
            + mensajes
        cuerpo = {"model": modelo, "messages": msgs, "stream": False}
        return urllib.request.Request(
            cfg["url"], data=json.dumps(cuerpo).encode(),
            headers={"content-type": "application/json"})

    if proveedor == "copilot":
        base = (endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")).rstrip("/")
        if not base:
            raise RuntimeError(
                "Copilot / Azure OpenAI necesita el endpoint de tu recurso "
                "(https://<recurso>.openai.azure.com).")
        version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
        url = (f"{base}/openai/deployments/{modelo}/chat/completions"
               f"?api-version={version}")
        msgs = ([{"role": "system", "content": sistema}] if sistema else []) \
            + mensajes
        cuerpo = {"messages": msgs, "max_tokens": max_tokens}
        return urllib.request.Request(
            url, data=json.dumps(cuerpo).encode(),
            headers={"content-type": "application/json", "api-key": api_key})

    # openai, groq, mistral, deepseek: todos hablan el dialecto OpenAI.
    msgs = ([{"role": "system", "content": sistema}] if sistema else []) \
        + mensajes
    cuerpo = {"model": modelo, "messages": msgs, "max_tokens": max_tokens}
    return urllib.request.Request(
        cfg["url"], data=json.dumps(cuerpo).encode(),
        headers={"content-type": "application/json",
                 "authorization": f"Bearer {api_key}"})


def _texto_respuesta(proveedor: str, datos: dict) -> str:
    if proveedor == "claude":
        return "".join(b.get("text", "") for b in datos.get("content", []))
    if proveedor == "gemini":
        candidatos = datos.get("candidates", [])
        if not candidatos:
            return ""
        partes = candidatos[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in partes)
    if proveedor == "ollama":
        return datos.get("message", {}).get("content", "")
    opciones = datos.get("choices", [])
    if not opciones:
        return ""
    return opciones[0].get("message", {}).get("content", "") or ""


def _es_saturacion(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 429, 500, 502, 503, 504, 529)
    return isinstance(exc, (urllib.error.URLError, TimeoutError))


# ==========================================================================
# API pública
# ==========================================================================
def consultar(mensajes: list[dict], sistema: str = "",
              proveedor: str = PROVEEDOR_DEFECTO, modelo: str = "",
              api_key: str | None = None, max_tokens: int = 2048,
              endpoint: str = "", en_progreso=None) -> str:
    """
    Consulta al proveedor elegido con fallback entre sus modelos.
    `en_progreso(texto)` recibe avisos de reintento (opcional).
    """
    if proveedor not in PROVEEDORES:
        raise ValueError(f"Proveedor desconocido: {proveedor}")
    clave = clave_de(proveedor, api_key)
    if necesita_clave(proveedor) and not clave:
        cfg = PROVEEDORES[proveedor]
        raise RuntimeError(
            f"Falta la API key de {cfg['nombre']}. Cargala en ⚙️ "
            f"Configuración o exportá {cfg['env']}. Obtenela en {cfg['doc']}.")

    principal = modelo or modelo_defecto(proveedor)
    cadena = [principal] + [m for m, _ in modelos_de(proveedor)
                            if m != principal]
    ultimo: Exception | None = None

    for i, candidato in enumerate(cadena):
        for intento in range(REINTENTOS + 1):
            try:
                peticion = _peticion(proveedor, candidato, mensajes, sistema,
                                     clave, max_tokens, endpoint)
                with urllib.request.urlopen(peticion, timeout=120) as resp:
                    datos = json.loads(resp.read())
                return _texto_respuesta(proveedor, datos)
            except Exception as exc:  # noqa: BLE001 — se decide por tipo
                ultimo = exc
                if not _es_saturacion(exc):
                    raise
                if intento < REINTENTOS:
                    espera = ESPERA_BASE_S * (intento + 1)
                    if en_progreso:
                        en_progreso(f"[{candidato} saturado, reintento "
                                    f"{intento + 1}/{REINTENTOS} en "
                                    f"{espera}s…]")
                    time.sleep(espera)
        if en_progreso and i < len(cadena) - 1:
            en_progreso(f"[{candidato} sigue sin responder → probando "
                        f"{cadena[i + 1]}]")
    raise RuntimeError(f"Ningún modelo de {PROVEEDORES[proveedor]['nombre']} "
                       f"respondió: {ultimo}")


def probar_conexion(proveedor: str, modelo: str = "",
                    api_key: str | None = None, endpoint: str = "") -> str:
    """Ping mínimo para el botón «Probar la conexión» de Configuración."""
    respuesta = consultar(
        [{"role": "user", "content": "Respondé solamente: OK"}],
        sistema="Sos un verificador de conexión. Respondé solo «OK».",
        proveedor=proveedor, modelo=modelo, api_key=api_key,
        max_tokens=16, endpoint=endpoint)
    return respuesta.strip()


# ==========================================================================
# Configuración MCP por agente
# ==========================================================================
MCP_REMOTO_POWERBI = "https://api.fabric.microsoft.com/v1/mcp/powerbi"

# Cada agente lee su config de un archivo y una clave distintas. La forma del
# servidor (command/args o type/url) es la misma en todos.
AGENTES_MCP = {
    "claude": {"nombre": "Claude Code / Claude Desktop",
               "archivo": ".mcp.json", "clave": "mcpServers"},
    "openai": {"nombre": "ChatGPT / Codex CLI",
               "archivo": "mcp.json", "clave": "mcpServers"},
    "copilot": {"nombre": "GitHub Copilot (VS Code)",
                "archivo": ".vscode/mcp.json", "clave": "servers"},
    "gemini": {"nombre": "Gemini CLI",
               "archivo": ".gemini/settings.json", "clave": "mcpServers"},
}


def config_mcp(agente: str = "claude", ruta_repo: str = ".") -> dict:
    """
    Config MCP lista para el agente elegido, con los tres servidores:
    el remoto oficial de Power BI, el local de modelado y el de esta app.
    """
    clave = AGENTES_MCP.get(agente, AGENTES_MCP["claude"])["clave"]
    servidores = {
        "powerbi-remote": {
            "type": "http",
            "url": MCP_REMOTO_POWERBI,
            "comment": "MCP remoto oficial de Power BI (Fabric): inspección "
                       "de modelos publicados, gestión de DAX y "
                       "documentación. Autenticación Microsoft Entra ID.",
        },
        "powerbi-modeling": {
            "command": "dotnet",
            "args": ["tool", "run", "powerbi-modeling-mcp"],
            "comment": "MCP local de Microsoft contra Power BI Desktop "
                       "(Windows): tablas, medidas y relaciones.",
        },
        "mv-dax-lab": {
            "command": "python",
            "args": [f"{ruta_repo}/daxlingo/mcp/servidor.py"],
            "comment": "MCP de esta plataforma: cargar_modelo, "
                       "analizar_modelo, generar_dax, explicar_dax, "
                       "exportar. Trabaja sobre archivos, sin credenciales.",
        },
    }
    return {clave: servidores}


def config_mcp_texto(agente: str = "claude", ruta_repo: str = ".") -> str:
    return json.dumps(config_mcp(agente, ruta_repo), indent=2,
                      ensure_ascii=False)
