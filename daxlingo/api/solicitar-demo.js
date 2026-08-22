// © 2026 Martín Viera. Todos los derechos reservados.

// MV DAX Lab · Pedido de demo.
//
// La demo NO es pública ni descargable: se entrega a pedido, en una reunión
// 1:1. Esta función recibe el formulario y avisa por mail. El mail ES el
// registro — quién pidió, con qué casilla, de qué empresa y de qué país —
// así que no hace falta una base de datos para tener el rastro.
//
// Sin RESEND_API_KEY configurada devuelve `correo_no_configurado` y la página
// cae sola al enlace `mailto:`. Es a propósito: es preferible un pedido que
// llega por otra vía a un formulario que traga los datos en silencio.

const DESTINO = "vieraschiavi@gmail.com";
const LIMITES = { nombre: 120, empresa: 120, pais: 60, mensaje: 1000, email: 200 };

// Suficiente para descartar un tipeo; no intenta validar que exista la
// casilla. Lo único que importa acá es que sea contestable.
const EMAIL_OK = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function limpiar(valor, tope) {
  return String(valor ?? "").trim().slice(0, tope);
}

// Va como texto plano y escapado a entidades: el cuerpo lo escribe un
// desconocido, y no hay motivo para que su contenido pueda inyectar HTML en
// la bandeja de quien lo lee.
function escapar(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "metodo" });
    return;
  }

  const cuerpo = typeof req.body === "string" ? JSON.parse(req.body || "{}")
                                              : (req.body || {});
  const datos = {
    nombre: limpiar(cuerpo.nombre, LIMITES.nombre),
    email: limpiar(cuerpo.email, LIMITES.email),
    empresa: limpiar(cuerpo.empresa, LIMITES.empresa),
    pais: limpiar(cuerpo.pais, LIMITES.pais),
    mensaje: limpiar(cuerpo.mensaje, LIMITES.mensaje),
  };

  const faltan = ["nombre", "email", "empresa", "pais"].filter((k) => !datos[k]);
  if (faltan.length) {
    res.status(400).json({ error: "faltan_campos", campos: faltan });
    return;
  }
  if (!EMAIL_OK.test(datos.email)) {
    res.status(400).json({ error: "email_invalido" });
    return;
  }

  const clave = process.env.RESEND_API_KEY;
  if (!clave) {
    res.status(503).json({ error: "correo_no_configurado" });
    return;
  }

  // `from` tiene que ser un dominio verificado en Resend. Mientras no tengas
  // dominio propio sirve onboarding@resend.dev, que Resend habilita para
  // probar — pero solo puede enviarte mails A VOS MISMO, que es justo lo que
  // esta función necesita.
  const remitente = process.env.RESEND_FROM || "MV DAX Lab <onboarding@resend.dev>";

  const lineas = [
    `Nombre:  ${datos.nombre}`,
    `Email:   ${datos.email}`,
    `Empresa: ${datos.empresa}`,
    `País:    ${datos.pais}`,
    datos.mensaje ? `\nMensaje:\n${datos.mensaje}` : "",
  ].join("\n");

  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "authorization": `Bearer ${clave}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        from: remitente,
        to: [DESTINO],
        reply_to: datos.email,
        subject: `Demo MV DAX Lab — ${datos.nombre} (${datos.empresa})`,
        text: lineas,
        html: `<pre style="font:14px/1.5 monospace">${escapar(lineas)}</pre>`,
      }),
    });

    if (!r.ok) {
      // El detalle de Resend queda en el log del servidor, no en el navegador:
      // puede traer la clave o el motivo interno del rechazo.
      console.error("resend", r.status, await r.text());
      res.status(502).json({ error: "envio_fallido" });
      return;
    }
    res.status(200).json({ ok: true });
  } catch (e) {
    console.error("resend", e);
    res.status(502).json({ error: "envio_fallido" });
  }
};
