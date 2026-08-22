// © 2026 Martín Viera. Todos los derechos reservados.

// MV DAX Lab · Descarga del instalador, detrás del pago.
//
// EL AGUJERO QUE TAPA
// -------------------
// Hasta acá el que compraba recibía la clave de licencia y NADA de dónde
// bajar el programa. El botón de la página de descarga llevaba de vuelta a
// la lista de precios. El instalador existía únicamente como artifact de
// GitHub Actions: caduca a los 30 días, hace falta una cuenta de GitHub para
// bajarlo, y en un repo público lo baja cualquiera. O sea: inaccesible para
// el que pagó y accesible para el que no.
//
// Acá el enlace sale solo después de comprobar el pago CONTRA MERCADOPAGO,
// del lado del servidor. Armar la URL a mano no sirve.
//
// POR QUÉ REDIRIGE Y NO SIRVE EL ARCHIVO
// --------------------------------------
// El instalador pesa ~176 MB. Una función serverless de Vercel no puede
// devolver eso (ni por tamaño ni por tiempo), así que lo que se manda es un
// 302 al archivo del release. Con `GITHUB_TOKEN` configurado se pide a la
// API una URL firmada y de vida corta —lo que hace que esto siga andando
// cuando el repositorio pase a privado—; sin token se cae al enlace público
// del release, que es lo que corresponde mientras el repo sea público.
//
// La duplicación de la consulta a MercadoPago con verificar-pago.js es a
// propósito: esos dos endpoints son los que emiten licencias y están
// cubiertos por tests; meterles un refactor para ahorrar quince líneas es
// mal negocio.

const { limitar } = require("./_limitador");
const { PLANES } = require("./_planes");
const almacen = require("./_almacen");

const REPO = process.env.GITHUB_REPO || "vieraschiavi/Power-bi";
const TAG = process.env.MVDAX_TAG_RELEASE || "programa-ultimo";
const ARCHIVO = "MV-DAX-Lab-Setup.exe";

// Un preapproval solo habilita descarga mientras esté autorizado; "paused"
// o "cancelled" no. Mismo criterio que verificar-suscripcion.js.
const SUSCRIPCION_VIGENTE = new Set(["authorized"]);

async function mp(ruta, token) {
  const r = await fetch("https://api.mercadopago.com" + ruta, {
    headers: { Authorization: "Bearer " + token },
  });
  return { ok: r.ok, datos: await r.json().catch(() => ({})) };
}

// ¿Pagó? Devuelve el plan cuando sí, o el motivo cuando no. Nunca devuelve
// datos de MercadoPago al navegador: solo el veredicto.
async function comproPago(req, token) {
  const q = req.query || {};
  const idPago = String(q.payment_id || "").trim();
  const idSub = String(q.preapproval_id || "").trim();

  if (idPago) {
    if (!/^[0-9]+$/.test(idPago)) return { ok: false, motivo: "id_invalido" };
    const { ok, datos } = await mp("/v1/payments/" + idPago, token);
    if (!ok) return { ok: false, motivo: "mp_error" };
    if (datos.status !== "approved") {
      return { ok: false, motivo: "no_aprobado", estado: datos.status };
    }
    return { ok: true, plan: (datos.metadata && datos.metadata.plan) || null };
  }

  if (idSub) {
    if (!/^[a-zA-Z0-9-]{8,64}$/.test(idSub)) {
      return { ok: false, motivo: "id_invalido" };
    }
    const { ok, datos } = await mp(
      "/preapproval/" + encodeURIComponent(idSub), token);
    if (!ok) return { ok: false, motivo: "mp_error" };
    if (!SUSCRIPCION_VIGENTE.has(datos.status)) {
      return { ok: false, motivo: "no_aprobado", estado: datos.status };
    }
    return { ok: true, plan: datos.external_reference || "mensual" };
  }

  return { ok: false, motivo: "falta_id" };
}

// URL firmada de vida corta vía la API de GitHub. Es lo que permite que la
// descarga siga funcionando con el repositorio en privado.
async function urlFirmada(token) {
  const cab = {
    Authorization: "Bearer " + token,
    Accept: "application/vnd.github+json",
    "User-Agent": "mv-dax-lab",
  };
  const r = await fetch(
    `https://api.github.com/repos/${REPO}/releases/tags/${TAG}`, { headers: cab });
  if (!r.ok) return null;
  const release = await r.json();
  const asset = (release.assets || []).find((a) => a.name === ARCHIVO);
  if (!asset) return null;

  // `redirect: manual` a propósito: lo que hace falta es el Location, no el
  // cuerpo. Bajarse 176 MB adentro de la función sería justamente lo que
  // este endpoint evita.
  const r2 = await fetch(asset.url, {
    headers: { ...cab, Accept: "application/octet-stream" },
    redirect: "manual",
  });
  return r2.headers.get("location");
}

module.exports = async (req, res) => {
  // Más holgado que el de verificar-pago: acá el navegador pega una sola vez
  // por descarga, pero reintentar tras un corte de red es normal.
  if (!limitar(req, res, "descargar", 30, 60)) return;

  const token = process.env.MP_ACCESS_TOKEN;
  if (!token) {
    res.status(503).json({ error: "medio_pago_no_configurado" });
    return;
  }

  let compro;
  try {
    compro = await comproPago(req, token);
  } catch (e) {
    console.error("descargar/mp", e);
    res.status(502).json({ error: "mp_error" });
    return;
  }

  if (!compro.ok) {
    // 402 y no 403: no es que no tenga permiso, es que falta el pago.
    // 502 cuando el que falló fue MercadoPago: no es culpa de quien pide, y
    // un 400 lo mandaría a revisar un enlace que está bien.
    const codigo = { no_aprobado: 402, mp_error: 502 }[compro.motivo] || 400;
    res.status(codigo).json({ error: compro.motivo, estado: compro.estado || null });
    return;
  }
  // Un plan que no existe significa que la preferencia se armó por fuera del
  // checkout: no se entrega nada.
  if (compro.plan && !PLANES[compro.plan]) {
    res.status(400).json({ error: "plan_invalido" });
    return;
  }

  let destino = null;
  const gh = process.env.GITHUB_TOKEN;
  if (gh) {
    try {
      destino = await urlFirmada(gh);
    } catch (e) {
      console.error("descargar/github", e);
    }
  }
  // Sin token —o si la API falló— queda el enlace público del release, que
  // es el correcto mientras el repositorio sea público.
  if (!destino) {
    destino = `https://github.com/${REPO}/releases/download/${TAG}/${ARCHIVO}`;
  }

  // Se cuenta la descarga, pero NO se espera a que termine de guardarse: si
  // el almacén está lento o caído, el cliente igual se lleva su instalador.
  // La estadística es lo prescindible acá, no la descarga.
  const q = req.query || {};
  almacen.contarDescarga(q.payment_id || q.preapproval_id);

  res.setHeader("Cache-Control", "no-store");
  res.statusCode = 302;
  res.setHeader("Location", destino);
  res.end();
};

module.exports.ARCHIVO = ARCHIVO;
module.exports.TAG = TAG;
