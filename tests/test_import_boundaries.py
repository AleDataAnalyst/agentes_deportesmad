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
