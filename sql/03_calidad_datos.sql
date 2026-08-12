/* =========================================================================
   FARMA DEMO — 03 · Controles de calidad de datos (Data Steward)

   Las 6 dimensiones canónicas: completitud, exactitud, consistencia,
   unicidad, vigencia, validez.

   Principio de diseño: los controles corren SOLOS y dejan evidencia en una
   tabla. No dependen de que alguien se acuerde de mirar. Y el resultado se
   publica EN EL PROPIO TABLERO — cuando el negocio ve el estado del dato,
   empieza a cuidarlo.

   Los controles con severidad 'alta' bloquean la publicación. El resto
   alertan. Esa distinción es la que evita que "todo esté siempre en rojo"
   y el semáforo deje de significar algo.
   ========================================================================= */

SET NOCOUNT ON;
GO

IF OBJECT_ID('dq.control_resultado') IS NULL
CREATE TABLE dq.control_resultado (
    id_ejecucion     INT           NOT NULL,
    fecha_ejecucion  DATETIME2(0)  NOT NULL DEFAULT SYSUTCDATETIME(),
    dimension        VARCHAR(20)   NOT NULL,
    control          VARCHAR(120)  NOT NULL,
    tabla            VARCHAR(60)   NOT NULL,
    filas_afectadas  BIGINT        NOT NULL,
    filas_totales    BIGINT        NOT NULL,
    pct_afectado     DECIMAL(9,4)  NOT NULL,
    severidad        VARCHAR(10)   NOT NULL,
    accion           VARCHAR(200)  NOT NULL,
    estado           AS (CASE WHEN filas_afectadas = 0 THEN 'OK'
                             WHEN severidad = 'alta'   THEN 'CRÍTICO'
                             ELSE 'ALERTA' END) PERSISTED
);
GO

CREATE OR ALTER PROCEDURE dq.usp_ejecutar_controles
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @eje INT = ISNULL((SELECT MAX(id_ejecucion) FROM dq.control_resultado), 0) + 1;

    /* --- COMPLETITUD ------------------------------------------------- */

    -- ¿Alguna filial no reportó algún mes en el panel de auditoría?
    -- Es EL control del rol: si una filial no cargó, el share corporativo
    -- está mal y nadie se entera hasta el comité.
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Completitud',
           'Filial-mes sin carga del panel de auditoría', 'fact_sellout',
           COUNT(*), NULLIF(esperado.total, 0),
           100.0 * COUNT(*) / NULLIF(esperado.total, 0), 'alta',
           'Mostrar el mes como SIN DATO en el tablero, nunca como cero'
    FROM (
        SELECT c.anio_mes, f.id_filial
        FROM (SELECT DISTINCT anio_mes FROM star.dim_calendario) c
        CROSS JOIN star.dim_filial f
        EXCEPT
        SELECT FORMAT(fecha_mes,'yyyy-MM'), id_filial FROM star.fact_sellout
    ) faltan
    CROSS JOIN (
        SELECT total = COUNT(DISTINCT c.anio_mes) * COUNT(DISTINCT f.id_filial)
        FROM star.dim_calendario c CROSS JOIN star.dim_filial f
    ) esperado
    GROUP BY esperado.total;

    -- Costo estándar sin cargar (se imputó, pero hay que reportarlo)
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Completitud', 'SKU con costo estándar imputado', 'dim_producto',
           SUM(CAST(costo_imputado AS INT)), COUNT(*),
           100.0 * SUM(CAST(costo_imputado AS INT)) / COUNT(*), 'alta',
           'Pedir el costo real a Finanzas; el margen de esos SKU no es confiable'
    FROM star.dim_producto;

    /* --- UNICIDAD ---------------------------------------------------- */

    -- El control clásico: contar filas antes y después de cada join.
    -- Si el hecho tiene más filas que combinaciones únicas de su clave,
    -- hay un join que duplicó.
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Unicidad', 'Grano del hecho violado (filas duplicadas)', 'fact_ventas',
           COUNT(*) - COUNT(DISTINCT CONCAT_WS('|', fecha, id_cliente, id_producto,
                                               id_deposito, id_transportista,
                                               id_tipo_oferta, tipo_documento)),
           COUNT(*),
           100.0 * (COUNT(*) - COUNT(DISTINCT CONCAT_WS('|', fecha, id_cliente, id_producto,
                                               id_deposito, id_transportista,
                                               id_tipo_oferta, tipo_documento))) / COUNT(*),
           'alta', 'Revisar el GROUP BY del ETL: el grano declarado no se cumple'
    FROM star.fact_ventas;

    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Unicidad', 'Código de cliente duplicado', 'dim_cliente',
           COUNT(*) - COUNT(DISTINCT cod_cliente), COUNT(*),
           100.0 * (COUNT(*) - COUNT(DISTINCT cod_cliente)) / COUNT(*), 'alta',
           'La clave de negocio debe ser única; bloquear la carga'
    FROM star.dim_cliente;

    /* --- CONSISTENCIA ------------------------------------------------ */

    -- Integridad referencial: hechos sin dimensión.
    -- En Power BI estas filas se agrupan en una fila EN BLANCO y el total
    -- deja de cuadrar con el detalle. Es la causa nº1 de "el total no da".
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Consistencia', 'Ventas con SKU inexistente en el maestro', 'fact_ventas',
           SUM(CASE WHEN p.id_producto IS NULL THEN 1 ELSE 0 END), COUNT(*),
           100.0 * SUM(CASE WHEN p.id_producto IS NULL THEN 1 ELSE 0 END) / COUNT(*),
           'alta', 'Dar de alta el SKU antes de publicar; si no, aparece fila en blanco'
    FROM star.fact_ventas v
    LEFT JOIN star.dim_producto p ON p.id_producto = v.id_producto;

    -- Cobertura de tipo de cambio: sin FX no hay cifra corporativa.
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Consistencia', 'Filial-mes sin tipo de cambio cargado', 'fact_tipo_cambio',
           COUNT(*), (SELECT COUNT(DISTINCT anio_mes) FROM star.dim_calendario)
                     * (SELECT COUNT(DISTINCT moneda) FROM star.dim_filial),
           0, 'alta', 'Bloquea la conversión a USD: no se publica el consolidado'
    FROM (
        SELECT DISTINCT c.anio_mes, f.moneda
        FROM star.dim_calendario c CROSS JOIN star.dim_filial f
        EXCEPT
        SELECT FORMAT(fecha,'yyyy-MM'), moneda FROM star.fact_tipo_cambio
    ) x;

    /* --- VALIDEZ ----------------------------------------------------- */

    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Validez', 'Líneas con margen bruto negativo', 'fact_ventas',
           SUM(CASE WHEN importe_usd < costo_usd THEN 1 ELSE 0 END), COUNT(*),
           100.0 * SUM(CASE WHEN importe_usd < costo_usd THEN 1 ELSE 0 END) / COUNT(*),
           'media', 'Puede ser legítimo (liquidación) o un costo mal cargado: revisar caso a caso';

    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Validez', 'Devolución mayor a la venta de la misma línea', 'fact_ventas',
           SUM(CASE WHEN unidades_devueltas > unidades THEN 1 ELSE 0 END), COUNT(*),
           100.0 * SUM(CASE WHEN unidades_devueltas > unidades THEN 1 ELSE 0 END) / COUNT(*),
           'alta', 'Imposible por definición: hay un error de matcheo venta-devolución'
    FROM star.fact_ventas;

    /* --- EXACTITUD --------------------------------------------------- */

    -- Reconciliación contra la fuente. Este es el control que decide si se
    -- publica o no: si el modelo no cierra contra el origen, no sale.
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Exactitud', 'Diferencia vs origen en unidades (tolerancia 0)', 'fact_ventas',
           ABS(dw.u - st.u), st.u,
           CASE WHEN st.u = 0 THEN 0 ELSE 100.0 * ABS(dw.u - st.u) / st.u END,
           'alta', 'Si el modelo no reconcilia contra el origen, NO se publica'
    FROM (SELECT u = SUM(CAST(unidades AS BIGINT)) FROM star.fact_ventas) dw
    CROSS JOIN (SELECT u = SUM(CAST(ABS(unidades) AS BIGINT)) FROM stg.sellin
                WHERE fecha IS NOT NULL) st;

    -- Outliers marcados en el ETL (no corregidos: marcados)
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Exactitud', 'Líneas marcadas para revisión (>25x mediana del SKU)', 'fact_ventas',
           SUM(lineas_en_revision), SUM(lineas),
           100.0 * SUM(lineas_en_revision) / NULLIF(SUM(lineas), 0), 'media',
           'Confirmar con la filial antes de tomar el dato como bueno'
    FROM star.fact_ventas;

    /* --- VIGENCIA ---------------------------------------------------- */

    -- El dato más peligroso no es el que está mal: es el que está viejo y
    -- nadie lo sabe. Por eso la marca de última actualización va VISIBLE
    -- en el tablero, no escondida en un tooltip.
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Vigencia', 'Días de atraso del último dato cargado', 'fact_ventas',
           DATEDIFF(DAY, MAX(fecha), CAST(SYSUTCDATETIME() AS DATE)), 1, 0,
           CASE WHEN DATEDIFF(DAY, MAX(fecha), CAST(SYSUTCDATETIME() AS DATE)) > 5
                THEN 'alta' ELSE 'media' END,
           'SLA de carga: 5 días hábiles. Se muestra en el encabezado del tablero'
    FROM star.fact_ventas;

    -- Filiales que dejaron de cargar (el silencio también es un dato)
    INSERT INTO dq.control_resultado
        (id_ejecucion, dimension, control, tabla, filas_afectadas, filas_totales,
         pct_afectado, severidad, accion)
    SELECT @eje, 'Vigencia', 'Filiales sin movimientos en los últimos 35 días', 'fact_ventas',
           COUNT(*), (SELECT COUNT(*) FROM star.dim_filial),
           100.0 * COUNT(*) / (SELECT COUNT(*) FROM star.dim_filial), 'alta',
           'Contactar a la filial: puede ser un problema de carga, no de venta'
    FROM (
        SELECT v.id_filial
        FROM star.fact_ventas v
        GROUP BY v.id_filial
        HAVING DATEDIFF(DAY, MAX(v.fecha),
                        (SELECT MAX(fecha) FROM star.fact_ventas)) > 35
    ) x;

    SELECT dimension, control, tabla, filas_afectadas, pct_afectado, severidad, estado, accion
    FROM dq.control_resultado
    WHERE id_ejecucion = @eje
    ORDER BY CASE estado WHEN 'CRÍTICO' THEN 1 WHEN 'ALERTA' THEN 2 ELSE 3 END,
             dimension;
END
GO

/* -------------------------------------------------------------------------
   Compuerta de publicación.
   Si hay algún control CRÍTICO, el refresh del modelo semántico NO corre.
   Publicar un tablero que no reconcilia cuesta más que no publicarlo.
   ------------------------------------------------------------------------- */
CREATE OR ALTER FUNCTION dq.fn_puede_publicar (@id_ejecucion INT)
RETURNS BIT
AS
BEGIN
    RETURN CASE WHEN EXISTS (
        SELECT 1 FROM dq.control_resultado
        WHERE id_ejecucion = @id_ejecucion AND estado = 'CRÍTICO'
    ) THEN 0 ELSE 1 END;
END
GO
