#!/usr/bin/env node
// © 2026 Martín Viera. Todos los derechos reservados.

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
//   node scripts/build-instaladores.js owner E:\mv-cache   ← caché en otro disco
//
// El segundo argumento elige DÓNDE trabaja electron-builder. Por defecto es
// `.cache-build` al lado de este proyecto, o sea el mismo disco donde lo
// tenés: la caché por defecto de electron-builder vive en C: y llenar el
// disco del sistema rompe el build a mitad de camino.

const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const { preparar } = require("./preparar-cache.js");

function ejecutar(comando) {
  execSync(comando, { cwd: RAIZ, stdio: "inherit" });
}

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
    // El sitio se conserva del archivo del repo (o se pisa con MVDAXLAB_SITIO):
    // si se perdiera acá, los instaladores saldrían apuntando al dominio por
    // defecto y los botones de compra llevarían a ningún lado.
    const sitio = process.env.MVDAXLAB_SITIO ||
      (edicionOriginal ? (leerJson(ARCHIVO_EDICION).sitio || "") : "");
    escribirJson(ARCHIVO_EDICION, {
      _comentario: "Generado por scripts/build-instaladores.js — no editar a mano.",
      edicion: cfg.edicion,
      bloqueada: cfg.bloqueada,
      secreto: secreto,
      sitio: sitio,
    });

    const paquete = leerJson(PAQUETE);
    paquete.build.appId = cfg.appId;
    paquete.build.productName = cfg.producto;
    paquete.productName = cfg.producto;
    paquete.build.win.artifactName = cfg.artefacto;
    paquete.build.nsis.shortcutName = cfg.producto;
    escribirJson(PAQUETE, paquete);

    console.log(`\n▶ Construyendo la edición «${nombre}» (${cfg.producto})…`);
    // `shell: true` no es cosmético: en Windows —la única plataforma donde
    // este script sirve— `npx` es `npx.cmd`, y execFileSync sin shell no
    // resuelve la extensión y muere con ENOENT.
    ejecutar("npx electron-builder --win");
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

// El front de React se compila UNA vez y sirve para las tres ediciones: lo
// que cambia entre ellas es el sello, no la interfaz. Sin este paso el
// instalador se armaba con lo que hubiera en `dist/` —o sin nada— porque
// `files` incluye `dist/**/*` y nadie lo generaba: el script saltaba directo
// a electron-builder, a diferencia del npm script `dist`.
function compilarFront() {
  console.log("\n▶ Compilando el front (vite)…");
  ejecutar("npm run build");
}

const pedido = (process.argv[2] || "cliente").toLowerCase();

// La caché va primero: elige el disco, comprueba que haya lugar y deja
// winCodeSign descomprimido sin los symlinks de macOS, que en Windows exigen
// privilegios que un usuario común no tiene. Ver scripts/preparar-cache.js.
preparar(process.argv[3]).then((cache) => {
  console.log(`  ELECTRON_BUILDER_CACHE = ${cache}`);
  compilarFront();
  if (pedido === "todos") {
    for (const nombre of Object.keys(EDICIONES)) construir(nombre);
  } else {
    construir(pedido);
  }
}).catch((e) => {
  console.error(e);
  process.exit(1);
});
