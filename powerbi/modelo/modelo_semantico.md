# Modelo semántico — Adium Pharma · Excelencia Comercial

Un solo modelo semántico para los tres tableros. No son tres modelos: son tres
reportes sobre el mismo bus dimensional. Eso es lo que hace que "unidades
vendidas" signifique exactamente lo mismo en VAR, en Ofertas y en Logística —
y es la diferencia entre democratizar información y multiplicar versiones de
la verdad.

---

## 1. Arquitectura: estrella, no copo de nieve

```
                        ┌──────────────────┐
                        │  dim_calendario  │  ← marcada como tabla de fechas
                        └────────┬─────────┘
                                 │
   ┌──────────────┐              │              ┌──────────────────┐
   │ dim_producto ├──────────┐   │   ┌──────────┤   dim_cliente    │
   └──────────────┘          ▼   ▼   ▼          └──────────────────┘
                        ╔═══════════════════╗
   ┌──────────────┐     ║                   ║   ┌──────────────────┐
   │  dim_filial  ├────►║   fact_ventas     ║◄──┤ dim_transportista│
   └──────────────┘     ║                   ║   └──────────────────┘
                        ╚═══════════════════╝
   ┌──────────────┐              ▲   ▲          ┌──────────────────┐
   │ dim_deposito ├──────────────┘   └──────────┤ dim_tipo_oferta  │
   └──────────────┘                             └──────────────────┘

   Otros hechos sobre las mismas dimensiones:
     fact_devoluciones · fact_ofertas · fact_sellout · fact_objetivos
     fact_stock · fact_recomendaciones · fact_scoring_devoluciones
```

**Por qué estrella y no copo.** Power BI corre sobre VertiPaq, un motor columnar
en memoria que comprime cada columna con diccionario y run-length. La
normalización ahorra espacio en un motor de filas; en un motor columnar ahorra
poco y cuesta mucho en tiempo de consulta, porque cada salto adicional entre
tablas es trabajo en cada query. La jerarquía ATC —que en un OLTP sería tres
tablas normalizadas— vive acá aplanada dentro de `dim_producto`.

**Excepción declarada:** ninguna. Con 120 SKU y 900 clientes no hay dimensión
lo bastante grande como para justificar normalizarla.

---

## 2. Relaciones

| Desde (1) | Hacia (*) | Columna | Cardinalidad | Dirección | Activa |
|---|---|---|---|---|---|
| dim_calendario | fact_ventas | Fecha | 1:* | Simple | Sí |
| dim_producto | fact_ventas | Id producto | 1:* | Simple | Sí |
| dim_cliente | fact_ventas | Id cliente | 1:* | Simple | Sí |
| dim_filial | fact_ventas | Id filial | 1:* | Simple | Sí |
| dim_deposito | fact_ventas | Id depósito | 1:* | Simple | Sí |
| dim_transportista | fact_ventas | Id transportista | 1:* | Simple | Sí |
| dim_tipo_oferta | fact_ventas | Id tipo oferta | 1:* | Simple | Sí |
| dim_calendario | fact_devoluciones | Fecha | 1:* | Simple | Sí |
| dim_motivo_devolucion | fact_devoluciones | Id motivo | 1:* | Simple | Sí |
| dim_producto / dim_cliente / dim_filial / dim_transportista | fact_devoluciones | (sus ids) | 1:* | Simple | Sí |
| dim_calendario | fact_ofertas | Fecha | 1:* | Simple | Sí |
| dim_producto / dim_cliente / dim_filial / dim_tipo_oferta | fact_ofertas | (sus ids) | 1:* | Simple | Sí |
| dim_calendario | fact_sellout | Fecha | 1:* | Simple | Sí |
| dim_producto / dim_filial | fact_sellout | (sus ids) | 1:* | Simple | Sí |
| dim_calendario | fact_objetivos | Fecha | 1:* | Simple | Sí |
| dim_producto / dim_filial | fact_objetivos | (sus ids) | 1:* | Simple | Sí |
| dim_calendario | fact_stock | Fecha | 1:* | Simple | Sí |
| dim_producto / dim_deposito | fact_stock | (sus ids) | 1:* | Simple | Sí |
| dim_producto / dim_filial | fact_recomendaciones | (sus ids) | 1:* | Simple | Sí |
| dim_calendario / dim_producto / dim_cliente / dim_filial / dim_transportista | fact_scoring_devoluciones | (sus ids) | 1:* | Simple | Sí |

### Tres decisiones que conviene poder defender

**Todas las relaciones son 1:muchos con dirección simple.** El filtro viaja de
la dimensión al hecho y nunca al revés.

**Cero relaciones bidireccionales en el modelo.** El filtro cruzado bidireccional
resuelve un problema puntual y crea dos: caminos de filtro ambiguos y pérdida
de performance en todas las consultas, no solo en la que lo necesitaba. Cuando
hace falta propagación inversa se resuelve dentro de la medida con
`CROSSFILTER()`, que lo activa solo ahí.

**Cero relaciones muchos-a-muchos.** Si aparece una, casi siempre significa que
falta una dimensión puente. En este modelo, `dim_cliente` y `dim_filial`
resuelven lo que de otro modo sería un M:M entre ventas y estructura comercial.

### El clásico "el total no coincide con la suma de las filas"

Cuatro causas, en orden de frecuencia:

1. Filtro bidireccional creando un camino ambiguo.
2. Relación muchos-a-muchos con resultados no determinísticos.
3. Una medida con `ALL()` mal ubicado en el denominador.
4. **Valores en el hecho sin correspondencia en la dimensión** — se agrupan en
   una fila en blanco. Esto lo detecta el control de integridad referencial de
   `sql/03_calidad_datos.sql` **antes** de publicar, que es justamente el punto:
   el error no debería llegar al tablero.

---

## 3. Tabla de fechas

`dim_calendario` es contigua (sin días faltantes), va del 1/1 del primer año al
31/12 del último, y está marcada con **Mark as date table**. Sin esa marca, las
funciones de inteligencia de tiempo pueden devolver resultados incorrectos sin
avisar.

Detalles que se pasan por alto y rompen el tablero:

- `[Mes]` ordenado por `[Mes N°]` (Sort by column). Sin eso, "Abr" aparece antes
  que "Ene" y nadie entiende el gráfico.
- `[Año-Mes]` ordenado por `[Año-Mes orden]`.
- **Nunca** usar la fecha de la tabla de hechos para inteligencia de tiempo.
- El nombre del mes se genera en SQL con `CHOOSE()`, no con `FORMAT()`: `FORMAT`
  depende del `LANGUAGE` de la sesión, y así el reporte cambia según quién lo
  corre.

---

## 4. Optimización del modelo — con evidencia medida

El pipeline reporta el antes y el después en cada corrida (`python src/02_transformar.py`):

```
grano línea de factura :   235,599 filas
grano analítico        :   234,455 filas
id_linea eliminado     :   235,599 valores distintos fuera del modelo
memoria del modelo     :      48.1 MB → 20.4 MB  (-57.6%)
```

**Qué se hizo, en orden de impacto:**

1. **Sacar `id_linea` del modelo.** Era la columna de mayor cardinalidad —un
   valor distinto por fila— y por lo tanto la más cara de comprimir. Nadie
   consulta una línea de factura individual en un tablero de gestión: preguntan
   por cliente, producto, mes, depósito. El conteo de líneas se conserva como
   medida aditiva, que era lo único que se perdía.

2. **Bajar el ancho de cada columna al mínimo que soporta su rango real**
   (`int64 → int32/int16`, `float64 → float32`). El costo de una tabla tabular
   lo manda la cardinalidad y el ancho de columna, no la cantidad de filas.

3. **Redondeo controlado de importes a 2 decimales antes de bajar precisión.**
   Un `float64` con 12 decimales de basura tiene cardinalidad casi única y
   destruye la compresión por diccionario.

4. **Exponer numeradores, no promedios.** `[Lead time x línea]` y
   `[Cobertura x stock]` van al modelo; el promedio se calcula en DAX con
   `DIVIDE`. Un promedio precalculado se promedia mal en cuanto el usuario
   cambia de nivel de agregación.

5. **Columnas calculadas: ninguna en el modelo.** Todo lo que se puede resolver
   aguas arriba se resuelve en SQL o en Python. Máxima de Roche: transformá lo
   más arriba posible — base > Power Query > DAX.

### Orden de diagnóstico cuando un modelo va lento

Contar el orden ya es la respuesta correcta: muestra método, no recetas.

1. **Medir primero** — Performance Analyzer: ¿el tiempo se va en DAX query,
   visual display u "other"?
2. **DAX Studio / VertiPaq Analyzer** — qué columnas ocupan memoria y con qué
   cardinalidad.
3. **Bajar cardinalidad** — es lo que más pesa. Separar fecha y hora, quitar
   decimales innecesarios, eliminar IDs de transacción que nadie usa.
4. **Sacar columnas que nadie usa** — cada columna cargada es memoria.
5. **Aplanar a estrella y eliminar bidireccionales.**
6. **Reescribir medidas** — variables en vez de repetir subexpresiones, evitar
   `FILTER` sobre tablas enteras.
7. **Reducir visuales por página** — cada visual es al menos una query.
8. **Incremental refresh** si el volumen es el problema real.

---

## 5. Modo de conexión

**Import.** Es la decisión correcta acá y conviene poder justificarla:

| Modo | Cuándo tendría sentido en este caso |
|---|---|
| **Import** ✅ | 20 MB de modelo, refresh diario, mejor performance de consulta |
| DirectQuery | Solo si el negocio necesitara latencia intradiaria real |
| Direct Lake | La opción natural si el DW estuviera en Fabric/OneLake: velocidad de Import con frescura de DQ |
| Composite | Innecesario: no hay un hecho tan grande que justifique la complejidad |
| Live Connection | Es lo que usarían los reportes derivados sobre este mismo modelo publicado |

**Incremental refresh** configurado con `RangeStart` / `RangeEnd` sobre
`fact_ventas`: se recargan los últimos 45 días y se conserva el histórico
particionado. Requisito que hay que verificar sí o sí: el origen tiene que
soportar **query folding**, si no descarga todo igual y no sirve de nada. Se
comprueba con *View Native Query* en Power Query.

---

## 6. Row-Level Security

Con presencia en toda LATAM, RLS es requisito, no adorno.

**Rol único dinámico** (no un rol por país, que no escala):

```dax
// Sobre la tabla puente Seguridad_Usuarios(Email, Id filial)
[Email] = USERPRINCIPALNAME()
```

La tabla puente se relaciona 1:* contra `dim_filial`, del lado 1, y el filtro
se propaga por las relaciones hasta los hechos. Un gerente regional con 5
países tiene 5 filas con su email — ese detalle práctico es el que distingue a
alguien que lo implementó de alguien que lo leyó.

**Se testea** con *View as role → Other user*, no asumiendo que funciona.

| Rol | Alcance |
|---|---|
| `Corporativo` | Sin filtro — Excelencia Comercial y dirección |
| `Filial` | Dinámico por `USERPRINCIPALNAME()` |
| `Regional` | Dinámico, múltiples filiales por usuario |

---

## 7. Diccionario de métricas

El diccionario mínimo viable no documenta 400 campos: documenta las métricas
que se usan en el 90% de las decisiones, con **nombre, definición, fórmula,
fuente y dueño**. Cambiar una definición requiere aprobación del dueño y queda
versionada en este repositorio.

| Métrica | Definición | Fuente | Dueño |
|---|---|---|---|
| Ventas Netas USD | Facturación menos notas de crédito, convertida a USD al TC del mes de la operación | `fact_ventas` | Controlling |
| Unidades | Unidades facturadas menos devueltas por NC | `fact_ventas` | Controlling |
| Margen Bruto | Ventas netas − costo estándar. Los SKU con costo imputado se marcan | `fact_ventas` + `dim_producto` | Finanzas |
| Market Share | Sell-out propio / mercado de la clase, en valores **y** en unidades | `fact_sellout` | Excelencia Comercial |
| MAT | Total móvil de 12 meses | `fact_ventas` | Excelencia Comercial |
| OTIF | Líneas entregadas a tiempo **y** completas / líneas despachadas | `fact_ventas` | Supply Chain |
| Tasa de Devolución | Importe devuelto / ventas brutas | `fact_devoluciones` | Supply Chain |
| Inversión Comercial | Descuento otorgado sobre ofertas aceptadas, ajustado por costo relativo del instrumento | `fact_ofertas` | Excelencia Comercial |

**Regla de nombres.** Lo que el usuario lee tiene que decir exactamente lo que
es: `Ventas Netas USD (sin IVA, sin devoluciones)` y no `Ventas`. La ambigüedad
en el nombre de una métrica es la causa raíz de la mitad de las discusiones de
comité.

---

## 8. Cómo armar el modelo en Power BI Desktop

1. **Origen:** *Get Data → SQL Server*, y conectar a las **vistas** `star.v_*`
   (nunca a las tablas). La capa de vistas es el contrato: aísla el `.pbix` de
   cambios físicos y deja el query folding intacto.
   Para probar sin SQL Server, `Get Data → Parquet` apuntando a `data/star/`.

2. **Power Query:** no debería hacer falta ninguna transformación. Todo se
   resolvió aguas arriba. Si aparece un paso acá, es señal de que algo se
   escapó del ETL.

3. **Modelado:** crear las relaciones de la tabla de la sección 2, todas
   simples y 1:*. Marcar `v_dim_calendario` como tabla de fechas.

4. **Ocultar** todas las columnas `Id *` de los hechos y las de las
   dimensiones que no se usan como atributo. Un panel de campos limpio es
   parte del trabajo, no un detalle estético.

5. **Sort by column:** `[Mes]` por `[Mes N°]`, `[Año-Mes]` por `[Año-Mes orden]`.

6. **Medidas:** crear una tabla vacía `_Medidas` (*Enter Data*, una columna,
   borrar la columna) y cargar ahí el contenido de `powerbi/dax/*.dax`.

7. **Formatos:** importes en `#,0` sin decimales; porcentajes con 1 decimal;
   variaciones en pp con 1 decimal. Consistente en los tres tableros.
