// Lo que se prueba acá es que NO se emite licencia sin pago aprobado.
const { test, beforeEach } = require("node:test");
const assert = require("node:assert/strict");

const verificarPago = require("./verificar-pago");
const { verificar } = require("./_licencia");

const SECRETO = "secreto-de-prueba";

function respuesta() {
  const r = {
    codigo: null, cuerpo: null,
    status(c) { r.codigo = c; return r; },
    json(o) { r.cuerpo = o; return r; },
  };
  return r;
}

const pedido = (id) => ({
  query: { payment_id: id },
  headers: { "x-forwarded-for": "10.1.0." + Math.floor(Math.random() * 250) },
});

beforeEach(() => {
  process.env.MP_ACCESS_TOKEN = "token";
  process.env.MVDAX_LICENSE_SECRET = SECRETO;
});

test("rechaza un payment_id que no es numérico", async () => {
  const res = respuesta();
  await verificarPago(pedido("../../admin"), res);
  assert.equal(res.codigo, 400);
});

test("pago aprobado ⇒ emite una licencia verificable", async () => {
  const original = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ status: "approved", metadata: { plan: "perpetua" },
                         payer: { email: "cliente@ejemplo.com" } }),
  });
  try {
    const res = respuesta();
    await verificarPago(pedido("123456"), res);
    assert.equal(res.cuerpo.aprobado, true);
    const payload = verificar(res.cuerpo.licencia, SECRETO);
    assert.equal(payload.plan, "perpetua");
    assert.equal(payload.equipos, 1);
    assert.equal(payload.email, "cliente@ejemplo.com");
  } finally { global.fetch = original; }
});

test("pago pendiente o rechazado ⇒ NO emite licencia", async () => {
  const original = global.fetch;
  for (const estado of ["pending", "rejected", "in_process", "cancelled"]) {
    global.fetch = async () => ({
      ok: true,
      json: async () => ({ status: estado, metadata: { plan: "perpetua" } }),
    });
    const res = respuesta();
    await verificarPago(pedido("123456"), res);
    assert.equal(res.cuerpo.aprobado, false, estado);
    assert.equal(res.cuerpo.licencia, null, estado);
  }
  global.fetch = original;
});

test("un plan que no está en el catálogo no genera licencia", async () => {
  const original = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ status: "approved", metadata: { plan: "inventado" } }),
  });
  try {
    const res = respuesta();
    await verificarPago(pedido("999"), res);
    assert.equal(res.cuerpo.aprobado, true);
    assert.equal(res.cuerpo.licencia, null);
  } finally { global.fetch = original; }
});
