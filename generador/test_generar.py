"""Pruebas del generador. Correr: py -3.14 -m pytest projects/OrduenLiturgia/generador -q"""
import json
from datetime import date, timedelta

import pytest

import generar

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
])
def test_visperas_de_quien(fecha, cuales, de):
    dia = generar.generar_dia(date.fromisoformat(fecha), {}, {})
    v = dia["celebraciones"][0]["visperas_de"]
    assert v["cuales"] == cuales
    if de:
        assert v["de"] == de


def test_memoria_libre_sale_como_opcional_y_la_feria_como_principal():
    dia = generar.generar_dia(date(2026, 11, 16), {}, {})   # santa Margarita de Escocia / santa Gertrudis
    assert [c["opcional"] for c in dia["celebraciones"]] == [False, True]
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
    return generar.formulario_completas(info, man, generar.tiene_primeras_visperas(man) and man["nivel"] < info["nivel"])


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
