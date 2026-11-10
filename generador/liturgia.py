#!/usr/bin/env python3
"""
Calculador determinista del dia liturgico catolico (calendario espanol).
Salida estructurada para consumo por Claude Code skill.

Uso: python liturgia.py [YYYY-MM-DD]
Sin argumentos: usa la fecha de hoy.

Norma de referencia: Normas Universales sobre el Año Litúrgico y el
Calendario (Pablo VI, 14-II-1969), Art. 1-59 + Tabla de precedencia.
"""

import sys
import json
import os
import re
from datetime import date, timedelta

# ── Tabla de precedencia de los días litúrgicos (Normas Universales, Art. 59) ─
# Cada nivel tiene prioridad sobre los siguientes. Dentro del mismo nivel,
# la celebración propia prevalece sobre la del calendario general.
#
# I.  1. Triduo Pascual de la Pasión y Resurrección del Señor
#     2. Natividad, Epifanía, Ascensión, Pentecostés
#        Domingos de Adviento, Cuaresma, Pascua
#        Miércoles de Ceniza
#        Ferias de Semana Santa (Lunes a Jueves Santo)
#        Días de la Octava de Pascua
#     3. Solemnidades del Señor, de la Virgen y de los Santos del Cal. General
#        Conmemoración de todos los Fieles Difuntos
#     4. Solemnidades propias (patrón, titular, dedicación, fundador, etc.)
#
# II. 5. Fiestas del Señor inscritas en el Calendario General
#     6. Domingos de Navidad y del Tiempo Ordinario
#     7. Fiestas de la Virgen y de los Santos del Calendario General
#     8. Fiestas propias
#
# III.9.  Ferias de Adviento del 17 al 24 de diciembre
#     10. Días de la Octava de Navidad
#     11. Ferias de Cuaresma
#     12. Memorias obligatorias del Calendario General
#     13. Memorias obligatorias propias
#
# IV. 14. Memorias libres
#     15. Ferias de Adviento hasta el 16 de diciembre
#     16. Ferias del Tiempo de Navidad desde el 2 de enero
#     17. Ferias del Tiempo Ordinario
#
# Reglas clave:
# - Art. 5: Los domingos de Adviento, Cuaresma y Pascua prevalecen sobre
#   todas las fiestas del Señor y sobre todas las solemnidades.
# - Art. 14: Las memorias obligatorias en Cuaresma son libres.
# - Art. 56: Cuando coinciden dos celebraciones, prevalece la de rango
#   superior en la tabla. Si son del mismo rango, se celebra la propia.
#
# ── Fiestas del Senor (Art. 59, II.5) ───────────────────────────────────
# These replace TO/Christmas Sundays when they coincide (Art. 10).
# Other feasts (BVM, Saints) do NOT replace Sundays.
FIESTAS_DEL_SENOR = {
    "La Presentación del Señor",
    "La Transfiguración del Señor",
    "La Exaltación de la Santa Cruz",
    "El Bautismo del Señor",
    "La Sagrada Familia de Jesús, María y José",
}

# ── I.2 level celebrations (Art. 59) ────────────────────────────────────
_LEVEL_I2_NAMES = {
    "Natividad del Señor", "Epifanía del Señor",
    "La Ascensión del Señor", "Domingo de Pentecostés",
}
_STRONG_SUNDAY_SEASONS = {"Adviento", "Cuaresma", "Tiempo de Pascua", "Semana Santa"}


def get_precedence_level(name: str, rank: str, season: str,
                         d: date, is_sunday: bool) -> int:
    """Return Art.59 precedence level (1=highest, 13=lowest).

    Levels:
      I:   1=Triduo, 2=Major solemnities+strong Sundays, 3=General solemnities
      II:  5=Fiestas del Senor, 6=Sundays Navidad/TO, 7=Fiestas BVM/Santos
      III: 9=Privileged ferias
      IV:  10=Memorias obligatorias, 12=Memorias libres, 13=Ferias ordinarias
    """
    # I.1 — Triduo Pascual
    if any(k in name for k in ("Jueves Santo", "Viernes Santo",
                                "Sabado Santo", "Vigilia Pascual")):
        return 1

    # I.2 — Major solemnities, strong-season Sundays, special days
    if name in _LEVEL_I2_NAMES:
        return 2
    if "Resurrección" in name or "Resurreccion" in name:
        return 2
    if is_sunday and season in _STRONG_SUNDAY_SEASONS:
        return 2
    if "Ceniza" in name:
        return 2
    if season == "Semana Santa" and rank == "Feria":  # Mon-Wed Holy Week
        return 2
    if "Octava de Pascua" in name:
        return 2

    # I.3 — General calendar solemnities (+ Fieles Difuntos)
    if rank == "Solemnidad":
        return 3

    # II.5 — Feasts of the Lord
    if rank == "Fiesta" and name in FIESTAS_DEL_SENOR:
        return 5

    # II.6 — Sundays of Christmas time and Ordinary Time
    if is_sunday and season in ("Tiempo de Navidad", "Tiempo Ordinario"):
        return 6

    # II.7 — Feasts of BVM and Saints (general calendar)
    if rank == "Fiesta":
        return 7

    # III.9 — Privileged ferias (Advent 17-24, Christmas Octave, Lent)
    if season == "Cuaresma" and rank == "Feria":
        return 9
    if season == "Semana Santa":
        return 9
    if "17-24" in name or "Feria privilegiada" in rank:
        return 9
    if season == "Tiempo de Navidad" and rank == "Feria":
        return 9

    # IV.10 — Obligatory memorials
    if rank == "Memoria Obligatoria":
        return 10

    # IV.12 — Free memorials
    if rank == "Memoria Libre":
        return 12

    # IV.13 — Ordinary ferias
    return 13


# OT_AFTER_PENT — REMOVED: now computed algorithmically (perennial).
# Week 34 = Christ the King (Sunday before Advent). Count backwards.

# ── Fiestas fijas (Calendario General + Espana) ──────────────────────────
FIXED_FEASTS = {
    (1, 1):   ("Santa María, Madre de Dios", "Solemnidad", "Blanco"),
    (1, 6):   ("Epifanía del Señor", "Solemnidad", "Blanco"),
    (2, 2):   ("La Presentación del Señor", "Fiesta", "Blanco"),
    (3, 19):  ("San José, Esposo de la Virgen María", "Solemnidad", "Blanco"),
    (3, 25):  ("La Anunciación del Señor", "Solemnidad", "Blanco"),
    (6, 24):  ("Natividad de San Juan Bautista", "Solemnidad", "Blanco"),
    (6, 29):  ("Santos Pedro y Pablo, Apóstoles", "Solemnidad", "Rojo"),
    (7, 25):  ("Santiago Apóstol, Patrón de España", "Solemnidad", "Rojo"),
    (8, 6):   ("La Transfiguración del Señor", "Fiesta", "Blanco"),
    (8, 15):  ("La Asunción de la Virgen María", "Solemnidad", "Blanco"),
    (9, 14):  ("La Exaltación de la Santa Cruz", "Fiesta", "Rojo"),
    (10, 12): ("Nuestra Señora del Pilar", "Fiesta", "Blanco"),
    (11, 1):  ("Todos los Santos", "Solemnidad", "Blanco"),
    (11, 2):  ("Conmemoración de los Fieles Difuntos", "Solemnidad", "Morado"),
    (12, 8):  ("La Inmaculada Concepción", "Solemnidad", "Blanco"),
    (12, 25): ("Natividad del Señor", "Solemnidad", "Blanco"),
}

# ── Memorias obligatorias y fiestas del calendario general + Espana ────────
# Formato: (mes, dia): ("Nombre", "Color") para memorias obligatorias
#           (mes, dia): ("Nombre", "Memoria Libre", "Color") para memorias libres
#           (mes, dia): ("Nombre", "Fiesta", "Color") para fiestas (lecturas propias)
OBLIGATORY_MEMORIALS = {
    # ── ENERO ──
    (1, 2):   ("Santos Basilio Magno y Gregorio Nacianceno", "Blanco"),
    (1, 7):   ("San Raimundo de Penyafort", "Memoria Libre", "Blanco"),  # Espana
    (1, 17):  ("San Antonio Abad", "Blanco"),
    (1, 20):  ("San Fabián y San Sebastián, mártires", "Memoria Libre", "Rojo"),
    (1, 21):  ("Santa Inés, virgen y mártir", "Rojo"),
    (1, 22):  ("San Vicente, diácono y mártir", "Rojo"),
    (1, 23):  ("San Ildefonso, obispo", "Blanco"),  # Espana
    (1, 24):  ("San Francisco de Sales", "Blanco"),
    (1, 25):  ("La Conversión de San Pablo", "Fiesta", "Blanco"),
    (1, 26):  ("Santos Timoteo y Tito", "Blanco"),
    (1, 28):  ("Santo Tomás de Aquino", "Blanco"),
    (1, 31):  ("San Juan Bosco", "Blanco"),
    # ── FEBRERO ──
    (2, 3):   ("San Blas / San Óscar", "Memoria Libre", "Blanco"),
    (2, 5):   ("Santa Águeda, virgen y mártir", "Rojo"),
    (2, 6):   ("San Pablo Miki y compañeros, mártires", "Rojo"),
    (2, 8):   ("San Jerónimo Emiliani / Santa Josefina Bakhita", "Memoria Libre", "Blanco"),
    (2, 10):  ("Santa Escolástica", "Blanco"),
    (2, 14):  ("Santos Cirilo y Metodio, patronos de Europa", "Fiesta", "Blanco"),
    (2, 17):  ("Los Siete Santos Fundadores de los Servitas", "Memoria Libre", "Blanco"),
    (2, 22):  ("La Cátedra de San Pedro", "Fiesta", "Blanco"),
    (2, 23):  ("San Policarpo, obispo y mártir", "Rojo"),
    # ── MARZO ──
    (3, 4):   ("San Casimiro", "Memoria Libre", "Blanco"),
    (3, 7):   ("Santas Perpetua y Felicidad, mártires", "Rojo"),
    (3, 8):   ("San Juan de Dios", "Memoria Libre", "Blanco"),
    (3, 9):   ("Santa Francisca Romana", "Memoria Libre", "Blanco"),
    (3, 17):  ("San Patricio", "Memoria Libre", "Blanco"),
    (3, 23):  ("Santo Toribio de Mogrovejo", "Memoria Libre", "Blanco"),
    # ── ABRIL ──
    (4, 2):   ("San Francisco de Paula", "Memoria Libre", "Blanco"),
    (4, 5):   ("San Vicente Ferrer", "Memoria Libre", "Blanco"),
    (4, 7):   ("San Juan Bautista de La Salle", "Blanco"),
    (4, 11):  ("San Estanislao, obispo y mártir", "Rojo"),
    (4, 13):  ("San Martín I, papa y mártir", "Memoria Libre", "Rojo"),
    (4, 26):  ("San Isidoro, obispo y doctor", "Fiesta", "Blanco"),  # Espana
    (4, 23):  ("San Jorge, mártir / San Adalberto", "Memoria Libre", "Rojo"),
    (4, 25):  ("San Marcos, evangelista", "Fiesta", "Rojo"),
    (4, 28):  ("San Pedro Chanel, mártir", "Memoria Libre", "Rojo"),
    (4, 29):  ("Santa Catalina de Siena, virgen y doctora, patrona de Europa", "Fiesta", "Blanco"),
    (4, 30):  ("San Pío V, papa", "Memoria Libre", "Blanco"),
    # ── MAYO ──
    (5, 1):   ("San José Obrero", "Memoria Libre", "Blanco"),
    (5, 2):   ("San Atanasio, obispo y doctor", "Blanco"),
    (5, 3):   ("Santos Felipe y Santiago, Apóstoles", "Fiesta", "Rojo"),
    (5, 10):  ("San Juan de Ávila", "Blanco"),  # Espana
    (5, 12):  ("Santos Nereo y Aquileo, mártires", "Memoria Libre", "Rojo"),
    (5, 13):  ("Nuestra Señora de Fátima", "Memoria Libre", "Blanco"),
    (5, 14):  ("San Matías, Apóstol", "Fiesta", "Rojo"),
    (5, 15):  ("San Isidro Labrador", "Blanco"),  # Espana
    (5, 18):  ("San Juan I, papa y mártir", "Memoria Libre", "Rojo"),
    (5, 20):  ("San Bernardino de Siena", "Memoria Libre", "Blanco"),
    (5, 22):  ("Santa Rita de Casia", "Memoria Libre", "Blanco"),
    (5, 25):  ("San Beda el Venerable / San Gregorio VII / Santa M. Magdalena de Pazzi", "Memoria Libre", "Blanco"),
    (5, 26):  ("San Felipe Neri", "Blanco"),
    (5, 27):  ("San Agustín de Canterbury", "Memoria Libre", "Blanco"),
    (5, 31):  ("La Visitación de la Virgen María", "Fiesta", "Blanco"),
    # ── JUNIO ──
    (6, 1):   ("San Justino, mártir", "Rojo"),
    (6, 2):   ("Santos Marcelino y Pedro, mártires", "Memoria Libre", "Rojo"),
    (6, 3):   ("San Carlos Lwanga y compañeros, mártires", "Rojo"),
    (6, 5):   ("San Bonifacio, obispo y mártir", "Rojo"),
    (6, 9):   ("San Efrén, diácono y doctor", "Memoria Libre", "Blanco"),
    (6, 11):  ("San Bernabé, Apóstol", "Rojo"),  # Memoria: primera obligatoria (CEE IV 580)
    (6, 13):  ("San Antonio de Padua", "Blanco"),
    (6, 21):  ("San Luis Gonzaga", "Blanco"),
    (6, 22):  ("San Paulino de Nola / Santos Juan Fisher y Tomás Moro", "Memoria Libre", "Blanco"),
    (6, 27):  ("San Cirilo de Alejandría", "Memoria Libre", "Blanco"),
    (6, 28):  ("San Ireneo, obispo y mártir", "Rojo"),
    # ── JULIO ──
    (7, 3):   ("Santo Tomás, Apóstol", "Fiesta", "Rojo"),
    (7, 4):   ("Santa Isabel de Portugal", "Memoria Libre", "Blanco"),
    (7, 5):   ("San Antonio María Zaccaria", "Memoria Libre", "Blanco"),
    (7, 6):   ("Santa María Goretti, virgen y mártir", "Memoria Libre", "Rojo"),
    (7, 11):  ("San Benito, abad, patrono de Europa", "Fiesta", "Blanco"),
    (7, 13):  ("San Enrique", "Memoria Libre", "Blanco"),
    (7, 14):  ("San Camilo de Lelis", "Memoria Libre", "Blanco"),
    (7, 15):  ("San Buenaventura, obispo y doctor", "Blanco"),
    (7, 16):  ("Nuestra Señora del Carmen", "Blanco"),  # Importante en Espana
    (7, 22):  ("Santa María Magdalena", "Fiesta", "Blanco"),
    (7, 23):  ("Santa Brígida, religiosa, patrona de Europa", "Fiesta", "Blanco"),
    # (7, 25) Santiago Apostol: ver FIXED_FEASTS (Solemnidad en Espana)
    (7, 26):  ("Santos Joaquín y Ana", "Blanco"),
    (7, 29):  ("Santa Marta, María y Lázaro", "Blanco"),
    (7, 30):  ("San Pedro Crisólogo", "Memoria Libre", "Blanco"),
    (7, 31):  ("San Ignacio de Loyola", "Blanco"),
    # ── AGOSTO ──
    (8, 1):   ("San Alfonso María de Ligorio", "Blanco"),
    (8, 2):   ("San Eusebio de Vercelli / San Pedro Julián Eymard", "Memoria Libre", "Blanco"),
    (8, 4):   ("San Juan María Vianney", "Blanco"),
    (8, 5):   ("Dedicación de la Basílica de Santa María la Mayor", "Memoria Libre", "Blanco"),
    (8, 7):   ("San Cayetano / Santos Sixto II y compañeros", "Memoria Libre", "Blanco"),
    (8, 8):   ("Santo Domingo de Guzmán", "Blanco"),
    (8, 9):   ("Santa Teresa Benedicta de la Cruz (Edith Stein), patrona de Europa", "Fiesta", "Rojo"),
    (8, 10):  ("San Lorenzo, diácono y mártir", "Fiesta", "Rojo"),
    (8, 11):  ("Santa Clara", "Blanco"),
    (8, 12):  ("Santa Juana Francisca de Chantal", "Memoria Libre", "Blanco"),
    (8, 13):  ("Santos Ponciano e Hipólito, mártires", "Memoria Libre", "Rojo"),
    (8, 14):  ("San Maximiliano Kolbe, mártir", "Rojo"),
    (8, 16):  ("San Esteban de Hungría", "Memoria Libre", "Blanco"),
    (8, 19):  ("San Juan Eudes", "Memoria Libre", "Blanco"),
    (8, 20):  ("San Bernardo, abad y doctor", "Blanco"),
    (8, 21):  ("San Pío X, Papa", "Blanco"),
    (8, 22):  ("Santa María Virgen, Reina", "Blanco"),
    (8, 23):  ("Santa Rosa de Lima", "Memoria Libre", "Blanco"),
    (8, 24):  ("San Bartolomé, Apóstol", "Fiesta", "Rojo"),
    (8, 25):  ("San Luis / San José de Calasanz", "Memoria Libre", "Blanco"),
    (8, 26):  ("Santa Teresa de Jesús Jornet e Ibars, virgen", "Blanco"),  # Espana
    (8, 27):  ("Santa Mónica", "Blanco"),
    (8, 28):  ("San Agustín, obispo y doctor", "Blanco"),
    (8, 29):  ("Martirio de San Juan Bautista", "Rojo"),
    # ── SEPTIEMBRE ──
    (9, 3):   ("San Gregorio Magno, papa y doctor", "Blanco"),
    (9, 8):   ("Natividad de la Virgen María", "Fiesta", "Blanco"),
    (9, 9):   ("San Pedro Claver", "Memoria Libre", "Blanco"),
    (9, 12):  ("El Dulce Nombre de María", "Memoria Libre", "Blanco"),
    (9, 13):  ("San Juan Crisóstomo, obispo y doctor", "Blanco"),
    (9, 15):  ("Nuestra Señora de los Dolores", "Blanco"),
    (9, 16):  ("Santos Cornelio y Cipriano, mártires", "Rojo"),
    (9, 17):  ("San Roberto Belarmino", "Memoria Libre", "Blanco"),
    (9, 19):  ("San Jenaro, obispo y mártir", "Memoria Libre", "Rojo"),
    (9, 20):  ("Santos Andrés Kim, Pablo Chong y compañeros, mártires", "Rojo"),
    (9, 21):  ("San Mateo, Apóstol y evangelista", "Fiesta", "Rojo"),
    (9, 23):  ("San Pío de Pietrelcina", "Blanco"),
    (9, 26):  ("Santos Cosme y Damián, mártires", "Memoria Libre", "Rojo"),
    (9, 27):  ("San Vicente de Paúl", "Blanco"),
    (9, 29):  ("Santos Arcángeles Miguel, Gabriel y Rafael", "Fiesta", "Blanco"),
    (9, 30):  ("San Jerónimo, presbítero y doctor", "Blanco"),
    # ── OCTUBRE ──
    (10, 1):  ("Santa Teresa del Niño Jesús", "Blanco"),
    (10, 2):  ("Santos Ángeles Custodios", "Blanco"),
    (10, 4):  ("San Francisco de Asís", "Blanco"),
    (10, 6):  ("San Bruno", "Memoria Libre", "Blanco"),
    (10, 7):  ("Nuestra Señora del Rosario", "Blanco"),
    (10, 9):  ("Santos Dionisio y compañeros / San Juan Leonardi", "Memoria Libre", "Rojo"),
    (10, 14): ("San Calixto I, papa y mártir", "Memoria Libre", "Rojo"),
    (10, 15): ("Santa Teresa de Jesús", "Blanco"),  # Espana
    (10, 16): ("Santa Margarita María de Alacoque / Santa Eduvigis", "Memoria Libre", "Blanco"),
    (10, 17): ("San Ignacio de Antioquía, obispo y mártir", "Rojo"),
    (10, 18): ("San Lucas, evangelista", "Fiesta", "Rojo"),
    (10, 19): ("Santos Juan de Brébeuf, Isaac Jogues y compañeros / San Pablo de la Cruz", "Memoria Libre", "Rojo"),
    (10, 22): ("San Juan Pablo II, papa", "Memoria Libre", "Blanco"),
    (10, 23): ("San Juan de Capistrano", "Memoria Libre", "Blanco"),
    (10, 24): ("San Antonio María Claret", "Memoria Libre", "Blanco"),  # Espana
    (10, 28): ("Santos Simón y Judas, Apóstoles", "Fiesta", "Rojo"),
    # ── NOVIEMBRE ──
    (11, 3):  ("San Martín de Porres", "Memoria Libre", "Blanco"),
    (11, 4):  ("San Carlos Borromeo", "Blanco"),
    (11, 6):  ("Santos Pedro Poveda, Inocencio de la Inmaculada y compañeros, mártires", "Rojo"),  # Espana
    (11, 9):  ("Dedicación de la Basílica de Letrán", "Fiesta", "Blanco"),
    (11, 10): ("San León Magno, papa y doctor", "Blanco"),
    (11, 11): ("San Martín de Tours, obispo", "Blanco"),
    (11, 12): ("San Josafat, obispo y mártir", "Rojo"),
    (11, 15): ("San Alberto Magno, obispo y doctor", "Memoria Libre", "Blanco"),
    (11, 16): ("Santa Margarita de Escocia / Santa Gertrudis", "Memoria Libre", "Blanco"),
    (11, 17): ("Santa Isabel de Hungría", "Blanco"),
    (11, 21): ("Presentación de la Virgen María", "Blanco"),
    (11, 22): ("Santa Cecilia, virgen y mártir", "Rojo"),
    (11, 23): ("San Clemente I / San Columbano", "Memoria Libre", "Blanco"),
    (11, 24): ("Santos Andrés Dung-Lac y compañeros, mártires", "Rojo"),
    (11, 30): ("San Andrés, Apóstol", "Fiesta", "Rojo"),
    # ── DICIEMBRE ──
    (12, 3):  ("San Francisco Javier", "Blanco"),
    (12, 4):  ("San Juan Damasceno", "Memoria Libre", "Blanco"),
    (12, 6):  ("San Nicolás, obispo", "Memoria Libre", "Blanco"),
    (12, 7):  ("San Ambrosio, obispo y doctor", "Blanco"),
    (12, 11): ("San Dámaso I, papa", "Memoria Libre", "Blanco"),
    (12, 12): ("Nuestra Señora de Guadalupe", "Memoria Libre", "Blanco"),
    (12, 13): ("Santa Lucía, virgen y mártir", "Rojo"),
    (12, 14): ("San Juan de la Cruz", "Blanco"),
    (12, 26): ("San Esteban, protomártir", "Fiesta", "Rojo"),
    (12, 27): ("San Juan, Apóstol y evangelista", "Fiesta", "Blanco"),
    (12, 28): ("Santos Inocentes, mártires", "Fiesta", "Rojo"),
    (12, 29): ("Santo Tomás Becket, obispo y mártir", "Memoria Libre", "Rojo"),
    (12, 31): ("San Silvestre I, papa", "Memoria Libre", "Blanco"),
}

ROMANS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
           "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
           "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII",
           "XXIX", "XXX", "XXXI", "XXXII", "XXXIII", "XXXIV"]

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
               "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def roman(n: int) -> str:
    return ROMANS[n] if 0 <= n < len(ROMANS) else str(n)


def easter(year: int) -> date:
    """Algoritmo de Gauss/Meeus para la fecha de Pascua."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def advent_start(year: int) -> date:
    """Primer Domingo de Adviento: 4to domingo antes de Navidad."""
    xmas = date(year, 12, 25)
    # isoweekday: Mon=1..Sun=7
    xmas_wd = xmas.isoweekday()  # 7 if Sunday
    if xmas_wd == 7:
        days_back = 28
    else:
        days_back = 21 + xmas_wd
    return xmas - timedelta(days=days_back)


def baptism_of_lord(year: int) -> date:
    """Bautismo del Senor: domingo despues de Epifania (6 ene).
    Si Epifania cae en domingo, Bautismo = lunes siguiente."""
    epi = date(year, 1, 6)
    if epi.isoweekday() == 7:  # Epiphany is Sunday
        return epi + timedelta(days=1)
    # Next Sunday after Jan 6
    days_to_sun = 7 - epi.isoweekday()
    return epi + timedelta(days=days_to_sun)


def week_of(start: date, current: date) -> int:
    """Semana transcurrida (1-based) desde start hasta current."""
    diff = (current - start).days
    return diff // 7 + 1


def get_ot_week_before_lent(d: date, year: int) -> int:
    """Calcula la semana del Tiempo Ordinario ANTES de Cuaresma.
    Bautismo del Senor = 1er Domingo del TO (cierra Navidad).
    Lunes despues = ferias de la Semana I.
    Siguiente domingo = II Domingo del TO."""
    baptism = baptism_of_lord(year)
    if d <= baptism:
        return 1
    diff = (d - baptism).days
    return diff // 7 + 1


def get_ot_week_after_pentecost(d: date, year: int) -> int:
    """Calcula la semana del TO despues de Pentecostes (perennial algorithm).

    Week 34 = Christ the King (Sunday before Advent). Count backwards from
    Christ the King Sunday to determine which OT week any date falls in.
    Weekdays (Mon-Sat) belong to the preceding Sunday's week. Works for any year.
    """
    adv = advent_start(year)
    # Christ the King = Sunday before Advent (always week 34)
    christ_king = adv - timedelta(days=7)
    # Anchor on the Sunday that "owns" this date
    # (isoweekday: Mon=1..Sun=7; Sun%7=0, Mon%7=1, ..., Sat%7=6)
    days_since_sunday = d.isoweekday() % 7
    week_sunday = d - timedelta(days=days_since_sunday)
    # Count Sundays between this week's Sunday and Christ the King
    weeks_to_ck = (christ_king - week_sunday).days // 7
    return max(1, 34 - weeks_to_ck)


def movable_feasts(year: int) -> dict:
    """Fiestas moviles que dependen de Pascua."""
    e = easter(year)
    pent = e + timedelta(days=49)
    feasts = {}

    # Santisima Trinidad: domingo despues de Pentecostes
    trinity = pent + timedelta(days=7)
    feasts[trinity] = ("Santísima Trinidad", "Solemnidad", "Blanco")

    # Corpus Christi: en Espana se celebra el domingo despues de Trinidad
    corpus = trinity + timedelta(days=7)
    feasts[corpus] = ("Santísimo Cuerpo y Sangre de Cristo (Corpus Christi)", "Solemnidad", "Blanco")

    # Sagrado Corazon de Jesus: viernes de la 3a semana despues de Pentecostes
    sacred_heart = pent + timedelta(days=19)
    feasts[sacred_heart] = ("Sagrado Corazón de Jesús", "Solemnidad", "Blanco")

    # Inmaculado Corazon de Maria: sabado despues del Sagrado Corazon
    feasts[sacred_heart + timedelta(days=1)] = ("Inmaculado Corazón de la Virgen María", "Memoria Obligatoria", "Blanco")

    # BVM Madre de la Iglesia: lunes despues de Pentecostes (desde 2018)
    bvm_madre = pent + timedelta(days=1)
    feasts[bvm_madre] = ("Bienaventurada Virgen María, Madre de la Iglesia", "Memoria Obligatoria", "Blanco")

    # Cristo Rey: ultimo domingo del TO (34a semana) = domingo antes de Adviento
    adv = advent_start(year)
    christ_king = adv - timedelta(days=7)
    feasts[christ_king] = ("Nuestro Señor Jesucristo, Rey del Universo", "Solemnidad", "Blanco")

    # Ascension: en Espana se celebra el domingo (7o de Pascua) = Pascua + 42
    ascension = e + timedelta(days=42)
    feasts[ascension] = ("La Ascensión del Señor", "Solemnidad", "Blanco")

    return feasts


def _get_base_day_level(d: date, year: int) -> int:
    """Get Art.59 precedence level of the base day (ignoring fixed feasts)."""
    e = easter(year)
    ash_wed = e - timedelta(days=46)
    pent = e + timedelta(days=49)
    adv = advent_start(year)
    xmas = date(year, 12, 25)
    baptism = baptism_of_lord(year)
    palm = e - timedelta(days=7)
    is_sunday = d.isoweekday() == 7

    # Movable feasts take precedence
    mov = movable_feasts(year)
    if d in mov:
        name, rank, _ = mov[d]
        season = determine_season(d, e, ash_wed, pent, adv, xmas, baptism)
        return get_precedence_level(name, rank, season, d, is_sunday)

    # Season-based classification
    if ash_wed <= d < e:
        if d >= palm:
            if is_sunday:
                return 2  # Palm Sunday
            if d.isoweekday() in (4, 5, 6):
                return 1  # Triduum
            return 2  # Mon-Wed Holy Week
        if d == ash_wed:
            return 2
        if is_sunday:
            return 2  # Lent Sunday
        return 9  # Lent feria

    if e <= d <= pent:
        if is_sunday:
            return 2
        if (d - e).days <= 7:
            return 2  # Easter Octave
        return 13  # Easter season feria

    if d >= adv:
        if is_sunday:
            return 2  # Advent Sunday
        if d.month == 12 and 17 <= d.day <= 24:
            return 9
        return 13

    if (d.month == 12 and d.day >= 25) or (d.month == 1 and d <= baptism):
        if is_sunday:
            return 6
        if (d.month == 12 and d.day >= 26) or (d.month == 1 and d.day <= 5):
            return 9
        return 13

    # Ordinary Time
    if is_sunday:
        return 6
    return 13


_transfers_cache = {}

def compute_transfers(year: int) -> dict:
    """Pre-compute solemnity transfers for a year (cached per year).
    Returns {transfer_date: (name, rank, color, original_date)}

    Rules (Art. 17-18):
    - Solemnity on Sunday of Advent/Lent/Easter -> Monday
    - Solemnity in Holy Week or Easter Octave -> Monday after Octave
    - San Jose on Palm Sunday -> Saturday before (Spain, Art.18)
    """
    if year in _transfers_cache:
        return _transfers_cache[year]

    e = easter(year)
    palm = e - timedelta(days=7)
    octave_end = e + timedelta(days=7)
    mon_after_octave = octave_end + timedelta(days=1)

    transfers = {}

    for (m, day_num), (name, rank, color) in FIXED_FEASTS.items():
        if rank != "Solemnidad":
            continue
        try:
            d = date(year, m, day_num)
        except ValueError:
            continue

        # I.2 solemnities (Navidad, Epifania) are never impeded
        if name in _LEVEL_I2_NAMES or name == "Natividad del Señor":
            continue

        # Spain-specific: Inmaculada on Advent Sunday is NOT transferred
        # (Vatican dispensation for Patrona de España — CEE calendar)
        if "Inmaculada" in name and d.isoweekday() == 7:
            continue

        base_level = _get_base_day_level(d, year)
        solemnity_level = 3  # I.3

        if base_level >= solemnity_level:
            continue  # Not impeded

        # Impeded — find transfer date
        if palm <= d <= octave_end:
            transfer_to = mon_after_octave
            # San Jose in Holy Week -> Saturday before Palm Sunday (Spain, Art.18)
            if ("José" in name or "Jose" in name) and palm <= d < e:
                transfer_to = palm - timedelta(days=1)
        elif d.isoweekday() == 7:
            transfer_to = d + timedelta(days=1)
        else:
            transfer_to = d + timedelta(days=1)

        # Ensure transfer date is free enough (level >= 3)
        safety = 0
        while safety < 7:
            tl = _get_base_day_level(transfer_to, year)
            if tl >= solemnity_level:
                break
            transfer_to += timedelta(days=1)
            safety += 1

        # Don't overwrite existing transfers
        while transfer_to in transfers:
            transfer_to += timedelta(days=1)

        transfers[transfer_to] = (name, rank, color, d)

    _transfers_cache[year] = transfers
    return transfers


def calculate(d: date) -> dict:
    """Calcula todos los datos liturgicos para una fecha."""
    y = d.year
    m = d.month
    day = d.day
    # isoweekday: 1=Mon..7=Sun
    wd = d.isoweekday()
    day_name = DAY_NAMES[wd - 1]
    is_sunday = wd == 7

    # ── Ano liturgico ──
    adv = advent_start(y)
    if d >= adv:
        lit_year = y + 1
    else:
        lit_year = y

    # Ciclo dominical
    rem = lit_year % 3
    sunday_cycle = {1: "A", 2: "B", 0: "C"}[rem]

    # Ciclo ferial
    weekday_cycle = "II" if lit_year % 2 == 0 else "I"

    # ── Fechas clave del ano civil ──
    e = easter(y)
    ash_wed = e - timedelta(days=46)
    pent = e + timedelta(days=49)
    holy_week_start = e - timedelta(days=7)  # Domingo de Ramos
    xmas = date(y, 12, 25)
    baptism = baptism_of_lord(y)

    # ── Check for transferred solemnities ──
    transfers = compute_transfers(y)
    if d in transfers:
        name, rank, color, original_date = transfers[d]
        season = determine_season(d, e, ash_wed, pent, adv, xmas, baptism)
        r = build_result(d, day_name, name, rank, season,
                         sunday_cycle, "", color, lit_year)
        r["transferred_from"] = original_date.isoformat()
        return r

    # ── Fiestas moviles y fijas (with precedence check per Art. 56) ──
    mov = movable_feasts(y)
    key = (m, day)
    mov_entry = mov.get(d)
    fix_entry = FIXED_FEASTS.get(key)

    # Skip fixed feasts that were transferred away
    impeded_dates = {orig for (_, _, _, orig) in transfers.values()}
    if fix_entry and d in impeded_dates:
        fix_entry = None

    # When both exist, higher precedence wins (lower level = higher precedence)
    if mov_entry and fix_entry:
        season = determine_season(d, e, ash_wed, pent, adv, xmas, baptism)
        mov_level = get_precedence_level(mov_entry[0], mov_entry[1], season, d, is_sunday)
        fix_level = get_precedence_level(fix_entry[0], fix_entry[1], season, d, is_sunday)
        if fix_level <= mov_level:
            mov_entry = None  # fixed feast takes precedence
        else:
            fix_entry = None  # movable feast takes precedence

    if mov_entry:
        name, rank, color = mov_entry
        season = determine_season(d, e, ash_wed, pent, adv, xmas, baptism)
        wdc = f"Año {weekday_cycle}" if "Ordinario" in season else ""
        r = build_result(d, day_name, name, rank, season,
                         sunday_cycle, wdc, color, lit_year)
        # Movable feasts in OT need ot_week for ferial reading lookup
        if "Ordinario" in season:
            if d < ash_wed:
                r["ot_week"] = get_ot_week_before_lent(d, y)
            else:
                r["ot_week"] = get_ot_week_after_pentecost(d, y)
        # Movable Memoria Obligatoria feasts need memorial fields for reading lookup
        if rank == "Memoria Obligatoria" and not is_sunday:
            r["memorial"] = name
            r["memorial_rank"] = rank
            r["memorial_color"] = color
            r["readings_source"] = "propias"
        return r

    if fix_entry:
        name, rank, color = fix_entry
        season = determine_season(d, e, ash_wed, pent, adv, xmas, baptism)
        return build_result(d, day_name, name, rank, season,
                            sunday_cycle, "", color, lit_year)

    # ── Temporada liturgica ──
    result = {"date": d.isoformat(), "day_name": day_name, "sunday_cycle": f"Ciclo {sunday_cycle}",
              "liturgical_year": lit_year}

    # -- Cuaresma / Semana Santa --
    if ash_wed <= d < e:
        if d >= holy_week_start:
            result["season"] = "Semana Santa"
            result["weekday_cycle"] = ""
            if is_sunday:
                result["name"] = "Domingo de Ramos en la Pasión del Señor"
                result["color"] = "Rojo"
                result["rank"] = "Solemnidad"
            elif wd == 4:  # Thursday
                result["name"] = "Jueves Santo - La Cena del Señor"
                result["color"] = "Blanco"
                result["rank"] = "Solemnidad"
            elif wd == 5:  # Friday
                result["name"] = "Viernes Santo - La Pasión del Señor"
                result["color"] = "Rojo"
                result["rank"] = "Solemnidad"
            elif wd == 6:  # Saturday
                result["name"] = "Sábado Santo - Vigilia Pascual"
                result["color"] = "Blanco"
                result["rank"] = "Solemnidad"
            else:
                result["name"] = f"{day_name} Santo"
                result["color"] = "Morado"
                result["rank"] = "Feria"
        else:
            result["season"] = "Cuaresma"
            result["color"] = "Morado"
            result["weekday_cycle"] = ""
            if d == ash_wed:
                result["name"] = "Miércoles de Ceniza"
                result["rank"] = "Feria"
            elif d < ash_wed + timedelta(days=4):
                result["name"] = f"{day_name} después de Ceniza"
                result["rank"] = "Feria"
            else:
                # Ceniza siempre es miercoles → I Domingo de Cuaresma = ceniza + 4
                first_sun_lent = ash_wed + timedelta(days=4)
                week_num = week_of(first_sun_lent, d)
                if is_sunday:
                    result["name"] = f"{roman(week_num)} Domingo de Cuaresma"
                    result["rank"] = "Domingo"
                    if week_num == 4:
                        result["color"] = "Rosa"  # Laetare
                else:
                    result["name"] = f"{day_name} de la {roman(week_num)} Semana de Cuaresma"
                    result["rank"] = "Feria"

            # Memorias suprimidas en Cuaresma, pero Fiestas se celebran
            if key in OBLIGATORY_MEMORIALS:
                mem_name, mem_rank, _ = parse_memorial(OBLIGATORY_MEMORIALS[key])
                if mem_rank != "Fiesta":
                    result["memorial_note"] = f"Memoria suprimida en Cuaresma: {mem_name}"

    # -- Pascua --
    elif e <= d <= pent:
        result["season"] = "Tiempo de Pascua"
        result["color"] = "Blanco"
        result["weekday_cycle"] = ""
        week_num = week_of(e, d)
        if is_sunday:
            if week_num == 1:
                result["name"] = "Domingo de Resurrección"
                result["rank"] = "Solemnidad"
            elif week_num == 8:
                result["name"] = "Domingo de Pentecostés"
                result["color"] = "Rojo"
                result["rank"] = "Solemnidad"
            else:
                result["name"] = f"{roman(week_num)} Domingo de Pascua"
                result["rank"] = "Domingo"
        else:
            if week_num == 1:
                result["name"] = f"{day_name} de la Octava de Pascua"
                result["rank"] = "Solemnidad"
            else:
                result["name"] = f"{day_name} de la {roman(week_num)} Semana de Pascua"
                result["rank"] = "Feria"
                # Memorias y fiestas en Pascua (fuera de la Octava)
                if key in OBLIGATORY_MEMORIALS:
                    mem_name, mem_rank, mem_color = parse_memorial(OBLIGATORY_MEMORIALS[key])
                    result["memorial"] = mem_name
                    result["memorial_rank"] = mem_rank
                    result["memorial_color"] = mem_color
                    result["readings_source"] = "propias" if mem_rank == "Fiesta" else "feriales"

    # -- Adviento --
    elif d >= adv and d < xmas:
        result["season"] = "Adviento"
        result["color"] = "Morado"
        result["weekday_cycle"] = ""
        week_num = week_of(adv, d)
        if is_sunday:
            result["name"] = f"{roman(week_num)} Domingo de Adviento"
            result["rank"] = "Domingo"
            if week_num == 3:
                result["color"] = "Rosa"  # Gaudete
        else:
            result["name"] = f"{day_name} de la {roman(week_num)} Semana de Adviento"
            result["rank"] = "Feria"
            # From Dec 17-24: special ferial days
            if m == 12 and 17 <= day <= 24:
                result["name"] = f"Feria del 17-24 de Diciembre ({day} dic)"
                result["rank"] = "Feria privilegiada"
                # Suppress obligatory memorials (Art.59 III.9) — Fiestas still prevail
                if key in OBLIGATORY_MEMORIALS:
                    mem_name, mem_rank, _ = parse_memorial(OBLIGATORY_MEMORIALS[key])
                    if mem_rank != "Fiesta":
                        result["memorial_note"] = f"Memoria suprimida en feria privilegiada: {mem_name}"
            else:
                # Ordinary Advent ferias (before Dec 17): memorials appear normally
                if key in OBLIGATORY_MEMORIALS:
                    mem_name, mem_rank, mem_color = parse_memorial(OBLIGATORY_MEMORIALS[key])
                    result["memorial"] = mem_name
                    result["memorial_rank"] = mem_rank
                    result["memorial_color"] = mem_color
                    result["readings_source"] = "propias" if mem_rank == "Fiesta" else "feriales"

    # -- Navidad --
    elif (m == 12 and day >= 25) or (m == 1 and d <= baptism):
        result["season"] = "Tiempo de Navidad"
        result["color"] = "Blanco"
        result["weekday_cycle"] = ""
        if m == 12 and day == 25:
            result["name"] = "Natividad del Señor"
            result["rank"] = "Solemnidad"
        elif m == 12 and 26 <= day <= 31:
            # Octava de Navidad
            if key in OBLIGATORY_MEMORIALS:
                mem_name, mem_rank, mem_color = parse_memorial(OBLIGATORY_MEMORIALS[key])
                is_feast = mem_rank == "Fiesta"
                result["name"] = mem_name
                result["rank"] = "Fiesta" if is_feast else "Feria"
                result["color"] = mem_color if is_feast else "Blanco"
                if not is_feast:
                    result["memorial"] = mem_name
                    result["memorial_rank"] = mem_rank
                    result["memorial_color"] = mem_color
            else:
                result["name"] = f"Día {day - 24} de la Octava de Navidad"
                result["rank"] = "Feria"
            # Sagrada Familia: domingo en la Octava de Navidad
            if is_sunday:
                result["name"] = "La Sagrada Familia de Jesús, María y José"
                result["rank"] = "Fiesta"
            # Si Navidad cae en domingo, no hay otro domingo en la octava → Sagrada Familia = 30 dic
            elif xmas.isoweekday() == 7 and day == 30:
                result["name"] = "La Sagrada Familia de Jesús, María y José"
                result["rank"] = "Fiesta"
        elif m == 1 and day == 1:
            result["name"] = "Santa María, Madre de Dios"
            result["rank"] = "Solemnidad"
        elif m == 1 and day < 6:
            if is_sunday:
                result["name"] = "II Domingo de Navidad"
                result["rank"] = "Domingo"
            else:
                result["name"] = f"Feria del Tiempo de Navidad ({day} enero)"
                result["rank"] = "Feria"
        elif m == 1 and day == 6:
            result["name"] = "Epifanía del Señor"
            result["rank"] = "Solemnidad"
        elif d == baptism:
            result["name"] = "El Bautismo del Señor"
            result["rank"] = "Fiesta"
        else:
            result["name"] = f"Feria del Tiempo de Navidad ({day} enero)"
            result["rank"] = "Feria"

    # -- Tiempo Ordinario --
    else:
        result["season"] = "Tiempo Ordinario"
        result["color"] = "Verde"
        result["weekday_cycle"] = f"Año {weekday_cycle}"

        # Determine if before Lent or after Pentecost
        if d < ash_wed:
            # Before Lent: count from Baptism of the Lord
            week_num = get_ot_week_before_lent(d, y)
        else:
            # After Pentecost
            week_num = get_ot_week_after_pentecost(d, y)

        result["ot_week"] = week_num

        if is_sunday:
            result["name"] = f"{roman(week_num)} Domingo del Tiempo Ordinario"
            result["rank"] = "Domingo"
            # Art.10: Fiestas del Senor replace TO Sundays
            if key in FIXED_FEASTS:
                fname, frank, fcolor = FIXED_FEASTS[key]
                if frank == "Fiesta" and fname in FIESTAS_DEL_SENOR:
                    result["name"] = fname
                    result["rank"] = "Fiesta"
                    result["color"] = fcolor
        else:
            result["name"] = f"{day_name} de la {roman(week_num)} Semana del Tiempo Ordinario"
            result["rank"] = "Feria"

        # Memorias y fiestas en TO
        if key in OBLIGATORY_MEMORIALS and not is_sunday:
            mem_name, mem_rank, mem_color = parse_memorial(OBLIGATORY_MEMORIALS[key])
            result["memorial"] = mem_name
            result["memorial_rank"] = mem_rank
            result["memorial_color"] = mem_color
            result["readings_source"] = "propias" if mem_rank == "Fiesta" else "feriales"
            # Fiestas promote the day rank (Art.59 II.7) so lookup uses santos path
            if mem_rank == "Fiesta":
                result["name"] = mem_name
                result["rank"] = "Fiesta"
                result["color"] = mem_color

    # ── Post-procesado: Fiestas prevalecen sobre ferias no privilegiadas ──
    if key in OBLIGATORY_MEMORIALS and not is_sunday and result.get("season") != "Tiempo Ordinario":
        mem_name, mem_rank, mem_color = parse_memorial(OBLIGATORY_MEMORIALS[key])
        if mem_rank == "Fiesta":
            is_privileged = (
                "Ceniza" in result.get("name", "") or          # Miércoles de Ceniza (Art. 59 I.2) vence a la Cátedra de San Pedro (22-II-2023)
                result.get("season") == "Semana Santa" or
                result.get("rank") in ("Solemnidad", "Feria privilegiada") or
                (result.get("season") == "Tiempo de Pascua" and week_of(e, d) == 1)
            )
            if not is_privileged:
                result.update(name=mem_name, rank="Fiesta", color=mem_color,
                              memorial=mem_name, memorial_rank="Fiesta",
                              memorial_color=mem_color, readings_source="propias")

    return result


def determine_season(d: date, e: date, ash_wed: date, pent: date,
                     adv: date, xmas: date, baptism: date) -> str:
    """Helper to determine season name for fixed/movable feasts."""
    if ash_wed <= d < e:
        return "Cuaresma" if d < e - timedelta(days=7) else "Semana Santa"
    if e <= d <= pent:
        return "Tiempo de Pascua"
    if d >= adv and d < xmas:
        return "Adviento"
    if (d.month == 12 and d.day >= 25) or (d.month == 1 and d <= baptism):
        return "Tiempo de Navidad"
    return "Tiempo Ordinario"


def parse_memorial(mem: tuple) -> tuple:
    """Extrae (nombre, rango, color) de una entrada de OBLIGATORY_MEMORIALS.
    2 elementos = memoria obligatoria, 3 elementos = rango explícito
    ("Fiesta" o "Memoria Libre")."""
    if len(mem) == 3:
        return mem[0], mem[1], mem[2]  # name, "Fiesta", color
    return mem[0], "Memoria Obligatoria", mem[1]  # name, rank, color


def build_result(d: date, day_name: str, name: str, rank: str, season: str,
                 sunday_cycle: str, weekday_cycle: str, color: str,
                 lit_year: int) -> dict:
    return {
        "date": d.isoformat(),
        "day_name": day_name,
        "name": name,
        "rank": rank,
        "season": season,
        "sunday_cycle": f"Ciclo {sunday_cycle}",
        "weekday_cycle": weekday_cycle,
        "color": color,
        "liturgical_year": lit_year,
    }


# ── Leccionario lookup ──────────────────────────────────────────────────────

_leccionario_cache = None

def _load_leccionario():
    """Load Leccionario_CL.json (cached).

    Este fichero vive en DOS layouts distintos y el sync lo copia tal cual:
      - skill:          scripts/liturgia.py  +  ../data/
      - lecturasdeldia: liturgia.py          +  ./data/
    Por eso se prueban ambos. Con una sola ruta, en el layout equivocado esta
    funcion devolvia None SIEMPRE y lookup_readings daba vacio para todos los
    dias, en silencio (07-08-2026: dos auditorias concluyeron que el sitio
    entero estaba sin lecturas).
    """
    global _leccionario_cache
    if _leccionario_cache is not None:
        return _leccionario_cache
    aqui = os.path.dirname(os.path.abspath(__file__))
    for base in (os.path.join(aqui, "..", "data"), os.path.join(aqui, "data")):
        data_path = os.path.join(base, "Leccionario_CL.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                _leccionario_cache = json.load(f)
            return _leccionario_cache
    return None


# Spanish day name (accented, as in DAY_NAMES) → leccionario key fragment (ASCII).
# Keys mirror day_name so lookups keep matching; values are the JSON key fragments.
_DAY_MAP = {
    "Lunes": "lunes", "Martes": "martes", "Miércoles": "miercoles",
    "Jueves": "jueves", "Viernes": "viernes", "Sábado": "sabado",
}


def _roman_to_int(s: str) -> int:
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50}
    total = prev = 0
    for c in reversed(s.upper()):
        v = vals.get(c, 0)
        total += -v if v < prev else v
        prev = v
    return total


def _build_dominical_key(result: dict) -> str | None:
    """Map calculate() output to a dominical leccionario key."""
    name = result.get("name", "")
    season = result.get("season", "")

    # Triduo Pascual + Easter
    if "Ramos" in name: return "ramos"
    if "Jueves Santo" in name: return "jueves_santo"
    if "Viernes Santo" in name: return "viernes_santo"
    if "Vigilia Pascual" in name or "Sábado Santo" in name or "Sabado Santo" in name: return "vigilia_pascual"  # multi-entry: vigilia_pascual_lectura_1..7 + vigilia_pascual
    if "Resurreccion" in name or "Resurrección" in name: return "pascua_resurreccion"

    # Solemnities after Easter
    if "Pentecostés" in name or "Pentecostes" in name: return "pentecostes"
    if "Trinidad" in name: return "trinidad"
    if "Corpus" in name or "Cuerpo" in name: return "corpus"
    if "Sagrado Corazón" in name or "Sagrado Corazon" in name: return "sagrado_corazon"
    if "Ascensión" in name or "Ascension" in name: return "ascension"
    if "Cristo Rey" in name or "Rey del Universo" in name: return "cristo_rey"

    # Christmas cycle
    if "Natividad" in name and "San Juan" not in name and "Virgen" not in name and "María" not in name: return "natividad_dia"
    if "Epifanía" in name or "Epifania" in name: return "epifania"
    if "Bautismo" in name: return "bautismo"
    if "Sagrada Familia" in name: return "sagrada_familia"
    if "Madre de Dios" in name: return "maria_madre_dios"
    if "Domingo de Navidad" in name: return "navidad_post_2"

    # Major feasts/solemnities with proper readings in dominical volumes
    if "Presentacion" in name or "Presentación" in name: return "presentacion"
    if "San Jose" in name or "San José" in name: return "san_jose"
    if "Anunciacion" in name or "Anunciación" in name: return "anunciacion"
    if "Transfiguracion" in name or "Transfiguración" in name: return "transfiguracion"
    if "Asuncion" in name or "Asunción" in name: return "asuncion"
    if "Exaltacion" in name or "Exaltación" in name: return "exaltacion_cruz"
    if "Todos los Santos" in name: return "todos_santos"
    if "Fieles Difuntos" in name: return "fieles_difuntos"
    if "Inmaculada" in name: return "inmaculada"
    if "Pedro y Pablo" in name: return "pedro_y_pablo"
    if "Santiago" in name and ("Patrón" in name or "Patron" in name): return "santiago"
    if "Pilar" in name: return "pilar"
    if "Inmaculado Corazon" in name or "Inmaculado Corazón" in name: return "inmaculado_corazon"

    # Extract week number from name
    num_match = re.search(r'\b([IVXL]+)\b', name)
    num = _roman_to_int(num_match.group(1)) if num_match else 0

    if "Adviento" in season or "Adviento" in name:
        return f"adviento_{num}" if num else None
    if "Cuaresma" in season or "Cuaresma" in name:
        return f"cuaresma_{num}" if num else None
    if "Pascua" in season or "Pascua" in name:
        return f"pascua_{num}" if num else None
    if "Ordinario" in season:
        ot = result.get("ot_week", num)
        return f"to_{ot}" if ot else None

    return None


def _build_ferial_to_key(result: dict) -> str | None:
    """Map calculate() output to a ferial TO leccionario key."""
    ot_week = result.get("ot_week")
    if not ot_week:
        return None
    day_name = result.get("day_name", "")
    dia = _DAY_MAP.get(day_name)
    if not dia:
        return None
    return f"{ot_week}_{dia}"


def _build_ferial_fuerte_key(result: dict) -> str | None:
    """Map calculate() output to a ferial fuerte leccionario key."""
    name = result.get("name", "")
    season = result.get("season", "")
    day_name = result.get("day_name", "")
    d = date.fromisoformat(result["date"])

    dia = _DAY_MAP.get(day_name)

    # Movable Memoria Obligatoria feasts with proper readings stored here
    # (name-keyed, not season/date-derived).
    if "Madre de la Iglesia" in name:
        return "maria_madre_iglesia"

    # Ash Wednesday itself (not post-ceniza ferias like "Jueves después de Ceniza")
    if "Ceniza" in name and "después" not in name.lower() and "despues" not in name.lower():
        return "ceniza"
    # Post-ceniza ferias (Thu/Fri/Sat after Ash Wednesday)
    if "después de Ceniza" in name or "despues de Ceniza" in name:
        if dia:
            return f"cuaresma_0_{dia}"

    # Semana Santa days (Lunes/Martes/Miércoles Santo)
    if season == "Semana Santa" and dia:
        return f"cuaresma_6_{dia}"

    # Octava de Pascua (week after Easter Sunday) — NOT Christmas Octave
    if "Octava" in name and season == "Tiempo de Pascua" and dia:
        return f"pascua_0_{dia}"

    # Dec 17-24 privileged ferias
    if "17-24" in name or "Feria privilegiada" in result.get("rank", ""):
        if season == "Adviento" and d.month == 12 and 17 <= d.day <= 24:
            return f"navidad_{d.day}_dic"

    # Navidad ferias (Jan 2-9, Dec 29-31)
    if season == "Tiempo de Navidad":
        if d.month == 1 and 2 <= d.day <= 12:
            return f"navidad_{d.day}_ene"
        if d.month == 12 and 29 <= d.day <= 31:
            return f"navidad_{d.day}_dic"

    # Extract week number
    num_match = re.search(r'\b([IVXL]+)\b', name)
    num = _roman_to_int(num_match.group(1)) if num_match else 0

    season_map = {
        "Adviento": "adviento",
        "Cuaresma": "cuaresma",
        "Tiempo de Pascua": "pascua",
        "Tiempo de Navidad": "navidad",
    }
    season_key = season_map.get(season)
    if not season_key or not dia:
        return None

    if num:
        return f"{season_key}_{num}_{dia}"
    return None


# Proper gospel overrides for movable Memoria Obligatoria feasts
# (no fixed santos entry — date changes each year)
MOVABLE_MEMORIAL_GOSPEL = {
    "Bienaventurada Virgen María, Madre de la Iglesia": {
        "titulo": "Ahí tienes a tu hijo. Ahí tienes a tu madre",
        "cita": "Juan 19, 25-27",
        "texto": (
            "En aquel tiempo, junto a la cruz de Jesús estaban su madre, "
            "la hermana de su madre, María, la de Cleofás, y María, la Magdalena.\n"
            "Jesús, al ver a su madre y cerca al discípulo que tanto quería, "
            "dijo a su madre:\n"
            "—«Mujer, ahí tienes a tu hijo.»\n"
            "Luego, dijo al discípulo:\n"
            "—«Ahí tienes a tu madre.»\n"
            "Y desde aquella hora, el discípulo la recibió en su casa."
        ),
    },
    "Inmaculado Corazón de la Virgen María": {
        "titulo": "Tu padre y yo te buscábamos angustiados",
        "cita": "Lucas 2, 41-51",
        "texto": (
            "Los padres de Jesús solían ir cada año a Jerusalén "
            "por las fiestas de Pascua.\n"
            "Cuando Jesús cumplió doce años, subieron a la fiesta según la costumbre "
            "y, cuando terminó, se volvieron; pero el niño Jesús se quedó en Jerusalén, "
            "sin que lo supieran sus padres.\n"
            "Éstos, creyendo que estaba en la caravana, hicieron una jornada "
            "y se pusieron a buscarlo entre los parientes y conocidos; "
            "al no encontrarlo, se volvieron a Jerusalén en su busca.\n"
            "A los tres días, lo encontraron en el templo, sentado en medio de los maestros, "
            "escuchándolos y haciéndoles preguntas; "
            "todos los que le oían quedaban asombrados de su talento "
            "y de las respuestas que daba.\n"
            "Al verlo, se quedaron atónitos, y le dijo su madre:\n"
            "—«Hijo, ¿por qué nos has tratado así? "
            "Mira que tu padre y yo te buscábamos angustiados.»\n"
            "Él les contestó:\n"
            "—«¿Por qué me buscabais? "
            "¿No sabíais que yo debía estar en la casa de mi Padre?»\n"
            "Pero ellos no comprendieron lo que quería decir.\n"
            "Él bajó con ellos a Nazaret y siguió bajo su autoridad.\n"
            "Su madre conservaba todo esto en su corazón."
        ),
    },
}

# Aclamación propia que acompaña a esos evangelios (CEE, Leccionario IV).
MOVABLE_MEMORIAL_ACLAMACION = {
    "Inmaculado Corazón de la Virgen María": {
        "tipo": "aleluya",
        "cita": "Cf. Lc 2, 19",
        "texto": "Bienaventurada Virgen María, que conservaba la palabra de Dios, "
                 "meditándola en su corazón.",
    },
}


# El mismo evangelio en euskera: el del libro vigente (MEZAKO IRAKURGAIAK MMXXI,
# IV, extraído por tools/pipeline/leccionario/bizkaiera_pdf_lecturas.py). Hasta
# el 2026-10-24 la página vasca recibía el castellano de arriba. Eleizaren Ama
# lleva en el libro vasco Jn 19, 25-34, no 25-27: es el del día en euskera.
MOVABLE_MEMORIAL_GOSPEL_EU = {
    "Bienaventurada Virgen María, Madre de la Iglesia": {  # IRAKURGAIAK 4 BIZK.pdf#p103
        "titulo": 'Horra hor zure semea! Horra hor zure ama!',
        "cita": "Jn 19, 25-34",
        "texto": (
            '\tAldi haretan, Jesusen kurutzearen ondoan egozan haren ama, bere amaren ahizta, Maria Kleofasena eta Maria Magdalena. Jesusek, bere ama eta, beronen ondoan, maite eban ikaslea ikusirik, esan eutson amari: «Emakume, horra hor zure semea!» Gero, ikasleari esan eutson: «Horra hor zure ama!»\n'
            '\tEta harrezkero ikasleak bere etxean hartu eban.\n'
            '\tOndoren, Jesusek, dana betea zala jakinik, Liburu Santuak esana guztiz bete zedin, esan eban: «Egarri naz!»\n'
            '\tBazan han ozpinez betetako pitxar bat. Orduan, belakia ozpinetan busti eta, kainaberari ertzean erantsiz, ahora hurreratu eutsoen. Ozpina hartu ebanean, Jesusek esan eban: «Bete da dana!» Eta, burua makurtuz, azken arnasa emon eban.\n'
            '\tPazko-jairako prestaketa-eguna zan, eta judeguek ez eben gura zapatuan gorpuak kurutzean gelditzerik, ze, zapatu ha oso jaiegun handia zan. Horregaitik, kurutzeratuei berna-hazurrak apurtu eta handik kentzeko eskatu eutsoen Pilatori.\n'
            '\tJoan ziran, bada, gudariak eta berna-hazurrak hausi eutsiezan Jesusegaz kurutzean jositako biei; baina, Jesusengana heldu ziranean, ordurako hilda egoala ikusirik, ez eutsoen berna-hazurrik hausi, ezpada ze, gudari batek lantzaz saihetsa zulatu eutson, eta bat-batean odolak eta urak urten eben.'
        ),
    },
    "Inmaculado Corazón de la Virgen María": {  # IRAKURGAIAK 4 BIZK.pdf#p104
        "titulo": 'Bere bihotzean gordetzen ebazan gauza honeek guztiak.',
        "cita": "Lk 2, 41-51",
        "texto": (
            '\tJesusen gurasoak Jerusalemera joaten ziran urtero erromes Pazko-jaietan. Jesusek hamabi urte bete zituanean, Jerusalemera igon eben jaietara, ohitura zan lez. Jaiegunak amaiturik gurasoak etxerantz abiatu ziranean, Jesus umea Jerusalemen gelditu zan, eurak jakin barik. Erromeskideen artean etorrelakoan, egun bateko bidea egin ostean, haren bila hasi ziran taldeko senideen eta ezagunen artean. Eta aurkitzen ez ebenez, Jerusalemera bihurtu ziran haren bila.\n'
            '\tHiru egunen buruan, tenpluan aurkitu eben, irakasleen artean jesarrita, hareei entzuten eta itaunka. Entzuten eutsoen guztiak harrituta egozan erantzunetan erakusten eban argitasunagaitik. Gurasoak, ikusi ebenean, zur eta lur gelditu ziran, eta amak esan eutson: «Seme, baina zergaitik egin deuskuzu hori? Begira zelako atsekabez ibili garan aita eta biok zure bila!» Harek erantzun eutsen: «Zergaitik ibili zarie nire bila? Ez ete zenkien Nik neure Aitaren etxean egon behar dodana?» Hareek, ostera, ez eben ulertu zer esan gura eutsen.\n'
            '\tJesus Nazaretera jatsi zan eurakaz, eta euren menpean bizi zan. Haren amak bere bihotzean gordetzen zituan gauza honeek guztiok.'
        ),
    },
}

# Su aclamación en euskera: la que el IV imprime pegada a ese evangelio.
MOVABLE_MEMORIAL_ACLAMACION_EU = {
    "Inmaculado Corazón de la Virgen María": {  # IRAKURGAIAK 4 BIZK.pdf#p104
        "tipo": "aleluia",
        "cita": "Lk 2, 19",
        "texto": "Zorionekoa Maria Birjina, gogoan jasotzen ebazan-eta gauza honeek "
                 "guztiak, bihotzean hausnartuz.",
    },
}


def is_empty_reading(r) -> bool:
    """True when a reading dict has no usable text (empty or unmatched)."""
    if not isinstance(r, dict):
        return True
    if r.get("unmatched"):
        return True
    return not (r.get("texto") or "").strip()


def lookup_readings(result: dict, cache=None) -> dict | None:
    """Maps calculate() result to leccionario readings.

    `cache` lets callers inject an alternate leccionario (e.g. the Basque
    Lezionarioa). When None, falls back to the global Spanish cache.
    """
    lec = cache if cache is not None else _load_leccionario()
    if not lec:
        return None

    d = date.fromisoformat(result["date"])
    season = result.get("season", "")
    rank = result.get("rank", "")
    is_sunday = result.get("day_name") == "Domingo"
    cycle = result.get("sunday_cycle", "").replace("Ciclo ", "")
    wdc = result.get("weekday_cycle", "").replace("Año ", "").replace("Ano ", "")
    memorial = result.get("memorial")
    readings_source = result.get("readings_source")

    # 1. Santos with proper readings (Fiestas only)
    # Skip for movable memorials (their date doesn't match any fixed santos entry)
    if memorial and readings_source == "propias" and memorial not in MOVABLE_MEMORIAL_GOSPEL:
        key = f"{d.month:02d}-{d.day:02d}"
        if key in lec.get("santos", {}):
            santo = lec["santos"][key]
            # Only return if it has actual reading text (not just refs)
            if any(isinstance(santo.get(k), dict) and 'texto' in santo.get(k, {})
                   for k in ('primera', 'salmo', 'evangelio')):
                return santo

    # 2. Dominical (Sundays + Solemnities + Fiestas)
    # Skip dominical path for memorial Fiestas with propias that had no inline text
    # (they should use santos refs, not generic Sunday readings)
    is_memorial_fiesta = memorial and readings_source == "propias" and rank == "Fiesta"
    if is_sunday or rank in ("Solemnidad", "Fiesta"):
        if not is_memorial_fiesta:
            day_key = _build_dominical_key(result)
            if day_key and cycle in lec.get("dominical", {}):
                if day_key in lec["dominical"][cycle]:
                    entry = lec["dominical"][cycle][day_key]
                    # Vigilia Pascual: merge 7 OT lectura entries into result
                    if day_key == "vigilia_pascual":
                        vigilia_lecturas = []
                        for i in range(1, 8):
                            lk = f"vigilia_pascual_lectura_{i}"
                            if lk in lec["dominical"][cycle]:
                                vigilia_lecturas.append(lec["dominical"][cycle][lk])
                        if vigilia_lecturas:
                            entry = dict(entry)
                            entry["vigilia_lecturas"] = vigilia_lecturas
                    return entry
        # For non-Sunday Solemnidades in strong seasons without dominical match,
        # try ferial_fuerte BEFORE santos (e.g., Easter octave days)
        if not is_sunday and season in ("Cuaresma", "Semana Santa", "Tiempo de Pascua", "Adviento", "Tiempo de Navidad"):
            ff_key = _build_ferial_fuerte_key(result)
            if ff_key and ff_key in lec.get("ferial_fuerte", {}):
                return lec["ferial_fuerte"][ff_key]
        # Fallback: santos by date for Fiestas/Solemnidades (including Sunday Solemnidades
        # like Santiago or Asunción when they fall on Sunday and dominical has no cycle-specific entry)
        # For transferred solemnities, use the canonical date (e.g., San José 03-19 → 03-20)
        santos_key = f"{d.month:02d}-{d.day:02d}"
        if result.get("transferred_from"):
            orig = date.fromisoformat(result["transferred_from"])
            santos_key = f"{orig.month:02d}-{orig.day:02d}"
        if santos_key in lec.get("santos", {}):
            santo = lec["santos"][santos_key]
            if any(isinstance(santo.get(k), dict) and santo.get(k, {})
                   for k in ('primera', 'salmo', 'evangelio')):
                return santo

    # 3. Ferial strong seasons (also fallback for Solemnidades not found above, e.g. Octava)
    # Note: no memorial gospel override here — strong-season ferial readings
    # always prevail over memorial propias (unlike Ordinary Time).
    if season in ("Cuaresma", "Semana Santa", "Tiempo de Pascua", "Adviento", "Tiempo de Navidad"):
        if not is_sunday:
            day_key = _build_ferial_fuerte_key(result)
            if day_key and day_key in lec.get("ferial_fuerte", {}):
                return lec["ferial_fuerte"][day_key]

    # 3.5 Movable Memoria Obligatoria with proper readings stored in
    # ferial_fuerte (e.g. María Madre de la Iglesia, lunes después de
    # Pentecostés — falls in Tiempo Ordinario, so the strong-season
    # ferial_fuerte branches above never reach it).
    if memorial and readings_source == "propias" and not is_sunday:
        ff_key = _build_ferial_fuerte_key(result)
        if ff_key and ff_key in lec.get("ferial_fuerte", {}):
            return lec["ferial_fuerte"][ff_key]

    # 4. Ferial TO
    if season == "Tiempo Ordinario" and not is_sunday:
        day_key = _build_ferial_to_key(result)
        if day_key:
            primera_salmo = lec.get("ferial_to", {}).get(wdc, {}).get(day_key)
            evangelio_data = lec.get("ferial_to", {}).get("evangelio", {}).get(day_key)
            if primera_salmo or evangelio_data:
                merged = {}
                if primera_salmo:
                    for k in ('primera', 'salmo', 'day_name'):
                        if k in primera_salmo:
                            merged[k] = primera_salmo[k]
                if evangelio_data:
                    # La aclamación va con el evangelio ferial (igual en año
                    # par e impar); si un memorial cambia el evangelio, abajo
                    # se cambia o se quita con él.
                    for k in ('aclamacion', 'evangelio'):
                        if k in evangelio_data:
                            merged[k] = evangelio_data[k]
                if any(k in merged for k in ('primera', 'evangelio')):
                    # Memorial gospel override: when a memorial has proper readings
                    # use the saint's gospel over the ferial one.
                    # Saints with comun_ref only override if evangelio_propio is set
                    # (e.g., Teresa de Jesús, Marta/María/Lázaro, Vianney, Kolbe).
                    if memorial and readings_source == "feriales":
                        santos_key = f"{d.month:02d}-{d.day:02d}"
                        santo = lec.get("santos", {}).get(santos_key, {})
                        if santo.get("primera_obligatoria"):
                            # «En esta memoria la primera lectura es obligatoria.
                            # El Evangelio, ordinariamente, de la feria» (Timoteo
                            # y Tito, Bernabé): primera y su salmo del santo.
                            for k in ('primera', 'salmo'):
                                if isinstance(santo.get(k), dict) and santo[k].get("texto"):
                                    merged[k] = santo[k]
                        elif not santo.get("comun_ref") or santo.get("evangelio_propio"):
                            santo_ev = santo.get("evangelio")
                            if isinstance(santo_ev, dict) and santo_ev.get("cita"):
                                merged["evangelio"] = santo_ev
                                # La aclamación ferial no casa con otro evangelio.
                                santo_acl = santo.get("aclamacion")
                                if isinstance(santo_acl, dict) and santo_acl.get("texto"):
                                    merged["aclamacion"] = santo_acl
                                else:
                                    merged.pop("aclamacion", None)
                    # Movable memorial gospel override (no santos entry — date varies)
                    if memorial and readings_source == "propias":
                        # El idioma lo dice el leccionario: el vasco no recibe
                        # el texto castellano (ni su aclamación, sin fuente vasca).
                        eu = (lec.get("meta") or {}).get("lang") == "eu"
                        mov_ev = (MOVABLE_MEMORIAL_GOSPEL_EU if eu else MOVABLE_MEMORIAL_GOSPEL).get(memorial)
                        if mov_ev:
                            merged["evangelio"] = mov_ev
                            mov_acl = (MOVABLE_MEMORIAL_ACLAMACION_EU if eu
                                       else MOVABLE_MEMORIAL_ACLAMACION).get(memorial)
                            if mov_acl:
                                merged["aclamacion"] = mov_acl
                            else:
                                merged.pop("aclamacion", None)
                    return merged
                return None

    return None


def format_readings(readings: dict) -> str:
    """Format readings for CLI output."""
    lines = []
    lines.append("")
    lines.append("  LECTURAS (CEE — Leccionario offline)")
    lines.append("  " + "-" * 50)

    # Vigilia Pascual: render 7 OT readings first
    if "vigilia_lecturas" in readings:
        for i, lec in enumerate(readings["vigilia_lecturas"], 1):
            p = lec.get("primera", {})
            s = lec.get("salmo", {})
            label = f"LECTURA {i}ª"
            lines.append(f"  {label:14s} {p.get('cita', '')}")
            if p.get('titulo'):
                lines.append(f"  {'':14s} {p['titulo']}")
            if s.get('cita'):
                lines.append(f"  {'SALMO':14s} {s.get('cita', '')}")
        lines.append("  " + "-" * 30)

    for key, label in [('primera', '1a LECTURA'), ('salmo', 'SALMO'),
                       ('segunda', 'EPÍSTOLA'), ('evangelio', 'EVANGELIO')]:
        r = readings.get(key)
        if not r or not isinstance(r, dict):
            continue
        cita = r.get('cita', '')
        titulo = r.get('titulo', '')
        lines.append(f"  {label:14s} {cita}")
        if titulo:
            lines.append(f"  {'':14s} {titulo}")

    lines.append("  " + "-" * 50)
    return "\n".join(lines)


def format_output(r: dict) -> str:
    """Formatea la salida para consumo por la skill."""
    d = date.fromisoformat(r["date"])
    day_name = r["day_name"]
    day_num = d.day
    month_name = MONTH_NAMES[d.month - 1]
    year = d.year

    lines = []
    lines.append("=" * 60)
    lines.append(f"  CALCULO LITURGICO: {day_name} {day_num} de {month_name} de {year}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Dia liturgico:   {r.get('name', '???')}")
    lines.append(f"  Rango:           {r.get('rank', 'Feria')}")
    lines.append(f"  Temporada:       {r.get('season', '???')}")
    lines.append(f"  Ciclo dominical: {r.get('sunday_cycle', '???')}")
    if r.get("weekday_cycle"):
        lines.append(f"  Ciclo ferial:    {r['weekday_cycle']}")
    if r.get("ot_week"):
        lines.append(f"  Semana del TO:   {r['ot_week']}")
    lines.append(f"  Color liturgico: {r.get('color', '???')}")
    lines.append(f"  Ano liturgico:   {r.get('liturgical_year', '???')}")

    if r.get("memorial"):
        lines.append("")
        lines.append(f"  >>> MEMORIAL: {r['memorial']}")
        lines.append(f"      Rango: {r.get('memorial_rank', 'Memoria Obligatoria')}")
        lines.append(f"      Color: {r.get('memorial_color', '???')}")
        lines.append(f"      Lecturas: {r.get('readings_source', 'feriales')}")

    if r.get("memorial_note"):
        lines.append("")
        lines.append(f"  NOTA: {r['memorial_note']}")

    if r.get("transferred_from"):
        lines.append("")
        lines.append(f"  >>> SOLEMNIDAD TRASLADADA del {r['transferred_from']}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


COLOR_THEME = {
    "Blanco": {"bg": "#faf8f0", "accent": "#c9a84c", "header": "#5c4a1e", "band": "linear-gradient(135deg, #f5e6b8, #c9a84c)"},
    "Morado": {"bg": "#f5f0fa", "accent": "#6b3fa0", "header": "#3d1f5c", "band": "linear-gradient(135deg, #d4b8e8, #6b3fa0)"},
    "Verde":  {"bg": "#f0f7f0", "accent": "#2e7d32", "header": "#1a4a1d", "band": "linear-gradient(135deg, #a8d5a2, #2e7d32)"},
    "Rojo":   {"bg": "#faf0f0", "accent": "#b71c1c", "header": "#5c0f0f", "band": "linear-gradient(135deg, #e8a0a0, #b71c1c)"},
    "Rosa":   {"bg": "#faf0f5", "accent": "#c2185b", "header": "#5c0f2e", "band": "linear-gradient(135deg, #f0b8d0, #c2185b)"},
}


def format_html(r: dict, readings: dict | None = None) -> str:
    """Genera HTML liturgico. If readings provided, fills in the text; otherwise uses placeholders."""
    d = date.fromisoformat(r["date"])
    day_name = r["day_name"]
    day_num = d.day
    month_name = MONTH_NAMES[d.month - 1]
    year = d.year
    color = r.get("color", "Blanco")
    theme = COLOR_THEME.get(color, COLOR_THEME["Blanco"])

    name = r.get("name", "")
    rank = r.get("rank", "Feria")
    season = r.get("season", "")
    cycle = r.get("sunday_cycle", "")
    wdc = r.get("weekday_cycle", "")
    memorial = r.get("memorial", "")
    memorial_rank = r.get("memorial_rank", "")
    memorial_note = r.get("memorial_note", "")

    # Titulo: memorial prevalece si es Fiesta
    display_name = name
    subtitle = ""
    if memorial and memorial_rank == "Fiesta":
        display_name = memorial
        subtitle = f"{name} &middot; lecturas propias"
    elif memorial:
        subtitle = f"{memorial} &middot; lecturas feriales"

    meta_parts = [rank, season, cycle]
    if wdc:
        meta_parts.append(wdc)
    meta_parts.append(color)
    meta_line = " &middot; ".join(meta_parts)

    # Reading content (from leccionario or placeholders)
    def _r(key):
        if not readings:
            return {}
        return readings.get(key, {}) if isinstance(readings.get(key), dict) else {}

    def _text_to_html(text):
        if not text:
            return ""
        return "".join(f"<p>{line}</p>" for line in text.split("\n") if line.strip())

    cita_1 = _r('primera').get('cita', '<!-- CITA_1 -->')
    texto_1 = _text_to_html(_r('primera').get('texto', '')) or '<!-- TEXTO_1 -->'
    cita_salmo = _r('salmo').get('cita', '<!-- CITA_SALMO -->')
    antifona = _r('salmo').get('antifona', '<!-- ANTIFONA -->')
    texto_salmo = _text_to_html(_r('salmo').get('texto', '')) or '<!-- TEXTO_SALMO -->'
    cita_ev = _r('evangelio').get('cita', '<!-- CITA_EVANGELIO -->')
    texto_ev = _text_to_html(_r('evangelio').get('texto', '')) or '<!-- TEXTO_EVANGELIO -->'
    acl_tipo = _r('aclamacion').get('tipo', '')
    acl_texto = _r('aclamacion').get('texto', '')
    acl_cita = _r('aclamacion').get('cita', '')
    source_text = "Leccionario CEE (offline)" if readings else "<!-- FUENTE -->"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lecturas — {day_name} {day_num} de {month_name} de {year}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@400;500;600&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Crimson Text', Georgia, serif; background: {theme['bg']}; color: #2c2c2c; min-height: 100vh; }}
  .band {{ background: {theme['band']}; height: 6px; }}
  .container {{ max-width: 720px; margin: 0 auto; padding: 2rem 1.5rem 3rem; }}
  .date {{ font-family: 'Inter', sans-serif; font-size: 0.85rem; font-weight: 500; color: {theme['accent']}; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.5rem; }}
  h1 {{ font-size: 2rem; font-weight: 700; color: {theme['header']}; line-height: 1.2; margin-bottom: 0.3rem; }}
  .subtitle {{ font-size: 1.1rem; font-style: italic; color: #666; margin-bottom: 0.5rem; }}
  .meta {{ font-family: 'Inter', sans-serif; font-size: 0.8rem; color: #888; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #ddd; }}
  .note {{ font-family: 'Inter', sans-serif; font-size: 0.8rem; color: #999; font-style: italic; margin-top: -1.5rem; margin-bottom: 2rem; }}
  .reading {{ margin-bottom: 2.5rem; }}
  .reading-label {{ font-family: 'Inter', sans-serif; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: {theme['accent']}; margin-bottom: 0.3rem; }}
  .reading-cite {{ font-family: 'Inter', sans-serif; font-size: 0.9rem; font-weight: 500; color: {theme['header']}; margin-bottom: 0.8rem; }}
  .reading-text {{ font-size: 1.15rem; line-height: 1.75; color: #333; }}
  .reading-text p {{ margin-bottom: 0.6rem; }}
  .antiphon {{ font-weight: 600; color: {theme['accent']}; font-size: 1.05rem; margin-bottom: 0.8rem; }}
  .separator {{ border: none; border-top: 1px solid #e0e0e0; margin: 2rem 0; }}
  .source {{ font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #aaa; text-align: center; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; }}
  .placeholder {{ font-family: 'Inter', sans-serif; font-size: 0.85rem; color: #bbb; font-style: italic; padding: 1rem; border: 1px dashed #ddd; border-radius: 4px; }}
  .aclamacion {{ margin-bottom: 2.5rem; }}
  .aclamacion summary {{ font-family: 'Inter', sans-serif; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: {theme['accent']}; cursor: pointer; list-style: none; display: flex; align-items: center; gap: 0.4rem; }}
  .aclamacion summary::-webkit-details-marker {{ display: none; }}
  .aclamacion summary::before {{ content: '\\25B6'; font-size: 0.6rem; transition: transform 0.2s; }}
  .aclamacion[open] summary::before {{ transform: rotate(90deg); }}
  .aclamacion-cite {{ font-family: 'Inter', sans-serif; font-size: 0.85rem; font-weight: 500; color: {theme['header']}; margin-top: 0.5rem; margin-bottom: 0.4rem; }}
  .aclamacion-text {{ font-size: 1.05rem; line-height: 1.6; color: #555; font-style: italic; }}
</style>
</head>
<body>
<div class="band"></div>
<div class="container">
  <p class="date">{day_name} {day_num} de {month_name} de {year}</p>
  <h1>{display_name}</h1>
  {"<p class='subtitle'>" + subtitle + "</p>" if subtitle else ""}
  <p class="meta">{meta_line}</p>
  {"<p class='note'>" + memorial_note + "</p>" if memorial_note else ""}

  <div class="reading" id="lectura-1">
    <p class="reading-label">1&ordf; Lectura</p>
    <p class="reading-cite">{cita_1}</p>
    <div class="reading-text">{texto_1}</div>
  </div>

  <hr class="separator">

  <div class="reading" id="salmo">
    <p class="reading-label">Salmo Responsorial</p>
    <p class="reading-cite">{cita_salmo}</p>
    <p class="antiphon">{antifona}</p>
    <div class="reading-text">{texto_salmo}</div>
  </div>

  <hr class="separator">

  {"" if not _r('segunda').get('texto') and not _r('segunda').get('cita') else '<div class="reading" id="lectura-2"><p class="reading-label">2&ordf; Lectura</p><p class="reading-cite">' + _r('segunda').get('cita', '') + '</p><div class="reading-text">' + _text_to_html(_r('segunda').get('texto', '')) + '</div></div><hr class="separator">'}

  {"" if not acl_texto else '<details class="aclamacion"><summary>Aclamaci&oacute;n — ' + (acl_tipo.capitalize() if acl_tipo else 'Aleluya') + '</summary>' + ('<p class="aclamacion-cite">' + acl_cita + '</p>' if acl_cita else '') + '<p class="aclamacion-text">' + acl_texto + '</p></details><hr class="separator">'}

  <div class="reading" id="evangelio">
    <p class="reading-label">Evangelio</p>
    <p class="reading-cite">{cita_ev}</p>
    <div class="reading-text">{texto_ev}</div>
  </div>

  <p class="source">{source_text}</p>
</div>
</body>
</html>"""


if __name__ == "__main__":
    use_html = "--html" in sys.argv
    use_readings = "--readings" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--html", "--readings")]

    if args:
        try:
            target = date.fromisoformat(args[0])
        except ValueError:
            print(f"Error: fecha invalida '{args[0]}'. Usa formato YYYY-MM-DD.")
            sys.exit(1)
    else:
        target = date.today()

    result = calculate(target)
    print(format_output(result))

    # Readings lookup
    readings = None
    if use_readings:
        readings = lookup_readings(result)
        if readings:
            print(format_readings(readings))
        else:
            print("\n  [Lecturas no encontradas en leccionario offline]")

    if use_html:
        import glob
        # Solo aquí se toca disco: una consulta sin --html no crea ni borra
        # nada (antes la limpieza corría siempre — una pregunta mutaba estado).
        # El destino se BUSCA hacia arriba, no se cuenta en niveles: este
        # fichero vive en dos layouts de distinta profundidad
        # (.claude/skills/.../scripts/ y tools/lecturasdeldia/) y una constante
        # de "..", "..", ... acierta en uno y se sale del arbol en el otro,
        # donde makedirs la crearia sin fallar.
        _d = os.path.dirname(os.path.abspath(__file__))
        lecturas_dir = None
        while True:
            if os.path.isdir(os.path.join(_d, "ztemp")):
                lecturas_dir = os.path.join(_d, "ztemp", "html")
                break
            _p = os.path.dirname(_d)
            if _p == _d:
                break
            _d = _p
        if lecturas_dir is None:
            lecturas_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "ztemp", "html")
        lecturas_dir = os.path.normpath(lecturas_dir)
        os.makedirs(lecturas_dir, exist_ok=True)
        # Limpiar archivos de lecturas anteriores
        for f in glob.glob(os.path.join(lecturas_dir, "*_lecturas.*")):
            os.remove(f)

        html = format_html(result, readings)
        fname = f"{target.year % 100:02d}{target.month:02d}{target.day:02d}_lecturas.html"
        fpath = os.path.join(lecturas_dir, fname)
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"\nHTML generado: {fpath}")
