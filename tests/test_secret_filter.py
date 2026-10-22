"""Credenciales sintéticas con formatos reales y lenguaje normal."""

from copy import deepcopy

import pytest

from agentes.secret_filter import sin_secretos


@pytest.mark.parametrize("texto,secreto", [
    ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
    ('{"Authorization": "Basic dXNlcjpwYXNz"}', "dXNlcjpwYXNz"),
    ("Proxy-Authorization: Basic VALOR_PRIVADO", "VALOR_PRIVADO"),
    ("authorization=basic VALOR_PRIVADO", "VALOR_PRIVADO"),
    ("Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
    ("basic YWxpY2U6czNjcjN0IQ==", "YWxpY2U6czNjcjN0IQ=="),
    ("Basic dXNlcjo=", "dXNlcjo="),
    ("Bearer token_de_ejemplo", "token_de_ejemplo"),
    ("api_key='clave con espacios'", "clave con espacios"),
    ('"client-secret": "valor_privado"', "valor_privado"),
    ("https://usuario:clave@example.test", "usuario:clave"),
    ("https://example.test?key=valor_privado&other=ok", "valor_privado"),
    ("sk-0123456789abcdefghijklmnop", "sk-0123456789abcdefghijklmnop"),
    ("AIza0123456789abcdefghijklmnop", "AIza0123456789abcdefghijklmnop"),
    ("api_\x1b[31mkey=valor_privado", "valor_privado"),
    ("api_\u200bkey=valor_privado", "valor_privado"),
    ("-----BEGIN PRIVATE KEY-----\nvalor_privado\n-----END PRIVATE KEY-----", "valor_privado"),
])
def test_oculta_credenciales(texto, secreto):
    resultado = sin_secretos(texto)
    assert secreto not in resultado
    assert "OCULT" in resultado


@pytest.mark.parametrize("texto", [
    "El plan Basic incluye piscina y gimnasio.", "Basic training para principiantes",
    "Curso de Visual Basic para adultos", "Basic natación", "Basic", "Basic !!!",
    "Basic YWJjZA==",  # Base64 de texto sin separador de credenciales.
    "La tarifa básica cuesta 20 euros.", "Consulta de instalaciones municipales.",
])
def test_conserva_frases_normales(texto):
    assert sin_secretos(texto) == texto


def test_filtra_objetos_sin_mutarlos_y_conserva_saltos():
    valor = {"password": "ejemplo", "lista": [1]}
    antes = deepcopy(valor)
    assert "ejemplo" not in sin_secretos(valor)
    assert valor == antes
    assert sin_secretos("uno\n\tdos\x1b[2J\u202e") == "uno\n\tdos"


@pytest.mark.parametrize("clave", ["password", "api_key", "access_token", "client-secret",
                                   "Authorization", "Proxy-Authorization", "api_\u200bkey"])
def test_oculta_valor_completo_de_claves_sensibles_anidadas(clave):
    valor = {"eventos": [{"datos": {clave: ["PRIVADO_UNO", {"otra": "PRIVADO_DOS"}]},
                           "mensaje": "El plan Basic incluye piscina."}]}
    antes = deepcopy(valor)
    salida = sin_secretos(valor)
    assert "PRIVADO_UNO" not in salida and "PRIVADO_DOS" not in salida
    assert "[OCULTO]" in salida
    assert "El plan Basic incluye piscina." in salida
    assert valor == antes


def test_filtra_colecciones_y_referencias_compartidas_sin_modificarlas():
    compartida = {"password": "PRIVADO_COMPARTIDO", "nota": "piscina"}
    valor = [compartida, (compartida, {"Basic dXNlcjpwYXNz"}),
             frozenset({"Bearer PRIVADO_BEARER"})]
    antes = deepcopy(valor)
    salida = sin_secretos(valor)
    assert "PRIVADO" not in salida and "dXNlcjpwYXNz" not in salida
    assert salida.count("piscina") == 2 and "[CICLO]" not in salida
    assert valor == antes and valor[0] is valor[1][0]


def test_estructura_circular_no_falla_ni_se_modifica():
    valor = {"password": ["PRIVADO_CIRCULAR"]}
    valor["ciclo"] = valor
    salida = sin_secretos(valor)
    assert "PRIVADO_CIRCULAR" not in salida and "[CICLO]" in salida
    assert valor["ciclo"] is valor and valor["password"] == ["PRIVADO_CIRCULAR"]
