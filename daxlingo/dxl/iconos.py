# © 2026 Martín Viera. Todos los derechos reservados.

"""
El set de íconos del producto — uno solo, para la app y para la web.

Antes cada superficie tenía sus emojis por su lado: la barra de pestañas de la
app, las tarjetas de la landing y la página de descarga. Emojis distintos para
la misma cosa, y encima cada sistema operativo los dibuja a su manera —lo que
en Windows es plano, en Mac es 3D y en Android otra cosa—, así que el producto
se veía distinto en cada máquina y de una pantalla a la otra.

Acá viven una vez. Son SVG de línea, todos con el mismo trazo, la misma caja
de 24×24 y sin relleno: un sistema, no una bolsa de dibujos. El color no está
en el ícono sino en quien lo usa (`currentColor` vía máscara CSS), así que el
mismo archivo sirve para la pestaña activa en ámbar y para la apagada en gris.

Los consume:
  · `app/app.py`            barra de las 14 pestañas (máscara CSS)
  · `web/assets/iconos.css` tarjetas de la landing y de descarga
                            (lo genera `web/generar-iconos-css.py`)
"""
from __future__ import annotations

# Las 14 pestañas, en el orden de `st.tabs(...)` de app.py. El nombre es la
# clave: si cambia el orden de las pestañas, acá no hay que tocar nada.
PESTANAS = (
    "guia", "modelo", "relaciones", "analizador", "generar", "explicador",
    "transformar", "exportar", "fabric", "overlay", "academia",
    "herramientas", "licencia", "config",
)

CUERPOS: dict[str, str] = {
    # --- Las 14 de la barra de pestañas -------------------------------------
    "guia": ("<circle cx='12' cy='12' r='9'/><path d='M9.1 9a3 3 0 015.8 1c0 "
             "2-3 2.5-3 4'/><path d='M12 17.5v.01'/>"),
    "modelo": "<path d='M12 3v12M7 11l5 5 5-5M4 21h16'/>",
    "relaciones": ("<circle cx='6' cy='6' r='2.5'/><circle cx='18' cy='6' "
                   "r='2.5'/><circle cx='12' cy='18' r='2.5'/>"
                   "<path d='M8 7.5l3 8M16 7.5l-3 8'/>"),
    "analizador": "<path d='M3 12h4l2.5-7 4 14L16 12h5'/>",
    "generar": ("<path d='M12 3l1.9 4.6 4.6 1.9-4.6 1.9L12 16l-1.9-4.6L5.5 "
                "9.5l4.6-1.9z'/><path d='M18 16l.9 2.1 2.1.9-2.1.9L18 22l-.9"
                "-2.1-2.1-.9 2.1-.9z'/>"),
    "explicador": ("<path d='M4 5h6a2 2 0 012 2v12a2 2 0 00-2-2H4zM20 5h-6a2 "
                   "2 0 00-2 2v12a2 2 0 012-2h6z'/>"),
    "transformar": ("<path d='M4 8h11M4 16h7'/>"
                    "<path d='M17 5l4 3-4 3M13 13l4 3-4 3'/>"),
    "exportar": "<path d='M4 20V10M10 20V4M16 20v-7M22 20H2'/>",
    "fabric": ("<path d='M12 3l8 4.5v9L12 21l-8-4.5v-9z'/>"
               "<path d='M12 12l8-4.5M12 12v9M12 12L4 7.5'/>"),
    "overlay": ("<rect x='3' y='4' width='18' height='13' rx='2'/>"
                "<path d='M8 21h8'/><path d='M9 10.5l2 2 4-4'/>"),
    "academia": ("<path d='M12 4L2 9l10 5 10-5z'/>"
                 "<path d='M6 11.5V17c0 1.7 2.7 3 6 3s6-1.3 6-3v-5.5'/>"),
    "herramientas": ("<path d='M14.5 6.5a4 4 0 105 5L21 13l-8 8-4-4 8-8z'/>"
                     "<path d='M7 13l-4 4 4 4 2-2'/>"),
    "licencia": ("<circle cx='8' cy='12' r='4'/>"
                 "<path d='M12 12h9M18 12v3M15 12v2'/>"),
    "config": ("<circle cx='12' cy='12' r='3'/><path d='M12 2v3M12 19v3M2 "
               "12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2'/>"),

    # --- Los que solo usa la web --------------------------------------------
    # Overlay: las tres teclas hacen cosas distintas y el ícono lo dice.
    "pantalla": ("<rect x='2' y='4' width='20' height='13' rx='2'/>"
                 "<path d='M8 21h8M12 17v4'/>"),
    "seleccion": ("<path d='M3 8V5a2 2 0 012-2h3M16 3h3a2 2 0 012 2v3M21 "
                  "16v3a2 2 0 01-2 2h-3M8 21H5a2 2 0 01-2-2v-3'/>"),
    "teclado": ("<rect x='2' y='6' width='20' height='12' rx='2'/>"
                "<path d='M6 10h.01M10 10h.01M14 10h.01M18 10h.01M8 14h8'/>"),
    "conector": ("<path d='M9 2v6M15 2v6'/>"
                 "<path d='M6 8h12v3a6 6 0 01-12 0z'/><path d='M12 17v5'/>"),
    "verificado": ("<circle cx='12' cy='12' r='9'/>"
                   "<path d='M8 12.5l2.5 2.5L16 9.5'/>"),
    "carpeta": ("<path d='M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 "
                "2H5a2 2 0 01-2-2z'/>"),
    "brujula": ("<circle cx='12' cy='12' r='9'/>"
                "<path d='M15.5 8.5l-2 5-5 2 2-5z'/>"),
    "limpiar": "<path d='M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13'/>",
    "paquete": ("<rect x='3' y='6' width='18' height='14' rx='2'/>"
                "<path d='M3 11h18M12 6v14'/>"),
    "windows": "<path d='M4 5h7v7H4zM13 5h7v7h-7zM4 14h7v5H4zM13 14h7v5h-7z'/>",
    "terminal": ("<rect x='2' y='4' width='20' height='16' rx='2'/>"
                 "<path d='M6 9l3 3-3 3M12 15h6'/>"),
}


def svg(nombre: str) -> str:
    """El SVG completo, listo para embeber en un `url("data:...")` de CSS.

    Se usan comillas simples adentro y se escapan `<`, `>` y `#`: dentro de un
    `url("data:image/svg+xml;utf8,...")` esos caracteres cortan el valor y la
    regla entera se descarta en silencio, sin error y sin ícono.
    """
    cuerpo = CUERPOS[nombre]
    texto = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
             "fill='none' stroke='black' stroke-width='2' "
             f"stroke-linecap='round' stroke-linejoin='round'>{cuerpo}</svg>")
    return texto.replace("<", "%3C").replace(">", "%3E").replace("#", "%23")
