# MV DAX Lab

**Tu modelo de Power BI, explicado, corregido y exportado.**

Plataforma estilo Kobra para DAX / Power BI / Fabric: carga un modelo real
(`.pbit`, proyecto **PBIP**, `model.bim`, y lectura parcial de `.pbix`), lo
audita, genera y explica DAX en español, lo transforma, y lo devuelve como
`.pbit`/PBIP **con tablero, filtros y navegación** — o lo publica en Fabric.
Incluye una **Academia DAX** gamificada (concepto inspirado en plataformas de
práctica tipo "Duolingo de DAX", con contenido 100% propio), el **DAX
Overlay** de escritorio (F9 / Shift+F9 / Ctrl+F9) y tres servidores **MCP**
para agentes de IA.

## Correr

```bash
pip install -r daxlingo/requirements.txt
streamlit run daxlingo/app/app.py          # la app completa
python3 -m pytest daxlingo/tests/ -q       # la suite (39 tests, sin red)
python3 daxlingo/mcp/servidor.py           # servidor MCP propio (stdio)
python3 daxlingo/overlay/DAX_Overlay.py    # overlay de escritorio (pide GUI)
```

La landing comercial está en `daxlingo/web/index.html` (HTML autocontenido,
sin build).

## Qué hace cada módulo (`dxl/`)

| Módulo | Responsabilidad |
|---|---|
| `modelo.py` | Carga/escritura `.pbit` (zip UTF-16), PBIP, `.bim`; lectura parcial `.pbix` con aviso honesto (el modelo del `.pbix` es un binario propietario) |
| `catalogo.py` | Vista aplanada del TMSL + búsqueda difusa (sin acentos, singular/plural) + validación de referencias DAX (anti-alucinación) |
| `analizador.py` | 15 reglas de buenas prácticas con severidad, arreglo y auto-fix; puntaje de salud 0-100 |
| `explicador.py` | Explica DAX en español sin IA: funciones (KB propia de ~60), contexto, pasos, nivel |
| `generador.py` | NL→DAX: motor de reglas local (total, %, YTD, YoY, media móvil, ranking, top N…) + Claude opcional (BYOK); **todo validado contra el catálogo** |
| `transformador.py` | Transformaciones sobre copia: DIVIDE, formatos, ocultar claves, tabla de medidas, renombrar con propagación, agregar/eliminar medida |
| `tablero.py` | Genera el layout del reporte (KPIs, línea, barras, dona, matriz, slicers, botones de navegación) con `prototypeQuery` reales |
| `ejercicios.py` | Academia: verificación local normalizada, XP y niveles (banco en `datos/ejercicios.json`) |
| `asistente.py` | Bandeja overlay ↔ app (archivos JSON) + parser respuesta-IA → acción (medida / columna calculada) |
| `ia.py` | Cliente Claude compartido: modelos a elección con fallback y reintentos ante saturación |
| `fabric.py` | Publicación en Fabric por API REST (token BYOK) + guía de integración Git del PBIP |
| `herramientas.py` | Las 10 herramientas del stack, operativas: detección, export `.dax`/`.bim`, config MCP |

## MCP (agentes de IA)

La acción «Configuración MCP» (pestaña 🛠️ Herramientas) genera un
`.mcp.json` con tres servidores:

1. **`powerbi-remote`** — el MCP remoto oficial de Power BI:
   `https://api.fabric.microsoft.com/v1/mcp/powerbi` (autenticación Entra
   ID; inspección de modelos publicados, gestión de DAX, documentación).
2. **`powerbi-modeling`** — el MCP local de Microsoft contra Power BI
   Desktop (Windows).
3. **`mv-dax-lab`** — el servidor propio (`mcp/servidor.py`, stdio, sin
   dependencias): `cargar_modelo`, `resumen_modelo`, `analizar_modelo`,
   `generar_dax` (con `aplicar`), `explicar_dax`, `exportar`.

## DAX Overlay (escritorio)

Adaptación para Power BI del SQL Overlay del autor. `pip install anthropic
pynput pillow` y `python daxlingo/overlay/DAX_Overlay.py`:

| Atajo | Acción |
|---|---|
| `F9` | Captura **toda la pantalla** y la resuelve con Claude |
| `Shift+F9` | Seleccionás un **rectángulo** con el mouse |
| `Ctrl+F9` | Ventana para **escribir la consulta** sin captura |
| `Ctrl+Shift+M` | Limpia la memoria de capturas previas |

Modelos en cadena (editable arriba del archivo): Opus 5 → Sonnet 5 →
Haiku 4.5, con reintentos ante saturación. Cada respuesta va a la **bandeja**
(`~/.mvdaxlab/bandeja`); la pestaña «🖥️ Asistente de pantalla» de la app la
levanta y aplica las medidas/columnas propuestas al modelo cargado.

## Decisiones honestas

- **`.pbix`**: el modelo tabular viaja comprimido en un binario propietario
  de Analysis Services; no se puede leer desde afuera de Power BI. Se lee el
  reporte + catálogo parcial y se explica el camino (.pbit/PBIP) — no se
  inventa lo que no se puede leer.
- **IA aditiva, nunca bloqueante**: sin API key funcionan el motor de reglas,
  el analizador, el explicador, la Academia y el export completo.
- **Anti-alucinación**: toda expresión generada (por reglas o por IA) se
  valida contra el catálogo real; una referencia inexistente la descarta.
- **Los modelos no salen de tu máquina**: el único tráfico de red es la
  llamada opcional a la API de Anthropic o a Fabric, con tus claves.
