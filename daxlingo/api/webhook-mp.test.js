// © 2026 Martín Viera. Todos los derechos reservados.

// Lo que se prueba acá: que un aviso falso no pueda inventar una venta, que
// un pago real y aprobado sí emita licencia y mail, y que nada de lo que
// falle de nuestro lado haga que MercadoPago reintente en bucle.
const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");

const webhook = require("./webhook-mp");
const { verificar } = require("./_licencia");

function respuesta() {
  const r = {
    codigo: null, cuerpo: null,
    status(c) { r.codigo = c; return r; },
    json(o) { r.cuerpo = o; return r; },
  };
  return r;
}

const SECRETO = "secreto-de-licencias-de-prueba";
let fetchOriginal;

beforeEach(() => {
  fetchOriginal = global.fetch;
  process.env.MP_ACCESS_TOKEN = "token-mp";
  process.env.MVDAX_LICENSE_SECRET = SECRETO;
  delete process.env.MP_WEBHOOK_SECRET;
  delete process.env.RESEND_API_KEY;
  delete process.env.KV_REST_API_URL;
  delete process.env.KV_REST_API_TOKEN;
});
afterEach(() => { global.fetch = fetchOriginal; });

// MercadoPago devuelve lo que se le diga. `llamadas` deja ver a quién se
// llamó, que es como se comprueba que el mail salió.
function simular(pago) {
  const llamadas = [];
  global.fetch = async (url, opciones) => {
    llamadas.push({ url: String(url), opciones });
    if (String(url).includes("mercadopago")) {
      return { ok: true, json: async () => pago };
    }
    return { ok: true, status: 200, text: async () => "" };
  };
  return llamadas;
}

const PAGO_OK = {
  status: "approved",
  metadata: { plan: "perpetua" },
  payer: { email: "cliente@ejemplo.com" },
  transaction_amount: 3960,
  currency_id: "UYU",
};

test("un pago aprobado emite una licencia que el programa acepta", async () => {
  simular(PAGO_OK);
  const res = respuesta();
  await webhook({ method: "POST", body: { type: "payment", data: { id: "123" } },
                  headers: {} }, res);

  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.licencia, true);
});

test("la clave que emite el webhook es la misma que verifica el programa", async () => {
  // El webhook no devuelve la clave al que llama —sería regalarla—, así que
  // se la intercepta en el mail.
  process.env.RESEND_API_KEY = "clave-resend";
  let mail = null;
  global.fetch = async (url, opciones) => {
    if (String(url).includes("mercadopago")) {
      return { ok: true, json: async () => PAGO_OK };
    }
    mail = JSON.parse(opciones.body);
    return { ok: true, status: 200, text: async () => "" };
  };
  await webhook({ method: "POST", body: { type: "payment", data: { id: "123" } },
                  headers: {} }, respuesta());

  assert.ok(mail, "tenía que mandar el mail");
  assert.deepEqual(mail.to, ["cliente@ejemplo.com"]);
  const clave = (mail.text.match(/MVDAX1\.[\w-]+\.[\w-]+/) || [])[0];
  assert.ok(clave, "el mail tiene que traer la clave");
  const payload = verificar(clave, SECRETO);
  assert.ok(payload, "la clave del mail tiene que verificar contra el secreto");
  assert.equal(payload.plan, "perpetua");
  assert.equal(payload.pid, "123");
  // Y el enlace de descarga, que es la otra mitad de "ya lo tengo".
  assert.match(mail.text, /\/api\/descargar\?payment_id=123/);
});

test("un pago NO aprobado no emite nada", async () => {
  for (const estado of ["pending", "rejected", "in_process", "refunded"]) {
    simular({ ...PAGO_OK, status: estado });
    const res = respuesta();
    await webhook({ method: "POST", body: { type: "payment", data: { id: "1" } },
                    headers: {} }, res);
    assert.equal(res.codigo, 200, "nunca 500: haría que MP reintente en bucle");
    assert.notEqual(res.cuerpo.licencia, true, `no debería emitir con ${estado}`);
  }
});

test("no le cree al cuerpo del aviso: el estado lo pide a la API", async () => {
  // Este es el candado que hace que un aviso falso no sirva. El cuerpo dice
  // "approved" y trae un plan; MercadoPago dice que está rechazado.
  simular({ status: "rejected", metadata: { plan: "perpetua" } });
  const res = respuesta();
  await webhook({ method: "POST", headers: {}, body: {
    type: "payment", data: { id: "999" },
    status: "approved", metadata: { plan: "perpetua" },
    payer: { email: "ladron@ejemplo.com" },
  } }, res);
  assert.notEqual(res.cuerpo.licencia, true);
});

test("un plan que no existe no emite licencia", async () => {
  simular({ ...PAGO_OK, metadata: { plan: "gratis-total" } });
  const res = respuesta();
  await webhook({ method: "POST", body: { type: "payment", data: { id: "1" } },
                  headers: {} }, res);
  assert.notEqual(res.cuerpo.licencia, true);
});

test("con MP_WEBHOOK_SECRET, una firma inválida se rechaza", async () => {
  process.env.MP_WEBHOOK_SECRET = "secreto-webhook";
  simular(PAGO_OK);
  const res = respuesta();
  await webhook({ method: "POST", query: { "data.id": "123" },
                  headers: { "x-signature": "ts=1,v1=" + "0".repeat(64),
                             "x-request-id": "abc" },
                  body: { type: "payment", data: { id: "123" } } }, res);
  assert.equal(res.codigo, 401);
  assert.equal(res.cuerpo.error, "firma_invalida");
});

test("con MP_WEBHOOK_SECRET, la firma correcta pasa", async () => {
  const secreto = "secreto-webhook";
  process.env.MP_WEBHOOK_SECRET = secreto;
  const ts = "1700000000";
  const v1 = crypto.createHmac("sha256", secreto)
    .update("id:123;request-id:abc;ts:" + ts + ";").digest("hex");
  simular(PAGO_OK);
  const res = respuesta();
  await webhook({ method: "POST", query: { "data.id": "123" },
                  headers: { "x-signature": `ts=${ts},v1=${v1}`,
                             "x-request-id": "abc" },
                  body: { type: "payment", data: { id: "123" } } }, res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.licencia, true);
});

test("sin firma en la cabecera, con secreto configurado, se rechaza", async () => {
  process.env.MP_WEBHOOK_SECRET = "secreto-webhook";
  simular(PAGO_OK);
  const res = respuesta();
  await webhook({ method: "POST", body: { type: "payment", data: { id: "1" } },
                  headers: {} }, res);
  assert.equal(res.codigo, 401);
});

test("una suscripción autorizada emite licencia con vencimiento", async () => {
  process.env.RESEND_API_KEY = "clave-resend";
  let mail = null;
  global.fetch = async (url, opciones) => {
    if (String(url).includes("mercadopago")) {
      return { ok: true, json: async () => ({
        status: "authorized", external_reference: "mensual",
        payer_email: "mensual@ejemplo.com",
        auto_recurring: { transaction_amount: 400, currency_id: "UYU" },
      }) };
    }
    mail = JSON.parse(opciones.body);
    return { ok: true, status: 200, text: async () => "" };
  };
  const res = respuesta();
  await webhook({ method: "POST", headers: {}, body: {
    type: "subscription_preapproval", data: { id: "abc12345def" } } }, res);

  assert.equal(res.cuerpo.licencia, true);
  const clave = (mail.text.match(/MVDAX1\.[\w-]+\.[\w-]+/) || [])[0];
  const payload = verificar(clave, SECRETO);
  assert.ok(payload.exp, "la mensual tiene que vencer");
  assert.equal(payload.sub, "abc12345def");
  assert.match(mail.text, /preapproval_id=abc12345def/);
});

test("una suscripción pausada no emite nada", async () => {
  simular({ status: "paused", external_reference: "mensual" });
  const res = respuesta();
  await webhook({ method: "POST", headers: {}, body: {
    type: "subscription_preapproval", data: { id: "abc12345def" } } }, res);
  assert.notEqual(res.cuerpo.licencia, true);
});

test("los avisos que no son de pago se ignoran sin romperse", async () => {
  for (const tipo of ["merchant_order", "plan", "invoice", ""]) {
    const res = respuesta();
    await webhook({ method: "POST", headers: {}, body: {
      type: tipo, data: { id: "1" } } }, res);
    assert.equal(res.codigo, 200, `${tipo} no debería fallar`);
    assert.notEqual(res.cuerpo.licencia, true);
  }
});

test("si Resend falla, la licencia igual queda emitida", async () => {
  // El mail es un extra. Perderlo no puede invalidar una venta.
  process.env.RESEND_API_KEY = "clave-resend";
  global.fetch = async (url) => {
    if (String(url).includes("mercadopago")) {
      return { ok: true, json: async () => PAGO_OK };
    }
    return { ok: false, status: 500, text: async () => "boom" };
  };
  const res = respuesta();
  await webhook({ method: "POST", body: { type: "payment", data: { id: "1" } },
                  headers: {} }, res);
  assert.equal(res.cuerpo.licencia, true);
  assert.equal(res.cuerpo.mail, false);
});

test("un error inesperado devuelve 200, no 500", async () => {
  global.fetch = async () => { throw new Error("red caída"); };
  const res = respuesta();
  await webhook({ method: "POST", body: { type: "payment", data: { id: "1" } },
                  headers: {} }, res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.ok, false);
});

test("sin MVDAX_LICENSE_SECRET avisa pero no revienta", async () => {
  delete process.env.MVDAX_LICENSE_SECRET;
  simular(PAGO_OK);
  const res = respuesta();
  await webhook({ method: "POST", body: { type: "payment", data: { id: "1" } },
                  headers: {} }, res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.licencia, false);
});
