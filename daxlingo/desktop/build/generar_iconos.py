#!/usr/bin/env python3
# © 2026 Martín Viera. Todos los derechos reservados.

"""
Genera el icono del producto: `icono.png` (ventana y Linux) e `icono.ico`
multi-resolución (Windows: instalador, acceso directo, barra de tareas).

Se genera por código a propósito — así el icono queda versionado como fuente
y no como un binario opaco que nadie sabe regenerar.

Uso:  python daxlingo/desktop/build/generar_iconos.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
AMBAR = (242, 180, 65, 255)
AMBAR_OSCURO = (227, 154, 46, 255)
TINTA = (28, 19, 5, 255)
LADO = 1024

FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def dibujar(lado: int = LADO) -> Image.Image:
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    dib = ImageDraw.Draw(img)

    # Cuadrado redondeado ámbar: la marca de MV DAX Lab.
    margen = int(lado * 0.06)
    radio = int(lado * 0.22)
    dib.rounded_rectangle([margen, margen, lado - margen, lado - margen],
                          radius=radio, fill=AMBAR)

    # Franja inferior más oscura: da profundidad sin usar degradados, que a
    # 16×16 se convierten en barro.
    dib.rounded_rectangle([margen, int(lado * 0.72), lado - margen,
                           lado - margen], radius=radio, fill=AMBAR_OSCURO)
    dib.rectangle([margen, int(lado * 0.72), lado - margen, int(lado * 0.80)],
                  fill=AMBAR_OSCURO)

    # "fx" es el símbolo universal de "acá se escribe una fórmula" — se lee
    # mejor a tamaño chico que las tres letras de DAX.
    fnt = ImageFont.truetype(FUENTE, int(lado * 0.46))
    texto = "fx"
    caja = dib.textbbox((0, 0), texto, font=fnt)
    ancho, alto = caja[2] - caja[0], caja[3] - caja[1]
    dib.text(((lado - ancho) / 2 - caja[0],
              (lado - alto) / 2 - caja[1] - lado * 0.04),
             texto, font=fnt, fill=TINTA)

    # Tres barras: el tablero que sale del otro lado.
    y = int(lado * 0.78)
    alto_barra = int(lado * 0.085)
    ancho_barra = int(lado * 0.075)
    x = int(lado * 0.33)
    for k, factor in enumerate((0.55, 1.0, 0.78)):
        h = int(alto_barra * factor)
        dib.rounded_rectangle(
            [x + k * int(ancho_barra * 1.5), y + (alto_barra - h),
             x + k * int(ancho_barra * 1.5) + ancho_barra, y + alto_barra],
            radius=int(lado * 0.012), fill=TINTA)
    return img


def main() -> None:
    grande = dibujar()
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
