
# Archivo: tests/test_fallback_catalogo.py
# Función: probar la validación del JSON y el fallback del catálogo sin red.

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentes.tools import externa


def crear_centro(
    pk: str = "101",
    nombre: str = "Centro de prueba",
) -> dict[str, str]:
    """Devuelve un centro mínimo válido para las pruebas."""
    return {
        "pk": pk,
        "nombre": nombre,
        "distrito": "SALAMANCA",
        "content_url": "https://example.org/centro",
    }


def crear_captura(
    centros: list[dict[str, str]] | None = None,
) -> dict:
    """Crea una captura de prueba con metadatos coherentes."""
    if centros is None:
        centros = [crear_centro()]

    return {
        "metadata": {
            "fecha_captura": "2026-10-16",
            "fecha_extraccion": "2026-10-16T14:34:11+02:00",
            "total_centros": len(centros),
        },
        "centros": centros,
    }


def crear_error_api() -> dict:
    """Simula el resultado de una consulta CKAN fallida."""
    return {
        "ok": False,
        "modo": "catalogo",
        "datos": [],
        "fuente": "CKAN",
        "origen": "api",
        "fecha_consulta": "2026-10-16T14:00:00+02:00",
        "fecha_captura_fallback": None,
        "advertencias": [],
        "error": "Error HTTP al consultar CKAN: código 503.",
    }


class TestFallbackCatalogo(unittest.TestCase):
    """Pruebas unitarias del catálogo local."""

    def test_carga_captura_valida(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            directorio = Path(temporal)
            ruta = directorio / "catalogo_centros_2026-10-16.json"
            ruta.write_text(
                json.dumps(crear_captura(), ensure_ascii=False),
                encoding="utf-8",
            )

            centros, fecha, archivo = externa._cargar_fallback_catalogo(
                directorio
            )

            self.assertEqual(len(centros), 1)
            self.assertEqual(centros[0]["pk"], "101")
            self.assertEqual(fecha, "2026-10-16")
            self.assertEqual(archivo, ruta)

    def test_rechaza_directorio_sin_capturas(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            with self.assertRaises(RuntimeError):
                externa._cargar_fallback_catalogo(Path(temporal))

    def test_rechaza_captura_con_pk_duplicada(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            directorio = Path(temporal)
            ruta = directorio / "catalogo_centros_2026-10-16.json"
            contenido = crear_captura([
                crear_centro("101", "Centro A"),
                crear_centro("101", "Centro B"),
            ])
            ruta.write_text(json.dumps(contenido), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                externa._cargar_fallback_catalogo(directorio)

    def test_ignora_captura_malformada_si_hay_otra_valida(self) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            directorio = Path(temporal)
            (directorio / "catalogo_centros_2026-10-17.json").write_text(
                "{JSON no válido",
                encoding="utf-8",
            )
            ruta_valida = directorio / "catalogo_centros_2026-10-16.json"
            ruta_valida.write_text(
                json.dumps(crear_captura()),
                encoding="utf-8",
            )

            centros, fecha, archivo = externa._cargar_fallback_catalogo(
                directorio
            )

            self.assertEqual(len(centros), 1)
            self.assertEqual(fecha, "2026-10-16")
            self.assertEqual(archivo, ruta_valida)

    @patch("agentes.tools.externa._consultar_catalogo_ckan")
    def test_api_correcta_no_necesita_fallback(self, mock_api) -> None:
        resultado = {
            **crear_error_api(),
            "ok": True,
            "datos": [crear_centro()],
            "error": None,
        }
        mock_api.return_value = resultado

        respuesta = externa.consultar_catalogo_con_fallback()

        self.assertTrue(respuesta["ok"])
        self.assertEqual(respuesta["origen"], "api")
        self.assertEqual(respuesta["datos"], resultado["datos"])

    @patch("agentes.tools.externa._cargar_fallback_catalogo")
    @patch("agentes.tools.externa._consultar_catalogo_ckan")
    def test_api_fallida_usa_fallback_valido(
        self,
        mock_api,
        mock_fallback,
    ) -> None:
        mock_api.return_value = crear_error_api()
        mock_fallback.return_value = (
            [crear_centro()],
            "2026-10-16",
            Path("catalogo_centros_2026-10-16.json"),
        )

        respuesta = externa.consultar_catalogo_con_fallback()

        self.assertTrue(respuesta["ok"])
        self.assertEqual(respuesta["origen"], "fallback")
        self.assertEqual(respuesta["fecha_captura_fallback"], "2026-10-16")
        self.assertIsNone(respuesta["error"])
        self.assertTrue(respuesta["advertencias"])

    @patch("agentes.tools.externa._cargar_fallback_catalogo")
    @patch("agentes.tools.externa._consultar_catalogo_ckan")
    def test_si_api_y_fallback_fallan_conserva_error(
        self,
        mock_api,
        mock_fallback,
    ) -> None:
        error_original = crear_error_api()
        mock_api.return_value = error_original
        mock_fallback.side_effect = RuntimeError("No hay capturas válidas.")

        respuesta = externa.consultar_catalogo_con_fallback()

        self.assertFalse(respuesta["ok"])
        self.assertEqual(respuesta["error"], error_original["error"])
        self.assertTrue(
            any(
                "No hay capturas válidas" in advertencia
                for advertencia in respuesta["advertencias"]
            )
        )


if __name__ == "__main__":
    unittest.main()
