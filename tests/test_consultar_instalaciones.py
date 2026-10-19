"""Tests de consultar_instalaciones (punto de entrada público)."""

import unittest
from unittest.mock import patch

from agentes.tools import externa


class TestConsultarInstalaciones(unittest.TestCase):

    @patch.object(externa, "consultar_catalogo_con_fallback")
    def test_modo_catalogo(self, mock_cat):
        mock_cat.return_value = {"ok": True, "datos": [], "modo": "catalogo"}
        r = externa.consultar_instalaciones("catalogo")
        self.assertEqual(r["modo"], "catalogo")
        mock_cat.assert_called_once()

    @patch.object(externa, "consultar_aviso_centro")
    def test_modo_avisos_con_centro(self, mock_aviso):
        mock_aviso.return_value = {"ok": True, "modo": "avisos", "datos": []}
        r = externa.consultar_instalaciones("avisos", "114782")
        self.assertEqual(r["modo"], "avisos")
        mock_aviso.assert_called_once_with("114782")

    def test_modo_avisos_sin_centro(self):
        r = externa.consultar_instalaciones("avisos")
        self.assertFalse(r["ok"])
        self.assertIn("centro_id", r["error"])

    def test_modo_invalido(self):
        r = externa.consultar_instalaciones("otro")
        self.assertFalse(r["ok"])
        self.assertIn("no soportado", r["error"])


if __name__ == "__main__":
    unittest.main()