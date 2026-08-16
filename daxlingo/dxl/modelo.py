# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Carga y escritura de archivos de Power BI.

Formatos que entiende:

  · .pbit  — Power BI Template. Es un zip con el modelo tabular (TMSL) en
             `DataModelSchema` y el reporte en `Report/Layout`, ambos en
             UTF-16 LE con BOM. Se lee y se escribe completo.
  · PBIP   — Power BI Project. Carpetas *.SemanticModel (model.bim) y
             *.Report (report.json). Se lee y se escribe completo.
  · .bim   — el modelo TMSL suelto (Tabular Editor lo abre directo).
  · .pbix  — se lee el LAYOUT del reporte y, de ahí, un catálogo parcial.
             El modelo tabular de un .pbix viaja en `DataModel`, un binario
             comprimido propietario de Analysis Services (Xpress9) que no se
             puede abrir desde afuera de Power BI. No se inventa lo que no se
             puede leer: se avisa y se ofrece el camino .pbit/PBIP.

Todas las funciones trabajan sobre dicts planos de Python (el JSON de TMSL
tal cual), sin clases intermedias: lo que se carga se puede volver a escribir.
"""
from __future__ import annotations

import json
import uuid
import zipfile
from pathlib import Path


# ==========================================================================
# Codificación interna de .pbit / .pbix
# ==========================================================================
def _u16(texto: str) -> bytes:
    """Las partes internas de un .pbit van en UTF-16 LE con BOM."""
    return b"\xff\xfe" + texto.encode("utf-16-le")


def _des16(crudo: bytes) -> str:
    """Decodifica una parte interna, tolerando BOM UTF-16 o UTF-8 plano."""
    if crudo[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return crudo.decode("utf-16")
    if crudo[:3] == b"\xef\xbb\xbf":
        return crudo[3:].decode("utf-8")
    # Algunas herramientas escriben UTF-16 sin BOM; probamos y caemos a UTF-8.
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError:
        texto = crudo.decode("utf-16-le")
    return texto


def _content_types(con_datamashup: bool = False) -> str:
    """El [Content_Types].xml del .pbit, declarando las partes que se escriben.

    Se arma en función de lo que realmente va adentro: declarar una parte que
    no existe —o escribir una sin declararla— es de las cosas que hacen que
    Power BI rechace el archivo como corrupto.
    """
    partes = ["/Version", "/Report/Layout", "/Settings", "/Metadata",
              "/DataModelSchema"]
    if con_datamashup:
        partes.append("/DataMashup")
    overrides = "".join(f'<Override PartName="{p}" ContentType="" />'
                        for p in partes)
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="json" ContentType="" />'
            f"{overrides}</Types>")


# Compatibilidad: algunos módulos importaban la constante.
CONTENT_TYPES = _content_types()


# ==========================================================================
# Carga
# ==========================================================================
def cargar(ruta: str | Path) -> dict:
    """
    Carga un archivo/carpeta de Power BI y devuelve un dict con:

      formato       'pbit' | 'pbip' | 'bim' | 'pbix'
      modelo        el TMSL completo (dict) o None si no se pudo leer
      layout        el layout del reporte (dict) o None
      advertencias  lista de strings con lo que NO se pudo leer y por qué

    Un archivo corrupto o truncado (zip roto, JSON a medio escribir) no tira
    un traceback crudo — cae en `advertencias` como cualquier otro «no se
    pudo leer», que es lo que ya hacía `_cargar_pbip` para el caso de un
    model.bim faltante. Sin esto, subir un .pbit corrupto en la app rompía
    la pestaña con un `JSONDecodeError` sin traducir en vez de avisar.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe: {ruta}")

    sufijo = ruta.suffix.lower()
    if sufijo == ".pbit":
        formato, cargador = "pbit", _cargar_pbit
    elif sufijo == ".pbix":
        formato, cargador = "pbix", _cargar_pbix
    elif sufijo == ".bim" or (sufijo == ".json" and ruta.name != "report.json"):
        formato, cargador = "bim", _cargar_bim
    elif sufijo == ".pbip" or ruta.is_dir():
        formato, cargador = "pbip", _cargar_pbip
    else:
        raise ValueError(
            f"Formato no reconocido: {ruta.name}. "
            "Se aceptan .pbit, .pbix, .bim, .pbip o una carpeta PBIP."
        )
    try:
        return cargador(ruta)
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError,
            KeyError, OSError) as exc:
        return {"formato": formato, "modelo": None, "layout": None,
                "advertencias": [
                    f"No se pudo leer {ruta.name} ({type(exc).__name__}): "
                    f"{exc}. ¿El archivo está corrupto o incompleto?"],
                "origen": str(ruta)}


def _cargar_pbit(ruta: Path) -> dict:
    resultado = {"formato": "pbit", "modelo": None, "layout": None,
                 "datamashup": None, "advertencias": [], "origen": str(ruta)}
    with zipfile.ZipFile(ruta) as z:
        nombres = set(z.namelist())
        if "DataModelSchema" in nombres:
            resultado["modelo"] = json.loads(_des16(z.read("DataModelSchema")))
        else:
            resultado["advertencias"].append(
                "El .pbit no trae DataModelSchema — ¿está corrupto?")
        if "Report/Layout" in nombres:
            resultado["layout"] = json.loads(_des16(z.read("Report/Layout")))
        resultado["datamashup"] = _leer_datamashup(z, nombres)
    return resultado


def _leer_datamashup(z: zipfile.ZipFile, nombres: set) -> bytes | None:
    """Los bytes crudos de la parte `DataMashup`, si el archivo la trae.

    Ahí viven las consultas de Power Query (el código M) y las credenciales
    de conexión. Es un binario propietario: no se interpreta, se copia tal
    cual. Antes ni se leía, así que un modelo que entraba con sus consultas
    salía sin ellas y en Power BI no quedaba de dónde refrescar los datos —
    la pérdida era silenciosa, nadie la veía hasta abrir el archivo.
    """
    for nombre in ("DataMashup", "Formulas/Section1.m"):
        if nombre in nombres:
            return z.read(nombre)
    return None


def _cargar_pbix(ruta: Path) -> dict:
    resultado = {"formato": "pbix", "modelo": None, "layout": None,
                 "advertencias": [], "origen": str(ruta)}
    with zipfile.ZipFile(ruta) as z:
        nombres = set(z.namelist())
        # Algunos .pbix con modelo en vivo (live connection) sí traen el
        # esquema en claro. Si está, lo aprovechamos.
        if "DataModelSchema" in nombres:
            resultado["modelo"] = json.loads(_des16(z.read("DataModelSchema")))
        elif "DataModel" in nombres:
            resultado["advertencias"].append(
                "El modelo tabular del .pbix viaja comprimido en un binario "
                "propietario de Analysis Services y no se puede leer desde "
                "afuera de Power BI. Se leyó el reporte (páginas y visuales) y "
                "un catálogo parcial de lo que los visuales referencian. Para "
                "el modelo completo: en Power BI Desktop, Archivo → Exportar → "
                "Plantilla de Power BI (.pbit), o guardar como Proyecto (PBIP)."
            )
        if "Report/Layout" in nombres:
            resultado["layout"] = json.loads(_des16(z.read("Report/Layout")))
        elif "Report/definition.pbir" in nombres:
            resultado["advertencias"].append(
                "El reporte usa el formato PBIR mejorado; abrilo como PBIP "
                "para editarlo acá."
            )
    return resultado


def _cargar_bim(ruta: Path) -> dict:
    modelo = json.loads(ruta.read_text(encoding="utf-8-sig"))
    # Un model.bim es el objeto database de TMSL: {name, compatibilityLevel,
    # model:{...}}. Si vino el `model` pelado, lo envolvemos para uniformar.
    if "model" not in modelo and "tables" in modelo:
        modelo = {"name": ruta.stem, "compatibilityLevel": 1567, "model": modelo}
    return {"formato": "bim", "modelo": modelo, "layout": None,
            "advertencias": [], "origen": str(ruta)}


def _cargar_pbip(ruta: Path) -> dict:
    """`ruta` puede ser el archivo .pbip o la carpeta que lo contiene."""
    base = ruta.parent if ruta.suffix.lower() == ".pbip" else ruta
    resultado = {"formato": "pbip", "modelo": None, "layout": None,
                 "advertencias": [], "origen": str(ruta)}

    bims = sorted(base.glob("*.SemanticModel/model.bim"))
    if ruta.suffix.lower() == ".pbip":
        # Si nos dieron el .pbip puntual, priorizamos su modelo homónimo.
        propio = base / f"{ruta.stem}.SemanticModel" / "model.bim"
        if propio.exists():
            bims = [propio]
    if bims:
        resultado["modelo"] = json.loads(bims[0].read_text(encoding="utf-8-sig"))
    else:
        tmdl = sorted(base.glob("*.SemanticModel/definition/*.tmdl"))
        if tmdl:
            resultado["advertencias"].append(
                "El modelo está en formato TMDL (carpeta definition/). Este "
                "motor lee model.bim (TMSL). En Power BI Desktop: Opciones → "
                "Vista previa → desactivar TMDL, o exportá un .pbit."
            )
        else:
            resultado["advertencias"].append(
                "No se encontró *.SemanticModel/model.bim junto al .pbip.")

    reportes = sorted(base.glob("*.Report/report.json"))
    if ruta.suffix.lower() == ".pbip":
        propio = base / f"{ruta.stem}.Report" / "report.json"
        if propio.exists():
            reportes = [propio]
    if reportes:
        resultado["layout"] = json.loads(reportes[0].read_text(encoding="utf-8-sig"))
    return resultado


# ==========================================================================
# Escritura
# ==========================================================================
def exportar_pbit(modelo: dict, layout: dict | None, destino: str | Path,
                  descripcion: str = "", datamashup: bytes | None = None) -> Path:
    """Escribe un .pbit para abrir con doble clic en Power BI Desktop.

    `datamashup`: los bytes de la parte homónima del archivo de origen, si el
    modelo vino de un .pbit/.pbix que la traía (`cargar()` la devuelve en la
    clave `datamashup`). Ahí están las consultas de Power Query. Sin ella el
    archivo abre igual, pero el modelo queda sin origen de datos: no hay nada
    que refrescar. Se copia tal cual, no se interpreta — es un binario
    propietario de Microsoft.

    Para un modelo armado desde cero en la app no hay DataMashup que copiar, y
    ahí el .pbit sale sin esa parte, que es lo correcto: inventar una mal
    formada haría que Power BI lo rechace como corrupto.
    """
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "Version": 3,
        "AutoCreatedRelationships": [],
        "FileDescription": descripcion or destino.stem,
        "CreatedFrom": "Cloud",
    }
    settings = {"Version": 4,
                "ReportSettings": {"UseStylableVisualContainerHeader": True}}
    if layout is None:
        layout = {"id": 0, "resourcePackages": [], "sections": [],
                  "config": json.dumps({}), "layoutOptimization": 0}

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        # El Content_Types tiene que declarar EXACTAMENTE las partes que se
        # escriben: si declara una que no está, o falta una que sí está, Power
        # BI da "corrupt or invalid report file".
        z.writestr("[Content_Types].xml", _content_types(bool(datamashup)))
        z.writestr("Version", _u16("1.28"))
        z.writestr("DataModelSchema", _u16(json.dumps(modelo, ensure_ascii=False)))
        z.writestr("Report/Layout", _u16(json.dumps(layout, ensure_ascii=False)))
        z.writestr("Settings", _u16(json.dumps(settings, ensure_ascii=False)))
        z.writestr("Metadata", _u16(json.dumps(metadata, ensure_ascii=False)))
        if datamashup:
            # Bytes crudos: NO pasa por _u16(). Es un binario, no texto UTF-16.
            z.writestr("DataMashup", datamashup)
    return destino


def exportar_pbip(modelo: dict, layout: dict | None, carpeta: str | Path,
                  nombre: str) -> Path:
    """
    Escribe la estructura PBIP completa (control de versiones):
    <nombre>.pbip + <nombre>.SemanticModel/ + <nombre>.Report/.
    """
    carpeta = Path(carpeta)
    sm = carpeta / f"{nombre}.SemanticModel"
    rp = carpeta / f"{nombre}.Report"
    sm.mkdir(parents=True, exist_ok=True)
    rp.mkdir(parents=True, exist_ok=True)

    def esc(p: Path, obj) -> None:
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False),
                     encoding="utf-8")

    esquema_plat = ("https://developer.microsoft.com/json-schemas/fabric/"
                    "gitIntegration/platformProperties/2.0.0/schema.json")
    esc(sm / ".platform", {
        "$schema": esquema_plat,
        "metadata": {"type": "SemanticModel", "displayName": nombre},
        "config": {"version": "2.0",
                   "logicalId": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"sm{nombre}"))},
    })
    esc(sm / "definition.pbism", {"version": "1.0", "settings": {}})
    esc(sm / "model.bim", modelo)

    esc(rp / ".platform", {
        "$schema": esquema_plat,
        "metadata": {"type": "Report", "displayName": nombre},
        "config": {"version": "2.0",
                   "logicalId": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"rp{nombre}"))},
    })
    esc(rp / "definition.pbir", {
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../{nombre}.SemanticModel"}},
    })
    if layout is None:
        layout = {"id": 0, "resourcePackages": [], "sections": [],
                  "config": json.dumps({}), "layoutOptimization": 0}
    esc(rp / "report.json", layout)

    pbip = carpeta / f"{nombre}.pbip"
    esc(pbip, {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{nombre}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    return pbip


# ==========================================================================
# Utilidades sobre expresiones TMSL
# ==========================================================================
def expr_texto(expresion) -> str:
    """En TMSL una expresión puede ser un string o una lista de líneas."""
    if expresion is None:
        return ""
    if isinstance(expresion, list):
        return "\n".join(expresion)
    return str(expresion)


def expr_lineas(texto: str):
    """Inversa de expr_texto: TMSL prefiere lista de líneas si hay saltos."""
    return texto.split("\n") if "\n" in texto else texto
