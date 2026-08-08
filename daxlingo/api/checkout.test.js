// El checkout es la puerta del dinero: si acepta un plan inventado o filtra
// el error crudo de MercadoPago, el problema es real. No hay red acá — se
// mockea `fetch`.
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
  method: metodo, body, headers: { host: "mvdaxlab.vercel.app",
                                   "x-forwarded-for": "10.0.0." + Math.floor(Math.random() * 250) },
});

beforeEach(() => {
  delete process.env.MP_ACCESS_TOKEN;
  delete process.env.MP_LINK_PROFESIONAL;
});

test("rechaza métodos que no son POST", async () => {
  const res = respuesta();
  await checkout(pedido({}, "GET"), res);
  assert.equal(res.codigo, 405);
});

test("rechaza un plan que no existe", async () => {
  const res = respuesta();
  await checkout(pedido({ plan: "gratis-total" }), res);
  assert.equal(res.codigo, 400);
  assert.equal(res.cuerpo.error, "plan_invalido");
});

test("sin token ni link configurado avisa que no hay medio de pago", async () => {
  const res = respuesta();
  await checkout(pedido({ plan: "profesional" }), res);
  assert.equal(res.codigo, 503);
  assert.equal(res.cuerpo.error, "medio_pago_no_configurado");
});

test("sin token pero con link de pago, devuelve el link", async () => {
  process.env.MP_LINK_PROFESIONAL = "https://mpago.la/abc123";
  const res = respuesta();
  await checkout(pedido({ plan: "profesional" }), res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.url, "https://mpago.la/abc123");
});

test("con token, crea la preferencia y devuelve init_point", async () => {
  process.env.MP_ACCESS_TOKEN = "token-de-prueba";
  let visto = null;
  const original = global.fetch;
  global.fetch = async (url, opciones) => {
    visto = { url, cuerpo: JSON.parse(opciones.body) };
    return { ok: true, json: async () => ({ init_point: "https://mp/pagar" }) };
  };
  try {
    const res = respuesta();
    await checkout(pedido({ plan: "estudio" }), res);
    assert.equal(res.codigo, 200);
    assert.equal(res.cuerpo.url, "https://mp/pagar");
    assert.match(visto.url, /checkout\/preferences$/);
    assert.equal(visto.cuerpo.metadata.plan, "estudio");
    // El precio viaja convertido, nunca en USD contra un collector uruguayo.
    assert.ok(visto.cuerpo.items[0].unit_price >= PLANES.estudio.usd);
  } finally { global.fetch = original; }
});

test("si MercadoPago falla, no filtra su respuesta al navegador", async () => {
  process.env.MP_ACCESS_TOKEN = "token-de-prueba";
  const original = global.fetch;
  global.fetch = async () => ({
    ok: false,
    json: async () => ({ message: "collector_id no habilitado", cause: [{ code: 2034 }] }),
  });
  try {
    const res = respuesta();
    await checkout(pedido({ plan: "profesional" }), res);
    assert.equal(res.codigo, 502);
    assert.deepEqual(res.cuerpo, { error: "mp_error" });
  } finally { global.fetch = original; }
});
