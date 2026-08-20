# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Configuración común de la suite.

Acá vive una sola cosa, y es importante: aislar el estado local.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def estado_aislado(tmp_path, monkeypatch):
    """
    Cada test corre con su propia carpeta de estado, vacía.

    `licencia.carpeta_estado()` usa `MVDAXLAB_DATOS` si está, y si no
    `~/.mvdaxlab` — donde vive `estado.json`, que guarda cuándo arrancó la
    prueba de 7 días. Sin este aislamiento, cualquier test que pase por el
    candado de licencia daba un resultado distinto según hacía cuánto se
    había abierto la app en esa máquina.

    No es teórico: el 20/8 cuatro tests empezaron a fallar con «Esta función
    necesita una licencia activa» sin que nadie tocara el código. La demo de
    esa máquina había arrancado el 11/8 y se venció en el medio. En CI
    seguían verdes, porque el runner nace sin ese archivo — que es la peor
    versión del problema: rojo en la máquina de quien programa, verde en el
    tablero, y la discusión sobre si «anda» pasa a depender de a quién le
    creés.

    Con la carpeta en `tmp_path`, la prueba arranca de cero en cada test y
    quedan siempre los 7 días completos. Los tests que necesitan OTRO estado
    —por ejemplo, comprobar que el candado corta con la demo vencida— siguen
    haciendo su propio `monkeypatch.setenv` después de este, y ganan ellos.
    """
    monkeypatch.setenv("MVDAXLAB_DATOS", str(tmp_path / "estado-mvdax"))
