"""Spanish liturgical day names → Basque (euskera batua).

`liturgia.calculate()` is canonical and returns Spanish strings (e.g.
"Domingo I de Adviento", "Tiempo Ordinario", "Solemnidad", "Lunes de la
III Semana de Cuaresma"). This module rewrites them to batua at the
presentation boundary, so calculate() stays untouched.

Sources cross-checked (2026-04 search; cited in plan file):
- igandetakoak.arantzazu.org — Arantzazu sanctuary (Gipuzkoa). Most complete
  navigation menu of liturgical Sundays in batua.
- elizagipuzkoa.org — Diocese of San Sebastián liturgy area.
- bizkeliza.org — Diocese of Bilbao "Irakurgaiak" CEE-approved volumes.
- amunsa.eus — daily liturgy aids in batua.
- arratiaeliza.blogspot.com — south-Basque liturgy use ("Jaia" for fiesta).

This translator is INTENTIONALLY conservative: anything it does not match
falls through to the original Spanish. That guarantees we never invent names.
The few entries that admit alternative renderings are marked REVIEW; for
those the user should validate against an authoritative missal.

SINGLE-DIALECT RULE FOR CHROME — batua, always.
The site carries two Basque layers and they do NOT share a dialect. The
readings are bizkaiera (Bizkeliza source, quoted verbatim, never translated).
Everything the site says in its own voice — day and season names, page titles,
meta descriptions, buttons, search UI — is batua. A reading and its chrome may
differ; the chrome may not differ from itself. Do not "preserve" a bizkaiera
UI string for consistency with the reading beside it: that is the mix this
rule exists to prevent (`Bazko-aldiko` shipped live and had to be corrected to
`Pazko-aldiko` on 2026-04-28). Same rule governs `i18n.py:I18N_EU` and
`i18n.py:DAY_ES_TO_EU`.
"""

from __future__ import annotations

import re
import unicodedata

# ── Liturgical season ─────────────────────────────────────────────────────────
# `result["season"]` from liturgia.calculate() takes one of these values.
SEASON_ES_TO_EU = {
    "Adviento": "Abendualdia",
    "Tiempo de Navidad": "Eguberrialdia",
    "Tiempo Ordinario": "Urtean Zehar",
    "Cuaresma": "Garizuma",
    "Semana Santa": "Aste Santua",
    "Triduo Pascual": "Pazko Hirurrena",         # REVIEW
    "Tiempo de Pascua": "Pazkoaldia",
    "Octava de Pascua": "Pazko Zortziurrena",    # REVIEW
}


# ── Liturgical rank (`result["rank"]`) ────────────────────────────────────────
RANK_ES_TO_EU = {
    "Solemnidad": "Solemnitatea",
    "Fiesta": "Jaia",
    "Memoria": "Oroitzapena",
    "Memoria Obligatoria": "Nahitaezko Oroitzapena",
    "Memoria Libre": "Aukerako Oroitzapena",
    "Feria": "Asteguna",
    "Domingo": "Igandea",
}


# ── Sunday cycle / weekday cycle ──────────────────────────────────────────────
SUNDAY_CYCLE_ES_TO_EU = {
    "Ciclo A": "A zikloa",
    "Ciclo B": "B zikloa",
    "Ciclo C": "C zikloa",
}
WEEKDAY_CYCLE_ES_TO_EU = {
    "Año I": "I urtea",
    "Año II": "II urtea",
    "Ano I": "I urtea",
    "Ano II": "II urtea",
}


# ── Spanish weekday → Basque weekday (batua) ──────────────────────────────────
# (Bizkaiera versions live in i18n.py for the date-line; here we use batua
# because liturgical day names use the standardized form.)
WEEKDAY_ES_TO_EU_BATUA = {
    "Lunes": "Astelehena",
    "Martes": "Asteartea",
    "Miércoles": "Asteazkena",
    "Miercoles": "Asteazkena",
    "Jueves": "Osteguna",
    "Viernes": "Ostirala",
    "Sábado": "Larunbata",
    "Sabado": "Larunbata",
    "Domingo": "Igandea",
}


# ── Specific liturgical days (exact-match lookup, takes precedence over patterns)
# Keys are exact Spanish names returned by liturgia.calculate(). The actual
# values used in this codebase are the unaccented forms (e.g. "Pasion",
# "Senor", "Cuaresma") because the lectionary stores them that way. We list
# the unaccented form as canonical and include the accented variant where it
# could plausibly come from another source.
EXACT_NAME_ES_TO_EU = {
    # ── Advent / Christmas ─────────────────────────────────────────
    "El Bautismo del Senor": "Jaunaren Bataioa",
    "El Bautismo del Señor": "Jaunaren Bataioa",
    "Bautismo del Senor": "Jaunaren Bataioa",
    "Bautismo del Señor": "Jaunaren Bataioa",
    "Natividad del Senor": "Jaunaren Jaiotza",
    "Natividad del Señor": "Jaunaren Jaiotza",
    "La Sagrada Familia de Jesus, Maria y Jose": "Famili Santua: Jesus, Maria eta Jose",
    "La Sagrada Familia de Jesús, María y José": "Famili Santua: Jesus, Maria eta Jose",
    "Sagrada Familia": "Famili Santua: Jesus, Maria eta Jose",
    "Santa Maria, Madre de Dios": "Jainkoaren Ama",
    "Santa María, Madre de Dios": "Jainkoaren Ama",
    "II Domingo de Navidad": "Eguberri Ondorengo II Igandea",
    "Epifania del Senor": "Jaunaren Agerkundea",
    "Epifanía del Señor": "Jaunaren Agerkundea",
    "Dia 6 de la Octava de Navidad": "Eguberri Zortziurreneko 6. Eguna",  # REVIEW
    "Día 6 de la Octava de Navidad": "Eguberri Zortziurreneko 6. Eguna",  # REVIEW

    # ── Holy Week / Triduum ─────────────────────────────────────────
    "Domingo de Ramos en la Pasion del Senor": "Jaunaren Nekaldiko Erramu Igandea",
    "Domingo de Ramos en la Pasión del Señor": "Jaunaren Nekaldiko Erramu Igandea",
    "Lunes Santo": "Astelehen Santua",
    "Martes Santo": "Astearte Santua",
    "Miercoles Santo": "Asteazken Santua",
    "Miércoles Santo": "Asteazken Santua",
    "Jueves Santo - La Cena del Senor": "Ostegun Santua: Jaunaren Afaria",  # REVIEW
    "Jueves Santo - La Cena del Señor": "Ostegun Santua: Jaunaren Afaria",  # REVIEW
    "Jueves Santo": "Ostegun Santua",
    "Viernes Santo - La Pasion del Senor": "Jaunaren Nekaldiko Ostiral Santua",
    "Viernes Santo - La Pasión del Señor": "Jaunaren Nekaldiko Ostiral Santua",
    "Viernes Santo": "Ostiral Santua",
    "Sabado Santo - Vigilia Pascual": "Larunbat Santua: Pazko Bijilia",
    "Sábado Santo - Vigilia Pascual": "Larunbat Santua: Pazko Bijilia",
    "Sabado Santo": "Larunbat Santua",
    "Sábado Santo": "Larunbat Santua",
    "Vigilia Pascual": "Pazko Bijilia",
    "Domingo de Resurreccion": "Jaunaren Biztuerako Pazko Igandea",
    "Domingo de Resurrección": "Jaunaren Biztuerako Pazko Igandea",

    # ── Easter season specific ──────────────────────────────────────
    "La Ascension del Senor": "Igokunde Igandea",
    "La Ascensión del Señor": "Igokunde Igandea",
    "Ascension del Senor": "Igokunde Igandea",
    "Ascensión del Señor": "Igokunde Igandea",
    "Domingo de Pentecostes": "Pentekoste Igandea",
    "Domingo de Pentecostés": "Pentekoste Igandea",
    "Pentecostes": "Pentekoste Igandea",
    "Pentecostés": "Pentekoste Igandea",

    # ── Solemnities after Pentecost ─────────────────────────────────
    "Santisima Trinidad": "Hirutasun Igandea",
    "Santísima Trinidad": "Hirutasun Igandea",
    "Santisimo Cuerpo y Sangre de Cristo (Corpus Christi)": "Kristoren Gorputz-Odol Santuak",
    "Santísimo Cuerpo y Sangre de Cristo (Corpus Christi)": "Kristoren Gorputz-Odol Santuak",
    "Sagrado Corazon de Jesus": "Jesusen Bihotz Guztiz Santua",
    "Sagrado Corazón de Jesús": "Jesusen Bihotz Guztiz Santua",
    "Inmaculado Corazon de la Virgen Maria": "Andre Mariaren Bihotz Garbia",     # REVIEW
    "Inmaculado Corazón de la Virgen María": "Andre Mariaren Bihotz Garbia",     # REVIEW
    "Nuestro Senor Jesucristo, Rey del Universo": "Kristo Errege",
    "Nuestro Señor Jesucristo, Rey del Universo": "Kristo Errege",

    # ── Marian feasts ───────────────────────────────────────────────
    "La Anunciacion del Senor": "Jaunaren Iragarpena",                # REVIEW
    "La Anunciación del Señor": "Jaunaren Iragarpena",                # REVIEW
    "La Asuncion de la Virgen Maria": "Andre Mariaren Jasokundea",    # REVIEW
    "La Asunción de la Virgen María": "Andre Mariaren Jasokundea",    # REVIEW
    "La Inmaculada Concepcion": "Andre Maria Sortzez Garbia",
    "La Inmaculada Concepción": "Andre Maria Sortzez Garbia",
    "Bienaventurada Virgen Maria, Madre de la Iglesia": "Andre Maria, Elizaren Ama",   # REVIEW
    "Bienaventurada Virgen María, Madre de la Iglesia": "Andre Maria, Elizaren Ama",   # REVIEW
    "La Presentacion del Senor": "Jaunaren Aurkezpena",               # REVIEW
    "La Presentación del Señor": "Jaunaren Aurkezpena",               # REVIEW
    "La Transfiguracion del Senor": "Jaunaren Antzaldatzea",          # REVIEW
    "La Transfiguración del Señor": "Jaunaren Antzaldatzea",          # REVIEW
    "La Exaltacion de la Santa Cruz": "Gurutze Santuaren Goratzea",   # REVIEW
    "La Exaltación de la Santa Cruz": "Gurutze Santuaren Goratzea",   # REVIEW

    # ── Other major fixed feasts ────────────────────────────────────
    "Todos los Santos": "Santu Guztien Eguna",
    "Conmemoracion de los Fieles Difuntos": "Hildakoen Eguna",        # REVIEW
    "Conmemoración de los Fieles Difuntos": "Hildakoen Eguna",        # REVIEW
    "La Conversion de San Pablo": "San Paulen Bihozberritzea",        # REVIEW
    "La Conversión de San Pablo": "San Paulen Bihozberritzea",        # REVIEW
    "Dedicacion de la Basilica de Letran": "Lateraneko Basilikaren Sagaratzea",  # REVIEW
    "Dedicación de la Basílica de Letrán": "Lateraneko Basilikaren Sagaratzea",  # REVIEW

    # ── Ash Wednesday (boundary day) ────────────────────────────────
    "Miercoles de Ceniza": "Hauts Asteazkena",
    "Miércoles de Ceniza": "Hauts Asteazkena",

    # ── Apostles + saints (special structures only) ─────────────────
    # Most "San X, role" / "Santos X y Y, role" memorials are handled by the
    # generic localize_memorial() parser. Only structurally complex names
    # remain in this exact-match table (e.g. ones with extra modifiers like
    # "Esposo de la Virgen Maria" or proper-noun complements that the parser
    # would otherwise mistreat).
    "San Jose, Esposo de la Virgen Maria": "Jose, Andre Mariaren senarra",         # REVIEW
    "San José, Esposo de la Virgen María": "Jose, Andre Mariaren senarra",         # REVIEW
    "Santiago Apostol, Patron de Espana": "Santiago apostolua, Espainiako zaindaria",  # REVIEW
    "Santiago Apóstol, Patrón de España": "Santiago apostolua, Espainiako zaindaria",  # REVIEW
    "Santos Inocentes, martires": "Errugabe martiriak",                            # REVIEW
    "Santos Inocentes, mártires": "Errugabe martiriak",                            # REVIEW
    "Santos Arcangeles Miguel, Gabriel y Rafael": "Mikel, Gabriel eta Rafael goiaingeruak",  # REVIEW
    "Santos Arcángeles Miguel, Gabriel y Rafael": "Mikel, Gabriel eta Rafael goiaingeruak",  # REVIEW
    "Santa Catalina de Siena, virgen y doctora, patrona de Europa": "Katalina Sienakoa birjina eta doktorea, Europako zaindaria",  # REVIEW
    "Santa Brigida, religiosa, patrona de Europa": "Brigida erlijiosa, Europako zaindaria",  # REVIEW
    "Santa Brígida, religiosa, patrona de Europa": "Brigida erlijiosa, Europako zaindaria",  # REVIEW

    # ── Marian feasts (additional) ──────────────────────────────────
    "La Visitacion de la Virgen Maria": "Andre Mariaren Bisitaldia",               # REVIEW
    "La Visitación de la Virgen María": "Andre Mariaren Bisitaldia",               # REVIEW
    "Visitacion de la Virgen Maria": "Andre Mariaren Bisitaldia",                  # REVIEW
    "Natividad de la Virgen Maria": "Andre Mariaren Jaiotza",                      # REVIEW
    "Natividad de la Virgen María": "Andre Mariaren Jaiotza",                      # REVIEW
    "Nuestra Senora del Pilar": "Pilarko Andre Maria",                             # REVIEW
    "Nuestra Señora del Pilar": "Pilarko Andre Maria",                             # REVIEW
    "Natividad de San Juan Bautista": "San Joan Bataiatzailearen Jaiotza",         # REVIEW

    # ── Cathedras / dedications ─────────────────────────────────────
    "La Catedra de San Pedro": "San Pedroren Aulkia",                              # REVIEW
    "La Cátedra de San Pedro": "San Pedroren Aulkia",                              # REVIEW
    "Catedra de San Pedro": "San Pedroren Aulkia",                                 # REVIEW
    "Dedicacion de la Basilica de Santa Maria la Mayor": "Andre Maria Handiaren Basilikaren Sagaratzea",  # REVIEW
    "Dedicación de la Basílica de Santa María la Mayor": "Andre Maria Handiaren Basilikaren Sagaratzea",  # REVIEW

    # ── Marian devotions and feasts ─────────────────────────────────
    "Presentacion de la Virgen Maria": "Andre Mariaren Aurkezpena",                # REVIEW
    "Presentación de la Virgen María": "Andre Mariaren Aurkezpena",                # REVIEW
    "El Dulce Nombre de Maria": "Andre Mariaren Izen Goxoa",                       # REVIEW
    "El Dulce Nombre de María": "Andre Mariaren Izen Goxoa",                       # REVIEW
    "Santa Maria Virgen, Reina": "Andre Maria Birjina Erregina",                   # REVIEW
    "Santa María Virgen, Reina": "Andre Maria Birjina Erregina",                   # REVIEW
    "Nuestra Senora de Fatima": "Fatimako Andre Maria",                            # REVIEW
    "Nuestra Señora de Fátima": "Fatimako Andre Maria",                            # REVIEW
    "Nuestra Senora de Guadalupe": "Guadalupeko Andre Maria",                      # REVIEW
    "Nuestra Señora de Guadalupe": "Guadalupeko Andre Maria",                      # REVIEW
    "Nuestra Senora del Carmen": "Karmengo Andre Maria",                           # REVIEW
    "Nuestra Señora del Carmen": "Karmengo Andre Maria",                           # REVIEW
    "Nuestra Senora del Rosario": "Errosarioko Andre Maria",                       # REVIEW
    "Nuestra Señora del Rosario": "Errosarioko Andre Maria",                       # REVIEW
    "Nuestra Senora de los Dolores": "Andre Maria Nahigabetua",                    # REVIEW
    "Nuestra Señora de los Dolores": "Andre Maria Nahigabetua",                    # REVIEW

    # ── Specific saint events ───────────────────────────────────────
    "Martirio de San Juan Bautista": "Joan Bataiatzailearen Martiritza",            # REVIEW
    "Los Siete Santos Fundadores de los Servitas": "Servitarren Zazpi Sortzaile Santuak",  # REVIEW
    "Santos Angeles Custodios": "Aingeru Zaindariak",                              # REVIEW
    "Santos Ángeles Custodios": "Aingeru Zaindariak",                              # REVIEW
    "Santa Marta, Maria y Lazaro": "Marta, Maria eta Lazaro Santuak",              # REVIEW
    "Santa Marta, María y Lázaro": "Marta, Maria eta Lazaro Santuak",              # REVIEW

    # ── Multi-companion saint memorials (don't fit the simple parser) ─
    "Santos Andres Kim, Pablo Chong y companeros, martires": "Andres Kim, Paulo Chong eta lagun martiriak",  # REVIEW
    "Santos Andrés Kim, Pablo Chong y compañeros, mártires": "Andres Kim, Paulo Chong eta lagun martiriak",  # REVIEW
    "Santos Juan de Brebeuf, Isaac Jogues y companeros": "Joan de Brebeuf, Isaac Jogues eta lagun santuak",  # REVIEW
    "Santos Juan de Brébeuf, Isaac Jogues y compañeros": "Joan de Brebeuf, Isaac Jogues eta lagun santuak",  # REVIEW
}


# ── Pattern rules (regex → replacement template) ──────────────────────────────
# Patterns operate on the original Spanish name. Roman numerals are preserved.

_ROMAN = r"(?P<roman>[IVXLCDM]+)"
_WD = r"(?P<wd>Lunes|Martes|Miércoles|Miercoles|Jueves|Viernes|Sábado|Sabado)"
_DIA = r"(?P<dia>\d{1,2})"
_MES = r"(?P<mes>enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"

# Order matters: more specific patterns first.
_PATTERNS = [
    # Sundays — Roman comes BEFORE "Domingo" in liturgia.calculate output:
    # "I Domingo de Adviento", "XIV Domingo del Tiempo Ordinario"
    (re.compile(rf"^{_ROMAN}\s+Domingo\s+de\s+Adviento$", re.IGNORECASE),
     "Abenduko {roman} Igandea"),
    (re.compile(rf"^{_ROMAN}\s+Domingo\s+de\s+Cuaresma$", re.IGNORECASE),
     "Garizumako {roman} Igandea"),
    (re.compile(rf"^{_ROMAN}\s+Domingo\s+de\s+Pascua$", re.IGNORECASE),
     "Pazko-aldiko {roman} Igandea"),
    (re.compile(rf"^{_ROMAN}\s+Domingo\s+del?\s+Tiempo\s+Ordinario$", re.IGNORECASE),
     "Urtean Zehar {roman} Igandea"),
    # II Domingo de Navidad — handled by EXACT but if the form is different:
    (re.compile(rf"^{_ROMAN}\s+Domingo\s+de\s+Navidad$", re.IGNORECASE),
     "Eguberri Ondorengo {roman} Igandea"),

    # Weekdays of seasons: "Lunes de la I Semana de Adviento"
    (re.compile(rf"^{_WD}\s+de\s+la\s+{_ROMAN}\s+Semana\s+de\s+Adviento$", re.IGNORECASE),
     "Abenduko {roman}. Asteko {wd_eu}"),
    (re.compile(rf"^{_WD}\s+de\s+la\s+{_ROMAN}\s+Semana\s+de\s+Cuaresma$", re.IGNORECASE),
     "Garizumako {roman}. Asteko {wd_eu}"),
    (re.compile(rf"^{_WD}\s+de\s+la\s+{_ROMAN}\s+Semana\s+de\s+Pascua$", re.IGNORECASE),
     "Pazko-aldiko {roman}. Asteko {wd_eu}"),
    (re.compile(rf"^{_WD}\s+de\s+la\s+{_ROMAN}\s+Semana\s+del?\s+Tiempo\s+Ordinario$", re.IGNORECASE),
     "Urtean Zeharreko {roman}. Asteko {wd_eu}"),
    # Octave of Easter: "Lunes de la Octava de Pascua"
    (re.compile(rf"^{_WD}\s+de\s+la\s+Octava\s+de\s+Pascua$", re.IGNORECASE),
     "Pazko Zortziurreneko {wd_eu}"),

    # Days after Ash Wednesday (before I Sunday of Lent):
    # "Jueves despues de Ceniza"
    (re.compile(rf"^{_WD}\s+despu[eé]s\s+de\s+Ceniza$", re.IGNORECASE),
     "Hauts Asteazkenaren ondorengo {wd_eu}"),

    # Late-Advent ferias: "Feria del 17-24 de Diciembre (17 dic)"
    (re.compile(r"^Feria\s+del\s+17-24\s+de\s+Diciembre\s+\((?P<dia>\d{1,2})\s+dic\)$", re.IGNORECASE),
     "Abenduaren {dia}a (Abendu betea)"),  # REVIEW

    # Christmas-octave ferias: "Feria del Tiempo de Navidad (10 enero)"
    (re.compile(rf"^Feria\s+del\s+Tiempo\s+de\s+Navidad\s+\({_DIA}\s+{_MES}\)$", re.IGNORECASE),
     "Eguberrialdiko Asteguna ({mes_eu}aren {dia}a)"),  # REVIEW
]


_MES_ES_TO_EU = {
    "enero": "urtarrila",
    "febrero": "otsaila",
    "marzo": "martxoa",
    "abril": "apirila",
    "mayo": "maiatza",
    "junio": "ekaina",
    "julio": "uztaila",
    "agosto": "abuztua",
    "septiembre": "iraila",
    "setiembre": "iraila",
    "octubre": "urria",
    "noviembre": "azaroa",
    "diciembre": "abendua",
}


# ── Saint memorial role translation ───────────────────────────────────────────
#
# Most CEE memorials follow the form: "<Saint name>, <role>[ y <role2>]". We
# translate the role predicate (post-comma) using these tables and keep the
# saint's proper name except where a well-known Basque variant exists.

# Role translations. Keys are lowercase Spanish role words.
SAINT_ROLES = {
    # Apostolic / evangelical
    "apostol": "apostolua",
    "apóstol": "apostolua",
    "apostoles": "apostoluak",
    "apóstoles": "apostoluak",
    "evangelista": "ebanjelaria",
    # Martyrdom
    "martir": "martiria",
    "mártir": "martiria",
    "martires": "martiriak",
    "mártires": "martiriak",
    "protomartir": "lehen martiria",
    "protomártir": "lehen martiria",
    # Episcopate / pastoral
    "obispo": "gotzaina",
    "obispos": "gotzainak",
    "papa": "aita santua",
    "papas": "aita santuak",
    "presbitero": "presbiteroa",
    "presbítero": "presbiteroa",
    "diacono": "diakonoa",
    "diácono": "diakonoa",
    "abad": "abadea",
    # Doctors and teachers
    "doctor": "doktorea",
    "doctora": "doktorea",
    # Religious life
    "religioso": "erlijiosoa",
    "religiosa": "erlijiosoa",
    "monje": "monjea",
    "monja": "monjea",
    "fundador": "sortzailea",
    "fundadora": "sortzailea",
    # Marian / virginal
    "virgen": "birjina",
    "virgenes": "birjinak",
    "vírgenes": "birjinak",
    "reina": "erregina",
    # Geographic / patronage
    "patron": "zaindaria",
    "patrón": "zaindaria",
    "patrona": "zaindaria",
    # Compagnion phrasing
    "companeros": "lagunak",
    "compañeros": "lagunak",
    "companera": "laguna",
    "compañera": "laguna",
}

# Connectors
SAINT_CONNECTORS = {
    " y ": " eta ",
    " y, ": " eta, ",
}

# Country / region names where they appear in "Patrón de X" / "patrona de Europa"
SAINT_GEO_GENITIVE = {
    # ES locative -> EU genitive form
    "Espana": "Espainiako",
    "España": "Espainiako",
    "Europa": "Europako",
    "Italia": "Italiako",
    "Francia": "Frantziako",
    "Hungria": "Hungariako",
    "Hungría": "Hungariako",
    "Portugal": "Portugalgo",
    "Polonia": "Poloniako",
    "Asia": "Asiako",
    "America": "Amerikako",
    "América": "Amerikako",
}

# Saint personal-name spellings where Basque differs from Spanish.
# Conservative: only well-attested forms in CEE batua usage. Names not listed
# pass through unchanged.
SAINT_NAME_SUBSTITUTIONS = {
    "Juan": "Joan",
    "Pablo": "Paulo",
    "Lucas": "Lukas",
    "Marcos": "Markos",
    "Mateo": "Mateo",      # same in batua
    "Miguel": "Mikel",
    "Pedro": "Pedro",      # same
    "Andres": "Andres",
    "Andrés": "Andres",
    "Lorenzo": "Lorentzo",
    "Esteban": "Esteban",
    "Tomas": "Tomas",
    "Tomás": "Tomas",
    "Felipe": "Felipe",
    "Bartolome": "Bartolome",
    "Bartolomé": "Bartolome",
    "Jose": "Jose",
    "José": "Jose",
    "Maria": "Maria",
    "María": "Maria",
    "Catalina": "Katalina",
    "Cecilia": "Zezilia",
    "Bernabe": "Bernabe",
    "Bernabé": "Bernabe",
    "Bernardo": "Bernardo",
    "Lucia": "Luzia",
    "Lucía": "Luzia",
    "Brigida": "Brigida",
    "Brígida": "Brigida",
    "Agueda": "Ageda",
    "Águeda": "Ageda",
    "Ines": "Ines",
    "Inés": "Ines",
    "Magdalena": "Magdalena",
}

# Words to drop when present alongside a saint name (purely decorative).
# Currently empty — kept here for future use.
SAINT_DROP_WORDS: set[str] = set()

_SAINT_PREFIX_RE = re.compile(r"^(Santos|Santo|Santa|San)\s+", re.IGNORECASE)


def _strip_saint_prefix(text: str) -> tuple[str, bool]:
    """Strip a leading 'San/Santo/Santa/Santos' prefix.

    Returns (text_without_prefix, was_plural). Per Euskaltzaindia and the
    Arantzazu batua liturgical calendar, in modern unified Basque the
    preferred postposed form replaces the Spanish prefix:
      - "San X"    → "X Santua"     (singular)
      - "Santos X" → "X Santuak"    (plural)
      - "Santa X"  → "X Santua"     (santu is gender-neutral in batua)
      - "Santo X"  → "X Santua"     ("Santo" is a Spanish-only prefix)
    """
    m = _SAINT_PREFIX_RE.match(text)
    if not m:
        return text, False
    prefix = m.group(1).lower()
    return text[m.end():], (prefix == "santos")


def _translate_roles_segment(roles_es: str) -> str:
    """Translate a roles predicate like 'obispo y martir' or 'virgen y doctora'."""
    parts = re.split(r"\s+y\s+", roles_es.strip(), flags=re.IGNORECASE)
    out_parts = []
    for p in parts:
        # Geographic patronage: "patron de Espana" / "patrona de Europa"
        m = re.match(r"^(patron|patrón|patrona)\s+de\s+(.+)$", p.strip(), re.IGNORECASE)
        if m:
            geo_es = m.group(2).strip()
            geo_eu = SAINT_GEO_GENITIVE.get(geo_es, geo_es)
            out_parts.append(f"{geo_eu} zaindaria")
            continue
        key = p.strip().lower()
        out_parts.append(SAINT_ROLES.get(key, p.strip()))
    return " eta ".join(out_parts)


_INNER_SAINT_PREFIX_RE = re.compile(
    r"\b(San|Santo|Santa|Santos)\s+", re.IGNORECASE,
)


def _fold(token: str) -> str:
    """Quita tildes y virgulilla (NFD y fuera las marcas combinantes)."""
    return "".join(c for c in unicodedata.normalize("NFD", token)
                   if not unicodedata.combining(c))


def _translate_saint_name_only(name_es: str) -> str:
    """Translate the proper-name tokens (without changing structure).

    Strips ALL embedded 'San/Santo/Santa/Santos' prefixes (not just the
    leading one), so 'Fabian y San Sebastian' → 'Fabian eta Sebastian'.
    Replaces the Spanish connectors ' y ' and ' e ' with ' eta '.
    """
    # Remove inner saint prefixes (the leading one was already stripped by the caller)
    cleaned = _INNER_SAINT_PREFIX_RE.sub("", name_es)
    tokens = cleaned.split()
    # El motor escribe los nombres en castellano correcto (Agustín, Pío,
    # Niño Jesús); el batua no lleva tilde. La tabla se consulta por la forma
    # plegada y, si no traduce, sale la forma plegada: "Agustín" -> "Agustin".
    out_tokens = [SAINT_NAME_SUBSTITUTIONS.get(t, SAINT_NAME_SUBSTITUTIONS.get(_fold(t), _fold(t)))
                  for t in tokens]
    out = " ".join(out_tokens)
    out = re.sub(r"\s+y\s+", " eta ", out)
    out = re.sub(r"\s+e\s+", " eta ", out)
    return out


def _translate_saint_name(name_es: str) -> str:
    """Translate the name portion of a memorial, stripping the Spanish 'San/
    Santo/Santa/Santos' prefix and applying name spelling substitutions.

    The postposed 'Santua/Santuak' is NOT appended here — that is the caller's
    responsibility, because whether to append depends on whether a role
    follows: 'San Mateo, evangelista' becomes 'Mateo ebanjelaria' (role
    implies sainthood, postposed Santua omitted), while bare 'San Mateo'
    becomes 'Mateo Santua'.
    """
    inner, _ = _strip_saint_prefix(name_es)
    return _translate_saint_name_only(inner)


_SANTOS_PLURAL_RE = re.compile(
    r"^Santos\s+(?P<n1>[A-Za-zÁÉÍÓÚáéíóúñ.]+(?:\s+[A-Z][a-záéíóú.]+)*)"
    r"\s+y\s+"
    r"(?P<n2>[A-Za-zÁÉÍÓÚáéíóúñ.]+(?:\s+[A-Z][a-záéíóú.]+)*)"
    r"(?:,\s*(?P<roles>.+))?$"
)


def _expand_santos_plural(name_part: str) -> str | None:
    """If name_part starts with 'Santos X y Y', expand to 'San X eta San Y'."""
    m = _SANTOS_PLURAL_RE.match(name_part)
    if not m:
        return None
    n1 = _translate_saint_name(m.group("n1"))
    n2 = _translate_saint_name(m.group("n2"))
    return f"San {n1} eta San {n2}"


def localize_memorial(memorial_es: str, lang: str = "eu") -> str:
    """Translate a saint memorial from CEE Spanish to batua.

    Convention (per Euskaltzaindia + Arantzazu):
      - Bare saint name:       "San X"            → "X Santua"
      - With role:             "San X, role"      → "X role"   (no Santua)
      - Plural bare:           "Santos X y Y"     → "X eta Y Santuak"
      - Plural with role:      "Santos X y Y, R"  → "X eta Y R" (no Santuak)
      - Compound memorials:    "X / Y"            → recurse on each side

    The role implies sainthood, so the explicit "Santua/Santuak" marker is
    only appended when no role qualifier follows the name.
    """
    if not memorial_es or lang != "eu":
        return memorial_es or ""

    # 1. Compound memorials → recurse on each side
    if " / " in memorial_es:
        parts = [localize_memorial(p, lang) for p in memorial_es.split(" / ")]
        return " / ".join(parts)

    # 2. Exact-match table (covers major solemnities/feasts)
    if memorial_es in EXACT_NAME_ES_TO_EU:
        return EXACT_NAME_ES_TO_EU[memorial_es]

    # Pre-process: "y companeros" idiom anywhere in the string
    pre = memorial_es
    pre = re.sub(r"\s+y\s+compa(?:n|ñ)eros\b", " eta lagunak", pre, flags=re.IGNORECASE)

    # 3. "Santos X y Y[, role]" plural
    sp_match = _SANTOS_PLURAL_RE.match(pre)
    if sp_match:
        n1 = _translate_saint_name_only(sp_match.group("n1"))
        n2 = _translate_saint_name_only(sp_match.group("n2"))
        roles = sp_match.group("roles")
        if roles:
            return f"{n1} eta {n2} {_translate_roles_segment(roles)}".strip()
        return f"{n1} eta {n2} Santuak"

    # 4. Standard "<name>, role" — strip San/Santo/Santa prefix, no Santua
    if "," in pre:
        name_part, roles_part = pre.split(",", 1)
        name_eu = _translate_saint_name(name_part.strip())
        roles_eu = _translate_roles_segment(roles_part.strip())
        return f"{name_eu} {roles_eu}".strip()

    # 5. Bare saint name (no role): postpose Santua/Santuak
    inner, was_plural = _strip_saint_prefix(pre)
    if inner != pre:  # had a saint prefix
        inner_eu = _translate_saint_name_only(inner)
        # If the name already implies sainthood (carries 'lagunak' or 'lagun')
        # don't append a redundant Santuak.
        if re.search(r"\blagun(?:ak)?\b", inner_eu):
            return inner_eu
        suffix = "Santuak" if was_plural else "Santua"
        return f"{inner_eu} {suffix}"
    # No prefix detected → translate names only and pass through
    return _translate_saint_name_only(pre)


def localize_name(name_es: str, lang: str = "eu") -> str:
    """Translate a liturgical day name from ES to batua. Falls through unchanged
    when nothing matches — never invents.
    """
    if not name_es or lang != "eu":
        return name_es or ""

    s = name_es.strip()

    # 1. Exact match table wins
    if s in EXACT_NAME_ES_TO_EU:
        return EXACT_NAME_ES_TO_EU[s]

    # 2. Pattern rules
    for regex, template in _PATTERNS:
        m = regex.match(s)
        if m:
            groups = m.groupdict()
            wd_es = groups.get("wd") or ""
            wd_eu = WEEKDAY_ES_TO_EU_BATUA.get(wd_es, wd_es)
            mes_es = (groups.get("mes") or "").lower()
            # Strip the "a" / "the genitive" properly when composing
            mes_root = _MES_ES_TO_EU.get(mes_es, mes_es)
            # Drop trailing "a" so we can reattach the case ending "aren"
            if mes_root.endswith("a"):
                mes_root_for_format = mes_root[:-1]
            else:
                mes_root_for_format = mes_root
            return template.format(
                roman=groups.get("roman", ""),
                wd_eu=wd_eu,
                dia=groups.get("dia", ""),
                mes_eu=mes_root_for_format,
            )

    # 3. Saint feasts (Apostles, evangelists, doctors, etc.): the H1 takes
    # the same form as a memorial line, so reuse the structural translator.
    # localize_memorial passes through unchanged when nothing matches, so
    # this is safe even for purely-Spanish names without saint markers.
    return localize_memorial(s, lang)


def localize_season(season_es: str, lang: str = "eu") -> str:
    if not season_es or lang != "eu":
        return season_es or ""
    return SEASON_ES_TO_EU.get(season_es, season_es)


def localize_rank(rank_es: str, lang: str = "eu") -> str:
    if not rank_es or lang != "eu":
        return rank_es or ""
    return RANK_ES_TO_EU.get(rank_es, rank_es)


def localize_sunday_cycle(cycle_es: str, lang: str = "eu") -> str:
    if not cycle_es or lang != "eu":
        return cycle_es or ""
    return SUNDAY_CYCLE_ES_TO_EU.get(cycle_es, cycle_es)


def localize_weekday_cycle(cycle_es: str, lang: str = "eu") -> str:
    if not cycle_es or lang != "eu":
        return cycle_es or ""
    return WEEKDAY_CYCLE_ES_TO_EU.get(cycle_es, cycle_es)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    samples = [
        "Domingo I de Adviento",
        "Domingo III de Adviento",
        "Lunes de la II Semana de Adviento",
        "Domingo II de Cuaresma",
        "Viernes de la III Semana de Cuaresma",
        "Domingo de Ramos en la Pasión del Señor",
        "Jueves Santo",
        "Viernes Santo en la Pasión del Señor",
        "Vigilia Pascual",
        "Domingo de Resurrección",
        "Lunes de la Octava de Pascua",
        "Domingo II de Pascua",
        "Domingo VII de Pascua",
        "Solemnidad de la Ascensión",
        "Domingo de Pentecostés",
        "Solemnidad de la Santísima Trinidad",
        "Solemnidad del Cuerpo y la Sangre de Cristo",
        "Solemnidad de Nuestro Señor Jesucristo, Rey del Universo",
        "Domingo XIV del Tiempo Ordinario",
        "Martes de la X Semana del Tiempo Ordinario",
        "Inmaculada Concepción",
        "Asunción de la Virgen María",
        "Todos los Santos",
        # Pass-through cases
        "San Pedro y San Pablo",
        "Algo desconocido",
    ]
    print("ES → EU (batua) day name translation")
    print("=" * 70)
    for s in samples:
        eu = localize_name(s, "eu")
        marker = "  ==" if eu == s else "  →"
        print(f"  {s:55} {marker} {eu}")

    print()
    print("Seasons / ranks / cycles:")
    for s in ["Adviento", "Tiempo Ordinario", "Cuaresma", "Tiempo de Pascua"]:
        print(f"  season {s:24} → {localize_season(s, 'eu')}")
    for r in ["Solemnidad", "Fiesta", "Memoria Obligatoria", "Feria"]:
        print(f"  rank   {r:24} → {localize_rank(r, 'eu')}")
    for c in ["Ciclo A", "Ciclo B", "Ciclo C"]:
        print(f"  cycle  {c:24} → {localize_sunday_cycle(c, 'eu')}")
