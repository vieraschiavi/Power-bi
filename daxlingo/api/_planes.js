// MV DAX Lab · Modalidades de pago — fuente única para el checkout, la
// emisión de licencias y la landing.
//
// Un solo producto, con TODO desbloqueado en las dos modalidades. No hay
// versiones recortadas: lo único que cambia es cómo se paga.
//
//   perpetua · USD 99 una vez  → licencia sin vencimiento
//   mensual  · USD 10 por mes  → suscripción; la licencia vence y se renueva
//                                con cada cobro acreditado
//
// Por qué la conversión de moneda: una cuenta de cobro de Uruguay (site MLU)
// solo acepta preferencias en UYU — mandar "USD" hace que la API rechace la
// preferencia y el checkout falle sin decir por qué. Mismo problema y misma
// solución que en Kobra.

const PLANES = {
  perpetua: {
    titulo: "MV DAX Lab · licencia perpetua",
    usd: 99,
    recurrente: false,
    equipos: 1,
  },
  mensual: {
    titulo: "MV DAX Lab · suscripción mensual",
    usd: 10,
    recurrente: true,
    equipos: 1,
  },
};

const MONEDA = process.env.MP_CURRENCY || "UYU";
// Mismo valor de referencia que muestra la landing (US$1 ≈ $U 40).
const TASA_UYU = Number(process.env.MP_TASA_UYU) || 40;

// Días de validez de la licencia mensual. Son 32 y no 30 a propósito: si
// venciera justo a los 30, un cobro que se acredita un día tarde le cortaría
// el acceso a alguien que pagó. El margen se recupera en la renovación,
// porque cada licencia nueva se cuenta desde su propia emisión.
const DIAS_MENSUAL = 32;

function precioEnMoneda(plan) {
  const p = PLANES[plan];
  if (!p) return null;
  return MONEDA === "USD" ? p.usd : Math.round(p.usd * TASA_UYU);
}

module.exports = { PLANES, MONEDA, TASA_UYU, DIAS_MENSUAL, precioEnMoneda };
