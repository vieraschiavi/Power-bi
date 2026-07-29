# Archivos de Power BI — cómo abrirlos

Tres tableros, dos formatos de cada uno. Los dos llevan **todo** adentro:
las 20 tablas del modelo estrella, las 38 relaciones, las **117 medidas DAX**,
formatos, jerarquías, columnas ocultas, orden por columna, el rol de RLS y las
páginas del reporte.

| Tablero | Template | Proyecto | Páginas |
|---|---|---|---|
| VAR — Ventas, Análisis y Rentabilidad | `Adium_VAR.pbit` | `Adium_VAR.pbip` | 3 |
| Ofertas — política comercial e IA | `Adium_Ofertas.pbit` | `Adium_Ofertas.pbip` | 3 |
| Logística — servicio, devoluciones y riesgo | `Adium_Logistica.pbit` | `Adium_Logistica.pbip` | 4 |

---

## Antes de abrir: generar los datos

Los archivos traen el modelo, no los datos — un template nunca lleva datos, por
diseño. Hay que generarlos una vez:

```bash
pip install -r requirements.txt
python src/run_all.py
```

Eso deja los `.parquet` del modelo estrella en `data/star/`. Anotá esa ruta
completa: es lo único que te va a pedir el archivo al abrirse.

---

## Opción 1 — `.pbit` (la más rápida)

1. Doble clic en `Adium_VAR.pbit`.
2. Power BI Desktop pide el parámetro **RutaDatos**. Pegá la ruta absoluta de
   tu carpeta `data/star` — por ejemplo `C:\Proyectos\Power-bi\data\star`.
   Sin barra al final.
3. **Cargar**. Tarda unos segundos: son ~234.000 filas en el hecho principal.
4. **Archivo → Guardar como → `Adium_VAR.pbix`**.

Repetir con los otros dos.

## Opción 2 — PBIP (para trabajar con control de versiones)

Requiere activar *Archivo → Opciones → Características de vista previa → **Power
BI Project (.pbip)***, y después *Archivo → Abrir → `Adium_VAR.pbip`*.

Es el formato que conviene si vas a versionar el trabajo: el modelo queda en
`model.bim` y el reporte en `report.json`, ambos texto plano y revisables en un
diff. Desde acá también se guarda como `.pbix`.

---

## Por qué no hay un `.pbix` directamente

Un `.pbix` guarda el modelo tabular como un binario comprimido propietario de
Analysis Services. No se puede autorizar desde afuera de Power BI, y tampoco se
puede leer en un diff: para el control de versiones es una caja negra.

`.pbit` y PBIP son los dos formatos que Microsoft define exactamente para este
caso. Desde cualquiera de los dos, llegar al `.pbix` es un *Guardar como*.

---

## Si algo falla

**«No se encontró el archivo»** al cargar → la ruta del parámetro está mal.
*Inicio → Transformar datos → Administrar parámetros → RutaDatos*, corregila y
*Cerrar y aplicar*. Tiene que ser la ruta **absoluta** de la carpeta, sin barra
final y sin comillas.

**Falta el conector Parquet** → actualizá Power BI Desktop. `Parquet.Document`
está disponible desde 2021; en versiones muy viejas no existe.

**Preferís cargar desde SQL Server** → desplegá `sql/01` a `sql/04` en tu
instancia y en *Transformar datos* cambiá el origen de cada consulta por
`Sql.Database("servidor", "base")` apuntando a las vistas `star.v_*`. Los
nombres de columna del modelo son exactamente los que devuelven esas vistas,
así que las 117 medidas siguen funcionando sin tocar una línea de DAX.

**Si un archivo no abre** → los tres se regeneran con
`python powerbi/generar_pbit.py`. Y como último recurso, el modelo completo
está en `Adium_VAR.SemanticModel/model.bim`, que Tabular Editor abre e importa
a un `.pbix` en blanco.

---

## Una aclaración honesta

Estos archivos se generaron programáticamente y se validaron por código:
estructura del paquete, codificación UTF-16 de las partes internas, sintaxis M,
y —lo más importante— que **cada tabla, columna y medida referenciada exista
realmente en el modelo** (0 referencias rotas sobre 117 medidas y 38 relaciones,
y las consultas M contrastadas contra el esquema real de los `.parquet`).

Lo que **no** se pudo hacer acá es abrirlos en Power BI Desktop, que no corre en
este entorno. Si alguno se queja al abrir, es cuestión de un ajuste en el
generador, no de rehacer el trabajo: el modelo, las medidas y el diseño están
todos en texto plano y versionados.

---

## Qué mirar primero en cada tablero

**VAR** → página 2, el puente Precio–Volumen–Mix. No dice que las ventas
cayeron: dice cuánto de esa caída es precio, cuánto volumen y cuánto mezcla. Y
si la descomposición no cierra exactamente, el tablero lo marca en rojo.

**Ofertas** → página 2, la recomendación del motor de IA. El justificativo
ocupa el ancho completo a propósito: una recomendación que no se puede discutir
es una recomendación que no se aplica.

**Logística** → página 3, riesgo predictivo. Es la única página pensada para
mirarse *antes* de despachar, no después de que la devolución ya ocurrió.
