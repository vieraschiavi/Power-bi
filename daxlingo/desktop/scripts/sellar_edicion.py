#!/usr/bin/env python3
# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Reescribir el sello de edición de una instalación.

El sello es `resources/app/edicion.json`, el archivo que el motor lee al
arrancar para saber qué edición es. Cambiarlo convierte una instalación ya
hecha en otra edición sin reinstalar ni descargar nada.

Lo usa `Convertir-a-version-dueno.bat`. Está en Python y no embebido en el .bat a
propósito: hay que **conservar** `secreto` y `sitio` del sello anterior —si se
pisaran, la copia dejaría de validar las licencias emitidas y los botones de
compra apuntarían a ningún lado— y batch no sabe leer JSON. Armarlo a mano con
comillas escapadas es exactamente como se rompen estas cosas, y acá además se
puede testear.

Uso:
    python sellar_edicion.py <carpeta-instalacion> --edicion owner
    python sellar_edicion.py <carpeta-instalacion> --revertir
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Mismo motivo que en empaquetar-portable.py: el runtime embebido de Windows
# usa cp1252 con stdout redirigido, y este archivo imprime «tildes». Sin esto
# es cuestión de tiempo hasta que Convertir-a-version-dueno.bat reviente con el mismo
# UnicodeEncodeError.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

EDICIONES = ("owner", "profesional", "demo")
NOMBRE_SELLO = "edicion.json"
NOMBRE_COPIA = "edicion.original.json"


def carpeta_sello(instalacion: Path) -> Path:
    """`resources/app/` es donde `dxl/licencia.py` busca el sello: es
    `parents[1]` desde el módulo. Si se mueve, el motor deja de verlo y
    la edición vuelve a decidirla una variable de entorno."""
    return instalacion / "resources" / "app"


def validar(instalacion: Path) -> Path:
    destino = carpeta_sello(instalacion)
    if not (destino / "dxl" / "licencia.py").exists():
        raise SystemExit(
            f"No parece una instalación de MV DAX Lab: {instalacion}\n"
            f"Falta {destino / 'dxl' / 'licencia.py'}")
    return destino


def sellar(instalacion: Path, edicion: str) -> Path:
    destino = validar(instalacion)
    sello, copia = destino / NOMBRE_SELLO, destino / NOMBRE_COPIA

    previo: dict = {}
    if sello.exists():
        if not copia.exists():
            shutil.copy2(sello, copia)     # para poder volver atrás
        try:
            previo = json.loads(sello.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previo = {}

    sello.write_text(json.dumps({
        "_comentario": f"Edición «{edicion}» aplicada por sellar_edicion.py",
        "edicion": edicion,
        "bloqueada": True,
        # Se conservan: el secreto valida las licencias que emitís y el sitio
        # es a dónde llevan los botones de compra y de renovación.
        "secreto": previo.get("secreto", ""),
        "sitio": previo.get("sitio", ""),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sello


def revertir(instalacion: Path) -> Path:
    destino = validar(instalacion)
    sello, copia = destino / NOMBRE_SELLO, destino / NOMBRE_COPIA
    if not copia.exists():
        raise SystemExit("No hay copia del sello original para restaurar.")
    shutil.copy2(copia, sello)
    copia.unlink()
    return sello


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("instalacion", type=Path,
                    help="carpeta donde está «MV DAX Lab.exe»")
    ap.add_argument("--edicion", choices=EDICIONES)
    ap.add_argument("--revertir", action="store_true")
    args = ap.parse_args(argv)

    if args.revertir:
        sello = revertir(args.instalacion)
        print(f"Sello restaurado: {sello}")
    else:
        if not args.edicion:
            ap.error("indicá --edicion o --revertir")
        sello = sellar(args.instalacion, args.edicion)
        print(f"Edición «{args.edicion}» aplicada en: {sello}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
