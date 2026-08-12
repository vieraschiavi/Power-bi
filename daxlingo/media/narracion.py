#!/usr/bin/env python3
"""
MV DAX Lab · La voz del video demo, en los tres idiomas.

Por qué pre-renderizado y no síntesis en vivo
---------------------------------------------
Es la misma decisión que en Kobra (`data/generar_audio_demo_voz.py`): la voz
del navegador o de un motor local suena robótica y arranca con latencia, y en
un video de venta eso se nota en el primer segundo. Acá se sintetiza UNA vez
con ElevenLabs y quedan los MP3 en `media/audio/<idioma>/<slug>.mp3`. El video
después los pega: no hay síntesis en tiempo de reproducción, así que no hay
lag ni desfasaje posible.

Cómo se evita el desfasaje
--------------------------
`build_video.py` NO usa una duración fija por placa. Mide cada MP3 y le da a
la placa el largo de su locución más un respiro. La imagen dura lo que dura la
voz, por definición — no puede correrse aunque se cambie el guion.

Sin claves no rompe nada
------------------------
Si no están `ELEVENLABS_API_KEY` y `ELEVENLABS_VOICE_ID`, no sintetiza y avisa.
El video se arma igual, mudo, como hasta ahora.

Uso:
    ELEVENLABS_API_KEY=... ELEVENLABS_VOICE_ID=... \\
        python daxlingo/media/narracion.py            # es, en, pt
    python daxlingo/media/narracion.py --idioma es
    python daxlingo/media/narracion.py --listar       # ver el guion, sin sintetizar

Para que la voz suene rioplatense hay que elegirla en elevenlabs.io →
Voice Library (buscar «Argentinian» / «Rioplatense») y poner ese id en
ELEVENLABS_VOICE_ID. Se puede dar una voz distinta por idioma con
ELEVENLABS_VOICE_ID_EN y ELEVENLABS_VOICE_ID_PT.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
AUDIO = Path(__file__).resolve().parent / "audio"

# El modelo multilingüe: la misma voz sirve para los tres idiomas.
MODELO_TTS = "eleven_multilingual_v2"
API = "https://api.elevenlabs.io/v1/text-to-speech"

# El guion hablado. NO es el texto de la placa: en pantalla va un título corto
# y acá va la frase que se escucha. Español rioplatense (voseo), como el resto
# del producto.
#
# Las claves son las mismas que en build_video.py — `_intro`, los 14 slugs de
# pestaña y `_cierre` — y hay un test que verifica que no falte ninguna en
# ningún idioma.
GUION: dict[str, dict[str, str]] = {
    "es": {
        "_intro": "MV DAX Lab. Cargá tu modelo de Power BI y en un minuto sabés "
                  "qué tiene mal, por qué, y cómo se arregla.",
        "guia": "Todo el ciclo queda verificable: inspeccionar, modelar, "
                "construir, validar, verificar y exportar.",
        "modelo": "Arrastrás tu punto pbit, tu PBIP o tu model punto bim. Te "
                  "muestra las tablas, las columnas y el DAX de cada medida.",
        "relaciones": "El modelo entero en un grafo: cardinalidades, el "
                      "calendario marcado, y las bidireccionales en rojo, que "
                      "son las que te rompen los totales.",
        "analizador": "Quince reglas de buenas prácticas, con severidad y con "
                      "el impacto real. Y el arreglo se aplica con un clic.",
        "generar": "Pedís la medida en tu idioma y sale el DAX, validado "
                   "contra tu catálogo. Si la columna no existe, no la inventa.",
        "explicador": "Pegás cualquier DAX y te explica qué calcula, qué hace "
                      "el contexto de filtro y de qué nivel es.",
        "transformar": "Renombrás con propagación, agregás columnas, cambiás "
                       "formatos. Siempre sobre una copia: tu modelo no se toca.",
        "exportar": "Volvés a Power BI con el tablero armado: KPIs, evolución, "
                    "barras, dona, matriz y filtros.",
        "fabric": "Publicás en Microsoft Fabric con tu token, o por la "
                  "integración Git del proyecto PBIP.",
        "overlay": "Apretás efe nueve sobre lo que estás mirando. Te lo explica "
                   "paso a paso y lo aplica al modelo.",
        "academia": "Diecisiete ejercicios en cinco niveles, con verificación "
                    "al instante y sin conexión.",
        "herramientas": "Se conecta con lo que ya usás: DAX Studio, Tabular "
                        "Editor, Bravo, ALM Toolkit y los tres servidores MCP.",
        "licencia": "Siete días con todo abierto. Después activás la clave que "
                    "te llega al pagar.",
        "configuracion": "La inteligencia artificial la elegís vos: Claude, "
                         "ChatGPT, Gemini o Copilot, con tu propia clave.",
        "_cierre": "Probalo con tu propio modelo. Siete días gratis.",
    },
    "en": {
        "_intro": "MV DAX Lab. Load your Power BI model and in a minute you know "
                  "what's wrong with it, why, and how to fix it.",
        "guia": "The whole cycle stays verifiable: inspect, model, build, "
                "validate, verify and export.",
        "modelo": "Drop in your dot pbit, your PBIP or your model dot bim. It "
                  "shows the tables, the columns and the DAX behind every measure.",
        "relaciones": "The whole model as a graph: cardinality, the marked date "
                      "table, and bidirectional links in red — the ones that "
                      "break your totals.",
        "analizador": "Fifteen best-practice rules, with severity and real "
                      "impact. And the fix applies in one click.",
        "generar": "Ask for the measure in your own language and the DAX comes "
                   "out validated against your catalog. If a column doesn't "
                   "exist, it won't invent it.",
        "explicador": "Paste any DAX and it tells you what it computes, what "
                      "filter context is doing, and how advanced it is.",
        "transformar": "Rename with propagation, add columns, change formats. "
                       "Always on a copy: your model is never touched.",
        "exportar": "Go back to Power BI with the report already built: KPIs, "
                    "trend, bars, donut, matrix and slicers.",
        "fabric": "Publish to Microsoft Fabric with your token, or through the "
                  "PBIP project's Git integration.",
        "overlay": "Press F9 on whatever you're looking at. It explains it step "
                   "by step and applies it to the model.",
        "academia": "Seventeen exercises across five levels, checked instantly "
                    "and with no connection.",
        "herramientas": "It plugs into what you already use: DAX Studio, Tabular "
                        "Editor, Bravo, ALM Toolkit and all three MCP servers.",
        "licencia": "Seven days with everything unlocked. Then you activate the "
                    "key that arrives when you pay.",
        "configuracion": "You pick the AI: Claude, ChatGPT, Gemini or Copilot, "
                         "with your own key.",
        "_cierre": "Try it on your own model. Seven days free.",
    },
    "pt": {
        "_intro": "MV DAX Lab. Carregue seu modelo do Power BI e em um minuto "
                  "você sabe o que está errado, por quê, e como se conserta.",
        "guia": "Todo o ciclo fica verificável: inspecionar, modelar, construir, "
                "validar, verificar e exportar.",
        "modelo": "Você arrasta seu ponto pbit, seu PBIP ou seu model ponto bim. "
                  "Mostra as tabelas, as colunas e o DAX de cada medida.",
        "relaciones": "O modelo inteiro em um grafo: cardinalidades, o calendário "
                      "marcado, e as bidirecionais em vermelho, que são as que "
                      "quebram seus totais.",
        "analizador": "Quinze regras de boas práticas, com severidade e com o "
                      "impacto real. E a correção se aplica com um clique.",
        "generar": "Você pede a medida no seu idioma e sai o DAX, validado "
                   "contra o seu catálogo. Se a coluna não existe, ele não inventa.",
        "explicador": "Cole qualquer DAX e ele explica o que calcula, o que o "
                      "contexto de filtro faz e qual é o nível.",
        "transformar": "Renomeie com propagação, adicione colunas, mude formatos. "
                       "Sempre sobre uma cópia: seu modelo não é tocado.",
        "exportar": "Volte ao Power BI com o painel pronto: KPIs, evolução, "
                    "barras, rosca, matriz e filtros.",
        "fabric": "Publique no Microsoft Fabric com seu token, ou pela "
                  "integração Git do projeto PBIP.",
        "overlay": "Aperte F9 no que você está olhando. Ele explica passo a "
                   "passo e aplica ao modelo.",
        "academia": "Dezessete exercícios em cinco níveis, com verificação "
                    "instantânea e sem conexão.",
        "herramientas": "Conecta com o que você já usa: DAX Studio, Tabular "
                        "Editor, Bravo, ALM Toolkit e os três servidores MCP.",
        "licencia": "Sete dias com tudo liberado. Depois você ativa a chave que "
                    "chega ao pagar.",
        "configuracion": "A inteligência artificial você escolhe: Claude, "
                         "ChatGPT, Gemini ou Copilot, com sua própria chave.",
        "_cierre": "Teste com o seu próprio modelo. Sete dias grátis.",
    },
}


def voz_de(idioma: str) -> str:
    """Id de voz para el idioma. Una sola alcanza (el modelo es multilingüe),
    pero se puede afinar por idioma si alguna suena mejor."""
    return (os.environ.get(f"ELEVENLABS_VOICE_ID_{idioma.upper()}")
            or os.environ.get("ELEVENLABS_VOICE_ID", ""))


def ruta(idioma: str, slug: str) -> Path:
    return AUDIO / idioma / f"{slug}.mp3"


def sintetizar(texto: str, voz: str, clave: str) -> bytes:
    """Un pedido a ElevenLabs. Devuelve los bytes del MP3."""
    import json
    cuerpo = json.dumps({
        "text": texto,
        "model_id": MODELO_TTS,
        # stability/similarity moderadas: una locución de producto tiene que
        # sonar pareja entre placas, no interpretada distinto en cada una.
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75,
                           "style": 0.15, "use_speaker_boost": True},
    }).encode("utf-8")
    pedido = urllib.request.Request(
        f"{API}/{voz}", data=cuerpo, method="POST",
        headers={"xi-api-key": clave, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(pedido, timeout=120) as r:
        return r.read()


def generar(idioma: str, rehacer: bool = False) -> int:
    """Sintetiza lo que falte de un idioma. Devuelve cuántos archivos escribió."""
    clave = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voz = voz_de(idioma).strip()
    if not clave or not voz:
        print(f"  ⚠️  {idioma}: falta ELEVENLABS_API_KEY o ELEVENLABS_VOICE_ID; "
              "no se sintetiza (el video se arma mudo)")
        return 0

    (AUDIO / idioma).mkdir(parents=True, exist_ok=True)
    escritos = 0
    for slug, texto in GUION[idioma].items():
        destino = ruta(idioma, slug)
        if destino.exists() and not rehacer:
            print(f"  · {idioma}/{slug}.mp3 ya estaba")
            continue
        try:
            destino.write_bytes(sintetizar(texto, voz, clave))
            escritos += 1
            print(f"  ✓ {idioma}/{slug}.mp3")
        except urllib.error.HTTPError as e:
            print(f"  ✗ {idioma}/{slug}: HTTP {e.code} — {e.read()[:200]!r}")
            return escritos
        except Exception as e:            # red caída, timeout…
            print(f"  ✗ {idioma}/{slug}: {e}")
            return escritos
    return escritos


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--idioma", choices=sorted(GUION))
    p.add_argument("--rehacer", action="store_true",
                   help="volver a sintetizar aunque el MP3 ya exista")
    p.add_argument("--listar", action="store_true",
                   help="mostrar el guion y salir, sin llamar a la API")
    a = p.parse_args()

    idiomas = [a.idioma] if a.idioma else sorted(GUION)

    if a.listar:
        for idi in idiomas:
            print(f"\n=== {idi} ===")
            for slug, texto in GUION[idi].items():
                print(f"  [{slug}] {texto}")
        return 0

    total = 0
    for idi in idiomas:
        print(f"\n▶ Narración en «{idi}»…")
        total += generar(idi, a.rehacer)
    print(f"\n{total} archivo(s) nuevo(s) en {AUDIO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
