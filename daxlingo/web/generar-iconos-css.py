#!/usr/bin/env python3
# © 2026 Martín Viera. Todos los derechos reservados.

"""
Escribe `web/assets/iconos.css` a partir de `dxl/iconos.py`.

La landing no tiene build (es HTML/CSS/JS servido tal cual), así que el CSS
se genera acá y se commitea. Lo importante es de DÓNDE sale: del mismo módulo
que usa la app para su barra de pestañas. Antes la web tenía sus emojis y el
programa los suyos, y cada vez que se tocaba uno el otro quedaba distinto.

Los íconos van como MÁSCARA, no como imagen: así el color lo pone el CSS
(`background-color`) y el mismo archivo sirve en ámbar, en gris o en hover,
sin generar una copia por color.

Uso:  python daxlingo/web/generar-iconos-css.py
"""
from __future__ import annotations

import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from dxl import iconos  # noqa: E402

CABECERA = """/* GENERADO por web/generar-iconos-css.py — no editar a mano.
   Los dibujos viven en dxl/iconos.py, el mismo módulo que usa la barra de
   pestañas de la app. Si hay que cambiar un ícono, se cambia allá y se
   vuelve a correr ese script. */

.ico{display:inline-block;background-color:var(--amber);
  -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;
  -webkit-mask-position:center;mask-position:center;
  -webkit-mask-size:contain;mask-size:contain;
  width:1.15rem;height:1.15rem;vertical-align:-.18em;margin-right:.45rem}

/* El de las tarjetas va solo en su renglón, como estaba el emoji. */
.ico-bloque{display:block;width:1.6rem;height:1.6rem;margin:0 0 10px}
"""


def main() -> None:
    reglas = [CABECERA]
    for nombre in sorted(iconos.CUERPOS):
        url = f'url("data:image/svg+xml;utf8,{iconos.svg(nombre)}")'
        reglas.append(f".ico-{nombre}{{-webkit-mask-image:{url};"
                      f"mask-image:{url}}}")
    salida = AQUI / "assets" / "iconos.css"
    salida.write_text("\n".join(reglas) + "\n", encoding="utf-8")
    print(f"✓ {salida.relative_to(AQUI.parent)} "
          f"({len(iconos.CUERPOS)} íconos, {salida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
