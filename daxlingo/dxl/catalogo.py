# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Catálogo del modelo: la vista de trabajo sobre el TMSL.

El TMSL crudo es incómodo para analizar. `Catalogo` lo aplana en listas de
tablas, columnas, medidas y relaciones, y ofrece búsqueda tolerante a
mayúsculas y acentos — la misma que usa el generador NL→DAX para anclar cada
pedido a objetos que EXISTEN en el modelo (anti-alucinación).

También puede armarse desde el layout de un .pbix (catálogo parcial: solo lo
que los visuales referencian), para que un .pbix no sea una caja negra total.
"""
from __future__ import annotations

import json
import re
import unicodedata

from .i18n import IDIOMA_DEFECTO, t as traducir
from .modelo import expr_texto

TIPOS_NUMERICOS = {"int64", "double", "decimal", "currency"}


def _norm(texto: str) -> str:
    """minúsculas + sin acentos: 'Año-Mes' → 'ano-mes'."""
    plano = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in plano if not unicodedata.combining(c)).lower().strip()


def _palabras(texto: str) -> list[str]:
    """
    Palabras alfanuméricas del texto, normalizadas. Sirve para comparar
    nombres ignorando separadores: «% del total · Importe» y
    «% del total - importe» son el mismo nombre.
    """
    return [p for p in re.split(r"[^a-z0-9]+", _norm(texto)) if p]


# Palabras que delatan que una medida YA es el resultado de un cálculo sobre
# otra. Una medida así no sirve de base para una derivación nueva: la media
# móvil de un acumulado anual, o la variación interanual de un ranking, son
# DAX válido y número sin sentido. Ver `Catalogo.buscar_medidas`.
MARCAS_DERIVADAS = frozenset({
    "ytd", "mtd", "qtd", "ytm", "acumulado", "acumulada", "acum",
    "aa", "anterior", "previo", "var", "variacion", "delta", "dif",
    "diferencia", "pct", "porcentaje", "participacion", "share",
    "movil", "moving", "rolling", "ranking", "rank", "puesto",
    "vs", "contra", "growth", "crecimiento", "yoy", "mom",
})

# Los sufijos abreviados que los modeladores le ponen a las derivadas:
# «Ventas Netas USD MA3», «Importe MM12», «Unidades 3M». Mismo criterio que
# MARCAS_DERIVADAS, pero no se pueden enumerar de a una.
_MARCA_ABREVIADA = re.compile(r"^(?:m[am]\d*|\d+m|t\d|q\d|acum\d*)$")


def _es_derivada(palabra: str) -> bool:
    return palabra in MARCAS_DERIVADAS or bool(_MARCA_ABREVIADA.match(palabra))


class Catalogo:
    """Vista aplanada e indexada de un modelo tabular."""

    def __init__(self) -> None:
        self.nombre = ""
        self.parcial = False          # True si vino del layout de un .pbix
        self.tablas: list[dict] = []  # {nombre, columnas, medidas, es_calendario, oculta}
        self.relaciones: list[dict] = []
        self.cultura = ""

    # ------------------------------------------------------------------
    @classmethod
    def desde_modelo(cls, modelo: dict) -> "Catalogo":
        cat = cls()
        cat.nombre = modelo.get("name", "")
        m = modelo.get("model", modelo)
        cat.cultura = m.get("culture", "")

        for t in m.get("tables", []):
            columnas = []
            for c in t.get("columns", []):
                columnas.append({
                    "nombre": c.get("name", ""),
                    "tipo": c.get("dataType", ""),
                    "oculta": bool(c.get("isHidden")),
                    "formato": c.get("formatString", ""),
                    "calculada": c.get("type") == "calculated",
                    "expresion": expr_texto(c.get("expression")),
                    "origen": c.get("sourceColumn", ""),
                })
            medidas = []
            for md in t.get("measures", []):
                medidas.append({
                    "nombre": md.get("name", ""),
                    "expresion": expr_texto(md.get("expression")),
                    "formato": md.get("formatString", ""),
                    "descripcion": md.get("description", ""),
                    "carpeta": md.get("displayFolder", ""),
                    "tabla": t.get("name", ""),
                })
            cat.tablas.append({
                "nombre": t.get("name", ""),
                "columnas": columnas,
                "medidas": medidas,
                "es_calendario": t.get("dataCategory") == "Time",
                "oculta": bool(t.get("isHidden")),
                "interna": t.get("name", "").startswith(
                    ("LocalDateTable_", "DateTableTemplate_")),
            })

        for r in m.get("relationships", []):
            cat.relaciones.append({
                "nombre": r.get("name", ""),
                "desde_tabla": r.get("fromTable", ""),
                "desde_col": r.get("fromColumn", ""),
                "hacia_tabla": r.get("toTable", ""),
                "hacia_col": r.get("toColumn", ""),
                "bidireccional": r.get("crossFilteringBehavior") == "bothDirections",
                "activa": r.get("isActive", True),
                "muchos_a_muchos": (r.get("fromCardinality") == "many"
                                    and r.get("toCardinality") == "many"),
            })
        return cat

    # ------------------------------------------------------------------
    @classmethod
    def desde_layout(cls, layout: dict) -> "Catalogo":
        """
        Catálogo PARCIAL desde el layout de un reporte (.pbix): junta las
        entidades y propiedades que los visuales referencian en sus
        prototypeQuery. No hay tipos ni expresiones — y se dice.
        """
        cat = cls()
        cat.parcial = True
        tablas: dict[str, dict] = {}

        def tabla_de(nombre: str) -> dict:
            if nombre not in tablas:
                tablas[nombre] = {"nombre": nombre, "columnas": [], "medidas": [],
                                  "es_calendario": False, "oculta": False,
                                  "interna": False}
            return tablas[nombre]

        for seccion in layout.get("sections", []):
            for vc in seccion.get("visualContainers", []):
                try:
                    conf = json.loads(vc.get("config", "{}"))
                except (TypeError, ValueError):
                    continue
                proto = (conf.get("singleVisual") or {}).get("prototypeQuery") or {}
                alias = {f.get("Name"): f.get("Entity")
                         for f in proto.get("From", [])}
                for sel in proto.get("Select", []):
                    if "Column" in sel:
                        fuente = sel["Column"]["Expression"]["SourceRef"].get("Source")
                        col = sel["Column"].get("Property", "")
                        ent = alias.get(fuente)
                        if ent and col and not any(
                                c["nombre"] == col
                                for c in tabla_de(ent)["columnas"]):
                            tabla_de(ent)["columnas"].append({
                                "nombre": col, "tipo": "", "oculta": False,
                                "formato": "", "calculada": False,
                                "expresion": "", "origen": ""})
                    if "Measure" in sel:
                        fuente = sel["Measure"]["Expression"]["SourceRef"].get("Source")
                        med = sel["Measure"].get("Property", "")
                        ent = alias.get(fuente)
                        if ent and med and not any(
                                mm["nombre"] == med
                                for mm in tabla_de(ent)["medidas"]):
                            tabla_de(ent)["medidas"].append({
                                "nombre": med, "expresion": "", "formato": "",
                                "descripcion": "", "carpeta": "", "tabla": ent})
        cat.tablas = list(tablas.values())
        return cat

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def tabla(self, nombre: str) -> dict | None:
        objetivo = _norm(nombre)
        for t in self.tablas:
            if _norm(t["nombre"]) == objetivo:
                return t
        return None

    def medidas(self) -> list[dict]:
        return [m for t in self.tablas for m in t["medidas"]]

    def medida(self, nombre: str) -> dict | None:
        objetivo = _norm(nombre)
        for m in self.medidas():
            if _norm(m["nombre"]) == objetivo:
                return m
        return None

    def columnas(self, solo_visibles: bool = False) -> list[tuple[str, dict]]:
        pares = []
        for t in self.tablas:
            if t["interna"]:
                continue
            for c in t["columnas"]:
                if solo_visibles and (c["oculta"] or t["oculta"]):
                    continue
                pares.append((t["nombre"], c))
        return pares

    def existe_columna(self, tabla: str, columna: str) -> bool:
        t = self.tabla(tabla)
        if not t:
            return False
        objetivo = _norm(columna)
        return any(_norm(c["nombre"]) == objetivo for c in t["columnas"])

    def tabla_fechas(self) -> dict | None:
        """La tabla de calendario: marcada como Time, o por nombre/columna."""
        for t in self.tablas:
            if t["es_calendario"] and not t["interna"]:
                return t
        for t in self.tablas:
            if t["interna"]:
                continue
            if any(p in _norm(t["nombre"])
                   for p in ("calendario", "calendar", "fecha", "date", "tiempo")):
                return t
        for t in self.tablas:
            if t["interna"]:
                continue
            if any(c["tipo"] == "dateTime" and _norm(c["nombre"]) in
                   ("fecha", "date") for c in t["columnas"]):
                return t
        return None

    def columna_fecha(self) -> tuple[str, str] | None:
        t = self.tabla_fechas()
        if not t:
            return None
        for c in t["columnas"]:
            if c["tipo"] == "dateTime" or _norm(c["nombre"]) in ("fecha", "date"):
                return (t["nombre"], c["nombre"])
        return None

    # ------------------------------------------------------------------
    def buscar_columna(self, texto: str,
                       solo_numericas: bool = False) -> tuple[str, dict] | None:
        """
        Búsqueda difusa de una columna por texto libre. Puntúa igualdad exacta,
        subcadena y solapamiento de palabras — todo sin acentos ni mayúsculas.
        Devuelve (tabla, columna) o None: nunca inventa.
        """
        objetivo = _norm(texto)
        if not objetivo:
            return None
        # también en singular: «clientes» tiene que encontrar IdCliente
        singular = " ".join(p.rstrip("s") if len(p) > 3 else p
                            for p in objetivo.split())
        palabras = {p for cand in (objetivo, singular)
                    for p in cand.replace("_", " ").split()}
        mejor, mejor_puntaje = None, 0.0
        for nombre_t, c in self.columnas():
            if solo_numericas and c["tipo"] not in TIPOS_NUMERICOS:
                continue
            nc = _norm(c["nombre"])
            puntaje = 0.0
            if nc in (objetivo, singular):
                puntaje = 100
            elif any(cand in nc or nc in cand
                     for cand in (objetivo, singular)):
                puntaje = 60 + 20 * min(len(objetivo), len(nc)) / max(len(objetivo), len(nc))
            else:
                pc = set(nc.replace("_", " ").split())
                comunes = {p for p in palabras
                           if any(p in x or x in p for x in pc)}
                if comunes:
                    puntaje = 40 * len(comunes) / max(len(palabras), len(pc))
            if puntaje > mejor_puntaje:
                mejor, mejor_puntaje = (nombre_t, c), puntaje
        return mejor if mejor_puntaje >= 30 else None

    def buscar_medidas(self, texto: str) -> list[dict]:
        """
        Medidas candidatas para un pedido, de la más probable a la menos.

        Tres reglas, en orden:

        1. **Nombre completo** → esa medida y nada más. «% del total ·
           Importe» pedido entero devuelve exactamente esa.
        2. **Prefijo** → el nombre de la medida *empieza* con las palabras
           pedidas: «ventas» encuentra «Ventas Brutas USD». Que sea prefijo y
           no subcadena es lo que evita que «importe» agarre a «% del total ·
           Importe», donde la palabra está al final y el sentido es otro.
        3. **Nunca una medida ya derivada como base de otra derivación.** Con
           «Importe YTD» en el modelo, pedir «importe vs año anterior» daba la
           variación interanual de un acumulado: DAX impecable, número sin
           sentido — el peor error posible, porque nadie lo ve leyendo. Si lo
           que sobra del nombre es una marca de derivación (YTD, acumulado,
           vs AA, variación, ranking, media móvil…), la medida no califica
           como base y se cae a la columna, que es el camino seguro.

        Se devuelven todas las que pasan para que quien llama pueda avisar
        cuál eligió y qué alternativas había — un modelo con «Ventas Brutas
        USD» y «Ventas Netas USD» es ambiguo de verdad, y elegir en silencio
        es lo que hace que el número esté mal sin que nadie se entere.
        """
        objetivo = _palabras(texto)
        if not objetivo:
            return []

        medidas = self.medidas()
        exactas = [m for m in medidas if _palabras(m["nombre"]) == objetivo]
        if exactas:
            return exactas

        candidatas = []
        for m in medidas:
            palabras = _palabras(m["nombre"])
            if palabras[:len(objetivo)] != objetivo:
                continue
            sobra = palabras[len(objetivo):]
            if any(_es_derivada(p) for p in sobra):
                continue
            candidatas.append((len(sobra), m))
        # Menos palabras sobrantes = más cerca de lo pedido. A igualdad, el
        # orden del modelo, que es el que eligió quien lo armó.
        return [m for _, m in sorted(candidatas, key=lambda par: par[0])]

    def buscar_medida(self, texto: str) -> dict | None:
        """La mejor medida candidata, o None. Ver `buscar_medidas`."""
        candidatas = self.buscar_medidas(texto)
        return candidatas[0] if candidatas else None

    # ------------------------------------------------------------------
    def resumen(self) -> dict:
        visibles = [t for t in self.tablas if not t["interna"]]
        return {
            "nombre": self.nombre,
            "parcial": self.parcial,
            "tablas": len(visibles),
            "columnas": sum(len(t["columnas"]) for t in visibles),
            "medidas": len(self.medidas()),
            "relaciones": len(self.relaciones),
            "calculadas": sum(1 for t in visibles
                              for c in t["columnas"] if c["calculada"]),
            "tabla_fechas": (self.tabla_fechas() or {}).get("nombre", ""),
        }


# ==========================================================================
# Referencias dentro de una expresión DAX
# ==========================================================================
RE_TABLA_COL = re.compile(r"(?:'([^']+)'|([A-Za-z_][\w ]*?))\s*\[([^\[\]]+)\]")


def referencias_dax(expresion: str) -> dict:
    """
    Extrae del DAX las referencias Tabla[Columna] y las [Medida] sueltas.
    Aproximación léxica: suficiente para validar contra el catálogo.
    """
    texto = re.sub(r'"[^"]*"', '""', expresion or "")  # sin strings literales
    texto = re.sub(r"--[^\n]*|//[^\n]*", "", texto)     # sin comentarios
    columnas, ocupado = [], []
    for m in RE_TABLA_COL.finditer(texto):
        tabla = (m.group(1) or m.group(2) or "").strip()
        col = m.group(3).strip()
        if tabla:
            columnas.append((tabla, col))
            ocupado.append((m.start(3) - 1, m.end(3) + 1))
    medidas = []
    for m in re.finditer(r"\[([^\[\]]+)\]", texto):
        if any(a <= m.start() < b for a, b in ocupado):
            continue
        medidas.append(m.group(1).strip())
    return {"columnas": columnas, "medidas": medidas}


def validar_referencias(expresion: str, cat: Catalogo,
                        idioma: str = IDIOMA_DEFECTO) -> list[str]:
    """Devuelve la lista de referencias que NO existen en el modelo."""
    errores = []
    refs = referencias_dax(expresion)
    for tabla, col in refs["columnas"]:
        t = cat.tabla(tabla)
        if not t:
            errores.append(
                traducir("cat_tabla_inexistente", idioma).format(tabla=tabla))
        elif not cat.existe_columna(tabla, col):
            errores.append(traducir("cat_columna_inexistente", idioma).format(
                tabla=tabla, col=col))
    for med in refs["medidas"]:
        if not cat.medida(med):
            errores.append(
                traducir("cat_medida_inexistente", idioma).format(medida=med))
    return errores
