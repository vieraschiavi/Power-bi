# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Las herramientas del analista Power BI moderno, operativas.

Registro de las 10+ herramientas del stack (Desktop, Power Query, Service,
Bravo, DAX Studio, Tabular Editor, ALM Toolkit, VS Code + PBIP, Fabric y el
MCP de modelado de Power BI) con acciones concretas desde la plataforma:
detectar la instalación local y exportar el modelo en el formato que cada una
abre. La configuración MCP para agentes de IA vive en `proveedores_ia.py`
(soporta varios agentes: Claude, ChatGPT/Codex, Copilot, Gemini).

No todas se detectan igual, y por eso cada una declara su `tipo`:

  escritorio    se instala y se busca (registro de Windows, PATH, rutas)
  web           es un sitio: no hay nada que detectar
  dentro_de:X   viene adentro de otra (Power Query vive en Desktop)
  config        no es un programa sino un archivo que esta app genera (MCP)

Antes se les aplicaba la detección de escritorio a las diez, así que la
pestaña mostraba «no detectada acá» hasta para Power BI Service y Fabric, que
son páginas web. Un semáforo en rojo sobre algo que no se instala no informa:
hace dudar de los otros nueve.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

HERRAMIENTAS: list[dict] = [
    {
        "clave": "desktop", "tipo": "escritorio", "exe": "PBIDesktop.exe", "nombre": "Power BI Desktop",
        "etapa": "01 · Crear", "descripcion": "Informes y modelos.",
        "url": "https://www.microsoft.com/download/details.aspx?id=58494",
        "rutas": [r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
                  r"C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_*\bin\PBIDesktop.exe"],
        "integracion": "Los .pbit y PBIP que exporta esta plataforma se abren "
                       "con doble clic y se guardan como .pbix.",
    },
    {
        "clave": "powerquery", "tipo": "dentro_de:desktop", "nombre": "Power Query",
        "etapa": "01 · Crear", "descripcion": "Transforma datos antes del modelo.",
        "url": "https://learn.microsoft.com/power-query/",
        "rutas": [],
        "integracion": "Las particiones M del modelo cargado se ven en la "
                       "pestaña Modelo; el analizador sugiere mover columnas "
                       "calculadas a Power Query.",
    },
    {
        "clave": "service", "tipo": "web", "nombre": "Power BI Service",
        "etapa": "02 · Operar", "descripcion": "Publica y gobierna.",
        "url": "https://app.powerbi.com",
        "rutas": [],
        "integracion": "El PBIP exportado se publica vía Git integration o "
                       "subiendo el .pbix guardado desde Desktop.",
    },
    {
        "clave": "bravo", "tipo": "escritorio", "exe": "Bravo.exe", "nombre": "Bravo",
        "etapa": "02 · Operar", "descripcion": "Revisa el modelo (SQLBI).",
        "url": "https://bravo.bi",
        "rutas": [r"C:\Program Files\Bravo for Power BI\Bravo.exe"],
        "integracion": "Exportá el modelo como .pbit, abrilo en Desktop y "
                       "conectá Bravo a esa instancia para analizar tamaño y "
                       "formatear el DAX.",
    },
    {
        "clave": "daxstudio", "tipo": "escritorio", "exe": "DaxStudio.exe", "nombre": "DAX Studio",
        "etapa": "03 · Modelar", "descripcion": "Mide y optimiza consultas DAX.",
        "url": "https://daxstudio.org",
        "rutas": [r"C:\Program Files\DAX Studio\DaxStudio.exe"],
        "integracion": "Acción «Exportar medidas .dax»: todas las medidas del "
                       "modelo en un archivo listo para pegar y medir "
                       "(Server Timings) en DAX Studio.",
    },
    {
        "clave": "tabulareditor", "tipo": "escritorio", "exe": "TabularEditor.exe", "nombre": "Tabular Editor",
        "etapa": "03 · Modelar", "descripcion": "Modelado avanzado y BPA.",
        "url": "https://tabulareditor.com",
        "rutas": [r"C:\Program Files (x86)\Tabular Editor\TabularEditor.exe",
                  r"C:\Program Files\Tabular Editor 3\TabularEditor3.exe"],
        "integracion": "Acción «Exportar model.bim»: Tabular Editor lo abre "
                       "directo (File → Open → From File) con todo lo "
                       "transformado acá.",
    },
    {
        "clave": "almtoolkit", "tipo": "escritorio", "exe": "ALMTOolkit.exe", "nombre": "ALM Toolkit",
        "etapa": "04 · Industrializar", "descripcion": "Compara y despliega.",
        "url": "http://alm-toolkit.com",
        "rutas": [r"C:\Program Files (x86)\ALM Toolkit\AlmToolkit.exe"],
        "integracion": "Exportá dos versiones del modelo (antes/después de "
                       "las transformaciones) y comparalas como source y "
                       "target en ALM Toolkit.",
    },
    {
        "clave": "vscode", "tipo": "escritorio", "exe": "Code.exe", "nombre": "VS Code + PBIP",
        "etapa": "04 · Industrializar", "descripcion": "Versiona como código.",
        "url": "https://code.visualstudio.com",
        "rutas": [r"C:\Program Files\Microsoft VS Code\Code.exe"],
        "integracion": "El export PBIP es texto plano (TMSL + report.json): "
                       "diff, blame y PRs como cualquier código.",
    },
    {
        "clave": "fabric", "tipo": "web", "nombre": "Microsoft Fabric",
        "etapa": "05 · Escalar con IA", "descripcion": "Datos y analítica.",
        "url": "https://app.fabric.microsoft.com",
        "rutas": [],
        "integracion": "Pestaña Fabric: publicación directa por API REST "
                       "(token BYOK) o vía integración Git del PBIP.",
    },
    {
        "clave": "mcp", "tipo": "config", "nombre": "Power BI MCP (local + remoto)",
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


def detectar(herramienta: dict) -> str | None:
    """Ruta local si la herramienta está instalada (Windows); si no, None.

    Tres vías, de la más barata a la más cara. Las rutas fijas solas no
    alcanzaban: DAX Studio y Tabular Editor se instalan por usuario en
    %LOCALAPPDATA% tanto como en Archivos de programa, y cualquiera puede
    elegir otra carpeta en el instalador. El registro es el que sabe dónde
    quedó de verdad.
    """
    # 1. las rutas conocidas
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

    # 2. el registro de Windows (App Paths: donde Windows anota los .exe)
    exe = herramienta.get("exe")
    if exe:
        ruta = _desde_registro(exe)
        if ruta:
            return ruta
        # 3. el PATH — cubre VS Code, que se agrega solo, y las portables
        desde_path = shutil.which(Path(exe).stem)
        if desde_path:
            return desde_path
    return None


def _desde_registro(exe: str) -> str | None:
    """Consulta `App Paths` del registro. Fuera de Windows devuelve None.

    Windows anota ahí el ejecutable de cada programa instalado, sin importar
    en qué carpeta lo pusieron. Es la misma clave que hace que `start bravo`
    funcione desde cualquier lado.
    """
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return None  # no es Windows: no hay registro que consultar

    sub = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{Path(exe).name}"
    for raiz in (getattr(winreg, "HKEY_CURRENT_USER"),
                 getattr(winreg, "HKEY_LOCAL_MACHINE")):
        try:
            with winreg.OpenKey(raiz, sub) as k:
                valor = winreg.QueryValueEx(k, "")[0]
                if valor and Path(valor).exists():
                    return str(valor)
        except OSError:
            continue
    return None


def estado(herramienta: dict, contexto: dict | None = None) -> dict:
    """Estado de una herramienta para mostrar en la UI.

    Devuelve `{"clave", "nivel", "detalle"}` donde `nivel` es uno de:
    `instalada`, `falta`, `web`, `incluida`, `lista` o `sin_soporte`.

    Existe porque la pestaña mostraba «no detectada acá» para las diez, y en
    seis de ellas eso era directamente falso: Power BI Service y Fabric son
    SITIOS —no hay nada que instalar—, Power Query viene adentro de Desktop, y
    el MCP no es un programa sino un archivo de configuración que esta misma
    app genera. Un semáforo que dice «no» sobre algo que no se instala no es
    un estado: es ruido que hace dudar de todo lo demás.
    """
    contexto = contexto or {}
    tipo = herramienta.get("tipo", "escritorio")

    if tipo == "web":
        return {"clave": herramienta["clave"], "nivel": "web", "detalle": None}

    if tipo == "config":
        return {"clave": herramienta["clave"], "nivel": "lista", "detalle": None}

    if tipo.startswith("dentro_de:"):
        anfitrion = tipo.split(":", 1)[1]
        # Power Query no se instala aparte: si está Desktop, está. Y si su
        # anfitriona no se puede ni buscar en este sistema, hereda eso — decir
        # «falta» en Linux sugeriría que hay algo que instalar, y no lo hay.
        if not _es_windows():
            return {"clave": herramienta["clave"], "nivel": "sin_soporte",
                    "detalle": None}
        return {"clave": herramienta["clave"],
                "nivel": "incluida" if contexto.get(anfitrion) else "falta",
                "detalle": anfitrion}

    if not _es_windows():
        # Decir «no detectada» en Linux/Mac sugiere que falta instalarla,
        # cuando el punto es que estas herramientas son de Windows.
        return {"clave": herramienta["clave"], "nivel": "sin_soporte",
                "detalle": None}

    ruta = detectar(herramienta)
    return {"clave": herramienta["clave"],
            "nivel": "instalada" if ruta else "falta", "detalle": ruta}


def _es_windows() -> bool:
    return os.name == "nt"


def estados(contexto_extra: dict | None = None) -> dict[str, dict]:
    """El estado de las diez, resuelto en el orden correcto.

    Las que viven adentro de otra (Power Query) necesitan saber si su
    anfitriona está: por eso primero se resuelven las de escritorio.
    """
    resueltos: dict[str, dict] = {}
    instaladas: dict[str, bool] = dict(contexto_extra or {})

    for h in HERRAMIENTAS:
        if not h.get("tipo", "escritorio").startswith("dentro_de:"):
            e = estado(h)
            resueltos[h["clave"]] = e
            instaladas[h["clave"]] = e["nivel"] == "instalada"
    for h in HERRAMIENTAS:
        if h.get("tipo", "").startswith("dentro_de:"):
            resueltos[h["clave"]] = estado(h, instaladas)
    return resueltos


def texto_medidas_dax(cat) -> str:
    """Todas las medidas del catálogo como texto .dax, sin tocar el disco."""
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
    return "\n".join(lineas)


def exportar_medidas_dax(cat, destino: str | Path) -> Path:
    """Todas las medidas del catálogo en un .dax para DAX Studio / revisión."""
    destino = Path(destino)
    destino.write_text(texto_medidas_dax(cat), encoding="utf-8")
    return destino
