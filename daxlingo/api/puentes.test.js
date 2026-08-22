// © 2026 Martín Viera. Todos los derechos reservados.

// Vercel despliega las funciones serverless desde el /api de la RAÍZ del
// repo, pero la implementación vive acá, en daxlingo/api/. El pegamento son
// unos puentes de una línea en la raíz que hacen `require` de este directorio.
//
// Nada obligaba a crear el puente al agregar una función nueva, y el precio
// de olvidarse no se paga en el CI sino en producción: `solicitar-demo.js`
// se mergeó sin su puente y el formulario de demo quedó pegándole a un 404.
// Los tests de la función pasaban perfecto —la función estaba bien— y la
// página estaba publicada; lo que faltaba era el archivo que la conecta.
//
// Este test es esa obligación, escrita.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const AQUI = __dirname;
const RAIZ = path.join(AQUI, "..", "..", "api");

// Públicas = las que Vercel expone como endpoint. Se saltean los helpers
// (`_licencia.js`, `_planes.js`…) y los tests: ni unos ni otros son rutas.
function publicas(dir) {
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".js") && !f.startsWith("_") && !f.endsWith(".test.js"))
    .sort();
}

test("cada función tiene su puente en el /api de la raíz", () => {
  const faltan = publicas(AQUI).filter((f) => !fs.existsSync(path.join(RAIZ, f)));
  assert.deepEqual(faltan, [], `sin puente en api/ de la raíz: ${faltan.join(", ")}. ` +
    "Sin él la ruta devuelve 404 en producción aunque la función esté perfecta.");
});

test("cada puente apunta a una función que existe", () => {
  // Al revés que el anterior: un puente que quedó huérfano porque se renombró
  // o se borró la implementación revienta el deploy entero de Vercel, no solo
  // su propia ruta.
  for (const f of publicas(RAIZ)) {
    assert.ok(fs.existsSync(path.join(AQUI, f)),
      `api/${f} de la raíz no tiene implementación en daxlingo/api/`);
    assert.doesNotThrow(() => require(path.join(RAIZ, f)),
      `api/${f} de la raíz no se puede cargar`);
  }
});

test("los puentes son puentes y no una copia del código", () => {
  // Una copia se desincroniza en silencio: se arregla un bug de un lado y el
  // otro sigue sirviendo la versión vieja.
  for (const f of publicas(RAIZ)) {
    const texto = fs.readFileSync(path.join(RAIZ, f), "utf8");
    assert.match(texto, new RegExp(`require\\(["']\\.\\./daxlingo/api/${f.replace(".", "\\.")}["']\\)`),
      `api/${f} de la raíz debería ser un require a daxlingo/api/${f}, no código propio`);
  }
});
