// Catálogo de planes de MV DAX Lab — fuente única para el checkout y la
// landing. Los precios se muestran en USD de referencia; la preferencia de
// MercadoPago se crea en la moneda del collector.
//
// Por qué la conversión: una cuenta de cobro de Uruguay (site MLU) solo
// acepta preferencias en UYU — mandar "USD" hace que la API rechace la
// preferencia y el checkout falle sin decir por qué. Mismo problema y misma
// solución que en Kobra.

const PLANES = {
  profesional: {
    titulo: "MV DAX Lab · Profesional (licencia perpetua, 1 equipo)",
    usd: 99,
    equipos: 1,
  },
  estudio: {
    titulo: "MV DAX Lab · Estudio (5 equipos)",
    usd: 349,
    equipos: 5,
  },
  corporativo: {
    titulo: "MV DAX Lab · Corporativo (equipos ilimitados + soporte)",
    usd: 990,
    equipos: 0, // 0 = sin límite
  },
};

const MONEDA = process.env.MP_CURRENCY || "UYU";
// Mismo valor de referencia que muestra la landing (US$1 ≈ $U 40).
const TASA_UYU = Number(process.env.MP_TASA_UYU) || 40;

function precioEnMoneda(plan) {
  const p = PLANES[plan];
  if (!p) return null;
  return MONEDA === "USD" ? p.usd : Math.round(p.usd * TASA_UYU);
}

module.exports = { PLANES, MONEDA, TASA_UYU, precioEnMoneda };
