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
                if (fullname in {"agentes.nodes.documental", "agentes.nodes.instalaciones"}
                        or fullname == "agentes.tools.rag"
                        or fullname.split('.')[0] in {"rag", "chromadb"}):
                    raise AssertionError(f"Carga inesperada: {fullname}")

        sys.meta_path.insert(0, BlockRag())
        from agentes.agent import AgentService
        from agentes.runtime import crear_servicio
        import agentes.tools

        service = crear_servicio(modo="demo")
        state = service.procesar_turno("Consulta de prueba", service.nueva_conversacion())
        assert state["pendiente_hitl"]
        assert state["approved"] is None
    ''')


def test_real_runtime_construction_with_tool_double_does_not_import_rag_or_chroma():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder
        from types import ModuleType, SimpleNamespace

        class BlockRag(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {"rag", "chromadb"}:
                    raise AssertionError(f"Carga inesperada: {fullname}")

        def forbidden(*args, **kwargs):
            raise AssertionError("Consulta inesperada durante construcción")

        sys.meta_path.insert(0, BlockRag())
        tool = ModuleType("agentes.tools.rag")
        tool.rag_preguntar = forbidden
        sys.modules["agentes.tools.rag"] = tool

        def block_network(event, args):
            if event in {"socket.connect", "socket.getaddrinfo"}:
                raise AssertionError(f"Red inesperada: {event}")
        sys.addaudithook(block_network)

        import agentes.nodes.instalaciones as ni
        ni.consultar_instalaciones = forbidden
        from agentes.runtime import crear_servicio_real
        from agentes.supervisor_llm import crear_proveedor_rutas
        provider = crear_proveedor_rutas(
            adapter=SimpleNamespace(generate=forbidden), message_factory=SimpleNamespace)
        service = crear_servicio_real(route_provider=provider)
        assert service.nueva_conversacion()
        assert not any(name.split('.')[0] in {"rag", "chromadb"} for name in sys.modules)
    ''')


def test_common_client_helpers_without_ui_backend_or_io():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder

        class BlockDependencies(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {"streamlit", "clientes", "langgraph", "rag"}:
                    raise AssertionError(f"Carga inesperada: {fullname}")
                if fullname in {"agentes.agent", "agentes.runtime", "agentes.graph"}:
                    raise AssertionError(f"Carga inesperada: {fullname}")

        sys.meta_path.insert(0, BlockDependencies())
        from agentes.validation import (
            validar_entrada, validar_mensaje, validar_decision, validar_id, validar_estado,
        )
        from agentes.secret_filter import sin_secretos

        def block_io(event, args):
            if event in {"open", "builtins.input", "socket.connect", "socket.getaddrinfo"}:
                raise AssertionError(f"IO inesperado: {event}")

        sys.addaudithook(block_io)
        validar_entrada("Consulta")
        validar_mensaje("Consulta")
        validar_decision(False)
        validar_id("hilo")
        estado = {"thread_id": "hilo", "pendiente_hitl": True,
                  "plan_id": "plan", "plan": ["Paso"]}
        assert validar_estado(estado, "hilo") is estado
        assert sin_secretos("Basic dXNlcjpwYXNz") == "Basic [OCULTO]"
        valor = {"datos": [{"password": ["privado", "otro privado"]}]}
        assert "privado" not in sin_secretos(valor)
        assert valor["datos"][0]["password"] == ["privado", "otro privado"]
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
