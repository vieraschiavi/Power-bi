#!/usr/bin/env python3
# © 2026 Martín Viera. Todos los derechos reservados.

"""
Genera el icono del producto: `icono.png` (ventana y Linux) e `icono.ico`
multi-resolución (Windows: instalador, acceso directo, barra de tareas).

Es la MARCA MV: cuadrado redondeado azul con la M blanca y la V verde. La
misma que usa el resto de los productos MV, para que en la barra de tareas
se reconozcan como de la misma casa. Antes de esto el icono era un cuadrado
ámbar con "fx" dibujado a mano — no era la marca de nada.

Se genera por código a propósito — así el icono queda versionado como fuente
y no como un binario opaco que nadie sabe regenerar.

## De dónde salen las letras

De `logo-mv.svg`, el archivo de marca (está al lado de este script). Los dos
glifos vienen de DejaVu Sans Bold convertidos a contorno con fontTools, y
—por suerte— quedaron como polígonos puros: los `d` de esos paths solo usan
`H`, `L` y `V`, ni una curva. Así que se pueden dibujar acá con
`ImageDraw.polygon` y el resultado es EXACTAMENTE el del SVG, sin sumar un
rasterizador (cairosvg y compañía) como dependencia.

Los puntos de abajo son esos mismos paths ya leídos a mano, con la misma
transformación que aplica el SVG: `translate(tx, ty) scale(s, -s)`, o sea
`x = tx + s·px` y `y = ty − s·py` (el eje Y del SVG va al revés que el de
la imagen, de ahí el signo).

Uso:  python daxlingo/desktop/build/generar_iconos.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent

# Los colores salen de logo-mv.svg, no de la percepción de una captura.
AZUL_ARRIBA = (28, 63, 99)     # #1c3f63
AZUL_ABAJO = (13, 36, 64)      # #0d2440
BLANCO = (255, 255, 255, 255)  # la M
VERDE = (92, 181, 49, 255)     # #5cb531 — la V

# El SVG trabaja sobre un lienzo de 1024 con 6 px de margen y esquinas de
# radio 230. Se guardan como proporción para poder dibujar a cualquier lado.
LIENZO_SVG = 1024
MARGEN = 6 / LIENZO_SVG
RADIO = 230 / LIENZO_SVG
ESCALA_GLIFO = 0.21484375

# Contornos de los dos glifos, en unidades de la fuente. Cerrados: el último
# punto se une con el primero.
M_PUNTOS = [(188, 1493), (678, 1493), (1018, 694), (1360, 1493), (1849, 1493),
            (1849, 0), (1485, 0), (1485, 1092), (1141, 287), (897, 287),
            (553, 1092), (553, 0), (188, 0)]
V_PUNTOS = [(10, 1493), (397, 1493), (793, 391), (1188, 1493), (1575, 1493),
            (1022, 0), (563, 0)]

# Dónde se apoya cada glifo (el `translate` del SVG), también proporcional.
M_ORIGEN = (205 / LIENZO_SVG, 650 / LIENZO_SVG)
V_ORIGEN = (540 / LIENZO_SVG, 650 / LIENZO_SVG)


def _fondo(lado: int) -> Image.Image:
    """El cuadrado redondeado con el degradado azul de la marca."""
    # El degradado se arma fila por fila y después se recorta con una
    # máscara redondeada. Pillow no tiene degradados, pero 1024 filas de
    # interpolación lineal son instantáneas y salen idénticas al SVG.
    grad = Image.new("RGB", (1, lado))
    for y in range(lado):
        t = y / max(lado - 1, 1)
        grad.putpixel((0, y), tuple(
            round(a + (b - a) * t)
            for a, b in zip(AZUL_ARRIBA, AZUL_ABAJO)))
    grad = grad.resize((lado, lado))

    margen = MARGEN * lado
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [margen, margen, lado - 1 - margen, lado - 1 - margen],
        radius=RADIO * lado, fill=255)

    fondo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    fondo.paste(grad, (0, 0), mascara)
    return fondo


def _glifo(dib: ImageDraw.ImageDraw, puntos, origen, color, lado: int) -> None:
    """Dibuja un contorno de la fuente con la transformación del SVG."""
    tx, ty = origen[0] * lado, origen[1] * lado
    s = ESCALA_GLIFO * lado / LIENZO_SVG
    dib.polygon([(tx + s * px, ty - s * py) for px, py in puntos], fill=color)


def dibujar(lado: int = LIENZO_SVG) -> Image.Image:
    img = _fondo(lado)
    dib = ImageDraw.Draw(img)
    _glifo(dib, M_PUNTOS, M_ORIGEN, BLANCO, lado)
    _glifo(dib, V_PUNTOS, V_ORIGEN, VERDE, lado)
    return img


def main() -> None:
    # Se dibuja en grande y se reduce: los bordes en diagonal de la M y la V
    # quedan con antialias en vez de escalonados, que es lo que se nota a
    # 32×32 en la barra de tareas.
    grande = dibujar(LIENZO_SVG)
    png = AQUI / "icono.png"
    grande.resize((512, 512), Image.LANCZOS).save(png)

    # El .ico lleva todos los tamaños que pide Windows: 16 para la barra de
    # título, 32/48 para el explorador, 256 para vistas grandes.
    ico = AQUI / "icono.ico"
    grande.save(ico, format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                       (128, 128), (256, 256)])
    print(f"✓ {png.name} ({png.stat().st_size // 1024} KB)")
    print(f"✓ {ico.name} ({ico.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
