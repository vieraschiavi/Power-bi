// © 2026 Martín Viera. Todos los derechos reservados.

// Firma y verificación de licencias MV DAX Lab (HMAC-SHA256, sin dependencias).
// Prefijo "_" para que Vercel NO lo trate como endpoint: es un módulo interno.
//
// Es el MISMO formato que lee `dxl/licencia.py` en la app de escritorio:
//     MVDAX1.<payload_base64url>.<firma_base64url>
// Si tocás algo acá, tocá también el módulo Python — hay un test que compara
// las dos implementaciones sobre el mismo payload.

const crypto = require("crypto");

const PREFIJO = "MVDAX1";

function b64u(buf) {
  return Buffer.from(buf).toString("base64")
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function firmar(payload, secreto) {
  // separadores sin espacios: el payload tiene que salir byte a byte igual
  // que el de Python (json.dumps con separators=(",", ":")).
  const cuerpo = b64u(JSON.stringify(payload));
  const firma = b64u(crypto.createHmac("sha256", secreto).update(cuerpo).digest());
  return PREFIJO + "." + cuerpo + "." + firma;
}

function verificar(clave, secreto) {
  if (typeof clave !== "string") return null;
  const partes = clave.trim().split(".");
  if (partes.length !== 3 || partes[0] !== PREFIJO) return null;
  const [, cuerpo, firma] = partes;
  const esperada = b64u(crypto.createHmac("sha256", secreto).update(cuerpo).digest());
  const a = Buffer.from(firma), b = Buffer.from(esperada);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  let payload;
  try {
    const json = Buffer.from(cuerpo.replace(/-/g, "+").replace(/_/g, "/"),
                             "base64").toString("utf8");
    payload = JSON.parse(json);
  } catch (e) { return null; }
  if (!payload || typeof payload !== "object") return null;
  if (payload.exp != null && Date.now() / 1000 > Number(payload.exp)) return null;
  return payload;
}

module.exports = { firmar, verificar, PREFIJO };
