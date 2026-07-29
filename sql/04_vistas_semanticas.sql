/* =========================================================================
   ADIUM PHARMA — 04 · Vistas semánticas para Power BI

   Power BI se conecta a ESTAS vistas, no a las tablas.

   Por qué esa capa intermedia, que parece un rodeo:
     · aísla el modelo semántico de cambios físicos (renombrar una columna
       o particionar una tabla no rompe el .pbix)
     · permite versionar el contrato: si cambia una definición, se ve en el
       diff del repositorio y hay que aprobarlo
     · fuerza a que los nombres que ve el negocio sean los del negocio,
       no los del sistema origen
     · deja el query folding intacto: son vistas simples, no lógica pesada,
       así que Power Query las empuja al motor SQL sin romper el plegado

   Nombres en español y sin prefijos técnicos: el usuario final no tiene
   por qué saber qué es un `id_` ni un `fact_`.
   ========================================================================= */

/* -------------------------------------------------------------------------
   DIMENSIONES
   ------------------------------------------------------------------------- */

CREATE OR ALTER VIEW star.v_dim_calendario AS
SELECT
    fecha                   AS [Fecha],
    anio                    AS [Año],
    mes_nro                 AS [Mes N°],
    mes_nombre              AS [Mes],
    anio_mes                AS [Año-Mes],
    anio_mes_orden          AS [Año-Mes orden],     -- Sort by column de [Año-Mes]
    trimestre               AS [Trimestre],
    anio_trimestre          AS [Año-Trimestre],
    CAST(es_habil AS BIT)   AS [Es día hábil],
    CAST(es_pasado AS BIT)  AS [Es pasado],
    CAST(temporada_respiratoria AS BIT) AS [Temporada respiratoria]
FROM star.dim_calendario;
GO

CREATE OR ALTER VIEW star.v_dim_producto AS
SELECT
    id_producto             AS [Id producto],
    sku                     AS [SKU],
    marca                   AS [Marca],
    atc1                    AS [ATC1],
    atc1_desc               AS [Clase terapéutica],
    atc3                    AS [ATC3],
    forma_farmaceutica      AS [Forma farmacéutica],
    presentacion            AS [Presentación],
    tipo_venta              AS [Tipo de venta],
    CASE WHEN cadena_frio = 1 THEN 'Cadena de frío' ELSE 'Temperatura ambiente' END
                            AS [Condición de conservación],
    ciclo_vida              AS [Ciclo de vida],
    vida_util_meses         AS [Vida útil (meses)],
    precio_lista_usd        AS [Precio de lista USD],
    costo_std_usd           AS [Costo estándar USD],
    margen_std_pct          AS [Margen estándar %],
    -- Trazabilidad del dato: el tablero muestra qué SKU tienen costo imputado.
    -- Un margen calculado sobre un costo imputado no es un margen: es una
    -- estimación, y el usuario tiene derecho a saberlo.
    CASE WHEN costo_imputado = 1 THEN 'Costo imputado' ELSE 'Costo real' END
                            AS [Origen del costo]
FROM star.dim_producto;
GO

CREATE OR ALTER VIEW star.v_dim_cliente AS
SELECT
    c.id_cliente        AS [Id cliente],
    c.cod_cliente       AS [Código cliente],
    c.razon_social      AS [Cliente],
    c.canal             AS [Canal],
    c.segmento          AS [Segmento],
    c.antiguedad_meses  AS [Antigüedad (meses)],
    r.nombre_rep        AS [Representante],
    r.supervisor        AS [Supervisor],
    r.linea_promocion   AS [Línea de promoción]
FROM star.dim_cliente c
LEFT JOIN star.dim_representante r ON r.id_representante = c.id_representante;
GO

CREATE OR ALTER VIEW star.v_dim_filial AS
SELECT
    id_filial        AS [Id filial],
    cod_filial       AS [Filial],
    pais             AS [País],
    region           AS [Región],
    moneda           AS [Moneda local],
    sla_entrega_dias AS [SLA entrega (días)]
FROM star.dim_filial;
GO

CREATE OR ALTER VIEW star.v_dim_logistica AS
SELECT
    d.id_deposito                AS [Id depósito],
    d.nombre_deposito            AS [Depósito],
    d.id_filial                  AS [Id filial],
    CASE WHEN d.tiene_camara_frio = 1 THEN 'Con cámara de frío' ELSE 'Sin cámara de frío' END
                                 AS [Capacidad de frío],
    d.capacidad_pallets          AS [Capacidad (pallets)]
FROM star.dim_deposito d;
GO

CREATE OR ALTER VIEW star.v_dim_transportista AS
SELECT
    id_transportista AS [Id transportista],
    transportista    AS [Transportista],
    confiabilidad    AS [Confiabilidad histórica],
    CASE WHEN control_frio = 1 THEN 'Con control de frío' ELSE 'Sin control de frío' END
                     AS [Control de temperatura]
FROM star.dim_transportista;
GO

CREATE OR ALTER VIEW star.v_dim_motivo_devolucion AS
SELECT
    id_motivo        AS [Id motivo],
    cod_motivo       AS [Código motivo],
    motivo           AS [Motivo de devolución],
    area_responsable AS [Área responsable],
    CASE WHEN es_evitable = 1 THEN 'Evitable' ELSE 'No evitable' END AS [Evitabilidad]
FROM star.dim_motivo_devolucion;
GO

CREATE OR ALTER VIEW star.v_dim_tipo_oferta AS
SELECT
    id_tipo_oferta   AS [Id tipo oferta],
    cod_tipo_oferta  AS [Código],
    tipo_oferta_desc AS [Tipo de oferta],
    costo_relativo   AS [Costo relativo]
FROM star.dim_tipo_oferta;
GO

/* -------------------------------------------------------------------------
   HECHOS

   Regla: la vista de un hecho NO agrega ni calcula ratios. Solo renombra y
   expone columnas aditivas. Todo lo que sea división (share, tasa, promedio
   ponderado) se calcula en DAX, en el contexto de filtro del visual.

   Si el ratio se calcula acá, se promedia mal en cuanto el usuario cambia de
   nivel de agregación. Es el error más común y el más difícil de detectar,
   porque el número "parece" razonable.
   ------------------------------------------------------------------------- */

CREATE OR ALTER VIEW star.v_fact_ventas AS
SELECT
    fecha                   AS [Fecha],
    id_cliente              AS [Id cliente],
    id_producto             AS [Id producto],
    id_filial               AS [Id filial],
    id_deposito             AS [Id depósito],
    id_transportista        AS [Id transportista],
    id_tipo_oferta          AS [Id tipo oferta],
    tipo_documento          AS [Tipo documento],
    -- Signo del documento: la nota de crédito resta. Guardarlo como columna
    -- y no como filtro en la medida permite que TODA medida use el mismo
    -- criterio sin repetir lógica.
    CASE WHEN tipo_documento = 'NC' THEN -1 ELSE 1 END AS [Signo],
    unidades                AS [Unidades],
    importe_usd             AS [Importe USD],
    costo_usd               AS [Costo USD],
    importe_local           AS [Importe moneda local],
    lineas                  AS [Líneas],
    lineas_otif             AS [Líneas OTIF],
    lineas_completas        AS [Líneas completas],
    lead_time_dias_x_linea  AS [Lead time x línea],
    unidades_devueltas      AS [Unidades devueltas],
    importe_devuelto_usd    AS [Importe devuelto USD],
    lineas_devueltas        AS [Líneas devueltas],
    lineas_en_revision      AS [Líneas en revisión],
    dias_a_vencer_x_linea   AS [Días a vencer x línea]
FROM star.fact_ventas;
GO

CREATE OR ALTER VIEW star.v_fact_devoluciones AS
SELECT
    fecha                AS [Fecha],
    id_cliente           AS [Id cliente],
    id_producto          AS [Id producto],
    id_filial            AS [Id filial],
    id_transportista     AS [Id transportista],
    id_motivo            AS [Id motivo],
    unidades_devueltas   AS [Unidades devueltas],
    importe_devuelto_usd AS [Importe devuelto USD],
    lineas               AS [Líneas devueltas]
FROM star.fact_devoluciones;
GO

CREATE OR ALTER VIEW star.v_fact_ofertas AS
SELECT
    fecha                  AS [Fecha],
    id_cliente             AS [Id cliente],
    id_producto            AS [Id producto],
    id_filial              AS [Id filial],
    id_tipo_oferta         AS [Id tipo oferta],
    descuento_pct          AS [Descuento %],
    unidades_ofertadas     AS [Unidades ofertadas],
    cobertura_cliente_dias AS [Cobertura del cliente (días)],
    CAST(aceptada AS INT)  AS [Aceptada],
    1                      AS [Ofertas]
FROM star.fact_ofertas;
GO

CREATE OR ALTER VIEW star.v_fact_sellout AS
SELECT
    fecha_mes        AS [Fecha],
    id_filial        AS [Id filial],
    id_producto      AS [Id producto],
    unidades_sellout AS [Unidades sell-out],
    importe_sellout  AS [Importe sell-out USD],
    unidades_mercado AS [Unidades mercado],
    importe_mercado  AS [Importe mercado USD]
FROM star.fact_sellout;
GO

CREATE OR ALTER VIEW star.v_fact_objetivos AS
SELECT
    fecha                AS [Fecha],
    id_filial            AS [Id filial],
    id_producto          AS [Id producto],
    objetivo_importe_usd AS [Objetivo USD],
    objetivo_unidades    AS [Objetivo unidades]
FROM star.fact_objetivos;
GO

CREATE OR ALTER VIEW star.v_fact_stock AS
SELECT
    s.fecha                    AS [Fecha],
    s.id_deposito              AS [Id depósito],
    s.id_producto              AS [Id producto],
    s.stock_unidades           AS [Stock unidades],
    s.valor_stock_usd          AS [Valor de stock USD],
    s.stock_en_transito        AS [Stock en tránsito],
    s.unidades_por_vencer_180d AS [Unidades por vencer 180d],
    s.dias_a_vencer_promedio   AS [Días a vencer promedio],
    -- Numerador del promedio ponderado de cobertura. Se expone el numerador,
    -- no el promedio ya calculado: promediar promedios da mal en cuanto se
    -- cambia el nivel de agregación.
    s.dias_cobertura * s.stock_unidades AS [Cobertura x stock],
    s.unidades_mes             AS [Consumo del mes]
FROM star.fact_stock s;
GO

CREATE OR ALTER VIEW star.v_fact_recomendaciones AS
SELECT
    mes_objetivo               AS [Mes objetivo],
    id_filial                  AS [Id filial],
    id_producto                AS [Id producto],
    canal                      AS [Canal],
    segmento                   AS [Segmento],
    rank_segmento              AS [Ranking en el segmento],
    descuento_pct              AS [Descuento recomendado],
    precio_neto                AS [Precio neto recomendado],
    margen_unitario            AS [Margen unitario USD],
    elasticidad                AS [Elasticidad estimada],
    nivel_estimacion           AS [Nivel de estimación],
    indice_estacional          AS [Índice estacional],
    aporte_margen_pct          AS [Aporte al margen de la filial],
    dias_cobertura             AS [Días de cobertura],
    unidades_por_vencer        AS [Unidades por vencer],
    demanda_esperada           AS [Demanda esperada],
    prob_aceptacion            AS [Probabilidad de aceptación],
    riesgo_devolucion          AS [Riesgo de devolución],
    margen_esperado_usd        AS [Margen esperado USD],
    valor_rescate_usd          AS [Valor de stock rescatado USD],
    ganancia_vs_sin_oferta_usd AS [Ganancia vs no ofertar USD],
    CASE WHEN en_borde_de_soporte = 1
         THEN 'Requiere test controlado' ELSE 'Dentro de evidencia histórica' END
                               AS [Confianza de la recomendación],
    justificativo              AS [Justificativo]
FROM star.fact_recomendaciones;
GO

CREATE OR ALTER VIEW star.v_fact_scoring_devoluciones AS
SELECT
    fecha                 AS [Fecha],
    id_cliente            AS [Id cliente],
    id_producto           AS [Id producto],
    id_filial             AS [Id filial],
    id_transportista      AS [Id transportista],
    unidades              AS [Unidades],
    importe_usd           AS [Importe USD],
    CAST(devuelta AS INT) AS [Devuelta real],
    prob_devolucion       AS [Probabilidad de devolución],
    banda_riesgo          AS [Banda de riesgo],
    importe_en_riesgo_usd AS [Importe en riesgo USD]
FROM star.fact_scoring_devoluciones;
GO

/* -------------------------------------------------------------------------
   Vista de servicio: estado de calidad para el encabezado de los tableros.
   Una sola fila, barata de consultar, que alimenta el semáforo y la marca
   de última actualización.
   ------------------------------------------------------------------------- */
CREATE OR ALTER VIEW star.v_estado_datos AS
SELECT
    (SELECT MAX(fecha) FROM star.fact_ventas)                    AS [Último dato],
    (SELECT COUNT(*) FROM dq.control_resultado
      WHERE id_ejecucion = (SELECT MAX(id_ejecucion) FROM dq.control_resultado)
        AND estado = 'CRÍTICO')                                  AS [Controles críticos],
    (SELECT COUNT(*) FROM dq.control_resultado
      WHERE id_ejecucion = (SELECT MAX(id_ejecucion) FROM dq.control_resultado)
        AND estado = 'ALERTA')                                   AS [Controles en alerta],
    (SELECT MAX(fecha_ejecucion) FROM dq.control_resultado)      AS [Última validación];
GO
