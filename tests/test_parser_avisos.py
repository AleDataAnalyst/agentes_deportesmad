"""Tests del extractor de avisos HTML (_ExtractorAvisoHTML)."""

import unittest

from agentes.tools.externa import _ExtractorAvisoHTML


def extraer(html: str) -> tuple[bool | None, list[str]]:
    extractor = _ExtractorAvisoHTML()
    extractor.feed(html)
    extractor.close()
    return extractor.resultado()


class TestExtractorAvisoHTML(unittest.TestCase):

    def test_html_normal_detecta(self):
        html = (
            '<div class="modal-alert">'
            "<h3 class=\"title-modal\">Aviso a usuarios/as</h3>"
            "<p>Cierre por obras.</p>"
            "</div>"
        )
        detectado, bloques = extraer(html)
        self.assertTrue(detectado)
        self.assertEqual(len(bloques), 1)
        self.assertIn("Cierre por obras", bloques[0])

    def test_br_simple_detecta(self):
        html = (
            '<div class="modal-alert">'
            '<h3 class="title-modal">Aviso a usuarios/as</h3>'
            "<p>Linea 1<br>Linea 2</p>"
            "</div>"
        )
        detectado, bloques = extraer(html)
        self.assertTrue(detectado, "Un <br> no debe romper el parser")
        self.assertEqual(len(bloques), 1)
        self.assertIn("Linea 2", bloques[0])

    def test_br_autocierre_detecta(self):
        html = (
            '<div class="modal-alert">'
            '<h3 class="title-modal">Aviso a usuarios/as</h3>'
            "<p>Linea 1<br/>Linea 2</p>"
            "</div>"
        )
        detectado, bloques = extraer(html)
        self.assertTrue(detectado)
        self.assertEqual(len(bloques), 1)

    def test_img_sin_cierre_detecta(self):
        html = (
            '<div class="modal-alert">'
            '<h3 class="title-modal">Aviso a usuarios/as</h3>'
            '<img src="x.png">'
            "<p>Cierre por obras.</p>"
            "</div>"
        )
        detectado, bloques = extraer(html)
        self.assertTrue(detectado, "Un <img> no debe romper el parser")
        self.assertEqual(len(bloques), 1)

    def test_p_sin_cerrar_detecta(self):
        html = (
            '<div class="modal-alert">'
            '<h3 class="title-modal">Aviso a usuarios/as</h3>'
            "<p>Cierre por obras."
            "</div>"
        )
        detectado, bloques = extraer(html)
        self.assertTrue(detectado, "Un <p> sin cerrar no debe romper el parser")
        self.assertEqual(len(bloques), 1)

    def test_modal_sin_cierre_es_no_verificable(self):
        html = (
            '<div class="modal-alert">'
            '<h3 class="title-modal">Aviso a usuarios/as</h3>'
            "<p>Cierre por obras.</p>"
            # falta </div>
        )
        detectado, bloques = extraer(html)
        self.assertIsNone(detectado, "Un modal abierto no es verificable")
        self.assertEqual(bloques, [])

    def test_dos_modales_se_extraen_ambos(self):
        html = (
            '<div class="modal-alert">'
            '<h3 class="title-modal">Aviso a usuarios/as</h3>'
            "<p>Cierre por obras.</p>"
            "</div>"
            "<p>Texto intermedio</p>"
            '<div class="modal-alert">'
            '<h3 class="title-modal">Aviso a usuarios/as</h3>'
            "<p>Piscina cerrada.</p>"
            "</div>"
        )
        detectado, bloques = extraer(html)
        self.assertTrue(detectado)
        self.assertEqual(len(bloques), 2)

    def test_sin_modal_devuelve_false(self):
        html = "<html><body><p>Sin avisos</p></body></html>"
        detectado, bloques = extraer(html)
        self.assertFalse(detectado)
        self.assertEqual(bloques, [])


if __name__ == "__main__":
    unittest.main()