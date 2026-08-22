// © 2026 Martín Viera. Todos los derechos reservados.

// Lo que se prueba acá: que el monitor no se abra sin token —incluido el
// caso peligroso de "todavía no configuré el token"— y que las cuentas que
// muestra sean las correctas.
const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");

function respuesta() {
  const r = {
    codigo: null, cuerpo: null, cabeceras: {},
    status(c) { r.codigo = c; return r; },
    json(o) { r.cuerpo = o; return r; },
    setHeader(k, v) { r.cabeceras[k.toLowerCase()] = v; },
    end() {},
  };
  return r;
}


// Cada petición desde una IP distinta: el limitador es de 10 por minuto y por
// IP, y con todos los tests compartiendo la misma se agotaba solo (429). Que
// haya saltado acá es señal de que el freno funciona.
let nIp = 0;
function pedido(cabeceras = {}, query = {}) {
  nIp += 1;
  return { headers: { "x-forwarded-for": `10.0.0.${nIp}`, ...cabeceras }, query };
}

const TOKEN = "token-del-dueno-larguisimo-y-secreto";
let fetchOriginal;

// El módulo lee la config del almacén al importarse, así que hay que
// ponerla ANTES y recargarlo en cada test.
function cargar({ conAlmacen = true } = {}) {
  delete require.cache[require.resolve("./metricas")];
  delete require.cache[require.resolve("./_almacen")];
  if (conAlmacen) {
    process.env.KV_REST_API_URL = "https://falso.upstash.io";
    process.env.KV_REST_API_TOKEN = "token-falso";
  } else {
    delete process.env.KV_REST_API_URL;
    delete process.env.KV_REST_API_TOKEN;
  }
  return require("./metricas");
}

beforeEach(() => {
  fetchOriginal = global.fetch;
  process.env.MVDAX_OWNER_TOKEN = TOKEN;
  delete process.env.MVDAX_COMISION_PCT;
});
afterEach(() => {
  global.fetch = fetchOriginal;
  delete require.cache[require.resolve("./metricas")];
  delete require.cache[require.resolve("./_almacen")];
});

// Simula el Redis REST: primero el ZRANGE con los ids, después la tanda con
// los GET de cada venta y de cada contador.
function almacenCon(ventas) {
  const ids = ventas.map((v) => String(v.id));
  global.fetch = async (url, opciones) => {
    const cmd = JSON.parse(opciones.body);
    if (!String(url).endsWith("/pipeline")) {
      return { ok: true, json: async () => ({ result: ids }) };  // ZRANGE
    }
    const resultados = [
      ...ventas.map((v) => ({ result: JSON.stringify(v) })),
      ...ventas.map((v) => ({ result: String(v.descargas || 0) })),
    ];
    assert.equal(cmd.length, resultados.length);
    return { ok: true, json: async () => resultados };
  };
}

test("sin token en la petición: 401", async () => {
  const metricas = cargar();
  const res = respuesta();
  await metricas(pedido(), res);
  assert.equal(res.codigo, 401);
});

test("con un token equivocado: 401", async () => {
  const metricas = cargar();
  for (const malo of ["x", TOKEN + "!", TOKEN.slice(0, -1), ""]) {
    const res = respuesta();
    await metricas(pedido({ authorization: "Bearer " + malo }), res);
    assert.equal(res.codigo, 401, `no debería aceptar «${malo}»`);
  }
});

test("SIN MVDAX_OWNER_TOKEN configurado queda CERRADO, no abierto", async () => {
  // El error clásico: "si no hay contraseña, dejá pasar". Sería publicar los
  // mails de todos los clientes y la facturación.
  delete process.env.MVDAX_OWNER_TOKEN;
  const metricas = cargar();
  const res = respuesta();
  await metricas(pedido({ authorization: "Bearer " }), res);
  assert.equal(res.codigo, 401);
});

test("el token también se acepta por query, para el enlace directo", async () => {
  const metricas = cargar();
  almacenCon([]);
  const res = respuesta();
  await metricas(pedido({}, { token: TOKEN }), res);
  assert.equal(res.codigo, 200);
});

test("sin base de datos lo dice, en vez de mostrar ceros como si fueran datos", async () => {
  const metricas = cargar({ conAlmacen: false });
  const res = respuesta();
  await metricas(pedido({ authorization: "Bearer " + TOKEN }), res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.configurado, false);
  assert.match(res.cuerpo.nota, /KV_REST_API_URL/);
});

test("las cuentas salen bien", async () => {
  const metricas = cargar();
  almacenCon([
    { id: "1", plan: "perpetua", email: "ana@x.com", usd: 99, cuando: 1700000000, descargas: 2 },
    { id: "2", plan: "mensual", email: "ana@x.com", usd: 10, cuando: 1700000100, descargas: 1 },
    { id: "3", plan: "perpetua", email: "beto@x.com", usd: 99, cuando: 1700000200, descargas: 0 },
  ]);
  const res = respuesta();
  await metricas(pedido({ authorization: "Bearer " + TOKEN }), res);

  assert.equal(res.cuerpo.ventas, 3);
  // Ana compró dos veces: son 3 ventas pero 2 clientes.
  assert.equal(res.cuerpo.clientes, 2);
  assert.equal(res.cuerpo.descargas, 3);
  assert.deepEqual(res.cuerpo.porPlan, { perpetua: 2, mensual: 1 });
  assert.equal(res.cuerpo.dinero.brutoUsd, 208);
  // 5,99% + 22% de IVA sobre la comisión = 7,3078% → 15,20 sobre 208.
  assert.equal(res.cuerpo.dinero.comisionPct, 7.31);
  assert.equal(res.cuerpo.dinero.netoEstimadoUsd, 192.8);
  assert.equal(res.cabeceras["cache-control"], "no-store");
});

test("la comisión se puede pisar por entorno", async () => {
  process.env.MVDAX_COMISION_PCT = "10";
  const metricas = cargar();
  almacenCon([{ id: "1", plan: "perpetua", email: "a@x.com", usd: 100, cuando: 1 }]);
  const res = respuesta();
  await metricas(pedido({ authorization: "Bearer " + TOKEN }), res);
  assert.equal(res.cuerpo.dinero.comisionUsd, 10);
  assert.equal(res.cuerpo.dinero.netoEstimadoUsd, 90);
});

test("una fila corrupta no tumba el monitor entero", async () => {
  const metricas = cargar();
  global.fetch = async (url, opciones) => {
    if (!String(url).endsWith("/pipeline")) {
      return { ok: true, json: async () => ({ result: ["1", "2"] }) };
    }
    return { ok: true, json: async () => [
      { result: "{esto no es json" },
      { result: JSON.stringify({ id: "2", plan: "perpetua", email: "b@x.com", usd: 99 }) },
      { result: "0" }, { result: "5" },
    ] };
  };
  const res = respuesta();
  await metricas(pedido({ authorization: "Bearer " + TOKEN }), res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.ventas, 2);
  assert.equal(res.cuerpo.dinero.brutoUsd, 99);   // la corrupta no suma
});

test("si el almacén no responde, lo dice; no inventa un cero", async () => {
  const metricas = cargar();
  global.fetch = async () => ({ ok: false, status: 500, text: async () => "" });
  const res = respuesta();
  await metricas(pedido({ authorization: "Bearer " + TOKEN }), res);
  assert.equal(res.codigo, 502);
  assert.equal(res.cuerpo.error, "almacen_no_responde");
});
