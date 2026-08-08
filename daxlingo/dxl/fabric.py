"""
MV DAX Lab · Integración con Microsoft Fabric.

Dos caminos, según lo que tenga el usuario:

  1. SIN credenciales (siempre disponible): el export PBIP que produce esta
     plataforma ES el formato de integración Git de Fabric — se conecta el
     workspace a un repo (Azure DevOps / GitHub) con las carpetas
     *.SemanticModel y *.Report y Fabric los materializa como ítems. Este
     módulo genera además la guía paso a paso.

  2. CON token (BYOK): publicación directa vía la API REST de Fabric
     (`POST /v1/workspaces/{id}/items`), mandando la definición del modelo
     semántico y del reporte en partes base64 (formato TMSL/PBIR-Legacy).
     El token es del usuario (az cli / app registration) y viaja solo en el
     header; acá no se guarda nada.

Como el resto del motor: sin credenciales no se inventa nada — se explica el
camino y se dejan los payloads listos.
"""
from __future__ import annotations

import base64
import json
import urllib.request

API_FABRIC = "https://api.fabric.microsoft.com/v1"


def _parte(ruta: str, contenido: str) -> dict:
    return {
        "path": ruta,
        "payload": base64.b64encode(contenido.encode("utf-8")).decode(),
        "payloadType": "InlineBase64",
    }


def payload_modelo_semantico(nombre: str, modelo: dict) -> dict:
    """Ítem SemanticModel para la API de Fabric (definición TMSL)."""
    pbism = {"version": "1.0", "settings": {}}
    return {
        "displayName": nombre,
        "type": "SemanticModel",
        "definition": {
            "parts": [
                _parte("model.bim",
                       json.dumps(modelo, indent=2, ensure_ascii=False)),
                _parte("definition.pbism",
                       json.dumps(pbism, indent=2)),
            ],
        },
    }


def payload_reporte(nombre: str, layout: dict,
                    id_modelo_semantico: str) -> dict:
    """Ítem Report enlazado por id al modelo semántico ya creado."""
    pbir = {
        "version": "1.0",
        "datasetReference": {
            "byConnection": {
                "connectionString": None,
                "pbiServiceModelId": None,
                "pbiModelVirtualServerName": "sobe_wowvirtualserver",
                "pbiModelDatabaseName": id_modelo_semantico,
                "name": "EntityDataSource",
                "connectionType": "pbiServiceXmlaStyleLive",
            },
        },
    }
    return {
        "displayName": nombre,
        "type": "Report",
        "definition": {
            "format": "PBIR-Legacy",
            "parts": [
                _parte("report.json",
                       json.dumps(layout, ensure_ascii=False)),
                _parte("definition.pbir", json.dumps(pbir, indent=2)),
            ],
        },
    }


def _llamar(metodo: str, url: str, token: str, cuerpo: dict | None = None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(
        url, data=datos, method=metodo,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=120) as resp:
        crudo = resp.read()
        return json.loads(crudo) if crudo else {}


def publicar(workspace_id: str, nombre: str, modelo: dict,
             layout: dict | None, token: str) -> dict:
    """
    Publica el modelo (y el reporte, si hay layout) en un workspace de
    Fabric. Devuelve {'modelo_semantico': id, 'reporte': id | None}.
    """
    url = f"{API_FABRIC}/workspaces/{workspace_id}/items"
    r1 = _llamar("POST", url, token, payload_modelo_semantico(nombre, modelo))
    id_modelo = r1.get("id", "")
    id_reporte = None
    if layout is not None and id_modelo:
        r2 = _llamar("POST", url, token,
                     payload_reporte(nombre, layout, id_modelo))
        id_reporte = r2.get("id")
    return {"modelo_semantico": id_modelo, "reporte": id_reporte}


def listar_workspaces(token: str) -> list[dict]:
    datos = _llamar("GET", f"{API_FABRIC}/workspaces", token)
    return [{"id": w.get("id", ""), "nombre": w.get("displayName", "")}
            for w in datos.get("value", [])]


GUIA_GIT = """\
### Publicar en Fabric sin token — integración Git (recomendado)

1. Exportá el modelo como **PBIP** (pestaña *Exportar*): quedan las carpetas
   `<Nombre>.SemanticModel/` y `<Nombre>.Report/`.
2. Subí esas carpetas a un repo de **Azure DevOps** o **GitHub**.
3. En Fabric: *Workspace settings → Git integration* → conectá el repo y la
   carpeta.
4. Fabric detecta los ítems y los **materializa en el workspace**; cada
   commit posterior se sincroniza con *Update from Git*.

### Con token (publicación directa por API)

1. Token con scope `https://api.fabric.microsoft.com/.default`
   (p. ej. `az account get-access-token --resource https://api.fabric.microsoft.com`).
2. Pegalo en el campo de arriba, elegí workspace y **Publicar**.
3. El token viaja solo en el header de la llamada; no se guarda.
"""
