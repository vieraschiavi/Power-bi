# Diseño de los tres tableros

Principio que ordena todo lo que sigue: **cada número tiene un dueño y una
decisión asociada.** Si un visual no cambia una decisión, no va. Un tablero no
se mide por cuántos gráficos tiene sino por cuántas discusiones evita.

---

## Reglas transversales

### Jerarquía de lectura (regla de los 5 segundos)

Cada página se lee de arriba a abajo en tres niveles:

```
┌────────────────────────────────────────────────────────────────┐
│  1. ENCABEZADO   qué estoy mirando + estado del dato            │  10% alto
├────────────────────────────────────────────────────────────────┤
│  2. KPI ROW      4-5 números que responden "¿cómo venimos?"     │  20% alto
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  3. ANÁLISIS     el porqué: evolución, apertura, ranking        │  70% alto
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

A los 5 segundos el usuario tiene que saber si está bien o mal. A los 30, por
qué. A los 2 minutos, qué hacer.

### Encabezado: el estado del dato va visible

En las tres páginas, arriba a la derecha:

```
🟢 Validado contra origen    ·    Último dato: 28/12/2025    ·    🟢 Al día
```

Alimentado por `[Encabezado de Confianza]`, `[Último Dato]` y
`[Estado de Vigencia]`. **Cuando el negocio ve el estado del dato, empieza a
cuidarlo.** Un tablero que no dice cuándo se actualizó por última vez es un
tablero en el que no se puede confiar.

### Paleta

| Uso | Color | Cuándo |
|---|---|---|
| Primario | `#0B3C5D` | Series principales, encabezados |
| Secundario | `#1D7874` | Series de comparación (año anterior, objetivo) |
| Acento | `#F2A65A` | Proyecciones y recomendaciones del modelo |
| OK | `#2E8B57` | Semáforo verde |
| Alerta | `#E4A020` | Semáforo amarillo |
| Riesgo | `#C1443C` | Semáforo rojo |
| Neutro | `#5A6B7B` | Ejes, grillas, texto secundario |

**Todo lo que viene de un modelo va en color acento y con línea punteada.** El
usuario tiene que distinguir de un vistazo qué pasó de qué se estima. Mezclar
real y proyectado en la misma línea sólida es la forma más rápida de perder
credibilidad cuando el modelo falla.

### Accesibilidad

El color **nunca** es el único portador de información: cada semáforo lleva
además ícono y texto (`🔴 Fuera de SLA`). Aproximadamente 1 de cada 12 hombres
tiene alguna deficiencia en la visión del color, y en una compañía LATAM eso
son varias personas en el comité.

### Performance de la página

Máximo **8 visuales por página**. Cada visual es al menos una consulta DAX; una
página con 20 visuales tarda y el usuario deja de usarla. Cuando hacen falta
más cortes, van en drill-through, no apilados en la misma vista.

---

## Tablero 1 — VAR (Ventas · Análisis · Rentabilidad)

**Usuario:** dirección comercial y gerentes de filial.
**Decisión que habilita:** dónde poner el foco comercial este mes.

### Página 1.1 · Resumen ejecutivo

| Zona | Visual | Medidas |
|---|---|---|
| KPI 1 | Card + variación | `Ventas Netas USD`, `Var % vs AA` |
| KPI 2 | Card + gauge | `Cumplimiento %`, `Cumplimiento Proyectado %` |
| KPI 3 | Card + tendencia | `Market Share Valores %`, `Var Share pp` |
| KPI 4 | Card | `Margen Bruto %`, `Var Margen pp` |
| KPI 5 | Card | `MAT Ventas USD`, `MAT Var %` |
| Centro-izq | Línea + columnas | Ventas por mes, con objetivo y año anterior |
| Centro-der | Mapa LATAM | `Ventas Netas USD` por país, color por `Cumplimiento %` |
| Inferior-izq | Barras horizontales | Top 10 SKU por `Ventas Netas USD` |
| Inferior-der | Tarjeta de texto | `Origen de la Variación de Share` |

**El visual que hace la diferencia** es el de abajo a la derecha: no es un
gráfico, es una frase generada por DAX que dice, por ejemplo:

> *"Problema propio: el mercado creció 4,2% y nosotros −1,8%"*

Responde de entrada la primera pregunta que hay que hacerse ante una caída de
share —¿caí yo o creció el mercado?— y evita media reunión.

### Página 1.2 · Puente Precio–Volumen–Mix

Un solo visual protagonista: **gráfico de cascada** con
`Efecto Volumen USD`, `Efecto Precio USD`, `Efecto Mix USD`.

```
Ventas AA  ████████████████████  12,4 M
Volumen         ▲ +0,9 M
Precio               ▼ −0,4 M
Mix                       ▲ +0,2 M
Ventas actual ███████████████████████  13,1 M
```

Debajo, tabla por filial y clase terapéutica con los tres efectos, para bajar
del agregado al foco. Y al pie, `Control Cierre del Puente`: si la
descomposición no cierra exactamente contra la variación total, el tablero lo
dice en rojo. **Una descomposición que no cierra es una opinión, no un dato**, y
esconder el descuadre es la peor decisión posible.

### Página 1.3 · Sell-in vs Sell-out

| Visual | Para qué |
|---|---|
| Línea doble (sell-in / sell-out) por mes | Ver si la venta al canal sigue a la demanda real |
| Tarjeta `Alerta de Carga de Canal` | Traduce la brecha a una frase accionable |
| Dispersión: `Brecha Sell-in vs Sell-out %` vs `Tasa de Devolución Valor %` | El cuadrante superior derecho son los productos que hoy se están cargando al canal y mañana vuelven |
| Tabla por SKU con brecha acumulada | Bajar al detalle |

Esta página es la que da vocabulario de industria al tablero. La dispersión
conecta VAR con Logística: **la carga de canal de hoy es la devolución del mes
que viene**, y verlo en un mismo eje es lo que hace que comercial y supply
dejen de discutir.

### Página 1.4 · Detalle (drill-through)

Tabla a nivel cliente-producto-mes con `Ventas Netas USD`, `Unidades`,
`Precio Promedio USD`, `Descuento Efectivo %`, `Margen Bruto %`.
Se llega por drill-through desde cualquier visual de las páginas anteriores,
conservando el contexto.

---

## Tablero 2 — Ofertas

**Usuario:** Excelencia Comercial y jefes de producto.
**Decisión que habilita:** dónde poner el próximo peso de descuento.

### Página 2.1 · Retorno de la política comercial

| Zona | Visual | Medidas |
|---|---|---|
| KPI | Cards | `Inversión Comercial USD`, `Inversión sobre Ventas %`, `Tasa de Aceptación %`, `ROI de Ofertas` |
| Centro | Líneas | Inversión y ventas con oferta por mes |
| Der. superior | Barras + ranking | `Margen por USD Invertido` por tipo de oferta |
| Der. inferior | Barras | `Inversión en Clientes A %` por filial |
| Pie | Tarjeta de texto | `Nota Metodológica ROI` |

Dos decisiones de diseño que conviene poder defender:

**La nota metodológica va fija en la página, no en un tooltip.** El ROI de una
oferta no es causal: parte de esa venta se habría hecho igual sin descuento.
Decirlo en el propio tablero es lo que evita que alguien lo cite en un comité
como impacto incremental. Prefiero un tablero que declare sus límites a uno que
los esconda.

**`Inversión en Clientes A %`** suele ser el hallazgo más incómodo y más
rentable: descuento asignado a los clientes que menos lo necesitan. Es plata
que ya se está gastando y que se puede reasignar sin pedir presupuesto.

### Página 2.2 · Recomendación del motor de IA

La página que convierte el tablero en herramienta de decisión.

```
┌─────────────────────────────────────────────────────────────────────┐
│  145 recomendaciones · 17.462 USD de margen incremental estimado     │
│  21.285 USD de stock crítico rescatado · 104 requieren test          │
├──────────────────────────────┬──────────────────────────────────────┤
│  Matriz segmento × producto  │  Detalle de la recomendación         │
│  (Top 5 por segmento)        │                                       │
│                              │  SKU        ADM-0114 Farma Demo K114  │
│  Filial ▸ Canal ▸ Segmento   │  Descuento  22%   (actual: 14%)       │
│                              │  Aceptación 80%                       │
│  color = ganancia estimada   │  Riesgo dev 10% 🟢                    │
│  ícono = requiere test       │  Elasticidad −2,88 (nivel Producto)   │
│                              │                                       │
├──────────────────────────────┴──────────────────────────────────────┤
│  JUSTIFICATIVO                                                       │
│  Elasticidad estimada −2,88 (nivel producto), con margen unitario    │
│  de USD 10,33 (59% sobre precio neto); probabilidad de aceptación    │
│  estimada 80%; riesgo de devolución controlado (10%). El 22%         │
│  maximiza el margen esperado neto: USD 1.475 contra USD 1.358 sin    │
│  oferta (+USD 117). NOTA: el óptimo cae en el borde del rango de     │
│  descuentos con evidencia histórica. El modelo NO extrapola más      │
│  allá — si se quiere explorar un descuento mayor, corresponde un     │
│  test controlado sobre un subconjunto de clientes.                   │
└─────────────────────────────────────────────────────────────────────┘
```

**El justificativo ocupa el ancho completo, no un tooltip.** Una recomendación
que un comercial no puede discutir es una recomendación que no va a aplicar.
El texto expone cada término que entró en la decisión —estacionalidad, stock,
elasticidad, aporte al margen, riesgo— para que se pueda objetar punto por
punto. Un modelo que no se puede discutir no se adopta.

La marca **"requiere test controlado"** aparece cuando el óptimo cae en el borde
del rango con evidencia histórica. Es preferible declarar el límite del modelo
y proponer un experimento antes que extrapolar y presentarlo como certeza.

### Página 2.3 · Proyección de inversión

Línea de inversión real vs proyectada por filial, con la parte proyectada en
color acento y punteada. Al pie, `Precisión del Forecast %` calculada **solo
sobre holdout**.

Mostrar la precisión in-sample sería mentir con estadística correcta: el modelo
siempre acierta donde entrenó. El número que va al tablero es el de datos que
el modelo nunca vio.

---

## Tablero 3 — Logística

**Usuario:** Supply Chain y operaciones de filial.
**Decisión que habilita:** qué pedido revisar antes de que salga del depósito.

### Página 3.1 · Nivel de servicio

| Zona | Visual | Medidas |
|---|---|---|
| KPI | Cards con semáforo | `OTIF %`, `Fill Rate %`, `Lead Time Promedio`, `Exceso sobre SLA` |
| Centro | Línea por mes | `OTIF %` con banda de objetivo (95%) |
| Der. | Barras por transportista | `OTIF %` y `Lead Time Promedio` |
| Inferior | Matriz filial × transportista | `OTIF %`, color por semáforo |
| Alerta | Tarjeta de texto | `Alerta de Cadena de Frío` |

`Alerta de Cadena de Frío` cruza producto que requiere frío con transportistas
que no controlan temperatura. Es el hallazgo más accionable del tablero: se
resuelve cambiando una asignación, sin proyecto ni presupuesto. También es la
variable con mayor importancia en el modelo de devoluciones — el dato y el
modelo apuntan al mismo lugar.

### Página 3.2 · Devoluciones

| Visual | Medidas |
|---|---|
| KPI | `Tasa de Devolución Valor %`, `Var Tasa Devolución pp`, `% Devoluciones Evitables`, `Margen Perdido por Devoluciones USD` |
| Pareto por motivo | `Importe Devuelto USD` por motivo, con acumulado |
| Barras apiladas | Devoluciones por área responsable (Logística / Comercial / Calidad) |
| Tarjeta | `Motivo Principal de Devolución` |
| Dispersión | Tasa de devolución vs volumen por cliente — identifica al que devuelve mucho **y** pesa |

La apertura evitable / no evitable es la que hace accionable la página. Un 6%
de devoluciones donde el 80% es evitable es un problema de gestión con dueño;
el mismo 6% mayormente no evitable es una característica del negocio. Actuar
igual en los dos casos es desperdiciar esfuerzo.

### Página 3.3 · Riesgo predictivo (operativa diaria)

La página que se mira **antes** de despachar.

| Visual | Para qué |
|---|---|
| Tabla de pedidos ordenada por `Probabilidad de devolución` desc | La lista de trabajo del día |
| Cards | `Pedidos en Riesgo Crítico`, `Importe en Riesgo USD` |
| Tarjeta de texto | `Lectura del Modelo de Riesgo` |
| Barras por banda de riesgo | Volumen y monto por banda |
| Gráfico de captura acumulada | Qué % de devoluciones se captura revisando qué % de pedidos |

`Lectura del Modelo de Riesgo` traduce el modelo al idioma de quien decide:

> *"Revisando el 10% de pedidos con mayor riesgo se anticipan el 44% de las
> devoluciones. Exposición estimada del período: USD 312.400."*

A un gerente de logística no se le comunica "AUC 0,82". Se le comunica cuántas
devoluciones evita revisando 1 de cada 10 pedidos. Es el mismo modelo, dicho de
la única forma en que se va a usar.

### Página 3.4 · Stock y vencimientos

| Visual | Medidas |
|---|---|
| KPI | `Días de Cobertura`, `Valor de Stock USD`, `Valor en Riesgo de Vencimiento USD` |
| Matriz depósito × clase ATC | `Días de Cobertura` con `Estado de Cobertura` |
| Barras | `Unidades por Vencer` por SKU, ordenado por valor a costo |
| Botón | *"Ver recomendación de oferta"* → drill-through al tablero de Ofertas |

Ese botón es lo que cierra el circuito: el stock por vencer que se detecta acá
es exactamente el input que el motor de IA usa para priorizar qué ofertar. El
usuario pasa del problema a la acción sin salir de Power BI ni exportar a Excel.

---

## Navegación entre tableros

```
     VAR ──────► "esta filial cae en share"
      │
      ├──► Sell-in vs sell-out ──► "hay carga de canal"
      │                                    │
      │                                    ▼
      └──────────────────────────► LOGÍSTICA · devoluciones
                                           │
                                           ▼
                                   Stock por vencer
                                           │
                                           ▼
                                   OFERTAS · recomendación IA
                                           │
                                           ▼
                                   "ofertar este SKU al 22%"
```

Los tres tableros comparten el modelo semántico, así que el drill-through
conserva el contexto de filtro: el usuario nunca pierde dónde estaba parado.

Esa cadena es el argumento del proyecto entero: **de "el share cayó 2 pp" a
"ofertá este SKU en este segmento a este precio, por estas razones" sin salir
de Power BI.**
