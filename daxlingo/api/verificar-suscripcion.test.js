// © 2026 Martín Viera. Todos los derechos reservados.

// La suscripción se corta sola: cuando el cliente la da de baja, la licencia
// deja de renovarse y caduca. Lo que se prueba acá es que una suscripción que
// NO está autorizada no consiga clave, y que la que sí lo está la reciba con
// vencimiento (si saliera sin `exp`, un mes pagado valdría para siempre).
const { test, beforeEach } = require("node:test");
const assert = require("node:assert/strict");

const verificarSuscripcion = require("./verificar-suscripcion");
const { verificar } = require("./_licencia");
const { DIAS_MENSUAL } = require("./_planes");

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
  query: { preapproval_id: id },
  headers: { "x-forwarded-for": "10.2.0." + Math.floor(Math.random() * 250) },
});

beforeEach(() => {
  process.env.MP_ACCESS_TOKEN = "token";
  process.env.MVDAX_LICENSE_SECRET = SECRETO;
});

test("rechaza un preapproval_id con forma inválida", async () => {
  for (const malo of ["", "../../admin", "x", "a".repeat(80), "con espacio"]) {
    const res = respuesta();
    await verificarSuscripcion(pedido(malo), res);
    assert.equal(res.codigo, 400, malo);
  }
});

test("suscripción autorizada ⇒ licencia con vencimiento", async () => {
  const original = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ status: "authorized", external_reference: "mensual",
                         payer_email: "cliente@ejemplo.com" }),
  });
  try {
    const res = respuesta();
    await verificarSuscripcion(pedido("2c938084726fca480172750000000000"), res);
    assert.equal(res.cuerpo.vigente, true);

    const payload = verificar(res.cuerpo.licencia, SECRETO);
    assert.equal(payload.plan, "mensual");
    assert.equal(payload.email, "cliente@ejemplo.com");
    assert.ok(payload.exp, "la licencia mensual TIENE que vencer");
    const dias = (payload.exp - payload.iat) / 86400;
    assert.equal(Math.round(dias), DIAS_MENSUAL);
  } finally { global.fetch = original; }
});

test("suscripción cancelada, pausada o pendiente ⇒ sin licencia", async () => {
  const original = global.fetch;
  for (const estado of ["cancelled", "paused", "pending"]) {
    global.fetch = async () => ({
      ok: true,
      json: async () => ({ status: estado, external_reference: "mensual" }),
    });
    const res = respuesta();
    await verificarSuscripcion(pedido("2c93808472500000"), res);
    assert.equal(res.cuerpo.vigente, false, estado);
    assert.equal(res.cuerpo.licencia, null, estado);
  }
  global.fetch = original;
});

test("una renovación emite una clave nueva, no la misma de antes", async () => {
  const original = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ status: "authorized", external_reference: "mensual" }),
  });
  try {
    const a = respuesta();
    await verificarSuscripcion(pedido("2c93808472500000"), a);
    const payloadA = verificar(a.cuerpo.licencia, SECRETO);
    // Se simula que pasó un mes: la clave nueva vence más tarde que la vieja.
    const reloj = Date.now;
    Date.now = () => reloj() + 31 * 86400 * 1000;
    const b = respuesta();
    await verificarSuscripcion(pedido("2c93808472500000"), b);
    Date.now = reloj;
    const payloadB = verificar(b.cuerpo.licencia, SECRETO);
    assert.ok(payloadB.exp > payloadA.exp);
    assert.notEqual(a.cuerpo.licencia, b.cuerpo.licencia);
  } finally { global.fetch = original; }
});

test("sin secreto configurado no se inventa una licencia", async () => {
  delete process.env.MVDAX_LICENSE_SECRET;
  const original = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ status: "authorized", external_reference: "mensual" }),
  });
  try {
    const res = respuesta();
    await verificarSuscripcion(pedido("2c93808472500000"), res);
    assert.equal(res.cuerpo.vigente, true);
    assert.equal(res.cuerpo.licencia, null);
  } finally { global.fetch = original; }
});
