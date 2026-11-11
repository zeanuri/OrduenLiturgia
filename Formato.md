# Formato de OrduenLiturgia

Dos formatos: el de los **textos** (lo que se escribe a mano o se convierte de la fuente) y el de la **salida** (lo que genera `generador/generar.py` cada noche y lee la app). Fijado el 10-nov-2026, antes de recibir los textos en bizkaiera: puede ajustarse cuando se vea cómo vienen.

## 1. Textos (`textos/`)

Cualquier número de ficheros `.json` en cualquier subcarpeta. Cada fichero es un diccionario **clave → pieza**; el generador los une todos, y una clave repetida es un error. El reparto en ficheros es libre (por ejemplo, uno por día del salterio).

### La pieza

```json
{
  "salterio/s4/mar/laudes/himno": {
    "titulo": "…",
    "lineas": [
      {"t": "estrofa", "x": "primer verso\nsegundo verso"},
      {"t": "rubrica", "x": "…"}
    ]
  },
  "salterio/s4/mar/laudes/salmo1": {"ref": "salmos/101"}
}
```

- `titulo` (opcional) y `lineas` (lista ordenada).
- `fuente` (opcional): de dónde sale el texto (en `textos/bizkaiera/`, la URL de la entrada del blog del autor). El generador la copia a la salida.
- `batua` (opcional, `true`): texto en batua de «Liturgia euskaraz» donde aún no hay bizkaiera (`textos/batua/batua.json`). La app lo pinta con la nota «Bizkaierazko bertsioaren zain» encima. Una clave que ya está en bizkaiera no entra en batua: el bizkaiera manda.
- `ref`: la pieza remite a otra clave. Sirve para escribir cada salmo una sola vez (`salmos/101`) y citarlo desde cada día.

### Tipos de línea (`t`)

| Tipo | Uso |
|---|---|
| `titulo` | Título de sección |
| `rubrica` | Indicación en rojo |
| `texto` | Texto que se reza |
| `estrofa` | Texto en versos |
| `ant` | Marca de antífona («1. Ant.») |
| `v` / `r` | Versículo y respuesta |
| `salmo` | Título de salmo o cántico |
| `epigrafe` | Epígrafe del salmo |
| `cita` | Cita bíblica |
| `sentencia` | Sentencia que encabeza el salmo |

### Las claves

Forma general: `<base>/<hora>/<parte>`.

**Horas:** `invitatorio`, `laudes`, `visperas`, `visperas1` (primeras vísperas).

**Partes:** `himno` · `ant1` `salmo1` `ant2` `salmo2` `ant3` `salmo3` · `lectura` · `responsorio` · `ant_ev` (antífona del Benedictus o del Magníficat) · `preces` · `oracion`. En Laudes `salmo2` es el cántico del Antiguo Testamento; en Vísperas `salmo3`, el del Nuevo. En el invitatorio, solo `ant`.

**Antífona del Evangelio por ciclo:** el domingo, antes de cada `…/ant_ev` se busca `…/ant_ev-<ciclo>` (`ant_ev-A`, `-B`, `-C`), en cualquier tiempo. Así un domingo de Cuaresma o de Pascua puede tener la común y la propia de cada ciclo (decisión del usuario, 10-nov-2026).

La `oracion` puede escribirse sin hora (`<base>/oracion`) cuando es la misma todo el día.

**Bases:**

| Base | Qué es | Ejemplo |
|---|---|---|
| `fijo/…` | Lo que no cambia | `fijo/apertura`, `fijo/benedictus`, `fijo/magnificat`, `fijo/padrenuestro`, `fijo/conclusion`, `fijo/invitatorio/apertura`, `fijo/invitatorio/salmo95` |
| `salterio/s<1-4>/<día>` | Salterio de cuatro semanas; día = `lun` `mar` `mie` `jue` `vie` `sab` `dom` | `salterio/s4/mar/laudes/himno` |
| `tiempo/ordinario/dom<n>-<ciclo>` | Domingo del Tiempo Ordinario (antífonas del Evangelio por ciclo) | `tiempo/ordinario/dom33-A/laudes/ant_ev` |
| `tiempo/ordinario/s<n>/oracion` | Oración de la semana | `tiempo/ordinario/s33/oracion` |
| `tiempo/adviento/s<n>/<día>` · `tiempo/adviento/<MM-DD>` (17-24 dic) · `…/comun` · `…/comun-17-24` | Adviento | `tiempo/adviento/s1/dom/visperas1/himno` |
| `tiempo/navidad/<MM-DD>` · `…/comun` · `…/comun-epifania` | Navidad | `tiempo/navidad/01-02/laudes/ant_ev` |
| `tiempo/cuaresma/ceniza/<día>` · `…/s<n>/<día>` · `…/comun` | Cuaresma | `tiempo/cuaresma/s1/dom/laudes/himno` |
| `tiempo/semana-santa/<día>` · `…/comun` | Semana Santa (lunes a miércoles) | |
| `tiempo/pascua/octava/<día>` · `…/s<n>/<día>` · `…/comun` · `…/comun-ascension` | Pascua | |
| `propio/<nombre>` | Celebración con nombre: santos, fiestas del Señor, Triduo, octava de Pascua. `<nombre>` es el nombre del calendario en castellano, en minúsculas, sin tildes y con guiones | `propio/san-leon-magno-papa-y-doctor/oracion` |
| `comunes/<común>` | Comunes: `dedicacion`, `santa-maria`, `apostoles`, `martires-uno`, `martires-varios`, `doctores`, `pastores`, `virgenes`, `religiosos`, `santos-varones`, `santas-mujeres` | `comunes/pastores/laudes/himno` |
| `salmos/<n>` | Salmos y cánticos, para citarlos con `ref` | `salmos/101` |

`comun` dentro de un tiempo es lo que vale para todo ese tiempo (por ejemplo, el himno de Adviento).

## 2. Cómo elige el generador

Cada parte busca su texto en una lista de claves, de la más propia a la más general, y toma la primera que existe:

| Día | Salmos | Antífonas de los salmos | Himno, lectura, responsorio, antífona del Evangelio, preces, oración |
|---|---|---|---|
| Feria | salterio | tiempo → salterio | tiempo → salterio |
| Domingo | salterio | tiempo → salterio | tiempo → salterio (en el Tiempo Ordinario, antífona del Evangelio por ciclo y oración de la semana) |
| Memoria | salterio | tiempo → salterio | propio → comunes → tiempo → salterio |
| Fiesta y solemnidad | propio → comunes → domingo de la semana I (Laudes) | igual que los salmos | propio → comunes (sin caer al salterio) |

- **Memoria libre:** el día trae dos celebraciones, la feria y la memoria marcada como opcional.
- **Vísperas:** son las primeras vísperas de mañana cuando mañana es domingo o solemnidad (o fiesta del Señor en domingo) y precede a hoy según la tabla de precedencia; si no, las del día.
- **Semana del salterio:** semana del tiempo módulo 4; Ceniza, IV; Semana Santa, II; Navidad, I hasta el domingo que sigue al 1 de enero y II después. Cotejada con la app oficial «Liturgia euskaraz» en once fechas (`generador/test_generar.py`).
- **Qué común corresponde a cada santo** se deduce del nombre («obispo», «mártir», «virgen»…). Es una heurística: hay que revisarla con el libro.

Sin comprobar todavía con el libro: el reparto exacto de lo propio en las ferias de los tiempos fuertes (qué partes cambian cada día y cuáles son comunes al tiempo) y los días con oficio especial (Triduo, 2 de noviembre).

## 3. Salida (`salida/`, generada; no va a git)

- `dias/AAAA-MM-DD.json` — un día ya resuelto, con los textos incrustados.
- `indice.json` — la ventana entera en corto, para el calendario de la app.
- `faltan.txt` — con `--inventario`: las piezas que faltan.

### `dias/AAAA-MM-DD.json`

```json
{
  "fecha": "2026-11-10", "dia_semana": "mar", "tiempo": "ordinario",
  "semana": 32, "semana_salterio": 4, "ciclo_dominical": "A", "color": "Verde",
  "misa": "https://lecturasdeldia.org/eu/2026/11/10/",
  "celebraciones": [{
    "id": "san-leon-magno-papa-y-doctor", "nombre": "San León Magno, papa y doctor",
    "rango": "Memoria Obligatoria", "opcional": false,
    "visperas_de": {"cuales": "del dia", "de": "San León Magno, papa y doctor"},
    "horas": {
      "invitatorio": [ … ],
      "laudes": [
        {"parte": "himno", "clave": "salterio/s4/mar/laudes/himno", "titulo": "…", "lineas": [ … ]},
        {"parte": "preces", "falta": ["propio/…/laudes/preces", "…", "salterio/s4/mar/laudes/preces"]}
      ],
      "visperas": [ … ]
    }
  }]
}
```

Una parte lleva `clave` y sus `lineas` (y `fuente`, si la pieza la tiene) cuando hay texto, o `falta` con la lista de claves donde se buscó. La app pinta una parte con `falta` vacía, con la nota «Bizkaierazko bertsioaren zain». `visperas_de.cuales` vale `primeras`, `segundas` o `del dia`.

Los nombres de las celebraciones salen por ahora en castellano, tal como los da el motor de calendario; falta ponerlos en bizkaiera.

### `indice.json`

```json
{"hoy": "2026-11-10", "desde": "2026-10-01", "hasta": "2027-11-10",
 "dias": {"2026-11-10": {"nombre": "…", "rango": "…", "tiempo": "ordinario", "color": "Verde",
                         "semana_salterio": 4, "huella": "3f2a…"}}}
```

`huella` cambia cuando cambia el fichero del día: la app compara huellas y solo vuelve a bajar los días que han cambiado.
