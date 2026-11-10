"""Escribe textos de PRUEBA para todas las piezas que faltan.

No son textos litúrgicos: son relleno marcado como tal (`"prueba": true`), para
ver funcionar el generador y la app antes de tener los textos en bizkaiera.
Cada pieza real que se añada a `textos/` debe ir acompañada de borrar su relleno
(o de volver a correr este script, que solo rellena lo que sigue faltando).

    py -3.14 relleno.py            (re)escribe textos/prueba/relleno.json
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import generar

DESTINO = generar.PROYECTO / "textos" / "prueba" / "relleno.json"
MARCA = "PROBA"          # se ve en pantalla en cada pieza de relleno


def pieza(clave: str) -> dict:
    parte = clave.rsplit("/", 1)[-1]
    L = lambda t, x: {"t": t, "x": x}  # noqa: E731
    etiqueta = f"[{MARCA}] {clave}"
    if parte.startswith("salmo") or parte in ("benedictus", "magnificat", "salmo95"):
        lineas = [L("salmo", f"[{MARCA}] {parte}"), L("epigrafe", "epígrafe de prueba"), L("sentencia", "sentencia de prueba (cita)"),
                  L("estrofa", "verso de prueba uno,\nverso de prueba dos;\nverso de prueba tres,\nverso de prueba cuatro."),
                  L("estrofa", "verso de prueba cinco,\nverso de prueba seis."),
                  L("estrofa", "Gloria de prueba.")]
    elif parte.startswith("ant"):
        lineas = [L("ant", "Ant."), L("texto", f"antífona de prueba ({parte}).")]
    elif parte == "himno":
        lineas = [L("titulo", "Himno"), L("estrofa", "verso de prueba uno,\nverso de prueba dos,\nverso de prueba tres,\nverso de prueba cuatro."),
                  L("estrofa", "verso de prueba cinco,\nverso de prueba seis,\nverso de prueba siete,\nverso de prueba ocho. Amén.")]
    elif parte == "lectura":
        lineas = [L("titulo", "Lectura breve"), L("cita", "Cita 0, 0-0"), L("texto", "Texto de prueba de la lectura breve, de dos o tres renglones, para ver cómo cae en la pantalla un párrafo corrido.")]
    elif parte == "responsorio":
        lineas = [L("titulo", "Responsorio breve"), L("v", "V."), L("texto", "versículo de prueba."), L("r", "R."), L("texto", "respuesta de prueba.")]
    elif parte == "preces":
        lineas = [L("titulo", "Preces"), L("texto", "Invitación de prueba a la oración:"), L("r", "R."), L("texto", "respuesta de prueba."),
                  L("texto", "Petición de prueba primera,\n— segunda parte de la petición."), L("texto", "Petición de prueba segunda,\n— segunda parte de la petición.")]
    elif parte == "oracion":
        lineas = [L("titulo", "Oración"), L("texto", "Oración de prueba, que ocupa un par de renglones para ver el párrafo. Por nuestro Señor de prueba."), L("r", "R."), L("texto", "Amén.")]
    elif parte in ("apertura",):
        lineas = [L("v", "V."), L("texto", "versículo inicial de prueba."), L("r", "R."), L("texto", "respuesta inicial de prueba.")]
    elif parte == "padrenuestro":
        lineas = [L("titulo", "Padrenuestro"), L("texto", "texto de prueba del padrenuestro.")]
    elif parte == "conclusion":
        lineas = [L("titulo", "Conclusión"), L("v", "V."), L("texto", "bendición de prueba."), L("r", "R."), L("texto", "Amén.")]
    else:
        lineas = [L("texto", "texto de prueba.")]
    return {"prueba": True, "lineas": [L("rubrica", etiqueta), *lineas]}


def main() -> int:
    if DESTINO.exists():
        DESTINO.unlink()                               # se rehace entero: solo lo que falta sin él
    textos = generar.cargar_textos(generar.PROYECTO / "textos")
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
    faltan: dict = {}
    # Un año litúrgico entero más la ventana, para que el relleno no caduque cada noche.
    for n in range(-generar.DIAS_ATRAS - 30, generar.DIAS_ADELANTE + 400):
        generar.generar_dia(hoy + timedelta(days=n), textos, faltan)
    relleno = {clave: pieza(clave) for clave in sorted(faltan)}
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(relleno, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n")
    print(f"{len(relleno)} piezas de prueba en {DESTINO.relative_to(generar.PROYECTO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
