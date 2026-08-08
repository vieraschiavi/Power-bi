// Emite (y renueva) la licencia de la modalidad mensual.
//
// Una suscripción de MercadoPago es un `preapproval`: una autorización que va
// generando cobros mes a mes. Lo que hay que preguntar entonces no es "¿este
// pago se acreditó?" sino "¿esta autorización sigue viva?".
//
// La licencia que se emite acá VENCE (DIAS_MENSUAL). El cliente vuelve a esta
// URL —el programa le deja el enlace en la pestaña Licencia— y, mientras la
// suscripción siga autorizada, recibe una clave nueva. Si la da de baja o el
// cobro falla, deja de renovarse y la licencia caduca sola. Ese es el corte:
// no hace falta que el programa llame a casa ni que nosotros guardemos nada.

const { firmar } = require("./_licencia");
const { limitar } = require("./_limitador");
const { PLANES, DIAS_MENSUAL } = require("./_planes");

// Estados de un preapproval que habilitan licencia. "paused" no entra: la
// suscripción existe pero no está cobrando.
const VIGENTES = new Set(["authorized"]);

module.exports = async (req, res) => {
  if (!limitar(req, res, "verificar-suscripcion", 20, 60)) return;

  const id = String((req.query && (req.query.preapproval_id ||
                                   req.query.id)) || "").trim();
  // Los ids de preapproval son hexadecimales largos, no numéricos.
  if (!id || !/^[a-zA-Z0-9-]{8,64}$/.test(id)) {
    res.status(400).json({ vigente: false, error: "preapproval_id_invalido" });
    return;
  }
  const token = process.env.MP_ACCESS_TOKEN;
  if (!token) {
    res.status(500).json({ vigente: false, error: "sin_token" });
    return;
  }

  try {
    const r = await fetch(
      "https://api.mercadopago.com/preapproval/" + encodeURIComponent(id),
      { headers: { Authorization: "Bearer " + token } });
    const datos = await r.json();
    if (!r.ok) {
      res.status(502).json({ vigente: false, error: "mp_error" });
      return;
    }

    const vigente = VIGENTES.has(datos.status);
    const plan = datos.external_reference || "mensual";

    let clave = null;
    let venceEn = null;
    const secreto = process.env.MVDAX_LICENSE_SECRET;
    if (vigente && secreto && PLANES[plan]) {
      const ahora = Math.floor(Date.now() / 1000);
      venceEn = ahora + DIAS_MENSUAL * 86400;
      clave = firmar({
        plan: plan,
        equipos: PLANES[plan].equipos,
        sub: id,
        email: datos.payer_email || null,
        iat: ahora,
        exp: venceEn,
      }, secreto);
    }

    res.status(200).json({
      vigente: vigente,
      estado: datos.status,
      plan: plan,
      licencia: clave,
      vence: venceEn,
    });
  } catch (e) {
    res.status(500).json({ vigente: false, error: "excepcion" });
  }
};
