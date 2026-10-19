
"""Genera una captura local de avisos de centros deportivos municipales.

La captura solo se guarda si se obtiene al menos un aviso verificable.
Un HTTP 403, un fallo de conexión o la ausencia del encabezado esperado
se registran como estados no verificables, nunca como ausencia de avisos.

Ejecución desde la raíz del proyecto:
    python -m scripts.generar_fallback_avisos
    python -m scripts.generar_fallback_avisos --limite 5
    python -m scripts.generar_fallback_avisos --sobrescribir
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from agentes.tools.externa import (
    _consultar_pagina_aviso,
    _validar_url_oficial,
    consultar_catalogo_con_fallback,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
DIRECTORIO_FALLBACKS = ROOT_DIR / "data" / "fallbacks"

TIMEOUT_LOGICO = 10
MAX_TRABAJADORES = 4

logger = logging.getLogger("generar_fallback_avisos")


def fecha_actual() -> datetime:
    """Devuelve la fecha y hora local con zona horaria."""
    return datetime.now().astimezone()


def consultar_aviso(centro: dict[str, Any]) -> dict[str, Any]:
    """Consulta una ficha y devuelve un registro con estado explícito.

    Si la ficha tiene varios bloques de aviso, se concatenan con '\n\n'
    para conservarlos todos en el fallback. La estructura de un registro
    del fallback mantiene un único 'texto_aviso' por centro (el fallback
    simplifica a un bloque por centro); si necesitas multi-bloque exacto,
    amplía el esquema del fallback.
    """
    ahora = fecha_actual().isoformat(timespec="seconds")

    centro_id = str(centro.get("pk", "")).strip()
    nombre = str(centro.get("nombre", "")).strip()
    distrito = str(centro.get("distrito", "")).strip()
    url_original = str(centro.get("content_url", "")).strip()

    registro: dict[str, Any] = {
        "centro_id": centro_id,
        "centro_nombre": nombre,
        "distrito": distrito,
        "url_ficha": url_original,
        "estado_verificacion": "no_verificable",
        "aviso_detectado": None,
        "texto_aviso": None,
        "fecha_consulta": ahora,
        "detalle_verificacion": None,
    }

    if not centro_id or not nombre or not distrito or not url_original:
        registro["detalle_verificacion"] = (
            "El registro del catálogo carece de campos obligatorios."
        )
        return registro

    try:
        url_segura = _validar_url_oficial(url_original)
        registro["url_ficha"] = url_segura

        detectado, textos = _consultar_pagina_aviso(url_segura)

        if detectado is True and textos:
            registro["estado_verificacion"] = "aviso"
            registro["aviso_detectado"] = True
            registro["texto_aviso"] = "\n\n".join(textos)
            registro["detalle_verificacion"] = (
                f"Aviso extraído de la ficha oficial ({len(textos)} bloque/s)."
            )
        else:
            registro["detalle_verificacion"] = (
                "No se pudo confirmar la ausencia de avisos: "
                "la ficha no contiene el encabezado esperado."
            )

    except HTTPError as exc:
        registro["detalle_verificacion"] = (
            f"Error HTTP {exc.code} al consultar la ficha."
        )
    except URLError as exc:
        registro["detalle_verificacion"] = (
            f"Error de conexión al consultar la ficha: {exc.reason}."
        )
    except (RuntimeError, ValueError, TimeoutError, OSError) as exc:
        registro["detalle_verificacion"] = str(exc)
    except Exception:
        logger.exception(
            "Error inesperado al consultar el centro %s.",
            centro_id,
        )
        registro["detalle_verificacion"] = (
            "Error inesperado durante la consulta; revisar los logs."
        )

    return registro


def construir_captura(
    centros: list[dict[str, Any]],
    max_trabajadores: int = MAX_TRABAJADORES,
) -> dict[str, Any]:
    """Consulta los centros y construye una captura con metadatos."""
    if not centros:
        raise RuntimeError("El catálogo no contiene centros para consultar.")

    registros: list[dict[str, Any]] = []

    # Mantiene un límite de concurrencia para no saturar la web municipal.
    with ThreadPoolExecutor(max_workers=max_trabajadores) as executor:
        tareas = {
            executor.submit(consultar_aviso, centro): centro
            for centro in centros
        }

        for tarea in as_completed(tareas):
            centro = tareas[tarea]

            try:
                registro = tarea.result()
            except Exception as exc:
                # Protección adicional: una tarea fallida no detiene las demás.
                registro = {
                    "centro_id": str(centro.get("pk", "")).strip(),
                    "centro_nombre": str(centro.get("nombre", "")).strip(),
                    "distrito": str(centro.get("distrito", "")).strip(),
                    "url_ficha": str(
                        centro.get("content_url", "")
                    ).strip(),
                    "estado_verificacion": "no_verificable",
                    "aviso_detectado": None,
                    "texto_aviso": None,
                    "fecha_consulta": fecha_actual().isoformat(
                        timespec="seconds"
                    ),
                    "detalle_verificacion": (
                        f"No se pudo completar la tarea: {exc}"
                    ),
                }

            registros.append(registro)

            estado = registro["estado_verificacion"]
            logger.info(
                "Centro %s (%s): %s",
                registro["centro_id"],
                registro["centro_nombre"],
                estado,
            )

    # El orden de salida será determinista aunque las consultas sean concurrentes.
    registros.sort(key=lambda item: item["centro_id"])

    identificadores = [registro["centro_id"] for registro in registros]
    identificadores_validos = [
        identificador for identificador in identificadores if identificador
    ]

    if len(identificadores_validos) != len(set(identificadores_validos)):
        raise RuntimeError(
            "El catálogo contiene centros duplicados; no se guardará "
            "una captura ambigua."
        )

    total_avisos = sum(
        registro["estado_verificacion"] == "aviso"
        for registro in registros
    )
    total_sin_avisos_confirmados = sum(
        registro["estado_verificacion"] == "sin_avisos_confirmado"
        for registro in registros
    )
    total_no_verificables = sum(
        registro["estado_verificacion"] == "no_verificable"
        for registro in registros
    )

    ahora = fecha_actual()

    return {
        "metadata": {
            "fuente": "Fichas oficiales de centros deportivos de Madrid",
            "recurso_catalogo": "200186-0-polideportivos-csv",
            "fecha_extraccion": ahora.isoformat(timespec="seconds"),
            "fecha_captura": ahora.date().isoformat(),
            "total_centros_consultados": len(registros),
            "total_avisos": total_avisos,
            "total_sin_avisos_confirmados": total_sin_avisos_confirmados,
            "total_no_verificables": total_no_verificables,
            "tipo_captura": "consulta_oficial_en_fecha_de_ejecucion",
            "nota": (
                "La captura refleja únicamente lo que se pudo verificar "
                "durante esta ejecución. Un estado no verificable no "
                "significa que no existan avisos. La ausencia del encabezado "
                "tampoco confirma la ausencia de incidencias."
            ),
        },
        "avisos": registros,
    }


def guardar_captura(
    documento: dict[str, Any],
    ruta_salida: Path,
    sobrescribir: bool = False,
) -> None:
    """Guarda el JSON validado sin sobrescribir por defecto."""
    if ruta_salida.exists() and not sobrescribir:
        raise RuntimeError(
            f"El archivo ya existe: {ruta_salida}. "
            "Usa --sobrescribir para autorizar su reemplazo."
        )

    metadata = documento.get("metadata")
    registros = documento.get("avisos")

    if not isinstance(metadata, dict) or not isinstance(registros, list):
        raise RuntimeError("La estructura de la captura no es válida.")

    total_declarado = metadata.get("total_centros_consultados")
    if total_declarado != len(registros):
        raise RuntimeError(
            "El total declarado no coincide con los registros de la captura."
        )

    # No generar una captura sin información verificada que pueda ser útil.
    total_avisos = metadata.get("total_avisos")
    if not isinstance(total_avisos, int) or total_avisos < 1:
        raise RuntimeError(
            "No se ha encontrado ningún aviso verificable. "
            "No se guardará una captura que no permita responder consultas "
            "sobre avisos. Revisa los estados y errores del resultado."
        )

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps(
        documento,
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    if sobrescribir:
        ruta_salida.write_text(contenido, encoding="utf-8")
    else:
        # Apertura exclusiva: no reemplaza un archivo creado simultáneamente.
        with ruta_salida.open(
            "x",
            encoding="utf-8",
            newline="\n",
        ) as archivo:
            archivo.write(contenido)

    logger.info("Captura guardada en %s", ruta_salida)


def crear_argumentos() -> argparse.Namespace:
    """Define las opciones de ejecución."""
    fecha = fecha_actual().date().isoformat()
    parser = argparse.ArgumentParser(
        description=(
            "Genera una captura fechada de avisos verificables "
            "de centros deportivos municipales."
        )
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=DIRECTORIO_FALLBACKS / f"avisos_centros_{fecha}.json",
        help="Ruta del JSON de salida.",
    )
    parser.add_argument(
        "--sobrescribir",
        action="store_true",
        help="Autoriza reemplazar el archivo de salida si ya existe.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help=(
            "Limita el número de centros para una prueba inicial. "
            "Por defecto, consulta todo el catálogo."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Ejecuta la consulta, validación y escritura de la captura."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    args = crear_argumentos()

    if args.limite is not None and args.limite < 1:
        logger.error("--limite debe ser un entero mayor que cero.")
        return 2

    ruta_salida = args.salida
    if not ruta_salida.is_absolute():
        ruta_salida = ROOT_DIR / ruta_salida

    try:
        logger.info("Consultando el catálogo municipal...")
        resultado_catalogo = consultar_catalogo_con_fallback()

        if not resultado_catalogo["ok"]:
            raise RuntimeError(
                resultado_catalogo.get("error")
                or "No se pudo obtener el catálogo municipal."
            )

        centros = resultado_catalogo["datos"]
        centros = [
            centro
            for centro in centros
            if isinstance(centro, dict)
        ]

        if args.limite is not None:
            centros = centros[: args.limite]

        if not centros:
            raise RuntimeError(
                "No hay centros válidos para consultar."
            )

        logger.info("Centros que se van a consultar: %s", len(centros))
        documento = construir_captura(centros)

        metadata = documento["metadata"]
        logger.info(
            "Resumen: avisos=%s, no verificables=%s, "
            "sin avisos confirmados=%s",
            metadata["total_avisos"],
            metadata["total_no_verificables"],
            metadata["total_sin_avisos_confirmados"],
        )

        guardar_captura(
            documento,
            ruta_salida,
            sobrescribir=args.sobrescribir,
        )

    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        logger.error("%s", exc)
        return 1

    print("\nCAPTURA GENERADA CORRECTAMENTE")
    print(f"Archivo: {ruta_salida}")
    print(f"Centros consultados: {metadata['total_centros_consultados']}")
    print(f"Avisos verificables: {metadata['total_avisos']}")
    print(f"Estados no verificables: {metadata['total_no_verificables']}")
    print(
        "Ausencias confirmadas: "
        f"{metadata['total_sin_avisos_confirmados']}"
    )
    print(
        "La fecha real de extracción y las advertencias están "
        "incluidas en los metadatos."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
