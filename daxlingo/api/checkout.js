// Checkout de MercadoPago — función serverless (Vercel, CommonJS).
//
// El Access Token vive SOLO como variable de entorno del servidor
// (MP_ACCESS_TOKEN): nunca se expone al navegador ni se guarda en el repo.
// Alternativa sin token: links de pago por plan (MP_LINK_PROFESIONAL, etc.).
//
// POST + JSON, no GET/redirect: el cliente hace fetch acá y recién después
// navega él mismo a la URL de pago que devolvemos.

const { limitar } = require("./_limitador");
const { PLANES, MONEDA, precioEnMoneda } = require("./_planes");

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "metodo" });
    return;
  }
  // 10 por minuto por IP: de sobra para alguien probando planes, corto para
  // un script golpeando la API de MercadoPago a través de este endpoint.
  if (!limitar(req, res, "checkout", 10, 60)) return;

  const cuerpo = typeof req.body === "string" ? jsonSeguro(req.body)
                                              : (req.body || {});
  const plan = String(cuerpo.plan || "").toLowerCase();
  const p = PLANES[plan];
  if (!p) { res.status(400).json({ error: "plan_invalido" }); return; }

  const base = "https://" + (req.headers.host || "mvdaxlab.vercel.app");
  const token = process.env.MP_ACCESS_TOKEN;
  const link = process.env["MP_LINK_" + plan.toUpperCase()];

  // Sin Access Token: si hay link de pago configurado, devuelvo ese.
  if (!token) {
    if (link) { res.status(200).json({ url: link }); return; }
    res.status(503).json({ error: "medio_pago_no_configurado" });
    return;
  }

  const preferencia = {
    items: [{
      title: p.titulo,
      quantity: 1,
      unit_price: precioEnMoneda(plan),
      currency_id: MONEDA,
    }],
    metadata: { plan: plan },
    back_urls: {
      success: base + "/descarga.html",
      pending: base + "/descarga.html",
      failure: base + "/#precios",
    },
    auto_return: "approved",
    statement_descriptor: "MVDAXLAB",
  };

  try {
    const r = await fetch("https://api.mercadopago.com/checkout/preferences", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
      body: JSON.stringify(preferencia),
    });
    const datos = await r.json();
    if (!r.ok || !datos.init_point) {
      // No devolvemos el cuerpo de MercadoPago tal cual: puede traer detalles
      // de la cuenta de cobro que no tienen por qué llegar al navegador.
      res.status(502).json({ error: "mp_error" });
      return;
    }
    res.status(200).json({ url: datos.init_point });
  } catch (e) {
    res.status(500).json({ error: "excepcion" });
  }
};

function jsonSeguro(texto) {
  try { return JSON.parse(texto); } catch (e) { return {}; }
}
