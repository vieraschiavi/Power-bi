// © 2026 Martín Viera. Todos los derechos reservados.

// Checkout de MercadoPago — función serverless (Vercel, CommonJS).
//
// Dos caminos, porque MercadoPago los trata distinto:
//   · pago único  → /checkout/preferences  (preferencia)
//   · suscripción → /preapproval           (autorización recurrente)
// Los dos devuelven una URL a la que el navegador navega después.
//
// El Access Token vive SOLO como variable de entorno del servidor
// (MP_ACCESS_TOKEN): nunca se expone al navegador ni se guarda en el repo.
// Alternativa sin token: links de pago por modalidad (MP_LINK_PERPETUA,
// MP_LINK_MENSUAL).
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
  // 10 por minuto por IP: de sobra para alguien probando modalidades, corto
  // para un script golpeando la API de MercadoPago a través de este endpoint.
  if (!limitar(req, res, "checkout", 10, 60)) return;

  const cuerpo = typeof req.body === "string" ? jsonSeguro(req.body)
                                              : (req.body || {});
  const plan = String(cuerpo.plan || "").toLowerCase();
  const p = PLANES[plan];
  if (!p) { res.status(400).json({ error: "plan_invalido" }); return; }

  // El host lo pone Vercel en el request, así que las URLs de retorno salen
  // solas con el dominio real, sea el que sea. MVDAXLAB_SITIO es el respaldo
  // para invocaciones sin header Host (tests, cron, curl a mano).
  const base = req.headers.host ? "https://" + req.headers.host
                                : (process.env.MVDAXLAB_SITIO || "");
  const token = process.env.MP_ACCESS_TOKEN;
  const link = process.env["MP_LINK_" + plan.toUpperCase()];

  // Sin Access Token: si hay link de pago configurado, devuelvo ese.
  if (!token) {
    if (link) { res.status(200).json({ url: link }); return; }
    res.status(503).json({ error: "medio_pago_no_configurado" });
    return;
  }

  const { url, cuerpoPeticion } = p.recurrente
    ? peticionSuscripcion(plan, p, base)
    : peticionPagoUnico(plan, p, base);

  try {
    const r = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
      body: JSON.stringify(cuerpoPeticion),
    });
    const datos = await r.json();
    // La preferencia devuelve init_point; el preapproval, init_point también,
    // pero algunas respuestas de suscripción lo traen en sandbox_init_point.
    const destino = datos.init_point || datos.sandbox_init_point;
    if (!r.ok || !destino) {
      // No devolvemos el cuerpo de MercadoPago tal cual: puede traer detalles
      // de la cuenta de cobro que no tienen por qué llegar al navegador.
      res.status(502).json({ error: "mp_error" });
      return;
    }
    res.status(200).json({ url: destino, recurrente: p.recurrente });
  } catch (e) {
    res.status(500).json({ error: "excepcion" });
  }
};

function peticionPagoUnico(plan, p, base) {
  return {
    url: "https://api.mercadopago.com/checkout/preferences",
    cuerpoPeticion: {
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
    },
  };
}

function peticionSuscripcion(plan, p, base) {
  return {
    url: "https://api.mercadopago.com/preapproval",
    cuerpoPeticion: {
      reason: p.titulo,
      // El id externo viaja acá porque un preapproval no tiene `metadata`:
      // es lo que después permite saber qué modalidad se contrató.
      external_reference: plan,
      auto_recurring: {
        frequency: 1,
        frequency_type: "months",
        transaction_amount: precioEnMoneda(plan),
        currency_id: MONEDA,
      },
      back_url: base + "/descarga.html",
      status: "pending",
    },
  };
}

function jsonSeguro(texto) {
  try { return JSON.parse(texto); } catch (e) { return {}; }
}
