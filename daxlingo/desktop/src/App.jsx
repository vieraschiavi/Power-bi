// © 2026 Martín Viera. Todos los derechos reservados.

import { useEffect, useState } from "react";

// Pantalla de arranque de MV DAX Lab.
//
// No es decoración: es la única superficie donde el usuario puede enterarse de
// por qué la app no abrió. Cuando el motor Python levanta bien, el proceso
// principal navega a Streamlit y esta pantalla desaparece sola.

const ERRORES = {
  no_python: {
    titulo: "No encontramos Python",
    texto:
      "La app necesita el runtime que trae el instalador. Si estás corriendo " +
      "desde el código, instalá Python 3.11 o superior y volvé a abrir.",
    accion: "https://www.python.org/downloads/",
    accionTexto: "Descargar Python",
  },
  sin_motor: {
    titulo: "Falta el motor",
    texto:
      "No se encontró app/app.py junto a la aplicación. Si esto pasó después " +
      "de una instalación, reinstalá: probablemente quedó incompleta.",
  },
  python_murio: {
    titulo: "El motor se cerró al arrancar",
    texto:
      "Python arrancó pero terminó antes de levantar el servidor. Abajo está " +
      "el final del registro, que suele decir qué falta.",
  },
  sin_respuesta: {
    titulo: "El motor no respondió a tiempo",
    texto:
      "El servidor local no contestó en 45 segundos. Suele ser un antivirus " +
      "o un firewall bloqueando la conexión a 127.0.0.1.",
  },
};

const PASOS = [
  "Preparando el entorno",
  "Levantando el motor de análisis",
  "Cargando el catálogo DAX",
  "Casi listo",
];

export default function App() {
  const [estado, setEstado] = useState({ fase: "arrancando", detalle: "" });
  const [paso, setPaso] = useState(0);
  const [sitio, setSitio] = useState("");

  useEffect(() => {
    if (!window.mvdax) return;
    window.mvdax.estadoActual().then(setEstado);
    window.mvdax.sitio().then(setSitio);
    return window.mvdax.alCambiarEstado(setEstado);
  }, []);

  useEffect(() => {
    if (estado.fase !== "arrancando") return;
    // El avance es indicativo: el motor no reporta porcentaje real, así que
    // fingir uno exacto sería mentir. Se muestran las etapas, no un número.
    const t = setInterval(
      () => setPaso((p) => Math.min(p + 1, PASOS.length - 1)),
      2200
    );
    return () => clearInterval(t);
  }, [estado.fase]);

  const error = estado.fase === "error" ? ERRORES[estado.error] : null;

  return (
    <div className="pantalla">
      <div className="marca">
        <span className="cuadro" />
        <h1>
          MV <b>DAX Lab</b>
        </h1>
      </div>
      <p className="lema">
        Tu modelo de Power BI, explicado, corregido y exportado.
      </p>

      {!error && (
        <div className="arranque">
          <div className="barra">
            <span style={{ width: `${((paso + 1) / PASOS.length) * 100}%` }} />
          </div>
          <p className="paso">{PASOS[paso]}…</p>
          {estado.detalle && <p className="detalle">{estado.detalle}</p>}
        </div>
      )}

      {error && (
        <div className="error">
          <h2>{error.titulo}</h2>
          <p>{error.texto}</p>
          {estado.detalle && <pre className="registro">{estado.detalle}</pre>}
          <div className="botones">
            <button
              className="btn-a"
              onClick={() => window.mvdax && window.mvdax.reintentar()}
            >
              Reintentar
            </button>
            {error.accion && (
              <button
                className="btn-b"
                onClick={() =>
                  window.mvdax && window.mvdax.abrirExterno(error.accion)
                }
              >
                {error.accionTexto}
              </button>
            )}
          </div>
        </div>
      )}

      <footer>
        {sitio && (
          <button
            className="enlace"
            onClick={() => window.mvdax && window.mvdax.abrirExterno(sitio)}
          >
            {sitio.replace(/^https?:\/\//, "")}
          </button>
        )}
      </footer>
    </div>
  );
}
