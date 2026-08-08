"""
MV DAX Lab · Las herramientas del analista Power BI moderno, operativas.

Registro de las 10+ herramientas del stack (Desktop, Power Query, Service,
Bravo, DAX Studio, Tabular Editor, ALM Toolkit, VS Code + PBIP, Fabric y el
MCP de modelado de Power BI) con acciones concretas desde la plataforma:
detectar la instalación local, exportar el modelo en el formato que cada una
abre, y generar la configuración MCP para agentes de IA.

La detección de rutas es de Windows (donde viven estas herramientas); en
Linux/Mac devuelve None y la app lo muestra como «no detectada acá».
"""
from __future__ import annotations

import json
from pathlib import Path

HERRAMIENTAS: list[dict] = [
    {
        "clave": "desktop", "nombre": "Power BI Desktop",
        "etapa": "01 · Crear", "descripcion": "Informes y modelos.",
        "url": "https://www.microsoft.com/download/details.aspx?id=58494",
        "rutas": [r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
                  r"C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_*\bin\PBIDesktop.exe"],
        "integracion": "Los .pbit y PBIP que exporta esta plataforma se abren "
                       "con doble clic y se guardan como .pbix.",
    },
    {
        "clave": "powerquery", "nombre": "Power Query",
        "etapa": "01 · Crear", "descripcion": "Transforma datos antes del modelo.",
        "url": "https://learn.microsoft.com/power-query/",
        "rutas": [],
        "integracion": "Las particiones M del modelo cargado se ven en la "
                       "pestaña Modelo; el analizador sugiere mover columnas "
                       "calculadas a Power Query.",
    },
    {
        "clave": "service", "nombre": "Power BI Service",
        "etapa": "02 · Operar", "descripcion": "Publica y gobierna.",
        "url": "https://app.powerbi.com",
        "rutas": [],
        "integracion": "El PBIP exportado se publica vía Git integration o "
                       "subiendo el .pbix guardado desde Desktop.",
    },
    {
        "clave": "bravo", "nombre": "Bravo",
        "etapa": "02 · Operar", "descripcion": "Revisa el modelo (SQLBI).",
        "url": "https://bravo.bi",
        "rutas": [r"C:\Program Files\Bravo for Power BI\Bravo.exe"],
        "integracion": "Exportá el modelo como .pbit, abrilo en Desktop y "
                       "conectá Bravo a esa instancia para analizar tamaño y "
                       "formatear el DAX.",
    },
    {
        "clave": "daxstudio", "nombre": "DAX Studio",
        "etapa": "03 · Modelar", "descripcion": "Mide y optimiza consultas DAX.",
        "url": "https://daxstudio.org",
        "rutas": [r"C:\Program Files\DAX Studio\DaxStudio.exe"],
        "integracion": "Acción «Exportar medidas .dax»: todas las medidas del "
                       "modelo en un archivo listo para pegar y medir "
                       "(Server Timings) en DAX Studio.",
    },
    {
        "clave": "tabulareditor", "nombre": "Tabular Editor",
        "etapa": "03 · Modelar", "descripcion": "Modelado avanzado y BPA.",
        "url": "https://tabulareditor.com",
        "rutas": [r"C:\Program Files (x86)\Tabular Editor\TabularEditor.exe",
                  r"C:\Program Files\Tabular Editor 3\TabularEditor3.exe"],
        "integracion": "Acción «Exportar model.bim»: Tabular Editor lo abre "
                       "directo (File → Open → From File) con todo lo "
                       "transformado acá.",
    },
    {
        "clave": "almtoolkit", "nombre": "ALM Toolkit",
        "etapa": "04 · Industrializar", "descripcion": "Compara y despliega.",
        "url": "http://alm-toolkit.com",
        "rutas": [r"C:\Program Files (x86)\ALM Toolkit\AlmToolkit.exe"],
        "integracion": "Exportá dos versiones del modelo (antes/después de "
                       "las transformaciones) y comparalas como source y "
                       "target en ALM Toolkit.",
    },
    {
        "clave": "vscode", "nombre": "VS Code + PBIP",
        "etapa": "04 · Industrializar", "descripcion": "Versiona como código.",
        "url": "https://code.visualstudio.com",
        "rutas": [r"C:\Program Files\Microsoft VS Code\Code.exe"],
        "integracion": "El export PBIP es texto plano (TMSL + report.json): "
                       "diff, blame y PRs como cualquier código.",
    },
    {
        "clave": "fabric", "nombre": "Microsoft Fabric",
        "etapa": "05 · Escalar con IA", "descripcion": "Datos y analítica.",
        "url": "https://app.fabric.microsoft.com",
        "rutas": [],
        "integracion": "Pestaña Fabric: publicación directa por API REST "
                       "(token BYOK) o vía integración Git del PBIP.",
    },
    {
        "clave": "mcp", "nombre": "Power BI MCP (local + remoto)",
        "etapa": "05 · Escalar con IA",
        "descripcion": "IA conectada al modelo (agentes).",
        "url": "https://learn.microsoft.com/power-bi/developer/mcp/"
               "remote-mcp-server-get-started",
        "rutas": [],
        "integracion": "Acción «Configuración MCP»: genera el .mcp.json con "
                       "el MCP remoto oficial de Power BI (Fabric, Entra "
                       "ID), el MCP local de modelado (Desktop/.pbix) y el "
                       "servidor MCP propio de esta plataforma (análisis, "
                       "NL→DAX, export).",
    },
]

# Endpoint del servidor MCP remoto oficial de Power BI (servicio Fabric).
# Autenticación: Microsoft Entra ID. Permite inspeccionar modelos, gestionar
# DAX en lenguaje natural y documentar modelos publicados, sin instalar nada.
MCP_REMOTO_POWERBI = "https://api.fabric.microsoft.com/v1/mcp/powerbi"


def detectar(herramienta: dict) -> str | None:
    """Ruta local si la herramienta está instalada (Windows); si no, None."""
    for patron in herramienta.get("rutas", []):
        p = Path(patron)
        if "*" in patron:
            base = Path(patron.split("*")[0]).parent
            resto = patron.split("\\")[-1]
            if base.exists():
                encontrados = list(base.glob(f"**/{resto}"))
                if encontrados:
                    return str(encontrados[0])
        elif p.exists():
            return str(p)
    return None


def exportar_medidas_dax(cat, destino: str | Path) -> Path:
    """Todas las medidas del catálogo en un .dax para DAX Studio / revisión."""
    destino = Path(destino)
    lineas = ["// Medidas exportadas por MV DAX Lab",
              f"// Modelo: {cat.nombre or '(sin nombre)'}", ""]
    for m in cat.medidas():
        lineas.append(f"// Tabla: {m['tabla']}"
                      + (f" · Carpeta: {m['carpeta']}" if m["carpeta"] else ""))
        if m["descripcion"]:
            lineas.append(f"// {m['descripcion']}")
        lineas.append(f"[{m['nombre']}] :=")
        lineas.append(m["expresion"])
        if m["formato"]:
            lineas.append(f'// formatString: "{m["formato"]}"')
        lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


def config_mcp(ruta_repo: str = ".") -> dict:
    """
    El .mcp.json para Claude Code / VS Code: el MCP oficial de modelado de
    Power BI (requiere Windows + Desktop) y el servidor MCP de esta
    plataforma (multiplataforma, sin dependencias).
    """
    return {
        "mcpServers": {
            "powerbi-remote": {
                "type": "http",
                "url": MCP_REMOTO_POWERBI,
                "comment": "MCP remoto oficial de Power BI (Fabric): "
                           "inspección de modelos publicados, gestión de "
                           "DAX y documentación automática. Requiere "
                           "autenticación Microsoft Entra ID — ver "
                           "learn.microsoft.com/power-bi/developer/mcp/"
                           "remote-mcp-server-get-started.",
            },
            "powerbi-modeling": {
                "command": "dotnet",
                "args": ["tool", "run", "powerbi-modeling-mcp"],
                "comment": "MCP local de Microsoft: crea/modifica tablas, "
                           "medidas y relaciones contra Power BI Desktop "
                           "(Windows).",
            },
            "mv-dax-lab": {
                "command": "python",
                "args": [f"{ruta_repo}/daxlingo/mcp/servidor.py"],
                "comment": "MCP de esta plataforma: cargar_modelo, analizar, "
                           "generar_dax, explicar_dax, exportar_pbit.",
            },
        },
    }


def config_mcp_texto(ruta_repo: str = ".") -> str:
    return json.dumps(config_mcp(ruta_repo), indent=2, ensure_ascii=False)
