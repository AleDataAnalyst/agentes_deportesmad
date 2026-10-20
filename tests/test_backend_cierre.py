"""Cierre del backend: checkpoint inyectado y FINISH temprano sin servicios.

Supervisor, router, grafo, servicio, síntesis y aplicar son los actuales.
El proveedor de rutas es un doble explícito; los especialistas no deben llamarse.
No se importa el documental ni se ejecutan herramientas, RAG o HTTP.
"""

from copy import deepcopy

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agentes.agent import AgentService
from agentes.contracts import SupervisorDecision
from agentes.nodes.aplicar import aplicar
from agentes.nodes.sintetizar import sintetizar
from agentes.settings import AgentSettings


@pytest.mark.parametrize("aprobado", [True, False])
def test_injected_checkpoint_keeps_early_finish_pause_and_same_thread_resume(aprobado):
    checkpointer = MemorySaver()
    decisiones = []
    aplicaciones = []

    def especialista_no_esperado(state):
        pytest.fail("FINISH temprano no debe inventar una consulta de especialista")

    def proveedor_doble(state):
        decisiones.append(state["iterations"])
        return SupervisorDecision("FINISH", "Propuesta temprana del doble de prueba")

    def aplicar_contado(state):
        aplicaciones.append(state["approved"])
        return aplicar(state)

    servicio = AgentService(
        documental_node=especialista_no_esperado,
        instalaciones_node=especialista_no_esperado,
        sintetizar_node=sintetizar,
        aplicar_node=aplicar_contado,
        route_provider=proveedor_doble,
        settings=AgentSettings(max_iter=8),
        checkpointer=checkpointer,
    )
    hilo = servicio.nueva_conversacion()
    otro_hilo = servicio.nueva_conversacion()
    config = {"configurable": {"thread_id": hilo}}
    config_otro = {"configurable": {"thread_id": otro_hilo}}

    pendiente = servicio.procesar_turno("[SIMULADO] FINISH antes de tener plan", hilo)
    checkpoint_pendiente = checkpointer.get_tuple(config)
    assert checkpoint_pendiente is not None  # Se usa la instancia inyectada.
    assert checkpointer.get_tuple(config_otro) is None
    assert checkpoint_pendiente.config["configurable"]["thread_id"] == hilo
    assert checkpoint_pendiente.checkpoint["channel_values"]["plan"] == pendiente["plan"]
    assert checkpoint_pendiente.checkpoint["channel_values"]["approved"] is None
    assert pendiente["specialist_results"] == {}
    assert "No hay resultados útiles" in pendiente["final_answer"]
    assert pendiente["plan"] and pendiente["plan_id"]
    assert pendiente["pendiente_hitl"] is True
    assert pendiente["approved"] is None and pendiente["done"] is False
    assert aplicaciones == []  # FINISH no salta la pausa antes de aplicar.
    assert decisiones == [0, 1]  # El proveedor no está alcanzando MAX_ITER.
    assert pendiente["debug_trace"] == [
        "inicio de pedido",
        "iter 1: supervisor -> FINISH; origen=proveedor",
        "síntesis: 0 de 2 resultados útiles",
        "iter 2: supervisor -> FINISH; origen=proveedor",
    ]
    traza_pendiente = deepcopy(pendiente["debug_trace"])

    final = servicio.resolver_plan(hilo, aprobado, plan_id=pendiente["plan_id"])
    checkpoint_final = checkpointer.get_tuple(config)
    assert checkpoint_final.config["configurable"]["thread_id"] == hilo
    assert checkpoint_final.config != checkpoint_pendiente.config
    assert checkpoint_final.checkpoint["channel_values"]["approved"] is aprobado
    assert checkpoint_final.checkpoint["channel_values"]["done"] is aprobado
    assert final["thread_id"] == hilo and final["plan_id"] == pendiente["plan_id"]
    assert final["pendiente_hitl"] is False and final["done"] is aprobado
    assert aplicaciones == [aprobado]
    evento = "HITL -> plan " + ("aprobado" if aprobado else "rechazado")
    assert final["debug_trace"] == traza_pendiente + [evento]
    assert servicio.resolver_plan(hilo, aprobado, plan_id=pendiente["plan_id"]) == final
    assert aplicaciones == [aprobado]
    assert servicio.consultar_estado(otro_hilo)["specialist_results"] == {}
    assert checkpointer.get_tuple(config_otro) is None

    siguiente = servicio.procesar_turno("[SIMULADO] Pedido posterior al cierre", hilo)
    assert siguiente["pendiente_hitl"] is True
    assert siguiente["approved"] is None and siguiente["done"] is False
    assert siguiente["plan_id"] != pendiente["plan_id"]
    assert siguiente["debug_trace"] == final["debug_trace"] + traza_pendiente
    with pytest.raises(ValueError, match="PLAN_NOT_CURRENT"):
        servicio.resolver_plan(hilo, aprobado, plan_id=pendiente["plan_id"])
