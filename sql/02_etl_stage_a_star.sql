/* =========================================================================
   ADIUM PHARMA — 02 · ETL de staging a modelo estrella

   Estas son LAS reglas de negocio canónicas. Están acá, en SQL, y no en DAX,
   por una razón concreta: una regla en DAX vive dentro de un reporte; una
   regla en SQL la ven todos los consumos (Power BI, Excel, otro tablero,
   una API). Cuando alguien pregunta "¿por qué este número da distinto?", la
   respuesta tiene que estar en un solo lugar.

   Orden de ejecución: 01 (DDL) → 02 (este) → 03 (calidad) → 04 (vistas)
   ========================================================================= */

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* -------------------------------------------------------------------------
   0 · Calendario contiguo
   Sin días faltantes, del 1/1 del primer año al 31/12 del último.
   Se genera acá y no en DAX para que sea el mismo calendario en todo consumo.
   ------------------------------------------------------------------------- */
DECLARE @desde DATE = '2024-01-01', @hasta DATE = '2025-12-31';

;WITH n AS (
    SELECT TOP (DATEDIFF(DAY, @desde, @hasta) + 1)
           ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
), f AS (
    SELECT DATEADD(DAY, i, @desde) AS fecha FROM n
)
INSERT INTO star.dim_calendario
SELECT
    fecha,
    YEAR(fecha),
    MONTH(fecha),
    -- nombre de mes en español, fijo: no depende del LANGUAGE de la sesión,
    -- que es una fuente clásica de reportes que cambian según quién los corre
    CHOOSE(MONTH(fecha),'Ene','Feb','Mar','Abr','May','Jun',
                        'Jul','Ago','Sep','Oct','Nov','Dic'),
    FORMAT(fecha,'yyyy-MM'),
    YEAR(fecha) * 100 + MONTH(fecha),
    'Q' + CAST(DATEPART(QUARTER, fecha) AS CHAR(1)),
    CAST(YEAR(fecha) AS CHAR(4)) + '-Q' + CAST(DATEPART(QUARTER, fecha) AS CHAR(1)),
    ((DATEPART(WEEKDAY, fecha) + @@DATEFIRST - 2) % 7) + 1,   -- lunes = 1, sin depender de DATEFIRST
    CASE WHEN ((DATEPART(WEEKDAY, fecha) + @@DATEFIRST - 2) % 7) + 1 <= 5 THEN 1 ELSE 0 END,
    CASE WHEN fecha <= @hasta THEN 1 ELSE 0 END,
    CASE WHEN fecha = EOMONTH(fecha) THEN 1 ELSE 0 END,
    CASE WHEN MONTH(fecha) BETWEEN 5 AND 8 THEN 1 ELSE 0 END   -- temporada respiratoria hemisferio sur
FROM f;
GO

/* -------------------------------------------------------------------------
   1 · Producto — imputación trazable del costo estándar
   Regla: un costo faltante NO se rellena con cero (eso inventa margen 100%)
   ni se descarta (eso pierde la venta). Se imputa con la mediana del ATC3 y
   se MARCA. El tablero muestra la marca; el negocio decide si confía.
   ------------------------------------------------------------------------- */
INSERT INTO star.dim_producto
SELECT
    p.id_producto, p.sku, p.marca, p.atc1, p.atc1_desc, p.atc3,
    p.forma_farmaceutica, p.presentacion, p.tipo_venta, p.cadena_frio,
    p.ciclo_vida, p.vida_util_meses, p.precio_lista_usd,
    COALESCE(p.costo_std_usd, m.costo_mediana_atc3, g.costo_mediana_global) AS costo_std_usd,
    CASE WHEN p.costo_std_usd IS NULL THEN 1 ELSE 0 END                     AS costo_imputado,
    CASE WHEN p.precio_lista_usd > 0
         THEN 1 - COALESCE(p.costo_std_usd, m.costo_mediana_atc3, g.costo_mediana_global)
                  / p.precio_lista_usd
    END                                                                      AS margen_std_pct
FROM stg.producto p
OUTER APPLY (
    SELECT costo_mediana_atc3 = PERCENTILE_CONT(0.5)
           WITHIN GROUP (ORDER BY x.costo_std_usd) OVER ()
    FROM stg.producto x
    WHERE x.atc3 = p.atc3 AND x.costo_std_usd IS NOT NULL
) m
CROSS APPLY (
    SELECT TOP 1 costo_mediana_global = PERCENTILE_CONT(0.5)
           WITHIN GROUP (ORDER BY y.costo_std_usd) OVER ()
    FROM stg.producto y WHERE y.costo_std_usd IS NOT NULL
) g;
GO

/* -------------------------------------------------------------------------
   2 · Cliente — normalización de la clave de negocio
   TRIM + UPPER siempre. Un código con un espacio adelante es un cliente
   distinto para el motor, y aparece como fila en blanco en el tablero.
   ------------------------------------------------------------------------- */
INSERT INTO star.dim_cliente
SELECT
    c.id_cliente,
    UPPER(LTRIM(RTRIM(c.cod_cliente))) AS cod_cliente,
    c.razon_social, c.id_filial, c.canal, c.segmento,
    c.antiguedad_meses, c.id_representante
FROM stg.cliente c;
GO

/* -------------------------------------------------------------------------
   3 · Hecho de ventas — el corazón del ETL

   Cinco reglas de negocio, todas explícitas:

   R1  DEDUPLICACIÓN: el reproceso de carga duplica líneas. Se conserva una
       sola por id_linea (la primera cargada).
   R2  NOTAS DE CRÉDITO: el origen manda importes negativos. NO se descartan
       ni se dejan negativos sueltos: se clasifican como 'NC', se pasan a
       positivo y se guarda el signo aparte. Así "ventas brutas" y "ventas
       netas" son dos medidas distintas y ambas son auditables.
   R3  NORMALIZACIÓN FX: cada filial factura en su moneda. Se convierte a USD
       con el tipo de cambio DEL MES DE LA OPERACIÓN, no con el de hoy.
       Usar el TC actual para todo el histórico es el error que hace que el
       acumulado del año cambie cada vez que se refresca el tablero.
   R4  OUTLIERS: una línea con más de 25x la mediana del SKU se MARCA, no se
       corrige. Corregir en silencio es peor que el error.
   R5  AGREGACIÓN DE GRANO: se sube de línea de factura a grano analítico.
       Se pierde id_linea (que nadie consulta) y se gana compresión.
   ------------------------------------------------------------------------- */
WITH dedup AS (              -- R1
    SELECT *, ROW_NUMBER() OVER (PARTITION BY id_linea ORDER BY id_linea) AS rn
    FROM stg.sellin
    WHERE fecha IS NOT NULL
),
clasificado AS (             -- R2
    SELECT
        d.*,
        CASE WHEN d.importe_local < 0 OR d.unidades < 0 THEN 'NC' ELSE 'FC' END AS tipo_documento,
        ABS(d.unidades)             AS unidades_abs,
        ABS(d.importe_local)        AS importe_local_abs,
        ABS(d.costo_total_local)    AS costo_local_abs,
        ABS(d.importe_devuelto_local) AS importe_devuelto_local_abs
    FROM dedup d
    WHERE d.rn = 1
),
convertido AS (              -- R3
    SELECT
        c.*,
        tc.tc_a_usd,
        c.importe_local_abs          / tc.tc_a_usd AS importe_usd,
        c.costo_local_abs            / tc.tc_a_usd AS costo_usd,
        c.importe_devuelto_local_abs / tc.tc_a_usd AS importe_devuelto_usd
    FROM clasificado c
    JOIN star.dim_filial f  ON f.id_filial = c.id_filial
    JOIN star.fact_tipo_cambio tc
      ON tc.moneda = f.moneda
     AND tc.fecha  = DATEFROMPARTS(YEAR(c.fecha), MONTH(c.fecha), 1)
),
marcado AS (                 -- R4
    SELECT
        v.*,
        CASE WHEN v.unidades_abs >
                  25 * NULLIF(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v.unidades_abs)
                              OVER (PARTITION BY v.id_producto), 0)
             THEN 1 ELSE 0 END AS flag_revision
    FROM convertido v
)
INSERT INTO star.fact_ventas                                   -- R5
SELECT
    m.fecha,
    m.id_cliente,
    m.id_producto,
    m.id_filial,
    m.id_deposito,
    COALESCE(m.id_transportista, 99)          AS id_transportista,  -- 99 = 'No informado'
    o.id_tipo_oferta,
    m.tipo_documento,
    SUM(m.unidades_abs)                       AS unidades,
    SUM(m.importe_usd)                        AS importe_usd,
    SUM(m.costo_usd)                          AS costo_usd,
    SUM(m.importe_local_abs)                  AS importe_local,
    COUNT(*)                                  AS lineas,
    SUM(CAST(m.otif AS INT))                  AS lineas_otif,
    SUM(CAST(m.entrega_completa AS INT))      AS lineas_completas,
    SUM(m.lead_time_dias)                     AS lead_time_dias_x_linea,
    SUM(m.unidades_devueltas)                 AS unidades_devueltas,
    SUM(m.importe_devuelto_usd)               AS importe_devuelto_usd,
    SUM(CAST(m.devuelta AS INT))              AS lineas_devueltas,
    SUM(m.flag_revision)                      AS lineas_en_revision,
    SUM(CAST(m.dias_a_vencer AS BIGINT))      AS dias_a_vencer_x_linea
FROM marcado m
LEFT JOIN star.dim_tipo_oferta o ON o.cod_tipo_oferta = COALESCE(m.tipo_oferta, 'SIN')
GROUP BY
    m.fecha, m.id_cliente, m.id_producto, m.id_filial, m.id_deposito,
    COALESCE(m.id_transportista, 99), o.id_tipo_oferta, m.tipo_documento;
GO

/* -------------------------------------------------------------------------
   4 · Devoluciones — hecho separado porque tiene su propia dimensión (motivo)
   Meter el motivo en fact_ventas obligaría a repetir la venta por motivo y
   rompería la aditividad de las unidades vendidas.
   ------------------------------------------------------------------------- */
INSERT INTO star.fact_devoluciones
SELECT
    s.fecha, s.id_cliente, s.id_producto, s.id_filial,
    COALESCE(s.id_transportista, 99),
    md.id_motivo,
    SUM(s.unidades_devueltas),
    SUM(ABS(s.importe_devuelto_local) / tc.tc_a_usd),
    COUNT(*)
FROM stg.sellin s
JOIN star.dim_filial f ON f.id_filial = s.id_filial
JOIN star.fact_tipo_cambio tc
  ON tc.moneda = f.moneda AND tc.fecha = DATEFROMPARTS(YEAR(s.fecha), MONTH(s.fecha), 1)
JOIN star.dim_motivo_devolucion md ON md.cod_motivo = s.motivo_devolucion
WHERE s.devuelta = 1
GROUP BY s.fecha, s.id_cliente, s.id_producto, s.id_filial,
         COALESCE(s.id_transportista, 99), md.id_motivo;
GO

/* -------------------------------------------------------------------------
   5 · Sell-out del panel
   Se carga tal cual llega. La completitud (filial-mes faltante) se controla
   en 03_calidad_datos.sql y se muestra en el tablero como "sin dato",
   NUNCA como cero: un cero dice "no vendió", un blanco dice "no reportó",
   y confundirlos arruina cualquier análisis de share.
   ------------------------------------------------------------------------- */
INSERT INTO star.fact_sellout
SELECT fecha_mes AS fecha, id_filial, id_producto,
       unidades_sellout, importe_sellout, unidades_mercado, importe_mercado
FROM stg.sellout;
GO
