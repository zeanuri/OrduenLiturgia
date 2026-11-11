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
# 11-nov-2026), por `id`: {"nombre": …, "rango": …}. Lo que no está aquí lo traduce `eu`.
_NOMBRES = Path(__file__).with_name("nombres_eu.json")
NOMBRES_EU = json.loads(_NOMBRES.read_text(encoding="utf-8")) if _NOMBRES.exists() else {}


def nombre_eu(nombre_es: str, traducido: str) -> str:
    n = NOMBRES_EU.get(slug(nombre_es))
    return n["nombre"] if n else traducido


def rango_eu(nombre_es: str, rango_es: str) -> str:
    n = NOMBRES_EU.get(slug(nombre_es))
    return n["rango"] if n and n["rango"] else eu.localize_rank(rango_es)

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
    "invitatorio": ["fijo/invitatorio/apertura", "ant", "fijo/invitatorio/salmo95"],
}
# Parte que vale para todas las horas del día: se busca también sin la hora en la clave.
COMPARTIDAS = {"oracion"}


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
        opcionales.append({"nombre": mem, "rango": rango_mem, "opcional": True})
    elif mem:                                   # memoria obligatoria o fiesta: es la celebración
        principal = {"nombre": mem, "rango": rango_mem, "opcional": False}
    info["celebraciones"] = [principal, *opcionales]
    for c in info["celebraciones"]:
        c["tipo"] = tipo_de(c["rango"])
        c["id"] = slug(c["nombre"])
        # Nombre en euskera: el del día por `localize_name`; el de un santo, por `localize_memorial`.
        c["nombre_eu"] = nombre_eu(c["nombre"], eu.localize_name(c["nombre"]) if c["nombre"] == r["name"]
                                   else eu.localize_memorial(c["nombre"]))
        c["rango_eu"] = rango_eu(c["nombre"], c["rango"])
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


def candidatas(info: dict, cel: dict, hora: str, parte: str) -> list[str]:
    """Claves donde buscar `parte` de `hora`, de la más propia a la más general."""
    if parte.startswith("fijo/"):
        return [parte]
    tipo = cel["tipo"]
    dia = DIAS[info["fecha"].weekday()]
    hora_sal = "visperas1" if hora == "visperas1" and dia == "dom" else hora.replace("visperas1", "visperas")
    salterio = f"salterio/s{info['salterio']}/{dia}"
    propio = [f"propio/{cel['id']}"] + [f"comunes/{c}" for c in comunes_de(cel["nombre"])]
    tiempo = bases_del_tiempo(info)
    es_salmo = parte.startswith("salmo")

    if tipo in ("solemnidad", "fiesta"):
        bases = list(propio)
        if es_salmo or parte.startswith("ant") and parte != "ant_ev":
            # Sin salmodia propia: en Laudes, la del domingo de la semana I.
            bases.append("salterio/s1/dom" if hora == "laudes" else salterio)
    elif es_salmo:
        bases = [salterio]                       # ferias, domingos y memorias: salmos del salterio
    elif parte in ("ant1", "ant2", "ant3"):
        bases = tiempo + [salterio]
    elif tipo == "memoria":
        bases = propio + tiempo + [salterio]
    else:
        bases = tiempo + [salterio]

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


def componer(info: dict, cel: dict, hora: str, textos: dict, faltan: dict) -> list[dict]:
    partes = []
    for parte in ORDEN["visperas" if hora == "visperas1" else hora]:
        claves = candidatas(info, cel, hora, parte)
        clave, pieza = resolver(textos, claves)
        nombre = parte.split("/")[-1]
        if pieza is None:
            faltan.setdefault(claves[-1], set()).add(claves[0])
            partes.append({"parte": nombre, "falta": claves})
        else:
            partes.append({"parte": nombre, "clave": clave,
                           **{k: pieza[k] for k in ("titulo", "lineas", "prueba", "fuente", "batua") if k in pieza}})
    return partes


# ── El día ──────────────────────────────────────────────────────────────────

def tiene_primeras_visperas(info: dict) -> bool:
    tipo = info["celebraciones"][0]["tipo"]
    return tipo in ("solemnidad", "domingo") or (tipo == "fiesta" and info["fecha"].weekday() == 6)


def generar_dia(d: date, textos: dict, faltan: dict) -> dict:
    info, manana = dia_liturgico(d), dia_liturgico(d + timedelta(days=1))
    # Vísperas: las primeras de mañana solo si mañana las tiene y precede a hoy.
    primeras = tiene_primeras_visperas(manana) and manana["nivel"] < info["nivel"]
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
        celebraciones.append({
            "id": cel["id"], "nombre": cel["nombre"], "nombre_eu": cel["nombre_eu"],
            "rango": cel["rango"], "rango_eu": cel["rango_eu"], "opcional": cel["opcional"],
            "visperas_de": visperas_de, "horas": horas,
        })
    r = info["r"]
    return {
        "fecha": d.isoformat(), "dia_semana": DIAS[d.weekday()], "tiempo": info["tiempo"],
        "semana": info["semana"], "semana_salterio": info["salterio"], "ciclo_dominical": info["ciclo"],
        "color": r["color"], "celebraciones": celebraciones, "misa": WEB_MISA.format(d),
        # Cabecera del día en euskera, como la de lecturasdeldia.org/eu.
        "cabecera": {
            "nombre": nombre_eu(r["name"], eu.localize_name(r["name"])), "tiempo": eu.localize_season(r["season"]),
            "rango": rango_eu(r["name"], r["rank"]), "ciclo": eu.localize_sunday_cycle(r["sunday_cycle"]),
            "ciclo_ferial": eu.localize_weekday_cycle(r["weekday_cycle"]) if r.get("weekday_cycle") else "",
            "memoria": nombre_eu(r["memorial"], eu.localize_memorial(r["memorial"]))
                       if r.get("memorial") and r["memorial"] != r["name"] else "",
            "memoria_rango": rango_eu(r["memorial"], r["memorial_rank"]) if r.get("memorial_rank") else "",
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
