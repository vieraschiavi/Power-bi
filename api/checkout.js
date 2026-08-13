// © 2026 Martín Viera. Todos los derechos reservados.

// Puente de raíz para Vercel: las funciones serverless se despliegan desde
// /api de la raíz del repo, pero la implementación vive junto al resto del
// producto, en daxlingo/api/. Este archivo es solo el reenvío.
module.exports = require("../daxlingo/api/checkout.js");
