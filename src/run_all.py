# © 2026 Martín Viera. Todos los derechos reservados.

"""
Orquestador: corre el pipeline completo de punta a punta.

    python src/run_all.py

Regenera todo desde cero de forma reproducible (semilla fija en config.py):
dataset origen → limpieza y modelo estrella → modelo de devoluciones →
modelo de ofertas → motor de IA de precios.

Si un paso falla, corta ahí y muestra el error. No sigue con datos a medias:
un pipeline que "termina igual" con un paso roto es peor que uno que falla.
"""
from __future__ import annotations

import runpy
import sys
import time
from pathlib import Path

PASOS = [
    ("01_generar_dataset.py", "Simulación de sistemas origen"),
    ("02_transformar.py", "Data Steward: calidad + modelo estrella"),
    ("03_ml_devoluciones.py", "ML: devoluciones (clasificación + forecast)"),
    ("04_ml_ofertas.py", "ML: ofertas (clasificación + forecast)"),
    ("05_ia_precios.py", "IA: precio y producto óptimos por segmento"),
]


def main() -> int:
    aqui = Path(__file__).resolve().parent
    sys.path.insert(0, str(aqui))
    t0 = time.perf_counter()

    for i, (archivo, titulo) in enumerate(PASOS, start=1):
        print("\n" + "=" * 78)
        print(f"  {i}/{len(PASOS)}  {titulo}")
        print("=" * 78)
        t = time.perf_counter()
        try:
            runpy.run_path(str(aqui / archivo), run_name="__main__")
        except Exception as exc:  # noqa: BLE001 — se quiere el corte explícito
            print(f"\n  FALLÓ {archivo}: {type(exc).__name__}: {exc}")
            return 1
        print(f"\n  ({time.perf_counter() - t:.1f}s)")

    print("\n" + "=" * 78)
    print(f"  Pipeline completo en {time.perf_counter() - t0:.1f}s")
    print("  Modelo estrella listo en data/star/ para conectar desde Power BI.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
