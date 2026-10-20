"""Filtrado puro de credenciales reconocibles y controles invisibles.

No consulta configuración ni modifica el valor recibido. No es un escape HTML
ni garantiza detectar secretos sin un patrón reconocible.
"""

import base64
import binascii
import re
import unicodedata

_NOMBRE_SECRETO = (
    r"[a-z0-9_-]*api[_-]?key|[a-z0-9_-]*token|[a-z0-9_-]*secret|"
    r"password|(?:proxy-)?authorization|key"
)
_CLAVE_SECRETA = re.compile(rf"(?:{_NOMBRE_SECRETO})", re.IGNORECASE)


def _ocultar_basic(match: re.Match[str]) -> str:
    try:
        credencial = base64.b64decode(match[2], validate=True)
    except (ValueError, binascii.Error):
        return match[0]
    return f"{match[1]} [OCULTO]" if b":" in credencial else match[0]


def _limpiar_controles(texto: str) -> str:
    # Eliminar OSC/CSI antes del filtrado: no permitir enlaces, portapapeles,
    # borrado de terminal ni credenciales partidas por códigos de color.
    texto = re.sub(r"(?:\x1b\]|\x9d)[^\x07\x1b\x9c]*(?:\x07|\x1b\\|\x9c|$)", "", texto)
    texto = re.sub(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]", "", texto)
    return "".join(c for c in texto if c in "\n\t" or unicodedata.category(c) not in ("Cc", "Cf"))


def _filtrar_texto(texto: str) -> str:
    texto = _limpiar_controles(texto)
    texto = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                   "[CLAVE PRIVADA OCULTA]", texto, flags=re.DOTALL)
    # Una cabecera aporta contexto incluso si la credencial no es Base64.
    texto = re.sub(
        r"(?i)\b((?:proxy-)?authorization)\b[\"']?\s*[:=]\s*[\"']?(?:Basic|Bearer)\s+[^\s,;\"'}]+",
        r"\1=[OCULTO]", texto,
    )
    texto = re.sub(r"(?i)\b(Bearer)\s+[^\s,;]+", r"\1 [OCULTO]", texto)
    # Fuera de una cabecera, Basic solo es credencial si decodifica usuario:clave.
    texto = re.sub(
        r"(?i)\b(Basic)\s+([A-Za-z0-9+/]+={0,2})(?![A-Za-z0-9+/=])",
        _ocultar_basic, texto,
    )
    texto = re.sub(rf"(?i)\b({_NOMBRE_SECRETO})\b[\"']?\s*[:=]\s*(?:[\"'][^\"']*[\"']|[^\s,;&}}]+)",
                   r"\1=[OCULTO]", texto)
    texto = re.sub(r"\b(?:AIza[\w-]{20,}|sk-[\w-]{16,})", "[OCULTO]", texto)
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[OCULTO]@", texto)


def _filtrar_estructura(valor: object, ancestros: set[int]) -> object:
    if isinstance(valor, str):
        return _filtrar_texto(valor)
    if not isinstance(valor, (dict, list, tuple, set, frozenset)):
        return valor
    identidad = id(valor)
    if identidad in ancestros:
        return "[CICLO]"
    ancestros.add(identidad)
    try:
        if isinstance(valor, dict):
            return {
                _filtrar_estructura(clave, ancestros): (
                    "[OCULTO]" if isinstance(clave, str)
                    and _CLAVE_SECRETA.fullmatch(_limpiar_controles(clave))
                    else _filtrar_estructura(contenido, ancestros)
                )
                for clave, contenido in valor.items()
            }
        elementos = (_filtrar_estructura(elemento, ancestros) for elemento in valor)
        if isinstance(valor, list):
            return list(elementos)
        if isinstance(valor, tuple):
            return tuple(elementos)
        return frozenset(elementos) if isinstance(valor, frozenset) else set(elementos)
    finally:
        ancestros.remove(identidad)


def sin_secretos(valor: object) -> str:
    """Prepara texto de presentación sin mutar diccionarios ni colecciones anidadas.

    Las claves sensibles ocultan su valor completo, incluidas listas o mapas.
    No lee .env ni vuelca configuración; conserva la firma que usaba la CLI.
    """
    return _filtrar_texto(str(_filtrar_estructura(valor, set())))

