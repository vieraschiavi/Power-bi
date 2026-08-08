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
        "es": "La demo carga el modelo Adium de este mismo repo (117 medidas "
              "reales) desde **📥 Modelo**, sin subir nada.",
        "en": "The demo loads the Adium model from this very repo (117 real "
              "measures) from **📥 Model**, with nothing to upload.",
        "pt": "A demo carrega o modelo Adium deste mesmo repo (117 medidas "
              "reais) em **📥 Modelo**, sem enviar nada.",
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
    "modelo_demo": {"es": "Modelo demo (Adium · 117 medidas)",
                    "en": "Demo model (Adium · 117 measures)",
                    "pt": "Modelo demo (Adium · 117 medidas)"},
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
