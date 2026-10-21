
"""Tests del cargador de capturas locales de avisos."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from agentes.tools import externa


def crear_captura(fecha_captura: str) -> dict:
    """Genera una captura mínima válida para probar el cargador."""
    return {
        "metadata": {
            "fecha_captura": fecha_captura,
            "total_centros_consultados": 1,
        },
        "avisos": [
            {
                "centro_id": "114782",
                "centro_nombre": "Centro de prueba",
                "distrito": "MONCLOA-ARAVACA",
                "url_ficha": "https://www.madrid.es/ficha-test",
                "aviso_detectado": True,
                "texto_aviso": "Cierre por obras.",
                "fecha_consulta": fecha_captura,
            }
        ],
    }


class TestCargarFallbackAvisos(unittest.TestCase):

    def guardar_captura(self, directorio: Path, fecha: str) -> Path:
        """Guarda una captura de prueba con nombre basado en su fecha."""
        ruta = directorio / f"avisos_centros_{fecha[:10]}.json"
        ruta.write_text(
            json.dumps(crear_captura(fecha), ensure_ascii=False),
            encoding="utf-8",
        )
        return ruta

    def test_captura_reciente_valida(self):
        with TemporaryDirectory() as temporal:
            directorio = Path(temporal)
            fecha = datetime.now(timezone.utc).isoformat()
            self.guardar_captura(directorio, fecha)

            registros, fecha_captura, ruta = (
                externa._cargar_fallback_avisos(directorio)
            )

            self.assertIn("114782", registros)
            self.assertEqual(registros["114782"]["aviso_detectado"], True)
            self.assertEqual(fecha_captura, fecha)
            self.assertTrue(ruta.exists())

    def test_captura_antigua_se_rechaza(self):
        with TemporaryDirectory() as temporal:
            directorio = Path(temporal)
            fecha_antigua = (
                datetime.now(timezone.utc)
                - timedelta(
                    days=externa.MAX_EDAD_FALLBACK_AVISOS_DIAS + 1
                )
            ).isoformat()
            self.guardar_captura(directorio, fecha_antigua)

            with self.assertRaisesRegex(
                RuntimeError, "ninguna captura de avisos válida"
            ):
                externa._cargar_fallback_avisos(directorio)

    def test_captura_antigua_no_impide_usar_otra_reciente(self):
        with TemporaryDirectory() as temporal:
            directorio = Path(temporal)

            fecha_antigua = (
                datetime.now(timezone.utc)
                - timedelta(
                    days=externa.MAX_EDAD_FALLBACK_AVISOS_DIAS + 2
                )
            ).isoformat()
            self.guardar_captura(directorio, fecha_antigua)

            fecha_reciente = datetime.now(timezone.utc).isoformat()
            ruta_reciente = self.guardar_captura(
                directorio, fecha_reciente
            )

            registros, fecha_captura, ruta = (
                externa._cargar_fallback_avisos(directorio)
            )

            self.assertIn("114782", registros)
            self.assertEqual(fecha_captura, fecha_reciente)
            self.assertEqual(ruta, ruta_reciente)


if __name__ == "__main__":
    unittest.main()
