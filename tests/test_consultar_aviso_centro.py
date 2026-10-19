"""Tests de consultar_aviso_centro con mocks (sin red)."""

import unittest
from unittest.mock import patch

from agentes.tools import externa


def _catalogo_ok(centro_pk="114782"):
    return {
        "ok": True,
        "modo": "catalogo",
        "datos": [
            {
                "pk": centro_pk,
                "nombre": "Centro de prueba",
                "distrito": "MONCLOA-ARAVACA",
                "content_url": "https://www.madrid.es/ficha-test",
            }
        ],
        "fuente": "api",
        "origen": "api",
        "fecha_consulta": "2026-10-19T10:00:00+02:00",
        "fecha_captura_fallback": None,
        "advertencias": [],
        "error": None,
    }


class TestConsultarAvisoCentro(unittest.TestCase):

    def test_centro_id_vacio(self):
        r = externa.consultar_aviso_centro("")
        self.assertFalse(r["ok"])
        self.assertIn("obligatorio", r["error"])

    @patch.object(externa, "consultar_catalogo_con_fallback")
    def test_centro_inexistente(self, mock_catalogo):
        mock_catalogo.return_value = _catalogo_ok()
        r = externa.consultar_aviso_centro("999999")
        self.assertFalse(r["ok"])
        self.assertIn("no aparece", r["error"])

    @patch.object(externa, "_validar_url_oficial", side_effect=lambda u: u)
    @patch.object(externa, "_consultar_pagina_aviso")
    @patch.object(externa, "consultar_catalogo_con_fallback")
    def test_aviso_detectado_un_bloque(self, mock_cat, mock_html, _m):
        mock_cat.return_value = _catalogo_ok()
        mock_html.return_value = (True, ["Cierre por obras."])
        r = externa.consultar_aviso_centro("114782")
        self.assertTrue(r["ok"])
        self.assertEqual(r["origen"], "html")
        self.assertEqual(len(r["datos"]), 1)
        self.assertTrue(r["datos"][0]["aviso_detectado"])
        self.assertEqual(r["datos"][0]["texto_aviso"], "Cierre por obras.")

    @patch.object(externa, "_validar_url_oficial", side_effect=lambda u: u)
    @patch.object(externa, "_consultar_pagina_aviso")
    @patch.object(externa, "consultar_catalogo_con_fallback")
    def test_aviso_detectado_dos_bloques(self, mock_cat, mock_html, _m):
        mock_cat.return_value = _catalogo_ok()
        mock_html.return_value = (True, ["Bloque A", "Bloque B"])
        r = externa.consultar_aviso_centro("114782")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["datos"]), 2)
        self.assertEqual(r["datos"][0]["texto_aviso"], "Bloque A")
        self.assertEqual(r["datos"][1]["texto_aviso"], "Bloque B")

    @patch.object(externa, "_validar_url_oficial", side_effect=lambda u: u)
    @patch.object(externa, "_consultar_pagina_aviso")
    @patch.object(externa, "consultar_catalogo_con_fallback")
    def test_sin_aviso(self, mock_cat, mock_html, _m):
        mock_cat.return_value = _catalogo_ok()
        mock_html.return_value = (False, [])
        r = externa.consultar_aviso_centro("114782")
        self.assertTrue(r["ok"])
        self.assertFalse(r["datos"][0]["aviso_detectado"])
        self.assertTrue(
            any("no garantiza" in a for a in r["advertencias"])
        )

    @patch.object(externa, "_cargar_fallback_avisos")
    @patch.object(externa, "_consultar_pagina_aviso")
    @patch.object(externa, "consultar_catalogo_con_fallback")
    def test_fallo_html_usa_fallback(self, mock_cat, mock_html, mock_fb):
        mock_cat.return_value = _catalogo_ok()
        mock_html.side_effect = RuntimeError("HTTP 403")
        mock_fb.return_value = (
            {
                "114782": {
                    "centro_id": "114782",
                    "centro_nombre": "Centro de prueba",
                    "distrito": "MONCLOA-ARAVACA",
                    "url_ficha": "https://www.madrid.es/ficha-test",
                    "aviso_detectado": True,
                    "texto_aviso": "Texto histórico.",
                    "fecha_consulta": "2026-10-16T10:00:00+02:00",
                }
            },
            "2026-10-16",
            __import__("pathlib").Path("avisos_centros_2026-10-16.json"),
        )
        r = externa.consultar_aviso_centro("114782")
        self.assertTrue(r["ok"])
        self.assertEqual(r["origen"], "fallback")
        self.assertEqual(r["fecha_captura_fallback"], "2026-10-16")

    @patch.object(externa, "_cargar_fallback_avisos")
    @patch.object(externa, "_consultar_pagina_aviso")
    @patch.object(externa, "consultar_catalogo_con_fallback")
    def test_fallo_html_y_sin_fallback(self, mock_cat, mock_html, mock_fb):
        mock_cat.return_value = _catalogo_ok()
        mock_html.side_effect = RuntimeError("HTTP 403")
        mock_fb.side_effect = RuntimeError("No hay capturas")
        r = externa.consultar_aviso_centro("114782")
        self.assertFalse(r["ok"])
        self.assertIn("fallback", r["error"])


if __name__ == "__main__":
    unittest.main()