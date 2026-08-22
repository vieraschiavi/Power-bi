// © 2026 Martín Viera. Todos los derechos reservados.

// Lo que se prueba acá: que NADIE baje el instalador sin haber pagado, y que
// el que pagó lo baje. Es el endpoint que separa "cliente" de "cualquiera",
// así que las dos mitades importan igual.
const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");

const descargar = require("./descargar");

function respuesta() {
  const r = {
    codigo: null, cuerpo: null, statusCode: null, cabeceras: {},
    status(c) { r.codigo = c; return r; },
    json(o) { r.cuerpo = o; return r; },
    setHeader(k, v) { r.cabeceras[k.toLowerCase()] = v; },
    end() { r.termino = true; },
  };
  return r;
}

let fetchOriginal;
beforeEach(() => {
  fetchOriginal = global.fetch;
  process.env.MP_ACCESS_TOKEN = "token-de-prueba";
  delete process.env.GITHUB_TOKEN;
});
afterEach(() => { global.fetch = fetchOriginal; });

// MercadoPago responde lo que se le diga; nunca se llama a la API real.
function mpResponde(datos, ok = true) {
  global.fetch = async () => ({ ok, json: async () => datos });
}

test("sin id de pago no se entrega nada", async () => {
  const res = respuesta();
  await descargar({ query: {} }, res);
  assert.equal(res.codigo, 400);
  assert.equal(res.cuerpo.error, "falta_id");
});

test("un pago que MercadoPago no aprobó no da descarga", async () => {
  for (const estado of ["pending", "rejected", "in_process", "cancelled"]) {
    mpResponde({ status: estado, metadata: { plan: "perpetua" } });
    const res = respuesta();
    await descargar({ query: { payment_id: "123456" } }, res);
    assert.equal(res.codigo, 402, `debería rechazar ${estado}`);
    assert.equal(res.cuerpo.error, "no_aprobado");
  }
});

test("una suscripción pausada o cancelada tampoco", async () => {
  for (const estado of ["paused", "cancelled", "pending"]) {
    mpResponde({ status: estado, external_reference: "mensual" });
    const res = respuesta();
    await descargar({ query: { preapproval_id: "abc12345def" } }, res);
    assert.equal(res.codigo, 402, `debería rechazar ${estado}`);
  }
});

test("un payment_id inventado no pasa el formato", async () => {
  for (const id of ["../../etc", "abc", "1 OR 1=1", ""]) {
    const res = respuesta();
    await descargar({ query: { payment_id: id } }, res);
    assert.notEqual(res.codigo, 302, `no debería aceptar ${id}`);
  }
});

test("pago aprobado ⇒ 302 al instalador", async () => {
  mpResponde({ status: "approved", metadata: { plan: "perpetua" } });
  const res = respuesta();
  await descargar({ query: { payment_id: "123456" } }, res);

  assert.equal(res.statusCode, 302);
  const destino = res.cabeceras.location;
  assert.match(destino, /releases\/download/);
  assert.match(destino, /MV-DAX-Lab-Setup\.exe$/);
  // Que no quede cacheado: la próxima vez hay que volver a comprobar el pago.
  assert.equal(res.cabeceras["cache-control"], "no-store");
});

test("suscripción autorizada ⇒ 302 al instalador", async () => {
  mpResponde({ status: "authorized", external_reference: "mensual" });
  const res = respuesta();
  await descargar({ query: { preapproval_id: "abc12345def" } }, res);
  assert.equal(res.statusCode, 302);
  assert.match(res.cabeceras.location, /MV-DAX-Lab-Setup\.exe$/);
});

test("un plan que no existe no habilita descarga", async () => {
  // Una preferencia armada por fuera del checkout, con un plan inventado.
  mpResponde({ status: "approved", metadata: { plan: "gratis-total" } });
  const res = respuesta();
  await descargar({ query: { payment_id: "123456" } }, res);
  assert.equal(res.codigo, 400);
  assert.equal(res.cuerpo.error, "plan_invalido");
});

test("con GITHUB_TOKEN usa la URL firmada, no la pública", async () => {
  // Es lo que va a hacer falta cuando el repositorio pase a privado.
  process.env.GITHUB_TOKEN = "ghp_falso";
  global.fetch = async (url, opciones) => {
    if (String(url).includes("mercadopago")) {
      return { ok: true, json: async () => ({ status: "approved", metadata: { plan: "perpetua" } }) };
    }
    if (String(url).includes("api.github.com/repos")) {
      return { ok: true, json: async () => ({
        assets: [{ name: "MV-DAX-Lab-Setup.exe", url: "https://api.github.com/…/assets/9" }],
      }) };
    }
    // La petición al asset: lo único que interesa es el Location.
    assert.equal(opciones.redirect, "manual", "no debe bajarse los 176 MB adentro de la función");
    return { headers: { get: (k) => (k === "location" ? "https://firmada.example/x?sig=1" : null) } };
  };
  const res = respuesta();
  await descargar({ query: { payment_id: "123456" } }, res);
  assert.equal(res.cabeceras.location, "https://firmada.example/x?sig=1");
});

test("si la API de GitHub falla, cae al enlace público en vez de romperse", async () => {
  process.env.GITHUB_TOKEN = "ghp_falso";
  global.fetch = async (url) => {
    if (String(url).includes("mercadopago")) {
      return { ok: true, json: async () => ({ status: "approved", metadata: { plan: "perpetua" } }) };
    }
    throw new Error("github caído");
  };
  const res = respuesta();
  await descargar({ query: { payment_id: "123456" } }, res);
  assert.equal(res.statusCode, 302);
  assert.match(res.cabeceras.location, /github\.com\/.*releases\/download/);
});

test("sin MP_ACCESS_TOKEN avisa en vez de dejar pasar", async () => {
  delete process.env.MP_ACCESS_TOKEN;
  const res = respuesta();
  await descargar({ query: { payment_id: "123456" } }, res);
  assert.equal(res.codigo, 503);
  assert.equal(res.cuerpo.error, "medio_pago_no_configurado");
});

test("un error de MercadoPago no abre la puerta", async () => {
  mpResponde({ message: "internal" }, false);
  const res = respuesta();
  await descargar({ query: { payment_id: "123456" } }, res);
  // 502: el que falló fue MercadoPago. Un 400 mandaría al cliente a revisar
  // un enlace que está perfecto.
  assert.equal(res.codigo, 502);
  assert.equal(res.cuerpo.error, "mp_error");
  assert.notEqual(res.statusCode, 302);
});
