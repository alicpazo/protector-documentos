(function () {
  "use strict";

  const EXTENSIONES = {
    pdf: { extension: ".pdf", urlApi: "/api/proteger/pdf" },
    excel: { extension: ".xlsx", urlApi: "/api/proteger/excel" },
  };

  document.querySelectorAll(".formulario").forEach(inicializarFormulario);
  inicializarCarpeta();

  function inicializarFormulario(formulario) {
    const tipo = formulario.dataset.tipo;
    const config = EXTENSIONES[tipo];

    const zonaArrastre = formulario.querySelector(".zona-arrastre");
    const campoArchivo = formulario.querySelector(".campo-archivo");
    const nombreArchivoElegido = formulario.querySelector(".nombre-archivo-elegido");

    const campoPassword = formulario.querySelector('input[id^="password-"]:not([id*="repetir"])');
    const campoPasswordRepetir = formulario.querySelector('input[id*="repetir"]');
    const botonVer = formulario.querySelector(".boton-ver");
    const mensajeNoCoincide = formulario.querySelector(".mensaje-password-no-coincide");

    const botonProteger = formulario.querySelector(".boton-proteger");
    const zonaResultado = formulario.querySelector(".zona-resultado");

    let archivoElegido = null;
    let urlDescargaActual = null;
    let nombreDescargaActual = null;

    // --- Elegir archivo: clic o arrastrar ---

    zonaArrastre.addEventListener("click", () => campoArchivo.click());
    zonaArrastre.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        campoArchivo.click();
      }
    });

    ["dragenter", "dragover"].forEach((evento) => {
      zonaArrastre.addEventListener(evento, (ev) => {
        ev.preventDefault();
        zonaArrastre.classList.add("zona-arrastre-activa");
      });
    });

    ["dragleave", "dragend", "drop"].forEach((evento) => {
      zonaArrastre.addEventListener(evento, () => {
        zonaArrastre.classList.remove("zona-arrastre-activa");
      });
    });

    zonaArrastre.addEventListener("drop", (ev) => {
      ev.preventDefault();
      const archivos = ev.dataTransfer && ev.dataTransfer.files;
      if (archivos && archivos.length > 0) {
        manejarArchivoElegido(archivos[0]);
      }
    });

    campoArchivo.addEventListener("change", () => {
      if (campoArchivo.files && campoArchivo.files.length > 0) {
        manejarArchivoElegido(campoArchivo.files[0]);
      }
    });

    function manejarArchivoElegido(archivo) {
      const nombre = archivo.name || "";
      const valido = nombre.toLowerCase().endsWith(config.extension);

      if (!valido) {
        archivoElegido = null;
        nombreArchivoElegido.textContent = "";
        const etiqueta = tipo === "pdf" ? "un PDF" : "un Excel (.xlsx)";
        mostrarResultado(
          zonaResultado,
          "error",
          `Este archivo no es ${etiqueta}. Prueba con otro, por favor.`
        );
        return;
      }

      archivoElegido = archivo;
      nombreArchivoElegido.textContent = nombre;
      limpiarResultado(zonaResultado);
    }

    // --- Ver / ocultar contraseña ---

    botonVer.addEventListener("click", () => {
      const mostrando = campoPassword.type === "text";
      campoPassword.type = mostrando ? "password" : "text";
      campoPasswordRepetir.type = mostrando ? "password" : "text";
      botonVer.textContent = mostrando ? "Ver contraseña" : "Ocultar contraseña";
      botonVer.setAttribute("aria-pressed", String(!mostrando));
    });

    function comprobarCoincidencia() {
      if (!campoPasswordRepetir.value) {
        mensajeNoCoincide.hidden = true;
        return true;
      }
      const coincide = campoPassword.value === campoPasswordRepetir.value;
      mensajeNoCoincide.hidden = coincide;
      return coincide;
    }

    campoPassword.addEventListener("input", comprobarCoincidencia);
    campoPasswordRepetir.addEventListener("input", comprobarCoincidencia);

    // --- Enviar ---

    formulario.addEventListener("submit", (ev) => {
      ev.preventDefault();
      enviarFormulario();
    });

    async function enviarFormulario() {
      if (!archivoElegido) {
        const etiqueta = tipo === "pdf" ? "un documento PDF" : "un documento Excel";
        mostrarResultado(zonaResultado, "error", `Elige primero ${etiqueta}, por favor.`);
        return;
      }

      const password = campoPassword.value;
      const repetida = campoPasswordRepetir.value;

      if (password.length < 4) {
        mostrarResultado(
          zonaResultado,
          "error",
          "La contraseña debe tener al menos 4 caracteres."
        );
        return;
      }

      if (password !== repetida) {
        mensajeNoCoincide.hidden = false;
        mostrarResultado(
          zonaResultado,
          "error",
          "Las contraseñas no coinciden. Revísalas, por favor."
        );
        return;
      }

      const datosFormulario = new FormData();
      datosFormulario.append("documento", archivoElegido, archivoElegido.name);
      datosFormulario.append("password", password);

      botonProteger.disabled = true;
      mostrarResultado(
        zonaResultado,
        "espera",
        "Un momento, estamos protegiendo tu documento…",
        true
      );

      try {
        const respuesta = await fetch(config.urlApi, {
          method: "POST",
          body: datosFormulario,
        });

        if (!respuesta.ok) {
          let mensaje = "No hemos podido proteger este documento. Inténtalo de nuevo, por favor.";
          try {
            const datosError = await respuesta.json();
            if (datosError && datosError.error) mensaje = datosError.error;
          } catch (_err) {
            /* usamos el mensaje por defecto */
          }
          mostrarResultado(zonaResultado, "error", mensaje);
          return;
        }

        const blob = await respuesta.blob();
        const nombreDescarga = nombreDesdeCabecera(respuesta, archivoElegido.name, config.extension);

        if (urlDescargaActual) URL.revokeObjectURL(urlDescargaActual);
        urlDescargaActual = URL.createObjectURL(blob);
        nombreDescargaActual = nombreDescarga;

        descargarArchivo(urlDescargaActual, nombreDescargaActual);
        mostrarExito(zonaResultado, () => descargarArchivo(urlDescargaActual, nombreDescargaActual));
        actualizarListaDocumentos();

        // Limpiamos los campos de contraseña por seguridad.
        campoPassword.value = "";
        campoPasswordRepetir.value = "";
      } catch (_err) {
        mostrarResultado(
          zonaResultado,
          "error",
          "No hemos podido conectar con la aplicación. Cierra y vuelve a abrirla, por favor."
        );
      } finally {
        botonProteger.disabled = false;
      }
    }
  }

  function nombreDesdeCabecera(respuesta, nombreOriginal, extension) {
    const cabecera = respuesta.headers.get("Content-Disposition") || "";
    const coincidencia = /filename="?([^";]+)"?/i.exec(cabecera);
    if (coincidencia && coincidencia[1]) return coincidencia[1];

    const base = nombreOriginal.replace(/\.[^.]+$/, "");
    return `${base}-protegido${extension}`;
  }

  function descargarArchivo(url, nombre) {
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);
  }

  function limpiarResultado(zonaResultado) {
    zonaResultado.innerHTML = "";
  }

  function mostrarResultado(zonaResultado, tipo, mensaje, conSpinner) {
    zonaResultado.innerHTML = "";
    const div = document.createElement("div");
    div.className = `mensaje-estado ${tipo}`;
    if (conSpinner) {
      const spinner = document.createElement("span");
      spinner.className = "spinner";
      spinner.setAttribute("aria-hidden", "true");
      div.appendChild(spinner);
    }
    div.appendChild(document.createTextNode(mensaje));
    zonaResultado.appendChild(div);
  }

  function mostrarExito(zonaResultado, alDescargarDeNuevo) {
    zonaResultado.innerHTML = "";
    const div = document.createElement("div");
    div.className = "mensaje-estado exito";
    div.textContent = "¡Listo! Tu documento ya está protegido.";
    zonaResultado.appendChild(div);

    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "boton-descargar-de-nuevo";
    boton.textContent = "Descargar de nuevo";
    boton.addEventListener("click", alDescargarDeNuevo);
    zonaResultado.appendChild(boton);
  }

  // --- Carpeta de documentos protegidos ---

  function inicializarCarpeta() {
    const boton = document.querySelector(".boton-abrir-carpeta");
    const mensaje = document.querySelector(".mensaje-carpeta");
    if (!boton) return;

    boton.addEventListener("click", async () => {
      mensaje.hidden = true;
      try {
        const resp = await fetch("/api/abrir-carpeta", { method: "POST" });
        if (!resp.ok) {
          const datos = await resp.json().catch(() => ({}));
          mensaje.textContent =
            datos.error || "No hemos podido abrir la carpeta. Búscala en tu Escritorio.";
          mensaje.hidden = false;
        }
      } catch (_err) {
        mensaje.textContent = "No hemos podido abrir la carpeta. Búscala en tu Escritorio.";
        mensaje.hidden = false;
      }
    });

    actualizarListaDocumentos();
  }

  async function actualizarListaDocumentos() {
    const lista = document.querySelector(".lista-documentos");
    if (!lista) return;

    try {
      const resp = await fetch("/api/documentos");
      if (!resp.ok) return;
      const datos = await resp.json();
      renderizarListaDocumentos(lista, datos.documentos || []);
    } catch (_err) {
      // Si falla, dejamos la lista como estaba; no es un error crítico.
    }
  }

  function renderizarListaDocumentos(lista, documentos) {
    lista.innerHTML = "";

    if (documentos.length === 0) {
      const vacio = document.createElement("li");
      vacio.className = "lista-documentos-vacia";
      vacio.textContent = "Aquí irán apareciendo los documentos que protejas.";
      lista.appendChild(vacio);
      return;
    }

    documentos.forEach((doc) => {
      const item = document.createElement("li");
      item.className = "documento-item";

      const icono = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      icono.setAttribute("class", "documento-icono");
      icono.setAttribute("viewBox", "0 0 32 32");
      icono.setAttribute("aria-hidden", "true");
      const pagina =
        '<path d="M8 3 H20 L26 9 V28 H8 Z" fill="#ffffff" stroke="#c9ccd1" stroke-width="1.3" stroke-linejoin="round"/>' +
        '<path d="M20 3 L26 9 H20 Z" fill="#eef0f2" stroke="#c9ccd1" stroke-width="1" stroke-linejoin="round"/>';
      icono.innerHTML =
        doc.tipo === "excel"
          ? pagina +
            '<path d="M11 13v8M14.3 13v8M17.6 13v8M21 13v8M11 15.7h10M11 18.3h10" stroke="#cfd2d6" stroke-width="1" stroke-linecap="round"/>' +
            '<rect x="5" y="21" width="24" height="9" rx="1.6" fill="#1d6f42"/>' +
            '<text x="17" y="28.2" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="9.5" font-weight="700" fill="#ffffff">X</text>'
          : pagina +
            '<path d="M11 14h10M11 17h10M11 20h6" stroke="#cfd2d6" stroke-width="1.2" stroke-linecap="round"/>' +
            '<rect x="5" y="21" width="24" height="9" rx="1.6" fill="#e2231a"/>' +
            '<text x="17" y="27.8" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="7.5" font-weight="700" fill="#ffffff">PDF</text>';

      const info = document.createElement("div");
      info.className = "documento-info";

      const nombre = document.createElement("p");
      nombre.className = "documento-nombre";
      nombre.textContent = doc.nombre;

      const fecha = document.createElement("p");
      fecha.className = "documento-fecha";
      fecha.textContent = formatearFecha(doc.fecha);

      info.appendChild(nombre);
      info.appendChild(fecha);

      const enlace = document.createElement("a");
      enlace.className = "documento-descargar";
      enlace.href = `/api/documentos/${encodeURIComponent(doc.nombre)}`;
      enlace.textContent = "Descargar otra vez";

      item.appendChild(icono);
      item.appendChild(info);
      item.appendChild(enlace);
      lista.appendChild(item);
    });
  }

  function formatearFecha(fechaIso) {
    try {
      const fecha = new Date(fechaIso);
      return fecha.toLocaleString("es-ES", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_err) {
      return "";
    }
  }

  // --- La app se cierra sola si cierras la pestaña ---
  window.addEventListener("pagehide", () => {
    try {
      navigator.sendBeacon("/shutdown");
    } catch (_err) {
      /* si falla, el aviso de inactividad la cerrará igualmente */
    }
  });
})();
