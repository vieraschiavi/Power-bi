// © 2026 Martín Viera. Todos los derechos reservados.

// MV DAX Lab · Aviso de MercadoPago cuando un pago se acredita.
//
// EL PROBLEMA QUE RESUELVE
// ------------------------
// Hasta acá la venta dependía de que el cliente volviera al sitio: la página
// de descarga preguntaba «¿está aprobado?» y recién ahí emitía la clave. Si
// cerraba el navegador en la pantalla de MercadoPago —o si la tarjeta se
// acreditaba veinte minutos después, que con transferencia y efectivo es lo
// normal— pagaba y no recibía nada. La única salida era que escribiera
// pidiendo la clave a mano.
//
// MercadoPago avisa por acá aunque no vuelva nadie. Este endpoint emite la
// licencia, se la manda por mail con el enlace de descarga, y deja la venta
// registrada para el monitor.
//
// DOS CANDADOS, Y EL SEGUNDO ES EL QUE IMPORTA
// --------------------------------------------
// 1. Firma: MercadoPago manda `x-signature` con un HMAC del aviso. Se
//    verifica cuando MP_WEBHOOK_SECRET está configurado.
// 2. **Nunca se le cree al cuerpo del aviso.** Del POST solo se saca el ID; el
//    estado, el monto y el pagador se vuelven a pedir a la API de MercadoPago
//    con el access token. Por eso, aun sin la firma configurada, un aviso
//    falso no puede inventar una venta: tendría que nombrar un pago real y
//    aprobado, y ese pago existe porque alguien lo pagó.
//
// Siempre responde 200. Un 500 hace que MercadoPago reintente en bucle, y un
// error nuestro —el mail, el almacén— no es motivo para que reintente: el
// pago ya está bien. Lo que salió mal se ve en los logs y en el monitor.

const crypto = require("crypto");
const { firmar } = require("./_licencia");
const { PLANES, DIAS_MENSUAL, precioEnMoneda, MONEDA } = require("./_planes");
const almacen = require("./_almacen");

const VIGENTES = new Set(["authorized"]);

// El manifiesto que MercadoPago firma, tal cual lo documenta: los campos van
// en este orden y con estos separadores, y los que faltan se omiten enteros.
function firmaValida(req, secreto) {
  const cabeceras = req.headers || {};
  const cabecera = cabeceras["x-signature"];
  if (!cabecera) return false;

  const partes = {};
  for (const trozo of String(cabecera).split(",")) {
    const i = trozo.indexOf("=");
    if (i > 0) partes[trozo.slice(0, i).trim()] = trozo.slice(i + 1).trim();
  }
  if (!partes.ts || !partes.v1) return false;

  const q = req.query || {};
  // `data.id` es el que va al manifiesto, en minúsculas si trae letras.
  const id = String((q["data.id"] || q.id || "")).toLowerCase();
  const pedido = cabeceras["x-request-id"] || "";

  let manifiesto = "";
  if (id) manifiesto += `id:${id};`;
  if (pedido) manifiesto += `request-id:${pedido};`;
  manifiesto += `ts:${partes.ts};`;

  const esperada = crypto.createHmac("sha256", secreto)
    .update(manifiesto).digest("hex");
  const a = Buffer.from(partes.v1), b = Buffer.from(esperada);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

async function mp(ruta, token) {
  const r = await fetch("https://api.mercadopago.com" + ruta, {
    headers: { Authorization: "Bearer " + token },
  });
  return { ok: r.ok, datos: await r.json().catch(() => ({})) };
}

// El mail es lo que convierte "pagué" en "tengo el programa". Si no hay
// Resend configurado no se rompe nada: la clave igual queda emitida y la
// página de descarga la muestra cuando el cliente vuelve.
async function avisar(sitio, venta, clave) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey || !venta.email) return false;

  const enlace = `${sitio}/api/descargar?` +
    (venta.tipo === "suscripcion" ? "preapproval_id=" : "payment_id=") +
    encodeURIComponent(venta.id);

  const texto = [
    "¡Gracias por comprar MV DAX Lab!",
    "",
    "Tu clave de licencia:",
    clave,
    "",
    "Descargá el instalador para Windows acá:",
    enlace,
    "",
    "Cómo activarlo: abrí MV DAX Lab, andá a la pestaña Licencia, pegá la",
    "clave y tocá Activar. Guardá este mail: la clave sirve para reinstalar.",
    venta.tipo === "suscripcion"
      ? "\nTu suscripción es mensual: la clave vale 32 días y se renueva sola\n" +
        "mientras la suscripción siga activa. Volvé a este enlace cuando el\n" +
        "programa te pida una clave nueva."
      : "",
    "",
    "Cualquier cosa, respondé este mail.",
  ].join("\n");

  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        authorization: "Bearer " + apiKey,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        from: process.env.RESEND_FROM || "MV DAX Lab <onboarding@resend.dev>",
        to: [venta.email],
        reply_to: "vieraschiavi@gmail.com",
        subject: "Tu licencia de MV DAX Lab y el enlace de descarga",
        text: texto,
      }),
    });
    if (!r.ok) console.error("webhook/resend", r.status, await r.text());
    return r.ok;
  } catch (e) {
    console.error("webhook/resend", e);
    return false;
  }
}

module.exports = async (req, res) => {
  // 200 y punto: un método raro no tiene por qué generar reintentos.
  if (req.method !== "POST") {
    res.status(200).json({ ok: true, nota: "solo POST hace algo" });
    return;
  }

  const token = process.env.MP_ACCESS_TOKEN;
  const secreto = process.env.MVDAX_LICENSE_SECRET;
  const secretoWebhook = process.env.MP_WEBHOOK_SECRET;

  if (secretoWebhook && !firmaValida(req, secretoWebhook)) {
    // Acá sí 401: es el único caso en el que conviene que MercadoPago sepa
    // que el aviso no se aceptó.
    res.status(401).json({ error: "firma_invalida" });
    return;
  }
  if (!token) {
    console.error("webhook: sin MP_ACCESS_TOKEN, no se puede confirmar nada");
    res.status(200).json({ ok: false, error: "sin_token" });
    return;
  }

  const cuerpo = typeof req.body === "string"
    ? (() => { try { return JSON.parse(req.body || "{}"); } catch (e) { return {}; } })()
    : (req.body || {});
  const q = req.query || {};
  const tipo = String(cuerpo.type || cuerpo.topic || q.type || q.topic || "");
  const id = String((cuerpo.data && cuerpo.data.id) || cuerpo.id ||
                    q["data.id"] || q.id || "").trim();

  if (!id) {
    res.status(200).json({ ok: true, nota: "aviso sin id" });
    return;
  }

  try {
    let venta = null;

    if (tipo.startsWith("payment")) {
      if (!/^[0-9]+$/.test(id)) {
        res.status(200).json({ ok: true, nota: "id no numérico" });
        return;
      }
      const { ok, datos } = await mp("/v1/payments/" + id, token);
      if (!ok || datos.status !== "approved") {
        res.status(200).json({ ok: true, estado: datos.status || "?" });
        return;
      }
      const plan = (datos.metadata && datos.metadata.plan) || null;
      if (!PLANES[plan]) {
        console.error("webhook: pago aprobado con plan desconocido", plan);
        res.status(200).json({ ok: true, nota: "plan desconocido" });
        return;
      }
      venta = {
        id, tipo: "pago", plan,
        email: (datos.payer && datos.payer.email) || null,
        usd: PLANES[plan].usd,
        cobrado: datos.transaction_amount ?? precioEnMoneda(plan),
        moneda: datos.currency_id || MONEDA,
      };
    } else if (tipo.startsWith("subscription") || tipo.startsWith("preapproval")) {
      if (!/^[a-zA-Z0-9-]{8,64}$/.test(id)) {
        res.status(200).json({ ok: true, nota: "id inválido" });
        return;
      }
      const { ok, datos } = await mp(
        "/preapproval/" + encodeURIComponent(id), token);
      if (!ok || !VIGENTES.has(datos.status)) {
        res.status(200).json({ ok: true, estado: datos.status || "?" });
        return;
      }
      const plan = datos.external_reference || "mensual";
      if (!PLANES[plan]) {
        res.status(200).json({ ok: true, nota: "plan desconocido" });
        return;
      }
      venta = {
        id, tipo: "suscripcion", plan,
        email: datos.payer_email || null,
        usd: PLANES[plan].usd,
        cobrado: (datos.auto_recurring && datos.auto_recurring.transaction_amount) ??
                 precioEnMoneda(plan),
        moneda: (datos.auto_recurring && datos.auto_recurring.currency_id) || MONEDA,
      };
    } else {
      // MercadoPago manda avisos de muchas cosas (merchant_order, chargebacks…).
      res.status(200).json({ ok: true, nota: "tipo ignorado: " + tipo });
      return;
    }

    // La venta se registra aunque no haya secreto de licencias: perder la
    // estadística además de la clave sería empeorar el problema.
    await almacen.guardarVenta(venta);

    if (!secreto) {
      console.error("webhook: venta registrada pero SIN MVDAX_LICENSE_SECRET, " +
                    "no se pudo emitir la licencia del pago " + id);
      res.status(200).json({ ok: true, licencia: false });
      return;
    }

    const ahora = Math.floor(Date.now() / 1000);
    const clave = firmar({
      plan: venta.plan,
      equipos: PLANES[venta.plan].equipos,
      [venta.tipo === "suscripcion" ? "sub" : "pid"]: id,
      email: venta.email,
      iat: ahora,
      ...(venta.tipo === "suscripcion"
          ? { exp: ahora + DIAS_MENSUAL * 86400 } : {}),
    }, secreto);

    const sitio = process.env.MVDAXLAB_SITIO ||
      ((req.headers && req.headers.host) ? "https://" + req.headers.host : "");
    const avisado = await avisar(sitio, venta, clave);

    res.status(200).json({ ok: true, licencia: true, mail: avisado });
  } catch (e) {
    console.error("webhook", e);
    // 200 igual: reintentar no va a arreglar un error nuestro.
    res.status(200).json({ ok: false });
  }
};

module.exports.firmaValida = firmaValida;
