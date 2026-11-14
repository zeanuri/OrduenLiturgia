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

**Horas:** `invitatorio`, `laudes`, `visperas`, `visperas1` (primeras vísperas), `completas` (sus claves, abajo, § Completas).

**Partes:** `himno` · `ant1` `salmo1` `ant2` `salmo2` `ant3` `salmo3` · `lectura` · `responsorio` · `ant_ev` (antífona del Benedictus o del Magníficat) · `preces` · `oracion`. En Laudes `salmo2` es el cántico del Antiguo Testamento; en Vísperas `salmo3`, el del Nuevo. En el invitatorio, `ant` y los cuatro salmos `fijo/invitatorio/salmo95`, `…/salmo100`, `…/salmo67`, `…/salmo24` (`lineas`: el encabezado —`salmo`, `epigrafe`, `sentencia`— y una línea `estrofa` por estrofa, Gloria incluido, sin la antífona).

**Antífona del Evangelio por ciclo:** el domingo, antes de cada `…/ant_ev` se busca `…/ant_ev-<ciclo>` (`ant_ev-A`, `-B`, `-C`), en cualquier tiempo. Así un domingo de Cuaresma o de Pascua puede tener la común y la propia de cada ciclo (decisión del usuario, 10-nov-2026).

La `oracion` puede escribirse sin hora (`<base>/oracion`) cuando es la misma todo el día.

**Bases:**

| Base | Qué es | Ejemplo |
|---|---|---|
| `fijo/…` | Lo que no cambia. Primero el de la hora (`fijo/laudes/…`, `fijo/visperas/…`) y luego el común; `…/apertura-cuaresma` (sin «Aleluia», Cuaresma y Semana Santa) y `…/conclusion-pascua` (con «Aleluia, aleluia», octava de Pascua y Pentecostés) van delante en su tiempo | `fijo/laudes/apertura`, `fijo/benedictus`, `fijo/magnificat`, `fijo/padrenuestro`, `fijo/visperas/conclusion`, `fijo/invitatorio/apertura`, `fijo/invitatorio/salmo95` |
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

### Completas

Siete formularios (`f1`…`f7`) en `textos/batua/completas.json` (de «Liturgia euskaraz»; sin bizkaiera, salvo la apertura, que es la de Vísperas). Orden de la hora: `fijo/apertura` · `fijo/completas/examen` · `himno` · `ant1` `salmo1` [`ant2` `salmo2`] · `lectura` · `responsorio` · `ant_ev` · `fijo/completas/nunc-dimittis` · `oracion` · `fijo/completas/conclusion` · `fijo/completas/maria`.

| Parte | Claves (la primera que existe) |
|---|---|
| `himno` | `completas/f<n>/himno` en Tiempo Ordinario (el `f2` lleva los dos himnos juntos); en los demás tiempos, `completas/f2/himno` |
| `ant1` `salmo1` `ant2` `salmo2` | `completas/f<n>/<parte>`; en Pascua antes `completas/pascua/f<n>/<parte>` (una sola antífona: en `f1` y `f5` los dos salmos van juntos en `salmo1`, sin `ant2`/`salmo2`) |
| `lectura` · `oracion` | `completas/f<n>/<parte>`; la oración, antes `completas/solemnidad/oracion` |
| `responsorio` | `completas/triduo/<jue\|vie\|sab>/responsorio` · `completas/octava/responsorio` (de Pascua al II domingo) · `completas/pascua/responsorio` · `completas/responsorio` |
| `ant_ev` | `completas/pascua/ant_ev` · `completas/ant_ev` |
| `maria` | `fijo/completas/maria-pascua` (Pascua) · `fijo/completas/maria` |

Formulario de la noche (`formulario_completas`), medido contra el servidor (`referencia/completas_informe.txt`): si son **primeras** (noche de sábado, o víspera de solemnidad que precede a hoy; nunca en Semana Santa), `f1`; domingo o solemnidad (también el Triduo), `f2`; octava de Pascua, lunes, miércoles y viernes `f1`, martes y jueves `f2`; lunes a viernes, `f3`…`f7`. Tiempo y apertura son los de mañana si son primeras. Oración de solemnidad (`C5002`): solemnidad que no es domingo, ella o su víspera, salvo la octava de Pascua y los Difuntos (rezan como domingo). Dos salmos: `f1` y `f5`, fuera de Pascua. El lunes de Tiempo Ordinario (`f3`) no tiene himno: el del servidor está en castellano.

## 2. Cómo elige el generador

Cada parte busca su texto en una lista de claves, de la más propia a la más general, y toma la primera que existe:

| Día | Salmos | Antífonas de los salmos | Himno, lectura, responsorio, antífona del Evangelio, preces, oración |
|---|---|---|---|
| Feria | tiempo → salterio | tiempo → salterio | tiempo → salterio |
| Domingo | tiempo → salterio | tiempo → salterio | tiempo → salterio (en el Tiempo Ordinario, antífona del Evangelio por ciclo y oración de la semana) |
| Memoria | propio → tiempo → salterio | propio → tiempo → salterio | propio → tiempo → salterio; si la feria solo está en batua y el común en bizkaiera, el común |
| Fiesta y solemnidad | propio → comunes → domingo de la semana I (Laudes) | igual que los salmos | propio → comunes (sin caer al salterio) |

- **Memoria:** como «Liturgia euskaraz», lo propio del santo (con su salmodia, si la tiene: San Martín) y lo demás de la feria; lo que el santo toma del común ya está en su `propio/`.
- **Memoria libre:** el día trae dos celebraciones, la feria y la memoria marcada como opcional. Si el calendario da varios santos alternativos («San Beda / San Gregorio VII / Santa M. Magdalena de Pazzi»: se elige uno), cada santo es su propia celebración opcional, con su `id` (`propio/san-beda-el-venerable/…`), su nombre y sus textos. Solo se parte por « / »: «Santos Juan Fisher y Tomás Moro» es una sola.
- **Santa María en sábado** (`propio/santa-maria-en-sabado/…`, nombre de «Liturgia euskaraz»): memoria libre que el motor de calendario no da y el generador añade, al final de la lista y sin alternar con los santos, los sábados del Tiempo Ordinario sin memoria obligatoria, fiesta ni solemnidad (26 en la ventana de hoy a 365 días; el 24-oct-2026, junto a Claret). Como la ofrece la referencia, solo propios en el Invitatorio (antífona) y en Laudes (himno, lectura breve y responsorio con sus tres opciones, antífona del Benedictus, preces del común, oración; en batua, sin bizkaiera propio); la salmodia es la del salterio del sábado y Vísperas y Completas, las de la feria (primeras del domingo). La cabecera del día la añade a `memoria` con « / ».
- **Salmos del tiempo:** los días con salmodia propia la toman del tiempo (Miércoles de Ceniza, octava de Pascua y su domingo, octava de Navidad, que reza la del domingo de la semana I desde `tiempo/navidad/comun`). No cuentan para los salmos las carpetas por fecha (`tiempo/adviento/12-21`, `tiempo/navidad/01-04`: el blog escribe ahí los salmos del día de la semana de aquel año) ni `tiempo/navidad/comun` fuera de diciembre. Si el salmo del tiempo solo está en batua y el salterio tiene el mismo salmo o cántico en bizkaiera, sale el del salterio; «el mismo» es el mismo número de salmo o el mismo libro y capítulo del cántico, y si no se puede saber se queda el del tiempo (en Cuaresma el cántico dominical de Vísperas es 1 Pe 2, no el Ap 19 del salterio).
- **Vísperas:** son las primeras vísperas de mañana cuando mañana es domingo o solemnidad (o fiesta del Señor en domingo) y precede a hoy según la tabla de precedencia; si no, las del día. Dos excepciones: el Triduo y el domingo de Pascua no tienen primeras vísperas (el Miércoles Santo y el Sábado Santo rezan las suyas), y a igual nivel gana el domingo de mañana (sábado después de Ceniza, sábado de la octava de Pascua).
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
    "completas_de": {"cuales": "del dia", "de": "San León Magno, papa y doctor"},
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

Una parte lleva `clave` y sus `lineas` (y `fuente`, si la pieza la tiene) cuando hay texto, o `falta` con la lista de claves donde se buscó. La app pinta una parte con `falta` vacía, con la nota «Oraindik osatu gabe» (no hay texto ni en bizkaiera ni en batua). `visperas_de.cuales` y `completas_de.cuales` valen `primeras`, `segundas` o `del dia`.

Una parte lleva además `cabecera` cuando tiene título de sección: los de «Liturgia euskaraz» (`CABECERAS` en `generar.py`: «Hasierako deia», «Gorazarrea», «Salmoak», «Irakurgai laburra», «Galde-erantzuna», «Ebanjelioko kantika», «Eskariak», «Jaunaren otoitza», «Otoitza», «Amaiera»; en Completas también «Kontzientzia azterketa», «Salmoa» la noche de un solo salmo y «Maria Birjina Dohatsuari azken kantuak»). No sale si el texto ya la trae como línea `titulo` (en la pieza, o al final de las preces la del Padre nuestro), ni en el Invitatorio. La app la pinta encima de la parte, también si la parte es una `falta`, y no la repite con la antífona que vuelve tras el salmo. El título y el epígrafe del Benedictus y del Magníficat van dentro de la pieza (`extraccion/fijos.py`).

Una parte puede llevar en vez de `lineas` una lista `opciones` (el salmo del Invitatorio): `{"parte": "salmo", "opciones": [{"n": "95", "clave": "fijo/invitatorio/salmo95", "lineas": […], "batua": true, "fuente": "…"}, {"n": "100", …}, …]}`; solo salen los salmos que tienen texto, y si no hay ninguno, la parte es una `falta` con las cuatro claves.

`nombre_eu` y la `cabecera` llevan los nombres de «Liturgia euskaraz» (`generador/nombres_eu.json`, por `id`; la feria de la octava de Navidad, que el motor llama como al santo, con `-feria`); lo que no está en la tabla, el de lecturasdeldia.org/eu. Los rangos, con sus palabras («beharrezko oroipena», «festaburua»…), según el rango de nuestro motor.

### `indice.json`

```json
{"hoy": "2026-11-10", "desde": "2026-10-01", "hasta": "2027-11-10",
 "dias": {"2026-11-10": {"nombre": "…", "rango": "…", "tiempo": "ordinario", "color": "Verde",
                         "semana_salterio": 4, "huella": "3f2a…"}}}
```

`huella` cambia cuando cambia el fichero del día: la app compara huellas y solo vuelve a bajar los días que han cambiado.
