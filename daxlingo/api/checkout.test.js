// El checkout es la puerta del dinero: si acepta una modalidad inventada,
// manda la suscripción al endpoint del pago único o filtra el error crudo de
// MercadoPago, el problema es real. No hay red acá — se mockea `fetch`.
const { test, beforeEach } = require("node:test");
const assert = require("node:assert/strict");

const checkout = require("./checkout");
const { PLANES } = require("./_planes");

function respuesta() {
  const r = {
    codigo: null, cuerpo: null,
    status(c) { r.codigo = c; return r; },
    json(o) { r.cuerpo = o; return r; },
  };
  return r;
}

const pedido = (body, metodo = "POST") => ({
  method: metodo,
  body,
  headers: {
    host: "mvdaxlab.vercel.app",
    "x-forwarded-for": "10.0.0." + Math.floor(Math.random() * 250),
  },
});

beforeEach(() => {
  delete process.env.MP_ACCESS_TOKEN;
  delete process.env.MP_LINK_PERPETUA;
  delete process.env.MP_LINK_MENSUAL;
});

test("solo hay dos modalidades y las dos desbloquean lo mismo", () => {
  assert.deepEqual(Object.keys(PLANES).sort(), ["mensual", "perpetua"]);
  assert.equal(PLANES.perpetua.usd, 99);
  assert.equal(PLANES.mensual.usd, 10);
  assert.equal(PLANES.perpetua.recurrente, false);
  assert.equal(PLANES.mensual.recurrente, true);
  // Mismo producto: ninguna modalidad da más equipos que la otra.
  assert.equal(PLANES.perpetua.equipos, PLANES.mensual.equipos);
});

test("rechaza métodos que no son POST", async () => {
  const res = respuesta();
  await checkout(pedido({}, "GET"), res);
  assert.equal(res.codigo, 405);
});

test("rechaza una modalidad que no existe", async () => {
  const res = respuesta();
  await checkout(pedido({ plan: "gratis-total" }), res);
  assert.equal(res.codigo, 400);
  assert.equal(res.cuerpo.error, "plan_invalido");
});

test("sin token ni link configurado avisa que no hay medio de pago", async () => {
  const res = respuesta();
  await checkout(pedido({ plan: "perpetua" }), res);
  assert.equal(res.codigo, 503);
  assert.equal(res.cuerpo.error, "medio_pago_no_configurado");
});

test("sin token pero con link de pago, devuelve el link", async () => {
  process.env.MP_LINK_MENSUAL = "https://mpago.la/abc123";
  const res = respuesta();
  await checkout(pedido({ plan: "mensual" }), res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.url, "https://mpago.la/abc123");
});

test("pago único: crea una PREFERENCIA y devuelve init_point", async () => {
  process.env.MP_ACCESS_TOKEN = "token-de-prueba";
  let visto = null;
  const original = global.fetch;
  global.fetch = async (url, opciones) => {
    visto = { url, cuerpo: JSON.parse(opciones.body) };
    return { ok: true, json: async () => ({ init_point: "https://mp/pagar" }) };
  };
  try {
    const res = respuesta();
    await checkout(pedido({ plan: "perpetua" }), res);
    assert.equal(res.codigo, 200);
    assert.equal(res.cuerpo.url, "https://mp/pagar");
    assert.equal(res.cuerpo.recurrente, false);
    assert.match(visto.url, /checkout\/preferences$/);
    assert.equal(visto.cuerpo.metadata.plan, "perpetua");
    // El precio viaja convertido, nunca en USD contra un collector uruguayo.
    assert.ok(visto.cuerpo.items[0].unit_price >= PLANES.perpetua.usd);
  } finally { global.fetch = original; }
});

test("mensual: crea un PREAPPROVAL con la recurrencia mensual", async () => {
  process.env.MP_ACCESS_TOKEN = "token-de-prueba";
  let visto = null;
  const original = global.fetch;
  global.fetch = async (url, opciones) => {
    visto = { url, cuerpo: JSON.parse(opciones.body) };
    return { ok: true, json: async () => ({ init_point: "https://mp/suscribir" }) };
  };
  try {
    const res = respuesta();
    await checkout(pedido({ plan: "mensual" }), res);
    assert.equal(res.codigo, 200);
    assert.equal(res.cuerpo.recurrente, true);
    assert.match(visto.url, /\/preapproval$/);
    assert.equal(visto.cuerpo.auto_recurring.frequency, 1);
    assert.equal(visto.cuerpo.auto_recurring.frequency_type, "months");
    // Un preapproval no tiene metadata: la modalidad va en external_reference.
    assert.equal(visto.cuerpo.external_reference, "mensual");
  } finally { global.fetch = original; }
});

test("acepta sandbox_init_point cuando MercadoPago no manda init_point", async () => {
  process.env.MP_ACCESS_TOKEN = "token-de-prueba";
  const original = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ sandbox_init_point: "https://sandbox/mp" }),
  });
  try {
    const res = respuesta();
    await checkout(pedido({ plan: "mensual" }), res);
    assert.equal(res.cuerpo.url, "https://sandbox/mp");
  } finally { global.fetch = original; }
});

test("si MercadoPago falla, no filtra su respuesta al navegador", async () => {
  process.env.MP_ACCESS_TOKEN = "token-de-prueba";
  const original = global.fetch;
  global.fetch = async () => ({
    ok: false,
    json: async () => ({ message: "collector_id no habilitado",
                         cause: [{ code: 2034 }] }),
  });
  try {
    const res = respuesta();
    await checkout(pedido({ plan: "perpetua" }), res);
    assert.equal(res.codigo, 502);
    assert.deepEqual(res.cuerpo, { error: "mp_error" });
  } finally { global.fetch = original; }
});
