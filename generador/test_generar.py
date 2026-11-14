"""Pruebas del generador. Correr: py -3.14 -m pytest projects/OrduenLiturgia/generador -q"""
import json
import re
from datetime import date, timedelta

import pytest

import generar


@pytest.fixture(scope="module")
def textos_reales():
    return generar.cargar_textos(generar.PROYECTO / "textos")

# Semana del salterio de cada fecha, cotejada con la app oficial «Liturgia euskaraz»
# el 10-nov-2026.
SALTERIO_APP_OFICIAL = [
    ("2026-11-10", 4),   # Urtean Zeharreko XXXII. astea
    ("2026-11-29", 1),   # Abendualdiko I. astea
    ("2026-12-18", 3),
    ("2026-12-28", 1),   # Eguberri zortziurrena
    ("2027-01-02", 1),   # Agerkunde aurretik
    ("2027-01-04", 2),   # Agerkunde aurretik, tras el domingo
    ("2027-01-07", 2),   # Agerkunde ondoren
    ("2027-01-11", 1),   # Urtean Zeharreko I. astea
    ("2027-02-11", 4),   # Hausterre
    ("2027-03-22", 2),   # Aste Santua
    ("2027-04-06", 2),   # II. Pazko astea
]


@pytest.mark.parametrize("fecha,semana", SALTERIO_APP_OFICIAL)
def test_semana_salterio_coincide_con_la_app_oficial(fecha, semana):
    assert generar.dia_liturgico(date.fromisoformat(fecha))["salterio"] == semana


@pytest.mark.parametrize("fecha,cuales,de", [
    ("2026-11-14", "primeras", "XXXIII Domingo del Tiempo Ordinario"),          # sábado feria → domingo
    ("2026-11-15", "segundas", "XXXIII Domingo del Tiempo Ordinario"),          # domingo → lunes feria
    ("2026-11-21", "primeras", "Nuestro Señor Jesucristo, Rey del Universo"),   # sábado con memoria → solemnidad
    ("2026-12-07", "primeras", "La Inmaculada Concepción"),                     # lunes feria → solemnidad
    ("2026-11-10", "del dia", "San León Magno, papa y doctor"),                 # memoria obligatoria
    ("2027-03-27", "segundas", None),                                           # Sábado Santo: no hay primeras de Pascua
    ("2027-03-30", "segundas", "Martes de la Octava de Pascua"),                # octava: cada día las suyas
    ("2027-03-24", "del dia", "Miércoles Santo"),                               # no hay primeras del Jueves Santo
    ("2027-02-13", "primeras", "I Domingo de Cuaresma"),                        # sábado después de Ceniza (empate de nivel)
    ("2027-04-03", "primeras", "II Domingo de Pascua"),                         # sábado de la octava (empate de nivel)
])
def test_visperas_de_quien(fecha, cuales, de):
    dia = generar.generar_dia(date.fromisoformat(fecha), {}, {})
    v = dia["celebraciones"][0]["visperas_de"]
    assert v["cuales"] == cuales
    if de:
        assert v["de"] == de


def test_memoria_libre_sale_como_opcional_y_la_feria_como_principal():
    dia = generar.generar_dia(date(2026, 11, 16), {}, {})   # santa Margarita de Escocia / santa Gertrudis
    assert [c["opcional"] for c in dia["celebraciones"]] == [False, True, True]   # feria + una por santo
    assert dia["celebraciones"][0]["rango"] == "Feria"


def test_cadena_de_una_memoria_va_de_lo_propio_al_salterio():
    info = generar.dia_liturgico(date(2026, 11, 10))
    cel = info["celebraciones"][0]
    # Como «Liturgia euskaraz»: lo propio del santo y, si no, la feria (sin caer a los comunes).
    assert generar.candidatas(info, cel, "laudes", "himno") == [
        "propio/san-leon-magno-papa-y-doctor/laudes/himno",
        "salterio/s4/mar/laudes/himno",
    ]
    # Salmodia propia si el santo la tiene (San Martín); si no, la del salterio.
    assert generar.candidatas(info, cel, "laudes", "salmo1") == [
        "propio/san-leon-magno-papa-y-doctor/laudes/salmo1", "salterio/s4/mar/laudes/salmo1"]


def test_memoria_prefiere_el_comun_en_bizkaiera_a_la_feria_en_batua():
    info = generar.dia_liturgico(date(2026, 11, 10))
    cel = info["celebraciones"][0]
    textos = {"salterio/s4/mar/laudes/preces": {"batua": True, "lineas": [{"t": "texto", "x": "batua"}]},
              "comunes/doctores/laudes/preces": {"lineas": [{"t": "texto", "x": "bizkaiera"}]}}
    partes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert partes["preces"]["clave"] == "comunes/doctores/laudes/preces"
    # Lo propio del santo, aunque esté en batua, se queda.
    textos["propio/san-leon-magno-papa-y-doctor/laudes/preces"] = {"batua": True, "lineas": []}
    partes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert partes["preces"]["clave"] == "propio/san-leon-magno-papa-y-doctor/laudes/preces"


def test_partes_fijas_por_hora_y_tiempo():
    cuaresma = generar.dia_liturgico(date(2027, 2, 16))
    c = cuaresma["celebraciones"][0]
    assert generar.candidatas(cuaresma, c, "laudes", "fijo/apertura") == [
        "fijo/laudes/apertura-cuaresma", "fijo/laudes/apertura", "fijo/apertura"]
    octava = generar.dia_liturgico(date(2027, 3, 30))
    o = octava["celebraciones"][0]
    assert generar.candidatas(octava, o, "visperas", "fijo/conclusion") == [
        "fijo/visperas/conclusion-pascua", f"propio/{o['id']}/visperas/fijo/conclusion",
        "fijo/visperas/conclusion", "fijo/conclusion"]
    assert generar.candidatas(octava, o, "visperas1", "fijo/magnificat") == ["fijo/visperas/magnificat", "fijo/magnificat"]


def test_domingo_busca_antes_la_antifona_de_su_ciclo():
    info = generar.dia_liturgico(date(2027, 3, 7))          # IV domingo de Cuaresma, ciclo B
    cel = info["celebraciones"][0]
    claves = generar.candidatas(info, cel, "laudes", "ant_ev")
    assert claves[:2] == ["tiempo/cuaresma/s4/dom/laudes/ant_ev-B", "tiempo/cuaresma/s4/dom/laudes/ant_ev"]
    # Una feria no busca ciclo.
    info = generar.dia_liturgico(date(2027, 3, 8))
    assert not any(c.endswith("-B") for c in generar.candidatas(info, info["celebraciones"][0], "laudes", "ant_ev"))


def test_solemnidad_no_cae_al_salterio_salvo_la_salmodia():
    info = generar.dia_liturgico(date(2026, 12, 8))
    cel = info["celebraciones"][0]
    assert all(not c.startswith("salterio/") for c in generar.candidatas(info, cel, "laudes", "himno"))
    assert generar.candidatas(info, cel, "laudes", "salmo1")[-1] == "salterio/s1/dom/laudes/salmo1"


def test_texto_presente_se_incrusta_y_el_ausente_se_marca():
    textos = {
        "salterio/s4/mar/laudes/salmo1": {"ref": "salmos/101"},
        "salmos/101": {"titulo": "RELLENO", "lineas": [{"t": "texto", "x": "relleno"}]},
    }
    faltan: dict = {}
    dia = generar.generar_dia(date(2026, 11, 10), textos, faltan)
    partes = {p["parte"]: p for p in dia["celebraciones"][0]["horas"]["laudes"]}
    assert partes["salmo1"]["clave"] == "salterio/s4/mar/laudes/salmo1"
    assert partes["salmo1"]["lineas"] == [{"t": "texto", "x": "relleno"}]
    assert partes["himno"]["falta"][-1] == "salterio/s4/mar/laudes/himno"
    assert "salterio/s4/mar/laudes/himno" in faltan and "salterio/s4/mar/laudes/salmo1" not in faltan


def test_ventana_completa_e_indice(tmp_path):
    assert generar.main(["--hoy", "2026-11-10", "--salida", str(tmp_path), "--textos", str(tmp_path / "no"),
                         "--inventario"]) == 0
    dias = sorted(p.name for p in (tmp_path / "dias").glob("*.json"))
    assert len(dias) == 406 and dias[0] == "2026-10-01.json" and dias[-1] == "2027-11-10.json"
    indice = json.loads((tmp_path / "indice.json").read_text(encoding="utf-8"))
    assert indice["desde"] == "2026-10-01" and len(indice["dias"]) == 406
    hoy = json.loads((tmp_path / "dias" / "2026-11-10.json").read_text(encoding="utf-8"))
    assert hoy["misa"] == "https://lecturasdeldia.org/eu/2026/11/10/"
    assert [p["parte"] for p in hoy["celebraciones"][0]["horas"]["invitatorio"]] == ["apertura", "ant", "salmo"]
    # Al mover la ventana un día, el día que sale se retira.
    generar.main(["--hoy", "2026-11-11", "--salida", str(tmp_path), "--textos", str(tmp_path / "no")])
    assert not (tmp_path / "dias" / "2026-10-01.json").exists()


def test_cabecera_en_euskera_y_color_del_tiempo_como_lecturasdeldia():
    dia = generar.generar_dia(date(2026, 11, 10), {}, {})
    assert dia["color"] == "Verde"                                   # el del tiempo, no el del santo
    assert dia["cabecera"] == {
        # nombres y rangos de «Liturgia euskaraz» (generador/nombres_eu.json)
        "nombre": "Urtean Zeharreko hogeita hamabigarren asteko asteartea", "tiempo": "Urtean Zehar",
        "rango": "asteguna", "ciclo": "A zikloa", "ciclo_ferial": "II urtea",
        "memoria": "San Leon Handia, aita santua eta eliz irakaslea", "memoria_rango": "beharrezko oroipena",
    }
    assert dia["celebraciones"][0]["nombre_eu"] == "San Leon Handia, aita santua eta eliz irakaslea"
    solemnidad = generar.generar_dia(date(2026, 12, 8), {}, {})
    assert solemnidad["cabecera"]["nombre"] == "Maria Birjina Dohatsuaren Sortze Garbia" and solemnidad["cabecera"]["memoria"] == ""
    # Octava de Navidad: el motor llama a la feria como al santo; la feria lleva su nombre propio.
    octava = generar.generar_dia(date(2026, 12, 31), {}, {})
    assert octava["cabecera"]["nombre"] == "Eguberri-Zortziurreneko VII. eguna"
    assert octava["cabecera"]["memoria"] == "San Silvestre I.a, aita santua"


# ── Completas ───────────────────────────────────────────────────────────────

def noche(fecha: str) -> dict:
    d = date.fromisoformat(fecha)
    info, man = generar.dia_liturgico(d), generar.dia_liturgico(d + timedelta(days=1))
    return generar.formulario_completas(info, man, generar.primeras_visperas(info, man))


@pytest.mark.parametrize("fecha,f,primeras,solemnidad", [
    ("2026-11-10", 4, False, False),   # martes ordinario
    ("2026-11-14", 1, True, False),    # sábado: primeras de domingo
    ("2026-11-15", 2, False, False),   # domingo
    ("2026-12-07", 1, True, True),     # lunes, víspera de la Inmaculada: primeras de solemnidad
    ("2026-12-08", 2, False, True),    # solemnidad entre semana
    ("2026-11-02", 2, False, False),   # Difuntos: formulario 2 con la oración del domingo
    ("2027-03-24", 5, False, False),   # miércoles de Semana Santa: no hay primeras del Jueves Santo
    ("2027-03-25", 2, False, True),    # Jueves Santo
    ("2027-03-26", 2, False, True),    # Viernes Santo
    ("2027-03-27", 2, False, True),    # Sábado Santo: no son primeras de la Pascua
    ("2027-03-28", 2, False, False),   # domingo de Pascua
    ("2027-03-29", 1, False, False),   # lunes de la octava
    ("2027-03-30", 2, False, False),   # martes de la octava
    ("2027-03-31", 1, False, False),   # miércoles de la octava
    ("2027-04-03", 1, True, False),    # sábado de la octava
    ("2027-04-05", 2, False, True),    # Anunciación trasladada, en Pascua
    ("2027-04-20", 4, False, False),   # martes de Pascua
    ("2027-02-16", 4, False, False),   # martes de Cuaresma
])
def test_formulario_de_completas(fecha, f, primeras, solemnidad):
    n = noche(fecha)
    assert (n["f"], n["primeras"], n["solemnidad"]) == (f, primeras, solemnidad)


def test_completas_cadena_de_claves():
    n = noche("2026-11-10")                                                    # martes ordinario
    assert generar.candidatas_completas(n, "salmo1") == ["completas/f4/salmo1"]
    assert generar.candidatas_completas(n, "oracion") == ["completas/f4/oracion"]
    assert generar.candidatas_completas(n, "himno") == ["completas/f4/himno"]
    assert generar.candidatas_completas(n, "fijo/completas/maria") == ["fijo/completas/maria"]
    cuaresma = noche("2027-02-16")
    assert generar.candidatas_completas(cuaresma, "himno") == ["completas/f2/himno"]       # los dos himnos juntos
    assert generar.candidatas_completas(cuaresma, "fijo/apertura")[0] == "fijo/visperas/apertura-cuaresma"
    assert generar.candidatas_completas(noche("2026-11-14"), "fijo/apertura")[0] == "fijo/visperas/apertura"   # sin «Aleluia» solo en Cuaresma
    assert generar.candidatas_completas(noche("2027-03-25"), "responsorio") == [
        "completas/triduo/jue/responsorio", "completas/responsorio"]
    assert generar.candidatas_completas(noche("2027-03-25"), "oracion") == [
        "completas/solemnidad/oracion", "completas/f2/oracion"]
    pascua = noche("2027-03-31")
    assert generar.candidatas_completas(pascua, "responsorio") == [
        "completas/octava/responsorio", "completas/pascua/responsorio", "completas/responsorio"]
    assert generar.candidatas_completas(pascua, "salmo1") == ["completas/pascua/f1/salmo1", "completas/f1/salmo1"]
    assert generar.candidatas_completas(pascua, "fijo/completas/maria") == [
        "fijo/completas/maria-pascua", "fijo/completas/maria"]
    pascua_tarde = noche("2027-04-20")
    assert generar.candidatas_completas(pascua_tarde, "responsorio") == ["completas/pascua/responsorio", "completas/responsorio"]
    # Una noche de primeras usa el tiempo de mañana: el sábado antes del I domingo de Adviento es de Adviento.
    assert noche("2026-11-28")["tiempo"] == "adviento"


def test_completas_una_noche_de_un_salmo_no_tiene_ant2():
    claves = ["fijo/completas/examen", "fijo/completas/nunc-dimittis", "fijo/completas/conclusion",
              "fijo/completas/maria", "completas/ant_ev", "completas/responsorio", "completas/f4/himno",
              "completas/f4/ant1", "completas/f4/salmo1", "completas/f4/lectura", "completas/f4/oracion"]
    textos = {k: {"lineas": [{"t": "texto", "x": k}]} for k in claves}
    dia = generar.generar_dia(date(2026, 11, 10), textos, {})
    partes = [p["parte"] for p in dia["celebraciones"][0]["horas"]["completas"]]
    assert partes == ["apertura", "examen", "himno", "ant1", "salmo1", "lectura", "responsorio", "ant_ev",
                      "nunc-dimittis", "oracion", "conclusion", "maria"]
    assert dia["celebraciones"][0]["completas_de"]["cuales"] == "del dia"
    # El formulario 1 (sábado) sí tiene dos salmos, y es la primera Completas del domingo.
    sab = generar.generar_dia(date(2026, 11, 14), {}, {})
    assert [p["parte"] for p in sab["celebraciones"][0]["horas"]["completas"]].count("ant2") == 1
    assert sab["celebraciones"][0]["completas_de"]["cuales"] == "primeras"
    assert "XXXIII" in sab["celebraciones"][0]["completas_de"]["de"]
    # En Pascua el formulario 1 lleva una sola antífona (los dos salmos van juntos en salmo1).
    pas = generar.generar_dia(date(2027, 4, 3), {}, {})
    assert "ant2" not in [p["parte"] for p in pas["celebraciones"][0]["horas"]["completas"]]


# ── Invitatorio con los cuatro salmos ───────────────────────────────────────

def test_invitatorio_ofrece_los_salmos_que_existen():
    solo = {"fijo/invitatorio/salmo95": {"lineas": [{"t": "salmo", "x": "95"}], "batua": True},
            "fijo/invitatorio/salmo24": {"lineas": [{"t": "salmo", "x": "24"}]}}
    faltan: dict = {}
    dia = generar.generar_dia(date(2026, 11, 10), solo, faltan)
    inv = {p["parte"]: p for p in dia["celebraciones"][0]["horas"]["invitatorio"]}
    assert [o["n"] for o in inv["salmo"]["opciones"]] == ["95", "24"]
    assert inv["salmo"]["opciones"][0]["batua"] is True and inv["salmo"]["opciones"][1]["clave"] == "fijo/invitatorio/salmo24"
    assert "falta" in inv["ant"]                                   # la antífona sigue su cadena de siempre
    # Sin ninguno, la parte es una falta con las cuatro claves.
    vacio = generar.generar_dia(date(2026, 11, 10), {}, {})
    salmo = {p["parte"]: p for p in vacio["celebraciones"][0]["horas"]["invitatorio"]}["salmo"]
    assert salmo["falta"] == [f"fijo/invitatorio/salmo{n}" for n in ("95", "100", "67", "24")]


# ── Cabeceras de las partes, como «Liturgia euskaraz» ───────────────────────

def test_cabeceras_de_las_partes_como_liturgia_euskaraz():
    dia = generar.generar_dia(date(2026, 11, 13), {}, {})          # sin textos: la cabecera sale igual
    horas = dia["celebraciones"][0]["horas"]
    cab = lambda h: {p["parte"]: p.get("cabecera") for p in horas[h]}
    comunes = {"apertura": "Hasierako deia", "himno": "Gorazarrea", "ant1": "Salmoak", "salmo1": None, "ant2": None,
               "lectura": "Irakurgai laburra", "responsorio": "Galde-erantzuna", "ant_ev": "Ebanjelioko kantika",
               "preces": "Eskariak", "padrenuestro": "Jaunaren otoitza", "oracion": "Otoitza", "conclusion": "Amaiera"}
    for h, cantico in (("laudes", "benedictus"), ("visperas", "magnificat")):
        assert {k: cab(h)[k] for k in comunes} == comunes and cab(h)[cantico] is None
    assert not any(cab("invitatorio").values())                    # su «Hasierako txatala» va en la apertura
    c = cab("completas")                                           # viernes: un solo salmo
    assert (c["examen"], c["ant1"], c["maria"]) == (
        "Kontzientzia azterketa", "Salmoa", "Maria Birjina Dohatsuari azken kantuak")
    sab = generar.generar_dia(date(2026, 11, 14), {}, {})          # sábado: dos salmos
    assert {p["parte"]: p.get("cabecera") for p in sab["celebraciones"][0]["horas"]["completas"]}["ant1"] == "Salmoak"


def test_cabecera_no_se_repite_si_el_texto_ya_la_trae():
    t = lambda *ls: {"lineas": [{"t": a, "x": b} for a, b in ls]}
    textos = {"salterio/s4/vie/laudes/preces": t(("texto", "…"), ("titulo", "Jaunaren otoitza"), ("texto", "…")),
              "salterio/s4/vie/laudes/responsorio": t(("titulo", "Galde-erantzuna"), ("texto", "…")),
              "fijo/padrenuestro": t(("estrofa", "Gure Aita"))}
    dia = generar.generar_dia(date(2026, 11, 13), textos, {})
    horas = dia["celebraciones"][0]["horas"]
    lau = {p["parte"]: p for p in horas["laudes"]}
    assert "cabecera" not in lau["padrenuestro"] and "cabecera" not in lau["responsorio"]
    assert {p["parte"]: p for p in horas["visperas"]}["padrenuestro"]["cabecera"] == "Jaunaren otoitza"


def test_benedictus_y_magnificat_llevan_titulo_y_epigrafe():
    textos = generar.cargar_textos(generar.PROYECTO / "textos")
    for clave, titulo in (("fijo/laudes/benedictus", "Benedictus"), ("fijo/visperas/magnificat", "Magnificat")):
        ls = textos[clave]["lineas"]
        assert [l["t"] for l in ls[:4]] == ["salmo", "cita", "epigrafe", "estrofa"] and ls[0]["x"] == titulo


# ── Primeras Vísperas: Triduo y empates de nivel ────────────────────────────

def test_el_triduo_y_su_vispera_no_tienen_primeras_visperas():
    for año in range(2021, 2032):
        pascua = generar.liturgia.easter(año)
        # Miércoles Santo, Jueves, Viernes y Sábado Santo: cada noche reza las Vísperas de su propio día.
        for dias in (-4, -3, -2, -1):
            d = pascua + timedelta(days=dias)
            cel = generar.generar_dia(d, {}, {})["celebraciones"][0]
            assert cel["visperas_de"]["cuales"] != "primeras" and cel["visperas_de"]["de"] == cel["nombre"], d
        # Sábado después de Ceniza y sábado de la octava: primeras del domingo siguiente.
        ceniza = pascua - timedelta(days=46)
        for d, domingo in ((ceniza + timedelta(days=3), "I Domingo de Cuaresma"),
                           (pascua + timedelta(days=6), "II Domingo de Pascua")):
            v = generar.generar_dia(d, {}, {})["celebraciones"][0]["visperas_de"]
            assert (v["cuales"], v["de"]) == ("primeras", domingo), d


def test_las_tres_noches_corregidas_no_dejan_partes_vacias_por_la_eleccion(textos_reales):
    for fecha in ("2027-03-24", "2027-02-13", "2027-04-03"):
        dia = generar.generar_dia(date.fromisoformat(fecha), textos_reales, {})
        faltas = [p["parte"] for p in dia["celebraciones"][0]["horas"]["visperas"] if "falta" in p]
        assert faltas == [], (fecha, faltas)


# ── Salmos propios del tiempo ───────────────────────────────────────────────

def salmo(dia, hora, parte, cel=0):
    p = {p["parte"]: p for p in dia["celebraciones"][cel]["horas"][hora]}[parte]
    titulo = next(l["x"] for l in p["lineas"] if l["t"] == "salmo")
    return p["clave"], int(re.search(r"\d+", titulo).group())


def test_ceniza_y_ii_domingo_de_pascua_rezan_sus_salmos_propios(textos_reales):
    # «Liturgia euskaraz»: Ceniza, salmos 50 y 99; II de Pascua, 62 y 149.
    ceniza = generar.generar_dia(date(2027, 2, 10), textos_reales, {})
    assert salmo(ceniza, "laudes", "salmo1") == ("tiempo/cuaresma/ceniza/mie/laudes/salmo1", 50)
    assert salmo(ceniza, "laudes", "salmo3") == ("tiempo/cuaresma/ceniza/mie/laudes/salmo3", 99)
    pascua = generar.generar_dia(date(2027, 4, 4), textos_reales, {})
    assert salmo(pascua, "laudes", "salmo1") == ("tiempo/pascua/s2/dom/laudes/salmo1", 62)
    assert salmo(pascua, "laudes", "salmo3") == ("tiempo/pascua/s2/dom/laudes/salmo3", 149)
    # La antífona sale de la misma carpeta que su salmo.
    for dia, base in ((ceniza, "tiempo/cuaresma/ceniza/mie"), (pascua, "tiempo/pascua/s2/dom")):
        partes = {p["parte"]: p for p in dia["celebraciones"][0]["horas"]["laudes"]}
        assert partes["ant1"]["clave"].startswith(base) and partes["salmo1"]["clave"].startswith(base)


def test_octava_de_navidad_reza_la_salmodia_del_domingo_i(textos_reales):
    for fecha in ("2026-12-29", "2026-12-30", "2026-12-31"):
        dia = generar.generar_dia(date.fromisoformat(fecha), textos_reales, {})
        for cel in range(len(dia["celebraciones"])):          # la feria y, si la hay, la memoria libre
            assert salmo(dia, "laudes", "salmo1", cel) == ("tiempo/navidad/comun/laudes/salmo1", 62), (fecha, cel)
            assert salmo(dia, "laudes", "salmo3", cel) == ("tiempo/navidad/comun/laudes/salmo3", 149), (fecha, cel)
    # También las Vísperas del 29 y el 30.
    for fecha in ("2026-12-29", "2026-12-30"):
        dia = generar.generar_dia(date.fromisoformat(fecha), textos_reales, {})
        assert salmo(dia, "visperas", "salmo1")[0] == "tiempo/navidad/comun/visperas/salmo1"
        assert salmo(dia, "visperas", "salmo2") == ("tiempo/navidad/comun/visperas/salmo2", 129)
    # Las antífonas siguen siendo las propias del día.
    dia = generar.generar_dia(date(2026, 12, 30), textos_reales, {})
    laudes = {p["parte"]: p for p in dia["celebraciones"][0]["horas"]["laudes"]}
    assert laudes["ant1"]["clave"] == "tiempo/navidad/12-30/laudes/ant1"


def test_los_salmos_del_tiempo_no_invaden_lo_que_reza_el_salterio(textos_reales):
    # Del 2 al 5 de enero y en las ferias de Adviento 17-24 el blog escribe los salmos por fecha (con los de
    # otro día de la semana): no valen, y salen los salmos del salterio (aunque sea su copia del tiempo).
    for fecha in ("2027-01-04", "2026-12-21", "2026-12-22", "2027-01-12"):
        d = date.fromisoformat(fecha)
        dia = generar.generar_dia(d, textos_reales, {})
        sal = f"salterio/s{generar.dia_liturgico(d)['salterio']}/{generar.DIAS[d.weekday()]}"
        for hora in ("laudes", "visperas"):
            for p in dia["celebraciones"][0]["horas"][hora]:
                if p["parte"].startswith("salmo"):
                    esperado = generar.resolver(textos_reales, [f"{sal}/{hora}/{p['parte']}"])[1]
                    assert generar.mismo_salmo(p, esperado), (fecha, hora, p["clave"])
    # Ninguna cadena de salmos de la ventana lleva una carpeta de fecha ni la salmodia común de Navidad fuera de diciembre.
    for n in range(-40, 366):
        d = date(2026, 11, 13) + timedelta(days=n)
        info = generar.dia_liturgico(d)
        for cel in info["celebraciones"]:
            for hora in ("laudes", "visperas"):
                for parte in ("salmo1", "salmo2", "salmo3"):
                    for clave in generar.candidatas(info, cel, hora, parte):
                        assert not re.search(r"/\d\d-\d\d/", clave), (d, clave)
                        assert not (clave.startswith("tiempo/navidad/comun/") and d.month != 12), (d, clave)


def test_cadena_de_salmos_de_feria_y_memoria_pasa_por_el_tiempo():
    info = generar.dia_liturgico(date(2027, 2, 10))                  # Miércoles de Ceniza
    assert generar.candidatas(info, info["celebraciones"][0], "laudes", "salmo1") == [
        "tiempo/cuaresma/ceniza/mie/laudes/salmo1", "tiempo/cuaresma/comun/laudes/salmo1", "salterio/s4/mie/laudes/salmo1"]
    info = generar.dia_liturgico(date(2026, 12, 29))                 # memoria libre de Becket en la octava
    assert generar.candidatas(info, info["celebraciones"][1], "laudes", "salmo1") == [
        "propio/santo-tomas-becket-obispo-y-martir/laudes/salmo1",
        "tiempo/navidad/comun/laudes/salmo1", "salterio/s1/mar/laudes/salmo1"]


def test_el_bizkaiera_del_salterio_manda_sobre_el_mismo_salmo_en_batua_del_tiempo():
    pieza = lambda titulo, **k: {"lineas": [{"t": "salmo", "x": titulo}], **k}
    info = generar.dia_liturgico(date(2027, 3, 23))                  # Martes Santo
    cel = info["celebraciones"][0]
    textos = {"tiempo/semana-santa/mar/laudes/salmo3": pieza("65. [64] Salmoa", batua=True),
              "salterio/s2/mar/laudes/salmo3": pieza("64 Salmoa")}
    laudes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert laudes["salmo3"]["clave"] == "salterio/s2/mar/laudes/salmo3"          # mismo salmo: el bizkaiera
    textos["tiempo/semana-santa/mar/laudes/salmo3"] = pieza("97. [96] Salmoa", batua=True)
    laudes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert laudes["salmo3"]["clave"] == "tiempo/semana-santa/mar/laudes/salmo3"  # otro salmo: el del tiempo
    textos["tiempo/semana-santa/mar/laudes/salmo3"] = pieza("97. [96] Salmoa")   # en bizkaiera: el del tiempo
    laudes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert laudes["salmo3"]["clave"] == "tiempo/semana-santa/mar/laudes/salmo3"


# ── Identidad de la feria y de la memoria libre ─────────────────────────────

@pytest.mark.parametrize("fecha,feria,santo", [
    ("2026-12-29", "santo-tomas-becket-obispo-y-martir-feria", "santo-tomas-becket-obispo-y-martir"),
    ("2026-12-31", "san-silvestre-i-papa-feria", "san-silvestre-i-papa"),
])
def test_la_feria_de_la_octava_tiene_id_propio(fecha, feria, santo):
    dia = generar.generar_dia(date.fromisoformat(fecha), {}, {})
    assert [(c["id"], c["opcional"]) for c in dia["celebraciones"]] == [(feria, False), (santo, True)]
    assert dia["celebraciones"][0]["nombre_eu"].startswith("Eguberri-Zortziurreneko ")      # el nombre no cambia
    # El `id` de la feria no cambia qué textos resuelve: no entra en sus cadenas de claves.
    info = generar.dia_liturgico(date.fromisoformat(fecha))
    cel = info["celebraciones"][0]
    sin_sufijo = {**cel, "id": santo}
    for hora in ("laudes", "visperas"):
        for parte in generar.ORDEN[hora]:
            assert generar.candidatas(info, cel, hora, parte) == generar.candidatas(info, sin_sufijo, hora, parte)


def test_santos_alternativos_son_una_celebracion_opcional_cada_uno(textos_reales):
    """«San Beda / San Gregorio VII / Santa M. Magdalena de Pazzi» (el motor los da en una cadena) se elige
    uno: feria y tres opcionales, cada una con su id, su nombre y sus textos."""
    dia = generar.generar_dia(date(2027, 5, 25), textos_reales, {})
    cels = dia["celebraciones"]
    assert [c["opcional"] for c in cels] == [False, True, True, True]
    assert [c["id"] for c in cels[1:]] == ["san-beda-el-venerable", "san-gregorio-vii", "santa-m-magdalena-de-pazzi"]
    assert len({c["id"] for c in cels}) == 4
    assert not any(" / " in c["nombre"] for c in cels)
    # La oración de cada santo es la suya: la de Beda solo está en la celebración de Beda.
    def oracion(c):
        p = next(p for p in c["horas"]["laudes"] if p["parte"] == "oracion")
        return p["clave"], " ".join(l["x"] for l in p["lineas"])
    claves = {c["id"]: oracion(c) for c in cels[1:]}
    for santo, (clave, texto) in claves.items():
        assert clave == f"propio/{santo}/laudes/oracion"
    assert "Beda" in claves["san-beda-el-venerable"][1]
    assert "Gregorio" in claves["san-gregorio-vii"][1]
    assert "Pazzi" in claves["santa-m-magdalena-de-pazzi"][1]
    for santo, (_, texto) in claves.items():
        assert ("Beda" in texto) == (santo == "san-beda-el-venerable"), santo
    # Y la feria no se lleva ninguna oración de santo.
    assert not any(l["x"].count("Beda") for p in cels[0]["horas"]["laudes"] for l in p.get("lineas", []))


def test_una_celebracion_conjunta_no_se_parte():
    """Solo se parte por « / »: «Santos Juan Fisher y Tomás Moro» es UNA celebración (de dos mártires)."""
    dia = generar.generar_dia(date(2027, 6, 22), {}, {})   # San Paulino de Nola / Santos Juan Fisher y Tomás Moro
    assert [c["nombre"] for c in dia["celebraciones"][1:]] == ["San Paulino de Nola", "Santos Juan Fisher y Tomás Moro"]
    assert [c["id"] for c in dia["celebraciones"][1:]] == ["san-paulino-de-nola", "santos-juan-fisher-y-tomas-moro"]
    dia = generar.generar_dia(date(2026, 10, 19), {}, {})  # Santos Juan de Brébeuf, Isaac Jogues y compañeros / San Pablo de la Cruz
    assert [c["nombre"] for c in dia["celebraciones"][1:]] == [
        "Santos Juan de Brébeuf, Isaac Jogues y compañeros", "San Pablo de la Cruz"]


def test_las_16_fechas_de_santos_alternativos_de_la_ventana():
    """Cada fecha con «A / B» da feria + un opcional por santo, sin «/» en los nombres ni ids repetidos, y la
    cabecera del día (memoria) sigue juntando sus nombres en euskera con « / »."""
    fechas = [d for d in (date(2026, 11, 13) + timedelta(days=n) for n in range(-40, 366))
              if " / " in (generar.liturgia.calculate(d).get("memorial") or "")]
    assert len(fechas) == 16
    for d in fechas:
        todas = generar.dia_liturgico(d)["celebraciones"]
        # Si el día es sábado de Tiempo Ordinario, a los santos se añade Santa María en sábado (no alterna con ellos).
        cels = [c for c in todas if c["id"] != "santa-maria-en-sabado"]
        mem = generar.liturgia.calculate(d)["memorial"]
        assert [c["nombre"] for c in cels[1:]] == mem.split(" / ")
        assert all(c["opcional"] and c["alterna"] and c["rango"] == "Memoria Libre" for c in cels[1:])
        assert len({c["id"] for c in todas}) == len(todas)
        assert generar.generar_dia(d, {}, {})["cabecera"]["memoria"].count(" / ") == len(todas) - 2


def test_ningun_dia_de_la_ventana_repite_id():
    for n in range(-40, 366):
        d = date(2026, 11, 13) + timedelta(days=n)
        ids = [c["id"] for c in generar.dia_liturgico(d)["celebraciones"]]
        assert len(ids) == len(set(ids)), (d, ids)


def test_cantico_de_visperas_dominical_en_cuaresma_y_adviento():
    """En Cuaresma el cántico de las II Vísperas del domingo es 1 Pe 2 (el del salterio, Ap 19, lleva
    «Alleluia»): aunque solo esté en batua, no lo desplaza el del salterio. En Adviento es el mismo
    cántico (Ap 19) y manda el bizkaiera del salterio."""
    textos = generar.cargar_textos(generar.PROYECTO / "textos")
    def salmo3(fecha):
        dia = generar.generar_dia(date.fromisoformat(fecha), textos, {})
        return next(p for p in dia["celebraciones"][0]["horas"]["visperas"] if p["parte"] == "salmo3")
    for fecha in ("2027-02-14", "2027-02-21", "2027-03-14"):
        p = salmo3(fecha)
        assert p["clave"].startswith("tiempo/cuaresma/"), (fecha, p["clave"])
        cabeza = " / ".join(l["x"] for l in p["lineas"][:2])        # batua: título y cita; bizkaiera: «Kantika: Ik 1 Pe 2…»
        assert "1 Pe 2" in cabeza, (fecha, cabeza)
    assert salmo3("2026-12-13")["clave"].startswith("salterio/")


# ── Himnos escritos en la entrada, primeras Vísperas del XXXIII, Inmaculada y Presentación (13-nov-2026) ──

def parte(dia, hora, nombre, cel=0):
    return next(p for p in dia["celebraciones"][cel]["horas"][hora] if p["parte"] == nombre)


def test_el_himno_que_la_entrada_trae_escrito_no_se_pierde(textos_reales):
    """Laudes del Pilar: el blog enlaza «Goratzarrea» a una página sin ancla, pero trae el himno escrito."""
    dia = generar.generar_dia(date(2026, 10, 12), textos_reales, {})
    himno = parte(dia, "laudes", "himno")
    assert "falta" not in himno
    assert himno["clave"] == "propio/nuestra-senora-del-pilar/laudes/himno"
    assert himno["lineas"][0]["x"].startswith("Agur, Jainkoaren\nAma maite ederra")
    assert not himno.get("batua")


def test_primeras_visperas_del_xxxiii_llevan_la_antifona_del_ciclo_y_no_el_marcador(textos_reales):
    # El 14-nov-2026 (ciclo A) y el 13-nov-2027 (ciclo B): antes salía «⇒Domekakoa», el marcador del salterio.
    for fecha, ciclo, empieza in (("2026-11-14", "A", "Badaukanari emon egingo jako"),
                                  ("2027-11-13", "B", "Zeru-lurrak igaroko dira")):
        dia = generar.generar_dia(date.fromisoformat(fecha), textos_reales, {})
        assert dia["celebraciones"][0]["visperas_de"]["cuales"] == "primeras"
        ant = parte(dia, "visperas", "ant_ev")
        assert ant["clave"] == f"tiempo/ordinario/dom33/visperas1/ant_ev-{ciclo}", fecha
        assert ant["lineas"][0]["x"].startswith(empieza), fecha
        assert not any("⇒" in l["x"] for l in ant["lineas"]), fecha


def test_ningun_dia_de_la_ventana_saca_el_marcador_del_salterio_ni_el_del_comun_como_texto(textos_reales):
    """«⇒Domekakoa» (antífona del Magníficat de las primeras Vísperas del domingo) y «Salmoak eta Kantika,
    astearen egunekoak.» (el marcador de comunes/doctores en lugar del salmo 62) no salen como texto litúrgico."""
    for n in range(-40, 366):
        dia = generar.generar_dia(date(2026, 11, 13) + timedelta(days=n), textos_reales, {})
        for c in dia["celebraciones"]:
            for hora, partes in c["horas"].items():
                for p in partes:
                    if p["parte"].startswith(("ant", "salmo")):
                        for l in p.get("lineas") or []:
                            assert "⇒" not in l["x"] and "astearen egunekoak" not in l["x"], (dia["fecha"], hora, p["parte"])


def test_inmaculada_primeras_visperas_del_blog_y_segundas_de_la_referencia(textos_reales):
    # Primeras (7-dic): la entrada del blog, que no lleva marca I/II, es la de las primeras (antífonas, 147,
    # lectura, responsorio, Magníficat) y entra entera, con su salmo 112 y su cántico Ef 1 (la salmodia del común
    # de Santa María), aunque la referencia (P1874) da 147 [146] 1-11 y Ap 19: aquí manda el bizkaiera del autor.
    # Segundas (8-dic): la referencia, salmos 121 y 126 (el bizkaiera de la Asunción, por remisión) y cántico Ef 1.
    primeras = generar.generar_dia(date(2026, 12, 7), textos_reales, {})
    v = primeras["celebraciones"][0]["visperas_de"]
    assert (v["cuales"], v["de"]) == ("primeras", "La Inmaculada Concepción")
    assert salmo(primeras, "visperas", "salmo1") == ("propio/la-inmaculada-concepcion/visperas1/salmo1", 112)
    assert salmo(primeras, "visperas", "salmo2") == ("propio/la-inmaculada-concepcion/visperas1/salmo2", 147)
    assert "Ef 1" in parte(primeras, "visperas", "salmo3")["lineas"][0]["x"]
    assert parte(primeras, "visperas", "ant1")["lineas"][0]["x"].startswith("Hasarrea sortuko dot")
    assert parte(primeras, "visperas", "ant_ev")["lineas"][0]["x"].startswith("Dohatsu deituko nabe")
    assert not [p for p in primeras["celebraciones"][0]["horas"]["visperas"] if "falta" in p]
    segundas = generar.generar_dia(date(2026, 12, 8), textos_reales, {})
    assert segundas["celebraciones"][0]["visperas_de"]["cuales"] == "segundas"
    assert salmo(segundas, "visperas", "salmo1") == ("propio/la-inmaculada-concepcion/visperas/salmo1", 121)
    assert salmo(segundas, "visperas", "salmo2") == ("propio/la-inmaculada-concepcion/visperas/salmo2", 126)
    assert "Ef 1" in parte(segundas, "visperas", "salmo3")["lineas"][0]["x"]
    assert parte(segundas, "visperas", "ant1")["lineas"][0]["x"].startswith("Guztiz ederra zara")
    assert not [p for p in segundas["celebraciones"][0]["horas"]["visperas"] if "falta" in p]


def test_presentacion_reza_en_laudes_la_salmodia_del_domingo_i_con_sus_antifonas_propias(textos_reales):
    dia = generar.generar_dia(date(2027, 2, 2), textos_reales, {})
    assert salmo(dia, "laudes", "salmo1")[1] == 62
    assert "57-88. 56" in parte(dia, "laudes", "salmo2")["lineas"][0]["x"]
    assert salmo(dia, "laudes", "salmo3")[1] == 149
    for n in (1, 2, 3):
        assert parte(dia, "laudes", f"ant{n}")["clave"] == f"propio/la-presentacion-del-senor/laudes/ant{n}"


# ── Oración propia que solo existe en castellano ────────────────────────────
# «Liturgia euskaraz» da a esas memorias su oración (en castellano, que no entra: `referencia/batua.py` la
# anota en `sin_euskera.json`). La feria ni el común la sustituyen: sería otra oración bajo el nombre del santo.

def oracion(dia, hora, cel=0):
    return {p["parte"]: p for p in dia["celebraciones"][cel]["horas"][hora]}["oracion"]


def test_memoria_con_oracion_propia_sin_euskera_no_reza_la_de_la_feria_ni_la_del_comun(monkeypatch):
    info = generar.dia_liturgico(date(2026, 11, 10))
    cel = info["celebraciones"][0]                       # San León Magno, memoria obligatoria
    propia = "propio/san-leon-magno-papa-y-doctor/laudes/oracion"
    textos = {"salterio/s4/mar/laudes/oracion": {"lineas": [{"t": "texto", "x": "feria"}]},
              "comunes/doctores/laudes/oracion": {"lineas": [{"t": "texto", "x": "común"}]}}
    faltan = {}
    monkeypatch.setattr(generar, "SIN_EUSKERA", {propia: "O0001"})
    p = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, faltan)}["oracion"]
    assert "clave" not in p and p["falta"] == [propia]
    assert faltan[propia] == {propia}
    # Solo la oración y solo esa hora: las demás partes siguen siendo las de la feria.
    textos["salterio/s4/mar/laudes/himno"] = {"lineas": [{"t": "texto", "x": "himno de feria"}]}
    partes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert partes["himno"]["clave"] == "salterio/s4/mar/laudes/himno"
    textos["salterio/s4/mar/visperas/oracion"] = {"lineas": [{"t": "texto", "x": "feria"}]}
    partes = {p["parte"]: p for p in generar.componer(info, cel, "visperas", textos, {})}
    assert partes["oracion"]["clave"] == "salterio/s4/mar/visperas/oracion"
    # Sin la anotación, o con el texto propio ya en euskera, nada cambia.
    monkeypatch.setattr(generar, "SIN_EUSKERA", {})
    partes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert partes["oracion"]["clave"] == "salterio/s4/mar/laudes/oracion"
    monkeypatch.setattr(generar, "SIN_EUSKERA", {propia: "O0001"})
    textos[propia] = {"batua": True, "lineas": [{"t": "texto", "x": "propia"}]}
    partes = {p["parte"]: p for p in generar.componer(info, cel, "laudes", textos, {})}
    assert partes["oracion"]["clave"] == propia


def test_san_oscar_no_reza_la_oracion_de_la_feria(textos_reales):
    dia = generar.generar_dia(date(2027, 2, 3), textos_reales, {})
    santo = next(i for i, c in enumerate(dia["celebraciones"]) if c["id"] == "san-oscar")
    for hora in ("laudes", "visperas"):
        p = oracion(dia, hora, santo)
        assert "clave" not in p and p["falta"] == [f"propio/san-oscar/{hora}/oracion"], hora
    # La feria del mismo día sí reza la suya.
    assert oracion(dia, "laudes", 0)["clave"].startswith("salterio/")


def test_san_calixto_reza_en_laudes_su_oracion_en_euskera(textos_reales):
    # El servidor de «Liturgia euskaraz» da en 2026 las Laudes con la oración de la feria; en 2021-2025 (y
    # en sus Vísperas de 2026) la del santo, en euskera: `llaves.subir` ya no deja que la feria la tape.
    dia = generar.generar_dia(date(2026, 10, 14), textos_reales, {})
    santo = next(i for i, c in enumerate(dia["celebraciones"]) if c["id"] == "san-calixto-i-papa-y-martir")
    assert oracion(dia, "laudes", santo)["clave"] == "propio/san-calixto-i-papa-y-martir/laudes/oracion"
    assert oracion(dia, "visperas", santo)["clave"] == "propio/san-calixto-i-papa-y-martir/visperas/oracion"
    assert oracion(dia, "laudes", santo)["lineas"]


def test_octava_de_navidad_el_santo_conmemorado_reza_la_oracion_del_dia(textos_reales):
    # Santo Tomás Becket (29-dic): en la octava solo se conmemora (su «oración» en el servidor es la rúbrica
    # de la conmemoración, en castellano); la oración del día es la de la octava y no falta.
    dia = generar.generar_dia(date(2026, 12, 29), textos_reales, {})
    santo = next(i for i, c in enumerate(dia["celebraciones"]) if c["id"] == "santo-tomas-becket-obispo-y-martir")
    assert oracion(dia, "laudes", santo)["clave"] == "tiempo/navidad/12-29/laudes/oracion"
    assert "propio/santo-tomas-becket-obispo-y-martir/laudes/oracion" not in generar.SIN_EUSKERA


def test_sin_euskera_json_solo_anota_oraciones_propias_sin_texto(textos_reales):
    assert generar.SIN_EUSKERA, "falta repo/generador/sin_euskera.json (referencia/batua.py)"
    for clave in generar.SIN_EUSKERA:
        assert re.fullmatch(r"propio/[a-z0-9-]+/(laudes|visperas|visperas1)/oracion", clave), clave
        assert clave not in textos_reales, f"{clave} ya tiene texto"


def test_ninguna_memoria_de_la_ventana_reza_la_feria_donde_el_santo_tiene_oracion_propia(textos_reales):
    anotadas, vistas = 0, 0
    hoy = date(2026, 11, 14)
    for n in range(-generar.DIAS_ATRAS, generar.DIAS_ADELANTE + 1):
        dia = generar.generar_dia(hoy + timedelta(days=n), textos_reales, {})
        for cel in dia["celebraciones"]:
            if not cel["rango"].startswith("Memoria"):
                continue
            for hora in ("laudes", "visperas"):
                if hora == "visperas" and cel["visperas_de"]["cuales"] == "primeras":
                    continue
                p = {p["parte"]: p for p in cel["horas"][hora]}["oracion"]
                propia = f"propio/{cel['id']}/{hora}/oracion"
                vistas += 1
                if propia in generar.SIN_EUSKERA:
                    anotadas += 1
                    assert "clave" not in p, (dia["fecha"], propia, p.get("clave"))
    assert anotadas > 50 and vistas > anotadas       # hay casos reales y la regla no alcanza a todas las memorias


def test_llaves_oracion_propia_no_se_pierde_porque_el_ultimo_ano_traiga_la_de_la_feria():
    # `referencia/llaves.py` no está en el repositorio público: la prueba solo corre en el clon de ZClaude.
    ref = generar.PROYECTO.parent / "referencia"
    if not (ref / "llaves.py").exists():
        pytest.skip("sin referencia/")
    import sys
    sys.path.insert(0, str(ref))
    import llaves

    def occ(fecha, firma, papel, feria=False):
        cadena = [f"propio/x/laudes/{papel}", f"salterio/s4/mie/laudes/{papel}"]
        return {"fecha": fecha, "llave": "x", "hora": "laudes", "papel": papel, "u": firma, "firma": firma,
                "cadena": cadena[1:] if feria else cadena, "feria": feria}
    for papel, se_pierde in (("oracion", False), ("himno", True)):   # el himno sigue la regla del año más reciente
        lista = [occ("2026-10-14", "FERIA", papel, feria=True),
                 occ("2025-10-14", "SANTO", papel), occ("2026-10-14", "FERIA", papel)]
        llaves.subir(lista)
        assert lista[1]["de_feria"] is se_pierde, papel
        assert lista[2]["de_feria"] is True


# ── Santa María en sábado (memoria libre; decisión del usuario, 14-nov-2026) ──

SM = "santa-maria-en-sabado"
# Los 26 sábados de la ventana (hoy = 2026-11-13) que la ofrecen: sábado de Tiempo Ordinario sin memoria
# obligatoria, fiesta ni solemnidad. Los 8 primeros, hasta enero, los sirve también «Liturgia euskaraz».
SABADOS_SANTA_MARIA = [
    "2026-10-10", "2026-10-24", "2026-10-31", "2026-11-07", "2026-11-14", "2026-11-28", "2027-01-16", "2027-01-30",
    "2027-05-22", "2027-05-29", "2027-06-12", "2027-06-19", "2027-06-26", "2027-07-10", "2027-07-17", "2027-07-24",
    "2027-08-07", "2027-09-04", "2027-09-11", "2027-09-18", "2027-09-25", "2027-10-09", "2027-10-16", "2027-10-23",
    "2027-10-30", "2027-11-13"]


def ids_del_dia(fecha: str) -> list[str]:
    return [c["id"] for c in generar.dia_liturgico(date.fromisoformat(fecha))["celebraciones"]]


@pytest.mark.parametrize("fecha", ["2026-11-14", "2026-11-28"])
def test_santa_maria_en_sabado_es_una_celebracion_opcional_con_su_laudes(textos_reales, fecha):
    dia = generar.generar_dia(date.fromisoformat(fecha), textos_reales, {})
    feria, sm = dia["celebraciones"][0], dia["celebraciones"][-1]
    assert [c["id"] for c in dia["celebraciones"]] == [feria["id"], SM]
    assert (sm["nombre"], sm["rango"], sm["opcional"]) == ("Santa María en sábado", "Memoria Libre", True)
    assert sm["nombre_eu"] == "Maria Birjina Dohatsuaren oroipena larunbatean" and sm["rango_eu"] == "nahierazko oroipena"
    # Laudes: el himno, la lectura breve, el responsorio, la antífona del Benedictus y la oración, los suyos.
    for nombre in ("himno", "lectura", "responsorio", "ant_ev", "oracion"):
        assert parte(dia, "laudes", nombre, -1)["clave"] == f"propio/{SM}/laudes/{nombre}", nombre
    assert parte(dia, "invitatorio", "ant", -1)["clave"] == f"propio/{SM}/invitatorio/ant"
    # La salmodia es la de la feria (salterio del sábado), y las Vísperas y las Completas son las del día.
    for nombre in ("ant1", "salmo1", "salmo2", "salmo3"):
        assert parte(dia, "laudes", nombre, -1)["clave"] == parte(dia, "laudes", nombre, 0)["clave"], nombre
    assert sm["horas"]["visperas"] == feria["horas"]["visperas"] and sm["horas"]["completas"] == feria["horas"]["completas"]
    assert sm["visperas_de"]["cuales"] == "primeras"
    # La cabecera del día la anuncia como a un santo de memoria libre.
    assert dia["cabecera"]["memoria"] == sm["nombre_eu"] and dia["cabecera"]["memoria_rango"] == "nahierazko oroipena"
    # Y la de la feria no se lleva nada de ella.
    assert not any(SM in p.get("clave", "") for h in ("invitatorio", "laudes", "visperas") for p in feria["horas"][h])


def test_santa_maria_en_sabado_sale_junto_a_los_santos_de_memoria_libre(textos_reales):
    dia = generar.generar_dia(date(2026, 10, 24), textos_reales, {})      # San Antonio María Claret
    assert [c["id"] for c in dia["celebraciones"]][1:] == ["san-antonio-maria-claret", SM]
    assert [c["opcional"] for c in dia["celebraciones"]] == [False, True, True]
    assert dia["cabecera"]["memoria"] == "San Antonio Maria Claret, gotzaina / Maria Birjina Dohatsuaren oroipena larunbatean"
    assert dia["cabecera"]["memoria_rango"] == "nahierazko oroipena"
    # Claret no se lleva las piezas de Santa María en sábado (el emparejamiento de la referencia las confundía).
    claret = dia["celebraciones"][1]
    assert not any(SM in p.get("clave", "") for h in ("invitatorio", "laudes") for p in claret["horas"][h])
    assert parte(dia, "laudes", "himno", 2)["clave"] == f"propio/{SM}/laudes/himno"


def test_santa_maria_en_sabado_solo_en_sabados_de_tiempo_ordinario_sin_memoria_obligatoria_fiesta_ni_solemnidad():
    hoy = date(2026, 11, 13)
    con = [d.isoformat() for d in (hoy + timedelta(days=n) for n in range(-generar.DIAS_ATRAS, generar.DIAS_ADELANTE + 1))
           if SM in ids_del_dia(d.isoformat())]
    assert con == SABADOS_SANTA_MARIA
    assert ids_del_dia("2026-11-21") == ["presentacion-de-la-virgen-maria"]            # memoria obligatoria
    assert ids_del_dia("2027-07-03") == ["santo-tomas-apostol"]                       # fiesta
    assert ids_del_dia("2028-06-24") == ["natividad-de-san-juan-bautista"]            # solemnidad
    for fecha in ("2026-12-05", "2027-02-20", "2027-01-02", "2027-03-27", "2027-04-17"):   # Adviento, Cuaresma, Navidad, Triduo, Pascua
        assert SM not in ids_del_dia(fecha), fecha
        assert date.fromisoformat(fecha).weekday() == 5
    for fecha in ("2026-11-13", "2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"):
        assert SM not in ids_del_dia(fecha), fecha                                    # ni viernes ni domingo ni entre semana


def test_llaves_santa_maria_en_sabado_solo_se_empareja_con_su_titulo():
    # `referencia/llaves.py` no está en el repositorio público: la prueba solo corre en el clon de ZClaude.
    ref = generar.PROYECTO.parent / "referencia"
    if not (ref / "llaves.py").exists():
        pytest.skip("sin referencia/")
    import sys
    sys.path.insert(0, str(ref))
    import llaves

    def suyas(*titulos):
        return [(f"c{i}", {"lista": "liturgiasFeria" if i == 0 else "liturgiasMemoria", "titulo": t})
                for i, t in enumerate(titulos)]
    feria = "SÁBADO DE LA XXIX SEMANA DEL TIEMPO ORDINARIO, feria"
    claret = "SAN ANTONIO MARÍA CLARET, obispo, memoria libre"
    mia, _ = llaves.nuestras(date(2026, 10, 24))                                   # feria + Claret + Santa María en sábado
    for orden in ((claret, "SANTA MARÍA EN SÁBADO, memoria libre"), ("SANTA MARÍA EN SÁBADO, memoria libre", claret)):
        pares, sin, sobra = llaves.emparejar(mia, suyas(feria, *orden))
        assert {m["llave"]: s[1]["titulo"] for m, s in pares} == {
            "sabado-de-la-xxix-semana-del-tiempo-ordinario": feria, "san-antonio-maria-claret": claret,
            SM: "SANTA MARÍA EN SÁBADO, memoria libre"}
        assert not sin and not sobra
    # La referencia no la trae ese día: queda sin pareja y no toma el santo que sobra.
    pares, sin, sobra = llaves.emparejar(llaves.nuestras(date(2026, 10, 31))[0], suyas(
        "SÁBADO DE LA XXX SEMANA DEL TIEMPO ORDINARIO, feria", "SAN ALGUIEN, memoria libre"))
    assert [m["llave"] for m in sin] == [SM] and not any(m["llave"] == SM for m, _ in pares)


def test_batua_partir_lectura_reparte_las_opciones_de_una_unidad():
    ref = generar.PROYECTO.parent / "referencia"
    if not (ref / "batua.py").exists():
        pytest.skip("sin referencia/")
    import sys
    sys.path.insert(0, str(ref))
    import batua

    def r(tipo, texto):
        return {"tipo": tipo, "texto": texto}
    unidad = [r("R2", "Irakurgai laburra"), r("R2", "I [II]"), r("R6", "Ga 4, 4-5"), r("N4", "lectura uno"),
              r("R2", "Galde-erantzuna"), r("N4", "responsorio uno"),
              r("R2", "II [II]"), r("R6", "Ap 12, 1"), r("N4", "lectura dos"),
              r("R2", "Galde-erantzuna"), r("N4", "responsorio dos")]
    partes = batua.partir_lectura(unidad)
    texto = lambda p: [l["texto"] for l in partes[p]]
    assert texto("lectura") == ["Ga 4, 4-5", "lectura uno", "II [II]", "Ap 12, 1", "lectura dos"]
    assert texto("responsorio") == ["responsorio uno", "II [II]", "responsorio dos"]
    # Una unidad sin opciones se parte como siempre: lectura hasta el segundo título, y el responsorio detrás.
    simple = [r("R2", "Irakurgai laburra"), r("R6", "Rm 1, 1"), r("N4", "lectura"), r("R2", "Galde-erantzuna"), r("N4", "resp")]
    p = batua.partir_lectura(simple)
    assert [l["texto"] for l in p["lectura"]] == ["Irakurgai laburra", "Rm 1, 1", "lectura"] and [l["texto"] for l in p["responsorio"]] == ["resp"]
