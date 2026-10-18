"""Las evaluaciones con modelos requieren una petición explícita al ejecutar."""
import pytest


def pytest_addoption(parser):
    parser.addoption("--run-rag-eval", action="store_true", default=False,
                     help="Ejecuta las evaluaciones del corpus con proveedores reales")


def pytest_configure(config):
    config.addinivalue_line("markers", "rag_eval: evaluación con índice y modelos reales")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-rag-eval"):
        skip = pytest.mark.skip(reason="evaluación real opt-in: --run-rag-eval")
        for item in items:
            if "rag_eval" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def indice_real():
    # Se evalúa tras recoger los tests, y solo si se pide la evaluación real.
    # La lectura no crea colecciones. Un índice ausente es un bloqueo visible.
    from rag.retrieve import obtener_coleccion
    assert obtener_coleccion().count() > 0, "RAG_INDEX_EMPTY: índice vacío"
