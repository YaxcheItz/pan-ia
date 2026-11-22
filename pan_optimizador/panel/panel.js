"use strict";

const porId = (id) => document.getElementById(id);
const texto = (id, valor) => { porId(id).textContent = valor; };
const formatoNumero = new Intl.NumberFormat("es-MX");
const numero = (valor) => formatoNumero.format(valor).replaceAll(",", "\u202f");
const formatoPorcentaje = new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});
const porcentaje = (valor) => valor === null ? "N/D" : `${formatoPorcentaje.format(valor)} %`;
const gramos = (valor) => `${numero(valor)} g`;

const metricas = [
    { clave: "cobertura_minima_pct", criterio: "cobertura_minima", nombre: "Cobertura mínima", formato: porcentaje },
    { clave: "piezas_totales", criterio: "piezas_totales", nombre: "Piezas totales", formato: numero },
    { clave: "masa_usada_g", criterio: "masa_usada_g", nombre: "Masa usada", formato: gramos },
];
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
const resultadosSemilla = { gana: "Gana", empata: "Empata", pierde: "Pierde" };

const formulario = porId("controles");
const selector = porId("escenario");
const campoMasa = porId("masa");
const campoSemilla = porId("semilla");
const comparar = porId("comparar-semillas");
const metricaGrafica = porId("metrica");
const generacion = porId("generacion");
const grafica = porId("grafica");
const escenarios = new Map();
let planActual = null;

function actualizarEstado(mensaje, { error = false, soloLectores = false } = {}) {
    const estado = porId("estado");
    estado.dataset.error = error;
    estado.classList.toggle("solo-lectores", soloLectores);
    estado.textContent = mensaje;
}

function ocuparControles(ocupado) {
    for (const control of [...formulario.elements, comparar]) {
        control.disabled = ocupado;
    }
    porId("resultado").setAttribute("aria-busy", String(ocupado));
}

async function pedirDatos(url) {
    let respuesta;
    try {
        respuesta = await fetch(url);
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

function mostrarFilasAdaptables(id, filas) {
    const cuerpo = porId(id);
    const encabezados = [...cuerpo.parentElement.tHead.rows[0].cells];
    for (const fila of filas) {
        [...fila.cells].slice(1).forEach((columna, indice) => {
            const etiqueta = document.createElement("span");
            etiqueta.className = "etiqueta-celda";
            etiqueta.setAttribute("aria-hidden", "true");
            etiqueta.textContent = encabezados[indice + 1].textContent;
            columna.prepend(etiqueta);
        });
    }
    cuerpo.replaceChildren(...filas);
}

function mostrarProductos(productos) {
    const filas = productos.map((producto) => {
        const fila = document.createElement("tr");
        celda(fila, producto.nombre, { encabezado: true, detalle: `${gramos(producto.gramos_por_pieza)} por pieza` });
        celda(fila, numero(producto.demanda));
        celda(fila, numero(producto.genetico), { clase: "col-genetico", detalle: `${numero(producto.pendientes)} pendientes` });
        celda(fila, numero(producto.proporcional));
        celda(fila, gramos(producto.masa_asignada_g));
        celda(fila, porcentaje(producto.cobertura_pct));
        return fila;
    });
    mostrarFilasAdaptables("productos", filas);
}

function mostrarComparacion(datos) {
    const { resultado, criterio } = datos.comparacion;
    porId("veredicto").dataset.resultado = resultado;
    texto("ganador", titulosVeredicto[resultado]);
    texto("motivo", criterio ? ventajas[criterio] : "Los tres criterios tienen el mismo valor.");
    const filas = metricas.map(({ clave, nombre, formato }) => {
        const fila = document.createElement("tr");
        celda(fila, nombre, { encabezado: true });
        celda(fila, formato(datos.genetico[clave]), { clase: "col-genetico" });
        celda(fila, formato(datos.proporcional[clave]));
        return fila;
    });
    porId("criterios").replaceChildren(...filas);
}

function mostrarSemillas(semillas) {
    porId("resumen-semillas").hidden = !semillas.length;
    comparar.setAttribute("aria-expanded", String(semillas.length > 0));
    if (!semillas.length) return;
    const conteo = { gana: 0, empata: 0, pierde: 0 };
    const filas = semillas.map((corrida) => {
        conteo[corrida.resultado] += 1;
        const fila = document.createElement("tr");
        celda(fila, numero(corrida.semilla), { encabezado: true });
        for (const { clave, formato } of metricas) {
            celda(fila, formato(corrida[clave]));
        }
        celda(fila, resultadosSemilla[corrida.resultado]);
        const metrica = metricas.find(({ criterio }) => criterio === corrida.criterio);
        celda(fila, metrica?.nombre ?? "Igual aptitud");
        return fila;
    });
    texto("conteo-semillas", `${conteo.gana} ganan · ${conteo.empata} empatan · ${conteo.pierde} quedan por debajo`);
    mostrarFilasAdaptables("semillas", filas);
}

function mostrarPlan(datos) {
    planActual = datos;
    const resultado = datos.genetico;
    const config = datos.configuracion;
    const titulo = datos.masa_modificada ? `Simulación con ${gramos(datos.masa_disponible_g)}` : datos.nombre;
    texto("escenario-titulo", titulo);
    texto("contexto", `Semilla ${numero(resultado.semilla)}`);
    texto("piezas-totales", `${numero(resultado.piezas_totales)} de ${numero(datos.demanda_total)}`);
    texto("cobertura-total", `${porcentaje(resultado.cobertura_total_pct)} de cobertura total`);
    texto("cobertura-minima", porcentaje(resultado.cobertura_minima_pct));
    texto("masa-usada", gramos(resultado.masa_usada_g));
    texto("masa-total", `De ${gramos(datos.masa_disponible_g)} disponibles`);
    texto("masa-sobrante", gramos(resultado.masa_sobrante_g));
    mostrarProductos(datos.productos);
    mostrarComparacion(datos);
    mostrarSemillas(datos.semillas);
    texto("modo-evolucion", resultado.trivial ? "Cálculo directo" : `${resultado.generaciones_ejecutadas} generaciones`);
    texto("configuracion", `${resultado.generaciones_ejecutadas} generaciones ejecutadas · Población ${config.poblacion} · Torneo ${config.torneo} · Cruce ${Math.round(config.prob_cruce * 100)} % · Mutación ${Math.round(config.prob_mutacion * 100)} % · Elitismo ${config.elitismo}`);
    if (resultado.trivial) {
        let motivo = "La masa alcanza para cubrir toda la demanda.";
        if (!datos.demanda_total) {
            motivo = "La demanda total es cero.";
        } else if (!resultado.piezas_totales) {
            motivo = "Con la masa disponible no cabe ninguna pieza solicitada.";
        }
        texto("solucion-directa", `${motivo} El programa registró el resultado en la generación 0.`);
    }
    porId("solucion-directa").hidden = !resultado.trivial;
    porId("opciones-evolucion").hidden = resultado.trivial;
    porId("evolucion-grafica").hidden = resultado.trivial;
    generacion.max = resultado.generaciones_ejecutadas;
    generacion.value = resultado.generaciones_ejecutadas;
    porId("resultado").hidden = false;
    actualizarGeneracion();
}

function actualizarGeneracion() {
    if (!planActual || planActual.genetico.trivial) return;
    const indice = Number(generacion.value);
    const medidas = planActual.genetico.historial[indice];
    const lectura = `Generación ${indice} · ${porcentaje(medidas.cobertura_minima_pct)} · ${numero(medidas.piezas_totales)} piezas · ${gramos(medidas.masa_usada_g)}`;
    texto("lectura-generacion", lectura);
    generacion.setAttribute("aria-valuetext", lectura);
    dibujarGrafica();
}

function escalaGrafica(valores, porcentual) {
    const inferior = Math.min(...valores);
    const superior = Math.max(...valores);
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
    if (!planActual || planActual.genetico.trivial) return;
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
    const borde = estilos.getPropertyValue("--borde");

    const { clave, nombre, formato } = metricas.find(({ clave }) => clave === metricaGrafica.value);
    const referencia = planActual.proporcional[clave];
    const valores = planActual.genetico.historial.map((medidas) => medidas[clave]);
    const marcas = escalaGrafica([...valores, referencia], clave === "cobertura_minima_pct");
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
    ctx.strokeStyle = borde;
    ctx.lineWidth = 1;
    for (const [indice, valor] of marcas.entries()) {
        ctx.textAlign = "right";
        ctx.fillText(etiquetas[indice], margenIzq - 8, y(valor));
        ctx.beginPath();
        ctx.moveTo(margenIzq, y(valor));
        ctx.lineTo(ancho - margenDer, y(valor));
        ctx.stroke();
    }

    ctx.textAlign = "center";
    for (let i = 0; i <= 4; i += 1) {
        const indice = Math.round(i * ultimo / 4);
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
    grafica.setAttribute("aria-label", `${nombre} por generación. Inicio ${formato(valores[0])}, final ${formato(valores.at(-1))}, referencia ${formato(referencia)}.`);
}

async function calcular(compararSemillas = false) {
    if (!formulario.reportValidity()) return;
    if (![campoMasa.valueAsNumber, campoSemilla.valueAsNumber].every(Number.isSafeInteger)) {
        actualizarEstado("Escribe números enteros en masa disponible y semilla.", { error: true });
        return;
    }
    const parametros = new URLSearchParams({
        escenario: selector.value,
        masa: campoMasa.valueAsNumber,
        semilla: campoSemilla.valueAsNumber,
        comparar: compararSemillas ? "1" : "0",
    });

    ocuparControles(true);
    actualizarEstado(compararSemillas ? "Calculando la comparación de cinco semillas…" : "Calculando el plan de producción…");
    try {
        const datos = await pedirDatos(`/api/plan?${parametros}`);
        actualizarEstado("Plan actualizado.", { soloLectores: true });
        mostrarPlan(datos);
        if (compararSemillas) porId("semillas-titulo").focus();
    } catch (error) {
        planActual = null;
        porId("resultado").hidden = true;
        actualizarEstado(error.message, { error: true });
    } finally {
        ocuparControles(false);
    }
}

function ponerMasaOriginal() {
    campoMasa.value = escenarios.get(selector.value).masa_disponible_g;
}

async function iniciar() {
    try {
        const datos = await pedirDatos("/api/escenarios");
        if (!datos.length) throw new Error("Agrega un escenario JSON a la carpeta datos.");
        const principales = document.createElement("optgroup");
        principales.label = "Escenarios de demostración";
        const limites = document.createElement("optgroup");
        limites.label = "Casos límite";
        for (const escenario of datos) {
            escenarios.set(escenario.id, escenario);
            const grupo = escenario.id.startsWith("casos_limite/") ? limites : principales;
            grupo.append(new Option(escenario.nombre, escenario.id));
        }
        selector.replaceChildren(...[principales, limites].filter((grupo) => grupo.childElementCount));
        if (escenarios.has("escasez_moderada.json")) selector.value = "escasez_moderada.json";
        ponerMasaOriginal();
        ocuparControles(false);
        await calcular();
    } catch (error) {
        actualizarEstado(error.message, { error: true });
    }
}

formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    calcular();
});
selector.addEventListener("change", () => {
    ponerMasaOriginal();
    calcular();
});
for (const campo of [campoMasa, campoSemilla]) {
    campo.addEventListener("input", () => actualizarEstado("Pulsa Calcular plan para aplicar el cambio."));
}
comparar.addEventListener("click", () => calcular(true));
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
