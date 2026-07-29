# Adium Pharma · Excelencia Comercial Corporativo
### Tres tableros de Power BI sobre un modelo semántico único, con ML y un motor de recomendación explicable

Proyecto end-to-end que va del dato crudo a la decisión comercial: simula los
sistemas origen de un laboratorio farmacéutico con presencia en LATAM, los
limpia con controles de Data Steward, los modela en estrella, entrena modelos
predictivos con validación temporal honesta y termina en un motor que recomienda
**qué producto ofertar, a qué precio, en qué segmento y por qué**.

> **Nota sobre los datos.** El dataset es **sintético y generado por código**
> (`src/01_generar_dataset.py`, semilla fija). No hay información real de ninguna
> compañía. Las métricas que se reportan son reales sobre esos datos: se miden
> con validación temporal, sobre un holdout que el modelo nunca vio, y el
> pipeline es reproducible con un comando. Donde un resultado está limitado por
> el propio simulador, se dice.

---

## Qué hay acá

| Carpeta | Contenido |
|---|---|
| `src/` | Pipeline Python: generación, transformación, ML y motor de IA |
| `sql/` | DDL del modelo estrella, ETL, controles de calidad y vistas semánticas (T-SQL) |
| `powerbi/archivos/` | **Los tres tableros listos para abrir** (`.pbit` y PBIP) |
| `powerbi/esquema.py` | El contrato único: nombres, tipos, relaciones, formatos |
| `powerbi/validar_contrato.py` | Verifica que las 4 capas del modelo no divergieron |
| `powerbi/dax/` | Biblioteca DAX: medidas base + una por tablero |
| `powerbi/generar_pbit.py` | Genera los archivos de Power BI desde ese contrato |
| `powerbi/tema_adium.json` | Tema corporativo importable en Power BI |
| `powerbi/modelo/` | Modelo semántico: relaciones, RLS, optimización, diccionario de métricas |
| `powerbi/diseno_tableros.md` | Diseño página por página de los tres tableros |
| `docs/` | Documentación visual del proceso completo |
| `data/out/` | Salidas versionadas: controles de calidad y recomendaciones |

---

## Correrlo

**En Windows, un doble clic en `construir_tableros.bat`** hace todo: instala
dependencias, corre el pipeline, valida el contrato del modelo, regenera los
tres archivos con la ruta de datos de tu máquina y abre el primero.

A mano:

```bash
pip install -r requirements.txt
python src/run_all.py                    # ~65 s, reproducible
python powerbi/generar_sql_vistas.py     # vistas SQL desde el contrato
python powerbi/validar_contrato.py       # ¿las 4 capas dicen lo mismo?
python powerbi/generar_pbit.py           # los tres archivos de Power BI
```

Genera todo en `data/`. Después, doble clic en
`powerbi/archivos/Adium_VAR.pbit`: Power BI Desktop pide la ruta de
`data/star`, carga, y con *Archivo → Guardar como* queda el `.pbix`.
Instrucciones completas en [`powerbi/archivos/LEEME.md`](powerbi/archivos/LEEME.md).

El modelo estrella también se despliega en SQL Server con los scripts de
`sql/`; los nombres de columna del modelo son exactamente los que devuelven las
vistas `star.v_*`, así que las 117 medidas funcionan igual sin tocar DAX.

---

## Los cinco pasos

### 1 · Dataset — simular como es, no como conviene

`src/01_generar_dataset.py` genera cuatro sistemas origen: ERP de facturación,
panel de auditoría tipo IQVIA, CRM de ofertas y WMS/TMS de logística. 8 filiales
LATAM, 120 SKU con jerarquía ATC, 900 clientes, 24 meses, ~235.000 líneas.

Lo que hace este generador distinto de un `random.rand()`:

- **Los defectos de calidad están inyectados a propósito.** Duplicados por
  reproceso, fechas en dos formatos conviviendo, importes negativos que son
  notas de crédito mal clasificadas, un filial-mes sin cargar en el panel,
  costos estándar faltantes. Sin eso, el paso 2 sería decorativo.
- **El ERP factura en moneda local.** La normalización FX es trabajo del ETL,
  como en la realidad.
- **Los targets tienen estructura causal.** Las devoluciones dependen de cadena
  de frío sin control de temperatura, vida útil remanente, exceso sobre SLA y
  carga de canal. La aceptación de ofertas depende de descuento, estacionalidad,
  cobertura del cliente y calidad del representante.
- **El precio mueve la demanda** vía `q = q_base · (1−d)^ε`, con una elasticidad
  propia por SKU. Es lo que después el paso 5 tiene que *recuperar* — y por eso
  la elasticidad estimada se puede validar contra la verdadera.

### 2 · Transformación y Data Steward

`src/02_transformar.py` + `sql/02` y `sql/03`.

**14 controles de calidad** sobre las 6 dimensiones canónicas (completitud,
exactitud, consistencia, unicidad, vigencia, validez). Cada uno deja evidencia
en `data/out/calidad_datos.csv`, con la acción asociada y la severidad. Los
críticos **bloquean la publicación**: si el modelo no reconcilia contra el
origen, no sale.

```
[ CRIT ] Completitud   Filial-mes sin carga del panel de auditoría         1
[ CRIT ] Unicidad      Líneas de factura duplicadas por reproceso      1.953
[ CRIT ] Exactitud     Unidades > 25x la mediana del SKU (dedazo)        338
[ alert] Validez       Importes/unidades negativos (notas de crédito)    978
[ alert] Completitud   Despachos sin transportista informado           1.465
```

Dos criterios que se aplican sin excepción:

- **Un outlier se marca, no se corrige en silencio.** Corregir sin avisar es
  peor que el error, porque nadie puede auditarlo después.
- **Un filial-mes faltante se muestra como "sin dato", nunca como cero.** Un
  cero dice "no vendió"; un blanco dice "no reportó". Confundirlos arruina
  cualquier análisis de market share.

**Optimización del modelo, medida y no declarada:**

```
grano línea de factura :   234.724 filas
id_linea eliminado     :   234.724 valores distintos fuera del modelo
memoria del modelo     :      46,7 MB → 19,9 MB  (−57,3%)
```

El ahorro no viene de tirar filas: viene de sacar la columna de mayor
cardinalidad —que nadie consulta en un tablero de gestión— y de ajustar el ancho
de cada columna a su rango real. En un motor columnar como VertiPaq, el costo lo
manda la cardinalidad, no la cantidad de filas.

### 3 · Modelo de devoluciones

`src/03_ml_devoluciones.py`. Dos entregables para dos preguntas distintas.

**(A) "¿Este pedido que estoy por despachar va a volver?"** — clasificación a
nivel pedido, holdout temporal (oct–dic 2025, 29.193 pedidos):

| Métrica | Valor |
|---|---|
| Accuracy | **0,877** |
| Precision | 0,443 |
| Recall | 0,483 |
| ROC-AUC | **0,822** |
| Tasa base | 11,0% |
| **Captura en el top 10% de riesgo** | **43,9%** (lift 4,4×) |

**El techo teórico del problema es 0,847** — el AUC que lograría alguien que
conociera la probabilidad real del proceso generador. El modelo alcanza el
**98% de ese techo**: lo que falta no es modelo, es ruido irreducible. Poder
distinguir una cosa de la otra evita meses de tuning inútil.

Lo que va al tablero no es el AUC: es *"revisando el 10% de pedidos con mayor
riesgo se anticipan el 44% de las devoluciones"*. Es el mismo modelo, dicho de
la única forma en que se va a usar.

**Calibración isotónica, y no es opcional.** `class_weight="balanced"` ayuda a
aprender un evento minoritario pero deforma la probabilidad hacia arriba:
media cruda **0,360** contra una tasa real de **0,119**. Después de calibrar:
**0,119**. Para ordenar pedidos alcanzaba sin calibrar; para que el motor de
precios use ese número como tasa esperada, no.

**(B) "¿Cuánta devolución voy a tener el mes que viene?"** — proyección mensual
por filial. WMAPE **0,160** en holdout contra **0,195** del naive (+3,5 pp).
Alimenta la provisión contable sugerida.

### 4 · Modelo de ofertas

`src/04_ml_ofertas.py`.

**Aceptación de oferta**, holdout temporal (5.149 ofertas):

| Métrica | Umbral F1 | Umbral 0,5 |
|---|---|---|
| Accuracy | 0,656 | **0,674** |
| Precision | 0,634 | 0,691 |
| Recall | **0,848** | 0,707 |
| ROC-AUC | 0,743 | 0,743 |

Techo teórico **0,770** — el modelo alcanza el **96%**.

Se reportan **dos puntos de operación** porque sirven para cosas distintas: el
umbral F1 arma la lista de llamados del representante (prioriza cobertura); el
0,5 estima cuántas ofertas se van a aceptar (prioriza exactitud). Usar un solo
umbral para las dos cosas es forzar un compromiso que no hace falta.

**Proyección de inversión comercial:** WMAPE **0,117** contra **0,390** del
naive — **27,3 pp de mejora**. Es la cifra que va al presupuesto del mes
siguiente.

### 5 · Motor de IA: precio y producto por segmento

`src/05_ia_precios.py`. Cuatro piezas, ninguna es una caja negra:

**1. Elasticidad precio** estimada por regresión log-log con efectos fijos de
mes, y jerarquía de respaldo producto → ATC3 → ATC1 → global cuando no hay datos
suficientes. Controlar por mes es lo que evita confundir estacionalidad con
precio: justamente se descuenta más fuera de temporada.

> Validación: la elasticidad estimada correlaciona **0,714** con la elasticidad
> real del simulador. El parámetro se recupera de verdad, no es un número que
> queda lindo en una tabla.

**2. Probabilidad de aceptación** del modelo calibrado del paso 4, evaluada
**contrafácticamente** sobre una grilla de descuentos. Esto es lo que convierte
un modelo predictivo en un modelo de decisión.

**3. Optimización** del margen esperado neto:

```
demanda(d)  = q_base · (1−d)^ε                    ← curva de demanda, tope 3× q_base
p_acept(d)  = modelo calibrado                    ← contrafáctico
margen(d)   = p_acept · demanda · (P(1−d) − C)
riesgo(d)   = riesgo_base · (1 + 1,2·sobrestock + 0,9·lote_corto + 1,5·d)
objetivo(d) = margen(d) · (1 − riesgo(d)) + valor_de_stock_rescatado
```

Con dos restricciones que no son de modelo sino de negocio:

- **Piso de margen del 15%.** Los descuentos que lo perforan salen de la grilla.
  Una restricción dura se explica en una línea; una penalización blanda hay que
  defenderla.
- **La grilla se recorta al percentil 95 histórico de descuentos.** Un modelo de
  árboles extrapola pésimo: fuera de su soporte devuelve el valor de la hoja del
  borde y el optimizador se va siempre al extremo. Eso no es un hallazgo, es un
  artefacto.

**4. Justificativo explicable**, generado por reglas a partir de las mismas
variables que entraron en la decisión:

> *Hay sobrestock: 118 días de cobertura contra un máximo deseado de 90; 3.400
> unidades vencen en menos de 180 días (USD 12.400 rescatables); el SKU aporta
> el 3,2% del margen de la filial; elasticidad estimada −2,88 (nivel Producto),
> con margen unitario de USD 10,33 (59% sobre precio neto); probabilidad de
> aceptación estimada 80%; riesgo de devolución controlado (10%). **El 22%
> maximiza el margen esperado neto: USD 1.475 contra USD 1.358 sin oferta
> (+USD 117).***

Salida para enero 2026: **145 recomendaciones** sobre **58 segmentos**,
USD 17.462 de margen incremental estimado y USD 21.285 de stock crítico
rescatado.

**112 de las 145 quedan marcadas como "requiere test controlado"**: su óptimo
cae en el borde del rango con evidencia histórica. El motor declara el límite
y propone un experimento en lugar de extrapolar y presentarlo como certeza.

---

## Los tres tableros

| Tablero | Pregunta | Pieza distintiva |
|---|---|---|
| **VAR** (Ventas·Análisis·Rentabilidad) | ¿Cómo venimos contra objetivo, año anterior y mercado? | Puente Precio–Volumen–Mix con control de cierre |
| **Ofertas** | ¿Cuánto cuesta la política comercial y dónde poner el próximo peso? | Recomendación del motor de IA con justificativo discutible |
| **Logística** | ¿Entregamos bien y qué pedidos van a volver? | Scoring de riesgo consultado **antes** de despachar |

Detalle página por página en [`powerbi/diseno_tableros.md`](powerbi/diseno_tableros.md).

**Un solo modelo semántico para los tres.** No son tres modelos: son tres
reportes sobre el mismo bus dimensional. Eso es lo que hace que "unidades
vendidas" signifique exactamente lo mismo en los tres y que el drill-through
entre tableros conserve el contexto de filtro.

La cadena que conecta todo:

```
VAR: "cae el share en Perú"
  └─► sell-in vs sell-out: "hay carga de canal"
        └─► LOGÍSTICA: devoluciones y stock por vencer
              └─► OFERTAS: "ofertá este SKU al 22% en este segmento, por esto"
```

---

## Decisiones técnicas que conviene poder defender

**Validación temporal, nunca aleatoria.** Un random split en datos con tiempo
mezcla futuro con pasado y devuelve métricas que después no se reproducen.
Train ≤ 30/06/2025, validación jul–sep, holdout oct–dic. El holdout no se toca
hasta el final.

**Features históricos con `expanding + shift(1)` y suavizado bayesiano.** Toda
tasa histórica se calcula con información estrictamente anterior al mes que se
predice. Una clave con 3 observaciones no puede tener tasa 100%: por eso el
suavizado hacia la media global.

**Umbrales calibrados en validación, medidos en holdout.** Elegir el umbral
mirando el holdout es contaminarlo.

**Todo ratio se calcula en DAX, no en SQL.** Un ratio materializado se promedia
mal en cuanto el usuario cambia de nivel de agregación. El modelo expone
numeradores (`Lead time × línea`, `Cobertura × stock`); la división va en la
medida.

**Todo lo demás se transforma lo más arriba posible.** Máxima de Roche: base >
Power Query > DAX. Cuanto más arriba, más barato y más reutilizable. En este
modelo no hay ninguna columna calculada en DAX.

**Cero relaciones bidireccionales.** Resuelven un problema puntual y crean dos:
caminos ambiguos y pérdida de performance en todas las consultas. Cuando hace
falta, se usa `CROSSFILTER()` dentro de la medida.

**Power BI se conecta a vistas, no a tablas.** La capa `star.v_*` es el
contrato: aísla el `.pbix` de cambios físicos, versiona las definiciones en el
repositorio y deja el query folding intacto.

---

## Límites, dichos de frente

- **Los datos son sintéticos.** Las métricas de los modelos son reales sobre
  esos datos, pero un dataset generado tiene una estructura causal más limpia
  que la realidad. Por eso se reporta el **AUC oráculo**: da la referencia de
  cuánto de lo que falta es ruido del propio problema.
- **El ROI de ofertas no es causal.** Parte de la venta con oferta se habría
  hecho igual sin descuento — eso es canibalización, y sin grupo de control no
  se puede separar. Se reporta como comparativo entre filiales e instrumentos,
  y la advertencia va fija en el tablero, no en un tooltip.
- **La proyección de devoluciones por filial-mes tiene poco margen sobre el
  naive** (+3,5 pp). La serie es corta y en buena parte ruido; el modelo está
  cerca del piso. Saber cuándo un modelo no puede ganarle mucho al método simple
  vale más que forzar una mejora que no se va a sostener en producción.
- **Los archivos de Power BI son `.pbit` y PBIP, no `.pbix` binario.** Un
  `.pbix` guarda el modelo tabular como un binario propietario de Analysis
  Services: no se puede autorizar desde afuera de Power BI y es una caja negra
  para el control de versiones. Los tres archivos de `powerbi/archivos/` llevan
  todo adentro —20 tablas, 38 relaciones, 117 medidas, RLS y las páginas— y
  desde cualquiera de los dos formatos, llegar al `.pbix` es un *Guardar como*.
  Se validaron por código (estructura, codificación, sintaxis M, cero
  referencias rotas), pero **no se pudieron abrir en Power BI Desktop**, que no
  corre en el entorno donde se generaron.
