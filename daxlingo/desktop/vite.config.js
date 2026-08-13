// © 2026 Martín Viera. Todos los derechos reservados.

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" es obligatorio: Electron carga el build con file://, y con base
// absoluta los assets quedarían colgando de la raíz del disco.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
