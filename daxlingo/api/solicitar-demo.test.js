// © 2026 Martín Viera. Todos los derechos reservados.

// Lo que se prueba acá: que el formulario de demo no deja pasar un pedido
// incompleto, que no se traga los datos en silencio cuando el correo no está
// configurado, y que lo que llega del navegador no puede inyectar HTML en la
// bandeja de quien lo lee.
const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");

const solicitar = require("./solicitar-demo");

function respuesta() {
  const r = {
    codigo: null, cuerpo: null,
    status(c) { r.codigo = c; return r; },
    json(o) { r.cuerpo = o; return r; },
  };
  return r;
}

const COMPLETO = {
  nombre: "Ana Pérez", email: "ana@empresa.com",
  empresa: "Empresa SA", pais: "Uruguay",
};

let fetchOriginal;
beforeEach(() => {
  fetchOriginal = global.fetch;
  delete process.env.RESEND_API_KEY;
  delete process.env.RESEND_FROM;
});
afterEach(() => { global.fetch = fetchOriginal; });

test("rechaza métodos que no son POST", async () => {
  const res = respuesta();
  await solicitar({ method: "GET" }, res);
  assert.equal(res.codigo, 405);
});

test("exige nombre, email, empresa y país", async () => {
  for (const falta of ["nombre", "email", "empresa", "pais"]) {
    const cuerpo = { ...COMPLETO };
    delete cuerpo[falta];
    const res = respuesta();
    await solicitar({ method: "POST", body: cuerpo }, res);
    assert.equal(res.codigo, 400, `debería faltar ${falta}`);
    assert.equal(res.cuerpo.error, "faltan_campos");
    assert.ok(res.cuerpo.campos.includes(falta));
  }
});

test("rechaza un email que no puede contestarse", async () => {
  for (const email of ["sin-arroba", "a@b", "@nada.com", "a b@c.com"]) {
    const res = respuesta();
    await solicitar({ method: "POST", body: { ...COMPLETO, email } }, res);
    assert.equal(res.codigo, 400, `debería rechazar ${email}`);
    assert.equal(res.cuerpo.error, "email_invalido");
  }
});

test("sin RESEND_API_KEY avisa, no finge que lo mandó", async () => {
  // Es la diferencia entre perder un prospecto y saber que lo perdiste.
  const res = respuesta();
  await solicitar({ method: "POST", body: COMPLETO }, res);
  assert.equal(res.codigo, 503);
  assert.equal(res.cuerpo.error, "correo_no_configurado");
});

test("pedido completo ⇒ manda el mail con los cuatro datos", async () => {
  process.env.RESEND_API_KEY = "clave";
  let enviado = null;
  global.fetch = async (url, opciones) => {
    enviado = { url, ...JSON.parse(opciones.body) };
    return { ok: true, status: 200, text: async () => "" };
  };
  const res = respuesta();
  await solicitar({ method: "POST", body: { ...COMPLETO, mensaje: "Somos 3 analistas" } }, res);

  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.ok, true);
  assert.match(enviado.url, /api\.resend\.com/);
  assert.deepEqual(enviado.to, ["vieraschiavi@gmail.com"]);
  // Contestar el mail tiene que escribirle al que pidió la demo.
  assert.equal(enviado.reply_to, "ana@empresa.com");
  for (const dato of ["Ana Pérez", "ana@empresa.com", "Empresa SA", "Uruguay",
                      "Somos 3 analistas"]) {
    assert.ok(enviado.text.includes(dato), `falta en el cuerpo: ${dato}`);
  }
});

test("el cuerpo del mail no puede inyectar HTML", async () => {
  process.env.RESEND_API_KEY = "clave";
  let enviado = null;
  global.fetch = async (_u, o) => {
    enviado = JSON.parse(o.body);
    return { ok: true, status: 200, text: async () => "" };
  };
  await solicitar({ method: "POST", body: {
    ...COMPLETO, nombre: '<img src=x onerror="alert(1)">',
  } }, respuesta());

  assert.ok(!enviado.html.includes("<img"), "el <img> tiene que salir escapado");
  assert.ok(enviado.html.includes("&lt;img"));
});

test("si Resend falla, no filtra su respuesta al navegador", async () => {
  process.env.RESEND_API_KEY = "clave";
  global.fetch = async () => ({
    ok: false, status: 401, text: async () => "API key inválida: re_secreta_123",
  });
  const res = respuesta();
  await solicitar({ method: "POST", body: COMPLETO }, res);
  assert.equal(res.codigo, 502);
  assert.equal(res.cuerpo.error, "envio_fallido");
  assert.ok(!JSON.stringify(res.cuerpo).includes("re_secreta_123"));
});

test("recorta campos desmedidos en vez de reenviarlos enteros", async () => {
  process.env.RESEND_API_KEY = "clave";
  let enviado = null;
  global.fetch = async (_u, o) => {
    enviado = JSON.parse(o.body);
    return { ok: true, status: 200, text: async () => "" };
  };
  await solicitar({ method: "POST", body: {
    ...COMPLETO, mensaje: "x".repeat(50000),
  } }, respuesta());
  assert.ok(enviado.text.length < 2000, "el mensaje tiene que venir recortado");
});
