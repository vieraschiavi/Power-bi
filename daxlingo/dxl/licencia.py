# © 2026 Martín Viera. Todos los derechos reservados.

"""
MV DAX Lab · Licencias, ediciones y prueba de 7 días.

Formato de clave — el mismo esquema que emite `api/verify-payment.js` después
de confirmar el pago con MercadoPago:

    MVDAX1.<payload_base64url>.<hmac_sha256_base64url>

El payload lleva `plan`, `pid` (id de pago), `email`, `iat` y opcionalmente
`exp`. La verificación es HMAC-SHA256 con comparación en tiempo constante.

Sobre qué protege esto y qué no — sin vueltas: HMAC es simétrico, así que la
clave que verifica es la misma que firma. En la app de escritorio esa clave
viaja horneada en el build, y alguien que la extraiga puede fabricarse una
licencia. Lo que sí impide es el caso real y masivo: pasarle la clave a otro,
inventarla a mano o editar la fecha de vencimiento. El corte de verdad está
del lado del servidor — `verify-payment.js` consulta la API de MercadoPago y
solo firma si el pago está aprobado. Un esquema asimétrico (Ed25519) dejaría
únicamente la clave pública en el cliente; no se usa acá para no sumar la
dependencia `cryptography` al motor, que hoy corre con pura stdlib.

Ediciones
---------
  owner        todo desbloqueado, sin vencimiento y sin pedir licencia.
  profesional  todo desbloqueado mientras la licencia esté vigente.
  demo         7 días con todo; después quedan abiertas las funciones de
               lectura y aprendizaje (analizador, explicador, academia).

La edición viene HORNEADA en el paquete (`edicion.json`, lo escribe
`desktop/scripts/build-instaladores.js`). En las ediciones vendidas queda
además bloqueada (`bloqueada: true`) para que la variable de entorno no pueda
convertir una copia comercial en owner.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

PREFIJO = "MVDAX1"
DIAS_DEMO = 7

EDICIONES = ("owner", "profesional", "demo")

# Funciones que exigen licencia vigente. Las que NO están acá quedan siempre
# abiertas: analizador, explicador, relaciones, academia y carga de modelos —
# a propósito, para que la demo vencida siga siendo útil y honesta.
FUNCIONES_CON_LICENCIA = frozenset({
    "generar", "transformar", "exportar", "fabric", "overlay",
})


# ==========================================================================
# Firma y verificación
# ==========================================================================
def _b64u(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode().rstrip("=")


def _des_b64u(texto: str) -> bytes:
    relleno = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto + relleno)


def firmar(payload: dict, secreto: str) -> str:
    cuerpo = _b64u(json.dumps(payload, separators=(",", ":"),
                             ensure_ascii=False).encode())
    firma = _b64u(hmac.new(secreto.encode(), cuerpo.encode(),
                           hashlib.sha256).digest())
    return f"{PREFIJO}.{cuerpo}.{firma}"


def verificar(clave: str, secreto: str) -> dict | None:
    """Devuelve el payload si la firma es válida y no venció; si no, None."""
    if not isinstance(clave, str):
        return None
    partes = clave.strip().split(".")
    if len(partes) != 3 or partes[0] != PREFIJO:
        return None
    cuerpo, firma = partes[1], partes[2]
    esperada = _b64u(hmac.new(secreto.encode(), cuerpo.encode(),
                              hashlib.sha256).digest())
    # Comparación en bytes, no en str: `compare_digest` exige ASCII puro para
    # argumentos str y tira TypeError con cualquier otra cosa — pegar una
    # clave con un caracter no-ASCII no tiene por qué reventar la pestaña de
    # Licencia con un traceback, tiene que decir «licencia inválida».
    if not hmac.compare_digest(firma.encode(), esperada.encode()):
        return None
    try:
        payload = json.loads(_des_b64u(cuerpo).decode())
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        return None
    return payload


# ==========================================================================
# Estado local (prueba, licencia activada, preferencias)
# ==========================================================================
def carpeta_estado() -> Path:
    base = os.environ.get("MVDAXLAB_DATOS", "")
    ruta = Path(base) if base else Path.home() / ".mvdaxlab"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _archivo_estado() -> Path:
    return carpeta_estado() / "estado.json"


def leer_estado() -> dict:
    archivo = _archivo_estado()
    if not archivo.exists():
        return {}
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def guardar_estado(datos: dict) -> None:
    _archivo_estado().write_text(
        json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def _edicion_horneada() -> dict:
    """
    Lee `edicion.json` del paquete. Lo escribe el build por edición; si no
    está (repo clonado, desarrollo), asumimos demo NO bloqueada.

    El sello EMPAQUETADO (`resources/app/` o la raíz del portable) va
    primero; `MVDAXLAB_EDICION_ARCHIVO` es el mecanismo con el que
    `lanzador.py`/Electron le dicen al motor DÓNDE está ese sello — no un
    permiso para que el usuario apunte la variable a un archivo propio y se
    invente una edición. Si el sello empaquetado existe, la variable no se
    consulta para nada.
    """
    candidatos = [
        Path(__file__).resolve().parents[1] / "edicion.json",
        Path(__file__).resolve().parents[2] / "edicion.json",
    ]
    for c in candidatos:
        if c.exists():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
    desde_env = Path(os.environ.get("MVDAXLAB_EDICION_ARCHIVO", ""))
    if desde_env.name and desde_env.exists():
        try:
            return json.loads(desde_env.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"edicion": "demo", "bloqueada": False}


_SECRETO_DEV = "mvdaxlab-secreto-de-desarrollo-cambiar-en-el-build"

# Si una copia SELLADA (bloqueada: true) sale sin secreto horneado —el
# empaquetador se corrió sin MVDAX_LICENSE_SECRET, por ejemplo—, NO hay que
# caer al secreto de desarrollo: es público (está en el código fuente), así
# que cualquiera podría firmar una licencia válida contra todas las copias
# que tengan ese mismo agujero — un keygen distribuible. Se genera uno al
# azar por proceso en su lugar: la copia queda sin poder validar NINGUNA
# licencia (ni siquiera una legítima), lo cual es ruidoso —el cliente se
# queja de que su licencia no activa— y por eso mismo seguro: un build roto
# tiene que fallar cerrado, no abierto.
_SECRETO_SELLO_ROTO = secrets.token_hex(32)


def secreto_licencia() -> str:
    """
    Clave de verificación. En el build se hornea en `edicion.json`; en
    desarrollo sale del entorno. El valor por defecto es deliberadamente
    obvio: una copia sin configurar no valida licencias reales.

    En una edición sellada (`bloqueada: true`) el secreto horneado manda
    siempre, igual que `edicion_actual()` ya hace con la edición: si la
    variable de entorno pudiera pisarlo, alcanzaría con
    MVDAX_LICENSE_SECRET + `firmar()` para activar cualquier copia vendida
    con una licencia falsa — el mismo agujero que el bloqueo de edición
    tapa, pero por la puerta de al lado.
    """
    horneada = _edicion_horneada()
    if horneada.get("bloqueada"):
        return horneada.get("secreto") or _SECRETO_SELLO_ROTO
    return (os.environ.get("MVDAX_LICENSE_SECRET")
            or horneada.get("secreto")
            or _SECRETO_DEV)


# ==========================================================================
# Estado de la licencia
# ==========================================================================
class Estado:
    """Resultado de evaluar edición + licencia + prueba, todo junto."""

    def __init__(self, edicion: str, activa: bool, dias_restantes: int | None,
                 motivo: str, payload: dict | None = None) -> None:
        self.edicion = edicion
        self.activa = activa
        self.dias_restantes = dias_restantes
        self.motivo = motivo            # 'owner' | 'licencia' | 'demo' | 'vencida'
        self.payload = payload or {}

    def permite(self, funcion: str) -> bool:
        if funcion not in FUNCIONES_CON_LICENCIA:
            return True
        return self.activa

    def __repr__(self) -> str:  # pragma: no cover — ayuda al depurar
        return (f"Estado(edicion={self.edicion!r}, activa={self.activa}, "
                f"dias={self.dias_restantes}, motivo={self.motivo!r})")


def edicion_actual() -> str:
    horneada = _edicion_horneada()
    if horneada.get("bloqueada"):
        # En las ediciones vendidas la variable de entorno NO manda: si no,
        # el cliente pone MVDAX_EDICION=owner y se lleva el producto entero.
        return str(horneada.get("edicion", "demo"))
    pedida = os.environ.get("MVDAX_EDICION", "").strip().lower()
    if pedida in EDICIONES:
        return pedida
    return str(horneada.get("edicion", "demo"))


def dias_demo_restantes(ahora: float | None = None) -> int:
    """
    Días que quedan de prueba. La cuenta arranca en el primer uso y se
    persiste; si el archivo se borra, arranca de nuevo — es una demo, no una
    caja fuerte, y decirlo es más honesto que fingir lo contrario.
    """
    ahora = ahora if ahora is not None else time.time()
    estado = leer_estado()
    inicio = estado.get("demo_inicio")
    if not inicio:
        inicio = ahora
        estado["demo_inicio"] = inicio
        guardar_estado(estado)
    transcurridos = (ahora - float(inicio)) / 86400.0
    return max(0, int(DIAS_DEMO - transcurridos + 0.999))


def evaluar(clave: str | None = None, ahora: float | None = None) -> Estado:
    """
    Estado efectivo de la instalación. `clave` permite evaluar una licencia
    puntual sin activarla (para el botón «Activar»).
    """
    ahora = ahora if ahora is not None else time.time()
    edicion = edicion_actual()
    if edicion == "owner":
        return Estado("owner", True, None, "owner")

    guardada = clave if clave is not None else leer_estado().get("licencia")
    if guardada:
        payload = verificar(guardada, secreto_licencia())
        if payload:
            exp = payload.get("exp")
            dias = (int((float(exp) - ahora) / 86400) + 1) if exp else None
            return Estado("profesional", True, dias, "licencia", payload)

    # La prueba de 7 días es de la edición DEMO y de nadie más.
    #
    # Antes caía acá cualquier edición sin clave, incluida `profesional` — la
    # que se vende. O sea que el instalador del producto pago le regalaba una
    # semana entera a cualquiera que lo consiguiera, sin pasar por la caja y
    # sin dejar rastro. Con la demo abierta al público eso daba más o menos
    # igual; con la demo entregada a pedido, era la puerta que dejaba sin
    # sentido cerrar la otra.
    #
    # Ahora la edición vendida sin licencia válida no desbloquea nada. Eso
    # permite publicar su instalador sin regalar el producto: sirve para que
    # el que compró lo baje solo, y no le sirve a nadie más.
    if edicion == "demo":
        dias = dias_demo_restantes(ahora)
        if dias > 0:
            return Estado("demo", True, dias, "demo")
        return Estado("demo", False, 0, "vencida")

    return Estado(edicion, False, 0, "sin_licencia")


def activar(clave: str) -> Estado:
    """Valida y guarda una licencia. Lanza ValueError si no es válida."""
    payload = verificar(clave, secreto_licencia())
    if not payload:
        raise ValueError("licencia_invalida")
    estado = leer_estado()
    estado["licencia"] = clave.strip()
    estado["licencia_activada"] = time.time()
    guardar_estado(estado)
    return evaluar()


def desactivar() -> None:
    estado = leer_estado()
    estado.pop("licencia", None)
    estado.pop("licencia_activada", None)
    guardar_estado(estado)


# ==========================================================================
# Preferencias (idioma, proveedor de IA elegido)
# ==========================================================================
def preferencia(clave: str, defecto=None):
    return leer_estado().get("prefs", {}).get(clave, defecto)


def guardar_preferencia(clave: str, valor) -> None:
    estado = leer_estado()
    prefs = estado.setdefault("prefs", {})
    prefs[clave] = valor
    guardar_estado(estado)
