"""Las consultas reales se ejecutan únicamente por petición explícita."""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration", action="store_true", default=False,
        help="Ejecutar también pruebas que requieren servicios o índices reales",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="requiere --run-integration y recursos reales")
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(skip)


"""Configuración común de pytest."""

@pytest.fixture(autouse=True)
def _especialistas_por_reglas(monkeypatch):
    """Los tests no llaman a modelos reales salvo que activen el modo llm ellos mismos."""
    monkeypatch.setenv("ESPECIALISTAS_MODO", "reglas")
