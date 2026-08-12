"""
MV DAX Lab · Textos trilingües (ES / EN / PT).

Todo texto de cara al usuario vive acá con las tres claves. La paridad está
cubierta por tests: si agregás una clave y le falta un idioma, el test rompe.
La misma tabla alimenta la app de escritorio; la landing tiene su espejo en
`web/assets/i18n.js` (también con test de paridad contra este archivo).
"""
from __future__ import annotations

IDIOMAS = ("es", "en", "pt")
NOMBRES_IDIOMA = {"es": "Español", "en": "English", "pt": "Português"}
IDIOMA_DEFECTO = "es"

T: dict[str, dict[str, str]] = {
    # ---- marca y encabezado -------------------------------------------
    "lema": {
        "es": "Tu modelo de Power BI, explicado, corregido y exportado.",
        "en": "Your Power BI model: explained, fixed and exported.",
        "pt": "Seu modelo de Power BI, explicado, corrigido e exportado.",
    },
    "idioma": {"es": "Idioma", "en": "Language", "pt": "Idioma"},
    # Ojo: este texto se inyecta dentro de un <div>, así que va en HTML, no en
    # markdown — los asteriscos saldrían literales.
    "sin_modelo": {
        "es": "Sin modelo cargado — empezá por la pestaña <b>📥 Modelo</b>.",
        "en": "No model loaded — start on the <b>📥 Model</b> tab.",
        "pt": "Sem modelo carregado — comece pela aba <b>📥 Modelo</b>.",
    },
    "tablas": {"es": "Tablas", "en": "Tables", "pt": "Tabelas"},
    "columnas": {"es": "Columnas", "en": "Columns", "pt": "Colunas"},
    "medidas": {"es": "Medidas", "en": "Measures", "pt": "Medidas"},
    "relaciones": {"es": "Relaciones", "en": "Relationships", "pt": "Relações"},

    # ---- pestañas ------------------------------------------------------
    "tab_guia": {"es": "❓ Guía", "en": "❓ Guide", "pt": "❓ Guia"},
    "tab_modelo": {"es": "📥 Modelo", "en": "📥 Model", "pt": "📥 Modelo"},
    "tab_relaciones": {"es": "🕸️ Relaciones", "en": "🕸️ Relationships",
                       "pt": "🕸️ Relações"},
    "tab_analizador": {"es": "🩺 Analizador", "en": "🩺 Analyzer",
                       "pt": "🩺 Analisador"},
    "tab_generar": {"es": "🤖 Generar DAX", "en": "🤖 Generate DAX",
                    "pt": "🤖 Gerar DAX"},
    "tab_explicar": {"es": "📖 Explicador", "en": "📖 Explainer",
                     "pt": "📖 Explicador"},
    "tab_transformar": {"es": "🔧 Transformar", "en": "🔧 Transform",
                        "pt": "🔧 Transformar"},
    "tab_exportar": {"es": "📊 Exportar", "en": "📊 Export",
                     "pt": "📊 Exportar"},
    "tab_fabric": {"es": "🟪 Fabric", "en": "🟪 Fabric", "pt": "🟪 Fabric"},
    "tab_overlay": {"es": "🖥️ Asistente de pantalla",
                    "en": "🖥️ Screen assistant",
                    "pt": "🖥️ Assistente de tela"},
    "tab_academia": {"es": "🎓 Academia DAX", "en": "🎓 DAX Academy",
                     "pt": "🎓 Academia DAX"},
    "tab_herramientas": {"es": "🛠️ Herramientas", "en": "🛠️ Tools",
                         "pt": "🛠️ Ferramentas"},
    "tab_licencia": {"es": "🔑 Licencia", "en": "🔑 License",
                     "pt": "🔑 Licença"},
    "tab_config": {"es": "⚙️ Configuración", "en": "⚙️ Settings",
                   "pt": "⚙️ Configuração"},

    # ---- guía ----------------------------------------------------------
    "guia_titulo": {
        "es": "El ciclo completo, verificable",
        "en": "The full cycle, verifiable",
        "pt": "O ciclo completo, verificável",
    },
    "guia_ciclo": {
        "es": "**inspeccionar → modelar → construir → validar → verificar → exportar**",
        "en": "**inspect → model → build → validate → verify → export**",
        "pt": "**inspecionar → modelar → construir → validar → verificar → exportar**",
    },
    "guia_pasos": {
        "es": """
1. **📥 Modelo** — cargá un `.pbit`, un proyecto **PBIP**, un `model.bim` o un
   `.pbix` (de un `.pbix` se lee el reporte y un catálogo parcial; el modelo
   tabular viaja en un binario propietario — la app te dice cómo obtener el
   completo).
2. **🕸️ Relaciones** — el modelo dibujado: tablas, cardinalidades, calendario.
3. **🩺 Analizador** — reglas de buenas prácticas con severidad y arreglo; las
   automáticas se aplican con un clic.
4. **🤖 Generar DAX** — pedile medidas en tu idioma. Sin API key usa el motor
   de reglas local; con tu clave, pedidos libres con la IA que elijas. En
   ambos casos la expresión se **valida contra el catálogo**.
5. **🔧 Transformar** — renombrar con propagación, columnas calculadas, tabla
   de medidas, formatos.
6. **📊 Exportar** — de vuelta a `.pbit` o **PBIP**, con **tablero automático**:
   KPIs, evolución, barras, dona, matriz y filtros.
7. **🟪 Fabric** — publicación directa por API o vía integración Git del PBIP.
8. **🖥️ Asistente de pantalla** — F9 / Shift+F9 / Ctrl+F9 y lo que la IA
   propone se aplica acá con un clic.
9. **🎓 Academia DAX** — práctica por niveles con verificación instantánea.
""",
        "en": """
1. **📥 Model** — load a `.pbit`, a **PBIP** project, a `model.bim` or a
   `.pbix` (from a `.pbix` we read the report and a partial catalog; its
   tabular model ships as a proprietary binary — the app tells you how to get
   the full one).
2. **🕸️ Relationships** — the model drawn: tables, cardinality, calendar.
3. **🩺 Analyzer** — best-practice rules with severity and fix; the automatic
   ones apply in one click.
4. **🤖 Generate DAX** — ask for measures in your language. With no API key it
   uses the local rules engine; with your key, free-form requests through the
   AI you choose. Either way the expression is **validated against the
   catalog**.
5. **🔧 Transform** — rename with reference propagation, calculated columns,
   measures table, formats.
6. **📊 Export** — back to `.pbit` or **PBIP**, with an **automatic report**:
   KPIs, trend, bars, donut, matrix and slicers.
7. **🟪 Fabric** — direct API publish or via the PBIP Git integration.
8. **🖥️ Screen assistant** — F9 / Shift+F9 / Ctrl+F9, and whatever the AI
   proposes applies here in one click.
9. **🎓 DAX Academy** — levelled practice with instant checking.
""",
        "pt": """
1. **📥 Modelo** — carregue um `.pbit`, um projeto **PBIP**, um `model.bim` ou
   um `.pbix` (de um `.pbix` lemos o relatório e um catálogo parcial; o modelo
   tabular vem num binário proprietário — o app explica como obter o
   completo).
2. **🕸️ Relações** — o modelo desenhado: tabelas, cardinalidades, calendário.
3. **🩺 Analisador** — regras de boas práticas com severidade e correção; as
   automáticas se aplicam com um clique.
4. **🤖 Gerar DAX** — peça medidas no seu idioma. Sem API key usa o motor de
   regras local; com sua chave, pedidos livres com a IA que escolher. Nos dois
   casos a expressão é **validada contra o catálogo**.
5. **🔧 Transformar** — renomear com propagação, colunas calculadas, tabela de
   medidas, formatos.
6. **📊 Exportar** — de volta a `.pbit` ou **PBIP**, com **painel automático**:
   KPIs, evolução, barras, rosca, matriz e filtros.
7. **🟪 Fabric** — publicação direta por API ou via integração Git do PBIP.
8. **🖥️ Assistente de tela** — F9 / Shift+F9 / Ctrl+F9 e o que a IA propõe se
   aplica aqui com um clique.
9. **🎓 Academia DAX** — prática por níveis com verificação instantânea.
""",
    },
    "guia_demo": {
        "es": "La demo trae un modelo de ejemplo con 117 medidas y 20 tablas, "
              "listo en **📥 Modelo**, sin subir nada.",
        "en": "The demo ships an example model with 117 measures and 20 "
              "tables, ready in **📥 Model**, with nothing to upload.",
        "pt": "A demo traz um modelo de exemplo com 117 medidas e 20 tabelas, "
              "pronto em **📥 Modelo**, sem enviar nada.",
    },

    # ---- modelo --------------------------------------------------------
    "cargar_modelo": {"es": "Cargar un modelo", "en": "Load a model",
                      "pt": "Carregar um modelo"},
    "arrastra": {
        "es": "Arrastrá un .pbit, .pbix, model.bim o un PBIP comprimido (.zip)",
        "en": "Drop a .pbit, .pbix, model.bim or a zipped PBIP (.zip)",
        "pt": "Arraste um .pbit, .pbix, model.bim ou um PBIP em .zip",
    },
    "btn_cargar": {"es": "Cargar archivo", "en": "Load file",
                   "pt": "Carregar arquivo"},
    "modelo_demo": {"es": "Modelo de ejemplo · 117 medidas, 20 tablas",
                    "en": "Example model · 117 measures, 20 tables",
                    "pt": "Modelo de exemplo · 117 medidas, 20 tabelas"},
    "btn_demo": {"es": "Cargar el modelo demo", "en": "Load the demo model",
                 "pt": "Carregar o modelo demo"},
    "no_se_pudo_cargar": {"es": "No se pudo cargar", "en": "Could not load",
                          "pt": "Não foi possível carregar"},
    "catalogo_parcial": {"es": "catálogo PARCIAL", "en": "PARTIAL catalog",
                         "pt": "catálogo PARCIAL"},
    "cambios_sesion": {
        "es": "Cambios aplicados en esta sesión:",
        "en": "Changes applied in this session:",
        "pt": "Mudanças aplicadas nesta sessão:",
    },
    "oculta": {"es": "Oculta", "en": "Hidden", "pt": "Oculta"},
    "calculada": {"es": "Calculada", "en": "Calculated", "pt": "Calculada"},
    "tipo": {"es": "Tipo", "en": "Type", "pt": "Tipo"},
    "columna": {"es": "Columna", "en": "Column", "pt": "Coluna"},
    "sin_formato": {"es": "sin formato", "en": "no format", "pt": "sem formato"},

    # ---- relaciones ----------------------------------------------------
    "mapa_modelo": {"es": "Mapa del modelo", "en": "Model map",
                    "pt": "Mapa do modelo"},
    "carga_primero": {"es": "Cargá un modelo primero.",
                      "en": "Load a model first.",
                      "pt": "Carregue um modelo primeiro."},
    "sin_relaciones": {
        "es": "El modelo no declara relaciones (o el catálogo es parcial).",
        "en": "The model declares no relationships (or the catalog is partial).",
        "pt": "O modelo não declara relações (ou o catálogo é parcial).",
    },
    "leyenda_grafo": {
        "es": "Flechas: lado muchos → lado uno. Rojo doble = bidireccional "
              "(revisar). Punteada = inactiva. Fondo claro = calendario.",
        "en": "Arrows: many side → one side. Double red = bidirectional "
              "(review). Dashed = inactive. Lighter fill = calendar table.",
        "pt": "Setas: lado muitos → lado um. Vermelho duplo = bidirecional "
              "(revisar). Tracejada = inativa. Fundo claro = calendário.",
    },

    # ---- analizador ----------------------------------------------------
    "buenas_practicas": {"es": "Buenas prácticas del modelo",
                         "en": "Model best practices",
                         "pt": "Boas práticas do modelo"},
    "salud": {"es": "Salud del modelo", "en": "Model health",
              "pt": "Saúde do modelo"},
    "hallazgos": {"es": "Hallazgos", "en": "Findings", "pt": "Achados"},
    "arreglables": {"es": "Arreglables en 1 clic", "en": "One-click fixes",
                    "pt": "Corrigíveis em 1 clique"},
    "por_que_importa": {"es": "Por qué importa", "en": "Why it matters",
                        "pt": "Por que importa"},
    "como_se_arregla": {"es": "Cómo se arregla", "en": "How to fix it",
                        "pt": "Como corrigir"},
    "arreglable_auto": {"es": "Arreglable automáticamente",
                        "en": "Fixable automatically",
                        "pt": "Corrigível automaticamente"},
    "btn_arreglar": {
        "es": "🔧 Aplicar todos los arreglos automáticos",
        "en": "🔧 Apply every automatic fix",
        "pt": "🔧 Aplicar todas as correções automáticas",
    },
    "cambios_aplicados": {"es": "cambio(s) aplicados.",
                          "en": "change(s) applied.",
                          "pt": "mudança(s) aplicadas."},
    "opinion_ia": {"es": "🧠 Opinión de la IA sobre este modelo",
                   "en": "🧠 AI opinion on this model",
                   "pt": "🧠 Opinião da IA sobre este modelo"},
    "consultando": {"es": "Consultando…", "en": "Asking…",
                    "pt": "Consultando…"},
    "sin_clave_opinion": {
        "es": "Con una API key (⚙️ Configuración) también tenés la opinión de "
              "la IA sobre el modelo.",
        "en": "With an API key (⚙️ Settings) you also get the AI's opinion on "
              "the model.",
        "pt": "Com uma API key (⚙️ Configuração) você também recebe a opinião "
              "da IA sobre o modelo.",
    },

    # ---- generar -------------------------------------------------------
    "gen_titulo": {
        "es": "De tu idioma a DAX, sin inventar columnas",
        "en": "From your language to DAX, without inventing columns",
        "pt": "Do seu idioma para DAX, sem inventar colunas",
    },
    "gen_pregunta": {"es": "¿Qué medida necesitás?",
                     "en": "Which measure do you need?",
                     "pt": "Qual medida você precisa?"},
    "gen_ejemplos": {
        "es": "p. ej.: total de ventas · % del total · ventas vs año anterior "
              "· media móvil 3 meses · ranking de país por ventas",
        "en": "e.g.: total sales · % of total · sales vs last year · 3-month "
              "moving average · ranking of country by sales",
        "pt": "ex.: total de vendas · % do total · vendas vs ano anterior · "
              "média móvel 3 meses · ranking de país por vendas",
    },
    "gen_motor": {"es": "motor", "en": "engine", "pt": "motor"},
    "gen_porque": {"es": "Por qué", "en": "Why", "pt": "Por quê"},
    "gen_agregar": {"es": "➕ Agregar esta medida al modelo",
                    "en": "➕ Add this measure to the model",
                    "pt": "➕ Adicionar esta medida ao modelo"},
    "formato": {"es": "formato", "en": "format", "pt": "formato"},

    # ---- explicador ----------------------------------------------------
    "exp_titulo": {"es": "Pegá DAX, salí entendiéndolo",
                   "en": "Paste DAX, walk away understanding it",
                   "pt": "Cole DAX, saia entendendo"},
    "exp_selector": {
        "es": "Explicar una medida del modelo o pegar DAX",
        "en": "Explain a model measure or paste DAX",
        "pt": "Explicar uma medida do modelo ou colar DAX",
    },
    "exp_pegar": {"es": "(pegar una expresión)", "en": "(paste an expression)",
                  "pt": "(colar uma expressão)"},
    "exp_expresion": {"es": "Expresión DAX", "en": "DAX expression",
                      "pt": "Expressão DAX"},
    "exp_nivel": {"es": "nivel", "en": "level", "pt": "nível"},
    "exp_funcion": {"es": "Función", "en": "Function", "pt": "Função"},
    "exp_que_hace": {"es": "Qué hace", "en": "What it does", "pt": "O que faz"},
    "exp_categoria": {"es": "Categoría", "en": "Category", "pt": "Categoria"},

    # ---- transformar ---------------------------------------------------
    "tr_titulo": {
        "es": "Transformaciones seguras (siempre sobre una copia)",
        "en": "Safe transformations (always on a copy)",
        "pt": "Transformações seguras (sempre sobre uma cópia)",
    },
    "tr_necesito_completo": {
        "es": "Necesito el modelo completo (.pbit / PBIP / .bim).",
        "en": "I need the full model (.pbit / PBIP / .bim).",
        "pt": "Preciso do modelo completo (.pbit / PBIP / .bim).",
    },
    "tr_renombrar": {
        "es": "Renombrar medida (propaga referencias)",
        "en": "Rename measure (propagates references)",
        "pt": "Renomear medida (propaga referências)",
    },
    "tr_medida": {"es": "Medida", "en": "Measure", "pt": "Medida"},
    "tr_nuevo_nombre": {"es": "Nuevo nombre", "en": "New name",
                        "pt": "Novo nome"},
    "tr_btn_renombrar": {"es": "Renombrar", "en": "Rename", "pt": "Renomear"},
    "tr_tabla_medidas": {"es": "Crear tabla de medidas",
                         "en": "Create measures table",
                         "pt": "Criar tabela de medidas"},
    "tr_btn_concentrar": {
        "es": "Concentrar todas las medidas en «_Medidas»",
        "en": "Move every measure into “_Medidas”",
        "pt": "Concentrar todas as medidas em “_Medidas”",
    },
    "tr_col_calculada": {"es": "Columna calculada", "en": "Calculated column",
                         "pt": "Coluna calculada"},
    "tr_tabla": {"es": "Tabla", "en": "Table", "pt": "Tabela"},
    "tr_nombre_col": {"es": "Nombre de la columna", "en": "Column name",
                      "pt": "Nome da coluna"},
    "tr_btn_agregar_col": {"es": "Agregar columna", "en": "Add column",
                           "pt": "Adicionar coluna"},
    "tr_formatos": {"es": "Formatos y claves", "en": "Formats and keys",
                    "pt": "Formatos e chaves"},
    "tr_btn_formatos": {
        "es": "Asignar formatos faltantes + ocultar claves",
        "en": "Assign missing formats + hide keys",
        "pt": "Atribuir formatos faltantes + ocultar chaves",
    },
    "nada_que_mover": {"es": "Nada que mover.", "en": "Nothing to move.",
                       "pt": "Nada a mover."},

    # ---- exportar ------------------------------------------------------
    "ex_titulo": {
        "es": "Exportar con tablero, filtros y navegación",
        "en": "Export with report, slicers and navigation",
        "pt": "Exportar com painel, filtros e navegação",
    },
    "ex_nombre": {"es": "Nombre del archivo", "en": "File name",
                  "pt": "Nome do arquivo"},
    "ex_medidas": {
        "es": "Medidas para el tablero automático (hasta 5; vacío = primeras 5)",
        "en": "Measures for the automatic report (up to 5; empty = first 5)",
        "pt": "Medidas para o painel automático (até 5; vazio = primeiras 5)",
    },
    "ex_generar_tablero": {
        "es": "Generar tablero automático (KPIs + evolución + barras + dona + "
              "matriz + filtros)",
        "en": "Generate automatic report (KPIs + trend + bars + donut + "
              "matrix + slicers)",
        "pt": "Gerar painel automático (KPIs + evolução + barras + rosca + "
              "matriz + filtros)",
    },
    "ex_conservar": {
        "es": "Conservar el reporte original si el archivo traía uno",
        "en": "Keep the original report if the file had one",
        "pt": "Manter o relatório original se o arquivo tinha um",
    },
    "ex_btn_pbit": {"es": "⬇️ Generar .pbit", "en": "⬇️ Build .pbit",
                    "pt": "⬇️ Gerar .pbit"},
    "ex_btn_pbip": {"es": "⬇️ Generar PBIP (zip)", "en": "⬇️ Build PBIP (zip)",
                    "pt": "⬇️ Gerar PBIP (zip)"},
    "ex_descargar": {"es": "Descargar", "en": "Download", "pt": "Baixar"},
    "ex_nota_pbit": {
        "es": "Doble clic → Power BI Desktop → Archivo → Guardar como → .pbix",
        "en": "Double-click → Power BI Desktop → File → Save as → .pbix",
        "pt": "Duplo clique → Power BI Desktop → Arquivo → Salvar como → .pbix",
    },
    "ex_nota_pbip": {
        "es": "Formato de control de versiones — y el que entiende la "
              "integración Git de Fabric.",
        "en": "The version-control format — and the one Fabric's Git "
              "integration understands.",
        "pt": "Formato de controle de versão — e o que a integração Git do "
              "Fabric entende.",
    },

    # ---- fabric --------------------------------------------------------
    "fab_titulo": {"es": "Publicar en Microsoft Fabric",
                   "en": "Publish to Microsoft Fabric",
                   "pt": "Publicar no Microsoft Fabric"},
    "fab_token": {"es": "Token de Fabric (no se guarda)",
                  "en": "Fabric token (never stored)",
                  "pt": "Token do Fabric (não é salvo)"},
    "fab_workspace": {"es": "Workspace", "en": "Workspace", "pt": "Workspace"},
    "fab_nombre_item": {"es": "Nombre del ítem", "en": "Item name",
                        "pt": "Nome do item"},
    "fab_btn": {"es": "🚀 Publicar en Fabric", "en": "🚀 Publish to Fabric",
                "pt": "🚀 Publicar no Fabric"},
    "fab_publicando": {"es": "Publicando…", "en": "Publishing…",
                       "pt": "Publicando…"},
    "fab_error": {"es": "Fabric respondió con error",
                  "en": "Fabric returned an error",
                  "pt": "O Fabric respondeu com erro"},
    "fab_mcp_nota": {
        "es": "El MCP remoto oficial de Power BI también trabaja sobre "
              "modelos ya publicados — configuralo desde 🛠️ Herramientas.",
        "en": "Power BI's official remote MCP also works on already published "
              "models — set it up from 🛠️ Tools.",
        "pt": "O MCP remoto oficial do Power BI também funciona sobre modelos "
              "já publicados — configure em 🛠️ Ferramentas.",
    },

    # ---- overlay -------------------------------------------------------
    "ov_titulo": {
        "es": "DAX Overlay: capturá la pantalla, aplicá el resultado acá",
        "en": "DAX Overlay: capture the screen, apply the result here",
        "pt": "DAX Overlay: capture a tela, aplique o resultado aqui",
    },
    "ov_atajo": {"es": "Atajo", "en": "Shortcut", "pt": "Atalho"},
    "ov_que_hace": {"es": "Qué hace", "en": "What it does", "pt": "O que faz"},
    "ov_f9": {
        "es": "Captura **toda la pantalla** y la resuelve con la IA",
        "en": "Captures the **whole screen** and solves it with the AI",
        "pt": "Captura **a tela inteira** e resolve com a IA",
    },
    "ov_shift_f9": {
        "es": "Seleccionás un **rectángulo** con el mouse",
        "en": "You drag a **rectangle** with the mouse",
        "pt": "Você seleciona um **retângulo** com o mouse",
    },
    "ov_ctrl_f9": {
        "es": "Abre una ventana para **escribir la consulta**",
        "en": "Opens a window to **type your request**",
        "pt": "Abre uma janela para **escrever a consulta**",
    },
    "ov_limpiar_mem": {"es": "Limpia la memoria de capturas previas",
                       "en": "Clears the previous-capture memory",
                       "pt": "Limpa a memória de capturas anteriores"},
    "ov_explica": {
        "es": "Cada respuesta se explica **paso a paso** y queda en la "
              "**bandeja** de abajo: si trae medidas o columnas calculadas, "
              "se aplican al modelo cargado con un clic.",
        "en": "Every answer is explained **step by step** and lands in the "
              "**inbox** below: if it carries measures or calculated "
              "columns, they apply to the loaded model in one click.",
        "pt": "Cada resposta é explicada **passo a passo** e fica na "
              "**caixa** abaixo: se trouxer medidas ou colunas calculadas, "
              "elas se aplicam ao modelo carregado com um clique.",
    },
    "ov_escribir": {
        "es": "…o escribí la consulta acá mismo (sin overlay)",
        "en": "…or type your request right here (no overlay)",
        "pt": "…ou escreva a consulta aqui mesmo (sem overlay)",
    },
    "ov_placeholder": {
        "es": "p. ej.: necesito el margen % por categoría con semáforo, "
              "¿qué medidas armo?",
        "en": "e.g.: I need margin % by category with a traffic light, "
              "which measures should I build?",
        "pt": "ex.: preciso da margem % por categoria com semáforo, "
              "quais medidas eu crio?",
    },
    "ov_btn_resolver": {"es": "Resolver con la IA", "en": "Solve with the AI",
                        "pt": "Resolver com a IA"},
    "ov_bandeja": {"es": "📬 Bandeja del overlay", "en": "📬 Overlay inbox",
                   "pt": "📬 Caixa do overlay"},
    "ov_vacia": {
        "es": "Sin resultados todavía. Usá el overlay o la consulta de arriba.",
        "en": "Nothing yet. Use the overlay or the box above.",
        "pt": "Nada ainda. Use o overlay ou a consulta acima.",
    },
    "ov_aplicar": {"es": "➕ Aplicar", "en": "➕ Apply", "pt": "➕ Aplicar"},
    "ov_descartar": {"es": "Descartar", "en": "Discard", "pt": "Descartar"},
    "ov_tabla_destino": {"es": "Tabla destino", "en": "Target table",
                         "pt": "Tabela destino"},
    "ov_limpiar": {"es": "🧹 Limpiar resueltos", "en": "🧹 Clear resolved",
                   "pt": "🧹 Limpar resolvidos"},

    # ---- academia ------------------------------------------------------
    "ac_titulo": {
        "es": "Academia DAX — práctica con verificación instantánea",
        "en": "DAX Academy — practice with instant checking",
        "pt": "Academia DAX — prática com verificação instantânea",
    },
    "ac_nivel": {"es": "Nivel", "en": "Level", "pt": "Nível"},
    "ac_proximo": {"es": "Próximo nivel", "en": "Next level",
                   "pt": "Próximo nível"},
    "ac_faltan": {"es": "faltan", "en": "needs", "pt": "faltam"},
    "ac_maximo": {"es": "¡máximo!", "en": "maxed out!", "pt": "máximo!"},
    "ac_modelo_practica": {
        "es": "📋 El modelo de práctica (común a todos los ejercicios)",
        "en": "📋 The practice model (shared by every exercise)",
        "pt": "📋 O modelo de prática (comum a todos os exercícios)",
    },
    "ac_tu_dax": {"es": "Tu DAX", "en": "Your DAX", "pt": "Seu DAX"},
    "ac_verificar": {"es": "Verificar", "en": "Check", "pt": "Verificar"},
    "ac_pista": {"es": "Pista", "en": "Hint", "pt": "Dica"},
    "ac_sin_pista": {"es": "Sin pista para este.", "en": "No hint for this one.",
                     "pt": "Sem dica para este."},

    # ---- herramientas --------------------------------------------------
    "he_titulo": {
        "es": "El stack del analista Power BI moderno, operativo",
        "en": "The modern Power BI analyst stack, operational",
        "pt": "O stack do analista Power BI moderno, operacional",
    },
    "he_detectada": {"es": "detectada", "en": "detected", "pt": "detectada"},
    "he_no_detectada": {"es": "no detectada acá", "en": "not detected here",
                        "pt": "não detectada aqui"},
    "he_sitio": {"es": "sitio", "en": "site", "pt": "site"},
    "he_para_daxstudio": {"es": "Para DAX Studio", "en": "For DAX Studio",
                          "pt": "Para o DAX Studio"},
    "he_para_tabular": {"es": "Para Tabular Editor / ALM Toolkit",
                        "en": "For Tabular Editor / ALM Toolkit",
                        "pt": "Para Tabular Editor / ALM Toolkit"},
    "he_para_mcp": {"es": "Para agentes de IA (MCP)", "en": "For AI agents (MCP)",
                    "pt": "Para agentes de IA (MCP)"},
    "he_mcp_nota": {
        "es": "Incluye el MCP remoto oficial de Power BI, el MCP local de "
              "modelado y el servidor MCP de esta plataforma.",
        "en": "Includes Power BI's official remote MCP, the local modeling "
              "MCP and this platform's own MCP server.",
        "pt": "Inclui o MCP remoto oficial do Power BI, o MCP local de "
              "modelagem e o servidor MCP desta plataforma.",
    },
    "he_carga_medidas": {"es": "Cargá un modelo con medidas.",
                         "en": "Load a model with measures.",
                         "pt": "Carregue um modelo com medidas."},

    # ---- licencia ------------------------------------------------------
    "lic_titulo": {"es": "Licencia y edición", "en": "License and edition",
                   "pt": "Licença e edição"},
    "lic_edicion": {"es": "Edición", "en": "Edition", "pt": "Edição"},
    "lic_estado": {"es": "Estado", "en": "Status", "pt": "Status"},
    "lic_dias": {"es": "Días restantes", "en": "Days left",
                 "pt": "Dias restantes"},
    "lic_activa": {"es": "activa", "en": "active", "pt": "ativa"},
    "lic_vencida": {"es": "vencida", "en": "expired", "pt": "expirada"},
    "lic_pegar": {"es": "Pegá tu clave de licencia",
                  "en": "Paste your license key",
                  "pt": "Cole sua chave de licença"},
    "lic_activar": {"es": "Activar", "en": "Activate", "pt": "Ativar"},
    "lic_activada": {"es": "Licencia activada.", "en": "License activated.",
                     "pt": "Licença ativada."},
    "lic_invalida": {
        "es": "Clave inválida: revisá que esté completa y sin espacios.",
        "en": "Invalid key: check it is complete and has no spaces.",
        "pt": "Chave inválida: verifique se está completa e sem espaços.",
    },
    "lic_comprar": {"es": "Comprar una licencia", "en": "Buy a license",
                    "pt": "Comprar uma licença"},
    "lic_perpetua": {
        "es": "Licencia perpetua: no vence.",
        "en": "Perpetual license: it does not expire.",
        "pt": "Licença perpétua: não vence.",
    },
    "lic_mensual": {
        "es": "Suscripción mensual. La clave vale 32 días y se renueva sola "
              "mientras la suscripción siga activa: cuando falten pocos días, "
              "entrá al enlace de renovación y pegá la clave nueva.",
        "en": "Monthly subscription. The key lasts 32 days and renews itself "
              "while the subscription stays active: when it is close to "
              "expiring, open the renewal link and paste the new key.",
        "pt": "Assinatura mensal. A chave vale 32 dias e se renova sozinha "
              "enquanto a assinatura seguir ativa: quando faltarem poucos "
              "dias, abra o link de renovação e cole a chave nova.",
    },
    "lic_renovar": {"es": "Renovar la clave", "en": "Renew the key",
                    "pt": "Renovar a chave"},
    "lic_por_vencer": {
        "es": "Tu clave vence pronto. Renovala para no quedarte afuera.",
        "en": "Your key expires soon. Renew it so you are not locked out.",
        "pt": "Sua chave vence em breve. Renove para não ficar de fora.",
    },
    "lic_demo_activa": {
        "es": "Estás en la prueba gratuita de 7 días, con todo desbloqueado.",
        "en": "You are on the free 7-day trial, with everything unlocked.",
        "pt": "Você está no teste gratuito de 7 dias, com tudo liberado.",
    },
    "lic_demo_vencida": {
        "es": "La prueba de 7 días terminó. El analizador, el explicador y la "
              "Academia siguen abiertos; para generar DAX, transformar, "
              "exportar y publicar hace falta una licencia.",
        "en": "The 7-day trial is over. Analyzer, explainer and Academy stay "
              "open; generating DAX, transforming, exporting and publishing "
              "need a license.",
        "pt": "O teste de 7 dias terminou. Analisador, explicador e Academia "
              "seguem abertos; gerar DAX, transformar, exportar e publicar "
              "exigem uma licença.",
    },
    "lic_bloqueado": {
        "es": "Esta función necesita una licencia activa. Miralo en 🔑 Licencia.",
        "en": "This feature needs an active license. See 🔑 License.",
        "pt": "Este recurso precisa de uma licença ativa. Veja 🔑 Licença.",
    },
    "lic_owner": {
        "es": "Edición OWNER: todo desbloqueado, sin vencimiento.",
        "en": "OWNER edition: everything unlocked, no expiry.",
        "pt": "Edição OWNER: tudo liberado, sem vencimento.",
    },

    # ---- configuración -------------------------------------------------
    "cfg_titulo": {"es": "Configuración", "en": "Settings",
                   "pt": "Configuração"},
    "cfg_ia": {"es": "IA — opcional, con tu propia clave (BYOK)",
               "en": "AI — optional, bring your own key (BYOK)",
               "pt": "IA — opcional, com sua própria chave (BYOK)"},
    "cfg_proveedor": {"es": "Proveedor de IA", "en": "AI provider",
                      "pt": "Provedor de IA"},
    "cfg_modelo": {"es": "Modelo", "en": "Model", "pt": "Modelo"},
    "cfg_clave": {
        "es": "API key (solo esta sesión; no se guarda en disco)",
        "en": "API key (this session only; never written to disk)",
        "pt": "API key (apenas esta sessão; não é gravada em disco)",
    },
    "cfg_probar": {"es": "Probar la conexión", "en": "Test the connection",
                   "pt": "Testar a conexão"},
    "cfg_ok": {"es": "Conexión correcta.", "en": "Connection OK.",
               "pt": "Conexão correta."},
    "cfg_nota_ia": {
        "es": "Si el modelo elegido está saturado, se cae solo al siguiente "
              "de la lista, con reintentos. Sin clave, todo lo demás "
              "funciona igual: motor de reglas, analizador, explicador y "
              "export.",
        "en": "If the chosen model is overloaded it falls back to the next "
              "one, with retries. With no key everything else works the "
              "same: rules engine, analyzer, explainer and export.",
        "pt": "Se o modelo escolhido estiver sobrecarregado, cai sozinho para "
              "o próximo, com novas tentativas. Sem chave, todo o resto "
              "funciona igual: motor de regras, analisador, explicador e "
              "exportação.",
    },
    "cfg_mcp": {"es": "Conexión MCP", "en": "MCP connection",
                "pt": "Conexão MCP"},
    "cfg_mcp_nota": {
        "es": "El archivo .mcp.json que se descarga acá sirve para cualquier "
              "agente que hable MCP (Claude, ChatGPT, Copilot, Gemini): les "
              "da acceso al MCP remoto oficial de Power BI, al MCP local de "
              "modelado y al servidor de esta plataforma.",
        "en": "The .mcp.json you download here works for any MCP-speaking "
              "agent (Claude, ChatGPT, Copilot, Gemini): it gives them "
              "Power BI's official remote MCP, the local modeling MCP and "
              "this platform's server.",
        "pt": "O .mcp.json baixado aqui serve para qualquer agente que fale "
              "MCP (Claude, ChatGPT, Copilot, Gemini): dá a eles o MCP "
              "remoto oficial do Power BI, o MCP local de modelagem e o "
              "servidor desta plataforma.",
    },
    "cfg_bandeja": {"es": "Bandeja del overlay", "en": "Overlay inbox",
                    "pt": "Caixa do overlay"},
    "cfg_historial": {"es": "Historial de cambios de la sesión:",
                      "en": "Session change log:",
                      "pt": "Histórico de mudanças da sessão:"},
    # ---- reglas del analizador ----------------------------------------
    # Título, por qué importa y cómo se arregla, de las 16 reglas. Vivían
    # hardcodeadas en español dentro de `analizador.py`, así que la pestaña
    # salía en español aunque la app estuviera en inglés o portugués.
    # {tabla} y {medida} los completa `analizador.describir()`.
    "regla_R00": {
        "es": "Catálogo parcial",
        "en": "Partial catalog",
        "pt": "Catálogo parcial",
    },
    "regla_R00_detalle": {
        "es": "Este catálogo salió del layout de un .pbix: solo se ve lo que los visuales usan, no el modelo completo.",
        "en": "This catalog came from a .pbix layout: you only see what the visuals use, not the whole model.",
        "pt": "Este catálogo veio do layout de um .pbix: só se vê o que os visuais usam, não o modelo completo.",
    },
    "regla_R00_arreglo": {
        "es": "Exportá el archivo como .pbit o PBIP desde Power BI Desktop para el análisis completo.",
        "en": "Export the file as .pbit or PBIP from Power BI Desktop for the full analysis.",
        "pt": "Exporte o arquivo como .pbit ou PBIP no Power BI Desktop para a análise completa.",
    },
    "regla_R01": {
        "es": "División con «/»",
        "en": "Division with “/”",
        "pt": "Divisão com «/»",
    },
    "regla_R01_detalle": {
        "es": "Una división con «/» revienta con dividendo 0 o BLANK y muestra infinito o error en el visual.",
        "en": "A “/” division blows up with a 0 or BLANK divisor and shows infinity or an error in the visual.",
        "pt": "Uma divisão com «/» quebra com divisor 0 ou BLANK e mostra infinito ou erro no visual.",
    },
    "regla_R01_arreglo": {
        "es": "Usar DIVIDE(numerador, denominador): devuelve BLANK ante cero, sin costo extra.",
        "en": "Use DIVIDE(numerator, denominator): it returns BLANK on zero, at no extra cost.",
        "pt": "Use DIVIDE(numerador, denominador): devolve BLANK diante de zero, sem custo extra.",
    },
    "regla_R02": {
        "es": "Medida sin formato",
        "en": "Measure with no format",
        "pt": "Medida sem formato",
    },
    "regla_R02_detalle": {
        "es": "Sin formatString, cada visual muestra el número como quiere: decimales de más, sin separador de miles, porcentajes crudos.",
        "en": "Without formatString, every visual renders the number its own way: stray decimals, no thousands separator, raw percentages.",
        "pt": "Sem formatString, cada visual mostra o número como quer: decimais a mais, sem separador de milhares, percentuais crus.",
    },
    "regla_R02_arreglo": {
        "es": "Asignar un formato explícito (#,0 · #,0.00 · 0.0 %).",
        "en": "Set an explicit format (#,0 · #,0.00 · 0.0 %).",
        "pt": "Atribuir um formato explícito (#,0 · #,0.00 · 0.0 %).",
    },
    "regla_R03": {
        "es": "IFERROR en medida",
        "en": "IFERROR in a measure",
        "pt": "IFERROR na medida",
    },
    "regla_R03_detalle": {
        "es": "IFERROR fuerza al motor a evaluar fila por fila esperando el error: caro y esconde problemas de datos.",
        "en": "IFERROR forces the engine to evaluate row by row waiting for the error: expensive, and it hides data problems.",
        "pt": "IFERROR força o motor a avaliar linha a linha esperando o erro: caro e esconde problemas de dados.",
    },
    "regla_R03_arreglo": {
        "es": "Prevenir el error (DIVIDE, buscar el caso borde) en vez de taparlo.",
        "en": "Prevent the error (DIVIDE, handle the edge case) instead of masking it.",
        "pt": "Prevenir o erro (DIVIDE, tratar o caso limite) em vez de tapá-lo.",
    },
    "regla_R04": {
        "es": "FILTER sobre tabla entera",
        "en": "FILTER over a whole table",
        "pt": "FILTER sobre tabela inteira",
    },
    "regla_R04_detalle": {
        "es": "FILTER('{tabla}', …) materializa la tabla completa dentro de CALCULATE cuando un filtro de columna alcanza.",
        "en": "FILTER('{tabla}', …) materialises the entire table inside CALCULATE when a column filter would do.",
        "pt": "FILTER('{tabla}', …) materializa a tabela inteira dentro de CALCULATE quando um filtro de coluna bastaria.",
    },
    "regla_R04_arreglo": {
        "es": "Filtrar la columna (Tabla[Col] = valor) o usar KEEPFILTERS(VALUES(Tabla[Col])).",
        "en": "Filter the column (Table[Col] = value) or use KEEPFILTERS(VALUES(Table[Col])).",
        "pt": "Filtrar a coluna (Tabela[Col] = valor) ou usar KEEPFILTERS(VALUES(Tabela[Col])).",
    },
    "regla_R05": {
        "es": "Medida duplicada",
        "en": "Duplicate measure",
        "pt": "Medida duplicada",
    },
    "regla_R05_detalle": {
        "es": "Tiene exactamente la misma expresión que [{medida}].",
        "en": "It has exactly the same expression as [{medida}].",
        "pt": "Tem exatamente a mesma expressão que [{medida}].",
    },
    "regla_R05_arreglo": {
        "es": "Dejar una sola y referenciarla desde la otra si hace falta el alias.",
        "en": "Keep one and reference it from the other if you need the alias.",
        "pt": "Deixar uma só e referenciá-la a partir da outra se precisar do alias.",
    },
    "regla_R06": {
        "es": "Espacios en el nombre",
        "en": "Spaces in the name",
        "pt": "Espaços no nome",
    },
    "regla_R06_detalle": {
        "es": "El nombre empieza o termina con espacios: invisible en el panel y fuente de referencias rotas.",
        "en": "The name starts or ends with spaces: invisible in the field pane and a source of broken references.",
        "pt": "O nome começa ou termina com espaços: invisível no painel e fonte de referências quebradas.",
    },
    "regla_R06_arreglo": {
        "es": "Renombrar sin espacios en los bordes.",
        "en": "Rename it without leading or trailing spaces.",
        "pt": "Renomear sem espaços nas bordas.",
    },
    "regla_R07": {
        "es": "Columna calculada",
        "en": "Calculated column",
        "pt": "Coluna calculada",
    },
    "regla_R07_detalle": {
        "es": "Las columnas calculadas se materializan en el modelo y no se comprimen tan bien como las nativas; casi siempre hay una versión en Power Query o una medida.",
        "en": "Calculated columns are materialised in the model and compress worse than native ones; there is almost always a Power Query version or a measure.",
        "pt": "As colunas calculadas são materializadas no modelo e comprimem pior que as nativas; quase sempre há uma versão no Power Query ou uma medida.",
    },
    "regla_R07_arreglo": {
        "es": "Mover el cálculo a Power Query (mejor compresión) o convertirlo en medida si es agregable.",
        "en": "Move the calculation to Power Query (better compression) or turn it into a measure if it aggregates.",
        "pt": "Mover o cálculo para o Power Query (melhor compressão) ou convertê-lo em medida se for agregável.",
    },
    "regla_R08": {
        "es": "Clave foránea visible",
        "en": "Visible foreign key",
        "pt": "Chave estrangeira visível",
    },
    "regla_R08_detalle": {
        "es": "Las columnas que solo existen para relacionar tablas confunden en el panel de campos y tientan a sumarlas.",
        "en": "Columns that exist only to relate tables clutter the field pane and tempt people to sum them.",
        "pt": "As colunas que só existem para relacionar tabelas confundem no painel de campos e tentam a somá-las.",
    },
    "regla_R08_arreglo": {
        "es": "Ocultarla (isHidden). El filtro sigue funcionando igual.",
        "en": "Hide it (isHidden). The relationship keeps working exactly the same.",
        "pt": "Ocultá-la (isHidden). O filtro continua funcionando igual.",
    },
    "regla_R09": {
        "es": "Relación bidireccional",
        "en": "Bidirectional relationship",
        "pt": "Relação bidirecional",
    },
    "regla_R09_detalle": {
        "es": "El filtro cruzado en ambas direcciones genera ambigüedad de caminos y resultados que cambian según el visual.",
        "en": "Cross-filtering in both directions creates ambiguous paths and results that change from one visual to another.",
        "pt": "O filtro cruzado nas duas direções gera ambiguidade de caminhos e resultados que mudam conforme o visual.",
    },
    "regla_R09_arreglo": {
        "es": "Volver a dirección simple y resolver el caso puntual con CROSSFILTER dentro de la medida que lo necesite.",
        "en": "Go back to single direction and solve the specific case with CROSSFILTER inside the measure that needs it.",
        "pt": "Voltar à direção simples e resolver o caso pontual com CROSSFILTER dentro da medida que precisar.",
    },
    "regla_R10": {
        "es": "Relación muchos a muchos",
        "en": "Many-to-many relationship",
        "pt": "Relação muitos para muitos",
    },
    "regla_R10_detalle": {
        "es": "Las relaciones N:N ocultan duplicados en las claves y degradan el rendimiento del motor.",
        "en": "N:N relationships hide duplicate keys and degrade engine performance.",
        "pt": "As relações N:N escondem duplicados nas chaves e degradam o desempenho do motor.",
    },
    "regla_R10_arreglo": {
        "es": "Interponer una tabla puente con la clave única (esquema estrella).",
        "en": "Put a bridge table with the unique key in between (star schema).",
        "pt": "Interpor uma tabela ponte com a chave única (esquema estrela).",
    },
    "regla_R11": {
        "es": "Relación inactiva",
        "en": "Inactive relationship",
        "pt": "Relação inativa",
    },
    "regla_R11_detalle": {
        "es": "Está definida pero apagada: solo actúa vía USERELATIONSHIP.",
        "en": "It is defined but switched off: it only applies through USERELATIONSHIP.",
        "pt": "Está definida mas desligada: só atua via USERELATIONSHIP.",
    },
    "regla_R11_arreglo": {
        "es": "Confirmar que alguna medida la usa; si no, eliminarla.",
        "en": "Confirm some measure uses it; if not, delete it.",
        "pt": "Confirmar que alguma medida a usa; se não, eliminá-la.",
    },
    "regla_R12": {
        "es": "Tabla sin relaciones",
        "en": "Table with no relationships",
        "pt": "Tabela sem relações",
    },
    "regla_R12_detalle": {
        "es": "No participa de ninguna relación: sus filtros no viajan a ninguna otra tabla.",
        "en": "It takes part in no relationship: its filters never reach any other table.",
        "pt": "Não participa de nenhuma relação: seus filtros não chegam a nenhuma outra tabela.",
    },
    "regla_R12_arreglo": {
        "es": "Relacionarla al modelo o, si es tabla auxiliar, ocultarla.",
        "en": "Relate it to the model or, if it is a helper table, hide it.",
        "pt": "Relacioná-la ao modelo ou, se for tabela auxiliar, ocultá-la.",
    },
    "regla_R13": {
        "es": "Auto date/time activo",
        "en": "Auto date/time on",
        "pt": "Auto date/time ativo",
    },
    "regla_R13_detalle": {
        "es": "Power BI creó tablas de calendario ocultas por cada columna de fecha (LocalDateTable_*): infla el modelo y duplica lógica.",
        "en": "Power BI created a hidden date table for every date column (LocalDateTable_*): it bloats the model and duplicates logic.",
        "pt": "O Power BI criou tabelas de calendário ocultas para cada coluna de data (LocalDateTable_*): infla o modelo e duplica lógica.",
    },
    "regla_R13_arreglo": {
        "es": "Desactivar Auto date/time y usar una única tabla de calendario marcada como tabla de fechas.",
        "en": "Turn Auto date/time off and use a single date table marked as such.",
        "pt": "Desativar o Auto date/time e usar uma única tabela de calendário marcada como tabela de datas.",
    },
    "regla_R14": {
        "es": "Sin tabla de calendario",
        "en": "No date table",
        "pt": "Sem tabela de calendário",
    },
    "regla_R14_detalle": {
        "es": "Hay columnas de fecha pero ninguna tabla de calendario marcada: la inteligencia de tiempo (YTD, año anterior) puede devolver resultados incorrectos sin avisar.",
        "en": "There are date columns but no marked date table: time intelligence (YTD, previous year) can return wrong results with no warning.",
        "pt": "Há colunas de data mas nenhuma tabela de calendário marcada: a inteligência de tempo (YTD, ano anterior) pode devolver resultados incorretos sem avisar.",
    },
    "regla_R14_arreglo": {
        "es": "Crear una tabla de calendario continua y marcarla como tabla de fechas.",
        "en": "Create a continuous date table and mark it as the date table.",
        "pt": "Criar uma tabela de calendário contínua e marcá-la como tabela de datas.",
    },
    "regla_R15": {
        "es": "Medidas dispersas",
        "en": "Scattered measures",
        "pt": "Medidas dispersas",
    },
    "regla_R15_detalle": {
        "es": "Las medidas viven repartidas en tablas de datos; el panel de campos mezcla modelo y cálculos.",
        "en": "Measures live spread across data tables; the field pane mixes model and calculations.",
        "pt": "As medidas vivem espalhadas por tabelas de dados; o painel de campos mistura modelo e cálculos.",
    },
    "regla_R15_arreglo": {
        "es": "Concentrarlas en una tabla de medidas dedicada.",
        "en": "Concentrate them in a dedicated measures table.",
        "pt": "Concentrá-las numa tabela de medidas dedicada.",
    },
    # ---- explicador: base de conocimiento DAX y prosa -----------------
    # Las 62 descripciones de función, las categorías y las frases del
    # explicador. Estaban en español dentro de `explicador.py`, así que la
    # pestaña Explicador contestaba en español con la app en otro idioma.
    "fn_SUM": {
        "es": "suma los valores de una columna",
        "en": "sums the values of a column",
        "pt": "soma os valores de uma coluna",
    },
    "fn_SUMX": {
        "es": "recorre la tabla fila por fila, evalúa la expresión y suma los resultados",
        "en": "walks the table row by row, evaluates the expression and sums the results",
        "pt": "percorre a tabela linha a linha, avalia a expressão e soma os resultados",
    },
    "fn_AVERAGE": {
        "es": "promedia los valores de una columna",
        "en": "averages the values of a column",
        "pt": "faz a média dos valores de uma coluna",
    },
    "fn_AVERAGEX": {
        "es": "recorre la tabla fila por fila y promedia la expresión evaluada",
        "en": "walks the table row by row and averages the evaluated expression",
        "pt": "percorre a tabela linha a linha e faz a média da expressão avaliada",
    },
    "fn_MIN": {
        "es": "devuelve el mínimo de una columna",
        "en": "returns the minimum of a column",
        "pt": "devolve o mínimo de uma coluna",
    },
    "fn_MAX": {
        "es": "devuelve el máximo de una columna",
        "en": "returns the maximum of a column",
        "pt": "devolve o máximo de uma coluna",
    },
    "fn_MINX": {
        "es": "mínimo de una expresión evaluada fila por fila",
        "en": "minimum of an expression evaluated row by row",
        "pt": "mínimo de uma expressão avaliada linha a linha",
    },
    "fn_MAXX": {
        "es": "máximo de una expresión evaluada fila por fila",
        "en": "maximum of an expression evaluated row by row",
        "pt": "máximo de uma expressão avaliada linha a linha",
    },
    "fn_COUNT": {
        "es": "cuenta los valores no vacíos de una columna",
        "en": "counts the non-blank values of a column",
        "pt": "conta os valores não vazios de uma coluna",
    },
    "fn_COUNTROWS": {
        "es": "cuenta las filas de una tabla",
        "en": "counts the rows of a table",
        "pt": "conta as linhas de uma tabela",
    },
    "fn_COUNTX": {
        "es": "cuenta evaluando una expresión fila por fila",
        "en": "counts by evaluating an expression row by row",
        "pt": "conta avaliando uma expressão linha a linha",
    },
    "fn_DISTINCTCOUNT": {
        "es": "cuenta los valores distintos de una columna",
        "en": "counts the distinct values of a column",
        "pt": "conta os valores distintos de uma coluna",
    },
    "fn_CALCULATE": {
        "es": "evalúa la expresión CAMBIANDO el contexto de filtro con los filtros que se le pasan",
        "en": "evaluates the expression CHANGING the filter context with the filters it receives",
        "pt": "avalia a expressão MUDANDO o contexto de filtro com os filtros que recebe",
    },
    "fn_CALCULATETABLE": {
        "es": "como CALCULATE pero devuelve una tabla",
        "en": "like CALCULATE but returns a table",
        "pt": "como CALCULATE mas devolve uma tabela",
    },
    "fn_FILTER": {
        "es": "devuelve las filas de la tabla que cumplen la condición",
        "en": "returns the rows of the table that meet the condition",
        "pt": "devolve as linhas da tabela que cumprem a condição",
    },
    "fn_ALL": {
        "es": "quita los filtros de la tabla o columna indicada",
        "en": "removes the filters from the given table or column",
        "pt": "remove os filtros da tabela ou coluna indicada",
    },
    "fn_ALLEXCEPT": {
        "es": "quita todos los filtros salvo los de las columnas indicadas",
        "en": "removes every filter except those on the given columns",
        "pt": "remove todos os filtros exceto os das colunas indicadas",
    },
    "fn_ALLSELECTED": {
        "es": "quita los filtros internos del visual pero respeta los slicers",
        "en": "removes the visual's inner filters but respects the slicers",
        "pt": "remove os filtros internos do visual mas respeita os slicers",
    },
    "fn_REMOVEFILTERS": {
        "es": "quita filtros — versión moderna y legible de ALL",
        "en": "removes filters — the modern, readable version of ALL",
        "pt": "remove filtros — versão moderna e legível de ALL",
    },
    "fn_KEEPFILTERS": {
        "es": "agrega el filtro sin pisar los existentes (intersección)",
        "en": "adds the filter without overwriting the existing ones (intersection)",
        "pt": "adiciona o filtro sem sobrepor os existentes (interseção)",
    },
    "fn_VALUES": {
        "es": "devuelve los valores visibles (distintos) de una columna en el contexto actual",
        "en": "returns the visible (distinct) values of a column in the current context",
        "pt": "devolve os valores visíveis (distintos) de uma coluna no contexto atual",
    },
    "fn_DISTINCT": {
        "es": "devuelve los valores distintos de una columna",
        "en": "returns the distinct values of a column",
        "pt": "devolve os valores distintos de uma coluna",
    },
    "fn_SELECTEDVALUE": {
        "es": "devuelve el valor si hay UNO solo visible; si no, el alternativo",
        "en": "returns the value if exactly ONE is visible; otherwise the fallback",
        "pt": "devolve o valor se houver apenas UM visível; caso contrário, o alternativo",
    },
    "fn_HASONEVALUE": {
        "es": "verdadero si la columna tiene un único valor visible",
        "en": "true if the column has a single visible value",
        "pt": "verdadeiro se a coluna tem um único valor visível",
    },
    "fn_ISFILTERED": {
        "es": "verdadero si la columna está siendo filtrada",
        "en": "true if the column is being filtered",
        "pt": "verdadeiro se a coluna está sendo filtrada",
    },
    "fn_DIVIDE": {
        "es": "divide de forma segura: ante denominador 0 o BLANK devuelve BLANK (o el alternativo)",
        "en": "divides safely: on a 0 or BLANK divisor it returns BLANK (or the fallback)",
        "pt": "divide de forma segura: com divisor 0 ou BLANK devolve BLANK (ou o alternativo)",
    },
    "fn_IF": {
        "es": "evalúa una condición y devuelve una de dos ramas",
        "en": "evaluates a condition and returns one of two branches",
        "pt": "avalia uma condição e devolve um de dois ramos",
    },
    "fn_SWITCH": {
        "es": "compara contra varios casos y devuelve la rama que coincide",
        "en": "compares against several cases and returns the matching branch",
        "pt": "compara com vários casos e devolve o ramo que coincide",
    },
    "fn_AND": {
        "es": "verdadero si ambas condiciones lo son",
        "en": "true if both conditions are true",
        "pt": "verdadeiro se ambas as condições o forem",
    },
    "fn_OR": {
        "es": "verdadero si alguna condición lo es",
        "en": "true if either condition is true",
        "pt": "verdadeiro se alguma condição o for",
    },
    "fn_NOT": {
        "es": "invierte la condición",
        "en": "inverts the condition",
        "pt": "inverte a condição",
    },
    "fn_COALESCE": {
        "es": "devuelve el primer valor no BLANK de la lista",
        "en": "returns the first non-BLANK value in the list",
        "pt": "devolve o primeiro valor não BLANK da lista",
    },
    "fn_ISBLANK": {
        "es": "verdadero si el valor es BLANK",
        "en": "true if the value is BLANK",
        "pt": "verdadeiro se o valor é BLANK",
    },
    "fn_BLANK": {
        "es": "devuelve el valor vacío BLANK",
        "en": "returns the empty BLANK value",
        "pt": "devolve o valor vazio BLANK",
    },
    "fn_TOTALYTD": {
        "es": "acumula la expresión desde el inicio del año hasta la fecha del contexto",
        "en": "accumulates the expression from the start of the year to the context date",
        "pt": "acumula a expressão desde o início do ano até a data do contexto",
    },
    "fn_TOTALQTD": {
        "es": "acumula desde el inicio del trimestre",
        "en": "accumulates from the start of the quarter",
        "pt": "acumula desde o início do trimestre",
    },
    "fn_TOTALMTD": {
        "es": "acumula desde el inicio del mes",
        "en": "accumulates from the start of the month",
        "pt": "acumula desde o início do mês",
    },
    "fn_SAMEPERIODLASTYEAR": {
        "es": "desplaza las fechas del contexto un año hacia atrás",
        "en": "shifts the context dates one year back",
        "pt": "desloca as datas do contexto um ano para trás",
    },
    "fn_DATEADD": {
        "es": "desplaza las fechas del contexto el intervalo indicado",
        "en": "shifts the context dates by the given interval",
        "pt": "desloca as datas do contexto pelo intervalo indicado",
    },
    "fn_DATESINPERIOD": {
        "es": "devuelve las fechas de un período móvil que termina en la fecha dada",
        "en": "returns the dates of a rolling period ending on the given date",
        "pt": "devolve as datas de um período móvel que termina na data dada",
    },
    "fn_DATESYTD": {
        "es": "las fechas desde el inicio del año hasta la actual",
        "en": "the dates from the start of the year to the current one",
        "pt": "as datas desde o início do ano até a atual",
    },
    "fn_PREVIOUSMONTH": {
        "es": "las fechas del mes anterior completo",
        "en": "the dates of the whole previous month",
        "pt": "as datas do mês anterior completo",
    },
    "fn_LASTDATE": {
        "es": "la última fecha visible en el contexto",
        "en": "the last date visible in the context",
        "pt": "a última data visível no contexto",
    },
    "fn_FIRSTDATE": {
        "es": "la primera fecha visible en el contexto",
        "en": "the first date visible in the context",
        "pt": "a primeira data visível no contexto",
    },
    "fn_EOMONTH": {
        "es": "el fin de mes de una fecha, con corrimiento opcional",
        "en": "the end of month of a date, with an optional offset",
        "pt": "o fim de mês de uma data, com deslocamento opcional",
    },
    "fn_TODAY": {
        "es": "la fecha de hoy",
        "en": "today's date",
        "pt": "a data de hoje",
    },
    "fn_RANKX": {
        "es": "posición de cada elemento al ordenar la tabla por la expresión",
        "en": "the position of each item when sorting the table by the expression",
        "pt": "posição de cada elemento ao ordenar a tabela pela expressão",
    },
    "fn_TOPN": {
        "es": "las N filas con mayor valor de la expresión",
        "en": "the N rows with the highest value of the expression",
        "pt": "as N linhas com maior valor da expressão",
    },
    "fn_RELATED": {
        "es": "trae el valor desde el lado «uno» de la relación",
        "en": "brings the value from the “one” side of the relationship",
        "pt": "traz o valor do lado «um» da relação",
    },
    "fn_RELATEDTABLE": {
        "es": "las filas relacionadas desde el lado «muchos»",
        "en": "the related rows from the “many” side",
        "pt": "as linhas relacionadas do lado «muitos»",
    },
    "fn_USERELATIONSHIP": {
        "es": "activa una relación inactiva solo dentro de este cálculo",
        "en": "activates an inactive relationship only inside this calculation",
        "pt": "ativa uma relação inativa apenas dentro deste cálculo",
    },
    "fn_CROSSFILTER": {
        "es": "cambia la dirección del filtro de una relación solo en este cálculo",
        "en": "changes a relationship's filter direction only in this calculation",
        "pt": "muda a direção do filtro de uma relação apenas neste cálculo",
    },
    "fn_TREATAS": {
        "es": "aplica los valores de una tabla como filtro sobre otras columnas",
        "en": "applies a table's values as a filter over other columns",
        "pt": "aplica os valores de uma tabela como filtro sobre outras colunas",
    },
    "fn_LOOKUPVALUE": {
        "es": "busca un valor en otra tabla por igualdad de claves",
        "en": "looks a value up in another table by matching keys",
        "pt": "busca um valor em outra tabela por igualdade de chaves",
    },
    "fn_SUMMARIZE": {
        "es": "agrupa una tabla por columnas",
        "en": "groups a table by columns",
        "pt": "agrupa uma tabela por colunas",
    },
    "fn_ADDCOLUMNS": {
        "es": "agrega columnas calculadas a una tabla en memoria",
        "en": "adds calculated columns to an in-memory table",
        "pt": "adiciona colunas calculadas a uma tabela em memória",
    },
    "fn_SELECTCOLUMNS": {
        "es": "proyecta columnas de una tabla",
        "en": "projects columns from a table",
        "pt": "projeta colunas de uma tabela",
    },
    "fn_UNION": {
        "es": "apila dos tablas",
        "en": "stacks two tables",
        "pt": "empilha duas tabelas",
    },
    "fn_CONCATENATEX": {
        "es": "concatena textos evaluados fila por fila",
        "en": "concatenates texts evaluated row by row",
        "pt": "concatena textos avaliados linha a linha",
    },
    "fn_FORMAT": {
        "es": "convierte un valor a texto con formato",
        "en": "converts a value to formatted text",
        "pt": "converte um valor em texto com formato",
    },
    "fn_VAR": {
        "es": "define una variable: se evalúa una vez y se reutiliza",
        "en": "declares a variable: evaluated once and reused",
        "pt": "define uma variável: é avaliada uma vez e reutilizada",
    },
    "fn_RETURN": {
        "es": "devuelve el resultado final usando las variables definidas",
        "en": "returns the final result using the declared variables",
        "pt": "devolve o resultado final usando as variáveis definidas",
    },
    "catfn_agregacion": {
        "es": "agregación",
        "en": "aggregation",
        "pt": "agregação",
    },
    "catfn_iterador": {
        "es": "iterador",
        "en": "iterator",
        "pt": "iterador",
    },
    "catfn_contexto": {
        "es": "contexto",
        "en": "context",
        "pt": "contexto",
    },
    "catfn_tabla": {
        "es": "tabla",
        "en": "table",
        "pt": "tabela",
    },
    "catfn_matematica": {
        "es": "matemática",
        "en": "maths",
        "pt": "matemática",
    },
    "catfn_logica": {
        "es": "lógica",
        "en": "logic",
        "pt": "lógica",
    },
    "catfn_tiempo": {
        "es": "tiempo",
        "en": "time intelligence",
        "pt": "tempo",
    },
    "catfn_ranking": {
        "es": "ranking",
        "en": "ranking",
        "pt": "ranking",
    },
    "catfn_relacion": {
        "es": "relación",
        "en": "relationship",
        "pt": "relação",
    },
    "catfn_texto": {
        "es": "texto",
        "en": "text",
        "pt": "texto",
    },
    "catfn_estructura": {
        "es": "estructura",
        "en": "structure",
        "pt": "estrutura",
    },
    "catfn_otra": {
        "es": "otra",
        "en": "other",
        "pt": "outra",
    },
    "exp_vacia": {
        "es": "Expresión vacía.",
        "en": "Empty expression.",
        "pt": "Expressão vazia.",
    },
    "exp_fn_desconocida": {
        "es": "función DAX",
        "en": "DAX function",
        "pt": "função DAX",
    },
    "exp_quien_medida": {
        "es": "La medida [{nombre}]",
        "en": "Measure [{nombre}]",
        "pt": "A medida [{nombre}]",
    },
    "exp_quien_expresion": {
        "es": "La expresión",
        "en": "The expression",
        "pt": "A expressão",
    },
    "exp_res_tiempo": {
        "es": "{quien} calcula un valor con inteligencia de tiempo: desplaza o acumula el período del contexto antes de agregar.",
        "en": "{quien} computes a value with time intelligence: it shifts or accumulates the context period before aggregating.",
        "pt": "{quien} calcula um valor com inteligência de tempo: desloca ou acumula o período do contexto antes de agregar.",
    },
    "exp_res_ytd": {
        "es": "{quien} acumula el valor desde el inicio del año.",
        "en": "{quien} accumulates the value from the start of the year.",
        "pt": "{quien} acumula o valor desde o início do ano.",
    },
    "exp_res_rank": {
        "es": "{quien} calcula una posición en un ranking.",
        "en": "{quien} computes a position in a ranking.",
        "pt": "{quien} calcula uma posição num ranking.",
    },
    "exp_res_divide": {
        "es": "{quien} calcula un cociente con división segura.",
        "en": "{quien} computes a ratio with safe division.",
        "pt": "{quien} calcula um quociente com divisão segura.",
    },
    "exp_res_calculate": {
        "es": "{quien} agrega un valor modificando antes el contexto de filtro (eso es CALCULATE: cambia sobre qué filas se calcula).",
        "en": "{quien} aggregates a value after modifying the filter context (that is what CALCULATE does: it changes which rows are used).",
        "pt": "{quien} agrega um valor modificando antes o contexto de filtro (isso é CALCULATE: muda sobre quais linhas se calcula).",
    },
    "exp_res_base": {
        "es": "{quien} {base}{sobre}.",
        "en": "{quien} {base}{sobre}.",
        "pt": "{quien} {base}{sobre}.",
    },
    "exp_res_simple": {
        "es": "{quien} evalúa una expresión aritmética simple.",
        "en": "{quien} evaluates a simple arithmetic expression.",
        "pt": "{quien} avalia uma expressão aritmética simples.",
    },
    "exp_sobre": {
        "es": " sobre {col}",
        "en": " over {col}",
        "pt": " sobre {col}",
    },
    "exp_paso_var": {
        "es": "Define {n} variable(s) ({lista}{mas}): cada una se evalúa una sola vez y congela su valor — más rápido y más legible.",
        "en": "Declares {n} variable(s) ({lista}{mas}): each is evaluated once and freezes its value — faster and easier to read.",
        "pt": "Define {n} variável(is) ({lista}{mas}): cada uma é avaliada uma só vez e congela seu valor — mais rápido e mais legível.",
    },
    "exp_paso_calculate": {
        "es": "CALCULATE cambia el contexto de filtro: los filtros que recibe reemplazan (o intersecan, con KEEPFILTERS) a los del visual antes de evaluar la expresión.",
        "en": "CALCULATE changes the filter context: the filters it receives replace (or intersect, with KEEPFILTERS) the visual's own before the expression is evaluated.",
        "pt": "CALCULATE muda o contexto de filtro: os filtros que recebe substituem (ou intersectam, com KEEPFILTERS) os do visual antes de avaliar a expressão.",
    },
    "exp_paso_iterador": {
        "es": "{lista} recorre(n) la tabla fila por fila: el costo crece con la cantidad de filas visibles.",
        "en": "{lista} walk(s) the table row by row: the cost grows with the number of visible rows.",
        "pt": "{lista} percorre(m) a tabela linha a linha: o custo cresce com a quantidade de linhas visíveis.",
    },
    "exp_paso_tiempo": {
        "es": "Inteligencia de tiempo ({lista}): necesita una tabla de calendario continua y marcada como tabla de fechas para dar resultados correctos.",
        "en": "Time intelligence ({lista}): it needs a continuous date table, marked as such, to return correct results.",
        "pt": "Inteligência de tempo ({lista}): precisa de uma tabela de calendário contínua e marcada como tabela de datas para dar resultados corretos.",
    },
    "exp_paso_medidas": {
        "es": "Reutiliza medidas existentes ({lista}): el cambio en la medida base se propaga solo.",
        "en": "Reuses existing measures ({lista}): a change in the base measure propagates on its own.",
        "pt": "Reutiliza medidas existentes ({lista}): a mudança na medida base se propaga sozinha.",
    },
    "exp_paso_directo": {
        "es": "Agregación directa sobre el contexto del visual, sin modificar filtros.",
        "en": "Direct aggregation over the visual's context, with no filter changes.",
        "pt": "Agregação direta sobre o contexto do visual, sem modificar filtros.",
    },
    "nivel_basico": {
        "es": "básico",
        "en": "basic",
        "pt": "básico",
    },
    "nivel_intermedio": {
        "es": "intermedio",
        "en": "intermediate",
        "pt": "intermediário",
    },
    "nivel_avanzado": {
        "es": "avanzado",
        "en": "advanced",
        "pt": "avançado",
    },
    # ---- transformador, generador y nombre de la edición ---------------
    # Último resto de texto de usuario que vivía hardcodeado en español.
    "tr_divide": {
        "es": "[{obj}]: {n} división(es) «/» → DIVIDE",
        "en": "[{obj}]: {n} “/” division(s) → DIVIDE",
        "pt": "[{obj}]: {n} divisão(ões) «/» → DIVIDE",
    },
    "tr_formato": {
        "es": "[{obj}]: formato → {formato}",
        "en": "[{obj}]: format → {formato}",
        "pt": "[{obj}]: formato → {formato}",
    },
    "tr_oculta_clave": {
        "es": "{obj}: oculta (clave de relación)",
        "en": "{obj}: hidden (relationship key)",
        "pt": "{obj}: oculta (chave de relação)",
    },
    "tr_tabla_medidas": {
        "es": "Tabla de medidas «{nombre}» creada",
        "en": "Measures table “{nombre}” created",
        "pt": "Tabela de medidas «{nombre}» criada",
    },
    "tr_movidas": {
        "es": "{n} medida(s) movida(s) desde {origen}",
        "en": "{n} measure(s) moved from {origen}",
        "pt": "{n} medida(s) movida(s) de {origen}",
    },
    "tr_renombrada": {
        "es": "[{antes}] → [{despues}]",
        "en": "[{antes}] → [{despues}]",
        "pt": "[{antes}] → [{despues}]",
    },
    "tr_referencias": {
        "es": "[{obj}]: {n} referencia(s) actualizada(s)",
        "en": "[{obj}]: {n} reference(s) updated",
        "pt": "[{obj}]: {n} referência(s) atualizada(s)",
    },
    "tr_sin_tablas": {
        "es": "El modelo no tiene tablas.",
        "en": "The model has no tables.",
        "pt": "O modelo não tem tabelas.",
    },
    "gen_vacio": {
        "es": "Escribí qué medida querés: p. ej. «total de ventas», «ventas vs año anterior».",
        "en": "Type the measure you want: e.g. “total sales”, “sales vs last year”.",
        "pt": "Escreva a medida que quer: p. ex. «total de vendas», «vendas vs ano anterior».",
    },
    "gen_sin_modelo": {
        "es": "Primero cargá un modelo: el generador solo escribe DAX validado contra tu catálogo.",
        "en": "Load a model first: the generator only writes DAX validated against your catalog.",
        "pt": "Carregue um modelo primeiro: o gerador só escreve DAX validado contra o seu catálogo.",
    },
    "gen_sin_patron": {
        "es": "El motor de reglas no reconoció el patrón y la IA falló: {motivo}",
        "en": "The rule engine did not recognise the pattern and the AI failed: {motivo}",
        "pt": "O motor de regras não reconheceu o padrão e a IA falhou: {motivo}",
    },
    "edicion_owner": {
        "es": "owner",
        "en": "owner",
        "pt": "owner",
    },
    "edicion_profesional": {
        "es": "profesional",
        "en": "professional",
        "pt": "profissional",
    },
    "edicion_demo": {
        "es": "demo",
        "en": "demo",
        "pt": "demo",
    },
    "gen_sin_reconocer": {
        "es": "No reconocí el patrón del pedido. Probá con: total / promedio / máximo / mínimo / conteo distinto de <columna>, «% del total por <dimensión>», «<columna> acumulado del año», «<columna> vs año anterior», «media móvil 3 meses de <columna>», «ranking de <dimensión> por <columna>». Con una clave de IA configurada, el pedido libre también funciona.",
        "en": "I did not recognise the request pattern. Try: total / average / max / min / distinct count of <column>, “% of total by <dimension>”, “<column> year to date”, “<column> vs last year”, “3-month moving average of <column>”, “rank <dimension> by <column>”. With an AI key configured, free-form requests work too.",
        "pt": "Não reconheci o padrão do pedido. Tente: total / média / máximo / mínimo / contagem distinta de <coluna>, «% do total por <dimensão>», «<coluna> acumulado do ano», «<coluna> vs ano anterior», «média móvel 3 meses de <coluna>», «ranking de <dimensão> por <coluna>». Com uma chave de IA configurada, o pedido livre também funciona.",
    },
}


def t(clave: str, idioma: str = IDIOMA_DEFECTO) -> str:
    """Devuelve el texto en el idioma pedido; cae a español si falta."""
    entrada = T.get(clave)
    if entrada is None:
        return clave
    return entrada.get(idioma) or entrada.get(IDIOMA_DEFECTO, clave)


def faltantes() -> dict[str, list[str]]:
    """Claves a las que les falta algún idioma. Vacío = paridad completa."""
    fallas = {}
    for clave, valores in T.items():
        sin = [i for i in IDIOMAS if not valores.get(i)]
        if sin:
            fallas[clave] = sin
    return fallas
