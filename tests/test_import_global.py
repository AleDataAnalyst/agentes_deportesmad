# tests/test_import_global.py
import importlib
import traceback
import pytest

# Ajusta estas rutas a las del proyecto real.
MODULES = [
    "agentes.state",
    "agentes.graph",
    "agentes.supervisor",
    "agentes.llm",
    "agentes.sintetizar",
    "agentes.aplicar",
    "agentes.checkpointer",
    "agentes.service",
    "agentes.documental",
    "agentes.instalaciones",
    "agentes.trace",
    "agentes.tools.registry",
    "agentes.tools.vision",
    "agentes.tools.rag",
    "agentes.grafo_documental",
    "agentes.documental_adapter",
    "agentes.nodes",
]


@pytest.mark.parametrize("nombre", MODULES)
def test_importacion_global(nombre):
    """Cada módulo debe importarse sin lanzar excepción."""
    try:
        importlib.import_module(nombre)
    except Exception as e:
        raise AssertionError(
            f"El módulo '{nombre}' no pudo importarse. "
            f"Detalle:\n{traceback.format_exc()}"
        ) from e