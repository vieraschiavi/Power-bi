// MV DAX Lab · Proceso principal de Electron.
//
// La app de escritorio no reimplementa la UI: levanta el mismo motor Python
// (Streamlit) en un puerto local y lo muestra en una ventana nativa. Mientras
// el motor arranca, la ventana muestra la pantalla React de `dist/` con el
// estado real del arranque — no una pantalla en blanco de 8 segundos.
//
// Orden de arranque:
//   1. lock de instancia única (dos ventanas peleando por el puerto = lío)
//   2. ventana + splash React
//   3. se elige un puerto libre y se lanza Python
//   4. se sondea el puerto hasta que responde
//   5. la ventana navega al Streamlit ya listo

const { app, BrowserWindow, Menu, shell, dialog, ipcMain } = require("electron");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

const ES_DEV = !app.isPackaged;
let ventana = null;
let procesoPython = null;
let puerto = 0;
let ultimoEstado = { fase: "arrancando", detalle: "", error: null };

// --------------------------------------------------------------------------
// Rutas: en desarrollo el motor está un nivel arriba; empaquetado va en
// resources/app (lo copia electron-builder con extraResources).
// --------------------------------------------------------------------------
function carpetaMotor() {
  return ES_DEV ? path.join(__dirname, "..")
                : path.join(process.resourcesPath, "app");
}

function archivoEdicion() {
  const candidatos = [
    path.join(__dirname, "edicion.json"),
    path.join(process.resourcesPath || "", "edicion.json"),
  ];
  for (const c of candidatos) {
    try {
      if (fs.existsSync(c)) return JSON.parse(fs.readFileSync(c, "utf8"));
    } catch (e) { /* archivo corrupto: seguimos con el default */ }
  }
  return { edicion: "demo", bloqueada: false };
}

// Sitio público del producto. Vive en edicion.json para que el instalador
// apunte al dominio real sin recompilar nada.
function sitio(ruta) {
  const base = (archivoEdicion().sitio || "https://power-bi-mv13.vercel.app")
    .replace(/\/+$/, "");
  return ruta ? base + ruta : base;
}

// Python: primero el runtime embebido que trae el instalador; si no está
// (desarrollo, Linux, macOS), el del sistema. Sin runtime embebido el
// usuario final tendría que instalar Python — por eso el instalador lo lleva.
function buscarPython() {
  const embebido = process.platform === "win32"
    ? path.join(process.resourcesPath || "", "runtime", "python.exe")
    : path.join(process.resourcesPath || "", "runtime", "bin", "python3");
  if (fs.existsSync(embebido)) return embebido;

  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"], { encoding: "utf8" });
    if (r.status === 0) return cmd;
  }
  return null;
}

function puertoLibre() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.unref();
    s.on("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const p = s.address().port;
      s.close(() => resolve(p));
    });
  });
}

function esperarPuerto(p, intentos = 90) {
  return new Promise((resolve) => {
    let hechos = 0;
    const probar = () => {
      const req = http.get(
        { host: "127.0.0.1", port: p, path: "/", timeout: 1500 },
        (res) => { res.resume(); resolve(true); }
      );
      req.on("error", reintentar);
      req.on("timeout", () => { req.destroy(); reintentar(); });
    };
    const reintentar = () => {
      hechos += 1;
      if (hechos >= intentos) return resolve(false);
      setTimeout(probar, 500);
    };
    probar();
  });
}

function avisar(fase, detalle, error) {
  ultimoEstado = { fase, detalle: detalle || "", error: error || null };
  if (ventana && !ventana.isDestroyed()) {
    ventana.webContents.send("estado", ultimoEstado);
  }
}

// --------------------------------------------------------------------------
async function arrancarMotor() {
  const python = buscarPython();
  if (!python) {
    avisar("error", "", "no_python");
    return;
  }

  const motor = carpetaMotor();
  const appPy = path.join(motor, "app", "app.py");
  if (!fs.existsSync(appPy)) {
    avisar("error", appPy, "sin_motor");
    return;
  }

  puerto = await puertoLibre();
  const edicion = archivoEdicion();
  const datos = app.getPath("userData");

  avisar("arrancando", `puerto ${puerto}`);
  procesoPython = spawn(python, [
    "-m", "streamlit", "run", appPy,
    "--server.port", String(puerto),
    "--server.address", "127.0.0.1",
    "--server.headless", "true",
    "--browser.gatherUsageStats", "false",
    "--global.developmentMode", "false",
  ], {
    cwd: motor,
    env: {
      ...process.env,
      MVDAXLAB_DATOS: datos,
      MVDAXLAB_BANDEJA: path.join(datos, "bandeja"),
      MVDAX_EDICION: edicion.edicion || "demo",
      MVDAX_EDICION_ARCHIVO: path.join(__dirname, "edicion.json"),
      PYTHONIOENCODING: "utf-8",
      PYTHONUNBUFFERED: "1",
    },
    windowsHide: true,
  });

  let salida = "";
  const registrar = (b) => {
    salida += b.toString();
    if (salida.length > 8000) salida = salida.slice(-8000);
  };
  procesoPython.stdout.on("data", registrar);
  procesoPython.stderr.on("data", registrar);

  procesoPython.on("exit", (codigo) => {
    // Si Python se cae ANTES de que la ventana navegue, el usuario tiene que
    // ver por qué. Después de navegar, un exit al cerrar es lo esperado.
    if (ultimoEstado.fase !== "listo" && codigo !== 0 && codigo !== null) {
      avisar("error", salida.slice(-1200), "python_murio");
    }
  });

  const vivo = await esperarPuerto(puerto);
  if (!vivo) {
    avisar("error", salida.slice(-1200), "sin_respuesta");
    return;
  }
  avisar("listo", `http://127.0.0.1:${puerto}`);
  if (ventana && !ventana.isDestroyed()) {
    ventana.loadURL(`http://127.0.0.1:${puerto}`);
  }
}

function detenerMotor() {
  if (!procesoPython || procesoPython.killed) return;
  // En Windows, matar el proceso de Streamlit no alcanza: deja hijos vivos y
  // el puerto tomado. taskkill /T se lleva el árbol entero.
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(procesoPython.pid), "/f", "/t"]);
  } else {
    try { process.kill(-procesoPython.pid, "SIGTERM"); }
    catch (e) { procesoPython.kill("SIGTERM"); }
  }
  procesoPython = null;
}

// --------------------------------------------------------------------------
function construirMenu() {
  const plantilla = [
    {
      label: "Archivo",
      submenu: [
        {
          label: "Abrir la carpeta de datos",
          click: () => shell.openPath(app.getPath("userData")),
        },
        { type: "separator" },
        { role: "quit", label: "Salir" },
      ],
    },
    {
      label: "Ver",
      submenu: [
        { role: "reload", label: "Recargar" },
        { role: "forceReload", label: "Recargar sin caché" },
        { type: "separator" },
        { role: "resetZoom", label: "Zoom normal" },
        { role: "zoomIn", label: "Acercar" },
        { role: "zoomOut", label: "Alejar" },
        { type: "separator" },
        { role: "togglefullscreen", label: "Pantalla completa" },
        { role: "toggleDevTools", label: "Herramientas de desarrollo" },
      ],
    },
    {
      label: "Ayuda",
      submenu: [
        {
          label: "Sitio de MV DAX Lab",
          click: () => shell.openExternal(sitio()),
        },
        {
          label: "Comprar una licencia",
          click: () => shell.openExternal(sitio("/#precios")),
        },
        { type: "separator" },
        {
          label: "Acerca de",
          click: () => {
            const ed = archivoEdicion();
            dialog.showMessageBox(ventana, {
              type: "info",
              title: "MV DAX Lab",
              message: `MV DAX Lab ${app.getVersion()}`,
              detail: [
                `Edición: ${ed.edicion}`,
                `Electron ${process.versions.electron} · Node ${process.versions.node}`,
                `Datos: ${app.getPath("userData")}`,
              ].join("\n"),
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(plantilla));
}

function crearVentana() {
  ventana = new BrowserWindow({
    width: 1500,
    height: 940,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: "#081527",
    show: false,
    icon: path.join(__dirname, "build", "icono.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  ventana.once("ready-to-show", () => ventana.show());
  ventana.loadFile(path.join(__dirname, "dist", "index.html"));

  // Los enlaces externos (comprar, docs de Microsoft) van al navegador del
  // sistema, no a una ventana de Electron sin barra de direcciones.
  ventana.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  ventana.on("closed", () => { ventana = null; });
}

// --------------------------------------------------------------------------
const lock = app.requestSingleInstanceLock();
if (!lock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (ventana) {
      if (ventana.isMinimized()) ventana.restore();
      ventana.focus();
    }
  });

  app.whenReady().then(() => {
    ipcMain.handle("estado-actual", () => ultimoEstado);
    ipcMain.handle("reintentar", async () => { await arrancarMotor(); });
    ipcMain.handle("abrir-externo", (_e, url) => shell.openExternal(url));
    ipcMain.handle("sitio", () => sitio());

    construirMenu();
    crearVentana();
    arrancarMotor();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) crearVentana();
    });
  });

  app.on("window-all-closed", () => {
    detenerMotor();
    if (process.platform !== "darwin") app.quit();
  });
  app.on("before-quit", detenerMotor);
  process.on("exit", detenerMotor);
}
