// `_licencia.js` es el candado de la venta: firma la licencia que recibe
// quien pagó, y `verificar()` es lo único que separa una licencia real de
// una inventada. Por eso es lo primero que se testea del eje de dinero.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { firmar, verificar } = require("./_licencia");

const CLAVE = "un-secreto-de-prueba-bien-largo";

test("firmar + verificar: ida y vuelta devuelve el payload original", () => {
  const payload = { plan: "profesional", equipos: 1, pid: "123", iat: 1000 };
  const lic = firmar(payload, CLAVE);
  assert.match(lic, /^MVDAX1\./);
  assert.deepEqual(verificar(lic, CLAVE), payload);
});

test("verificar rechaza con el secreto equivocado", () => {
  const lic = firmar({ plan: "estudio" }, CLAVE);
  assert.equal(verificar(lic, "otro-secreto"), null);
});

test("verificar rechaza si se falsifica el payload", () => {
  const lic = firmar({ plan: "profesional" }, CLAVE);
  const [pre, , firma] = lic.split(".");
  const falso = Buffer.from(JSON.stringify({ plan: "corporativo" }))
    .toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  assert.equal(verificar([pre, falso, firma].join("."), CLAVE), null);
});

test("verificar rechaza basura y formatos ajenos", () => {
  for (const malo of ["", "cualquier-cosa", "KOBRA1.a.b", "MVDAX1.solo-dos",
                      null, undefined, 42, {}]) {
    assert.equal(verificar(malo, CLAVE), null);
  }
});

test("verificar respeta el vencimiento", () => {
  const vencida = firmar({ plan: "profesional", exp: 1000 }, CLAVE);
  assert.equal(verificar(vencida, CLAVE), null);
  const futuro = Math.floor(Date.now() / 1000) + 3600;
  const vigente = firmar({ plan: "profesional", exp: futuro }, CLAVE);
  assert.equal(verificar(vigente, CLAVE).plan, "profesional");
});
