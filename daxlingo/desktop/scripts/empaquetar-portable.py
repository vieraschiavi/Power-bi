#!/usr/bin/env python3
"""
MV DAX Lab · Arma los ZIP de la versión portable, uno por edición.

La otra mitad de la distribución. `build-instaladores.js` produce los tres
`.exe` de Electron; esto produce los tres ZIP que se descomprimen y se abren
con doble clic, sin instalar nada — que es lo único que sirve en una PC de
trabajo donde no dan permisos de administrador.

Las tres ediciones salen del MISMO código, con el sello horneado igual que en
el instalador (`edicion.json`, con `bloqueada: true` en las que se venden) para
que `MVDAX_EDICION=owner` no convierta una copia vendida en la del dueño.

El runtime de Python NO viaja: son ~180 MB y la mayoría de las PC con Power BI
ya tienen Python o pueden instalarlo. El `.bat` lo busca, y si no está manda al
instalador `.exe`, que sí lo trae. Con `--con-runtime` se incluye si existe.

Uso:
    python desktop/scripts/empaquetar-portable.py            # las tres
    python desktop/scripts/empaquetar-portable.py owner
    python desktop/scripts/empaquetar-portable.py --con-runtime
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]        # daxlingo/
DESKTOP = RAIZ / "desktop"
SALIDA = DESKTOP / "dist-portable"

# Mismos sellos que build-instaladores.js. Si cambian allá, cambian acá: son
# el mismo producto vendido de dos formas.
EDICIONES = {
    "owner": {"edicion": "owner", "bloqueada": True,
              "carpeta": "MV-DAX-Lab-OWNER-portable"},
    "cliente": {"edicion": "profesional", "bloqueada": True,
                "carpeta": "MV-DAX-Lab-portable"},
    "demo": {"edicion": "demo", "bloqueada": True,
             "carpeta": "MV-DAX-Lab-DEMO-portable"},
}

# Lo que necesita el motor para correr. Deliberadamente corto: `powerbi/`,
# `media/`, `tests/` y `web/` no van en lo que se le entrega al cliente.
CONTENIDO = [
    ("dxl", "dxl"),
    ("app", "app"),
    ("datos/demo", "datos/demo"),
    ("mcp", "mcp"),
    ("overlay", "overlay"),
    ("lanzador.py", "lanzador.py"),
    ("requirements-app.txt", "requirements-app.txt"),
]

IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def copiar(destino: Path) -> list[str]:
    """Copia el producto al destino. Devuelve lo que faltaba."""
    faltantes = []
    for origen_rel, destino_rel in CONTENIDO:
        origen = RAIZ / origen_rel
        if not origen.exists():
            faltantes.append(origen_rel)
            continue
        final = destino / destino_rel
        final.parent.mkdir(parents=True, exist_ok=True)
        if origen.is_dir():
            shutil.copytree(origen, final, ignore=IGNORAR, dirs_exist_ok=True)
        else:
            shutil.copy2(origen, final)
    shutil.copy2(DESKTOP / "portable" / "MV_DAX_Lab.bat",
                 destino / "MV_DAX_Lab.bat")
    return faltantes


def sellar(destino: Path, cfg: dict) -> None:
    """Hornea la edición, conservando secreto y sitio del sello del repo.

    Si se perdieran, la copia dejaría de validar las licencias emitidas y los
    botones de compra apuntarían a ningún lado — el mismo cuidado que tiene
    build-instaladores.js.
    """
    previo = {}
    del_repo = DESKTOP / "edicion.json"
    if del_repo.exists():
        previo = json.loads(del_repo.read_text(encoding="utf-8"))
    import os
    (destino / "edicion.json").write_text(json.dumps({
        "_comentario": "Generado por empaquetar-portable.py — no editar a mano.",
        "edicion": cfg["edicion"],
        "bloqueada": cfg["bloqueada"],
        "secreto": os.environ.get("MVDAX_LICENSE_SECRET", previo.get("secreto", "")),
        "sitio": os.environ.get("MVDAXLAB_SITIO", previo.get("sitio", "")),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def empaquetar(nombre: str, con_runtime: bool) -> Path:
    cfg = EDICIONES[nombre]
    SALIDA.mkdir(parents=True, exist_ok=True)
    trabajo = SALIDA / cfg["carpeta"]
    shutil.rmtree(trabajo, ignore_errors=True)
    trabajo.mkdir(parents=True)

    print(f"\n▶ Empaquetando la edición «{nombre}»…")
    faltantes = copiar(trabajo)
    if faltantes:
        raise SystemExit(f"  [X] Falta en el repo: {', '.join(faltantes)}")
    sellar(trabajo, cfg)

    if con_runtime:
        runtime = DESKTOP / "runtime"
        if any(runtime.glob("python*")):
            shutil.copytree(runtime, trabajo / "runtime", ignore=IGNORAR,
                            dirs_exist_ok=True)
            print("  · runtime embebido incluido")
        else:
            print("  ⚠️  --con-runtime pedido pero desktop/runtime está vacío")

    zip_final = SALIDA / f"{cfg['carpeta']}.zip"
    zip_final.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_final, "w", zipfile.ZIP_DEFLATED) as z:
        for archivo in sorted(trabajo.rglob("*")):
            if archivo.is_file():
                z.write(archivo, archivo.relative_to(SALIDA))
    mb = zip_final.stat().st_size / 1_048_576
    print(f"  ✓ {zip_final.relative_to(RAIZ)} ({mb:.1f} MB)")
    return zip_final


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("edicion", nargs="?", choices=sorted(EDICIONES) + ["todos"],
                    default="todos")
    ap.add_argument("--con-runtime", action="store_true",
                    help="incluir desktop/runtime (~180 MB) en el ZIP")
    a = ap.parse_args()

    cuales = sorted(EDICIONES) if a.edicion == "todos" else [a.edicion]
    for nombre in cuales:
        empaquetar(nombre, a.con_runtime)
    print(f"\nListo en {SALIDA.relative_to(RAIZ)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
