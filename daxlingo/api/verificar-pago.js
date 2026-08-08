// Verifica un pago único de MercadoPago contra la API real (server-side) y
// recién entonces emite la licencia firmada. Es lo que impide armar la URL de
// /descarga.html a mano sin haber pagado.
//
// La suscripción mensual NO pasa por acá: tiene su propio endpoint
// (`verificar-suscripcion.js`), porque lo que hay que consultar es el estado
// de la autorización recurrente, no un pago suelto.
//
// La licencia se emite acá y NO en el navegador: el secreto de firma
// (MVDAX_LICENSE_SECRET) nunca sale del servidor.

const { firmar } = require("./_licencia");
const { limitar } = require("./_limitador");
const { PLANES } = require("./_planes");

module.exports = async (req, res) => {
  // Sin esto se podía tantear payment_id a la velocidad de la red: es un
  // endpoint público que consulta la API de MercadoPago. 20 por minuto
  // alcanza para el polling normal de la página de descarga.
  if (!limitar(req, res, "verificar-pago", 20, 60)) return;

  const idPago = String((req.query && req.query.payment_id) || "").trim();
  if (!idPago || !/^[0-9]+$/.test(idPago)) {
    res.status(400).json({ aprobado: false, error: "payment_id_invalido" });
    return;
  }
  const token = process.env.MP_ACCESS_TOKEN;
  if (!token) {
    res.status(500).json({ aprobado: false, error: "sin_token" });
    return;
  }

  try {
    const r = await fetch("https://api.mercadopago.com/v1/payments/" + idPago, {
      headers: { Authorization: "Bearer " + token },
    });
    const datos = await r.json();
    if (!r.ok) {
      res.status(502).json({ aprobado: false, error: "mp_error" });
      return;
    }

    const aprobado = datos.status === "approved";
    const plan = (datos.metadata && datos.metadata.plan) || null;

    let clave = null;
    const secreto = process.env.MVDAX_LICENSE_SECRET;
    if (aprobado && secreto && PLANES[plan]) {
      clave = firmar({
        plan: plan,
        equipos: PLANES[plan].equipos,
        pid: idPago,
        email: (datos.payer && datos.payer.email) || null,
        iat: Math.floor(Date.now() / 1000),
      }, secreto);
    }

    res.status(200).json({
      aprobado: aprobado,
      estado: datos.status,
      plan: plan,
      licencia: clave,
    });
  } catch (e) {
    res.status(500).json({ aprobado: false, error: "excepcion" });
  }
};
