// © 2026 Martín Viera. Todos los derechos reservados.

// MV DAX Lab · Guardado de ventas y descargas (Redis por REST).
//
// Hasta acá no se guardaba NADA: ni una venta, ni una descarga, ni una
// renovación. El dinero entraba a MercadoPago y del lado del producto no
// quedaba rastro, así que no había forma de saber cuántos clientes hay ni
// cuánto se facturó sin abrir el panel de MercadoPago a mano.
//
// Se usa la API REST y no un cliente: son dos `fetch` y así el proyecto
// sigue sin dependencias en `api/`, igual que el resto. Sirve tanto la
// integración de Vercel (KV_REST_API_*) como una cuenta de Upstash directa
// (UPSTASH_REDIS_REST_*) — se busca cualquiera de las dos.
//
// REGLA: sin almacén configurado, NADA se rompe. Cada escritura es un no-op
// que devuelve false y cada lectura devuelve null. El cobro, la licencia y
// la descarga funcionan igual; lo único que se pierde son las estadísticas.
// Un monitor caído no puede tumbar la venta.

const URL_BASE = process.env.KV_REST_API_URL ||
                 process.env.UPSTASH_REDIS_REST_URL || "";
const TOKEN = process.env.KV_REST_API_TOKEN ||
              process.env.UPSTASH_REDIS_REST_TOKEN || "";

// Claves:
//   venta:<id>     JSON de la venta (id de pago o de suscripción)
//   ventas         sorted set: score = epoch, member = id  → orden y rango
//   descargas:<id> contador de descargas de esa venta
const CLAVE_VENTA = (id) => `venta:${id}`;
const INDICE = "ventas";
const CLAVE_DESCARGAS = (id) => `descargas:${id}`;

function disponible() {
  return Boolean(URL_BASE && TOKEN);
}

// Un comando suelto o una tanda. Devuelve null ante cualquier problema:
// quien llama nunca tiene que envolver esto en try/catch.
async function ejecutar(comandos, esTanda) {
  if (!disponible()) return null;
  try {
    const r = await fetch(URL_BASE + (esTanda ? "/pipeline" : ""), {
      method: "POST",
      headers: {
        authorization: "Bearer " + TOKEN,
        "content-type": "application/json",
      },
      body: JSON.stringify(comandos),
    });
    if (!r.ok) {
      console.error("almacen", r.status, await r.text().catch(() => ""));
      return null;
    }
    const j = await r.json();
    return esTanda ? j.map((x) => x.result) : j.result;
  } catch (e) {
    console.error("almacen", e);
    return null;
  }
}

const uno = (...cmd) => ejecutar(cmd, false);
const tanda = (cmds) => ejecutar(cmds, true);

// Idempotente a propósito: MercadoPago reintenta el mismo webhook varias
// veces, y sin esto la misma venta se contaría dos o tres veces. `SET` pisa
// el JSON y `ZADD` con el mismo member solo actualiza el score, así que
// reprocesar no infla nada.
async function guardarVenta(venta) {
  if (!disponible() || !venta || !venta.id) return false;
  const cuando = venta.cuando || Math.floor(Date.now() / 1000);
  const r = await tanda([
    ["SET", CLAVE_VENTA(venta.id), JSON.stringify({ ...venta, cuando })],
    ["ZADD", INDICE, String(cuando), String(venta.id)],
  ]);
  return r !== null;
}

async function contarDescarga(id) {
  if (!disponible() || !id) return false;
  return (await uno("INCR", CLAVE_DESCARGAS(String(id)))) !== null;
}

// Las ventas más recientes primero, con su contador de descargas.
async function listarVentas(limite = 200) {
  if (!disponible()) return null;
  const ids = await uno("ZRANGE", INDICE, "0", String(limite - 1), "REV");
  // null y [] NO son lo mismo, y confundirlos era el bug: `null` es "el
  // almacén no contestó" y `[]` es "todavía no hay ventas". Devolver [] en
  // los dos casos hacía que un Redis caído se viera igual que un lunes
  // tranquilo — el monitor mostraría cero facturado como si fuera un dato.
  if (ids === null) return null;
  if (!ids.length) return [];

  const filas = await tanda([
    ...ids.map((id) => ["GET", CLAVE_VENTA(id)]),
    ...ids.map((id) => ["GET", CLAVE_DESCARGAS(id)]),
  ]);
  if (!filas) return null;

  const mitad = ids.length;
  return ids.map((id, i) => {
    let v = null;
    try { v = JSON.parse(filas[i]); } catch (e) { v = null; }
    // Una fila corrupta no puede tumbar el monitor entero: se muestra lo
    // que se sabe (el id) y se sigue.
    return { ...(v || { id }), descargas: Number(filas[mitad + i] || 0) };
  });
}

module.exports = {
  disponible, guardarVenta, contarDescarga, listarVentas,
  // exportados para los tests
  CLAVE_VENTA, CLAVE_DESCARGAS, INDICE,
};
