"""Comprueba las importaciones en procesos nuevos, sin cachés de otros tests."""

from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


def run_python(code):
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_backend_imports_without_loading_documental_or_rag():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder

        class BlockRag(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if (fullname == "agentes.nodes.documental"
                        or fullname == "agentes.tools.rag"
                        or fullname == "rag" or fullname.startswith("rag.")):
                    raise AssertionError(f"Carga inesperada: {fullname}")

        sys.meta_path.insert(0, BlockRag())
        from agentes.agent import AgentService
        from agentes.demo import crear_servicio_demo
        import agentes.tools

        service = crear_servicio_demo()
        state = service.procesar_turno("Consulta de prueba", service.nueva_conversacion())
        assert state["pendiente_hitl"]
        assert state["approved"] is None
    ''')


def test_real_construction_does_not_load_pipeline_or_query_models():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder

        class BlockPipeline(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "rag" or fullname.startswith("rag."):
                    raise AssertionError(f"Carga de pipeline durante construcción: {fullname}")

        sys.meta_path.insert(0, BlockPipeline())
        from agentes.runtime import crear_servicio_real
        service = crear_servicio_real()
        assert service.consultar_estado(service.nueva_conversacion())["specialist_results"] == {}
    ''')


def test_rag_tests_can_be_collected_without_pipeline_or_chroma():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder

        class BlockPipeline(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if (fullname == "rag" or fullname.startswith("rag.")
                        or fullname == "chromadb" or fullname.startswith("chromadb.")):
                    raise AssertionError(f"Efecto lateral durante colección: {fullname}")

        sys.meta_path.insert(0, BlockPipeline())
        import pytest
        assert pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider",
                            "tests/test_tool_rag.py", "tests/test_tools.py",
                            "tests/test_node_documental.py"]) == 0
    ''')


@pytest.mark.parametrize("package,module,export", [
    ("agentes.nodes", "agentes.nodes.documental", "nodo_documental"),
    ("agentes.tools", "agentes.tools.rag", "rag_preguntar"),
])
def test_public_export_preserves_original_callable(package, module, export):
    # Dobles explícitos: prueba la exportación, no la ejecución del especialista.
    run_python(f'''
        import importlib
        import sys
        from types import ModuleType

        package = importlib.import_module({package!r})
        assert {module!r} not in sys.modules
        target = ModuleType({module!r})
        def implementation(*args, **kwargs):
            return {{}}
        setattr(target, {export!r}, implementation)
        sys.modules[{module!r}] = target
        from {package} import {export}
        assert {export} is implementation
        try:
            package.nonexistent_export
        except AttributeError:
            pass
        else:
            raise AssertionError("Una exportación desconocida debe fallar")
    ''')
