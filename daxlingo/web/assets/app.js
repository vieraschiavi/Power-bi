// © 2026 Martín Viera. Todos los derechos reservados.

// MV DAX Lab · Lógica de la landing: idioma, galería y checkout.
// JS vanilla, sin dependencias ni build.

(function () {
  "use strict";

  const IDIOMAS = ["es", "en", "pt"];
  const CLAVE_GUARDADA = "mvdaxlab.idioma";

  function idiomaInicial() {
    const url = new URLSearchParams(location.search).get("lang");
    if (IDIOMAS.includes(url)) return url;
    const guardado = localStorage.getItem(CLAVE_GUARDADA);
    if (IDIOMAS.includes(guardado)) return guardado;
    const nav = (navigator.language || "es").slice(0, 2).toLowerCase();
    return IDIOMAS.includes(nav) ? nav : "es";
  }

  function aplicarIdioma(idioma) {
    const textos = window.TEXTOS[idioma] || window.TEXTOS.es;
    document.documentElement.lang = idioma;

    document.querySelectorAll("[data-i]").forEach(function (nodo) {
      const clave = nodo.getAttribute("data-i");
      const valor = textos[clave];
      if (valor === undefined) return;
      // Varios textos traen <b> o <br>: por eso innerHTML y no textContent.
      // El contenido es nuestro (i18n.js), no entra nada del usuario.
      nodo.innerHTML = valor;
    });
    document.querySelectorAll("[data-i-alt]").forEach(function (nodo) {
      const valor = textos[nodo.getAttribute("data-i-alt")];
      if (valor !== undefined) nodo.setAttribute("alt", valor);
    });

    // Las capturas están tomadas del programa en cada idioma. Si alguna no
    // está —un deploy sin los binarios, un asset que no subió— se esconde su
    // tarjeta entera: una galería con un ícono roto se ve peor que una
    // galería con una tarjeta menos.
    document.querySelectorAll("[data-shot]").forEach(function (img) {
      img.onerror = function () {
        const tarjeta = img.closest(".shot");
        if (tarjeta) tarjeta.hidden = true;
      };
      img.onload = function () {
        const tarjeta = img.closest(".shot");
        if (tarjeta) tarjeta.hidden = false;
      };
      img.src = "assets/img/" + idioma + "/" + img.getAttribute("data-shot") + ".png";
    });

    const video = document.getElementById("video-demo");
    if (video) {
      const fuente = video.querySelector("source");
      const nueva = "assets/video/demo-" + idioma + ".mp4";
      if (fuente && !fuente.src.endsWith(nueva)) {
        fuente.src = nueva;
        // Mismo criterio que con las capturas: si el video no está, se
        // esconde la sección en vez de dejar un reproductor negro y muerto.
        const seccion = document.getElementById("video");
        video.onerror = function () { if (seccion) seccion.hidden = true; };
        video.onloadeddata = function () { if (seccion) seccion.hidden = false; };
        video.load();
      }
    }

    document.querySelectorAll(".idiomas button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.lang === idioma));
    });
    localStorage.setItem(CLAVE_GUARDADA, idioma);
  }

  // ---- galería con lupa ------------------------------------------------
  function montarGaleria() {
    const lupa = document.getElementById("lupa");
    if (!lupa) return;
    const imagen = lupa.querySelector("img");

    document.querySelectorAll(".shot").forEach(function (tarjeta) {
      tarjeta.addEventListener("click", function () {
        const img = tarjeta.querySelector("img");
        imagen.src = img.src;
        imagen.alt = img.alt;
        lupa.classList.add("abierta");
      });
    });
    function cerrar() { lupa.classList.remove("abierta"); }
    lupa.addEventListener("click", cerrar);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") cerrar();
    });
  }

  // ---- checkout MercadoPago -------------------------------------------
  // POST + fetch y recién después navegamos: así el endpoint puede aplicar
  // su freno por IP y devolver un error legible, en vez de perderse en una
  // navegación de página completa.
  function montarCheckout() {
    document.querySelectorAll("[data-plan]").forEach(function (boton) {
      boton.addEventListener("click", async function () {
        const plan = boton.getAttribute("data-plan");
        const original = boton.textContent;
        boton.disabled = true;
        boton.textContent = "…";
        try {
          const r = await fetch("/api/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plan: plan }),
          });
          const datos = await r.json();
          if (datos.url) {
            location.href = datos.url;
            return;
          }
          alert(mensajeError(datos.error));
        } catch (e) {
          alert(mensajeError("red"));
        } finally {
          boton.disabled = false;
          boton.textContent = original;
        }
      });
    });
  }

  function mensajeError(codigo) {
    const idioma = document.documentElement.lang || "es";
    const M = {
      es: {
        medio_pago_no_configurado: "El medio de pago todavía no está " +
          "configurado. Escribinos y te pasamos el enlace.",
        demasiadas_peticiones: "Demasiados intentos seguidos. Probá en un minuto.",
        red: "No se pudo contactar al servidor de pagos. Revisá tu conexión.",
        otro: "No se pudo iniciar el pago. Probá de nuevo en un momento.",
      },
      en: {
        medio_pago_no_configurado: "Payments are not configured yet. " +
          "Write to us and we will send you the link.",
        demasiadas_peticiones: "Too many attempts in a row. Try again in a minute.",
        red: "Could not reach the payment server. Check your connection.",
        otro: "Could not start the payment. Please try again shortly.",
      },
      pt: {
        medio_pago_no_configurado: "O meio de pagamento ainda não está " +
          "configurado. Escreva para nós e enviamos o link.",
        demasiadas_peticiones: "Tentativas demais seguidas. Tente em um minuto.",
        red: "Não foi possível contatar o servidor de pagamentos. Verifique sua conexão.",
        otro: "Não foi possível iniciar o pagamento. Tente novamente em instantes.",
      },
    };
    const tabla = M[idioma] || M.es;
    return tabla[codigo] || tabla.otro;
  }

  // ---- arranque --------------------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    aplicarIdioma(idiomaInicial());
    document.querySelectorAll(".idiomas button").forEach(function (b) {
      b.addEventListener("click", function () { aplicarIdioma(b.dataset.lang); });
    });
    montarGaleria();
    montarCheckout();
  });
})();
