# tests/test_import_global.py
import importlib
import traceback
import pytest

# Ajusta estas rutas a las del proyecto real.
MODULES = [
    "agentes.state",
    "agentes.graph",
    "agentes.nodes.supervisor",
    "agentes.llm",
    "agentes.nodes.sintetizar",
    "agentes.nodes.aplicar",
    "agentes.agent",
    "agentes.runtime",
    "agentes.nodes.documental",
    "agentes.nodes.instalaciones",
    "agentes.nodes.vision",
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