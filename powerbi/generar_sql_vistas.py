# © 2026 Martín Viera. Todos los derechos reservados.

"""
Genera `sql/04_vistas_semanticas.sql` desde el contrato de `esquema.py`.

Por qué generarlo en vez de escribirlo a mano:

El mismo contrato —qué columnas hay, cómo se llaman de cara al negocio y qué
reglas derivadas se aplican— lo consumen dos cosas distintas: el archivo de
Power BI (en M) y las vistas del data warehouse (en T-SQL). Escribirlo dos
veces garantiza que en algún momento se desincronicen, y el día que pasa nadie
se entera hasta que dos tableros muestran números distintos y alguien pierde la
mañana buscando por qué.

Con esto, la única forma de cambiar un nombre de columna es cambiarlo en
`esquema.py`, y las dos salidas se regeneran juntas.

Uso:  python powerbi/generar_sql_vistas.py
      python powerbi/validar_contrato.py      (verifica que no divergieron)
"""
from __future__ import annotations

from pathlib import Path

import esquema as esq

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "sql" / "04_vistas_semanticas.sql"

CABECERA = """/* =========================================================================
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
"""


def _corchetes(nombre: str) -> str:
    return "[" + nombre.replace("]", "]]") + "]"


def vista(tabla: str, cfg: dict) -> str:
    derivadas = {d["nombre"]: d["sql"] for d in esq.DERIVADAS.get(tabla, [])}
    aplanar = esq.APLANAR.get(tabla)
    origen = cfg["origen"]

    lineas = [f"CREATE OR ALTER VIEW star.{tabla} AS", "SELECT"]
    campos = []
    for orig, visible, _tipo, _oculta in cfg["columnas"]:
        if orig is None:
            if visible in derivadas:
                campos.append(f"    {derivadas[visible]:<62} AS {_corchetes(visible)}")
            elif aplanar and visible in aplanar["columnas"].values():
                col = next(k for k, v in aplanar["columnas"].items() if v == visible)
                campos.append(f"    {'sat.' + col:<62} AS {_corchetes(visible)}")
            else:
                raise ValueError(f"{tabla}.{visible}: derivada sin expresión SQL")
        else:
            campos.append(f"    {'t.' + orig:<62} AS {_corchetes(visible)}")
    lineas.append(",\n".join(campos))
    lineas.append(f"FROM star.{origen} AS t")

    if aplanar:
        lineas.append(
            f"LEFT JOIN star.{aplanar['tabla']} AS sat "
            f"ON sat.{aplanar['clave']} = t.{aplanar['clave']}"
        )
    lineas.append("GO")
    return "\n".join(lineas)


def main() -> None:
    bloques = [CABECERA]

    for grupo, titulo in [("dimension", "DIMENSIONES"),
                          ("hecho", "HECHOS"),
                          ("servicio", "SERVICIO")]:
        tablas = {t: c for t, c in esq.TABLAS.items() if c["tipo"] == grupo}
        if not tablas:
            continue
        bloques.append(
            f"\n/* {'-' * 71}\n   {titulo}\n   {'-' * 71} */\n"
        )
        for tabla, cfg in tablas.items():
            bloques.append(vista(tabla, cfg))
            bloques.append("")

    DESTINO.write_text("\n".join(bloques), encoding="utf-8")
    n = sum(1 for c in esq.TABLAS.values())
    print(f"  {n} vistas generadas → {DESTINO.relative_to(RAIZ)}")
    print("  Los nombres de columna quedan sincronizados con el modelo semántico.")


if __name__ == "__main__":
    main()
