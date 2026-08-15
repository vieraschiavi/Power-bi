# MV DAX Lab

**Tu modelo de Power BI, explicado, corregido y exportado.**
*Your Power BI model: explained, fixed and exported. · Seu modelo de Power BI,
explicado, corrigido e exportado.*

Producto completo —programa, web y video, los tres en **ES / EN / PT**— para
trabajar modelos de Power BI con IA: carga `.pbit`, **PBIP**, `model.bim` (y
lectura parcial de `.pbix`), audita el modelo, genera y explica DAX en tu
idioma, transforma, y lo devuelve como `.pbit`/PBIP **con tablero, filtros y
navegación** — o lo publica en **Microsoft Fabric**.

| Pieza | Dónde | Qué es |
|---|---|---|
| Motor | `dxl/` | Python puro, sin dependencias. Importable y testeable solo. |
| App | `app/app.py` | Streamlit, 14 pestañas, trilingüe. |
| Escritorio | `desktop/` | Electron + React con instalador `.exe` (NSIS). |
| Overlay | `overlay/` | F9 / Shift+F9 / Ctrl+F9 sobre cualquier pantalla. |
| MCP | `mcp/servidor.py` | Servidor MCP propio (stdio, sin dependencias). |
| Web | `web/` | Landing trilingüe con capturas y video reales. |
| Pagos | `api/` | MercadoPago + licencias firmadas (Vercel). |
| Media | `media/` | Genera las capturas y el video desde la app real. |
| Tests | `tests/` | 66 tests Python + 15 Node. |

## Correr

```bash
pip install -r daxlingo/requirements.txt
streamlit run daxlingo/app/app.py          # la app completa
python3 -m pytest daxlingo/tests/ -q       # 66 tests, sin red
cd daxlingo/api && node --test             # 15 tests de pagos/licencias
python3 daxlingo/mcp/servidor.py           # servidor MCP (stdio)
python3 daxlingo/overlay/DAX_Overlay.py    # overlay de escritorio
cd daxlingo/desktop && npm install && npm start   # ventana Electron
```

## El motor (`dxl/`)

| Módulo | Responsabilidad |
|---|---|
| `modelo.py` | Carga/escritura `.pbit` (zip UTF-16), PBIP, `.bim`; lectura parcial `.pbix` con aviso honesto |
| `catalogo.py` | Vista aplanada del TMSL, búsqueda difusa (acentos, singular/plural) y validación anti-alucinación |
| `analizador.py` | 15 reglas de buenas prácticas **agrupadas**, con severidad, arreglo automático y puntaje de salud |
| `explicador.py` | Explica DAX sin IA ni red (base propia de ~60 funciones) |
| `generador.py` | NL→DAX: motor de reglas local + IA opcional; **todo validado contra el catálogo** |
| `transformador.py` | Transformaciones sobre copia: DIVIDE, formatos, claves, tabla de medidas, renombrar con propagación |
| `tablero.py` | Layout del reporte con `prototypeQuery` reales: KPIs, línea, barras, dona, matriz, slicers y navegación |
| `ejercicios.py` | Academia: verificación local normalizada, XP y niveles |
| `asistente.py` | Bandeja overlay ↔ app + parser respuesta-IA → acción aplicable |
| `proveedores_ia.py` | 8 proveedores de IA (BYOK) + configuración MCP por agente |
| `ia.py` | Prompts y usos de dominio sobre ese transporte |
| `licencia.py` | Firma/verificación de claves, ediciones y prueba de 7 días |
| `fabric.py` | Publicación en Fabric por API REST + guía de integración Git |
| `herramientas.py` | Las 10 herramientas del stack, operativas |
| `i18n.py` | Todos los textos en ES/EN/PT, con test de paridad |

## La IA que elijas (BYOK)

Claude, ChatGPT (OpenAI), Gemini, **Copilot / Azure OpenAI**, Groq, Mistral,
DeepSeek y **Ollama local**. Se eligen proveedor y modelo en ⚙️ Configuración,
con botón para probar la conexión; si el modelo está saturado cae al siguiente
con reintentos. **Sin ninguna clave** funcionan el motor de reglas, el
analizador, el explicador, el mapa de relaciones, la Academia y todo el export.

## MCP

⚙️ Configuración y 🛠️ Herramientas generan el archivo de configuración para el
agente que uses — Claude Code/Desktop (`.mcp.json`), ChatGPT/Codex
(`mcp.json`), GitHub Copilot (`.vscode/mcp.json`) o Gemini CLI
(`.gemini/settings.json`) — con **cuatro servidores**:

1. **`powerbi-remote`** — el MCP remoto oficial de Power BI:
   `https://api.fabric.microsoft.com/v1/mcp/powerbi` (Entra ID). Modelos
   semánticos publicados, DAX y documentación.
2. **`fabric-core`** — el MCP remoto oficial de Fabric Core (preview):
   `https://api.fabric.microsoft.com/v1/mcp/core` (Entra ID). Workspaces,
   items, permisos, carpetas y capacidades del tenant.
3. **`powerbi-modeling`** — el MCP local de Microsoft contra Power BI Desktop.
4. **`mv-dax-lab`** — el propio: `cargar_modelo`, `resumen_modelo`,
   `analizar_modelo`, `generar_dax`, `explicar_dax`, `exportar`.

Los dos primeros son servidores **distintos**, no el mismo con otra ruta:
`powerbi` contesta sobre el modelo semántico y `core` sobre el tenant. Publicar
desde la app (`dxl/fabric.py`) necesita saber a qué workspace va, y eso lo
contesta `core`.

## Ediciones y licencias

| Edición | Instalador | Qué habilita | ¿La variable de entorno la cambia? |
|---|---|---|---|
| `owner` | `MV-DAX-Lab-OWNER-Setup` | Todo, sin vencimiento | sí (en desarrollo) |
| `profesional` | `MV-DAX-Lab-Setup` | Todo mientras la licencia esté vigente | **no** |
| `demo` | `MV-DAX-Lab-DEMO-Setup` | 7 días con todo | **no** |

La edición viene **horneada** en `edicion.json` y **bloqueada** en las que se
venden: si no, el cliente pone `MVDAX_EDICION=owner` y se lleva el producto
gratis (hay un test que lo verifica). Vencida la prueba **siguen abiertos**
analizador, explicador, relaciones y Academia; se cierran generar,
transformar, exportar, Fabric y overlay.

⚠️ **La edición OWNER no se publica en un release público.** Regala el producto
entero. Publicá solo `cliente` y `demo`.

```bash
cd daxlingo/desktop
MVDAX_LICENSE_SECRET=... node scripts/build-instaladores.js todos
```

## Instalador de Windows

`npm run dist` genera un NSIS que **deja elegir la carpeta**, crea acceso en
**escritorio, barra de tareas y menú Inicio** con el icono del producto, se
registra en **Agregar o quitar programas** y trae **desinstalador** que
pregunta antes de borrar tus datos (licencia y preferencias sobreviven a una
reinstalación). El runtime de Python va embebido: el cliente **no instala
Python** — ver `desktop/runtime/LEEME.md`.

## Precio: uno solo, dos formas de pagarlo

No hay versiones recortadas — las dos modalidades desbloquean exactamente lo
mismo:

| Modalidad | Precio | Licencia |
|---|---|---|
| Prueba | 7 días gratis | Todo desbloqueado, sin tarjeta |
| Mensual | **USD 10 / mes** | Clave de 32 días que se renueva sola mientras la suscripción siga autorizada |
| Pago único | **USD 99** | Perpetua, sin vencimiento |

La mensual usa **suscripción** de MercadoPago (`preapproval`), no un pago
suelto: el corte es el vencimiento de la clave. Si el cliente da de baja o el
cobro falla, deja de renovarse y caduca sola — el programa no necesita llamar
a casa ni nosotros guardar nada. Son 32 días y no 30 a propósito: un cobro que
se acredita un día tarde no puede dejar afuera a alguien que pagó.

## Web y pagos

`web/` es la landing trilingüe (HTML/CSS/JS vanilla, sin build) con las
**capturas reales** de las 14 pestañas en los 3 idiomas y el **video demo** por
idioma. `api/` son las funciones serverless de MercadoPago:

- `checkout.js` — bifurca según la modalidad: `/checkout/preferences` para el
  pago único y `/preapproval` para la suscripción (token solo en el servidor;
  conversión a UYU porque un collector uruguayo rechaza preferencias en USD).
- `verificar-pago.js` — consulta el pago único **contra la API real** y solo
  entonces firma la licencia.
- `verificar-suscripcion.js` — consulta el estado de la suscripción y emite
  (o renueva) la clave mensual con vencimiento.
- `_licencia.js` — firma HMAC-SHA256, **mismo formato** que `dxl/licencia.py`
  (hay un test que compara las dos implementaciones byte a byte).

El deploy sale de la raíz del repo (`vercel.json` → `outputDirectory:
daxlingo/web`, funciones en `/api`). Variables necesarias: `MP_ACCESS_TOKEN`,
`MVDAX_LICENSE_SECRET`, y opcionalmente `MP_CURRENCY` / `MP_TASA_UYU`.

## Capturas y video: se regeneran, no se dibujan

```bash
python3 daxlingo/media/capturar.py      # levanta la app real y la fotografía
python3 daxlingo/media/build_video.py   # arma demo-es/en/pt.mp4 (1:46 c/u)
```

`capturar.py` arranca la app, carga el modelo demo, hace clic en cada pestaña
y guarda la captura. Si una pestaña se rompe, **la captura sale rota y nos
enteramos nosotros**, no el cliente.

## Decisiones honestas

- **`.pbix`**: su modelo tabular es un binario propietario de Analysis
  Services; no se puede leer desde afuera de Power BI. Se lee el reporte +
  catálogo parcial y se explica el camino corto (.pbit/PBIP) en vez de
  inventar lo que no se puede leer.
- **IA aditiva, nunca bloqueante**: sin clave el producto sigue siendo útil.
- **Anti-alucinación**: toda expresión —de reglas o de IA— se valida contra el
  catálogo real; una referencia inexistente la descarta.
- **HMAC en las licencias**: la clave que verifica es la misma que firma, y en
  el escritorio viaja horneada en el build. Frena el caso masivo (pasar la
  clave, inventarla, editar el vencimiento); el corte de verdad es
  server-side, contra la API de MercadoPago. Está explicado en el docstring de
  `licencia.py`, no escondido.
- **Los modelos no salen de tu máquina**: el único tráfico es la consulta a la
  IA que configures y la publicación a Fabric, ambas con tus claves.
