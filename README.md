# OrduenLiturgia

Liturgia de las Horas en euskera bizkaino para Android: **Invitatorio, Laudes y Vísperas**, con su calendario. Las Completas se añadirán más adelante.

**Estado: en desarrollo.** Laudes y Vísperas llevan los textos en bizkaiera que su autor publica en sus blogs de Gorespenak y Bezperak, con su permiso (`textos/bizkaiera/`; cada pieza lleva en `fuente` la entrada del blog de donde sale). Lo que todavía no tiene versión en bizkaiera sale en batua, el de la app «Liturgia euskaraz» (`textos/batua/`), con la nota «Bizkaierazko bertsioaren zain» encima: hoy, las partes fijas (apertura, Benedictus y Magníficat, Padre nuestro, conclusión), parte de los himnos y lo propio de algunos días. Sin texto todavía: la antífona y el salmo del Invitatorio.

## Cómo funciona

1. `textos/` guarda las piezas (himnos, salmos, antífonas, lecturas, preces, oraciones) en JSON.
2. Cada noche, `generador/generar.py` resuelve con el calendario litúrgico de la Conferencia Episcopal Española qué se celebra cada día y compone las horas: **365 días hacia adelante y 40 hacia atrás**, un fichero por día más un índice.
3. GitHub Pages publica esos ficheros.
4. La app, al abrirse, baja el índice y el día, y guarda lo que baja para funcionar sin conexión. A las demás fechas se llega por el calendario.

Las lecturas de la misa enlazan con [lecturasdeldia.org/eu](https://lecturasdeldia.org/eu/).

## Carpetas

| Carpeta | Qué hay |
|---|---|
| `textos/` | Los textos. Formato y claves en [`Formato.md`](Formato.md) |
| `generador/` | `generar.py` (los días), `relleno.py` (textos de prueba, para ensayar sin los reales), `liturgia.py` (motor de calendario) y las pruebas |
| `app/web/` | La app: HTML, CSS y JavaScript sin dependencias |
| `app/android/` | Envoltorio de Android: un WebView que lleva dentro `app/web` y una copia de los días |
| `.github/workflows/` | `generar.yml` (pruebas, generación nocturna y publicación) y `apk.yml` (compila el APK de pruebas) |

## Uso en local

```
python -m pytest generador -q          # pruebas
python generador/generar.py            # escribe salida/ (no va a git)
python generador/relleno.py            # textos de prueba de lo que falte (solo para ensayos; no se suben)
python -m http.server 8765             # y abrir http://127.0.0.1:8765/app/web/index.html?base=/salida/
```

## Notas

- `generador/liturgia.py` es una copia del motor de calendario que usa lecturasdeldia.org; no se edita aquí.
- Los rótulos de la app (`R` en `app/web/app.js`) y los nombres de las celebraciones son provisionales: están pendientes de fijarse en bizkaiera.
- Qué común corresponde a cada santo se deduce del nombre; hay que revisarlo con el libro (`Formato.md` § 2).
