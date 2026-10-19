"""Consulta HTTP municipal y fallback local real fechado.

Entradas: filtros soportados y límites; endpoint configurado por desarrollador.
Salidas: catálogo normalizado, procedencia, fecha, uso de fallback y limitaciones.
Validar formato de respuesta y manejar timeout, error HTTP, esquema cambiado
y ausencia de resultados. El fallback debe ser una descarga documentada,
no datos ficticios. Sin fallback válido, devolver error explícito.
Catálogo no acredita plazas libres ni reservas. No dejar elegir URLs al LLM.
"""


# Archivo: agentes/tools/externa.py
# Función: consultar el catálogo municipal de centros deportivos mediante CKAN,
# normalizar sus registros y devolver el resultado con el contrato acordado.

import json
from pathlib import Path
from datetime import datetime
from typing import Literal, Optional, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://datos.madrid.es/id/api/3/action/datastore_search"
RESOURCE_ID_CATALOGO = "200186-0-polideportivos-csv"
TIMEOUT_SEGUNDOS = 10
USER_AGENT = "PB2-Agente-Deportes/1.0"
LIMITE_POR_PETICION = 1000

Modo = Literal["catalogo", "avisos"]
Origen = Literal["api", "html", "fallback"]


class ItemCatalogo(TypedDict):
    """Registro normalizado de un centro deportivo municipal."""

    pk: str
    nombre: str
    distrito: str
    content_url: str


class BloqueAviso(TypedDict):
    """Estructura reservada para los avisos HTML."""

    centro_id: str
    centro_nombre: str
    distrito: str
    url_ficha: str
    aviso_detectado: Optional[bool]
    texto_aviso: Optional[str]
    origen: Literal["html", "fallback"]
    fecha_consulta: str
    advertencias: list[str]


class ToolResultInstalaciones(TypedDict):
    """Resultado común de las consultas de instalaciones."""

    ok: bool
    modo: Modo
    datos: list[ItemCatalogo] | list[BloqueAviso]
    fuente: str
    origen: Origen
    fecha_consulta: str
    fecha_captura_fallback: Optional[str]
    advertencias: list[str]
    error: Optional[str]


def _fecha_actual_iso() -> str:
    """Devuelve la fecha y hora local con su zona horaria."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _crear_error_catalogo(
    mensaje: str,
    fecha_consulta: str,
    advertencias: Optional[list[str]] = None,
) -> ToolResultInstalaciones:
    """Construye una respuesta de error siguiendo el contrato común."""
    return {
        "ok": False,
        "modo": "catalogo",
        "datos": [],
        "fuente": RESOURCE_ID_CATALOGO,
        "origen": "api",
        "fecha_consulta": fecha_consulta,
        "fecha_captura_fallback": None,
        "advertencias": advertencias or [],
        "error": mensaje,
    }


def _normalizar_registro(registro: dict) -> ItemCatalogo:
    """Convierte un registro CKAN a los cuatro campos acordados."""
    campos = {
        "pk": "PK",
        "nombre": "NOMBRE",
        "distrito": "DISTRITO",
        "content_url": "CONTENT-URL",
    }

    valores: dict[str, str] = {}

    for destino, campo_origen in campos.items():
        valor = registro.get(campo_origen)

        if valor is None:
            raise ValueError(
                f"Falta el campo obligatorio {campo_origen!r}."
            )

        valor_texto = str(valor).strip()

        if not valor_texto:
            raise ValueError(
                f"El campo obligatorio {campo_origen!r} está vacío."
            )

        valores[destino] = valor_texto

    return ItemCatalogo(
        pk=valores["pk"],
        nombre=valores["nombre"],
        distrito=valores["distrito"],
        content_url=valores["content_url"],
    )


def _consultar_catalogo_ckan() -> ToolResultInstalaciones:
    """
    Consulta todas las páginas del catálogo CKAN y normaliza sus registros.

    Una respuesta válida sin registros no se considera un error de conexión.
    Los errores HTTP, de conexión, JSON o estructura se devuelven explícitamente.
    """
    fecha_consulta = _fecha_actual_iso()
    registros_normalizados: list[ItemCatalogo] = []
    advertencias: list[str] = []
    offset = 0
    total_esperado: Optional[int] = None

    try:
        while total_esperado is None or offset < total_esperado:
            parametros = {
                "resource_id": RESOURCE_ID_CATALOGO,
                "limit": LIMITE_POR_PETICION,
                "offset": offset,
            }
            url = f"{BASE_URL}?{urlencode(parametros)}"

            peticion = Request(
                url,
                headers={"User-Agent": USER_AGENT},
            )

            with urlopen(
                peticion,
                timeout=TIMEOUT_SEGUNDOS,
            ) as respuesta:
                contenido = respuesta.read().decode("utf-8")

            datos = json.loads(contenido)

            if not isinstance(datos, dict) or not datos.get("success"):
                return _crear_error_catalogo(
                    "CKAN no ha confirmado que la consulta sea correcta.",
                    fecha_consulta,
                )

            resultado = datos.get("result")

            if not isinstance(resultado, dict):
                return _crear_error_catalogo(
                    "La respuesta de CKAN no contiene un resultado válido.",
                    fecha_consulta,
                )

            registros = resultado.get("records")
            total = resultado.get("total")

            if not isinstance(registros, list):
                return _crear_error_catalogo(
                    "La respuesta de CKAN no contiene una lista de registros.",
                    fecha_consulta,
                )

            if not isinstance(total, int) or total < 0:
                return _crear_error_catalogo(
                    "CKAN no ha proporcionado un total de registros válido.",
                    fecha_consulta,
                )

            if total_esperado is None:
                total_esperado = total

            if not registros and offset < total_esperado:
                return _crear_error_catalogo(
                    "CKAN ha devuelto una página vacía antes de completar "
                    "la consulta del catálogo.",
                    fecha_consulta,
                )

            for registro in registros:
                if not isinstance(registro, dict):
                    advertencias.append(
                        "Se ha omitido un registro con formato inesperado."
                    )
                    continue

                try:
                    registros_normalizados.append(
                        _normalizar_registro(registro)
                    )
                except ValueError as error:
                    advertencias.append(
                        f"Se ha omitido un registro incompleto: {error}"
                    )

            if not registros:
                break

            offset += len(registros)

            if offset < total_esperado and len(registros) < LIMITE_POR_PETICION:
                return _crear_error_catalogo(
                    "CKAN ha devuelto menos registros de los esperados "
                    "antes de completar la paginación.",
                    fecha_consulta,
                    advertencias,
                )

    except HTTPError as error:
        return _crear_error_catalogo(
            f"Error HTTP al consultar CKAN: código {error.code}.",
            fecha_consulta,
            advertencias,
        )

    except URLError as error:
        return _crear_error_catalogo(
            f"Error de conexión al consultar CKAN: {error.reason}.",
            fecha_consulta,
            advertencias,
        )

    except (TimeoutError, OSError):
        return _crear_error_catalogo(
            f"La consulta a CKAN ha fallado o ha superado el timeout "
            f"de {TIMEOUT_SEGUNDOS} segundos.",
            fecha_consulta,
            advertencias,
        )

    except (json.JSONDecodeError, UnicodeDecodeError):
        return _crear_error_catalogo(
            "La respuesta de CKAN no contiene JSON válido en UTF-8.",
            fecha_consulta,
            advertencias,
        )

    if total_esperado and not registros_normalizados:
        return _crear_error_catalogo(
            "CKAN devolvió registros, pero ninguno contiene todos los "
            "campos obligatorios del catálogo.",
            fecha_consulta,
            advertencias,
        )

    if not registros_normalizados:
        advertencias.append(
            "La consulta ha sido válida, pero el catálogo no contiene registros."
        )

    return {
        "ok": True,
        "modo": "catalogo",
        "datos": registros_normalizados,
        "fuente": RESOURCE_ID_CATALOGO,
        "origen": "api",
        "fecha_consulta": fecha_consulta,
        "fecha_captura_fallback": None,
        "advertencias": advertencias,
        "error": None,
    }


# Archivo: agentes/tools/externa.py
# Función: cargar el catálogo local más reciente y usarlo cuando CKAN falle.

def _cargar_fallback_catalogo(
    directorio: Path | None = None,
) -> tuple[list[ItemCatalogo], str, Path]:
    """Carga la captura local más reciente que supere las validaciones."""
    if directorio is None:
        directorio = Path(__file__).resolve().parents[2] / "data" / "fallbacks"

    archivos = sorted(
        directorio.glob("catalogo_centros_*.json"),
        reverse=True,
    )

    if not archivos:
        raise RuntimeError(
            f"No hay capturas catalogadas en el directorio: {directorio}"
        )

    errores: list[str] = []

    for ruta in archivos:
        try:
            contenido = json.loads(ruta.read_text(encoding="utf-8"))

            if not isinstance(contenido, dict):
                raise ValueError("La raíz del JSON no es un objeto.")

            metadata = contenido.get("metadata")
            centros = contenido.get("centros")

            if not isinstance(metadata, dict):
                raise ValueError("Faltan los metadatos del catálogo.")

            if not isinstance(centros, list) or not centros:
                raise ValueError("La lista de centros está vacía o no es válida.")

            fecha_captura = metadata.get("fecha_captura")
            if not isinstance(fecha_captura, str) or not fecha_captura.strip():
                raise ValueError("Falta la fecha de captura.")

            total_declarado = metadata.get("total_centros")
            if total_declarado != len(centros):
                raise ValueError(
                    "El total declarado en los metadatos no coincide "
                    "con el número de centros."
                )

            centros_normalizados: list[ItemCatalogo] = []
            identificadores: set[str] = set()

            for indice, centro in enumerate(centros, start=1):
                if not isinstance(centro, dict):
                    raise ValueError(
                        f"El centro número {indice} no es un objeto."
                    )

                campos = ("pk", "nombre", "distrito", "content_url")
                if any(
                    not isinstance(centro.get(campo), str)
                    or not centro[campo].strip()
                    for campo in campos
                ):
                    raise ValueError(
                        f"El centro número {indice} tiene campos "
                        "obligatorios ausentes o vacíos."
                    )

                centro_normalizado: ItemCatalogo = {
                    "pk": centro["pk"].strip(),
                    "nombre": centro["nombre"].strip(),
                    "distrito": centro["distrito"].strip(),
                    "content_url": centro["content_url"].strip(),
                }

                if centro_normalizado["pk"] in identificadores:
                    raise ValueError(
                        f"PK duplicada: {centro_normalizado['pk']}."
                    )

                identificadores.add(centro_normalizado["pk"])
                centros_normalizados.append(centro_normalizado)

            return centros_normalizados, fecha_captura, ruta

        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            errores.append(f"{ruta.name}: {exc}")
            continue

    detalle = " | ".join(errores)
    raise RuntimeError(
        "No se encontró ninguna captura de catálogo válida. " + detalle
    )


def consultar_catalogo_con_fallback() -> ToolResultInstalaciones:
    """Consulta CKAN y usa una captura local válida si la API falla."""
    resultado_api = _consultar_catalogo_ckan()

    # Si la API funciona, conservamos exactamente su resultado.
    if resultado_api["ok"]:
        return resultado_api

    error_api = resultado_api.get("error") or "Error desconocido al consultar CKAN."

    try:
        centros, fecha_captura, ruta = _cargar_fallback_catalogo()
    except RuntimeError as exc:
        resultado_error = dict(resultado_api)
        advertencias = list(resultado_error.get("advertencias", []))
        advertencias.append(
            "No se pudo utilizar el catálogo local: " + str(exc)
        )
        resultado_error["advertencias"] = advertencias
        return resultado_error  # Se conserva el error original de CKAN.

    return {
        "ok": True,
        "modo": "catalogo",
        "datos": centros,
        "fuente": (
            "Catálogo municipal de centros deportivos de Madrid; "
            f"captura local {ruta.name}"
        ),
        "origen": "fallback",
        "fecha_consulta": _fecha_actual_iso(),
        "fecha_captura_fallback": fecha_captura,
        "advertencias": [
            f"CKAN no está disponible: {error_api}",
            (
                f"Se utiliza una captura local del {fecha_captura}. "
                "Los datos pueden no estar actualizados."
            ),
        ],
        "error": None,
    }
