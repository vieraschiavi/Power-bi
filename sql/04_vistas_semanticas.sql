-- © 2026 Martín Viera. Todos los derechos reservados.

/* =========================================================================
   FARMA DEMO — 04 · Vistas semánticas para Power BI

   ARCHIVO GENERADO. No editar a mano.
   Se produce con:  python powerbi/generar_sql_vistas.py
   desde el contrato único de powerbi/esquema.py.

   Power BI se conecta a ESTAS vistas, no a las tablas.

   Por qué esa capa intermedia, que parece un rodeo:
     · aísla el modelo semántico de cambios físicos (renombrar una columna o
       particionar una tabla no rompe el reporte)
     · versiona el contrato: si cambia una definición, se ve en el diff del
       repositorio y hay que aprobarlo
     · fuerza a que los nombres que ve el negocio sean los del negocio
     · deja el query folding intacto: son vistas simples, sin lógica pesada,
       así que Power Query las empuja al motor SQL sin romper el plegado

   Los nombres de columna de estas vistas son EXACTAMENTE los que espera el
   modelo semántico. Esa correspondencia es lo que permite que el archivo de
   Power BI conmute entre origen Parquet y origen SQL Server con un parámetro,
   sin tocar una sola medida DAX.

   REGLA: una vista de hecho no agrega ni calcula ratios. Solo renombra y
   expone columnas aditivas. Todo lo que sea división (share, tasa, promedio
   ponderado) se calcula en DAX, en el contexto de filtro del visual. Un ratio
   materializado acá se promedia mal en cuanto el usuario cambia de nivel de
   agregación — es el error más común y el más difícil de detectar, porque el
   número "parece" razonable.
   ========================================================================= */


/* -----------------------------------------------------------------------
   DIMENSIONES
   ----------------------------------------------------------------------- */

CREATE OR ALTER VIEW star.v_dim_calendario AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.anio                                                         AS [Año],
    t.mes_nro                                                      AS [Mes N°],
    t.mes_nombre                                                   AS [Mes],
    t.anio_mes                                                     AS [Año-Mes],
    t.anio_mes_orden                                               AS [Año-Mes orden],
    t.trimestre                                                    AS [Trimestre],
    t.anio_trimestre                                               AS [Año-Trimestre],
    t.es_habil                                                     AS [Es día hábil],
    t.es_pasado                                                    AS [Es pasado],
    t.temporada_respiratoria                                       AS [Temporada respiratoria]
FROM star.dim_calendario AS t
GO

CREATE OR ALTER VIEW star.v_dim_producto AS
SELECT
    t.id_producto                                                  AS [Id producto],
    t.sku                                                          AS [SKU],
    t.marca                                                        AS [Marca],
    t.atc1                                                         AS [ATC1],
    t.atc1_desc                                                    AS [Clase terapéutica],
    t.atc3                                                         AS [ATC3],
    t.forma_farmaceutica                                           AS [Forma farmacéutica],
    t.presentacion                                                 AS [Presentación],
    t.tipo_venta                                                   AS [Tipo de venta],
    t.ciclo_vida                                                   AS [Ciclo de vida],
    t.vida_util_meses                                              AS [Vida útil (meses)],
    t.precio_lista_usd                                             AS [Precio de lista USD],
    t.costo_std_usd                                                AS [Costo estándar USD],
    t.margen_std_pct                                               AS [Margen estándar %],
    CASE WHEN cadena_frio = 1 THEN 'Cadena de frío' ELSE 'Temperatura ambiente' END AS [Condición de conservación],
    CASE WHEN costo_imputado = 1 THEN 'Costo imputado' ELSE 'Costo real' END AS [Origen del costo]
FROM star.dim_producto AS t
GO

CREATE OR ALTER VIEW star.v_dim_cliente AS
SELECT
    t.id_cliente                                                   AS [Id cliente],
    t.id_filial                                                    AS [Id filial cliente],
    t.cod_cliente                                                  AS [Código cliente],
    t.razon_social                                                 AS [Cliente],
    t.canal                                                        AS [Canal],
    t.segmento                                                     AS [Segmento],
    t.antiguedad_meses                                             AS [Antigüedad (meses)],
    sat.nombre_rep                                                 AS [Representante],
    sat.supervisor                                                 AS [Supervisor],
    sat.linea_promocion                                            AS [Línea de promoción]
FROM star.dim_cliente AS t
LEFT JOIN star.dim_representante AS sat ON sat.id_representante = t.id_representante
GO

CREATE OR ALTER VIEW star.v_dim_filial AS
SELECT
    t.id_filial                                                    AS [Id filial],
    t.cod_filial                                                   AS [Filial],
    t.pais                                                         AS [País],
    t.region                                                       AS [Región],
    t.moneda                                                       AS [Moneda local],
    t.sla_entrega_dias                                             AS [SLA entrega (días)]
FROM star.dim_filial AS t
GO

CREATE OR ALTER VIEW star.v_dim_deposito AS
SELECT
    t.id_deposito                                                  AS [Id depósito],
    t.nombre_deposito                                              AS [Depósito],
    t.id_filial                                                    AS [Id filial depósito],
    t.capacidad_pallets                                            AS [Capacidad (pallets)],
    CASE WHEN tiene_camara_frio = 1 THEN 'Con cámara de frío' ELSE 'Sin cámara de frío' END AS [Capacidad de frío]
FROM star.dim_deposito AS t
GO

CREATE OR ALTER VIEW star.v_dim_transportista AS
SELECT
    t.id_transportista                                             AS [Id transportista],
    t.transportista                                                AS [Transportista],
    t.confiabilidad                                                AS [Confiabilidad histórica],
    CASE WHEN control_frio = 1 THEN 'Con control de frío' ELSE 'Sin control de frío' END AS [Control de temperatura]
FROM star.dim_transportista AS t
GO

CREATE OR ALTER VIEW star.v_dim_motivo_devolucion AS
SELECT
    t.id_motivo                                                    AS [Id motivo],
    t.cod_motivo                                                   AS [Código motivo],
    t.motivo                                                       AS [Motivo de devolución],
    t.area_responsable                                             AS [Área responsable],
    CASE WHEN es_evitable = 1 THEN 'Evitable' ELSE 'No evitable' END AS [Evitabilidad]
FROM star.dim_motivo_devolucion AS t
GO

CREATE OR ALTER VIEW star.v_dim_tipo_oferta AS
SELECT
    t.id_tipo_oferta                                               AS [Id tipo oferta],
    t.cod_tipo_oferta                                              AS [Código],
    t.tipo_oferta_desc                                             AS [Tipo de oferta],
    t.costo_relativo                                               AS [Costo relativo]
FROM star.dim_tipo_oferta AS t
GO


/* -----------------------------------------------------------------------
   HECHOS
   ----------------------------------------------------------------------- */

CREATE OR ALTER VIEW star.v_fact_ventas AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_cliente                                                   AS [Id cliente],
    t.id_producto                                                  AS [Id producto],
    t.id_filial                                                    AS [Id filial],
    t.id_deposito                                                  AS [Id depósito],
    t.id_transportista                                             AS [Id transportista],
    t.id_tipo_oferta                                               AS [Id tipo oferta],
    t.tipo_documento                                               AS [Tipo documento],
    t.unidades                                                     AS [Unidades],
    t.importe_usd                                                  AS [Importe USD],
    t.costo_usd                                                    AS [Costo USD],
    t.importe_local                                                AS [Importe moneda local],
    t.lineas                                                       AS [Líneas],
    t.lineas_otif                                                  AS [Líneas OTIF],
    t.lineas_completas                                             AS [Líneas completas],
    t.lead_time_dias_x_linea                                       AS [Lead time x línea],
    t.unidades_devueltas                                           AS [Unidades devueltas],
    t.importe_devuelto_usd                                         AS [Importe devuelto USD],
    t.lineas_devueltas                                             AS [Líneas devueltas],
    t.lineas_en_revision                                           AS [Líneas en revisión],
    t.dias_a_vencer_x_linea                                        AS [Días a vencer x línea],
    CASE WHEN tipo_documento = 'NC' THEN -1 ELSE 1 END             AS [Signo]
FROM star.fact_ventas AS t
GO

CREATE OR ALTER VIEW star.v_fact_devoluciones AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_cliente                                                   AS [Id cliente],
    t.id_producto                                                  AS [Id producto],
    t.id_filial                                                    AS [Id filial],
    t.id_transportista                                             AS [Id transportista],
    t.id_motivo                                                    AS [Id motivo],
    t.unidades_devueltas                                           AS [Unidades devueltas],
    t.importe_devuelto_usd                                         AS [Importe devuelto USD],
    t.lineas                                                       AS [Líneas devueltas]
FROM star.fact_devoluciones AS t
GO

CREATE OR ALTER VIEW star.v_fact_ofertas AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_cliente                                                   AS [Id cliente],
    t.id_producto                                                  AS [Id producto],
    t.id_filial                                                    AS [Id filial],
    t.id_tipo_oferta                                               AS [Id tipo oferta],
    t.descuento_pct                                                AS [Descuento %],
    t.unidades_ofertadas                                           AS [Unidades ofertadas],
    t.cobertura_cliente_dias                                       AS [Cobertura del cliente (días)],
    t.aceptada                                                     AS [Aceptada],
    1                                                              AS [Ofertas]
FROM star.fact_ofertas AS t
GO

CREATE OR ALTER VIEW star.v_fact_sellout AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_filial                                                    AS [Id filial],
    t.id_producto                                                  AS [Id producto],
    t.unidades_sellout                                             AS [Unidades sell-out],
    t.importe_sellout                                              AS [Importe sell-out USD],
    t.unidades_mercado                                             AS [Unidades mercado],
    t.importe_mercado                                              AS [Importe mercado USD]
FROM star.fact_sellout AS t
GO

CREATE OR ALTER VIEW star.v_fact_objetivos AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_filial                                                    AS [Id filial],
    t.id_producto                                                  AS [Id producto],
    t.objetivo_importe_usd                                         AS [Objetivo USD],
    t.objetivo_unidades                                            AS [Objetivo unidades]
FROM star.fact_objetivos AS t
GO

CREATE OR ALTER VIEW star.v_fact_stock AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_deposito                                                  AS [Id depósito],
    t.id_producto                                                  AS [Id producto],
    t.stock_unidades                                               AS [Stock unidades],
    t.valor_stock_usd                                              AS [Valor de stock USD],
    t.stock_en_transito                                            AS [Stock en tránsito],
    t.unidades_por_vencer_180d                                     AS [Unidades por vencer 180d],
    t.dias_a_vencer_promedio                                       AS [Días a vencer promedio],
    t.unidades_mes                                                 AS [Consumo del mes],
    dias_cobertura * stock_unidades                                AS [Cobertura x stock]
FROM star.fact_stock AS t
GO

CREATE OR ALTER VIEW star.v_fact_scoring_devoluciones AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_cliente                                                   AS [Id cliente],
    t.id_producto                                                  AS [Id producto],
    t.id_filial                                                    AS [Id filial],
    t.id_transportista                                             AS [Id transportista],
    t.unidades                                                     AS [Unidades],
    t.importe_usd                                                  AS [Importe USD],
    t.devuelta                                                     AS [Devuelta real],
    t.prob_devolucion                                              AS [Probabilidad de devolución],
    t.banda_riesgo                                                 AS [Banda de riesgo],
    t.importe_en_riesgo_usd                                        AS [Importe en riesgo USD]
FROM star.fact_scoring_devoluciones AS t
GO

CREATE OR ALTER VIEW star.v_fact_recomendaciones AS
SELECT
    t.mes_objetivo                                                 AS [Mes objetivo],
    t.id_filial                                                    AS [Id filial],
    t.id_producto                                                  AS [Id producto],
    t.canal                                                        AS [Canal recomendado],
    t.segmento                                                     AS [Segmento recomendado],
    t.rank_segmento                                                AS [Ranking en el segmento],
    t.sku                                                          AS [SKU recomendado],
    t.marca                                                        AS [Marca recomendada],
    t.descuento_pct                                                AS [Descuento recomendado],
    t.precio_neto                                                  AS [Precio neto recomendado],
    t.margen_unitario                                              AS [Margen unitario USD],
    t.elasticidad                                                  AS [Elasticidad estimada],
    t.nivel_estimacion                                             AS [Nivel de estimación],
    t.indice_estacional                                            AS [Índice estacional],
    t.aporte_margen_pct                                            AS [Aporte al margen de la filial],
    t.dias_cobertura                                               AS [Días de cobertura],
    t.unidades_por_vencer                                          AS [Unidades por vencer],
    t.demanda_esperada                                             AS [Demanda esperada],
    t.prob_aceptacion                                              AS [Probabilidad de aceptación],
    t.riesgo_devolucion                                            AS [Riesgo de devolución],
    t.margen_esperado_usd                                          AS [Margen esperado USD],
    t.valor_rescate_usd                                            AS [Valor de stock rescatado USD],
    t.ganancia_vs_sin_oferta_usd                                   AS [Ganancia vs no ofertar USD],
    t.justificativo                                                AS [Justificativo],
    CASE WHEN en_borde_de_soporte = 1 THEN 'Requiere test controlado' ELSE 'Dentro de evidencia histórica' END AS [Confianza de la recomendación]
FROM star.fact_recomendaciones AS t
GO

CREATE OR ALTER VIEW star.v_forecast_devoluciones AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_filial                                                    AS [Id filial],
    t.tasa_dev_valor                                               AS [Tasa dev real],
    t.tasa_dev_proyectada                                          AS [Tasa dev proyectada],
    t.importe_dev                                                  AS [Importe dev real],
    t.importe_dev_proyectado                                       AS [Importe dev proyectado],
    t.es_holdout                                                   AS [Es holdout]
FROM star.fact_forecast_devoluciones AS t
GO

CREATE OR ALTER VIEW star.v_forecast_ofertas AS
SELECT
    t.fecha                                                        AS [Fecha],
    t.id_filial                                                    AS [Id filial],
    t.inversion_usd                                                AS [Inversión USD],
    t.inversion_proyectada_usd                                     AS [Inversión proyectada USD],
    t.ofertas                                                      AS [Ofertas del mes],
    t.aceptadas                                                    AS [Aceptadas del mes],
    t.es_holdout                                                   AS [Es holdout]
FROM star.fact_forecast_ofertas AS t
GO


/* -----------------------------------------------------------------------
   SERVICIO
   ----------------------------------------------------------------------- */

CREATE OR ALTER VIEW star.v_estado_datos AS
SELECT
    t.ultimo_dato                                                  AS [Último dato],
    t.controles_criticos                                           AS [Controles críticos],
    t.controles_alerta                                             AS [Controles en alerta],
    t.controles_ok                                                 AS [Controles OK],
    t.ultima_validacion                                            AS [Última validación]
FROM star.fact_estado_datos AS t
GO
