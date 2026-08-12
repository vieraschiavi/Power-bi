#!/usr/bin/env python3
"""
MV DAX Lab · Genera el video demo en los tres idiomas.

Compone los cuadros con las capturas REALES que produce `capturar.py` —una
por pestaña y por idioma— les pone título y bajada, y los encadena con
transiciones cortas. El resultado va a `web/assets/video/demo-<idioma>.mp4`,
que es lo que reproduce la landing según el selector de idioma.

Decisión de diseño: cuadro estático por pestaña + fundidos de medio segundo,
en vez de un paneo continuo. Un paneo obliga a redibujar los 2.600 cuadros y
tarda minutos por idioma; así se componen 14 cuadros y se mezclan solo los de
la transición. El video se ve igual de prolijo y se regenera en segundos.

Uso:
    python daxlingo/media/build_video.py               # es, en, pt
    python daxlingo/media/build_video.py --idioma es
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dxl import dominio  # noqa: E402
from dxl.i18n import IDIOMAS  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import narracion  # noqa: E402

ANCHO, ALTO = 1920, 1080
FPS = 25
SEG_POR_PESTANA = 7.0
SEG_INTRO = 4.0
SEG_CIERRE = 4.0
SEG_FUNDIDO = 0.5
# Aire después de la locución para que la placa no corte en seco.
RESPIRO_VOZ = 1.2

NAVY = (8, 21, 39)
NAVY2 = (12, 33, 55)
AMBAR = (242, 180, 65)
TINTA = (234, 241, 251)
APAGADO = (157, 176, 200)
LINEA = (29, 49, 73)

FUENTES = {
    "negrita": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "normal": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
}

# (slug de la captura, clave de texto). El orden ES el guion del video.
GUION = [
    ("modelo", "modelo"), ("relaciones", "relaciones"),
    ("analizador", "analizador"), ("generar", "generar"),
    ("explicador", "explicador"), ("transformar", "transformar"),
    ("exportar", "exportar"), ("fabric", "fabric"),
    ("overlay", "overlay"), ("academia", "academia"),
    ("herramientas", "herramientas"), ("configuracion", "configuracion"),
    ("licencia", "licencia"), ("guia", "guia"),
]

# Textos del video. Trilingüe obligatorio: hay un test que verifica que a
# ninguna clave le falte un idioma.
VIDEO: dict[str, dict[str, tuple[str, str]]] = {
    "es": {
        "_intro": ("MV DAX Lab",
                   "Tu modelo de Power BI, explicado, corregido y exportado"),
        "_cierre": ("Probalo con tu modelo",
                    "7 días gratis · {sitio}"),
        "modelo": ("Cargá tu modelo",
                   ".pbit, PBIP, model.bim o .pbix — tablas, columnas y el DAX de cada medida"),
        "relaciones": ("Mirá el modelo entero",
                       "Cardinalidades, calendario marcado y bidireccionales en rojo"),
        "analizador": ("Auditoría en un clic",
                       "15 reglas con severidad, impacto real y arreglo automático"),
        "generar": ("Pedí la medida en tu idioma",
                    "El DAX sale validado contra tu catálogo: nunca inventa columnas"),
        "explicador": ("Entendé cualquier DAX",
                       "Qué calcula, qué hace el contexto de filtro y de qué nivel es"),
        "transformar": ("Transformá sin miedo",
                        "Renombrar con propagación, columnas calculadas y formatos, sobre una copia"),
        "exportar": ("Volvé a Power BI con tablero",
                     "KPIs, evolución, barras, dona, matriz y filtros, en .pbit o PBIP"),
        "fabric": ("Publicá en Microsoft Fabric",
                   "API REST con tu token, o integración Git del proyecto PBIP"),
        "overlay": ("F9 y resolvé lo que estás mirando",
                    "Captura, explicación paso a paso, y se aplica al modelo con un clic"),
        "academia": ("Practicá DAX en serio",
                     "17 ejercicios, 5 niveles, verificación instantánea sin conexión"),
        "herramientas": ("Tu stack, conectado",
                         "DAX Studio, Tabular Editor, Bravo, ALM Toolkit y los tres MCP"),
        "configuracion": ("La IA que vos elijas",
                          "Claude, ChatGPT, Gemini, Copilot… con tu propia clave"),
        "licencia": ("Prueba de 7 días",
                     "Con todo desbloqueado; después activás la clave que llega al pagar"),
        "guia": ("Todo el ciclo, verificable",
                 "inspeccionar → modelar → construir → validar → verificar → exportar"),
    },
    "en": {
        "_intro": ("MV DAX Lab",
                   "Your Power BI model: explained, fixed and exported"),
        "_cierre": ("Try it on your model",
                    "7 days free · {sitio}"),
        "modelo": ("Load your model",
                   ".pbit, PBIP, model.bim or .pbix — tables, columns and each measure's DAX"),
        "relaciones": ("See the whole model",
                       "Cardinality, the marked date table and bidirectional links in red"),
        "analizador": ("Audit in one click",
                       "15 rules with severity, real impact and an automatic fix"),
        "generar": ("Ask for the measure in your language",
                    "DAX comes out validated against your catalog: it never invents columns"),
        "explicador": ("Understand any DAX",
                       "What it computes, what filter context does, and how advanced it is"),
        "transformar": ("Transform without fear",
                        "Rename with propagation, calculated columns and formats, on a copy"),
        "exportar": ("Back to Power BI, with a report",
                     "KPIs, trend, bars, donut, matrix and slicers, as .pbit or PBIP"),
        "fabric": ("Publish to Microsoft Fabric",
                   "REST API with your token, or the PBIP project's Git integration"),
        "overlay": ("Press F9 and solve what you see",
                    "Capture, step-by-step explanation, applied to the model in one click"),
        "academia": ("Practise DAX properly",
                     "17 exercises, 5 levels, instant checking with no connection"),
        "herramientas": ("Your stack, connected",
                         "DAX Studio, Tabular Editor, Bravo, ALM Toolkit and all three MCPs"),
        "configuracion": ("Whichever AI you choose",
                          "Claude, ChatGPT, Gemini, Copilot… with your own key"),
        "licencia": ("A 7-day trial",
                     "Everything unlocked; then activate the key you get on payment"),
        "guia": ("The whole cycle, verifiable",
                 "inspect → model → build → validate → verify → export"),
    },
    "pt": {
        "_intro": ("MV DAX Lab",
                   "Seu modelo de Power BI, explicado, corrigido e exportado"),
        "_cierre": ("Teste com seu modelo",
                    "7 dias grátis · {sitio}"),
        "modelo": ("Carregue seu modelo",
                   ".pbit, PBIP, model.bim ou .pbix — tabelas, colunas e o DAX de cada medida"),
        "relaciones": ("Veja o modelo inteiro",
                       "Cardinalidades, calendário marcado e bidirecionais em vermelho"),
        "analizador": ("Auditoria em um clique",
                       "15 regras com severidade, impacto real e correção automática"),
        "generar": ("Peça a medida no seu idioma",
                    "O DAX sai validado contra seu catálogo: nunca inventa colunas"),
        "explicador": ("Entenda qualquer DAX",
                       "O que calcula, o que o contexto de filtro faz e qual o nível"),
        "transformar": ("Transforme sem medo",
                        "Renomear com propagação, colunas calculadas e formatos, sobre uma cópia"),
        "exportar": ("Volte ao Power BI com painel",
                     "KPIs, evolução, barras, rosca, matriz e filtros, em .pbit ou PBIP"),
        "fabric": ("Publique no Microsoft Fabric",
                   "API REST com seu token, ou integração Git do projeto PBIP"),
        "overlay": ("F9 e resolva o que está vendo",
                    "Captura, explicação passo a passo, aplicada ao modelo com um clique"),
        "academia": ("Pratique DAX de verdade",
                     "17 exercícios, 5 níveis, verificação instantânea sem conexão"),
        "herramientas": ("Seu stack, conectado",
                         "DAX Studio, Tabular Editor, Bravo, ALM Toolkit e os três MCP"),
        "configuracion": ("A IA que você escolher",
                          "Claude, ChatGPT, Gemini, Copilot… com sua própria chave"),
        "licencia": ("Teste de 7 dias",
                     "Com tudo liberado; depois ative a chave que chega ao pagar"),
        "guia": ("Todo o ciclo, verificável",
                 "inspecionar → modelar → construir → validar → verificar → exportar"),
    },
}


def fuente(estilo: str, tamano: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FUENTES[estilo], tamano)


def _texto_centrado(dib, y, texto, fnt, color):
    ancho = dib.textlength(texto, font=fnt)
    dib.text(((ANCHO - ancho) / 2, y), texto, font=fnt, fill=color)


def cuadro_titulo(titulo: str, bajada: str) -> Image.Image:
    """Placa de apertura y de cierre."""
    img = Image.new("RGB", (ANCHO, ALTO), NAVY)
    dib = ImageDraw.Draw(img)
    # Cuadrado ámbar de la marca, centrado sobre el título.
    lado = 92
    x0 = (ANCHO - lado) // 2
    dib.rounded_rectangle([x0, 300, x0 + lado, 300 + lado], radius=20,
                          fill=AMBAR)
    _texto_centrado(dib, 430, titulo, fuente("negrita", 86), TINTA)
    _texto_centrado(dib, 550, bajada, fuente("normal", 36), APAGADO)
    dib.line([(ANCHO / 2 - 90, 640), (ANCHO / 2 + 90, 640)], fill=AMBAR,
             width=3)
    return img


def cuadro_pestana(captura: Path, titulo: str, bajada: str,
                   indice: int, total: int) -> Image.Image:
    """Un cuadro: título, bajada, la captura enmarcada y el avance."""
    img = Image.new("RGB", (ANCHO, ALTO), NAVY)
    dib = ImageDraw.Draw(img)

    dib.text((90, 62), titulo, font=fuente("negrita", 52), fill=TINTA)
    dib.text((90, 132), bajada, font=fuente("normal", 27), fill=APAGADO)

    # Marca discreta arriba a la derecha.
    dib.rounded_rectangle([ANCHO - 250, 66, ANCHO - 226, 90], radius=6,
                          fill=AMBAR)
    dib.text((ANCHO - 214, 64), "MV DAX Lab", font=fuente("negrita", 28),
             fill=TINTA)

    # La captura, escalada al ancho disponible y recortada si sobra alto.
    marco_x, marco_y = 90, 200
    marco_w = ANCHO - 2 * marco_x
    marco_h = ALTO - marco_y - 120
    shot = Image.open(captura).convert("RGB")
    escala = marco_w / shot.width
    nuevo = shot.resize((marco_w, max(1, int(shot.height * escala))),
                        Image.LANCZOS)
    if nuevo.height > marco_h:
        nuevo = nuevo.crop((0, 0, marco_w, marco_h))
    caja = Image.new("RGB", (marco_w, marco_h), NAVY2)
    caja.paste(nuevo, (0, 0))
    img.paste(caja, (marco_x, marco_y))
    dib.rectangle([marco_x - 1, marco_y - 1, marco_x + marco_w,
                   marco_y + marco_h], outline=LINEA, width=2)

    # Barra de avance: cuántas pestañas van.
    barra_y = ALTO - 62
    ancho_util = ANCHO - 2 * marco_x
    dib.line([(marco_x, barra_y), (marco_x + ancho_util, barra_y)],
             fill=LINEA, width=6)
    dib.line([(marco_x, barra_y),
              (marco_x + int(ancho_util * (indice + 1) / total), barra_y)],
             fill=AMBAR, width=6)
    dib.text((marco_x, barra_y + 16), f"{indice + 1} / {total}",
             font=fuente("mono", 22), fill=APAGADO)
    return img


def escribir_video(cuadros: list[tuple[Image.Image, float]],
                   destino: Path) -> Path:
    """Encadena (imagen, segundos) con fundidos y lo codifica a H.264."""
    import imageio_ffmpeg

    destino.parent.mkdir(parents=True, exist_ok=True)
    escritor = imageio_ffmpeg.write_frames(
        str(destino), (ANCHO, ALTO), fps=FPS, quality=7,
        macro_block_size=8,
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    escritor.send(None)

    n_fundido = int(SEG_FUNDIDO * FPS)
    try:
        for i, (img, segundos) in enumerate(cuadros):
            bytes_img = img.tobytes()
            total = int(segundos * FPS)

            # Fundido de entrada mezclando con el cuadro anterior. Solo estos
            # cuadros se recomponen; el resto se manda tal cual.
            if i > 0:
                previo = cuadros[i - 1][0]
                for k in range(n_fundido):
                    alfa = (k + 1) / n_fundido
                    mezcla = Image.blend(previo, img, alfa)
                    escritor.send(mezcla.tobytes())
                total -= n_fundido
            for _ in range(max(total, 1)):
                escritor.send(bytes_img)
    finally:
        escritor.close()
    return destino


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duracion_audio(ruta: Path) -> float | None:
    """Segundos de un MP3, leídos de la cabecera que imprime ffmpeg.

    Se parsea la salida de `ffmpeg -i` en vez de usar ffprobe porque
    imageio_ffmpeg trae ffmpeg pero NO ffprobe, y no vale la pena sumar una
    dependencia para leer un número.
    """
    salida = subprocess.run([_ffmpeg(), "-i", str(ruta)],
                            capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d\d):(\d\d\.\d+)", salida)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def sonorizar(mudo: Path, pistas: list[tuple[Path | None, float]]) -> None:
    """Le pega la narración al video, placa por placa, y pisa el archivo.

    Cada placa se convierte en un tramo de audio de EXACTAMENTE su duración:
    la locución al principio y silencio hasta completar. Así el total del
    audio es igual al total del video por construcción — la voz no se puede
    correr de la imagen aunque se cambie el guion o el orden de las placas.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes = []
        for i, (clip, segundos) in enumerate(pistas):
            parte = tmp / f"{i:03d}.wav"
            comun = ["-ar", "44100", "-ac", "2", "-t", f"{segundos:.4f}"]
            if clip is None:      # placa sin locución: silencio del mismo largo
                cmd = [_ffmpeg(), "-y", "-f", "lavfi", "-i",
                       "anullsrc=r=44100:cl=stereo", *comun, str(parte)]
            else:
                cmd = [_ffmpeg(), "-y", "-i", str(clip),
                       "-af", f"apad=whole_dur={segundos:.4f}", *comun,
                       str(parte)]
            subprocess.run(cmd, capture_output=True, check=True)
            partes.append(parte)

        lista = tmp / "partes.txt"
        lista.write_text("".join(f"file '{p}'\n" for p in partes),
                         encoding="utf-8")
        pista = tmp / "voz.wav"
        subprocess.run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lista), "-c", "copy", str(pista)],
                       capture_output=True, check=True)

        con_voz = tmp / "con-voz.mp4"
        subprocess.run([_ffmpeg(), "-y", "-i", str(mudo), "-i", str(pista),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", "-shortest", str(con_voz)],
                       capture_output=True, check=True)
        shutil.move(str(con_voz), str(mudo))


def construir(idioma: str) -> Path:
    textos = VIDEO[idioma]
    carpeta = RAIZ / "web" / "assets" / "img" / idioma
    if not carpeta.exists():
        raise FileNotFoundError(
            f"No hay capturas en {carpeta}. Corré primero: "
            f"python daxlingo/media/capturar.py --idioma {idioma}")

    # El cierre lleva el dominio real, que se resuelve al render: si el
    # sitio cambia, se regenera el video y listo.
    cierre = tuple(t.replace("{sitio}", dominio())
                   for t in textos["_cierre"])

    # Si hay narración, manda ella: la placa dura lo que dura la locución más
    # un respiro. Si no la hay, se usan los tiempos fijos de siempre y el
    # video sale mudo, igual que antes.
    def compas(clave: str, por_defecto: float) -> tuple[Path | None, float]:
        clip = narracion.ruta(idioma, clave)
        if not clip.exists():
            return None, por_defecto
        dur = duracion_audio(clip)
        if dur is None:
            return None, por_defecto
        return clip, max(por_defecto, dur + RESPIRO_VOZ)

    cuadros: list[tuple[Image.Image, float]] = []
    pistas: list[tuple[Path | None, float]] = []

    clip, seg = compas("_intro", SEG_INTRO)
    cuadros.append((cuadro_titulo(*textos["_intro"]), seg))
    pistas.append((clip, seg))

    presentes = [(slug, clave) for slug, clave in GUION
                 if (carpeta / f"{slug}.png").exists()]
    for i, (slug, clave) in enumerate(presentes):
        titulo, bajada = textos[clave]
        clip, seg = compas(clave, SEG_POR_PESTANA)
        cuadros.append((cuadro_pestana(carpeta / f"{slug}.png", titulo,
                                       bajada, i, len(presentes)), seg))
        pistas.append((clip, seg))

    clip, seg = compas("_cierre", SEG_CIERRE)
    cuadros.append((cuadro_titulo(*cierre), seg))
    pistas.append((clip, seg))

    destino = RAIZ / "web" / "assets" / "video" / f"demo-{idioma}.mp4"
    escribir_video(cuadros, destino)

    if any(clip for clip, _ in pistas):
        # Los segundos que se le pasan al audio son los que el video usó de
        # verdad: escribir_video redondea a cuadros enteros, y sin ese mismo
        # redondeo la pista se iría corriendo unos milisegundos por placa.
        exactas = [(clip, int(seg * FPS) / FPS) for clip, seg in pistas]
        sonorizar(destino, exactas)
        print(f"  ♪ narración pegada ({sum(s for _, s in exactas):.0f} s)")
    else:
        print("  · sin narración (corré media/narracion.py); el video sale mudo")
    return destino


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--idioma", choices=IDIOMAS)
    args = ap.parse_args()

    for idioma in ([args.idioma] if args.idioma else list(IDIOMAS)):
        print(f"▶ Componiendo el video en «{idioma}»…")
        ruta = construir(idioma)
        mb = ruta.stat().st_size / 1_048_576
        print(f"  ✓ {ruta.relative_to(RAIZ)} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
