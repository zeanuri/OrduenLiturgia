"""Generador de OrduenLiturgia: un fichero por día con Invitatorio, Laudes y Vísperas.

Para cada fecha de la ventana (40 días atrás, 365 adelante) resuelve con el motor
de calendario de la CEE (`liturgia.py`) qué se celebra, y compone cada hora como
una lista ordenada de PARTES. Cada parte busca su texto en `textos/` por una
cadena de claves candidatas, de la más propia a la más general, y se queda con
la primera que existe. Si no existe ninguna, la parte sale marcada como «falta»:
el generador funciona con los textos a medias y dice exactamente cuáles faltan.

    py -3.14 generar.py                      ventana de hoy (Europe/Madrid)
    py -3.14 generar.py --hoy 2026-11-10     ventana de esa fecha
    py -3.14 generar.py --inventario         además escribe faltan.txt

Formato de textos y de salida: ../Formato.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
PROYECTO = AQUI.parent
sys.path.insert(0, str(AQUI))
import liturgia  # noqa: E402  (copia del motor de calendario de la CEE; ver README)
import liturgical_names_eu as eu  # noqa: E402  (nombres en euskera, los de lecturasdeldia.org/eu)

# Nombres de las celebraciones como los da «Liturgia euskaraz» (decisión del usuario,
# 11-nov-2026), por `id` (o `clave_dia`): {"nombre": …, "rango": …}; los saca
# referencia/nombres_tabla.py del proyecto. Lo que no está aquí lo traduce `eu`.
_NOMBRES = Path(__file__).with_name("nombres_eu.json")
NOMBRES_EU = json.loads(_NOMBRES.read_text(encoding="utf-8")) if _NOMBRES.exists() else {}


def nombre_eu(clave: str, traducido: str) -> str:
    n = NOMBRES_EU.get(clave)
    return n["nombre"] if n else traducido


# Rango en euskera con las palabras de «Liturgia euskaraz». Sale del rango de nuestro motor y no
# de la tabla, para que diga lo mismo que el oficio que se compone (Santa Teresa: memoria aquí, jaia allí).
RANGOS_EU = {"Solemnidad": "festaburua", "Fiesta": "jaia", "Domingo": "igandea",
             "Memoria Obligatoria": "beharrezko oroipena", "Memoria Libre": "nahierazko oroipena",
             "Feria": "asteguna", "Feria privilegiada": "lehentasunezko asteguna", "Conmemoración": "oroitzapena"}


def rango_eu(rango_es: str) -> str:
    return RANGOS_EU.get(rango_es) or eu.localize_rank(rango_es)


def clave_dia(r: dict) -> str:
    """Clave del nombre del día. En la octava de Navidad el motor llama a la feria como al santo
    del día («San Silvestre I, papa», rango Feria): la feria va aparte, con «-feria»."""
    k = slug(r["name"])
    return k + "-feria" if r.get("memorial") == r["name"] and tipo_de(r["rank"]) == "feria" else k

DIAS_ATRAS = 40
DIAS_ADELANTE = 365
WEB_MISA = "https://lecturasdeldia.org/eu/{:%Y/%m/%d}/"

DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
TIEMPOS = {
    "Tiempo Ordinario": "ordinario", "Adviento": "adviento", "Tiempo de Navidad": "navidad",
    "Cuaresma": "cuaresma", "Semana Santa": "semana-santa", "Tiempo de Pascua": "pascua",
}
# Partes variables de Laudes y Vísperas, en su orden. En Laudes `salmo2` es el
# cántico del Antiguo Testamento; en Vísperas `salmo3` es el del Nuevo.
SALMODIA = ["ant1", "salmo1", "ant2", "salmo2", "ant3", "salmo3"]
ORDEN = {
    "laudes": ["fijo/apertura", "himno", *SALMODIA, "lectura", "responsorio", "ant_ev",
               "fijo/benedictus", "preces", "fijo/padrenuestro", "oracion", "fijo/conclusion"],
    "visperas": ["fijo/apertura", "himno", *SALMODIA, "lectura", "responsorio", "ant_ev",
                 "fijo/magnificat", "preces", "fijo/padrenuestro", "oracion", "fijo/conclusion"],
    # `salmos` no es una clave: es la parte que ofrece los cuatro salmos invitatorios (ver INVITATORIO).
    "invitatorio": ["fijo/invitatorio/apertura", "ant", "salmos"],
    # `ant2`/`salmo2` solo salen en las noches de dos salmos (ver `formulario_completas`).
    "completas": ["fijo/apertura", "fijo/completas/examen", "himno", "ant1", "salmo1", "ant2", "salmo2",
                  "lectura", "responsorio", "ant_ev", "fijo/completas/nunc-dimittis", "oracion",
                  "fijo/completas/conclusion", "fijo/completas/maria"],
}
# Salmos del Invitatorio, en el orden de «Liturgia euskaraz» (95., 100., 67., 24.).
INVITATORIO = ["95", "100", "67", "24"]
# Parte que vale para todas las horas del día: se busca también sin la hora en la clave.
COMPARTIDAS = {"oracion"}
# Cabecera de cada parte, con las palabras de «Liturgia euskaraz» (decisión del usuario, 13-nov-2026).
# Allí van como líneas de título dentro de cada unidad; aquí las pone el generador, en `cabecera`.
# El Invitatorio no lleva: su «Hasierako txatala» viene dentro de la apertura.
CABECERAS = {
    "apertura": "Hasierako deia", "himno": "Gorazarrea", "ant1": "Salmoak", "lectura": "Irakurgai laburra",
    "responsorio": "Galde-erantzuna", "ant_ev": "Ebanjelioko kantika", "preces": "Eskariak",
    "padrenuestro": "Jaunaren otoitza", "oracion": "Otoitza", "conclusion": "Amaiera",
    "examen": "Kontzientzia azterketa", "maria": "Maria Birjina Dohatsuari azken kantuak",
}
# Las preces en batua ya traen al final la cabecera del Padre nuestro (una, en castellano en el servidor).
YA_EN_LA_ANTERIOR = {"padrenuestro": {"Jaunaren otoitza", "Oración dominical"}}


def titulos(pieza: dict | None) -> set[str]:
    return {l["x"] for l in (pieza or {}).get("lineas", []) if l["t"] == "titulo"}


def cabecera_de(hora: str, nombre: str, pieza: dict | None, anterior: dict | None, noche: dict | None) -> str | None:
    """Cabecera de la parte, o None si no lleva o si el texto ya la trae (en la pieza o al final de la anterior)."""
    if hora == "invitatorio":
        return None
    cab = CABECERAS.get(nombre)
    if hora == "completas" and nombre == "ant1" and not noche["dos_salmos"]:
        cab = "Salmoa"                                     # noche de un solo salmo
    if cab is None or cab in titulos(pieza) or YA_EN_LA_ANTERIOR.get(nombre, set()) & titulos(anterior):
        return None
    return cab


# ── Calendario ──────────────────────────────────────────────────────────────

def slug(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def semana_del_tiempo(d: date, tiempo: str, r: dict) -> int | None:
    """Semana dentro de su tiempo litúrgico (None donde no se cuenta por semanas)."""
    if tiempo == "ordinario":
        if r.get("ot_week"):
            return r["ot_week"]
        # Las solemnidades y fiestas no traen `ot_week`: se calcula igual que el motor.
        if d < liturgia.easter(d.year):
            return liturgia.get_ot_week_before_lent(d, d.year)
        return liturgia.get_ot_week_after_pentecost(d, d.year)
    if tiempo == "adviento":
        return (d - liturgia.advent_start(d.year)).days // 7 + 1
    pascua = liturgia.easter(d.year)
    if tiempo == "cuaresma":
        primer_domingo = pascua - timedelta(days=42)
        return None if d < primer_domingo else (d - primer_domingo).days // 7 + 1
    if tiempo == "pascua":
        return (d - pascua).days // 7 + 1
    return None


def semana_salterio(d: date, tiempo: str, semana: int | None) -> int:
    """Semana del salterio (1-4). Cotejada con la app «Liturgia euskaraz» en once fechas."""
    if tiempo == "semana-santa":
        return 2
    if tiempo == "cuaresma" and semana is None:      # de Ceniza al sábado
        return 4
    if tiempo == "navidad":
        # Semana I hasta el domingo que sigue al 1 de enero; desde él, semana II.
        if d.month == 12:
            return 1
        uno = date(d.year, 1, 1)
        domingo = uno + timedelta(days=(6 - uno.weekday()) % 7 or 7)
        return 2 if d >= domingo or d.day > 6 else 1   # tras Epifanía, siempre II
    return (semana - 1) % 4 + 1


COMUNES = [  # (patrón sobre el nombre en castellano, común). Heurística: revisar con el libro.
    (r"Dedicación", "dedicacion"),
    (r"Virgen María|Nuestra Señora|Santa María|Inmaculad|Asunción", "santa-maria"),
    (r"\bapóstol|\bevangelista", "apostoles"),
    (r"\bmártires\b", "martires-varios"),
    (r"\bmártir\b", "martires-uno"),
    (r"\bdoctor", "doctores"),
    (r"\bpapa\b|\bobispo|\bpresbítero", "pastores"),
    (r"\bvirgen\b", "virgenes"),
    (r"\babad|\breligios|\bmonje|\bermitañ", "religiosos"),
]


def comunes_de(nombre: str) -> list[str]:
    lista = [c for patron, c in COMUNES if re.search(patron, nombre)]
    if re.match(r"Santas? ", nombre):
        lista.append("santas-mujeres")
    elif re.match(r"(San|Santo|Santos|Beato|Beatos) ", nombre):
        lista.append("santos-varones")
    return lista


def tipo_de(rango: str) -> str:
    if rango == "Solemnidad":
        return "solemnidad"
    if rango == "Fiesta":
        return "fiesta"
    if rango == "Domingo":
        return "domingo"
    return "memoria" if rango.startswith("Memoria") else "feria"


def dia_liturgico(d: date) -> dict:
    """Lo que se celebra el día `d`: datos del tiempo y lista de celebraciones."""
    r = liturgia.calculate(d)
    tiempo = TIEMPOS[r["season"]]
    semana = semana_del_tiempo(d, tiempo, r)
    info = {
        "fecha": d, "r": r, "tiempo": tiempo, "semana": semana,
        "salterio": semana_salterio(d, tiempo, semana),
        "ciclo": r["sunday_cycle"].replace("Ciclo ", ""), "color": r["color"],
    }
    principal = {"nombre": r["name"], "rango": r["rank"], "opcional": False}
    opcionales = []
    mem, rango_mem = r.get("memorial"), r.get("memorial_rank")
    if mem and rango_mem == "Memoria Libre":
        # El motor junta en una sola cadena los santos ALTERNATIVOS de una memoria libre («A / B / C»):
        # se elige uno. Cada uno es su celebración opcional, con su `id`, su nombre y sus textos. Los
        # nombres con «y» («Santos Juan Fisher y Tomás Moro») son UNA celebración conjunta: solo se parte por « / ».
        alternos = mem.split(" / ")
        for nombre in alternos:
            opcionales.append({"nombre": nombre, "rango": rango_mem, "opcional": True, "alterna": len(alternos) > 1})
    elif mem:                                   # memoria obligatoria o fiesta: es la celebración
        principal = {"nombre": mem, "rango": rango_mem, "opcional": False}
    info["celebraciones"] = [principal, *opcionales]
    for c in info["celebraciones"]:
        c["tipo"] = tipo_de(c["rango"])
        # Nombre en euskera: el del día por `localize_name`; el de un santo, por `localize_memorial`.
        es_dia = c["nombre"] == r["name"] and not c["opcional"]
        # El `id` del día es su clave: en la octava de Navidad (el motor llama a la feria como al santo)
        # la feria lleva «-feria» y no comparte `id` con la memoria libre del santo.
        c["id"] = clave_dia(r) if es_dia else slug(c["nombre"])
        clave = c["id"]
        c["nombre_eu"] = nombre_eu(clave, eu.localize_name(c["nombre"]) if es_dia
                                   else eu.localize_memorial(c["nombre"]))
        c["rango_eu"] = rango_eu(c["rango"])
    info["nivel"] = liturgia.get_precedence_level(
        principal["nombre"], principal["rango"], r["season"], d, d.weekday() == 6)
    return info


# ── Cadenas de claves ───────────────────────────────────────────────────────

def bases_del_tiempo(info: dict) -> list[str]:
    """Carpetas del propio del tiempo que valen para el día, de la más concreta a la común."""
    d, t, w, dia = info["fecha"], info["tiempo"], info["semana"], DIAS[info["fecha"].weekday()]
    if t == "ordinario":
        if dia == "dom":
            return [f"tiempo/ordinario/dom{w}-{info['ciclo']}", f"tiempo/ordinario/dom{w}"]
        return []
    if t == "adviento":
        tardio = d.month == 12 and d.day >= 17
        return ([f"tiempo/adviento/{d:%m-%d}"] if tardio else []) + [
            f"tiempo/adviento/s{w}/{dia}", "tiempo/adviento/comun-17-24" if tardio else "tiempo/adviento/comun"]
    if t == "navidad":
        tras_epifania = d.month == 1 and d.day > 6
        return [f"tiempo/navidad/{d:%m-%d}",
                "tiempo/navidad/comun-epifania" if tras_epifania else "tiempo/navidad/comun"]
    if t == "cuaresma":
        return [f"tiempo/cuaresma/ceniza/{dia}" if w is None else f"tiempo/cuaresma/s{w}/{dia}",
                "tiempo/cuaresma/comun"]
    if t == "semana-santa":
        return [f"tiempo/semana-santa/{dia}", "tiempo/semana-santa/comun"]
    ascension = liturgia.easter(d.year) + timedelta(days=42)
    return [f"tiempo/pascua/octava/{dia}" if w == 1 else f"tiempo/pascua/s{w}/{dia}",
            "tiempo/pascua/comun-ascension" if d > ascension else "tiempo/pascua/comun"]


def fijas(info: dict, cel: dict, hora: str, parte: str) -> list[str]:
    """Una parte fija: la de la hora (`fijo/laudes/apertura`) antes que la común (`fijo/apertura`).
    Cambian con el tiempo la apertura, sin «Aleluia» en Cuaresma y Semana Santa, y la conclusión,
    con «Aleluia, aleluia» en la octava de Pascua y Pentecostés: esa variante va delante y, si no la
    hay en la hora, la propia del día (en batua) antes que la de todo el año."""
    if parte.startswith("fijo/invitatorio/"):
        return [parte]
    h = "visperas" if hora in ("visperas1", "completas") else hora     # la apertura de Completas es la de Vísperas
    nombre = parte.removeprefix("fijo/")
    claves = [f"fijo/{h}/{nombre}", parte]
    pascua = (info["tiempo"] == "pascua" and info["semana"] == 1) or cel["id"] == "domingo-de-pentecostes"
    if nombre == "apertura" and info["tiempo"] in ("cuaresma", "semana-santa"):
        claves.insert(0, f"fijo/{h}/apertura-cuaresma")
    if nombre == "conclusion" and pascua:
        claves[:0] = [f"fijo/{h}/conclusion-pascua", f"propio/{cel['id']}/{hora}/{parte}"]
    return claves


def candidatas(info: dict, cel: dict, hora: str, parte: str) -> list[str]:
    """Claves donde buscar `parte` de `hora`, de la más propia a la más general."""
    if parte.startswith("fijo/"):
        return fijas(info, cel, hora, parte)
    tipo = cel["tipo"]
    dia = DIAS[info["fecha"].weekday()]
    hora_sal = "visperas1" if hora == "visperas1" and dia == "dom" else hora.replace("visperas1", "visperas")
    salterio = f"salterio/s{info['salterio']}/{dia}"
    propio = [f"propio/{cel['id']}"] + [f"comunes/{c}" for c in comunes_de(cel["nombre"])]
    tiempo = bases_del_tiempo(info)
    es_salmo = parte.startswith("salmo")
    # Los salmos del tiempo, sin lo que el blog escribe por fecha (`…/12-21`, `…/01-04`: lleva los salmos
    # del día de la semana de aquel año) y sin la salmodia común de Navidad fuera de la octava (el 2-5 de
    # enero se reza el salterio). Las antífonas sí buscan en todo el tiempo.
    tiempo_salmos = [b for b in tiempo if not re.search(r"/\d\d-\d\d$", b)
                     and not (b == "tiempo/navidad/comun" and info["fecha"].month != 12)]

    if tipo in ("solemnidad", "fiesta"):
        bases = list(propio)
        if es_salmo or parte.startswith("ant") and parte != "ant_ev":
            # Sin salmodia propia: en Laudes, la del domingo de la semana I.
            bases.append("salterio/s1/dom" if hora == "laudes" else salterio)
    # Memorias, como «Liturgia euskaraz» (decisión delegada por el usuario, 11-nov-2026): lo propio
    # del santo, si lo tiene (también salmodia propia, como San Martín); lo demás, de la feria. Sin
    # caer a los comunes: lo que el santo toma del común ya está en su `propio/`.
    elif tipo == "memoria":
        bases = [f"propio/{cel['id']}"] + (tiempo_salmos if es_salmo else tiempo) + [salterio]
    else:                                        # ferias y domingos: lo propio del tiempo y, si no, el salterio
        bases = (tiempo_salmos if es_salmo else tiempo) + [salterio]

    claves = []
    for b in bases:
        h = hora_sal if b.startswith("salterio/") else hora
        claves.append(f"{b}/{h}/{parte}")
        if parte in COMPARTIDAS:
            claves.append(f"{b}/{parte}")
    if parte == "oracion" and info["tiempo"] == "ordinario" and tipo == "domingo":
        claves.insert(0, f"tiempo/ordinario/s{info['semana']}/oracion")
    if parte == "ant_ev" and dia == "dom":
        # Domingo: antes que la común, la antífona del ciclo (`…/ant_ev-A`), si la hay.
        ciclo = info["ciclo"]
        claves = [v for c in claves for v in (
            [c] if c.startswith("salterio/") or f"-{ciclo}/" in c else [f"{c}-{ciclo}", c])]
    return claves


# ── Completas ───────────────────────────────────────────────────────────────
# La regla sale de comparar este calendario con las noches de «Liturgia euskaraz»
# (referencia/completas.py, informe en referencia/completas_informe.txt).

def primeras_completas(info: dict, manana: dict, primeras: bool) -> bool:
    """¿La noche es la primera Completas de mañana? Como las primeras Vísperas, y además toda noche de
    sábado: el servidor da el domingo entero (también cuando una fiesta o solemnidad del sábado le
    quita las Vísperas). En Semana Santa nunca: el miércoles no precede al Jueves Santo, y el Sábado
    Santo tiene las suyas (la Vigilia no las tiene)."""
    if info["tiempo"] == "semana-santa":
        return False
    return primeras or manana["fecha"].weekday() == 6


def formulario_completas(info: dict, manana: dict, primeras: bool) -> dict:
    """Qué Completas se rezan la noche de `info`. Siete formularios (1-7): el 1, tras las primeras
    Vísperas; el 2, domingo y solemnidad; del 3 al 7, de lunes a viernes. La octava de Pascua alterna
    1 (lunes, miércoles, viernes) y 2 (martes, jueves). Devuelve el formulario `f` y lo demás que
    cambia el texto: tiempo de la noche (el de mañana si son primeras), Pascua, octava, Triduo, oración
    de solemnidad y si tiene dos salmos."""
    pc = primeras_completas(info, manana, primeras)
    x = manana if pc else info
    d, wd = info["fecha"], info["fecha"].weekday()
    cel = info["celebraciones"][0]
    octava_hoy = (not pc and info["tiempo"] == "pascua" and 0 < (d - liturgia.easter(d.year)).days < 7)
    if pc:
        f = 1
    elif octava_hoy:
        f = 1 if wd in (0, 2, 4) else 2
    elif wd == 6 or cel["tipo"] == "solemnidad":
        f = 2
    else:
        f = 1 if wd == 5 else wd + 3
    pascua = x["tiempo"] == "pascua"
    cel_x = x["celebraciones"][0]
    # Oración «de solemnidad»: la solemnidad que no es domingo, ella misma o su víspera (no la
    # octava de Pascua, que reza como domingo, ni los Difuntos, que rezan el formulario 2).
    solemne = (cel_x["tipo"] == "solemnidad" and x["fecha"].weekday() != 6 and not octava_hoy
               and cel_x["id"] != "conmemoracion-de-los-fieles-difuntos")
    return {
        "f": f, "primeras": pc, "info": x, "cel": cel_x, "tiempo": x["tiempo"], "pascua": pascua,
        "octava": pascua and (x["fecha"] - liturgia.easter(x["fecha"].year)).days <= 7,
        "triduo": ("jue", "vie", "sab")[wd - 3] if info["tiempo"] == "semana-santa" and wd in (3, 4, 5) else None,
        "solemnidad": solemne, "dos_salmos": f in (1, 5) and not pascua,
    }


def candidatas_completas(noche: dict, parte: str) -> list[str]:
    """Claves donde buscar `parte` de Completas, de la más propia a la más general. Lo que no
    depende del formulario (responsorio, antífona del Evangelio) tiene una sola clave general."""
    f, p = noche["f"], parte
    if p == "fijo/apertura":      # la de Vísperas (sin «Aleluia» en Cuaresma y Semana Santa), según el tiempo de la noche
        return fijas(noche["info"], noche["cel"], "completas", p)
    if p.startswith("fijo/completas/"):
        return [p + "-pascua", p] if p.endswith("/maria") and noche["pascua"] else [p]
    if p == "himno":              # un solo himno, o los dos juntos (el del formulario 2) en los demás tiempos
        return [f"completas/f{f if noche['tiempo'] == 'ordinario' else 2}/himno"]
    if p == "responsorio":
        return ([f"completas/triduo/{noche['triduo']}/responsorio"] if noche["triduo"] else []) + (
            ["completas/octava/responsorio"] if noche["octava"] else []) + (
            ["completas/pascua/responsorio"] if noche["pascua"] else []) + ["completas/responsorio"]
    if p == "ant_ev":
        return (["completas/pascua/ant_ev"] if noche["pascua"] else []) + ["completas/ant_ev"]
    if p == "oracion":
        return (["completas/solemnidad/oracion"] if noche["solemnidad"] else []) + [f"completas/f{f}/oracion"]
    if noche["pascua"] and p in ("ant1", "salmo1"):
        return [f"completas/pascua/f{f}/{p}", f"completas/f{f}/{p}"]
    return [f"completas/f{f}/{p}"]


# ── Textos ──────────────────────────────────────────────────────────────────

def cargar_textos(carpeta: Path) -> dict:
    """Une todos los .json de `carpeta`: cada uno es un diccionario clave → pieza."""
    textos: dict = {}
    for f in sorted(carpeta.rglob("*.json")):
        for clave, pieza in json.loads(f.read_text(encoding="utf-8")).items():
            if clave in textos:
                raise SystemExit(f"Clave repetida: {clave} ({f})")
            textos[clave] = pieza
    return textos


def resolver(textos: dict, claves: list[str]) -> tuple[str | None, dict | None]:
    for clave in claves:
        pieza, vistos = textos.get(clave), {clave}
        while pieza is not None and "ref" in pieza:       # una pieza puede remitir a otra
            if pieza["ref"] in vistos:
                raise SystemExit(f"Referencia circular en {clave}")
            vistos.add(pieza["ref"])
            pieza = textos.get(pieza["ref"])
        if pieza is not None:
            return clave, pieza
    return None, None


def mismo_salmo(a: dict, b: dict) -> bool:
    """¿Dos piezas son el mismo salmo o cántico? Un salmo, por su número («65. [64] Salmoa» y «64 Salmoa»;
    lo que sigue a la coma son versículos); un cántico, por libro y capítulo de su cita, que en batua va
    en la línea siguiente al título («Kantika» / «Ik. 1 Pe 2, 21b-24»). Si no se sabe, no es el mismo:
    se queda el del tiempo (en Cuaresma el cántico dominical de Vísperas no es el del salterio)."""
    def firma(pieza: dict) -> set:
        ls = [l["x"] for l in (pieza.get("lineas") or [])[:2] if len(l["x"]) < 60]
        if not ls:
            return set()
        if ls[0].startswith("Kantika"):
            cita = re.sub(r"Kantika|Ik(us)?\b\.?|[():]", " ", " ".join(ls))
            m = re.search(r"((?:\d\s*)?[A-Za-z]+)\s*(\d+)", cita)
            return {(re.sub(r"\s", "", m.group(1)).lower().replace("apk", "ap"), m.group(2))} if m else set()
        return set(re.findall(r"\d+", ls[0].split(",")[0]))
    fa, fb = firma(a), firma(b)
    return bool(fa & fb)



def salmos_invitatorio(textos: dict, faltan: dict) -> dict:
    """La parte `salmo` del Invitatorio: los cuatro salmos a elegir (los que tengan texto)."""
    claves = {n: f"fijo/invitatorio/salmo{n}" for n in INVITATORIO}
    opciones = []
    for n, k in claves.items():
        clave, pieza = resolver(textos, [k])
        if pieza is not None:
            opciones.append({"n": n, "clave": clave,
                             **{c: pieza[c] for c in ("titulo", "lineas", "prueba", "fuente", "batua") if c in pieza}})
    if opciones:
        return {"parte": "salmo", "opciones": opciones}
    for k in claves.values():
        faltan.setdefault(k, set()).add(k)
    return {"parte": "salmo", "falta": list(claves.values())}


def componer(info: dict, cel: dict, hora: str, textos: dict, faltan: dict, noche: dict | None = None) -> list[dict]:
    partes, anterior = [], None
    for parte in ORDEN["visperas" if hora == "visperas1" else hora]:
        if parte == "salmos":
            partes.append(salmos_invitatorio(textos, faltan))
            continue
        if hora == "completas":
            if parte in ("ant2", "salmo2") and not noche["dos_salmos"]:
                continue                                  # noche de un solo salmo: no hay segundo
            claves = candidatas_completas(noche, parte)
        else:
            claves = candidatas(info, cel, hora, parte)
        clave, pieza = resolver(textos, claves)
        if hora != "completas" and cel["tipo"] == "memoria" and not parte.startswith(("fijo/", "salmo")) and (
                pieza is None or pieza.get("batua") and not clave.startswith("propio/")):
            # El bizkaiera manda: si la feria solo está en batua y el común está en bizkaiera, el común.
            # Lo propio del santo, aunque sea batua, se queda (como en las fiestas).
            h = "visperas" if hora == "visperas1" else hora
            comun = [f"comunes/{c}/{h}/{parte}" for c in comunes_de(cel["nombre"])]
            c2, p2 = resolver(textos, comun)
            if p2 is not None and not p2.get("batua"):
                clave, pieza, claves = c2, p2, claves + comun
        if (hora != "completas" and parte.startswith("salmo") and cel["tipo"] in ("feria", "domingo", "memoria")
                and pieza is not None and pieza.get("batua") and clave.startswith("tiempo/")):
            # El bizkaiera manda: el salmo del tiempo que solo está en batua no desplaza al mismo salmo
            # del salterio si este está en bizkaiera (casi todos los del tiempo repiten el del salterio).
            c2, p2 = resolver(textos, [c for c in claves if c.startswith("salterio/")])
            if p2 is not None and not p2.get("batua") and mismo_salmo(pieza, p2):
                clave, pieza = c2, p2
        nombre = parte.split("/")[-1]
        cab = cabecera_de(hora, nombre, pieza, anterior, noche)
        cab = {"cabecera": cab} if cab else {}
        if pieza is None:
            faltan.setdefault(claves[-1], set()).add(claves[0])
            partes.append({"parte": nombre, **cab, "falta": claves})
        else:
            partes.append({"parte": nombre, **cab, "clave": clave,
                           **{k: pieza[k] for k in ("titulo", "lineas", "prueba", "fuente", "batua") if k in pieza}})
        anterior = pieza
    return partes


# ── El día ──────────────────────────────────────────────────────────────────

def tiene_primeras_visperas(info: dict) -> bool:
    tipo = info["celebraciones"][0]["tipo"]
    return tipo in ("solemnidad", "domingo") or (tipo == "fiesta" and info["fecha"].weekday() == 6)


def primeras_visperas(info: dict, manana: dict) -> bool:
    """¿Las Vísperas de hoy son las primeras de mañana? Si mañana las tiene y precede a hoy en la tabla
    de precedencia. Dos excepciones: el Triduo y el domingo de Pascua no tienen primeras (el miércoles
    santo reza las suyas), y en un empate de nivel gana el domingo de mañana (sábado después de Ceniza,
    sábado de la octava de Pascua)."""
    if not tiene_primeras_visperas(manana):
        return False
    if 0 <= (liturgia.easter(manana["fecha"].year) - manana["fecha"]).days <= 3:
        return False
    return manana["nivel"] < info["nivel"] or (
        manana["nivel"] == info["nivel"] and manana["celebraciones"][0]["tipo"] == "domingo")


def generar_dia(d: date, textos: dict, faltan: dict) -> dict:
    info, manana = dia_liturgico(d), dia_liturgico(d + timedelta(days=1))
    primeras = primeras_visperas(info, manana)
    noche = formulario_completas(info, manana, primeras)
    celebraciones = []
    for cel in info["celebraciones"]:
        horas = {h: componer(info, cel, h, textos, faltan) for h in ("invitatorio", "laudes")}
        if primeras:
            cel_m = manana["celebraciones"][0]
            horas["visperas"] = componer(manana, cel_m, "visperas1", textos, faltan)
            visperas_de = {"cuales": "primeras", "de": cel_m["nombre"], "de_eu": cel_m["nombre_eu"]}
        else:
            horas["visperas"] = componer(info, cel, "visperas", textos, faltan)
            visperas_de = {"cuales": "segundas" if cel["tipo"] in ("solemnidad", "domingo") else "del dia",
                           "de": cel["nombre"], "de_eu": cel["nombre_eu"]}
        # Completas: las mismas para todas las celebraciones del día (dependen de la noche).
        horas["completas"] = componer(noche["info"], noche["cel"], "completas", textos, faltan, noche)
        if noche["primeras"]:
            completas_de = {"cuales": "primeras", "de": noche["cel"]["nombre"], "de_eu": noche["cel"]["nombre_eu"]}
        else:
            completas_de = {"cuales": "segundas" if cel["tipo"] in ("solemnidad", "domingo") else "del dia",
                            "de": cel["nombre"], "de_eu": cel["nombre_eu"]}
        celebraciones.append({
            "id": cel["id"], "nombre": cel["nombre"], "nombre_eu": cel["nombre_eu"],
            "rango": cel["rango"], "rango_eu": cel["rango_eu"], "opcional": cel["opcional"],
            "visperas_de": visperas_de, "completas_de": completas_de, "horas": horas,
        })
    r = info["r"]
    return {
        "fecha": d.isoformat(), "dia_semana": DIAS[d.weekday()], "tiempo": info["tiempo"],
        "semana": info["semana"], "semana_salterio": info["salterio"], "ciclo_dominical": info["ciclo"],
        "color": r["color"], "celebraciones": celebraciones, "misa": WEB_MISA.format(d),
        # Cabecera del día en euskera, como la de lecturasdeldia.org/eu.
        "cabecera": {
            "nombre": nombre_eu(clave_dia(r), eu.localize_name(r["name"])), "tiempo": eu.localize_season(r["season"]),
            "rango": rango_eu(r["rank"]), "ciclo": eu.localize_sunday_cycle(r["sunday_cycle"]),
            "ciclo_ferial": eu.localize_weekday_cycle(r["weekday_cycle"]) if r.get("weekday_cycle") else "",
            "memoria": " / ".join(nombre_eu(slug(m), eu.localize_memorial(m)) for m in r["memorial"].split(" / "))
                       if r.get("memorial") and (r["memorial"] != r["name"] or clave_dia(r) in NOMBRES_EU) else "",
            "memoria_rango": rango_eu(r["memorial_rank"]) if r.get("memorial_rank") else "",
        },
    }


def volcar(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hoy", help="fecha de referencia AAAA-MM-DD (por defecto, hoy en Europe/Madrid)")
    ap.add_argument("--atras", type=int, default=DIAS_ATRAS)
    ap.add_argument("--adelante", type=int, default=DIAS_ADELANTE)
    ap.add_argument("--textos", type=Path, default=PROYECTO / "textos")
    ap.add_argument("--salida", type=Path, default=PROYECTO / "salida")
    ap.add_argument("--inventario", action="store_true", help="escribe faltan.txt con las piezas que faltan")
    a = ap.parse_args(argv)

    hoy = date.fromisoformat(a.hoy) if a.hoy else datetime.now(ZoneInfo("Europe/Madrid")).date()
    textos = cargar_textos(a.textos) if a.textos.exists() else {}
    dias_dir = a.salida / "dias"
    dias_dir.mkdir(parents=True, exist_ok=True)
    faltan: dict = {}
    indice, vigentes, partes_total, partes_falta, partes_prueba = {}, set(), 0, 0, 0
    for n in range(-a.atras, a.adelante + 1):
        d = hoy + timedelta(days=n)
        dia = generar_dia(d, textos, faltan)
        cuerpo = volcar(dia)
        (dias_dir / f"{d.isoformat()}.json").write_text(cuerpo, encoding="utf-8", newline="\n")
        vigentes.add(f"{d.isoformat()}.json")
        for c in dia["celebraciones"]:
            for partes in c["horas"].values():
                partes_total += len(partes)
                partes_falta += sum(1 for p in partes if "falta" in p)
                partes_prueba += sum(1 for p in partes if p.get("prueba"))
        c0 = dia["celebraciones"][0]
        indice[d.isoformat()] = {
            "nombre": c0["nombre_eu"], "rango": c0["rango"], "tiempo": dia["tiempo"], "color": dia["color"],
            "semana_salterio": dia["semana_salterio"], "huella": hashlib.sha1(cuerpo.encode()).hexdigest()[:12],
        }
    for viejo in dias_dir.glob("*.json"):            # lo que salió de la ventana se retira
        if viejo.name not in vigentes:
            viejo.unlink()
    (a.salida / "indice.json").write_text(
        volcar({"hoy": hoy.isoformat(), "desde": min(indice), "hasta": max(indice), "dias": indice}),
        encoding="utf-8", newline="\n")
    if a.inventario:
        lineas = [f"{clave}\t{len(propias)} variante(s) más propia(s)" for clave, propias in sorted(faltan.items())]
        (a.salida / "faltan.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(indice)} días ({min(indice)} a {max(indice)}) · {len(textos)} piezas de texto · "
          f"{partes_falta} de {partes_total} partes sin texto, {partes_prueba} con texto de prueba · "
          f"{len(faltan)} piezas mínimas por recibir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
