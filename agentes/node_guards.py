"""Frontera de escritura de nodos síncronos, independiente de tools y clientes.

Se aíslan entradas y salidas en memoria. Esto valida el contrato de un callable;
no constituye un sandbox ni revierte efectos externos de código Python.
"""
from collections.abc import Callable
from copy import deepcopy

from agentes.contracts import Evidence, PendingAction, SPECIALIST_NAMES, ToolResult
from agentes.state import AgentState


def ejecutar_aislado(state: AgentState, node: Callable, *, campos: frozenset[str], codigo: str) -> dict:
    """Valida el patch antes de que LangGraph lo fusione y elimina alias mutables."""
    update = node(deepcopy(state))
    if not isinstance(update, dict) or not set(update).issubset(campos):
        raise ValueError(f"{codigo}: actualización con campos no permitidos o formato inválido")
    if "debug_trace" in update and (
        not isinstance(update["debug_trace"], list)
        or not all(isinstance(evento, str) for evento in update["debug_trace"])
    ):
        raise ValueError(f"{codigo}: debug_trace debe contener solo eventos de texto")
    if ("pending_action" in update and update["pending_action"] is not None
            and not isinstance(update["pending_action"], PendingAction)):
        raise ValueError(f"{codigo}: pending_action incompatible")
    return deepcopy(update)


def _validar_resultado(result: ToolResult) -> None:
    if (not isinstance(result, ToolResult) or result.status not in ("ok", "abstained", "error")
            or not isinstance(result.answer, str) or not isinstance(result.data, dict)
            or (result.error is not None and not isinstance(result.error, str))
            or not isinstance(result.evidence, list)):
        raise ValueError("SPECIALIST_CONTRACT: resultado incompatible")
    for evidence in result.evidence:
        if (not isinstance(evidence, Evidence) or not isinstance(evidence.source, str)
                or not isinstance(evidence.content, str) or not isinstance(evidence.metadata, dict)):
            raise ValueError("SPECIALIST_CONTRACT: evidencia incompatible")


def especialista_protegido(state: AgentState, *, rol: str, node: Callable) -> dict:
    """Solo el resultado del rol y sus eventos; otros roles no pueden alterarse.

    Acepta mapas completos existentes o un patch con solo el rol propio. Las
    entradas omitidas se conservan; un mapa vacío no borra resultados anteriores.
    Se mantiene la compatibilidad con nodos que devuelven un patch vacío.
    """
    if rol not in SPECIALIST_NAMES:
        raise ValueError("SPECIALIST_CONTRACT: rol no permitido")
    update = ejecutar_aislado(state, node, campos=frozenset({"specialist_results", "debug_trace"}),
                              codigo="SPECIALIST_CONTRACT")
    if "specialist_results" not in update:
        return update
    results = update["specialist_results"]
    if not isinstance(results, dict) or not set(results).issubset(SPECIALIST_NAMES):
        raise ValueError("SPECIALIST_CONTRACT: mapa de resultados incompatible")
    previous = state.get("specialist_results", {})
    for other, result in results.items():
        if other != rol and (other not in previous or result != previous[other]):
            raise ValueError("SPECIALIST_CONTRACT: no se permite modificar otro rol")
        _validar_resultado(result)
    update["specialist_results"] = {**deepcopy(previous), **results}
    return update
