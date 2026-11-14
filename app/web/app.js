/* Orduen Liturgia — Invitatorio, Laudes, Vísperas y Completas.
   Lee los días ya resueltos que genera cada noche el repositorio (indice.json y
   dias/AAAA-MM-DD.json), los guarda en el dispositivo y funciona sin conexión
   con lo último que bajó. Formato: Formato.md. */
"use strict";

// De dónde se leen los datos. `?base=` lo cambia (pruebas en local).
const BASE = new URLSearchParams(location.search).get("base") || "https://zeanuri.github.io/OrduenLiturgia/";
const SEMILLA = "datos/";            // copia incluida en la app: primer arranque sin conexión

// Rótulos. PROVISIONALES: pendientes de revisar por quien fije el bizkaiera.
const R = {
  app: "Orduen Liturgia", invitatorio: "Dei-salmoa", laudes: "Gorespenak", visperas: "Bezperak", completas: "Konpletak",
  primeras: "Lehenengo Bezperak", misa: "Mezako irakurgaiak", calendario: "Egutegia", hoy: "Gaur",
  prueba: "PROBAKO TESTUAK — ez dira liturgia-testuak", sinDatos: "Ezin izan da eguna kargatu.",
  sinConexion: "Konexino barik: gordetako azkena erakusten da.", falta: "Bizkaierazko bertsioaren zain", pendiente: "Oraindik osatu gabe", ant: "Ant.",
  salterio: "Salmutegiko astea", opcional: "aukerakoa", salmoa: "Salmoa", salmos: "95., 100., 67., 24.",
  // Días y meses en batua, como el resto de rótulos de lecturasdeldia.org/eu.
  dias: ["Astelehena", "Asteartea", "Asteazkena", "Osteguna", "Ostirala", "Larunbata", "Igandea"],
  diasCortos: ["al", "ar", "az", "og", "or", "lr", "ig"],
  meses: ["urtarrila", "otsaila", "martxoa", "apirila", "maiatza", "ekaina", "uztaila", "abuztua", "iraila", "urria", "azaroa", "abendua"],
};
const COLORES = { Verde: "#2e7d32", Morado: "#6a1b9a", Blanco: "#ffffff", Rojo: "#c62828", Rosa: "#f48fb1", Negro: "#222222" };
// Color del tiempo para las letras de la cabecera (el blanco litúrgico se escribe en oro oscuro).
const TINTA = { Verde: "#1b7d44", Morado: "#5b3a8e", Rojo: "#b3202a", Blanco: "#8c6e18", Rosa: "#a84e74" };
// Horas de la lista del día. El Dei-salmoa no es una entrada: va dentro de Gorespenak, plegado.
const HORAS = ["laudes", "visperas", "completas"];

// ── Almacén en el dispositivo (IndexedDB) ─────────────────────────────────
const almacen = (() => {
  let bd;
  const abrir = () => bd || (bd = new Promise((ok, mal) => {
    const p = indexedDB.open("orduenliturgia", 1);
    p.onupgradeneeded = () => p.result.createObjectStore("kv");
    p.onsuccess = () => ok(p.result);
    p.onerror = () => mal(p.error);
  }));
  const tx = (modo, f) => abrir().then(db => new Promise((ok, mal) => {
    const r = f(db.transaction("kv", modo).objectStore("kv"));
    r.onsuccess = () => ok(r.result);
    r.onerror = () => mal(r.error);
  })).catch(() => undefined);          // sin almacén (modo privado): se sigue sin caché
  return { leer: k => tx("readonly", s => s.get(k)), guardar: (k, v) => tx("readwrite", s => s.put(v, k)) };
})();

const pedir = async (url) => {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(r.status + " " + url);
  return r.json();
};

let indice = null, enLinea = true, indiceT = 0;       // indiceT: cuándo llegó el último índice de la red

async function cargarIndice() {
  try {
    indice = await pedir(BASE + "indice.json");
    enLinea = true; indiceT = Date.now();
    almacen.guardar("indice", indice);
  } catch (e) {
    enLinea = false;
    indice = indice || await almacen.leer("indice") || await pedir(SEMILLA + "indice.json").catch(() => null);   // el que ya había manda
  }
  return indice;
}

async function cargarDia(fecha) {
  const huella = indice && indice.dias[fecha] && indice.dias[fecha].huella;
  const guardado = await almacen.leer("dia:" + fecha);
  if (guardado && guardado.huella === huella) return guardado.dia;
  try {
    const dia = await pedir(BASE + "dias/" + fecha + ".json");
    enLinea = true;
    almacen.guardar("dia:" + fecha, { huella, dia });
    return dia;
  } catch (e) {
    if (e instanceof TypeError) enLinea = false;             // fallo de red (no un 404 de un día sin publicar)
    if (guardado) return guardado.dia;                       // lo último que se bajó
    return pedir(SEMILLA + "dias/" + fecha + ".json").catch(() => null);
  }
}

// ── Fechas ────────────────────────────────────────────────────────────────
const iso = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
const deIso = s => { const [a, m, d] = s.split("-").map(Number); return new Date(a, m - 1, d); };
const mas = (s, n) => { const d = deIso(s); d.setDate(d.getDate() + n); return iso(d); };
const hoyIso = () => iso(new Date());
const lunes0 = d => (d.getDay() + 6) % 7;                    // lunes = 0
const fechaLarga = s => { const d = deIso(s); return `${R.dias[lunes0(d)]} \u00b7 ${s.slice(8)}/${s.slice(5, 7)}/${s.slice(0, 4)}`; };

// ── Pintar ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const punto = color => `<span class="punto" style="background:${COLORES[color] || "#999"}"></span>`;

function cabecera(titulo, subtitulo, atras) {
  $("titulo").textContent = titulo;
  $("subtitulo").textContent = subtitulo || "";
  $("atras").hidden = !atras;
  $("atras").onclick = () => { location.hash = atras; };
  document.title = titulo + " · " + R.app;
}

function avisos(extra) {
  return (enLinea ? "" : `<p class="aviso">${R.sinConexion}</p>`) + (extra || "");
}

// Identificador de navegación: una vista asíncrona solo pinta si sigue siendo la vigente.
let navId = 0;

async function vistaDia(fecha, c, id) {
  const dia = await cargarDia(fecha);
  if (id !== navId) return;
  if (!dia) { cabecera(fechaLarga(fecha), "", null); $("vista").innerHTML = avisos(`<p class="aviso">${R.sinDatos}</p>`); return; }
  const cel = dia.celebraciones[c] || dia.celebraciones[0];
  c = dia.celebraciones.indexOf(cel);
  cabecera(R.app, "", null);
  const cab = dia.cabecera;
  // Memoria obligatoria: lo que se reza es la memoria, así que el santo va de título y la feria debajo, en pequeño.
  // Una fiesta cuyo nombre ya es el del día no se repite debajo.
  const c0 = dia.celebraciones[0], conMem = cab.memoria && cab.memoria !== cab.nombre;
  const oblig = conMem && !c0.opcional && c0.nombre_eu === cab.memoria;
  const rangoCab = oblig ? cab.memoria_rango : cab.rango;
  const tarde = new Date().getHours() >= 13;
  const ahora = fecha === hoyIso() ? (tarde ? "visperas" : "laudes") : null;
  const fichas = dia.celebraciones.length < 2 ? "" : `<div class="fichas">` + dia.celebraciones.map((x, i) =>
    `<button class="ficha" aria-pressed="${i === c}" data-ir="#/dia/${fecha}/${i}">${esc(x.nombre_eu)}${x.opcional ? ` (${R.opcional})` : ""}</button>`).join("") + `</div>`;
  const fila = h => {
    const pv = h === "visperas" && cel.visperas_de.cuales === "primeras";
    const pc = h === "completas" && cel.completas_de && cel.completas_de.cuales === "primeras";   // primeras Completas: el nombre de mañana
    return `<li><a class="${h === ahora ? "ahora" : ""}" href="#/dia/${fecha}/${c}/${h}"><span>${pv ? R.primeras : R[h]}` +
      (pv ? `<small>${esc(cel.visperas_de.de_eu)}</small>` : pc ? `<small>${esc(cel.completas_de.de_eu)}</small>` : "") + `</span></a></li>`;
  };
  const orden = HORAS.filter(h => cel.horas[h]);       // orden fijo: Gorespenak, Bezperak, Konpletak
  $("vista").innerHTML = avisos() +
    `<div class="cab" style="--c:${TINTA[dia.color] || TINTA.Verde}">
       ${enVentana(mas(fecha, -1)) ? `<a class="flecha ant" href="#/dia/${mas(fecha, -1)}" aria-label="Aurreko eguna">&larr;</a>` : ""}
       ${enVentana(mas(fecha, 1)) ? `<a class="flecha sig" href="#/dia/${mas(fecha, 1)}" aria-label="Hurrengo eguna">&rarr;</a>` : ""}
       <div class="fecha">${fechaLarga(fecha)}</div>
       <h1>${esc(oblig ? cab.memoria : cab.nombre)}</h1>
       ${oblig ? `<div class="memoria">${esc(cab.nombre)}</div>`
         : conMem ? `<div class="memoria"><span class="estrella">&#9733;</span>${esc(cab.memoria)} <em>${esc(cab.memoria_rango)}</em></div>` : ""}
       <div class="info">${esc(cab.tiempo)} &middot; ${esc(rangoCab.charAt(0).toUpperCase() + rangoCab.slice(1))} &middot; ${R.salterio}: ${["", "I", "II", "III", "IV"][dia.semana_salterio]}</div>
     </div>${fichas}
     <ul class="horas">${orden.map(fila).join("")}
       ${fecha >= mas(hoyIso(), -30) ? `<li><a href="${esc(dia.misa)}" target="_blank" rel="noopener"><span>${R.misa}<small>lecturasdeldia.org</small></span></a></li>` : ""}</ul>
     ${fecha !== hoyIso() ? `<nav class="pasos"><a href="#/">${R.hoy}</a></nav>` : ""}`;
}

const enVentana = f => !indice || (f >= indice.desde && f <= indice.hasta);

function lineas(ls) {
  // Una marca (V., R., Ant.) se pinta en el mismo renglón que el texto que la sigue. Versículo y
  // respuesta salen siempre «V/.» y «R/.»: en batua la marca viene sola («V.») y el texto en la
  // línea siguiente; en bizkaiera, marca y texto en la misma («V/. Zure zintzoek…»).
  let html = "", marca = "";
  for (const l of ls || []) {
    const vr = (l.t === "v" || l.t === "r") && /^([VR])\/?\.\s*([\s\S]*)$/.exec(l.x);
    if (vr && vr[2]) { html += `<p class="l-texto">${marca}<span class="marca">${vr[1]}/.</span>${esc(vr[2])}</p>`; marca = ""; continue; }
    if (vr) { marca += `<span class="marca">${vr[1]}/.</span>`; continue; }
    if (l.t === "v" || l.t === "r" || l.t === "ant") { marca += `<span class="marca">${esc(l.x)}</span>`; continue; }
    html += `<p class="l-${l.t}">${l.t === "texto" || l.t === "estrofa" ? marca : ""}${esc(l.x)}</p>`;
    if (l.t === "texto" || l.t === "estrofa") marca = "";
  }
  return html + (marca ? `<p>${marca}</p>` : "");
}

// `repetida`: la antífona que vuelve detrás de su salmo; no repite la cabecera de la parte.
function parteHtml(p, marca, repetida) {
  // Cabecera de la parte («Irakurgai laburra», «Eskariak»…), con las palabras de «Liturgia euskaraz».
  const cab = p.cabecera && !repetida ? `<p class="l-titulo">${esc(p.cabecera)}</p>` : "";
  if (p.falta) return `<section>${cab}<p class="falta" title="${esc(p.falta[0])}">${R.pendiente}</p></section>`;
  const ls = marca ? [{ t: "ant", x: marca }, ...(p.lineas || [])] : p.lineas;
  // Texto en batua de «Liturgia euskaraz» donde aún no hay bizkaiera: se dice encima.
  const batua = p.batua ? `<p class="batua" title="${esc(p.fuente || "")}">${R.falta}</p>` : "";
  return `<section data-parte="${p.parte}">${cab}${batua}${p.titulo ? `<p class="l-titulo">${esc(p.titulo)}</p>` : ""}${lineas(ls)}</section>`;
}

// Marca de la antífona, como en «Liturgia euskaraz»: «1. Ant.» antes del salmo y «Ant.»
// al repetirla detrás; la del Benedictus o el Magníficat y la del invitatorio, «Ant.». Una hora de
// una sola antífona (Completas de un salmo, o de dos con una sola antífona en Pascua) también «Ant.».
function marcaAnt(p, repetida, varias) {
  const n = /^ant(\d)$/.exec(p.parte);
  return n && !repetida && varias ? `${n[1]}. ${R.ant}` : R.ant;
}

// Salmo invitatorio elegido (95, 100, 67 o 24); el 95 por defecto. Se guarda en el dispositivo.
const salmoInv = () => localStorage.getItem("salmoInv") || "95";
let invActual = null;                 // {p, ant}: la parte `salmo` con sus opciones y la antífona del invitatorio
// Dentro de Gorespenak el Dei-salmoa va plegado: solo los botones; al pulsar uno se abre su salmo, y se
// pliega pulsándolo otra vez.
let invPlegable = false;

// El salmo elegido: encabezado, y la antífona antes de la primera estrofa y detrás de cada una (Gloria
// incluido), como «Liturgia euskaraz». Sin antífona (falta), el aviso una vez arriba y el salmo solo.
function salmoInvHtml(n) {
  const { p, ant } = invActual;
  const o = p.opciones.find(x => x.n === (n || salmoInv())) || p.opciones[0];
  const cab = o.lineas.filter(l => l.t !== "estrofa"), estrofas = o.lineas.filter(l => l.t === "estrofa");
  const conAnt = ant && !ant.falta;
  const nota = (!conAnt ? `<p class="falta" title="${esc(ant && ant.falta ? ant.falta[0] : "")}">${R.pendiente}</p>` : "") +
    (o.batua || (conAnt && ant.batua) ? `<p class="batua" title="${esc(o.fuente || "")}">${R.falta}</p>` : "");
  const a = conAnt ? `<section>${lineas([{ t: "ant", x: R.ant }, ...ant.lineas])}</section>` : "";
  return nota + `<section>${lineas(cab)}</section>` + a + estrofas.map(e => `<section>${lineas([e])}</section>` + a).join("");
}

// Fila de botones 95 · 100 · 67 · 24 y, debajo, el salmo elegido (se repinta al pulsar, sin navegar).
function selectorSalmoInv() {
  const n = invPlegable ? null : (invActual.p.opciones.find(x => x.n === salmoInv()) || invActual.p.opciones[0]).n;
  return `<section id="dei-salmoa"><p class="l-titulo">${invPlegable ? R.invitatorio : R.salmoa}</p><div class="fichas" role="group" aria-label="${R.salmos}">` +
    invActual.p.opciones.map(o => `<button class="ficha" data-salmo="${o.n}" aria-pressed="${o.n === n}">${o.n}</button>`).join("") +
    `</div></section><div id="salmo-inv">${n ? salmoInvHtml(n) : ""}</div>`;
}

// Con el Dei-salmoa abierto, la apertura del Invitatorio sustituye a la de Laudes. Devuelve si hubo cambio.
function aperturaInv(abierto) {
  const l = document.querySelector('[data-apertura="laudes"]'), i = document.querySelector('[data-apertura="inv"]');
  if (!l || !i) return false;
  l.hidden = abierto; i.hidden = !abierto;
  return true;
}

function plegarSalmoInv() {
  document.querySelectorAll("[data-salmo]").forEach(x => x.setAttribute("aria-pressed", false));
  $("salmo-inv").innerHTML = "";
  $("dei-salmoa").scrollIntoView({ block: "center" });
}

async function vistaHora(fecha, c, hora, id) {
  const dia = await cargarDia(fecha);
  if (id !== navId) return;
  const cel = dia && dia.celebraciones[c];
  if (!cel || !cel.horas[hora]) { location.hash = "#/dia/" + fecha; return; }
  const partes = cel.horas[hora];
  const pv = hora === "visperas" && cel.visperas_de.cuales === "primeras";
  const pc = hora === "completas" && cel.completas_de && cel.completas_de.cuales === "primeras";
  cabecera(fechaLarga(fecha), pv ? R.primeras : R[hora], `#/dia/${fecha}/${c}`);
  // La antífona se dice antes y después de su salmo o cántico: se repite detrás.
  const varias = partes.some(p => p.parte === "ant2");    // «1. Ant.» solo si hay una segunda
  let cuerpo = "", ant = null;
  invPlegable = hora === "laudes";
  // Dei-salmoa dentro de Gorespenak, tras la apertura: los salmos del Invitatorio del día, plegados.
  const inv = invPlegable && cel.horas.invitatorio, invSalmo = inv && inv.find(p => p.opciones);
  partes.forEach(p => {
    if (hora === "invitatorio" && p.parte === "ant") { ant = p; return; }     // la antífona entra en el salmo
    if (p.opciones) { invActual = { p, ant }; ant = null; cuerpo += selectorSalmoInv(); return; }
    const esAnt = p.parte.startsWith("ant");
    // Con un salmo abierto, la apertura del Invitatorio ocupa el sitio de la de Laudes (data-apertura).
    const apInv = invSalmo && p.parte === "apertura" && inv.find(x => x.parte === "apertura");
    cuerpo += apInv && !apInv.falta ? `<div data-apertura="laudes">${parteHtml(p, "")}</div><div data-apertura="inv" hidden>${parteHtml(apInv, "")}</div>`
      : parteHtml(p, esAnt ? marcaAnt(p, false, varias) : "");
    if (invSalmo && p.parte === "apertura") { invActual = { p: invSalmo, ant: inv.find(x => x.parte === "ant") }; cuerpo += selectorSalmoInv(); }
    if (esAnt) ant = p;
    else if (ant) { if (!ant.falta) cuerpo += parteHtml(ant, marcaAnt(ant, true, varias), true); ant = null; }
  });
  if (ant && hora === "invitatorio") cuerpo += parteHtml(ant, R.ant);         // sin salmos que elegir: la antífona sola
  const prueba = partes.some(p => p.prueba);
  $("vista").innerHTML = avisos(prueba ? `<p class="aviso prueba">${R.prueba}</p>` : "") +
    `<div class="herramientas"><button data-letra="-1" aria-label="Letra txikiagoa">A&minus;</button>
       <button data-letra="1" aria-label="Letra handiagoa">A+</button><button data-tema aria-label="Gaua / eguna">&#9680;</button></div>
     <article class="lector"><h1>${esc(pv ? cel.visperas_de.de_eu : pc ? cel.completas_de.de_eu : cel.nombre_eu)}</h1><h2>${pv ? R.primeras : R[hora]}</h2>${cuerpo}</article>`;
}

function vistaCalendario(mes) {
  const [a, m] = mes.split("-").map(Number);
  cabecera(R.calendario, "", "#/");
  const primero = new Date(a, m - 1, 1), n = new Date(a, m, 0).getDate();
  const otro = k => { const d = new Date(a, m - 1 + k, 1); return iso(d).slice(0, 7); };
  let celdas = R.diasCortos.map(d => `<div class="cab">${d}</div>`).join("") + "<span></span>".repeat(lunes0(primero));
  for (let d = 1; d <= n; d++) {
    const f = `${mes}-${String(d).padStart(2, "0")}`, info = indice && indice.dias[f];
    celdas += info
      ? `<a href="#/dia/${f}" class="${f === hoyIso() ? "hoy " : ""}${/Solemnidad|Fiesta|Domingo/.test(info.rango) ? "fiesta" : ""}" title="${esc(info.nombre)}">${d}${punto(info.color)}</a>`
      : !indice ? `<a href="#/dia/${f}" class="${f === hoyIso() ? "hoy" : ""}">${d}</a>`      // sin índice: se prueba el día igualmente
      : `<span class="d">${d}</span>`;
  }
  $("vista").innerHTML = avisos() +
    `<div class="mes"><button data-ir="#/egutegia/${otro(-1)}" aria-label="Aurreko hilea">&larr;</button>
       <span>${R.meses[m - 1]} ${a}</span><button data-ir="#/egutegia/${otro(1)}" aria-label="Hurrengo hilea">&rarr;</button></div>
     <div class="rejilla">${celdas}</div>
     <nav class="pasos"><a href="#/">${R.hoy}</a></nav>`;
}

// ── Navegación ────────────────────────────────────────────────────────────
async function navegar(quieto) {
  const id = ++navId, hash = location.hash;
  const p = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (!indice) await cargarIndice();
  if (id !== navId) return;
  if (p[0] === "egutegia") vistaCalendario(p[1] || hoyIso().slice(0, 7));
  else if (p[0] === "dia" && p[3]) await vistaHora(p[1], Number(p[2]) || 0, p[3], id);
  else await vistaDia(p[0] === "dia" && p[1] ? p[1] : hoyIso(), Number(p[2]) || 0, id);
  if (id !== navId) return;                                // otra navegación se adelantó: no se toca la pantalla
  if (!quieto) window.scrollTo(0, 0);
  document.documentElement.dataset.lista = hash || "#/";      // señal para las pruebas
}

// El índice se renueva al volver a primer plano y con «Gaur» si tiene más de 30 minutos y hay red. Si
// cambia lo que se está viendo (huella del día, o el aviso de conexión) se repinta en el sitio; dentro
// de una hora no se repinta (se perdería la lectura): la próxima navegación ya usa lo nuevo.
let renovando = false;
async function renovarIndice() {
  if (renovando || !navigator.onLine || Date.now() - indiceT < 30 * 60 * 1000) return;
  renovando = true;
  const antes = indice, estaba = enLinea;
  try { await cargarIndice(); } finally { renovando = false; }
  const p = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (p[0] === "dia" && p[3]) return;
  const f = p[0] === "dia" && p[1] ? p[1] : hoyIso();
  const huella = i => i && i.dias[f] && i.dias[f].huella;
  if (enLinea !== estaba || (p[0] !== "egutegia" && huella(indice) !== huella(antes))) navegar(true);
}

function ajustes() {
  const letra = Number(localStorage.getItem("letra")) || 19;
  document.documentElement.style.setProperty("--letra", letra + "px");
  document.documentElement.dataset.tema = localStorage.getItem("tema") || "claro";
}

document.addEventListener("click", e => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.ir) location.hash = b.dataset.ir;
  if (b.dataset.salmo) {                       // salmo invitatorio: se repinta en su sitio, sin navegar
    const y = b.getBoundingClientRect().top;
    if (invPlegable && b.getAttribute("aria-pressed") === "true") { aperturaInv(false); plegarSalmoInv(); }      // el abierto: se pliega
    else {
      localStorage.setItem("salmoInv", b.dataset.salmo);
      document.querySelectorAll("[data-salmo]").forEach(x => x.setAttribute("aria-pressed", x === b));
      $("salmo-inv").innerHTML = salmoInvHtml(b.dataset.salmo);
      if (aperturaInv(true)) window.scrollBy(0, b.getBoundingClientRect().top - y);     // el botón no se mueve bajo el dedo
    }
  }
  if (b.dataset.letra) {
    const v = Math.min(30, Math.max(14, (Number(localStorage.getItem("letra")) || 19) + 2 * Number(b.dataset.letra)));
    localStorage.setItem("letra", v); ajustes();
  }
  if ("tema" in b.dataset) { localStorage.setItem("tema", document.documentElement.dataset.tema === "oscuro" ? "claro" : "oscuro"); ajustes(); }
});
$("btn-cal").onclick = () => { location.hash = "#/egutegia/" + hoyIso().slice(0, 7); };
// «Gaur»: las oraciones de hoy. Si ya se está en «#/», no hay hashchange: se vuelve a pintar.
$("btn-gaur").onclick = () => { if (location.hash === "#/" || location.hash === "") navegar(); else location.hash = "#/"; renovarIndice(); };
window.addEventListener("hashchange", () => navegar());

// La app puede pasar días abierta en segundo plano: al volver a ella en otro día se carga de nuevo,
// para abrir en el día de hoy y con la última versión publicada (el código viejo no sabe pintar
// datos de un formato posterior: el 13-nov-2026 el Dei-salmoa salía sin salmo por eso).
const cargada = hoyIso();
document.addEventListener("visibilitychange", () => {
  if (document.hidden) return;
  if (hoyIso() !== cargada && navigator.onLine) location.replace(location.pathname + location.search);
  else renovarIndice();
});

// Guarda las pantallas para abrir la app sin conexión (solo en la versión publicada).
if ("serviceWorker" in navigator && location.hostname.endsWith("github.io")) navigator.serviceWorker.register("sw.js");

// Al arrancar, siempre el día de hoy (decisión del usuario, 13-nov-2026): el WebView restaura la última
// dirección (`restoreState` tras cerrar Android la app en segundo plano), y con ella el día que se miraba.
if (location.hash && location.hash !== "#/") history.replaceState(null, "", location.pathname + location.search + "#/");

ajustes();
navegar().then(async () => {                       // en segundo plano: la semana que viene, para leer sin conexión
  if (!enLinea || !indice) return;
  for (let n = 1; n <= 7; n++) if (enVentana(mas(hoyIso(), n))) await cargarDia(mas(hoyIso(), n));
});
