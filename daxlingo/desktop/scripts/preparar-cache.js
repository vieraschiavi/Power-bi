#!/usr/bin/env node
// MV DAX Lab · Dejar la caché de electron-builder lista ANTES de construir.
//
// Existe por dos fallas reales al construir en una PC Windows común, las dos
// en el mismo build:
//
//   1. «Cannot create symbolic link : El cliente no dispone de un privilegio
//      requerido» al descomprimir winCodeSign-2.6.0.7z. Ese paquete trae DOS
//      symlinks de macOS (`darwin/10.12/lib/libcrypto.dylib` y `libssl.dylib`)
//      que en Windows sólo puede crear un administrador o un usuario con el
//      Modo desarrollador prendido. 7-Zip sale con código 2, y
//      electron-builder da por fallada toda la extracción — aunque esos dos
//      archivos sean de macOS y no sirvan para nada en un build de Windows.
//
//      Acá se descomprime el paquete a mano EXCLUYENDO `darwin` y los
//      `.dylib`. Sin symlinks no hace falta ningún privilegio, y
//      electron-builder encuentra la carpeta ya lista y ni la toca.
//      Lo que sí necesita —`rcedit`, que le pone el icono y la versión al
//      .exe, y `signtool`— vive en `windows-10\` y se extrae igual.
//
//   2. «Espacio en disco insuficiente» en C:. La caché por defecto va a
//      `C:\Users\<vos>\AppData\Local\electron-builder\Cache`, y entre el
//      Electron de 111 MB y los reintentos llena el disco del sistema.
//      Por defecto la caché pasa a vivir al lado del repo — o sea, en el
//      mismo disco donde tenés el proyecto — y se puede mandar a donde
//      quieras.
//
// Elegir el disco, por orden de precedencia:
//
//     node scripts/preparar-cache.js E:\mv-cache     ← argumento
//     set MVDAX_BUILD_CACHE=E:\mv-cache              ← variable de entorno
//     (nada)                                         ← <repo>\.cache-build
//
// Devuelve por stdout la carpeta elegida, para que el .bat la muestre.

const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const RAIZ = path.join(__dirname, "..");

// La versión la fija electron-builder 24.13.3. Si algún día sube, esto no
// rompe nada: la carpeta no va a existir, electron-builder la baja como
// siempre y volvemos al problema del symlink — con el aviso de abajo.
const WINCODESIGN = "winCodeSign-2.6.0";
const URL_WINCODESIGN =
  "https://github.com/electron-userland/electron-builder-binaries/releases" +
  `/download/${WINCODESIGN}/${WINCODESIGN}.7z`;

// Con menos que esto el build muere a mitad de camino y deja la caché rota,
// que es peor que no haber empezado. Electron sin comprimir (~400 MB), los
// tres instaladores (~530 MB) y el temporal de NSIS.
const GIGAS_MINIMOS = Number(process.env.MVDAX_MIN_GB || 2);


function carpetaCache(pedida) {
  const elegida = (pedida || process.env.MVDAX_BUILD_CACHE || "").trim();
  if (elegida) return path.resolve(elegida);
  return path.join(RAIZ, ".cache-build");
}


function gigasLibres(carpeta) {
  // Sube hasta el primer directorio que exista: statfs sobre una carpeta que
  // todavía no creamos falla.
  let d = path.resolve(carpeta);
  while (!fs.existsSync(d)) {
    const padre = path.dirname(d);
    if (padre === d) return null;
    d = padre;
  }
  try {
    const s = fs.statfsSync(d);
    return (s.bsize * s.bavail) / 1024 ** 3;
  } catch {
    return null;   // statfs no está en todas las versiones de Node
  }
}


function exigirEspacio(nombre, carpeta) {
  const libres = gigasLibres(carpeta);
  if (libres === null) {
    console.log(`  ${nombre}: ${carpeta} (no pude medir el espacio libre)`);
    return;
  }
  console.log(`  ${nombre}: ${carpeta} — ${libres.toFixed(1)} GB libres`);
  if (libres < GIGAS_MINIMOS) {
    console.error(
      `\n  [X] Hacen falta al menos ${GIGAS_MINIMOS} GB libres y hay ` +
      `${libres.toFixed(1)} GB en ${path.parse(carpeta).root}\n\n` +
      `      Liberá espacio, o mandá la caché a otro disco:\n` +
      `          set MVDAX_BUILD_CACHE=E:\\mv-cache\n`);
    process.exit(1);
  }
}


function siete() {
  const exe = path.join(RAIZ, "node_modules", "7zip-bin", "win", "x64",
                        "7za.exe");
  return fs.existsSync(exe) ? exe : null;
}


async function bajar(url, destino) {
  const r = await fetch(url, { redirect: "follow" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} al bajar ${url}`);
  fs.writeFileSync(destino, Buffer.from(await r.arrayBuffer()));
}


/**
 * Deja `<cache>/winCodeSign/winCodeSign-2.6.0/` armado sin un solo symlink.
 * Si algo sale mal NO aborta el build: se avisa y se deja que
 * electron-builder lo intente a su manera, que en una PC con Modo
 * desarrollador o con permisos de administrador funciona igual.
 */
async function prepararWinCodeSign(cache) {
  const destino = path.join(cache, "winCodeSign", WINCODESIGN);
  const testigo = path.join(destino, "windows-10", "x64", "signtool.exe");

  if (fs.existsSync(testigo)) {
    console.log("  winCodeSign: ya estaba listo, no se toca");
    return;
  }

  const exe7z = siete();
  if (!exe7z) {
    console.warn("  ⚠️  winCodeSign: no encontré 7za.exe (¿falta npm install?);" +
                 " lo va a resolver electron-builder");
    return;
  }

  const temporal = path.join(cache, "winCodeSign", `.tmp-${process.pid}`);
  const archivo = path.join(cache, "winCodeSign", `.tmp-${process.pid}.7z`);
  fs.mkdirSync(path.dirname(temporal), { recursive: true });

  try {
    console.log("  winCodeSign: bajando…");
    await bajar(URL_WINCODESIGN, archivo);

    console.log("  winCodeSign: descomprimiendo sin los symlinks de macOS…");
    // -xr!darwin  y  -xr!*.dylib  sacan lo único que necesita privilegios.
    execFileSync(exe7z, ["x", "-bd", "-y", "-xr!darwin", "-xr!*.dylib",
                         archivo, `-o${temporal}`], { stdio: "pipe" });

    fs.mkdirSync(path.dirname(destino), { recursive: true });
    fs.rmSync(destino, { recursive: true, force: true });
    fs.renameSync(temporal, destino);
    console.log("  winCodeSign: listo");
  } catch (e) {
    console.warn(`  ⚠️  winCodeSign: no pude prepararlo (${e.message.trim()}).`);
    console.warn("      Si el build falla con «Cannot create symbolic link»," +
                 " prendé el Modo desarrollador de Windows");
    console.warn("      (Configuración › Privacidad y seguridad › Para" +
                 " desarrolladores) o corré este .bat como administrador.");
    fs.rmSync(temporal, { recursive: true, force: true });
  } finally {
    fs.rmSync(archivo, { force: true });
  }
}


/** Prepara todo y devuelve la carpeta de caché. La usa build-instaladores.js. */
async function preparar(pedida) {
  const cache = carpetaCache(pedida);
  fs.mkdirSync(cache, { recursive: true });

  console.log("\n▶ Preparando la caché de construcción…");
  exigirEspacio("caché ", cache);
  if (path.parse(cache).root !== path.parse(RAIZ).root) {
    exigirEspacio("salida", RAIZ);
  }

  // Esto es lo que saca la caché de C:. electron-builder lee esta variable.
  process.env.ELECTRON_BUILDER_CACHE = cache;

  if (os.platform() === "win32") await prepararWinCodeSign(cache);
  return cache;
}


module.exports = { preparar, carpetaCache };

if (require.main === module) {
  preparar(process.argv[2]).then((c) => console.log(c)).catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
