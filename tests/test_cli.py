"""CLI contra servicio/grafo reales y especialistas dobles; sin RAG ni HTTP."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from agentes.agent import AgentService
from agentes.contracts import Evidence, ToolResult
from agentes.nodes.aplicar import aplicar
from agentes.nodes.sintetizar import sintetizar
from agentes.settings import AgentSettings
from clientes import cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sesion(monkeypatch):
    eventos = {"pedidos": [], "decisiones": [], "tools": []}

    def especialista(rol):
        def nodo(estado):
            eventos["tools"].append(rol)
            resultado = ToolResult(
                "ok", "[SIMULADO] Evidencia de prueba",
                evidence=[Evidence(f"test://{rol}", "")],
                data={"limitaciones": ["[SIMULADO] Límite de prueba"],
                      "origen": "fallback", "fecha_captura_fallback": "13/10",
                      "request_id": "test-request",
                      "eventos": [{"tool": "test_tool", "ok": True, "ms": 1,
                                   "args": {"privado": "NO_VOLCAR_ARGUMENTOS"}}]},
            )
            return {"specialist_results": {**estado["specialist_results"], rol: resultado},
                    "debug_trace": [f"{rol}: evento nuevo"]}
        return nodo

    servicio = AgentService(
        documental_node=especialista("documental"),
        instalaciones_node=especialista("instalaciones"),
        sintetizar_node=sintetizar, aplicar_node=aplicar,
        settings=AgentSettings(max_iter=8),
    )
    procesar = servicio.procesar_turno
    resolver = servicio.resolver_plan

    def procesar_contado(mensaje, hilo):
        resultado = procesar(mensaje, hilo)
        eventos["pedidos"].append((mensaje, hilo, resultado))
        return resultado

    def resolver_contado(hilo, aprobado, *, plan_id):
        resultado = resolver(hilo, aprobado, plan_id=plan_id)
        eventos["decisiones"].append((hilo, aprobado, plan_id, resultado))
        return resultado

    monkeypatch.setattr(servicio, "procesar_turno", procesar_contado)
    monkeypatch.setattr(servicio, "resolver_plan", resolver_contado)
    return servicio, eventos


def conversar(servicio, entradas, **kwargs):
    entradas = iter(entradas)
    salida = []
    codigo = cli.ejecutar_interactivo(
        servicio, leer=lambda _: next(entradas, "/salir"), escribir=salida.append, **kwargs,
    )
    return codigo, "\n".join(salida)


@pytest.mark.parametrize("comando,aprobado", [("/aprobar", True), ("/rechazar", False)])
def test_cli_hitl_same_thread_next_request_and_new_conversation(sesion, comando, aprobado):
    servicio, eventos = sesion
    codigo, salida = conversar(servicio, [
        "Consulta 1", "No debe enviarse con plan pendiente", "/estado", "/debug",
        comando, "Consulta 2", "/rechazar", "/nueva", "/aprobar",
        "Consulta 3", "/rechazar", "/salir",
    ])
    assert codigo == 0
    assert [p[0] for p in eventos["pedidos"]] == ["Consulta 1", "Consulta 2", "Consulta 3"]
    primero, segundo, tercero = eventos["pedidos"]
    assert primero[1] == segundo[1] and tercero[1] != primero[1]
    assert len({p[2]["plan_id"] for p in eventos["pedidos"]}) == 3
    assert all(p[2]["approved"] is None and p[2]["pendiente_hitl"] for p in eventos["pedidos"])
    assert [d[1] for d in eventos["decisiones"]] == [aprobado, False, False]
    for pedido, decision in zip(eventos["pedidos"], eventos["decisiones"]):
        assert decision[0] == pedido[1] and decision[2] == pedido[2]["plan_id"]
        assert not decision[3]["pendiente_hitl"] and decision[3]["done"] is decision[1]
    assert eventos["tools"] == ["documental", "instalaciones"] * 3
    assert "Hay un plan pendiente" in salida and "No hay un plan pendiente" in salida
    assert "Fuente: test://documental" in salida and "Fuente: test://instalaciones" in salida
    assert "Límite de prueba" in salida and "Fallback histórico" in salida
    assert "fecha_captura_fallback: 13/10" in salida
    assert "request_id=test-request" in salida and "test_tool" in salida
    assert "NO_VOLCAR_ARGUMENTOS" not in salida
    if aprobado:
        assert "Plan informativo aprobado" in salida
    assert "Propuesta rechazada" in salida


@pytest.mark.parametrize("fin", [EOFError, KeyboardInterrupt])
def test_cli_eof_or_interrupt_never_resolves_pending_plan(sesion, fin):
    servicio, eventos = sesion
    salida = []

    def terminar(_):
        raise fin()

    assert cli.ejecutar_interactivo(
        servicio, mensaje="Consulta inicial", leer=terminar, escribir=salida.append,
    ) == 0
    assert not eventos["decisiones"]
    assert servicio.consultar_estado(eventos["pedidos"][0][1])["pendiente_hitl"]
    assert "Salida sin decisiones automáticas" in "\n".join(salida)


def test_cli_unknown_commands_and_empty_lines_do_not_query(sesion):
    servicio, eventos = sesion
    codigo, salida = conversar(servicio, ["", "  ", "/desconocido", "/ayuda", "/estado", "/salir"])
    assert codigo == 0 and eventos["tools"] == [] and eventos["pedidos"] == []
    assert "Comando desconocido" in salida


def test_cli_resolution_error_preserves_plan_until_explicit_retry(sesion, monkeypatch):
    servicio, eventos = sesion
    resolver = servicio.resolver_plan
    intentos = []

    def fallo_una_vez(hilo, aprobado, *, plan_id):
        intentos.append(plan_id)
        if len(intentos) == 1:
            raise ValueError("PLAN_NOT_CURRENT: fallo inducido")
        return resolver(hilo, aprobado, plan_id=plan_id)

    monkeypatch.setattr(servicio, "resolver_plan", fallo_una_vez)
    codigo, salida = conversar(servicio, ["Consulta", "/aprobar", "/estado", "/rechazar", "/salir"])
    assert codigo == 0 and "Error: PLAN_NOT_CURRENT" in salida
    assert "Plan informativo aprobado" not in salida
    assert len(intentos) == 2 and intentos[0] == intentos[1]
    assert [d[1] for d in eventos["decisiones"]] == [False]


def test_cli_processing_error_allows_new_conversation(sesion, monkeypatch):
    servicio, eventos = sesion
    procesar = servicio.procesar_turno

    def fallar(mensaje, hilo):
        if mensaje == "Fallo":
            raise RuntimeError("Fallo de procesamiento inducido")
        return procesar(mensaje, hilo)

    monkeypatch.setattr(servicio, "procesar_turno", fallar)
    codigo, salida = conversar(servicio, ["Fallo", "/nueva", "Recuperada", "/rechazar", "/salir"])
    assert codigo == 0 and "Error: Fallo de procesamiento inducido" in salida
    assert [p[0] for p in eventos["pedidos"]] == ["Recuperada"]
    assert len(eventos["decisiones"]) == 1


@pytest.mark.parametrize("lectura", ["/estado", "/debug"])
def test_failed_specialist_reports_incomplete_thread_and_recovers_with_new(lectura, monkeypatch):
    llamadas = []
    hilos = []

    def documental(estado):
        llamadas.append((estado["user_message"], estado["thread_id"]))
        if estado["user_message"] == "Fallo":
            raise RuntimeError("Fallo real dentro del nodo especialista")
        return {"specialist_results": {"documental": ToolResult("ok", "Respuesta simulada")}}

    servicio = AgentService(
        documental_node=documental, instalaciones_node=lambda estado: {},
        sintetizar_node=sintetizar, aplicar_node=aplicar, settings=AgentSettings(max_iter=8),
    )
    procesar = servicio.procesar_turno
    pedidos = []

    def contar(mensaje, hilo):
        pedidos.append(mensaje)
        return procesar(mensaje, hilo)

    crear = servicio.nueva_conversacion

    def nueva():
        hilo = crear()
        hilos.append(hilo)
        return hilo

    monkeypatch.setattr(servicio, "procesar_turno", contar)
    monkeypatch.setattr(servicio, "nueva_conversacion", nueva)
    codigo, salida = conversar(servicio, [
        "Fallo", lectura, "No reenviar al hilo incompleto", lectura, "/aprobar",
        "/nueva", "Recuperada", "/rechazar", "/salir",
    ])
    antes_de_nueva = salida.split("Nueva conversación:")[0]
    assert codigo == 0
    assert "Ejecución incompleta en este hilo: usa /nueva" in antes_de_nueva
    assert "Conversación sin propuesta pendiente" not in antes_de_nueva
    assert "Ejecución incompleta (REQUEST_INCOMPLETE)." in antes_de_nueva
    assert "Error: REQUEST_INCOMPLETE:" not in salida
    assert pedidos == ["Fallo", "Recuperada"]
    assert llamadas == [("Fallo", hilos[0]), ("Recuperada", hilos[1])]
    assert servicio.consultar_estado(hilos[0])["ejecucion_incompleta"] is True
    assert servicio.consultar_estado(hilos[0])["approved"] is None
    assert servicio.consultar_estado(hilos[1])["ejecucion_incompleta"] is False
    assert "Propuesta rechazada" in salida


def test_cli_debug_is_bounded_and_does_not_mutate_state(sesion):
    from copy import deepcopy

    servicio, _ = sesion
    estado = servicio.procesar_turno("Consulta", servicio.nueva_conversacion())
    estado["debug_trace"] = [f"EVENTO_{i:03}" for i in range(40)]
    estado["specialist_results"]["documental"].data["eventos"] *= 12
    antes = deepcopy(estado)
    salida = []
    cli.mostrar_estado(estado, debug=True, escribir=salida.append)
    texto = "\n".join(salida)
    assert "EVENTO_000" not in texto and "EVENTO_010" in texto and "EVENTO_039" in texto
    assert "10 eventos anteriores omitidos" in texto
    assert "2 eventos de tools omitidos" in texto
    assert "NO_VOLCAR_ARGUMENTOS" not in texto
    assert estado == antes


@pytest.mark.parametrize("args,modo", [([], "real"), (["--modo", "demo"], "demo")])
def test_cli_main_uses_runtime_factory_once(args, modo, monkeypatch):
    from agentes import runtime

    servicio = object()
    llamadas = []

    def crear(*, modo):
        llamadas.append(modo)
        return servicio

    def interactuar(recibido, **opciones):
        assert recibido is servicio
        return 0

    monkeypatch.setattr(runtime, "crear_servicio", crear)
    monkeypatch.setattr(cli, "ejecutar_interactivo", interactuar)
    assert cli.main(args) == 0
    assert llamadas == [modo]


def test_cli_initialization_error_does_not_fall_back_to_demo(monkeypatch, capsys):
    from agentes import runtime

    llamadas = []

    def fallar(*, modo):
        llamadas.append(modo)
        raise RuntimeError("Montaje no disponible")

    monkeypatch.setattr(runtime, "crear_servicio", fallar)
    assert cli.main(["--modo", "real"]) == 1
    assert llamadas == ["real"]
    salida = capsys.readouterr()
    assert "Montaje no disponible" in salida.err and "DEMO SIMULADA" not in salida.out


def test_cli_empty_initial_message_is_rejected_before_factory(monkeypatch):
    from agentes import runtime

    def no_crear(**kwargs):
        pytest.fail("No construir servicio para argumentos inválidos")

    monkeypatch.setattr(runtime, "crear_servicio", no_crear)
    with pytest.raises(SystemExit) as exc:
        cli.main(["--mensaje", "  "])
    assert exc.value.code == 2


def test_main_help_does_not_import_backend():
    codigo = textwrap.dedent('''
        import sys
        from importlib.abc import MetaPathFinder
        class Block(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if (fullname.startswith("agentes.")
                        and fullname not in {"agentes.validation", "agentes.secret_filter"}):
                    raise AssertionError("El help no debe cargar el backend")
        sys.meta_path.insert(0, Block())
        from main import main
        main(["--help"])
    ''')
    resultado = subprocess.run([sys.executable, "-c", codigo], cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert resultado.returncode == 0, resultado.stderr
    assert "--modo" in resultado.stdout


def test_main_demo_terminal_entrypoint_manual_rejection():
    resultado = subprocess.run(
        [sys.executable, "main.py", "--modo", "demo", "--debug", "--mensaje", "Consulta simulada"],
        input="/rechazar\n/estado\n/salir\n", cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1", "MAX_ITER": "8"},
        capture_output=True, encoding="utf-8", timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "DEMO SIMULADA" in resultado.stdout
    assert "Plan pendiente de decisión" in resultado.stdout
    assert "Borrador rechazado" in resultado.stdout
    assert "pendiente_hitl=False" in resultado.stdout
    assert "done=False" in resultado.stdout


def test_pending_plan_blocks_new_conversation(sesion, monkeypatch):
    servicio, eventos = sesion
    crear = servicio.nueva_conversacion
    hilos = []

    def nueva():
        hilo = crear()
        hilos.append(hilo)
        return hilo

    monkeypatch.setattr(servicio, "nueva_conversacion", nueva)
    codigo, salida = conversar(servicio, ["Consulta", "/nueva", "Otra", "/rechazar", "/nueva", "/salir"])
    assert codigo == 0 and len(hilos) == 2
    assert len(eventos["pedidos"]) == len(eventos["decisiones"]) == 1
    assert eventos["decisiones"][0][0] == hilos[0]
    assert "antes de /nueva" in salida


def test_error_after_service_mutation_requires_state_refresh(sesion, monkeypatch):
    servicio, eventos = sesion
    procesar = servicio.procesar_turno

    def fallar_despues(mensaje, hilo):
        procesar(mensaje, hilo)
        raise RuntimeError("Fallo después de guardar el plan")

    monkeypatch.setattr(servicio, "procesar_turno", fallar_despues)
    codigo, salida = conversar(servicio, [
        "Consulta", "No enviar", "/aprobar", "/estado", "/nueva", "/rechazar", "/salir",
    ])
    assert codigo == 0
    assert len(eventos["pedidos"]) == 1
    assert [d[1] for d in eventos["decisiones"]] == [False]
    assert "Estado sin confirmar" in salida
    assert "Plan informativo aprobado" not in salida


@pytest.mark.parametrize("seleccion,modo", [("1", "demo"), ("demo", "demo"), ("2", "real"), ("real", "real")])
def test_menu_selects_same_factory_once(monkeypatch, seleccion, modo, capsys):
    from agentes import runtime

    entradas = iter(["", "inválido", seleccion])
    monkeypatch.setattr("builtins.input", lambda _: next(entradas))
    llamadas = []
    servicio = object()

    def crear(*, modo):
        llamadas.append(modo)
        return servicio

    def ejecutar(recibido, **kwargs):
        assert recibido is servicio
        assert kwargs == {"mensaje": "Consulta", "debug": True}
        return 0

    monkeypatch.setattr(runtime, "crear_servicio", crear)
    monkeypatch.setattr(cli, "ejecutar_interactivo", ejecutar)
    assert cli.main(["--menu", "--mensaje", "Consulta", "--debug"]) == 0
    assert llamadas == [modo]
    assert "no hay selección por defecto" in capsys.readouterr().out


@pytest.mark.parametrize("fin", ["0", EOFError, KeyboardInterrupt])
def test_menu_exit_never_creates_service(monkeypatch, fin):
    from agentes import runtime

    def leer(_):
        if isinstance(fin, str):
            return fin
        raise fin()

    monkeypatch.setattr("builtins.input", leer)
    monkeypatch.setattr(runtime, "crear_servicio", lambda **_: pytest.fail("No crear servicio"))
    assert cli.main(["--menu"]) == 0


@pytest.mark.parametrize("args", [["--modo", "otro"], ["--menu", "--modo", "demo"]])
def test_invalid_selection_never_creates_service(monkeypatch, args):
    from agentes import runtime
    monkeypatch.setattr(runtime, "crear_servicio", lambda **_: pytest.fail("No crear servicio"))
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2


@pytest.mark.parametrize("fin", [EOFError, KeyboardInterrupt, RuntimeError])
def test_conversation_start_failure_is_handled(sesion, monkeypatch, fin):
    servicio, eventos = sesion

    def fallar():
        raise fin("Inicio interrumpido")

    monkeypatch.setattr(servicio, "nueva_conversacion", fallar)
    codigo, salida = conversar(servicio, [])
    assert codigo == (1 if fin is RuntimeError else 0)
    assert not eventos["pedidos"] and not eventos["decisiones"]
    if fin is RuntimeError:
        assert "Error al iniciar" in salida


def test_sensitive_service_output_is_redacted(sesion, monkeypatch):
    servicio, eventos = sesion
    estado = servicio.procesar_turno("Consulta", servicio.nueva_conversacion())
    secreto = "MARCADOR_PRIVADO_PRUEBA"
    estado["debug_trace"] = [f"GOOGLE_API_KEY={secreto}", f"Authorization: Bearer {secreto}"]
    estado["final_answer"] = f"Error del proveedor: api_key={secreto}"
    estado["specialist_results"]["documental"].error = f"https://user:{secreto}@example.test"
    salida = []
    cli.mostrar_estado(estado, debug=True, escribir=salida.append)
    assert secreto not in "\n".join(salida)
    assert "[OCULTO]" in "\n".join(salida)

    def fallar(mensaje, hilo):
        raise RuntimeError(f"access_token={secreto}")

    monkeypatch.setattr(servicio, "procesar_turno", fallar)
    _, texto = conversar(servicio, ["Fallo", "/salir"])
    assert secreto not in texto and "[OCULTO]" in texto


def test_state_read_error_preserves_current_plan(sesion, monkeypatch):
    servicio, eventos = sesion
    consultar = servicio.consultar_estado
    lecturas = []

    def leer(hilo):
        lecturas.append(hilo)
        if len(lecturas) == 2:
            raise RuntimeError("Lectura fallida")
        return consultar(hilo)

    monkeypatch.setattr(servicio, "consultar_estado", leer)
    codigo, salida = conversar(servicio, ["Consulta", "/estado", "/aprobar", "/estado", "/rechazar", "/salir"])
    assert codigo == 0 and "Lectura fallida" in salida
    assert len(set(lecturas)) == 1
    assert [d[1] for d in eventos["decisiones"]] == [False]
    assert eventos["decisiones"][0][2] == eventos["pedidos"][0][2]["plan_id"]


@pytest.mark.parametrize("fin", [EOFError, KeyboardInterrupt])
def test_factory_interrupt_exits_cleanly(monkeypatch, fin):
    from agentes import runtime

    def interrumpir(**kwargs):
        raise fin()

    monkeypatch.setattr(runtime, "crear_servicio", interrumpir)
    assert cli.main(["--modo", "real"]) == 0


def test_initial_state_error_returns_failure(sesion, monkeypatch):
    servicio, eventos = sesion

    def fallar(hilo):
        raise RuntimeError("No se pudo leer la conversación inicial")

    monkeypatch.setattr(servicio, "consultar_estado", fallar)
    codigo, salida = conversar(servicio, [])
    assert codigo == 1 and "Error al iniciar conversación" in salida
    assert not eventos["pedidos"] and not eventos["decisiones"]


@pytest.mark.parametrize("entrada,aprobado", [("aprobar", True), ("rechazar", False), (" APROBAR ", True)])
def test_plain_decision_uses_pending_identifiers(sesion, entrada, aprobado):
    servicio, eventos = sesion
    codigo, salida = conversar(servicio, ["Consulta", entrada, "salir"])
    assert codigo == 0
    assert [p[0] for p in eventos["pedidos"]] == ["Consulta"]
    assert len(eventos["decisiones"]) == 1
    decision = eventos["decisiones"][0]
    pedido = eventos["pedidos"][0]
    assert decision[:3] == (pedido[1], aprobado, pedido[2]["plan_id"])


def test_plain_decision_without_plan_never_becomes_query(sesion):
    servicio, eventos = sesion
    _, salida = conversar(servicio, ["aprobar", "rechazar", "salir"])
    assert not eventos["pedidos"] and not eventos["decisiones"]
    assert "No hay un plan pendiente" in salida


def test_plain_exit_keeps_pending_plan_unresolved(sesion):
    servicio, eventos = sesion
    codigo, salida = conversar(servicio, ["Consulta", "salir"])
    assert codigo == 0 and not eventos["decisiones"]
    assert servicio.consultar_estado(eventos["pedidos"][0][1])["pendiente_hitl"]


def test_command_word_in_initial_message_is_literal(sesion):
    servicio, eventos = sesion
    conversar(servicio, ["rechazar", "salir"], mensaje="aprobar")
    assert [p[0] for p in eventos["pedidos"]] == ["aprobar"]
    assert [d[1] for d in eventos["decisiones"]] == [False]


def test_demo_plain_commands_with_strict_checkpoint():
    resultado = subprocess.run(
        [sys.executable, "-B", "main.py", "--modo", "demo", "--mensaje", "Consulta simulada"],
        input="aprobar\nOtra consulta\nrechazar\nsalir\n", cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1", "MAX_ITER": "8", "LANGGRAPH_STRICT_MSGPACK": "true"},
        capture_output=True, encoding="utf-8", timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "Borrador aprobado" in resultado.stdout
    assert "Borrador rechazado" in resultado.stdout
    assert "Salida sin decisiones automáticas" in resultado.stdout
    assert "Deserializing unregistered type" not in resultado.stderr
    assert "Blocked deserialization" not in resultado.stderr


def test_all_plain_commands_and_new_alias_keep_session(sesion, monkeypatch):
    servicio, eventos = sesion
    crear = servicio.nueva_conversacion
    hilos = []

    def nueva():
        hilo = crear()
        hilos.append(hilo)
        return hilo

    monkeypatch.setattr(servicio, "nueva_conversacion", nueva)
    codigo, salida = conversar(servicio, [
        "ayuda", "estado", "debug", "nueva", "nuevo", "/nuevo",
        "Consulta", "ayuda", "estado", "debug", "nueva", "nuevo", "rechazar", "salir",
    ])
    assert codigo == 0 and len(hilos) == 4
    assert [p[0] for p in eventos["pedidos"]] == ["Consulta"]
    assert eventos["pedidos"][0][1] == hilos[-1]
    assert [d[1] for d in eventos["decisiones"]] == [False]
    assert "Debug:" in salida and "antes de /nueva" in salida


@pytest.mark.parametrize("errata", ["saalir", "nuevaa", "aprovar", "rechazarr"])
def test_command_typos_never_query_or_decide(sesion, errata):
    servicio, eventos = sesion
    codigo, salida = conversar(servicio, [errata, "Consulta", errata, "salir"])
    assert codigo == 0
    assert [p[0] for p in eventos["pedidos"]] == ["Consulta"]
    assert not eventos["decisiones"]
    assert salida.count("¿Querías escribir") == 2
    assert servicio.consultar_estado(eventos["pedidos"][0][1])["pendiente_hitl"]


def test_full_queries_containing_commands_remain_queries(sesion):
    servicio, eventos = sesion
    consulta = "Necesito ayuda para una nueva reserva"
    conversar(servicio, [consulta, "rechazar", "salir"])
    assert [p[0] for p in eventos["pedidos"]] == [consulta]
