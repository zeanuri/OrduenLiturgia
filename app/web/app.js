/* Orduen Liturgia — Invitatorio, Laudes y Vísperas.
   Lee los días ya resueltos que genera cada noche el repositorio (indice.json y
   dias/AAAA-MM-DD.json), los guarda en el dispositivo y funciona sin conexión
   con lo último que bajó. Formato: Formato.md. */
"use strict";

// De dónde se leen los datos. `?base=` lo cambia (pruebas en local).
const BASE = new URLSearchParams(location.search).get("base") || "https://zeanuri.github.io/OrduenLiturgia/";
const SEMILLA = "datos/";            // copia incluida en la app: primer arranque sin conexión

// Rótulos. PROVISIONALES: pendientes de revisar por quien fije el bizkaiera.
const R = {
  app: "Orduen Liturgia", invitatorio: "Dei-salmoa", laudes: "Gorespenak", visperas: "Bezperak",
  primeras: "Lehenengo Bezperak", misa: "Mezako irakurgaiak", calendario: "Egutegia", hoy: "Gaur",
  prueba: "PROBAKO TESTUAK — ez dira liturgia-testuak", sinDatos: "Ezin izan da eguna kargatu.",
  sinConexion: "Konexino barik: gordetako azkena erakusten da.", falta: "Bizkaierazko bertsioaren zain",
  salterio: "Salmutegiko astea", opcional: "aukerakoa",
  // Días y meses en batua, como el resto de rótulos de lecturasdeldia.org/eu.
  dias: ["Astelehena", "Asteartea", "Asteazkena", "Osteguna", "Ostirala", "Larunbata", "Igandea"],
  diasCortos: ["al", "ar", "az", "og", "or", "lr", "ig"],
  meses: ["urtarrila", "otsaila", "martxoa", "apirila", "maiatza", "ekaina", "uztaila", "abuztua", "iraila", "urria", "azaroa", "abendua"],
};
const COLORES = { Verde: "#2e7d32", Morado: "#6a1b9a", Blanco: "#ffffff", Rojo: "#c62828", Rosa: "#f48fb1", Negro: "#222222" };
// Color del tiempo para las letras de la cabecera (el blanco litúrgico se escribe en oro oscuro).
const TINTA = { Verde: "#1b7d44", Morado: "#5b3a8e", Rojo: "#b3202a", Blanco: "#8c6e18", Rosa: "#a84e74" };
const HORAS = ["invitatorio", "laudes", "visperas"];

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

let indice = null, enLinea = true;

async function cargarIndice() {
  try {
    indice = await pedir(BASE + "indice.json");
    almacen.guardar("indice", indice);
  } catch (e) {
    enLinea = false;
    indice = await almacen.leer("indice") || await pedir(SEMILLA + "indice.json").catch(() => null);
  }
  return indice;
}

async function cargarDia(fecha) {
  const huella = indice && indice.dias[fecha] && indice.dias[fecha].huella;
  const guardado = await almacen.leer("dia:" + fecha);
  if (guardado && guardado.huella === huella) return guardado.dia;
  try {
    const dia = await pedir(BASE + "dias/" + fecha + ".json");
    almacen.guardar("dia:" + fecha, { huella, dia });
    return dia;
  } catch (e) {
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

async function vistaDia(fecha, c) {
  const dia = await cargarDia(fecha);
  if (!dia) { cabecera(fechaLarga(fecha), "", null); $("vista").innerHTML = avisos(`<p class="aviso">${R.sinDatos}</p>`); return; }
  const cel = dia.celebraciones[c] || dia.celebraciones[0];
  c = dia.celebraciones.indexOf(cel);
  cabecera(R.app, "", null);
  const cab = dia.cabecera;
  const tarde = new Date().getHours() >= 13;
  const ahora = fecha === hoyIso() ? (tarde ? "visperas" : "laudes") : null;
  const fichas = dia.celebraciones.length < 2 ? "" : `<div class="fichas">` + dia.celebraciones.map((x, i) =>
    `<button class="ficha" aria-pressed="${i === c}" data-ir="#/dia/${fecha}/${i}">${esc(x.nombre_eu)}${x.opcional ? ` (${R.opcional})` : ""}</button>`).join("") + `</div>`;
  const fila = h => {
    const pv = h === "visperas" && cel.visperas_de.cuales === "primeras";
    return `<li><a class="${h === ahora ? "ahora" : ""}" href="#/dia/${fecha}/${c}/${h}"><span>${pv ? R.primeras : R[h]}` +
      (pv ? `<small>${esc(cel.visperas_de.de_eu)}</small>` : "") + `</span></a></li>`;
  };
  const orden = HORAS;                 // orden fijo: Dei-salmoa, Gorespenak, Bezperak
  $("vista").innerHTML = avisos() +
    `<div class="cab" style="--c:${TINTA[dia.color] || TINTA.Verde}">
       ${enVentana(mas(fecha, -1)) ? `<a class="flecha ant" href="#/dia/${mas(fecha, -1)}" aria-label="Aurreko eguna">&larr;</a>` : ""}
       ${enVentana(mas(fecha, 1)) ? `<a class="flecha sig" href="#/dia/${mas(fecha, 1)}" aria-label="Hurrengo eguna">&rarr;</a>` : ""}
       <div class="fecha">${fechaLarga(fecha)}</div>
       <h1>${esc(cab.nombre)}</h1>
       ${cab.memoria ? `<div class="memoria"><span class="estrella">&#9733;</span>${esc(cab.memoria)} <em>${esc(cab.memoria_rango)}</em></div>` : ""}
       <div class="info">${esc(cab.tiempo)} &middot; ${esc(cab.rango)} &middot; ${R.salterio}: ${["", "I", "II", "III", "IV"][dia.semana_salterio]}</div>
     </div>${fichas}
     <ul class="horas">${orden.map(fila).join("")}
       <li><a href="${esc(dia.misa)}" target="_blank" rel="noopener"><span>${R.misa}<small>lecturasdeldia.org</small></span></a></li></ul>
     ${fecha !== hoyIso() ? `<nav class="pasos"><a href="#/">${R.hoy}</a></nav>` : ""}`;
}

const enVentana = f => !indice || (f >= indice.desde && f <= indice.hasta);

function lineas(ls) {
  // Una marca (V., R., Ant.) se pinta en el mismo renglón que el texto que la sigue.
  let html = "", marca = "";
  for (const l of ls || []) {
    if (l.t === "v" || l.t === "r" || l.t === "ant") { marca += `<span class="marca">${esc(l.x)}</span>`; continue; }
    html += `<p class="l-${l.t}">${l.t === "texto" || l.t === "estrofa" ? marca : ""}${esc(l.x)}</p>`;
    if (l.t === "texto" || l.t === "estrofa") marca = "";
  }
  return html + (marca ? `<p>${marca}</p>` : "");
}

function parteHtml(p) {
  if (p.falta) return `<section><p class="falta" title="${esc(p.falta[0])}">${R.falta}</p></section>`;
  return `<section data-parte="${p.parte}">${p.titulo ? `<p class="l-titulo">${esc(p.titulo)}</p>` : ""}${lineas(p.lineas)}</section>`;
}

async function vistaHora(fecha, c, hora) {
  const dia = await cargarDia(fecha);
  const cel = dia && dia.celebraciones[c];
  if (!cel || !cel.horas[hora]) { location.hash = "#/dia/" + fecha; return; }
  const partes = cel.horas[hora];
  const pv = hora === "visperas" && cel.visperas_de.cuales === "primeras";
  cabecera(fechaLarga(fecha), pv ? R.primeras : R[hora], `#/dia/${fecha}/${c}`);
  // La antífona se dice antes y después de su salmo o cántico: se repite detrás.
  let cuerpo = "", ant = null;
  partes.forEach((p, i) => {
    cuerpo += parteHtml(p);
    if (p.parte.startsWith("ant")) ant = p;
    else if (ant) { cuerpo += parteHtml(ant); ant = null; }
  });
  const prueba = partes.some(p => p.prueba);
  $("vista").innerHTML = avisos(prueba ? `<p class="aviso prueba">${R.prueba}</p>` : "") +
    `<div class="herramientas"><button data-letra="-1" aria-label="Letra txikiagoa">A&minus;</button>
       <button data-letra="1" aria-label="Letra handiagoa">A+</button><button data-tema aria-label="Gaua / eguna">&#9680;</button></div>
     <article class="lector"><h1>${esc(pv ? cel.visperas_de.de_eu : cel.nombre_eu)}</h1><h2>${pv ? R.primeras : R[hora]}</h2>${cuerpo}</article>`;
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
      : `<span class="d">${d}</span>`;
  }
  $("vista").innerHTML = avisos() +
    `<div class="mes"><button data-ir="#/egutegia/${otro(-1)}" aria-label="Aurreko hilea">&larr;</button>
       <span>${R.meses[m - 1]} ${a}</span><button data-ir="#/egutegia/${otro(1)}" aria-label="Hurrengo hilea">&rarr;</button></div>
     <div class="rejilla">${celdas}</div>`;
}

// ── Navegación ────────────────────────────────────────────────────────────
async function navegar() {
  const p = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (!indice) await cargarIndice();
  if (p[0] === "egutegia") vistaCalendario(p[1] || hoyIso().slice(0, 7));
  else if (p[0] === "dia" && p[3]) await vistaHora(p[1], Number(p[2]) || 0, p[3]);
  else await vistaDia(p[0] === "dia" && p[1] ? p[1] : hoyIso(), Number(p[2]) || 0);
  window.scrollTo(0, 0);
  document.documentElement.dataset.lista = location.hash || "#/";      // señal para las pruebas
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
  if (b.dataset.letra) {
    const v = Math.min(30, Math.max(14, (Number(localStorage.getItem("letra")) || 19) + 2 * Number(b.dataset.letra)));
    localStorage.setItem("letra", v); ajustes();
  }
  if ("tema" in b.dataset) { localStorage.setItem("tema", document.documentElement.dataset.tema === "oscuro" ? "claro" : "oscuro"); ajustes(); }
});
$("btn-cal").onclick = () => { location.hash = "#/egutegia/" + hoyIso().slice(0, 7); };
window.addEventListener("hashchange", navegar);

// Guarda las pantallas para abrir la app sin conexión (solo en la versión publicada).
if ("serviceWorker" in navigator && location.hostname.endsWith("github.io")) navigator.serviceWorker.register("sw.js");

ajustes();
navegar().then(async () => {                       // en segundo plano: la semana que viene, para leer sin conexión
  if (!enLinea || !indice) return;
  for (let n = 1; n <= 7; n++) if (enVentana(mas(hoyIso(), n))) await cargarDia(mas(hoyIso(), n));
});
