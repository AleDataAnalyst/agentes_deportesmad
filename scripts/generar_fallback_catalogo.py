
# Archivo: scripts/generar_fallback_catalogo.py
# Función: descargar, validar y guardar una captura fechada del catálogo
# de centros deportivos municipales de Madrid para utilizarla como fallback.

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
DIRECTORIO_FALLBACKS = ROOT_DIR / "data" / "fallbacks"

BASE_URL = "https://datos.madrid.es/id/api/3/action/datastore_search"
RESOURCE_ID = "200186-0-polideportivos-csv"

CAMPOS_OBLIGATORIOS = ("PK", "NOMBRE", "DISTRITO", "CONTENT-URL")
CAMPOS_SALIDA = ("pk", "nombre", "distrito", "content_url")

LIMITE_PAGINA = 1000
TIMEOUT_SEGUNDOS = 20

logger = logging.getLogger("generar_fallback_catalogo")


def consultar_pagina(offset: int) -> dict[str, Any]:
    """Consulta una página de registros de CKAN."""
    parametros = {
        "resource_id": RESOURCE_ID,
        "limit": LIMITE_PAGINA,
        "offset": offset,
    }
    url = f"{BASE_URL}?{urlencode(parametros)}"
    peticion = Request(
        url,
        headers={"User-Agent": "PB2-Agente-Deportes/1.0"},
    )

    try:
        with urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            contenido = respuesta.read().decode("utf-8")
        resultado = json.loads(contenido)
    except HTTPError as exc:
        raise RuntimeError(
            f"CKAN respondió con HTTP {exc.code} al consultar offset={offset}."
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"No se pudo conectar con CKAN en offset={offset}: {exc}"
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            "CKAN devolvió una respuesta que no contiene JSON válido."
        ) from exc

    if not isinstance(resultado, dict) or resultado.get("success") is not True:
        raise RuntimeError(
            f"CKAN no confirmó la consulta en offset={offset}."
        )

    datos = resultado.get("result")
    if not isinstance(datos, dict):
        raise RuntimeError("La respuesta de CKAN no contiene un result válido.")

    registros = datos.get("records")
    total = datos.get("total")

    if not isinstance(registros, list):
        raise RuntimeError("CKAN no devolvió una lista de registros.")
    if not isinstance(total, int) or total < 0:
        raise RuntimeError("CKAN no devolvió un total de registros válido.")

    return {"total": total, "records": registros}


def normalizar_centro(registro: dict[str, Any], indice: int) -> dict[str, str]:
    """Valida y normaliza un registro del catálogo."""
    faltantes = [
        campo
        for campo in CAMPOS_OBLIGATORIOS
        if campo not in registro
        or registro[campo] is None
        or not str(registro[campo]).strip()
    ]
    if faltantes:
        raise RuntimeError(
            f"El registro {indice} no contiene campos obligatorios válidos: "
            f"{', '.join(faltantes)}."
        )

    return {
        "pk": str(registro["PK"]).strip(),
        "nombre": str(registro["NOMBRE"]).strip(),
        "distrito": str(registro["DISTRITO"]).strip(),
        "content_url": str(registro["CONTENT-URL"]).strip(),
    }


def descargar_catalogo() -> list[dict[str, str]]:
    """Descarga todas las páginas y valida el catálogo completo."""
    centros: list[dict[str, str]] = []
    offset = 0
    total_esperado: int | None = None

    while True:
        pagina = consultar_pagina(offset)
        total_pagina = pagina["total"]
        registros = pagina["records"]

        if total_esperado is None:
            total_esperado = total_pagina
            if total_esperado == 0:
                raise RuntimeError("CKAN respondió correctamente, pero el catálogo está vacío.")
        elif total_pagina != total_esperado:
            raise RuntimeError(
                "El total publicado por CKAN cambió durante la descarga. "
                "No se guardará una captura potencialmente inconsistente."
            )

        if not registros:
            break

        for registro in registros:
            if not isinstance(registro, dict):
                raise RuntimeError("CKAN devolvió un registro que no es un objeto.")
            centros.append(normalizar_centro(registro, len(centros) + 1))

        offset += len(registros)

        if offset >= total_esperado:
            break

    if total_esperado is None or len(centros) != total_esperado:
        raise RuntimeError(
            f"Descarga incompleta: se esperaban {total_esperado} registros "
            f"y se obtuvieron {len(centros)}."
        )

    identificadores = [centro["pk"] for centro in centros]
    if len(identificadores) != len(set(identificadores)):
        raise RuntimeError("El catálogo contiene identificadores PK duplicados.")

    return centros


def guardar_catalogo(
    centros: list[dict[str, str]],
    ruta_salida: Path,
    sobrescribir: bool,
) -> None:
    """Guarda el catálogo y sus metadatos sin sobrescribir por defecto."""
    if ruta_salida.exists() and not sobrescribir:
        raise RuntimeError(
            f"El archivo ya existe: {ruta_salida}\n"
            "No se ha modificado. Si quieres reemplazarlo expresamente, "
            "utiliza --sobrescribir."
        )

    ahora = datetime.now().astimezone()
    documento = {
        "metadata": {
            "recurso_id": RESOURCE_ID,
            "endpoint": BASE_URL,
            "fecha_extraccion": ahora.isoformat(timespec="seconds"),
            "fecha_captura": ahora.date().isoformat(),
            "total_centros": len(centros),
            "tipo_captura": "consulta_api_en_fecha_de_ejecucion",
            "nota": (
                "Datos obtenidos de CKAN en la fecha de extracción. "
                "No constituyen una captura histórica de una fecha anterior."
            ),
        },
        "centros": centros,
    }

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps(
        documento,
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    # Modo exclusivo: evita reemplazar un archivo que aparezca entre
    # la comprobación anterior y la escritura.
    if sobrescribir:
        ruta_salida.write_text(contenido, encoding="utf-8")
    else:
        with ruta_salida.open("x", encoding="utf-8", newline="\n") as archivo:
            archivo.write(contenido)

    logger.info("Catálogo guardado en: %s", ruta_salida)
    logger.info("Centros guardados: %s", len(centros))
    logger.info("Fecha real de extracción: %s", ahora.isoformat(timespec="seconds"))


def crear_argumentos() -> argparse.Namespace:
    """Define los argumentos de ejecución del script."""
    fecha_actual = datetime.now().astimezone().date().isoformat()
    salida_por_defecto = (
        DIRECTORIO_FALLBACKS / f"catalogo_centros_{fecha_actual}.json"
    )

    parser = argparse.ArgumentParser(
        description="Genera una captura validada del catálogo municipal de centros deportivos."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=salida_por_defecto,
        help="Ruta de salida del JSON. Por defecto, incluye la fecha real de extracción.",
    )
    parser.add_argument(
        "--sobrescribir",
        action="store_true",
        help="Permite reemplazar expresamente el archivo de salida si ya existe.",
    )
    return parser.parse_args()


def main() -> int:
    """Ejecuta la descarga, validación y escritura del catálogo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    args = crear_argumentos()
    ruta_salida = args.salida
    if not ruta_salida.is_absolute():
        ruta_salida = ROOT_DIR / ruta_salida

    try:
        logger.info("Consultando el catálogo municipal en CKAN...")
        centros = descargar_catalogo()
        guardar_catalogo(centros, ruta_salida, args.sobrescribir)
    except (RuntimeError, OSError) as exc:
        logger.error("%s", exc)
        return 1

    print("\nCAPTURA GENERADA CORRECTAMENTE")
    print(f"Archivo: {ruta_salida}")
    print(f"Total de centros: {len(centros)}")
    print("Campos guardados: pk, nombre, distrito, content_url")
    print("La fecha de extracción se encuentra en los metadatos del JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
