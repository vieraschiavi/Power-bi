"""
MV DAX Lab · Academia DAX: motor de práctica gamificada.

Los ejercicios viven en datos/ejercicios.json, agrupados en niveles con XP.
La verificación es local y determinística: se normaliza el DAX (mayúsculas de
funciones, espacios, comillas de tabla) y se compara contra la respuesta
canónica y sus variantes aceptadas — más patrones regex para respuestas que
admiten formas distintas. No hace falta IA ni conexión para practicar.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RUTA_EJERCICIOS = Path(__file__).resolve().parent.parent / "datos" / "ejercicios.json"

NIVELES = [
    (0, "🥚 Novato"),
    (100, "🐣 Aprendiz"),
    (250, "🦉 Analista"),
    (450, "🧠 Modelador"),
    (700, "🏆 Maestro DAX"),
]


def cargar_ejercicios(ruta: str | Path | None = None) -> list[dict]:
    ruta = Path(ruta) if ruta else RUTA_EJERCICIOS
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return datos["ejercicios"]


def normalizar(dax: str) -> str:
    """
    Lleva una expresión DAX a forma canónica para comparar:
    sin comentarios, un solo espacio, funciones en mayúsculas, sin comillas
    en nombres de tabla simples, sin espacios alrededor de ( ) , [ ].
    """
    texto = re.sub(r"--[^\n]*|//[^\n]*", " ", dax or "")
    texto = re.sub(r"/\*.*?\*/", " ", texto, flags=re.DOTALL)
    # tablas con comillas innecesarias: 'Ventas'[x] → Ventas[x]
    texto = re.sub(r"'([A-Za-z_][A-Za-z0-9_]*)'\[", r"\1[", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = re.sub(r"\s*([\(\),\[\]])\s*", r"\1", texto)
    texto = re.sub(r"\s*(<=|>=|<>|[=+\-*/<>])\s*", r"\1", texto)
    # funciones a mayúsculas (palabra seguida de paréntesis)
    texto = re.sub(r"\b([A-Za-z][A-Za-z0-9\.]*)\(",
                   lambda m: m.group(1).upper() + "(", texto)
    # el resto de identificadores compara case-insensitive
    return texto.lower()


def verificar(ejercicio: dict, respuesta: str) -> dict:
    """
    Devuelve {'correcto': bool, 'detalle': str}. Compara contra la solución,
    las variantes `acepta` (igualdad normalizada) y los `patrones` (regex
    sobre el DAX normalizado).
    """
    intento = normalizar(respuesta)
    if not intento:
        return {"correcto": False, "detalle": "Escribí tu expresión DAX."}

    candidatas = [ejercicio["solucion"]] + ejercicio.get("acepta", [])
    for c in candidatas:
        if intento == normalizar(c):
            return {"correcto": True,
                    "detalle": "¡Correcto! " + ejercicio.get("moraleja", "")}
    for patron in ejercicio.get("patrones", []):
        if re.fullmatch(patron, intento):
            return {"correcto": True,
                    "detalle": "¡Correcto! " + ejercicio.get("moraleja", "")}

    # diagnóstico suave: ¿al menos usó la función esperada?
    funciones = set(re.findall(r"\b([A-Z][A-Z0-9]{2,})\(",
                               normalizar(ejercicio["solucion"]).upper()))
    usadas = set(re.findall(r"\b([A-Z][A-Z0-9]{2,})\(", intento.upper()))
    if funciones and not (funciones & usadas):
        principal = sorted(funciones)[0]
        return {"correcto": False,
                "detalle": f"Pista: la solución esperada usa {principal}. "
                           + ejercicio.get("pista", "")}
    return {"correcto": False,
            "detalle": "Cerca, pero no es equivalente. "
                       + ejercicio.get("pista", "")}


def nivel_por_xp(xp: int) -> str:
    actual = NIVELES[0][1]
    for umbral, nombre in NIVELES:
        if xp >= umbral:
            actual = nombre
    return actual


def proximo_nivel(xp: int) -> tuple[str, int] | None:
    for umbral, nombre in NIVELES:
        if xp < umbral:
            return nombre, umbral - xp
    return None
