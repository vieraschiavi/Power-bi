// © 2026 Martín Viera. Todos los derechos reservados.

// Freno por IP para las funciones serverless (api/*.js).
//
// Es "mejor esfuerzo", no un límite distribuido: cada instancia de la función
// tiene su propia memoria, así que el freno real es "por IP y por instancia
// tibia". Igual vale: el abuso real es un mismo cliente golpeando la misma
// instancia en ráfaga, y las instancias tibias de Vercel viven varios minutos.

const cubos = new Map(); // clave -> { fichas, visto }

function ipDe(req) {
  const h = req.headers || {};
  const xff = h["x-forwarded-for"];
  if (xff) return String(xff).split(",")[0].trim();
  return h["x-real-ip"] || (req.socket && req.socket.remoteAddress) || "desconocida";
}

// Cubo de fichas: `cupo` peticiones por `ventana` segundos, con recarga
// proporcional al tiempo transcurrido.
function limitar(req, res, nombre, cupo, ventana) {
  const clave = nombre + ":" + ipDe(req);
  const ahora = Date.now();
  const cubo = cubos.get(clave) || { fichas: cupo, visto: ahora };
  const recarga = ((ahora - cubo.visto) / 1000) * (cupo / ventana);
  cubo.fichas = Math.min(cupo, cubo.fichas + recarga);
  cubo.visto = ahora;

  if (cubo.fichas < 1) {
    cubos.set(clave, cubo);
    if (res && res.status) {
      res.status(429).json({ error: "demasiadas_peticiones" });
    }
    return false;
  }
  cubo.fichas -= 1;
  cubos.set(clave, cubo);

  // Sin esto el Map crece sin techo en una instancia de vida larga.
  if (cubos.size > 5000) {
    for (const [k, v] of cubos) {
      if (ahora - v.visto > ventana * 2000) cubos.delete(k);
    }
  }
  return true;
}

module.exports = { limitar, ipDe };
