"""
config.py — Configuración compartida del proyecto de agentes.

Requisitos de agentes/tools/vision.py:
- ROOT: raíz del proyecto para resolver rutas relativas.
- IMAGEN_DEFAULT_PATH: imagen demo usada por la tool de visión.
- VISION_MODEL: modelo multimodal imagen -> texto.
"""

from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Raíz real del repositorio.
ROOT = Path(__file__).resolve().parent

# Recursos compartidos.
ASSETS_DIR = ROOT / "assets"

# Imagen obligatoria para la demo multimodal.
IMAGEN_DEFAULT_PATH = ASSETS_DIR / "imagen_demo.jpg"

# Modelo de visión usado por agentes/tools/vision.py.
VISION_MODEL = os.getenv("VISION_MODEL", "gemini-2.5-flash")