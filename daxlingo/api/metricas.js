// © 2026 Martín Viera. Todos los derechos reservados.

// MV DAX Lab · Monitor de ventas — solo para el dueño.
//
// Devuelve lo que hasta ahora había que ir a buscar al panel de MercadoPago:
// cuántos clientes, cuánto se facturó, cuántas descargas, y el detalle de
// las últimas ventas con el mail de cada uno.
//
// Protegido por MVDAX_OWNER_TOKEN. Sin ese token configurado el endpoint
// queda CERRADO, no abierto: un monitor de ventas sin contraseña es peor que
// no tener monitor.
//
// El neto es una ESTIMACIÓN y se dice que lo es: se descuenta la comisión de
// MercadoPago (configurable, por defecto la de Uruguay para acreditación
// inmediata: 5,99% + 22% de IVA sobre esa comisión = 7,31% efectivo). No
// incluye impuestos a la renta, que dependen de cómo esté constituido el
// negocio. Lo único que acá es un hecho es el bruto.

const crypto = require("crypto");
const { limitar } = require("./_limitador");
const almacen = require("./_almacen");

// Comisión efectiva sobre el bruto. 5,99% de comisión + 22% de IVA sobre
// esa comisión. Se puede pisar con MVDAX_COMISION_PCT si cambia el plan o
// el país.
const COMISION_PCT = Number(process.env.MVDAX_COMISION_PCT) || (5.99 * 1.22);

function autorizado(req) {
  const esperado = process.env.MVDAX_OWNER_TOKEN || "";
  if (!esperado) return false;

  const cab = (req.headers && req.headers.authorization) || "";
  const dado = cab.startsWith("Bearer ")
    ? cab.slice(7)
    : String((req.query && req.query.token) || "");
  if (!dado) return false;

  // Longitudes distintas revientan timingSafeEqual, así que se comparan los
  // hash: mismo largo siempre, y la comparación sigue siendo de tiempo
  // constante.
  const a = crypto.createHash("sha256").update(dado).digest();
  const b = crypto.createHash("sha256").update(esperado).digest();
  return crypto.timingSafeEqual(a, b);
}

module.exports = async (req, res) => {
  // Estrecho a propósito: es el endpoint donde tantear el token.
  if (!limitar(req, res, "metricas", 10, 60)) return;

  if (!autorizado(req)) {
    res.status(401).json({ error: "no_autorizado" });
    return;
  }

  if (!almacen.disponible()) {
    res.status(200).json({
      configurado: false,
      nota: "Falta la base de datos (KV_REST_API_URL + KV_REST_API_TOKEN). " +
            "Las ventas se cobran igual, pero no se registran.",
    });
    return;
  }

  const ventas = await almacen.listarVentas(500);
  if (ventas === null) {
    res.status(502).json({ error: "almacen_no_responde" });
    return;
  }

  const clientes = new Set();
  let bruto = 0, descargas = 0;
  const porPlan = {};
  for (const v of ventas) {
    if (v.email) clientes.add(v.email);
    bruto += Number(v.usd || 0);
    descargas += Number(v.descargas || 0);
    const p = v.plan || "?";
    porPlan[p] = (porPlan[p] || 0) + 1;
  }

  const comision = bruto * (COMISION_PCT / 100);

  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({
    configurado: true,
    ventas: ventas.length,
    // Clientes ≠ ventas: el mismo mail puede comprar dos veces, y una
    // suscripción que se renueva no es un cliente nuevo.
    clientes: clientes.size,
    descargas,
    porPlan,
    dinero: {
      brutoUsd: Math.round(bruto * 100) / 100,
      comisionPct: Math.round(COMISION_PCT * 100) / 100,
      comisionUsd: Math.round(comision * 100) / 100,
      netoEstimadoUsd: Math.round((bruto - comision) * 100) / 100,
      nota: "Neto estimado: descuenta la comisión de MercadoPago, no " +
            "impuestos a la renta.",
    },
    ultimas: ventas.slice(0, 50),
  });
};
