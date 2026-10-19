"""Tests del parser de avisos HTML (_ExtractorAvisoHTML)."""

import unittest

from agentes.tools.externa import _ExtractorAvisoHTML


HTML_UN_BLOQUE = """
<html><body>
<div class="info-seccion">
  <div class="modal-alert modal-info">
    <p class="title-modal">Aviso a usuarios/as</p>
    <p>Cierre completo por obras hasta nuevo aviso.</p>
  </div>
</div>
</body></html>
"""

HTML_DOS_BLOQUES = """
<html><body>
<div class="info-seccion">
  <div class="modal-alert modal-info">
    <p class="title-modal">Aviso a usuarios/as</p>
    <p>Cierre temporal de piscinas.</p>
  </div>
</div>
<div class="info-seccion">
  <div class="modal-alert modal-info">
    <p class="title-modal">Aviso a usuarios/as</p>
    <p>Ausencia de agua caliente.</p>
  </div>
</div>
</body></html>
"""

HTML_SIN_AVISO = """
<html><body>
<div class="info-seccion"><p>Horario de 9 a 21h.</p></div>
</body></html>
"""

HTML_MODAL_SIN_TITULO = """
<html><body>
<div class="modal-alert modal-info">
  <p>Otra cosa distinta.</p>
</div>
</body></html>
"""

HTML_CON_ENTIDADES = """
<html><body>
<div class="modal-alert">
  <p class="title-modal">Aviso a usuarios/as</p>
  <p>Del d&iacute;a 1 de julio. Duraci&oacute;n cinco meses.</p>
</div>
</body></html>
"""


class TestExtractorAvisoHTML(unittest.TestCase):

    def _extraer(self, html: str):
        p = _ExtractorAvisoHTML()
        p.feed(html)
        p.close()
        return p.resultado()

    def test_un_bloque(self):
        detectado, textos = self._extraer(HTML_UN_BLOQUE)
        self.assertTrue(detectado)
        self.assertEqual(len(textos), 1)
        self.assertIn("Cierre completo por obras", textos[0])
        self.assertIn("Aviso a usuarios/as", textos[0])

    def test_dos_bloques_separados(self):
        detectado, textos = self._extraer(HTML_DOS_BLOQUES)
        self.assertTrue(detectado)
        self.assertEqual(len(textos), 2)
        self.assertIn("Cierre temporal de piscinas", textos[0])
        self.assertIn("Ausencia de agua caliente", textos[1])

    def test_sin_aviso(self):
        detectado, textos = self._extraer(HTML_SIN_AVISO)
        self.assertFalse(detectado)
        self.assertEqual(textos, [])

    def test_modal_sin_titulo_no_cuenta(self):
        detectado, textos = self._extraer(HTML_MODAL_SIN_TITULO)
        self.assertFalse(detectado)
        self.assertEqual(textos, [])

    def test_entidades_html_decodificadas(self):
        detectado, textos = self._extraer(HTML_CON_ENTIDADES)
        self.assertTrue(detectado)
        self.assertIn("julio", textos[0])
        self.assertIn("cinco meses", textos[0])


if __name__ == "__main__":
    unittest.main()