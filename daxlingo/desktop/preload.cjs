// Puente entre el proceso principal y la pantalla React.
// contextIsolation activado: el renderer NO ve Node, solo esta superficie
// mínima y explícita.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("mvdax", {
  estadoActual: () => ipcRenderer.invoke("estado-actual"),
  reintentar: () => ipcRenderer.invoke("reintentar"),
  abrirExterno: (url) => ipcRenderer.invoke("abrir-externo", url),
  sitio: () => ipcRenderer.invoke("sitio"),
  alCambiarEstado: (fn) => {
    const oyente = (_evento, estado) => fn(estado);
    ipcRenderer.on("estado", oyente);
    return () => ipcRenderer.removeListener("estado", oyente);
  },
});
