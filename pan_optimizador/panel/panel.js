"use strict";

const porId = (id) => document.getElementById(id);
const texto = (id, valor) => { porId(id).textContent = valor; };
const formatoNumero = new Intl.NumberFormat("es-MX");
const numero = (valor) => formatoNumero.format(valor).replaceAll(",", "\u202f");
const formatoDecimal = new Intl.NumberFormat("es-ES", { maximumSignificantDigits: 12 });
const formatoPorcentaje = new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});
const porcentaje = (valor) => valor === null ? "N/D" : `${formatoPorcentaje.format(valor)} %`;
const gramos = (valor) => `${numero(valor)} g`;

const formatosMetricas = {
    cobertura_minima_pct: porcentaje,
    piezas_totales: numero,
    masa_usada_g: gramos,
};
const titulosVeredicto = {
    gana: "Gana el genético",
    empata: "Empate entre los métodos",
    pierde: "Gana el reparto proporcional",
};
const ventajas = {
    cobertura_minima: "Decide la cobertura del producto menos atendido.",
    piezas_totales: "A igual cobertura mínima, decide el total de piezas.",
    masa_usada_g: "A igual cobertura y piezas, decide la masa utilizada.",
};
const formulario = porId("controles");
const selector = porId("escenario");
const campoMasa = porId("masa");
const campoSemilla = porId("semilla");
const productosEdicion = porId("productos-edicion");
const camposConfiguracion = {
    poblacion: porId("poblacion"),
    generaciones: porId("generaciones"),
    torneo: porId("torneo"),
    prob_cruce: porId("prob-cruce"),
    prob_mutacion: porId("prob-mutacion"),
};
const metricaGrafica = porId("metrica");
const generacion = porId("generacion");
const grafica = porId("grafica");
const escenarios = new Map();
let planActual = null;
let configuracionInicial;

function actualizarEstado(mensaje, { error = false, soloLectores = false } = {}) {
    const estado = porId("estado");
    estado.dataset.error = error;
    estado.classList.toggle("solo-lectores", soloLectores);
    estado.textContent = mensaje;
}

function ocuparControles(ocupado) {
    porId("entradas-plan").disabled = ocupado;
    porId("resultado").setAttribute("aria-busy", String(ocupado));
}

async function pedirDatos(url, opciones) {
    let respuesta;
    try {
        respuesta = await fetch(url, opciones);
    } catch {
        throw new Error("El servidor local dejó de responder. Abre «Abrir interfaz.cmd» y vuelve a pulsar Calcular plan.");
    }
    const datos = await respuesta.json();
    if (!respuesta.ok) {
        throw new Error(datos.error);
    }
    return datos;
}

function celda(fila, contenido, { encabezado = false, clase, detalle } = {}) {
    const nodo = document.createElement(encabezado ? "th" : "td");
    if (encabezado) nodo.scope = "row";
    if (clase) nodo.classList.add(clase);
    nodo.textContent = contenido;
    if (detalle) {
        const aclaracion = document.createElement("small");
        aclaracion.textContent = detalle;
        nodo.append(aclaracion);
    }
    fila.append(nodo);
}

function mostrarProductos(productos) {
    const cuerpo = porId("productos");
    const etiquetas = [...cuerpo.parentElement.tHead.rows[0].cells].slice(1)
        .map((encabezado) => encabezado.textContent);
    const filas = productos.map((producto) => {
        const fila = document.createElement("tr");
        celda(fila, producto.nombre, { encabezado: true, detalle: `${gramos(producto.gramos_por_pieza)} por pieza` });
        celda(fila, numero(producto.demanda));
        celda(fila, numero(producto.genetico), { clase: "col-genetico", detalle: `${numero(producto.pendientes)} pendientes` });
        celda(fila, numero(producto.proporcional));
        celda(fila, gramos(producto.masa_asignada_g));
        celda(fila, porcentaje(producto.cobertura_pct));
        etiquetas.forEach((nombre, indice) => {
            const etiqueta = document.createElement("span");
            etiqueta.className = "etiqueta-celda";
            etiqueta.setAttribute("aria-hidden", "true");
            etiqueta.textContent = nombre;
            fila.cells[indice + 1].prepend(etiqueta);
        });
        return fila;
    });
    cuerpo.replaceChildren(...filas);
}

function mostrarVeredicto({ resultado, criterio }) {
    const motivo = criterio ? ` ${ventajas[criterio]}` : "";
    texto("veredicto", `${titulosVeredicto[resultado]}.${motivo}`);
}

function mostrarPlan(datos) {
    const resultado = datos.genetico;
    const config = datos.configuracion;
    const rondas = resultado.generaciones_ejecutadas;
    if (planActual?.nombre !== datos.nombre || Number(generacion.max) !== rondas) {
        generacion.max = rondas;
        generacion.value = rondas;
    }
    planActual = datos;
    let titulo = datos.nombre;
    if (datos.productos_modificados) {
        titulo = "Simulación personalizada";
    } else if (datos.masa_modificada) {
        titulo = `Simulación con ${gramos(datos.masa_disponible_g)}`;
    }
    texto("escenario-titulo", titulo);
    texto("contexto", `Semilla ${numero(resultado.semilla)}`);
    texto("piezas-totales", `${numero(resultado.piezas_totales)} de ${numero(datos.demanda_total)}`);
    texto("cobertura-total", `${porcentaje(resultado.cobertura_total_pct)} de cobertura total`);
    texto("cobertura-minima", porcentaje(resultado.cobertura_minima_pct));
    texto("masa-usada", gramos(resultado.masa_usada_g));
    texto("masa-total", `De ${gramos(datos.masa_disponible_g)} disponibles`);
    texto("masa-sobrante", gramos(resultado.masa_sobrante_g));
    mostrarProductos(datos.productos);
    mostrarVeredicto(datos.comparacion);
    let modo = `${numero(rondas)} ${rondas === 1 ? "generación" : "generaciones"}`;
    if (resultado.trivial) modo = "Cálculo directo";
    else if (!rondas) modo = "Solo población inicial";
    texto("modo-evolucion", modo);
    texto("configuracion", `Población ${numero(config.poblacion)} · Torneo ${numero(config.torneo)} · Cruce ${formatoDecimal.format(config.prob_cruce * 100)} % · Mutación ${formatoDecimal.format(config.prob_mutacion * 100)} % · Elitismo ${config.elitismo}`);
    if (resultado.trivial) {
        let motivo = "La masa alcanza para cubrir toda la demanda.";
        if (!datos.demanda_total) {
            motivo = "La demanda total es cero.";
        } else if (!resultado.piezas_totales) {
            motivo = "Con la masa disponible no cabe ninguna pieza solicitada.";
        }
        texto("solucion-directa", `${motivo} El programa registró el resultado en la generación 0.`);
    } else if (!rondas) {
        texto("solucion-directa", "El programa eligió el mejor plan de la población inicial. Configura una generación o más para ver la evolución.");
    }
    porId("solucion-directa").hidden = rondas > 0;
    porId("evolucion-grafica").hidden = !rondas;
    porId("configuracion").hidden = resultado.trivial;
    porId("resultado").hidden = false;
    actualizarGeneracion();
}

function actualizarGeneracion() {
    if (!planActual?.genetico.generaciones_ejecutadas) return;
    const indice = Number(generacion.value);
    const medidas = planActual.genetico.historial[indice];
    const lectura = `Generación ${indice} · ${porcentaje(medidas.cobertura_minima_pct)} · ${numero(medidas.piezas_totales)} piezas · ${gramos(medidas.masa_usada_g)}`;
    texto("lectura-generacion", lectura);
    generacion.setAttribute("aria-valuetext", lectura);
    dibujarGrafica();
}

function escalaGrafica(valores, referencia, porcentual) {
    let inferior = referencia;
    let superior = referencia;
    for (const valor of valores) {
        inferior = Math.min(inferior, valor);
        superior = Math.max(superior, valor);
    }
    const intervalo = (superior - inferior || Math.max(1, superior * .04)) / 4;
    const potencia = 10 ** Math.floor(Math.log10(intervalo));
    const multiplo = [1, 2, 5, 10].find((valor) => valor * potencia >= intervalo);
    const paso = Math.max(porcentual ? .01 : 1, multiplo * potencia);
    let inicio = Math.floor(inferior / paso);
    let fin = Math.ceil(superior / paso);
    if (inicio === fin) {
        inicio -= 1;
        fin += 1;
    }
    inicio = Math.max(0, inicio);
    if (porcentual) fin = Math.min(fin, Math.round(100 / paso));
    const marcas = [];
    for (let indice = inicio; indice <= fin; indice += 1) {
        marcas.push(indice * paso);
    }
    return marcas;
}

function dibujarGrafica() {
    if (!planActual?.genetico.generaciones_ejecutadas) return;
    const ancho = grafica.clientWidth;
    const alto = grafica.clientHeight;
    if (!ancho || !alto) return;
    const densidad = window.devicePixelRatio || 1;
    grafica.width = Math.round(ancho * densidad);
    grafica.height = Math.round(alto * densidad);
    const ctx = grafica.getContext("2d");
    if (!ctx) return;
    ctx.scale(densidad, densidad);
    const estilos = getComputedStyle(grafica);
    ctx.font = `13px ${estilos.getPropertyValue("--cuerpo")}`;
    const tinta = estilos.getPropertyValue("--secundario");
    const acento = estilos.getPropertyValue("--acento");
    const rejilla = estilos.getPropertyValue("--rejilla");

    const { value: clave, label: nombre } = metricaGrafica.selectedOptions[0];
    const formato = formatosMetricas[clave];
    const referencia = planActual.proporcional[clave];
    const valores = planActual.genetico.historial.map((medidas) => medidas[clave]);
    const marcas = escalaGrafica(valores, referencia, clave === "cobertura_minima_pct");
    const minimo = marcas[0];
    const maximo = marcas.at(-1);
    const etiquetas = marcas.map(formato);
    const margenIzq = Math.ceil(Math.max(...etiquetas.map((etiqueta) => ctx.measureText(etiqueta).width))) + 12;
    const margenDer = 13;
    const base = alto - 25;
    const ultimo = valores.length - 1;
    const x = (indice) => margenIzq + indice / ultimo * (ancho - margenIzq - margenDer);
    const y = (valor) => base - (valor - minimo) / (maximo - minimo) * (base - 14);

    ctx.fillStyle = tinta;
    ctx.textBaseline = "middle";
    ctx.textAlign = "right";
    ctx.strokeStyle = rejilla;
    ctx.lineWidth = 1;
    for (const [indice, valor] of marcas.entries()) {
        ctx.fillText(etiquetas[indice], margenIzq - 8, y(valor));
        ctx.beginPath();
        ctx.moveTo(margenIzq, y(valor));
        ctx.lineTo(ancho - margenDer, y(valor));
        ctx.stroke();
    }

    ctx.textAlign = "center";
    const marcasGeneracion = Math.min(4, ultimo);
    for (let i = 0; i <= marcasGeneracion; i += 1) {
        const indice = Math.round(i * ultimo / marcasGeneracion);
        ctx.fillText(indice, x(indice), alto - 9);
    }

    ctx.strokeStyle = acento;
    ctx.lineWidth = 3;
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(x(0), y(valores[0]));
    for (let i = 1; i <= ultimo; i += 1) {
        ctx.lineTo(x(i), y(valores[i - 1]));
        ctx.lineTo(x(i), y(valores[i]));
    }
    ctx.stroke();

    ctx.strokeStyle = tinta;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 5]);
    ctx.beginPath();
    ctx.moveTo(x(0), y(referencia));
    ctx.lineTo(x(ultimo), y(referencia));
    ctx.stroke();
    ctx.setLineDash([]);

    const seleccionado = Number(generacion.value);
    ctx.strokeStyle = tinta;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x(seleccionado), 14);
    ctx.lineTo(x(seleccionado), base);
    ctx.stroke();
    ctx.fillStyle = acento;
    ctx.beginPath();
    ctx.arc(x(seleccionado), y(valores[seleccionado]), 4, 0, Math.PI * 2);
    ctx.fill();
    const referenciaFormateada = formato(referencia);
    texto("referencia-grafica", `Reparto proporcional · ${referenciaFormateada}`);
    grafica.setAttribute("aria-label", `${nombre} por generación. Inicio ${formato(valores[0])}, final ${formato(valores.at(-1))}, referencia ${referenciaFormateada}.`);
}

function leerSolicitud() {
    const { poblacion, torneo } = camposConfiguracion;
    torneo.setCustomValidity(torneo.valueAsNumber > poblacion.valueAsNumber
        ? "El torneo debe tener como máximo tantos candidatos como la población." : "");
    const invalido = [...formulario.elements].find((control) =>
        control.willValidate && (!control.validity.valid
            || (control.type === "number" && control.step === "1" && !Number.isSafeInteger(control.valueAsNumber)))
    );
    if (invalido) {
        const editor = invalido.closest("details");
        if (editor) editor.open = true;
        actualizarEstado(invalido.validationMessage || "Escribe un número entero dentro del rango admitido.", { error: true });
        invalido.focus();
        invalido.reportValidity();
        return null;
    }
    return {
        escenario: selector.value,
        masa_disponible_g: campoMasa.valueAsNumber,
        semilla: campoSemilla.valueAsNumber,
        productos: [...productosEdicion.children].map((fila) => ({
            nombre: fila.querySelector('[name="nombre"]').value.trim(),
            gramos_por_pieza: fila.querySelector('[name="gramos_por_pieza"]').valueAsNumber,
            demanda: fila.querySelector('[name="demanda"]').valueAsNumber,
        })),
        configuracion: Object.fromEntries(Object.entries(camposConfiguracion).map(([clave, campo]) =>
            [clave, clave.startsWith("prob_") ? campo.valueAsNumber / 100 : campo.valueAsNumber]
        )),
    };
}

async function calcular() {
    const solicitud = leerSolicitud();
    if (!solicitud) return;

    ocuparControles(true);
    actualizarEstado("Calculando el plan de producción…");
    try {
        const datos = await pedirDatos("/api/plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(solicitud),
        });
        actualizarEstado("Plan actualizado.", { soloLectores: true });
        mostrarPlan(datos);
        return true;
    } catch (error) {
        planActual = null;
        porId("resultado").hidden = true;
        actualizarEstado(error.message, { error: true });
    } finally {
        ocuparControles(false);
    }
}

function crearFilaProducto(producto = {}) {
    const fila = porId("plantilla-producto").content.firstElementChild.cloneNode(true);
    for (const campo of fila.querySelectorAll("input")) {
        campo.value = producto[campo.name] ?? "";
    }
    return fila;
}

function actualizarEditorProductos() {
    const filas = [...productosEdicion.children];
    texto("cantidad-productos", `${filas.length} ${filas.length === 1 ? "producto" : "productos"}`);
    filas.forEach((fila, indice) => {
        for (const campo of fila.querySelectorAll("input")) {
            campo.setAttribute("aria-label", `${campo.previousElementSibling.textContent} del producto ${indice + 1}`);
        }
        const quitar = fila.querySelector(".quitar-producto");
        quitar.setAttribute("aria-label", `Quitar producto ${indice + 1}`);
        quitar.disabled = filas.length === 1;
    });
}

function cargarEscenario() {
    const escenario = escenarios.get(selector.value);
    campoMasa.value = escenario?.masa_disponible_g ?? "";
    const productos = escenario?.productos ?? [{}];
    productosEdicion.replaceChildren(...productos.map(crearFilaProducto));
    actualizarEditorProductos();
    porId("restaurar-escenario").hidden = !escenario;
    if (!escenario) {
        planActual = null;
        porId("resultado").hidden = true;
        porId("editar-productos").open = true;
        actualizarEstado("Ingresa la masa y los datos de tu primer pan.");
    }
    return Boolean(escenario);
}

function cargarParametros() {
    for (const [clave, campo] of Object.entries(camposConfiguracion)) {
        const valor = configuracionInicial[clave];
        campo.value = clave.startsWith("prob_") ? valor * 100 : valor;
    }
    texto("valor-elitismo", configuracionInicial.elitismo);
}

function indicarCambios() {
    actualizarEstado("Pulsa Calcular plan para aplicar los cambios.");
}

async function iniciar() {
    try {
        const [datos, { configuracion }] = await Promise.all([
            pedirDatos("/api/escenarios"),
            pedirDatos("/api/configuracion"),
        ]);
        configuracionInicial = configuracion;
        const principales = document.createElement("optgroup");
        principales.label = "Escenarios de demostración";
        const limites = document.createElement("optgroup");
        limites.label = "Casos límite";
        for (const escenario of datos) {
            escenarios.set(escenario.id, escenario);
            const grupo = escenario.id.startsWith("casos_limite/") ? limites : principales;
            grupo.append(new Option(escenario.nombre, escenario.id));
        }
        const personalizado = new Option("Personalizado", "personalizado");
        selector.replaceChildren(principales, personalizado);
        const preferido = "escasez_moderada.json";
        selector.value = escenarios.has(preferido) ? preferido : principales.firstElementChild?.value ?? personalizado.value;
        if (limites.childElementCount) {
            const mostrarLimites = porId("mostrar-casos-limite");
            mostrarLimites.hidden = false;
            mostrarLimites.addEventListener("click", () => {
                selector.insertBefore(limites, personalizado);
                mostrarLimites.hidden = true;
                selector.focus();
            }, { once: true });
        }
        cargarParametros();
        const precargado = cargarEscenario();
        ocuparControles(false);
        if (precargado) await calcular();
    } catch (error) {
        actualizarEstado(error.message, { error: true });
    }
}

formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const aplicado = await calcular();
    if (aplicado && evento.submitter?.id === "aplicar-cambios") {
        porId("escenario-titulo").focus();
    }
});
selector.addEventListener("change", () => {
    if (cargarEscenario()) calcular();
});
formulario.addEventListener("input", indicarCambios);
porId("agregar-producto").addEventListener("click", () => {
    const fila = crearFilaProducto();
    productosEdicion.append(fila);
    actualizarEditorProductos();
    fila.querySelector("input").focus();
    indicarCambios();
});
productosEdicion.addEventListener("click", (evento) => {
    const boton = evento.target.closest(".quitar-producto");
    if (!boton || boton.disabled) return;
    const fila = boton.closest(".producto-edicion");
    const siguiente = fila.nextElementSibling || fila.previousElementSibling;
    fila.remove();
    actualizarEditorProductos();
    siguiente.querySelector("input").focus();
    indicarCambios();
});
porId("restaurar-escenario").addEventListener("click", () => {
    if (cargarEscenario()) calcular();
});
porId("restaurar-parametros").addEventListener("click", () => {
    cargarParametros();
    indicarCambios();
});
generacion.addEventListener("input", actualizarGeneracion);
metricaGrafica.addEventListener("change", dibujarGrafica);
new ResizeObserver(dibujarGrafica).observe(grafica);

if (document.fullscreenEnabled) {
    const pantalla = porId("pantalla");
    pantalla.hidden = false;
    pantalla.addEventListener("click", async () => {
        try {
            if (document.fullscreenElement) {
                await document.exitFullscreen();
            } else {
                await document.documentElement.requestFullscreen();
            }
        } catch {
            actualizarEstado("Pulsa F11 para activar la pantalla completa del navegador.", { error: true });
        }
    });
    document.addEventListener("fullscreenchange", () => {
        texto("pantalla", document.fullscreenElement ? "Salir de pantalla completa" : "Pantalla completa");
    });
}

iniciar();
