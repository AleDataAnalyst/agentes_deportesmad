"""
Archivo: agentes/tools/externa.py

Propósito:
Consultar el catálogo municipal de centros deportivos de Madrid mediante CKAN,
normalizar sus registros y consultar los avisos de las fichas oficiales.

Incluye:
- Consulta paginada de CKAN.
- Validación de datos y URLs oficiales.
- Fallbacks locales fechados y validados.
- Extracción del apartado «Aviso a usuarios/as».
- Manejo explícito de errores HTTP, conexión, JSON y datos incompletos.

Limitaciones:
- Un HTTP 403 no demuestra que no existan avisos.
- Una captura local puede estar desactualizada.
- La ausencia del encabezado no demuestra que no haya incidencias.
- El catálogo no acredita plazas libres ni permite confirmar reservas.
"""

import json
import logging
import re
import unicodedata

from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, Optional, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
    urlopen,
)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BASE_URL = "https://datos.madrid.es/id/api/3/action/datastore_search"
RESOURCE_ID_CATALOGO = "200186-0-polideportivos-csv"

TIMEOUT_SEGUNDOS = 10
USER_AGENT = "PB2-Agente-Deportes/1.0"
LIMITE_POR_PETICION = 1000

DIRECTORIO_FALLBACKS = (
    Path(__file__).resolve().parents[2] / "data" / "fallbacks"
)

# Antigüedad máxima para utilizar capturas históricas de avisos.
MAX_EDAD_FALLBACK_AVISOS_DIAS = 3

DOMINIOS_OFICIALES = {"madrid.es", "www.madrid.es"}
HEADING_AVISO = "aviso a usuarios/as"
CLASE_TITULO_AVISO = "title-modal"
CLASE_CONTENEDOR_AVISO = "modal-alert"

Modo = Literal["catalogo", "avisos"]
Origen = Literal["api", "html", "fallback"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contratos de datos
# ---------------------------------------------------------------------------

class ItemCatalogo(TypedDict):
    """Registro normalizado de un centro deportivo municipal."""

    pk: str
    nombre: str
    distrito: str
    content_url: str


class BloqueAviso(TypedDict):
    """Aviso extraído de una ficha oficial o de una captura local.

    Un mismo centro puede tener varios bloques de aviso (p.ej. María Jesús
    Rosa tenía 2 en la captura del 13/10/2026). Cada bloque va como un
    elemento independiente en ToolResultInstalaciones["datos"].
    """

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
    ok: bool
    modo: Modo
    datos: list[ItemCatalogo] | list[BloqueAviso]
    fuente: str
    origen: Origen
    fecha_consulta: str
    fecha_captura_fallback: Optional[str]
    advertencias: list[str]
    error: Optional[str]
    requiere_aclaracion: bool  # nuevo, opcional en la práctica


# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------

def _fecha_actual_iso() -> str:
    """Devuelve la fecha y hora local con información de zona horaria."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _validar_fecha_iso(fecha: object) -> str:
    """Valida una fecha ISO 8601 y devuelve su representación original."""
    if not isinstance(fecha, str) or not fecha.strip():
        raise ValueError("Falta la fecha de captura.")

    valor = fecha.strip()

    try:
        datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"La fecha de captura no tiene un formato ISO válido: {valor!r}."
        ) from exc

    return valor


def _crear_error_catalogo(
    mensaje: str,
    fecha_consulta: str,
    advertencias: Optional[list[str]] = None,
) -> ToolResultInstalaciones:
    """Construye una respuesta de error para la consulta del catálogo."""
    return {
        "ok": False,
        "modo": "catalogo",
        "datos": [],
        "fuente": RESOURCE_ID_CATALOGO,
        "origen": "api",
        "fecha_consulta": fecha_consulta,
        "fecha_captura_fallback": None,
        "advertencias": list(advertencias or []),
        "error": mensaje,
    }


def _crear_error_aviso(
    centro_id: str,
    mensaje: str,
    fecha_consulta: str,
    advertencias: Optional[list[str]] = None,
    *,
    requiere_aclaracion: bool = False,
) -> ToolResultInstalaciones:
    """Construye una respuesta de error/aclaración para la consulta de avisos."""
    return {
        "ok": False,
        "modo": "avisos",
        "datos": [],
        "fuente": "Ficha oficial del centro",
        "origen": "html",
        "fecha_consulta": fecha_consulta,
        "fecha_captura_fallback": None,
        "advertencias": list(advertencias or []),
        "error": f"Centro {centro_id}: {mensaje}",
        # Campo extra interno; el nodo lo usa para mapear a abstained.
        "requiere_aclaracion": requiere_aclaracion,
    }


# ---------------------------------------------------------------------------
# Validación de URLs oficiales
# ---------------------------------------------------------------------------

def _validar_url_oficial(url: str) -> str:
    """
    Comprueba que una URL pertenece al dominio oficial madrid.es.

    Devuelve la URL normalizada a HTTPS. No admite credenciales, dominios
    externos ni puertos distintos de los habituales de HTTP/HTTPS.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("La URL de la ficha está vacía.")

    url = url.strip()
    partes = urlparse(url)

    if partes.scheme.lower() not in {"http", "https"}:
        raise ValueError("La URL debe utilizar HTTP o HTTPS.")

    hostname = (partes.hostname or "").lower()

    if hostname not in DOMINIOS_OFICIALES:
        raise ValueError("La URL no pertenece al dominio oficial madrid.es.")

    if partes.username or partes.password:
        raise ValueError("La URL no puede incluir credenciales.")

    try:
        puerto = partes.port
    except ValueError as exc:
        raise ValueError("La URL contiene un puerto inválido.") from exc

    if puerto not in (None, 80, 443):
        raise ValueError("La URL contiene un puerto no permitido.")

    if not partes.path:
        raise ValueError("La URL no contiene una ruta de ficha.")

    # Reconstruimos la autoridad a partir del hostname validado para evitar
    # conservar credenciales u otros componentes no necesarios.
    autoridad = hostname

    return urlunparse(
        (
            "https",
            autoridad,
            partes.path,
            partes.params,
            partes.query,
            partes.fragment,
        )
    )


class _RedireccionesOficiales(HTTPRedirectHandler):
    """Impide seguir redirecciones que apunten fuera de madrid.es."""

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        # La redirección debe pasar la misma validación que la URL inicial.
        url_segura = _validar_url_oficial(newurl)

        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            url_segura,
        )


# ---------------------------------------------------------------------------
# Catálogo municipal: normalización y consulta CKAN
# ---------------------------------------------------------------------------

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

def normalizar_texto(texto: str) -> str:
    """Normaliza texto: minúsculas y sin tildes, para comparaciones."""
    texto = (texto or "").casefold()
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )







def _consultar_catalogo_ckan() -> ToolResultInstalaciones:
    """
    Consulta todas las páginas del catálogo CKAN y normaliza sus registros.

    Devuelve un error explícito ante fallos HTTP, conexión, JSON o esquema.
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
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )

            with urlopen(
                peticion,
                timeout=TIMEOUT_SEGUNDOS,
            ) as respuesta:
                contenido = respuesta.read().decode("utf-8")

            datos = json.loads(contenido)

            if not isinstance(datos, dict) or datos.get("success") is not True:
                return _crear_error_catalogo(
                    "CKAN no ha confirmado que la consulta sea correcta.",
                    fecha_consulta,
                    advertencias,
                )

            resultado = datos.get("result")

            if not isinstance(resultado, dict):
                return _crear_error_catalogo(
                    "La respuesta de CKAN no contiene un resultado válido.",
                    fecha_consulta,
                    advertencias,
                )

            registros = resultado.get("records")
            total = resultado.get("total")

            if not isinstance(registros, list):
                return _crear_error_catalogo(
                    "La respuesta de CKAN no contiene una lista de registros.",
                    fecha_consulta,
                    advertencias,
                )

            if (
                not isinstance(total, int)
                or isinstance(total, bool)
                or total < 0
            ):
                return _crear_error_catalogo(
                    "CKAN no ha proporcionado un total de registros válido.",
                    fecha_consulta,
                    advertencias,
                )

            if total_esperado is None:
                total_esperado = total
            elif total != total_esperado:
                return _crear_error_catalogo(
                    "El total de registros de CKAN ha cambiado durante "
                    "la paginación; no se puede garantizar una captura completa.",
                    fecha_consulta,
                    advertencias,
                )

            if not registros and offset < total_esperado:
                return _crear_error_catalogo(
                    "CKAN ha devuelto una página vacía antes de completar "
                    "la consulta del catálogo.",
                    fecha_consulta,
                    advertencias,
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
                except ValueError as exc:
                    advertencias.append(
                        f"Se ha omitido un registro incompleto: {exc}"
                    )

            if not registros:
                break

            offset += len(registros)

            if (
                offset < total_esperado
                and len(registros) < LIMITE_POR_PETICION
            ):
                return _crear_error_catalogo(
                    "CKAN ha devuelto menos registros de los esperados "
                    "antes de completar la paginación.",
                    fecha_consulta,
                    advertencias,
                )

    except HTTPError as exc:
        return _crear_error_catalogo(
            f"Error HTTP al consultar CKAN: código {exc.code}.",
            fecha_consulta,
            advertencias,
        )
    except URLError as exc:
        return _crear_error_catalogo(
            f"Error de conexión al consultar CKAN: {exc.reason}.",
            fecha_consulta,
            advertencias,
        )
    except (TimeoutError, OSError) as exc:
        return _crear_error_catalogo(
            f"Fallo de conexión o timeout al consultar CKAN: {exc}.",
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


# ---------------------------------------------------------------------------
# Catálogo municipal: fallback local
# ---------------------------------------------------------------------------

def _cargar_fallback_catalogo(
    directorio: Optional[Path] = None,
) -> tuple[list[ItemCatalogo], str, Path]:
    """
    Carga la captura local más reciente que supere las validaciones.

    Se prueban las capturas de más reciente a más antigua para permitir
    recuperar una copia anterior si la última está dañada.
    """
    directorio = directorio or DIRECTORIO_FALLBACKS

    archivos = sorted(
        directorio.glob("catalogo_centros_*.json"),
        reverse=True,
    )

    if not archivos:
        logger.warning(
            "No hay capturas de catálogo en el directorio: %s", directorio
        )
        raise RuntimeError(
            "No hay capturas locales del catálogo disponibles."
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

            fecha_captura = _validar_fecha_iso(
                metadata.get("fecha_captura")
            )

            if not isinstance(centros, list) or not centros:
                raise ValueError(
                    "La lista de centros está vacía o no es válida."
                )

            total_declarado = metadata.get("total_centros")

            if (
                not isinstance(total_declarado, int)
                or isinstance(total_declarado, bool)
                or total_declarado != len(centros)
            ):
                raise ValueError(
                    "El total declarado no coincide con el número de centros."
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

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
        ) as exc:
            errores.append(f"{ruta.name}: {exc}")

    raise RuntimeError(
        "No se encontró ninguna captura de catálogo válida. "
        + " | ".join(errores)
    )


def consultar_catalogo_con_fallback() -> ToolResultInstalaciones:
    """Consulta CKAN y utiliza una captura local válida si la API falla."""
    resultado_api = _consultar_catalogo_ckan()

    if resultado_api["ok"]:
        return resultado_api

    error_api = (
        resultado_api.get("error")
        or "Error desconocido al consultar CKAN."
    )

    try:
        centros, fecha_captura, ruta = _cargar_fallback_catalogo()
    except RuntimeError:
        resultado_error = dict(resultado_api)
        advertencias = list(resultado_error.get("advertencias", []))
        # Conservar el motivo del fallo de la API (mensaje controlado, sin
        # rutas internas ni trazas) para que el usuario sepa qué pasó.
        if error_api:
            advertencias.append(error_api)
        advertencias.append(
            "No se pudo utilizar el catálogo local de respaldo."
        )
        resultado_error["advertencias"] = advertencias
        return resultado_error

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


# ---------------------------------------------------------------------------
# Extracción del aviso desde HTML
# ---------------------------------------------------------------------------


class _ExtractorAvisoHTML(HTMLParser):
    """
    Extrae los bloques de aviso contenidos en elementos modal-alert.

    Solo cuenta las etiquetas div para controlar la profundidad del modal.
    Las etiquetas p, br, img y otras etiquetas HTML no modifican esa
    profundidad, por lo que no pueden dejar el parser bloqueado.

    resultado() devuelve:
      (True, bloques): se encontraron avisos.
      (False, []): el HTML se procesó correctamente, pero no había avisos.
      (None, []): no se pudo verificar la extracción con seguridad.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._profundidad_modal = 0
        self._profundidad_ignorar = 0
        self._partes_bloque: list[str] = []
        self._bloques: list[str] = []
        self._modal_incompleto = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        atributos = dict(attrs or [])
        clases = (atributos.get("class") or "").split()

        if tag in {"script", "style", "noscript"}:
            self._profundidad_ignorar += 1
            return

        if self._profundidad_ignorar:
            return

        # Solo un div con la clase modal-alert inicia un bloque.
        if (
            self._profundidad_modal == 0
            and tag == "div"
            and CLASE_CONTENEDOR_AVISO in clases
        ):
            self._profundidad_modal = 1
            self._partes_bloque = []
            return

        if self._profundidad_modal:
            # Únicamente los div anidados aumentan la profundidad.
            if tag == "div":
                self._profundidad_modal += 1

            if tag in {"p", "div", "br", "li", "tr", "section"}:
                self._partes_bloque.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in {"script", "style", "noscript"}:
            if self._profundidad_ignorar:
                self._profundidad_ignorar -= 1
            return

        if self._profundidad_ignorar or not self._profundidad_modal:
            return

        if tag in {"p", "div", "br", "li", "tr", "section"}:
            self._partes_bloque.append(" ")

        # Las etiquetas distintas de div no alteran la profundidad.
        if tag != "div":
            return

        self._profundidad_modal -= 1

        if self._profundidad_modal == 0:
            texto = re.sub(
                r"\s+",
                " ",
                "".join(self._partes_bloque),
            ).strip()

            # Se conserva el texto del bloque si contiene el encabezado.
            if HEADING_AVISO in texto.casefold() and texto:
                self._bloques.append(texto)

            self._partes_bloque = []

    def handle_data(self, data: str) -> None:
        if self._profundidad_ignorar or not self._profundidad_modal:
            return

        self._partes_bloque.append(data)

    def resultado(self) -> tuple[bool | None, list[str]]:
        """
        Devuelve el estado de verificación y los bloques extraídos.

        None significa que quedó abierto un modal y no puede garantizarse
        que la extracción esté completa.
        """
        if self._profundidad_modal != 0:
            self._modal_incompleto = True

        if self._modal_incompleto:
            return None, []

        bloques = [bloque for bloque in self._bloques if bloque.strip()]

        if bloques:
            return True, bloques

        return False, []



def _consultar_pagina_aviso(url: str) -> tuple[bool, list[str]]:
    """
    Consulta una ficha oficial y extrae sus bloques de aviso.

    Devuelve (detectado, lista_de_textos). Si no hay ningún bloque,
    devuelve (False, []).

    Lanza RuntimeError si la consulta falla (HTTP, red, timeout, HTML
    vacío, etc.). Es importante distinguir "consulté y no había aviso"
    de "no pude consultar": el primero devuelve (False, []); el segundo
    lanza excepción.
    """
    url_segura = _validar_url_oficial(url)

    peticion = Request(
        url_segura,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-ES,es;q=0.9",
        },
    )

    opener = build_opener(_RedireccionesOficiales())

    try:
        with opener.open(
            peticion,
            timeout=TIMEOUT_SEGUNDOS,
        ) as respuesta:
            _validar_url_oficial(respuesta.geturl())
            contenido = respuesta.read().decode(
                "utf-8",
                errors="strict",
            )

    except HTTPError as exc:
        raise RuntimeError(
            f"Error HTTP al consultar la ficha oficial: código {exc.code}."
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"No se pudo consultar la ficha oficial: {exc.reason}."
        ) from exc
    except (TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Fallo de conexión o timeout al consultar la ficha: {exc}."
        ) from exc
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            "La ficha no se pudo interpretar como texto UTF-8."
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            f"La URL final de la ficha no es válida: {exc}"
        ) from exc

    if not contenido.strip():
        raise RuntimeError("La ficha oficial ha devuelto contenido vacío.")

    extractor = _ExtractorAvisoHTML()

    try:
        extractor.feed(contenido)
        extractor.close()
        return extractor.resultado()
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Avisos: fallback local
# ---------------------------------------------------------------------------

def _cargar_fallback_avisos(
    directorio: Optional[Path] = None,
) -> tuple[dict[str, dict], str, Path]:
    """
    Carga la captura local más reciente de avisos que sea válida.

    Cada registro debe contener el identificador, nombre, distrito, URL,
    estado del aviso y fecha de consulta. Si la captura más reciente está
    dañada, se intenta la siguiente.
    """
    directorio = directorio or DIRECTORIO_FALLBACKS

    archivos = sorted(
        directorio.glob("avisos_centros_*.json"),
        reverse=True,
    )

    if not archivos:
        logger.warning(
            "No hay capturas de avisos en el directorio: %s", directorio
        )
        raise RuntimeError("No hay capturas locales de avisos disponibles.")

    errores: list[str] = []

    for ruta in archivos:
        try:
            documento = json.loads(ruta.read_text(encoding="utf-8"))

            if not isinstance(documento, dict):
                raise ValueError("La raíz del JSON no es un objeto.")

            metadata = documento.get("metadata")
            avisos = documento.get("avisos")

            if not isinstance(metadata, dict):
                raise ValueError("Faltan los metadatos de la captura.")

            
            fecha = _validar_fecha_iso(metadata.get("fecha_captura"))

            fecha_captura_dt = datetime.fromisoformat(fecha)
            ahora = datetime.now(fecha_captura_dt.tzinfo)

            antiguedad = ahora - fecha_captura_dt

            if antiguedad > timedelta(
                days=MAX_EDAD_FALLBACK_AVISOS_DIAS
            ):
                raise ValueError(
                    "La captura supera la antigüedad máxima permitida "
                    "para utilizar avisos históricos."
                )

            if not isinstance(avisos, list) or not avisos:

                raise ValueError(
                    "La lista de avisos está vacía o no es válida."
                )

            total_declarado = metadata.get("total_centros_consultados")

            if (
                not isinstance(total_declarado, int)
                or isinstance(total_declarado, bool)
                or total_declarado != len(avisos)
            ):
                raise ValueError(
                    "El total de registros no coincide con los metadatos."
                )

            por_centro: dict[str, dict] = {}

            campos_obligatorios = (
                "centro_id",
                "centro_nombre",
                "distrito",
                "url_ficha",
                "fecha_consulta",
            )

            for indice, registro in enumerate(avisos, start=1):
                if not isinstance(registro, dict):
                    raise ValueError(f"Registro {indice} no válido.")

                for campo in campos_obligatorios:
                    valor = registro.get(campo)

                    if not isinstance(valor, str) or not valor.strip():
                        raise ValueError(
                            f"Registro {indice}: falta el campo {campo!r}."
                        )

                centro_id = registro["centro_id"].strip()
                detectado = registro.get("aviso_detectado")
                texto = registro.get("texto_aviso")

                if detectado is not True and detectado is not False and detectado is not None:
                    raise ValueError(
                        f"Registro {indice} tiene aviso_detectado inválido."
                    )

                if detectado is True and (
                    not isinstance(texto, str) or not texto.strip()
                ):
                    raise ValueError(
                        f"Registro {indice} indica aviso, pero no contiene texto."
                    )

                if texto is not None and not isinstance(texto, str):
                    raise ValueError(
                        f"Registro {indice} tiene texto_aviso inválido."
                    )

                try:
                    url_validada = _validar_url_oficial(
                        registro["url_ficha"]
                    )
                    _validar_fecha_iso(registro["fecha_consulta"])
                except ValueError as exc:
                    raise ValueError(
                        f"Registro {indice}: {exc}"
                    ) from exc

                if centro_id in por_centro:
                    raise ValueError(f"Centro duplicado: {centro_id}.")

                por_centro[centro_id] = {
                    "centro_id": centro_id,
                    "centro_nombre": registro["centro_nombre"].strip(),
                    "distrito": registro["distrito"].strip(),
                    "url_ficha": url_validada,
                    "aviso_detectado": detectado,
                    "texto_aviso": texto.strip() if texto else None,
                    "fecha_consulta": registro["fecha_consulta"].strip(),
                }

            return por_centro, fecha, ruta

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
        ) as exc:
            errores.append(f"{ruta.name}: {exc}")

    raise RuntimeError(
        "No hay ninguna captura de avisos válida. "
        + " | ".join(errores)
    )


# ---------------------------------------------------------------------------
# Consulta pública de avisos por identificador del centro
# ---------------------------------------------------------------------------

def consultar_aviso_centro(centro_id: str) -> ToolResultInstalaciones:
    """
    Consulta los avisos de un centro por PK, con fallback si es necesario.

    - Si la ficha responde y tiene 1+ bloques: devuelve un BloqueAviso por
      cada bloque en datos (multi-bloque).
    - Si la ficha responde pero no tiene ningún bloque: devuelve un
      BloqueAviso con aviso_detectado=False y advertencia de "no garantiza
      ausencia".
    - Si la ficha NO se puede consultar (403, 500, timeout, red): intenta
      el fallback local. Si no hay fallback válido, devuelve ok=False con
      error explícito (nunca aviso_detectado=False, porque no sabemos si
      hay aviso).
    """
    fecha_consulta = _fecha_actual_iso()
    centro_id = str(centro_id).strip() if centro_id is not None else ""

    if not centro_id:
        return _crear_error_aviso(
            centro_id or "(vacío)",
            "el identificador es obligatorio.",
            fecha_consulta,
        )

    catalogo = consultar_catalogo_con_fallback()

    if not catalogo["ok"]:
        return _crear_error_aviso(
            centro_id,
            "no se pudo consultar el catálogo para resolver la ficha.",
            fecha_consulta,
            list(catalogo["advertencias"]),
        )

    centros = catalogo["datos"]

    centro = next(
        (
            item
            for item in centros
            if isinstance(item, dict) and item.get("pk") == centro_id
        ),
        None,
    )

    if centro is None:
        return _crear_error_aviso(
            centro_id,
            "no aparece en el catálogo disponible.",
            fecha_consulta,
            list(catalogo["advertencias"]),
        )

    url = str(centro["content_url"])

    advertencias_catalogo: list[str] = []
    if catalogo["origen"] == "fallback":
        advertencias_catalogo.append(
            "El centro se ha localizado usando un catálogo local; "
            "comprueba que los datos sigan vigentes."
        )

    # 1) Intentar la consulta HTML real.
    error_html_msg: Optional[str] = None

    
    try:
        detectado, textos = _consultar_pagina_aviso(url)

        # Si el HTML no permite verificar el resultado, usar el fallback.
        if detectado is None:
            raise RuntimeError(
                "No se pudo verificar la presencia o ausencia de avisos."
            )

        url_ficha = _validar_url_oficial(url)
        advertencias = list(advertencias_catalogo)

        if detectado is False:

            advertencias.append(
                "La ficha se consultó correctamente, pero no se encontró "
                "el encabezado del aviso. Esto no garantiza que no exista "
                "una incidencia."
            )
            bloque: BloqueAviso = {
                "centro_id": centro_id,
                "centro_nombre": centro["nombre"],
                "distrito": centro["distrito"],
                "url_ficha": url_ficha,
                "aviso_detectado": False,
                "texto_aviso": None,
                "origen": "html",
                "fecha_consulta": fecha_consulta,
                "advertencias": advertencias,
            }
            return {
                "ok": True,
                "modo": "avisos",
                "datos": [bloque],
                "fuente": url_ficha,
                "origen": "html",
                "fecha_consulta": fecha_consulta,
                "fecha_captura_fallback": None,
                "advertencias": advertencias,
                "error": None,
            }

        # Multi-bloque: un BloqueAviso por cada texto.
        bloques: list[BloqueAviso] = []
        for texto in textos:
            bloques.append(
                {
                    "centro_id": centro_id,
                    "centro_nombre": centro["nombre"],
                    "distrito": centro["distrito"],
                    "url_ficha": url_ficha,
                    "aviso_detectado": True,
                    "texto_aviso": texto,
                    "origen": "html",
                    "fecha_consulta": fecha_consulta,
                    "advertencias": list(advertencias),
                }
            )

        return {
            "ok": True,
            "modo": "avisos",
            "datos": bloques,
            "fuente": url_ficha,
            "origen": "html",
            "fecha_consulta": fecha_consulta,
            "fecha_captura_fallback": None,
            "advertencias": advertencias,
            "error": None,
        }

    except (RuntimeError, ValueError) as exc:
        error_html_msg = str(exc)
        logger.warning(
            "Falló la consulta del aviso del centro %s: %s",
            centro_id,
            error_html_msg,
        )

    # 2) Fallback local.
    try:
        registros, fecha_captura, ruta = _cargar_fallback_avisos()
        registro = registros.get(centro_id)

        if registro is None:
            raise RuntimeError(
                f"La captura {ruta.name} no contiene el centro {centro_id}."
            )

        detectado = registro["aviso_detectado"]
        texto = registro["texto_aviso"]

        advertencias = list(advertencias_catalogo)
        advertencias.append(
            f"La consulta oficial falló: {error_html_msg}."
        )
        advertencias.append(
            f"Se utiliza la captura del {fecha_captura}; "
            "el aviso puede haber cambiado desde entonces."
        )

        if detectado is None:
            # Fallback no permite determinar el estado.
            bloque: BloqueAviso = {
                "centro_id": centro_id,
                "centro_nombre": registro["centro_nombre"],
                "distrito": registro["distrito"],
                "url_ficha": registro["url_ficha"],
                "aviso_detectado": None,
                "texto_aviso": None,
                "origen": "fallback",
                "fecha_consulta": fecha_consulta,
                "advertencias": advertencias,
            }
            return {
                "ok": False,
                "modo": "avisos",
                "datos": [bloque],
                "fuente": ruta.name,
                "origen": "fallback",
                "fecha_consulta": fecha_consulta,
                "fecha_captura_fallback": fecha_captura,
                "advertencias": advertencias,
                "error": (
                    "La captura no permite determinar si había un aviso "
                    "para este centro."
                ),
            }

        if detectado is False:
            advertencias.append(
                "La captura no detectó un aviso en la fecha de extracción; "
                "no confirma la situación actual."
            )

        bloque = {
            "centro_id": centro_id,
            "centro_nombre": registro["centro_nombre"],
            "distrito": registro["distrito"],
            "url_ficha": registro["url_ficha"],
            "aviso_detectado": detectado,
            "texto_aviso": texto,
            "origen": "fallback",
            "fecha_consulta": fecha_consulta,
            "advertencias": advertencias,
        }

        return {
            "ok": True,
            "modo": "avisos",
            "datos": [bloque],
            "fuente": ruta.name,
            "origen": "fallback",
            "fecha_consulta": fecha_consulta,
            "fecha_captura_fallback": fecha_captura,
            "advertencias": advertencias,
            "error": None,
        }

    
    except (RuntimeError, OSError) as error_fallback:
        logger.warning(
            "No se pudo consultar el aviso del centro %s ni utilizar "
            "el fallback. Tipo de error del fallback: %s",
            centro_id,
            type(error_fallback).__name__,
        )
        return _crear_error_aviso(
            centro_id,
            (
                "No se pudo consultar la ficha oficial y no hay una "
                "captura local utilizable para verificar el estado "
                "de los avisos."
            ),
            fecha_consulta,
            advertencias_catalogo,
        )


# ---------------------------------------------------------------------------
# Punto de entrada público (contrato del especialista)
# ---------------------------------------------------------------------------

def consultar_instalaciones(
    modo: Modo,
    centro_id: Optional[str] = None,
) -> ToolResultInstalaciones:
    if modo == "catalogo":
        return consultar_catalogo_con_fallback()

    if modo == "avisos":
        if not centro_id:
            return _crear_error_aviso(
                "(vacío)",
                "necesito saber de qué centro quieres consultar los avisos.",
                _fecha_actual_iso(),
                requiere_aclaracion=True,
            )
        return consultar_aviso_centro(centro_id)

    return _crear_error_catalogo(
        f"Modo no soportado: {modo!r}. Usa 'catalogo' o 'avisos'.",
        _fecha_actual_iso(),
    )

def resolver_centro_por_nombre(texto: str) -> list[ItemCatalogo]:
    """Devuelve centros cuyo nombre contenga todas las palabras de `texto`."""
    catalogo = consultar_catalogo_con_fallback()
    if not catalogo["ok"]:
        return []
    palabras = [
        normalizar_texto(p) for p in re.split(r"\W+", texto) if p
    ]
    palabras = [p for p in palabras if len(p) >= 3]
    if not palabras:
        return []
    coincidencias: list[ItemCatalogo] = []
    for item in catalogo["datos"]:
        if not isinstance(item, dict):
            continue
        nombre = normalizar_texto(str(item.get("nombre") or ""))
        if all(p in nombre for p in palabras):
            coincidencias.append(item)
    return coincidencias

