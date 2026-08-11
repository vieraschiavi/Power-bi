#!/usr/bin/env python3
"""
MV DAX Lab · Informar en una línea qué edición está activa y qué desbloquea.

Lo usa el workflow de instaladores para comprobar, sobre una instalación de
Windows de verdad, que el candado de la edición aguanta y que el .bat de owner
hace lo que dice. Vive acá y no embebido en el YAML porque un script de Python
metido dentro de PowerShell metido dentro de YAML es ilegible, rompe el
parseo (los here-strings `@"…"@` exigen columna 0) y no se puede probar.

Salida (una línea, fácil de comparar desde el runner):

    edicion|activa|dias_restantes|funciones_trabadas

Uso:
    python estado_edicion.py            # usa el entorno tal como está
"""
from __future__ import annotations

import sys


def main() -> int:
    from dxl import licencia as lic

    estado = lic.evaluar()
    trabadas = sorted(f for f in lic.FUNCIONES_CON_LICENCIA
                      if not estado.permite(f))
    print("|".join([
        estado.edicion,
        str(estado.activa),
        str(getattr(estado, "dias_restantes", None)),
        ",".join(trabadas),
    ]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
