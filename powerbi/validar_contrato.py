"""
Valida que las cuatro representaciones del modelo digan lo mismo.

El mismo modelo vive en cuatro lados:

    powerbi/esquema.py        el contrato
    sql/01_ddl...sql          las tablas físicas del data warehouse
    sql/04_vistas...sql       las vistas que consume Power BI
    data/star/*.parquet       la salida del pipeline de Python

Si alguno se desincroniza, el síntoma no es un error: es un tablero que carga
igual y muestra otro número, o una columna que aparece en blanco. Eso puede
sobrevivir meses sin que nadie lo note.

Este script rompe a propósito cuando algo no cierra, para que el problema
aparezca acá y no en un comité.

Uso:  python powerbi/validar_contrato.py
Sale con código 1 si encuentra alguna diferencia.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import esquema as esq

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "sql"
STAR = RAIZ / "data" / "star"
DAX = Path(__file__).resolve().parent / "dax"


def columnas_del_ddl() -> dict[str, set[str]]:
    """Extrae {tabla: {columnas}} de los CREATE TABLE de sql/01."""
    texto = (SQL / "01_ddl_modelo_estrella.sql").read_text(encoding="utf-8")
    tablas: dict[str, set[str]] = {}
    for m in re.finditer(
        r"CREATE\s+TABLE\s+star\.(\w+)\s*\((.*?)\n\);", texto, re.S | re.I
    ):
        nombre, cuerpo = m.group(1), m.group(2)
        cols = set()
        for linea in cuerpo.splitlines():
            linea = linea.strip()
            if not linea or linea.startswith(("--", "/*", "CONSTRAINT")):
                continue
            c = re.match(r"(\w+)\s+[A-Za-z]", linea)
            if c:
                cols.add(c.group(1))
        tablas[nombre] = cols
    return tablas


def main() -> int:
    fallas: list[str] = []
    avisos: list[str] = []

    # ---------- 1. el contrato contra el DDL ----------
    ddl = columnas_del_ddl()
    for tabla, cfg in esq.TABLAS.items():
        origen = cfg["origen"]
        if origen not in ddl:
            fallas.append(f"DDL: falta la tabla star.{origen} (la usa {tabla})")
            continue
        for orig, visible, _t, _o in cfg["columnas"]:
            if orig is not None and orig not in ddl[origen]:
                fallas.append(f"DDL: star.{origen} no tiene la columna '{orig}' "
                              f"(el modelo la expone como '{visible}')")
    for tabla in esq.APLANAR.values():
        if tabla["tabla"] not in ddl:
            fallas.append(f"DDL: falta la tabla satélite star.{tabla['tabla']}")

    # ---------- 2. el contrato contra los parquet ----------
    if STAR.exists() and any(STAR.glob("*.parquet")):
        import pandas as pd
        for tabla, cfg in esq.TABLAS.items():
            f = STAR / f"{cfg['origen']}.parquet"
            if not f.exists():
                fallas.append(f"Parquet: falta {f.name} (lo usa {tabla})")
                continue
            reales = set(pd.read_parquet(f).columns)
            for orig, visible, _t, _o in cfg["columnas"]:
                if orig is not None and orig not in reales:
                    fallas.append(f"Parquet: {f.name} no tiene '{orig}' "
                                  f"(el modelo la expone como '{visible}')")
            for d in esq.DERIVADAS.get(tabla, []):
                for c in re.findall(r"\[([a-z_0-9]+)\]", d["m"]):
                    if c not in reales:
                        fallas.append(f"Parquet: {f.name} no tiene '{c}', que usa "
                                      f"la derivada '{d['nombre']}'")
    else:
        avisos.append("Parquet: no hay datos generados todavía "
                      "(corré `python src/run_all.py` para validar también esa capa)")

    # ---------- 3. el contrato contra las vistas generadas ----------
    vistas_txt = (SQL / "04_vistas_semanticas.sql").read_text(encoding="utf-8")
    for tabla, cfg in esq.TABLAS.items():
        if f"CREATE OR ALTER VIEW star.{tabla} AS" not in vistas_txt:
            fallas.append(f"Vistas: falta star.{tabla} — regenerá con "
                          f"`python powerbi/generar_sql_vistas.py`")
            continue
        bloque = vistas_txt.split(f"CREATE OR ALTER VIEW star.{tabla} AS")[1].split("GO")[0]
        for _o, visible, _t, _oc in cfg["columnas"]:
            if f"[{visible}]" not in bloque:
                fallas.append(f"Vistas: star.{tabla} no expone [{visible}] — "
                              f"la vista quedó desactualizada")

    # ---------- 4. el DAX contra el contrato ----------
    columnas_modelo = {
        t: {v for _o, v, _tt, _oc in c["columnas"]} for t, c in esq.TABLAS.items()
    }
    medidas = set()
    for archivo in esq.BIBLIOTECA_DAX:
        for linea in (DAX / archivo).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([^\s/][^=\[\(]*?)\s*=\s*", linea)
            if m and not linea.startswith(" ") and m.group(1).split(" ")[0] not in {
                "VAR", "RETURN"
            }:
                medidas.add(m.group(1).strip())

    for archivo in esq.BIBLIOTECA_DAX:
        texto = (DAX / archivo).read_text(encoding="utf-8")
        # comentarios fuera: adentro hay referencias de ejemplo a propósito
        texto = "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("//"))
        for tab, col in re.findall(r"(v_[a-z_]+)\[([^\]]+)\]", texto):
            if tab not in columnas_modelo:
                fallas.append(f"DAX ({archivo}): tabla inexistente '{tab}'")
            elif col not in columnas_modelo[tab]:
                fallas.append(f"DAX ({archivo}): '{tab}' no tiene la columna '{col}'")
        for ref in re.findall(r"(?<![a-z_\]])\[([^\]]+)\]", texto):
            if not ref.startswith("@") and ref not in medidas:
                fallas.append(f"DAX ({archivo}): medida inexistente '[{ref}]'")

    # ---------- 5. reglas de modelado que no se negocian ----------
    for t1, c1, t2, c2 in esq.RELACIONES:
        if c1 not in columnas_modelo.get(t1, set()):
            fallas.append(f"Relación: {t1} no tiene '{c1}'")
        if c2 not in columnas_modelo.get(t2, set()):
            fallas.append(f"Relación: {t2} no tiene '{c2}'")
    hechos_sin_calendario = [
        t for t, c in esq.TABLAS.items()
        if c["tipo"] == "hecho"
        and not any(r[2] == t and r[0] == "v_dim_calendario" for r in esq.RELACIONES)
    ]
    for t in hechos_sin_calendario:
        avisos.append(f"Modelado: el hecho {t} no está relacionado con el calendario "
                      f"(sin eso, la inteligencia de tiempo no lo alcanza)")

    # ---------- informe ----------
    print("Validación del contrato del modelo\n")
    print(f"  tablas en el contrato : {len(esq.TABLAS)}")
    print(f"  medidas en la librería: {len(medidas)}")
    print(f"  relaciones declaradas : {len(esq.RELACIONES)}")
    print()
    for a in avisos:
        print(f"  [aviso] {a}")
    if fallas:
        print(f"\n  {len(fallas)} DIFERENCIA(S) — el modelo no está sincronizado:\n")
        for f in fallas:
            print(f"    · {f}")
        return 1
    print("  [ok] las cuatro representaciones del modelo coinciden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
