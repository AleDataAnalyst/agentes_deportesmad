"""Tests del nodo especialista de instalaciones con el contrato real."""

import unittest
from unittest.mock import patch

from agentes.contracts import ToolResult
from agentes.nodes import instalaciones
from agentes.state import initial_state


def _tool_result_catalogo_ok() -> dict:
    return {
        "ok": True,
        "modo": "catalogo",
        "datos": [
            {
                "pk": "101",
                "nombre": "Centro A",
                "distrito": "SALAMANCA",
                "content_url": "https://www.madrid.es/a",
            },
            {
                "pk": "102",
                "nombre": "Centro B",
                "distrito": "RETIRO",
                "content_url": "https://www.madrid.es/b",
            },
        ],
        "fuente": "CKAN",
        "origen": "api",
        "fecha_consulta": "2026-10-19T10:00:00+02:00",
        "fecha_captura_fallback": None,
        "advertencias": [],
        "error": None,
    }


def _tool_result_avisos_ok() -> dict:
    return {
        "ok": True,
        "modo": "avisos",
        "datos": [
            {
                "centro_id": "114782",
                "centro_nombre": "Alfredo Goyeneche",
                "distrito": "MONCLOA-ARAVACA",
                "url_ficha": "https://www.madrid.es/a",
                "aviso_detectado": True,
                "texto_aviso": "Cierre por obras.",
                "origen": "html",
                "fecha_consulta": "2026-10-19T10:00:00+02:00",
                "advertencias": [],
            }
        ],
        "fuente": "https://www.madrid.es/a",
        "origen": "html",
        "fecha_consulta": "2026-10-19T10:00:00+02:00",
        "fecha_captura_fallback": None,
        "advertencias": [],
        "error": None,
    }


def _tool_result_error() -> dict:
    return {
        "ok": False,
        "modo": "avisos",
        "datos": [],
        "fuente": "ficha",
        "origen": "html",
        "fecha_consulta": "2026-10-19T10:00:00+02:00",
        "fecha_captura_fallback": None,
        "advertencias": ["Fallo de red"],
        "error": "HTTP 403",
    }


class TestNodoInstalaciones(unittest.TestCase):

    def test_modo_catalogo_mapea_a_tool_result_ok(self):
        with patch.object(instalaciones, "consultar_instalaciones",
                          return_value=_tool_result_catalogo_ok()):
            state = initial_state("lista de centros")
            patch_result = instalaciones.nodo_instalaciones(state)

        self.assertIn("specialist_results", patch_result)
        tr = patch_result["specialist_results"]["instalaciones"]
        self.assertIsInstance(tr, ToolResult)
        self.assertEqual(tr.status, "ok")
        self.assertEqual(len(tr.evidence), 2)
        self.assertEqual(tr.evidence[0].source, "https://www.madrid.es/a")
        self.assertIn("Centro A", tr.answer)
        self.assertEqual(tr.data["modo"], "catalogo")

    def test_modo_avisos_con_pk_en_mensaje(self):
        with patch.object(instalaciones, "consultar_instalaciones",
                          return_value=_tool_result_avisos_ok()) as mock_tool:
            state = initial_state("¿hay avisos en el centro 114782?")
            patch_result = instalaciones.nodo_instalaciones(state)

        mock_tool.assert_called_once_with(modo="avisos", centro_id="114782")
        tr = patch_result["specialist_results"]["instalaciones"]
        self.assertEqual(tr.status, "ok")
        self.assertEqual(len(tr.evidence), 1)
        self.assertIn("Cierre por obras", tr.evidence[0].content)

    @patch.object(instalaciones, "resolver_centro_por_nombre", return_value=[])
    @patch.object(instalaciones, "consultar_instalaciones")
    def test_palabras_aviso_sin_pk(self, mock_tool, mock_resolver):
        state = {
            "user_message": "¿hay algún cierre por obras?",
            "specialist_results": {},
        }
        resultado = instalaciones.nodo_instalaciones(state)

        # Ya no se llama a la tool: se pide aclaración (abstained).
        mock_tool.assert_not_called()
        mock_resolver.assert_called_once_with("¿hay algún cierre por obras?")

        tr = resultado["specialist_results"]["instalaciones"]
        self.assertEqual(tr.status, "abstained")
        self.assertTrue(tr.data.get("requiere_aclaracion"))
        self.assertIn("identificador del centro", tr.answer)

    def test_error_mapea_a_status_error(self):
        with patch.object(instalaciones, "consultar_instalaciones",
                          return_value=_tool_result_error()):
            state = initial_state("¿avisos en 114782?")
            patch_result = instalaciones.nodo_instalaciones(state)

        tr = patch_result["specialist_results"]["instalaciones"]
        self.assertEqual(tr.status, "error")
        self.assertEqual(tr.error, "HTTP 403")
        self.assertIn("Fallo de red", tr.data["advertencias"])

    def test_excepcion_no_tumba_el_grafo(self):
        with patch.object(instalaciones, "consultar_instalaciones",
                          side_effect=RuntimeError("boom")):
            state = initial_state("lista")
            patch_result = instalaciones.nodo_instalaciones(state)

        tr = patch_result["specialist_results"]["instalaciones"]
        self.assertEqual(tr.status, "error")
        # El nodo no propaga el mensaje de la excepción (review de Ale).
        self.assertNotIn("boom", tr.error)
        self.assertIn("No se pudo completar", tr.error)

    def test_conserva_resultados_previos(self):
        previo = ToolResult(status="ok", answer="x", evidence=[], data={})
        with patch.object(instalaciones, "consultar_instalaciones",
                          return_value=_tool_result_catalogo_ok()):
            state = initial_state("lista")
            state["specialist_results"] = {"documental": previo}
            patch_result = instalaciones.nodo_instalaciones(state)

        self.assertIn("documental", patch_result["specialist_results"])
        self.assertIn("instalaciones", patch_result["specialist_results"])
        self.assertIs(
            patch_result["specialist_results"]["documental"], previo,
        )

    def test_debug_trace_es_lista_de_strings(self):
        with patch.object(instalaciones, "consultar_instalaciones",
                          return_value=_tool_result_catalogo_ok()):
            state = initial_state("lista")
            patch_result = instalaciones.nodo_instalaciones(state)

        trace = patch_result["debug_trace"]
        self.assertIsInstance(trace, list)
        self.assertTrue(all(isinstance(x, str) for x in trace))
        self.assertTrue(any("instalaciones:" in x for x in trace))


if __name__ == "__main__":
    unittest.main()
