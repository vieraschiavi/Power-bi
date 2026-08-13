-- © 2026 Martín Viera. Todos los derechos reservados.

/* =========================================================================
   FARMA DEMO — Excelencia Comercial Corporativo
   01 · DDL del modelo estrella (SQL Server / T-SQL)

   Un solo modelo estrella para los tres tableros (VAR, Ofertas, Logística).
   No son tres modelos: son tres reportes sobre un mismo bus dimensional.
   Eso es lo que hace que "unidades vendidas" signifique lo mismo en los tres.

   Convenciones:
     · dim_*   dimensiones conformadas, clave sustituta INT
     · fact_*  hechos, sin claves naturales de alta cardinalidad
     · todas las medidas monetarias en USD (moneda de reporte corporativa);
       el importe en moneda local se conserva para la conciliación con filial
   ========================================================================= */

IF SCHEMA_ID('star') IS NULL EXEC('CREATE SCHEMA star');
IF SCHEMA_ID('stg')  IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('dq')   IS NULL EXEC('CREATE SCHEMA dq');
GO

/* -------------------------------------------------------------------------
   DIMENSIONES
   ------------------------------------------------------------------------- */

-- Calendario: contiguo y completo. Se marca como tabla de fechas en Power BI.
IF OBJECT_ID('star.dim_calendario') IS NOT NULL DROP TABLE star.dim_calendario;
CREATE TABLE star.dim_calendario (
    fecha                   DATE         NOT NULL PRIMARY KEY,
    anio                    SMALLINT     NOT NULL,
    mes_nro                 TINYINT      NOT NULL,
    mes_nombre              CHAR(3)      NOT NULL,
    anio_mes                CHAR(7)      NOT NULL,   -- 'YYYY-MM'
    anio_mes_orden          INT          NOT NULL,   -- para Sort by column
    trimestre               CHAR(2)      NOT NULL,
    anio_trimestre          CHAR(7)      NOT NULL,
    dia_semana              TINYINT      NOT NULL,
    es_habil                BIT          NOT NULL,
    es_pasado               BIT          NOT NULL,
    es_ultimo_dia_mes       BIT          NOT NULL,
    temporada_respiratoria  BIT          NOT NULL
);
GO

IF OBJECT_ID('star.dim_filial') IS NOT NULL DROP TABLE star.dim_filial;
CREATE TABLE star.dim_filial (
    id_filial          INT          NOT NULL PRIMARY KEY,
    cod_filial         CHAR(2)      NOT NULL UNIQUE,
    pais               VARCHAR(40)  NOT NULL,
    region             VARCHAR(20)  NOT NULL,
    moneda             CHAR(3)      NOT NULL,
    sla_entrega_dias   TINYINT      NOT NULL
);
GO

-- Producto con la jerarquía ATC, que es el estándar de la industria farma.
IF OBJECT_ID('star.dim_producto') IS NOT NULL DROP TABLE star.dim_producto;
CREATE TABLE star.dim_producto (
    id_producto         INT           NOT NULL PRIMARY KEY,
    sku                 VARCHAR(20)   NOT NULL UNIQUE,
    marca               VARCHAR(60)   NOT NULL,
    atc1                CHAR(1)       NOT NULL,
    atc1_desc           VARCHAR(60)   NOT NULL,
    atc3                VARCHAR(10)   NOT NULL,
    forma_farmaceutica  VARCHAR(30)   NOT NULL,
    presentacion        VARCHAR(30)   NULL,
    tipo_venta          VARCHAR(15)   NOT NULL,   -- 'OTC' | 'Ético (Rx)'
    cadena_frio         BIT           NOT NULL,
    ciclo_vida          VARCHAR(15)   NOT NULL,
    vida_util_meses     SMALLINT      NOT NULL,
    precio_lista_usd    DECIMAL(12,2) NOT NULL,
    costo_std_usd       DECIMAL(12,2) NULL,
    costo_imputado      BIT           NOT NULL DEFAULT 0,  -- trazabilidad del dato
    margen_std_pct      DECIMAL(6,4)  NULL
);
CREATE INDEX ix_dim_producto_atc ON star.dim_producto (atc1, atc3);
GO

IF OBJECT_ID('star.dim_cliente') IS NOT NULL DROP TABLE star.dim_cliente;
CREATE TABLE star.dim_cliente (
    id_cliente        INT          NOT NULL PRIMARY KEY,
    cod_cliente       VARCHAR(20)  NOT NULL UNIQUE,
    razon_social      VARCHAR(120) NOT NULL,
    id_filial         INT          NOT NULL REFERENCES star.dim_filial(id_filial),
    canal             VARCHAR(30)  NOT NULL,
    segmento          CHAR(1)      NOT NULL,
    antiguedad_meses  SMALLINT     NULL,
    id_representante  INT          NULL
);
CREATE INDEX ix_dim_cliente_filial ON star.dim_cliente (id_filial, canal, segmento);
GO

IF OBJECT_ID('star.dim_representante') IS NOT NULL DROP TABLE star.dim_representante;
CREATE TABLE star.dim_representante (
    id_representante INT         NOT NULL PRIMARY KEY,
    nombre_rep       VARCHAR(60) NOT NULL,
    supervisor       VARCHAR(60) NULL,
    linea_promocion  VARCHAR(40) NULL
);
GO

IF OBJECT_ID('star.dim_deposito') IS NOT NULL DROP TABLE star.dim_deposito;
CREATE TABLE star.dim_deposito (
    id_deposito        INT         NOT NULL PRIMARY KEY,
    nombre_deposito    VARCHAR(40) NOT NULL,
    id_filial          INT         NOT NULL REFERENCES star.dim_filial(id_filial),
    tiene_camara_frio  BIT         NOT NULL,
    capacidad_pallets  INT         NULL
);
GO

IF OBJECT_ID('star.dim_transportista') IS NOT NULL DROP TABLE star.dim_transportista;
CREATE TABLE star.dim_transportista (
    id_transportista INT          NOT NULL PRIMARY KEY,
    transportista    VARCHAR(40)  NOT NULL,
    confiabilidad    DECIMAL(4,3) NULL,
    control_frio     BIT          NOT NULL
);
GO

IF OBJECT_ID('star.dim_tipo_oferta') IS NOT NULL DROP TABLE star.dim_tipo_oferta;
CREATE TABLE star.dim_tipo_oferta (
    id_tipo_oferta    INT          NOT NULL PRIMARY KEY,
    cod_tipo_oferta   CHAR(3)      NOT NULL UNIQUE,
    tipo_oferta_desc  VARCHAR(40)  NOT NULL,
    descuento_medio   DECIMAL(6,4) NULL,
    costo_relativo    DECIMAL(6,4) NULL   -- una bonificación cuesta el costo, no el precio
);
GO

IF OBJECT_ID('star.dim_motivo_devolucion') IS NOT NULL DROP TABLE star.dim_motivo_devolucion;
CREATE TABLE star.dim_motivo_devolucion (
    id_motivo        INT         NOT NULL PRIMARY KEY,
    cod_motivo       CHAR(3)     NOT NULL UNIQUE,
    motivo           VARCHAR(40) NOT NULL,
    area_responsable VARCHAR(20) NOT NULL,
    es_evitable      BIT         NOT NULL  -- separa "mala gestión" de "pasa y ya"
);
GO

/* -------------------------------------------------------------------------
   HECHOS
   ------------------------------------------------------------------------- */

-- Hecho principal. Grano: fecha × cliente × producto × depósito ×
-- transportista × tipo de oferta × tipo de documento.
-- NO lleva id_linea a propósito: es la columna de mayor cardinalidad del
-- origen y nadie la consulta. Sacarla es la optimización más rentable
-- del modelo (VertiPaq comprime por diccionario de columna).
IF OBJECT_ID('star.fact_ventas') IS NOT NULL DROP TABLE star.fact_ventas;
CREATE TABLE star.fact_ventas (
    fecha                    DATE          NOT NULL,
    id_cliente               INT           NOT NULL,
    id_producto              INT           NOT NULL,
    id_filial                INT           NOT NULL,
    id_deposito              INT           NOT NULL,
    id_transportista         INT           NOT NULL,
    id_tipo_oferta           INT           NOT NULL,
    tipo_documento           CHAR(2)       NOT NULL,   -- 'FC' factura | 'NC' nota de crédito
    unidades                 INT           NOT NULL,
    importe_usd              DECIMAL(18,2) NOT NULL,
    costo_usd                DECIMAL(18,2) NOT NULL,
    importe_local            DECIMAL(18,2) NOT NULL,   -- para conciliar con la filial
    lineas                   INT           NOT NULL,
    lineas_otif              INT           NOT NULL,
    lineas_completas         INT           NOT NULL,
    lead_time_dias_x_linea   DECIMAL(12,1) NOT NULL,   -- numerador del promedio ponderado
    unidades_devueltas       INT           NOT NULL,
    importe_devuelto_usd     DECIMAL(18,2) NOT NULL,
    lineas_devueltas         INT           NOT NULL,
    lineas_en_revision       INT           NOT NULL,   -- semáforo de calidad en el tablero
    dias_a_vencer_x_linea    BIGINT        NOT NULL
);
CREATE CLUSTERED COLUMNSTORE INDEX ccix_fact_ventas ON star.fact_ventas;
GO

IF OBJECT_ID('star.fact_devoluciones') IS NOT NULL DROP TABLE star.fact_devoluciones;
CREATE TABLE star.fact_devoluciones (
    fecha                DATE          NOT NULL,
    id_cliente           INT           NOT NULL,
    id_producto          INT           NOT NULL,
    id_filial            INT           NOT NULL,
    id_transportista     INT           NOT NULL,
    id_motivo            INT           NOT NULL,
    unidades_devueltas   INT           NOT NULL,
    importe_devuelto_usd DECIMAL(18,2) NOT NULL,
    lineas               INT           NOT NULL
);
CREATE CLUSTERED COLUMNSTORE INDEX ccix_fact_devoluciones ON star.fact_devoluciones;
GO

IF OBJECT_ID('star.fact_ofertas') IS NOT NULL DROP TABLE star.fact_ofertas;
CREATE TABLE star.fact_ofertas (
    id_oferta               BIGINT        NOT NULL,
    fecha                   DATE          NOT NULL,
    id_cliente              INT           NOT NULL,
    id_producto             INT           NOT NULL,
    id_filial               INT           NOT NULL,
    id_tipo_oferta          INT           NOT NULL,
    descuento_pct           DECIMAL(6,4)  NOT NULL,
    unidades_ofertadas      INT           NOT NULL,
    cobertura_cliente_dias  DECIMAL(8,1)  NULL,
    aceptada                BIT           NOT NULL
);
CREATE CLUSTERED COLUMNSTORE INDEX ccix_fact_ofertas ON star.fact_ofertas;
GO

-- Sell-out del panel de auditoría (IQVIA / Close-Up). Grano mensual.
-- Ojo: llega con desfasaje y con su propia granularidad. Nunca se mezcla
-- con sell-in en la misma tabla: son dos hechos distintos que comparten
-- las dimensiones de producto, filial y calendario.
IF OBJECT_ID('star.fact_sellout') IS NOT NULL DROP TABLE star.fact_sellout;
CREATE TABLE star.fact_sellout (
    fecha             DATE          NOT NULL,   -- mismo nombre en los 8 hechos
    id_filial         INT           NOT NULL,
    id_producto       INT           NOT NULL,
    unidades_sellout  BIGINT        NOT NULL,
    importe_sellout   DECIMAL(18,2) NOT NULL,
    unidades_mercado  BIGINT        NOT NULL,   -- denominador del market share
    importe_mercado   DECIMAL(18,2) NOT NULL
);
GO

IF OBJECT_ID('star.fact_objetivos') IS NOT NULL DROP TABLE star.fact_objetivos;
CREATE TABLE star.fact_objetivos (
    fecha                 DATE          NOT NULL,
    id_filial             INT           NOT NULL,
    id_producto           INT           NOT NULL,
    objetivo_importe_usd  DECIMAL(18,2) NOT NULL,
    objetivo_unidades     BIGINT        NOT NULL
);
GO

IF OBJECT_ID('star.fact_stock') IS NOT NULL DROP TABLE star.fact_stock;
CREATE TABLE star.fact_stock (
    fecha                     DATE          NOT NULL,
    id_deposito               INT           NOT NULL,
    id_producto               INT           NOT NULL,
    unidades_mes              INT           NOT NULL,
    stock_unidades            INT           NOT NULL,
    dias_cobertura            DECIMAL(8,1)  NOT NULL,
    stock_en_transito         INT           NOT NULL,
    dias_a_vencer_promedio    INT           NOT NULL,
    unidades_por_vencer_180d  INT           NOT NULL,
    valor_stock_usd           DECIMAL(18,2) NOT NULL
);
GO

IF OBJECT_ID('star.fact_tipo_cambio') IS NOT NULL DROP TABLE star.fact_tipo_cambio;
CREATE TABLE star.fact_tipo_cambio (
    fecha      DATE          NOT NULL,
    moneda     CHAR(3)       NOT NULL,
    tc_a_usd   DECIMAL(18,6) NOT NULL,
    CONSTRAINT pk_fact_tipo_cambio PRIMARY KEY (fecha, moneda)
);
GO

-- Salida del motor de IA del paso 5. Es un hecho más del modelo: así el
-- tablero de Ofertas muestra recomendación y realidad en la misma página,
-- sin exportar a Excel en el medio.
IF OBJECT_ID('star.fact_recomendaciones') IS NOT NULL DROP TABLE star.fact_recomendaciones;
CREATE TABLE star.fact_recomendaciones (
    mes_objetivo                CHAR(7)       NOT NULL,
    id_filial                   INT           NOT NULL,
    id_producto                 INT           NOT NULL,
    canal                       VARCHAR(30)   NOT NULL,
    segmento                    CHAR(1)       NOT NULL,
    rank_segmento               TINYINT       NOT NULL,
    sku                         VARCHAR(20)   NOT NULL,
    marca                       VARCHAR(60)   NOT NULL,
    descuento_pct               DECIMAL(6,4)  NOT NULL,
    precio_neto                 DECIMAL(12,2) NOT NULL,
    margen_unitario             DECIMAL(12,2) NOT NULL,
    elasticidad                 DECIMAL(6,3)  NOT NULL,
    nivel_estimacion            VARCHAR(10)   NOT NULL,
    indice_estacional           DECIMAL(6,3)  NOT NULL,
    aporte_margen_pct           DECIMAL(8,5)  NULL,
    dias_cobertura              DECIMAL(8,1)  NULL,
    unidades_por_vencer         INT           NULL,
    demanda_esperada            INT           NOT NULL,
    prob_aceptacion             DECIMAL(6,4)  NOT NULL,
    riesgo_devolucion           DECIMAL(6,4)  NOT NULL,
    margen_esperado_usd         DECIMAL(18,2) NOT NULL,
    valor_rescate_usd           DECIMAL(18,2) NOT NULL,
    objetivo                    DECIMAL(18,2) NOT NULL,
    objetivo_sin_oferta         DECIMAL(18,2) NOT NULL,
    ganancia_vs_sin_oferta_usd  DECIMAL(18,2) NOT NULL,
    en_borde_de_soporte         BIT           NOT NULL,
    justificativo               NVARCHAR(1200) NOT NULL
);
GO

-- Proyecciones mensuales de los modelos (pasos 3 y 4). Son hechos del modelo
-- como cualquier otro: se consultan desde el mismo tablero, con las mismas
-- dimensiones y el mismo contexto de filtro. Si vivieran en un Excel aparte,
-- nadie las usaría.
IF OBJECT_ID('star.fact_forecast_devoluciones') IS NOT NULL DROP TABLE star.fact_forecast_devoluciones;
CREATE TABLE star.fact_forecast_devoluciones (
    fecha                   DATE          NOT NULL,
    id_filial               INT           NOT NULL,
    cod_filial              CHAR(2)       NOT NULL,
    importe                 DECIMAL(18,2) NOT NULL,
    importe_dev             DECIMAL(18,2) NOT NULL,
    tasa_dev_valor          DECIMAL(8,5)  NOT NULL,
    tasa_dev_proyectada     DECIMAL(8,5)  NOT NULL,
    importe_dev_proyectado  DECIMAL(18,2) NOT NULL,
    -- Marca el tramo que el modelo NUNCA vio al entrenar. La precisión que se
    -- publica se calcula solo sobre estas filas: mostrar la de entrenamiento
    -- sería mentir con estadística correcta.
    es_holdout              BIT           NOT NULL
);
GO

IF OBJECT_ID('star.fact_forecast_ofertas') IS NOT NULL DROP TABLE star.fact_forecast_ofertas;
CREATE TABLE star.fact_forecast_ofertas (
    fecha                     DATE          NOT NULL,
    id_filial                 INT           NOT NULL,
    cod_filial                CHAR(2)       NOT NULL,
    ofertas                   INT           NOT NULL,
    aceptadas                 INT           NOT NULL,
    valor_ofertado            DECIMAL(18,2) NOT NULL,
    inversion_usd             DECIMAL(18,2) NOT NULL,
    inversion_proyectada_usd  DECIMAL(18,2) NOT NULL,
    tasa_aceptacion           DECIMAL(8,5)  NOT NULL,
    es_holdout                BIT           NOT NULL
);
GO

-- Estado de calidad: una sola fila que alimenta el encabezado de confianza de
-- los tres tableros. El estado del dato es parte del modelo, no un anexo: si
-- vive fuera, nadie lo mira y el semáforo deja de existir.
IF OBJECT_ID('star.fact_estado_datos') IS NOT NULL DROP TABLE star.fact_estado_datos;
CREATE TABLE star.fact_estado_datos (
    ultimo_dato         DATE         NOT NULL,
    controles_criticos  INT          NOT NULL,
    controles_alerta    INT          NOT NULL,
    controles_ok        INT          NOT NULL,
    ultima_validacion   DATETIME2(0) NOT NULL
);
GO

-- Scoring de riesgo a nivel pedido (salida del modelo del paso 3).
IF OBJECT_ID('star.fact_scoring_devoluciones') IS NOT NULL DROP TABLE star.fact_scoring_devoluciones;
CREATE TABLE star.fact_scoring_devoluciones (
    fecha                   DATE          NOT NULL,
    id_cliente              INT           NOT NULL,
    id_producto             INT           NOT NULL,
    id_filial               INT           NOT NULL,
    id_transportista        INT           NOT NULL,
    unidades                INT           NOT NULL,
    importe_usd             DECIMAL(18,2) NOT NULL,
    devuelta                BIT           NOT NULL,
    prob_devolucion         DECIMAL(8,5)  NOT NULL,
    banda_riesgo            VARCHAR(10)   NOT NULL,
    importe_en_riesgo_usd   DECIMAL(18,2) NOT NULL
);
CREATE CLUSTERED COLUMNSTORE INDEX ccix_fact_scoring ON star.fact_scoring_devoluciones;
GO

/* -------------------------------------------------------------------------
   INTEGRIDAD REFERENCIAL
   En un DW con columnstore no siempre se dejan FK activas por costo de carga.
   La decisión acá: se declaran NOT ENFORCED para documentar el modelo (y para
   que las herramientas de modelado las detecten) y la integridad real se
   valida con los controles de 03_calidad_datos.sql antes de publicar.
   ------------------------------------------------------------------------- */
ALTER TABLE star.fact_ventas WITH NOCHECK
    ADD CONSTRAINT fk_fv_calendario FOREIGN KEY (fecha) REFERENCES star.dim_calendario(fecha) NOT FOR REPLICATION;
ALTER TABLE star.fact_ventas NOCHECK CONSTRAINT fk_fv_calendario;
GO
