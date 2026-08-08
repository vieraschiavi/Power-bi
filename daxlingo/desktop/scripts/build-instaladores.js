#!/usr/bin/env node
// MV DAX Lab · Construye los instaladores por edición.
//
// Un mismo código produce TRES instaladores distintos, con la edición
// horneada en el paquete (`edicion.json`) y —en las que se venden— bloqueada,
// para que la variable de entorno no pueda convertir una copia comercial en
// owner:
//
//   owner    · MV-DAX-Lab-OWNER-Setup    · todo desbloqueado, sin vencimiento
//   cliente  · MV-DAX-Lab-Setup          · según la licencia; 7 días de prueba
//   demo     · MV-DAX-Lab-DEMO-Setup     · prueba de 7 días, sin comprar
//
// Los tres usan appId distinto, así se pueden instalar a la vez en la misma
// PC: hace falta para mostrarle la demo a alguien con tu copia abierta.
//
// ⚠️ La edición OWNER no debe publicarse en un release público: regala el
// producto entero. Publicá solo `cliente` y `demo`.
//
// Uso:
//   node scripts/build-instaladores.js todos
//   node scripts/build-instaladores.js owner|cliente|demo

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const RAIZ = path.join(__dirname, "..");
const ARCHIVO_EDICION = path.join(RAIZ, "edicion.json");
const PAQUETE = path.join(RAIZ, "package.json");

const EDICIONES = {
  owner: {
    edicion: "owner",
    bloqueada: true,
    appId: "uy.mv.daxlab.owner",
    producto: "MV DAX Lab OWNER",
    artefacto: "MV-DAX-Lab-OWNER-Setup-${version}.${ext}",
  },
  cliente: {
    edicion: "profesional",
    bloqueada: true,
    appId: "uy.mv.daxlab",
    producto: "MV DAX Lab",
    artefacto: "MV-DAX-Lab-Setup-${version}.${ext}",
  },
  demo: {
    edicion: "demo",
    bloqueada: true,
    appId: "uy.mv.daxlab.demo",
    producto: "MV DAX Lab DEMO",
    artefacto: "MV-DAX-Lab-DEMO-Setup-${version}.${ext}",
  },
};

function leerJson(ruta) {
  return JSON.parse(fs.readFileSync(ruta, "utf8"));
}

function escribirJson(ruta, obj) {
  fs.writeFileSync(ruta, JSON.stringify(obj, null, 2) + "\n", "utf8");
}

function construir(nombre) {
  const cfg = EDICIONES[nombre];
  if (!cfg) {
    console.error(`Edición desconocida: ${nombre}. Opciones: ` +
                  Object.keys(EDICIONES).join(", ") + ", todos");
    process.exit(1);
  }

  // El secreto de licencia se hornea desde el entorno. Sin él, la copia no
  // valida licencias reales — y es preferible eso a dejar un secreto de
  // ejemplo escrito en el repo.
  const secreto = process.env.MVDAX_LICENSE_SECRET || "";
  if (nombre === "cliente" && !secreto) {
    console.warn("⚠️  MVDAX_LICENSE_SECRET no está definido: la edición " +
                 "cliente no va a poder validar las licencias que emitís.");
  }

  const paqueteOriginal = fs.readFileSync(PAQUETE, "utf8");
  const edicionOriginal = fs.existsSync(ARCHIVO_EDICION)
    ? fs.readFileSync(ARCHIVO_EDICION, "utf8") : null;

  try {
    escribirJson(ARCHIVO_EDICION, {
      _comentario: "Generado por scripts/build-instaladores.js — no editar a mano.",
      edicion: cfg.edicion,
      bloqueada: cfg.bloqueada,
      secreto: secreto,
    });

    const paquete = leerJson(PAQUETE);
    paquete.build.appId = cfg.appId;
    paquete.build.productName = cfg.producto;
    paquete.productName = cfg.producto;
    paquete.build.win.artifactName = cfg.artefacto;
    paquete.build.nsis.shortcutName = cfg.producto;
    escribirJson(PAQUETE, paquete);

    console.log(`\n▶ Construyendo la edición «${nombre}» (${cfg.producto})…`);
    execFileSync("npx", ["electron-builder", "--win"], {
      cwd: RAIZ, stdio: "inherit",
    });
    console.log(`✓ Edición «${nombre}» lista en dist-instalador/`);
  } finally {
    // Siempre se restaura el repo: un build a medias no debe dejar el
    // package.json con el appId de owner ni el secreto escrito en disco.
    fs.writeFileSync(PAQUETE, paqueteOriginal, "utf8");
    if (edicionOriginal !== null) {
      fs.writeFileSync(ARCHIVO_EDICION, edicionOriginal, "utf8");
    }
  }
}

const pedido = (process.argv[2] || "cliente").toLowerCase();
if (pedido === "todos") {
  for (const nombre of Object.keys(EDICIONES)) construir(nombre);
} else {
  construir(pedido);
}
