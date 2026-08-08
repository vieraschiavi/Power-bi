#!/usr/bin/env python3
"""
MV DAX Lab · Genera el dataset y el modelo de práctica, 100% sintéticos.

Por qué existe: para probar el ciclo completo —cargar, analizar, generar DAX,
transformar, exportar— hace falta un modelo del que se conozca de antemano
cada tabla, cada columna y cada defecto. El modelo Adium sirve como demo
comercial, pero es un modelo real de otro dominio: no se puede afirmar sobre
él "acá faltan exactamente 3 formatos" sin ir a mirar.

Este genera:
  · CSVs con seed fijo (mismos datos en cada corrida)
  · un model.bim que los lee con Power Query (M), con la estrella
    Ventas → Clientes / Productos / Calendario
  · defectos INYECTADOS a propósito, para que el analizador tenga qué
    encontrar: una división con «/», una medida sin formato, una relación
    bidireccional y una tabla suelta.

Nada de esto son datos de personas reales: nombres, países y productos salen
de listas inventadas.

Uso:  python daxlingo/datos/demo/generar_sintetico.py [--salida CARPETA]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SEMILLA = 42

PAISES = ["Uruguay", "Argentina", "Brasil", "Chile", "Paraguay"]
SEGMENTOS = ["Empresas", "Comercios", "Consumidor final"]
CATEGORIAS = ["Bebidas", "Almacén", "Limpieza", "Perfumería"]
NOMBRES = ["Distribuidora Sur", "Almacén Central", "Mayorista Norte",
           "Kiosco La Esquina", "Supermercado Río", "Depósito Este",
           "Autoservicio Plaza", "Minimercado Sol", "Proveeduría Oeste",
           "Comercial del Puerto"]


def generar_datos(carpeta: Path, meses: int = 24,
                  n_ventas: int = 4000) -> dict[str, int]:
    """Escribe los CSV. Devuelve cuántas filas quedó cada tabla."""
    rnd = random.Random(SEMILLA)
    carpeta.mkdir(parents=True, exist_ok=True)

    # --- Clientes ---
    clientes = []
    for i in range(1, 41):
        clientes.append({
            "IdCliente": i,
            "Nombre": f"{rnd.choice(NOMBRES)} {i}",
            "Pais": rnd.choice(PAISES),
            "Segmento": rnd.choice(SEGMENTOS),
        })
    _escribir(carpeta / "clientes.csv", clientes)

    # --- Productos ---
    productos = []
    for i in range(1, 61):
        costo = round(rnd.uniform(20, 400), 2)
        productos.append({
            "IdProducto": i,
            "Producto": f"Artículo {i:03d}",
            "Categoria": rnd.choice(CATEGORIAS),
            "PrecioLista": round(costo * rnd.uniform(1.25, 2.1), 2),
        })
    _escribir(carpeta / "productos.csv", productos)

    # --- Calendario ---
    inicio = dt.date(2024, 1, 1)
    fin = _sumar_meses(inicio, meses) - dt.timedelta(days=1)
    calendario = []
    dia = inicio
    while dia <= fin:
        calendario.append({
            "Fecha": dia.isoformat(),
            "Anio": dia.year,
            "Mes": dia.month,
            "AnioMes": f"{dia.year}-{dia.month:02d}",
        })
        dia += dt.timedelta(days=1)
    _escribir(carpeta / "calendario.csv", calendario)

    # --- Ventas ---
    dias = (fin - inicio).days
    ventas = []
    for k in range(1, n_ventas + 1):
        prod = rnd.choice(productos)
        cantidad = rnd.randint(1, 40)
        # Descuento ocasional: da variabilidad al margen sin inventar nada.
        precio = prod["PrecioLista"] * rnd.uniform(0.82, 1.0)
        costo_unit = prod["PrecioLista"] / rnd.uniform(1.25, 2.1)
        ventas.append({
            "IdVenta": k,
            "Fecha": (inicio + dt.timedelta(days=rnd.randint(0, dias))).isoformat(),
            "IdCliente": rnd.choice(clientes)["IdCliente"],
            "IdProducto": prod["IdProducto"],
            "Cantidad": cantidad,
            "Importe": round(precio * cantidad, 2),
            "Costo": round(costo_unit * cantidad, 2),
        })
    _escribir(carpeta / "ventas.csv", ventas)

    return {"clientes": len(clientes), "productos": len(productos),
            "calendario": len(calendario), "ventas": len(ventas)}


def _sumar_meses(fecha: dt.date, meses: int) -> dt.date:
    mes = fecha.month - 1 + meses
    return dt.date(fecha.year + mes // 12, mes % 12 + 1, 1)


def _escribir(ruta: Path, filas: list[dict]) -> None:
    with ruta.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


# ==========================================================================
def _particion(nombre: str, archivo: str, tipos: list[tuple[str, str]]) -> dict:
    """Partición M que lee un CSV desde el parámetro RutaDatos."""
    transformaciones = ", ".join(f'{{"{c}", {t}}}' for c, t in tipos)
    return {
        "name": nombre,
        "mode": "import",
        "source": {"type": "m", "expression": [
            "let",
            f'    Origen = Csv.Document(File.Contents(RutaDatos & "\\{archivo}"),'
            "[Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),",
            "    Encabezados = Table.PromoteHeaders(Origen, "
            "[PromoteAllScalars=true]),",
            f"    Tipos = Table.TransformColumnTypes(Encabezados,"
            f"{{{transformaciones}}})",
            "in",
            "    Tipos",
        ]},
    }


def _col(nombre: str, tipo: str, oculta: bool = False) -> dict:
    c = {"name": nombre, "dataType": tipo, "sourceColumn": nombre,
         "summarizeBy": "none",
         "annotations": [{"name": "SummarizationSetBy", "value": "User"}]}
    if oculta:
        c["isHidden"] = True
    if tipo == "dateTime":
        c["formatString"] = "yyyy-mm-dd"
    return c


def construir_modelo(nombre: str = "MV_DAX_Lab_Sintetico") -> dict:
    """
    El TMSL del modelo de práctica, con defectos inyectados a propósito.
    Los defectos están marcados con «DEFECTO:» para que quede claro que son
    intencionales y nadie los "arregle" rompiendo los tests.
    """
    return {
        "name": nombre,
        "compatibilityLevel": 1567,
        "model": {
            "culture": "es-ES",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "es-ES",
            "expressions": [{
                "name": "RutaDatos",
                "kind": "m",
                "expression": ['"C:\\MV_DAX_Lab\\datos" meta '
                               '[IsParameterQuery=true, Type="Text", '
                               "IsParameterQueryRequired=true]"],
            }],
            "tables": [
                {
                    "name": "Ventas",
                    "columns": [
                        _col("IdVenta", "int64", oculta=True),
                        _col("Fecha", "dateTime"),
                        # DEFECTO (R08): clave de relación visible.
                        _col("IdCliente", "int64"),
                        _col("IdProducto", "int64"),
                        _col("Cantidad", "int64"),
                        _col("Importe", "double"),
                        _col("Costo", "double"),
                    ],
                    "partitions": [_particion("Ventas", "ventas.csv", [
                        ("IdVenta", "Int64.Type"), ("Fecha", "type date"),
                        ("IdCliente", "Int64.Type"),
                        ("IdProducto", "Int64.Type"),
                        ("Cantidad", "Int64.Type"),
                        ("Importe", "type number"), ("Costo", "type number"),
                    ])],
                    "measures": [
                        {"name": "Total Ventas",
                         "expression": "SUM ( Ventas[Importe] )",
                         "formatString": "#,0"},
                        # DEFECTO (R01 + R02): división con «/» y sin formato.
                        {"name": "Margen %",
                         "expression": "( SUM ( Ventas[Importe] ) - SUM ( "
                                       "Ventas[Costo] ) ) / SUM ( "
                                       "Ventas[Importe] )"},
                    ],
                },
                {
                    "name": "Clientes",
                    "columns": [_col("IdCliente", "int64"),
                                _col("Nombre", "string"),
                                _col("Pais", "string"),
                                _col("Segmento", "string")],
                    "partitions": [_particion("Clientes", "clientes.csv", [
                        ("IdCliente", "Int64.Type"), ("Nombre", "type text"),
                        ("Pais", "type text"), ("Segmento", "type text"),
                    ])],
                },
                {
                    "name": "Productos",
                    "columns": [_col("IdProducto", "int64"),
                                _col("Producto", "string"),
                                _col("Categoria", "string"),
                                _col("PrecioLista", "double")],
                    "partitions": [_particion("Productos", "productos.csv", [
                        ("IdProducto", "Int64.Type"), ("Producto", "type text"),
                        ("Categoria", "type text"),
                        ("PrecioLista", "type number"),
                    ])],
                },
                {
                    "name": "Calendario",
                    "dataCategory": "Time",
                    "columns": [
                        {**_col("Fecha", "dateTime"), "isKey": True},
                        _col("Anio", "int64"), _col("Mes", "int64"),
                        _col("AnioMes", "string"),
                    ],
                    "partitions": [_particion("Calendario", "calendario.csv", [
                        ("Fecha", "type date"), ("Anio", "Int64.Type"),
                        ("Mes", "Int64.Type"), ("AnioMes", "type text"),
                    ])],
                },
                {
                    # DEFECTO (R12): tabla sin ninguna relación.
                    "name": "Notas",
                    "columns": [_col("Tema", "string"), _col("Detalle", "string")],
                    "partitions": [{
                        "name": "Notas", "mode": "import",
                        "source": {"type": "m", "expression": [
                            "let",
                            '    Origen = #table({"Tema","Detalle"}, '
                            '{{"demo","datos sintéticos"}})',
                            "in", "    Origen"]},
                    }],
                },
            ],
            "relationships": [
                {
                    "name": "Ventas-Clientes",
                    "fromTable": "Ventas", "fromColumn": "IdCliente",
                    "toTable": "Clientes", "toColumn": "IdCliente",
                    # DEFECTO (R09): filtro cruzado en las dos direcciones.
                    "crossFilteringBehavior": "bothDirections",
                },
                {
                    "name": "Ventas-Productos",
                    "fromTable": "Ventas", "fromColumn": "IdProducto",
                    "toTable": "Productos", "toColumn": "IdProducto",
                    "crossFilteringBehavior": "oneDirection",
                },
                {
                    "name": "Ventas-Calendario",
                    "fromTable": "Ventas", "fromColumn": "Fecha",
                    "toTable": "Calendario", "toColumn": "Fecha",
                    "crossFilteringBehavior": "oneDirection",
                },
            ],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", default=str(AQUI / "sintetico"),
                    help="carpeta donde dejar los CSV y el model.bim")
    args = ap.parse_args()

    carpeta = Path(args.salida)
    filas = generar_datos(carpeta)
    modelo = construir_modelo()
    destino = carpeta / "modelo_sintetico.bim"
    destino.write_text(json.dumps(modelo, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    print(f"Dataset sintético en {carpeta} (seed {SEMILLA})")
    for tabla, n in filas.items():
        print(f"  {tabla:<12} {n:>6} filas")
    print(f"  modelo       {destino.name}")


if __name__ == "__main__":
    main()
