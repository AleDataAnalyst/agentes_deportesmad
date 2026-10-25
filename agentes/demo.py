"""Dobles explícitos y ejecutor de demo; sin LLM, red ni información real.

Ejecutar desde la raíz: python -m agentes.demo. Esta consola muestra un pedido
simulado; no sustituye la CLI final del PB02. Para clientes, conservar la instancia
devuelta por crear_servicio_demo y utilizar la API de AgentService.
"""

import argparse
from dataclasses import asdict, is_dataclass
from functools import partial
import json
from typing import Any, get_args

from agentes.agent import AgentService
from agentes.contracts import Evidence, SPECIALIST_NAMES, ToolResult, ToolStatus
from agentes.settings import AgentSettings
from agentes.state import AgentState

DEMO_MESSAGE = "Pedido simulado para comprobar especialistas, plan y aprobación humana."
DEMO_NOTICE = "DEMO SIMULADA: sin RAG, catálogo, herramientas ni información municipal reales."


def _especialista_demo(state: AgentState, *, role: str, scenario: ToolStatus) -> dict:
    if scenario == "ok":
        result = ToolResult(
            status="ok",
            answer=f"[SIMULADO] Resultado de {role} para comprobar la integración.",
            evidence=[Evidence(
                source=f"demo://{role}",
                content="[SIMULADO] Fragmento ficticio de prueba; no es una fuente municipal.",
                metadata={"simulated": True},
            )],
            data={"simulated": True, "scenario": scenario},
        )
    elif scenario == "abstained":
        result = ToolResult(
            status="abstained", answer=f"[SIMULADO] {role} se abstiene por falta de evidencia.",
            data={"simulated": True, "scenario": scenario},
        )
    else:
        result = ToolResult(
            status="error", answer=f"[SIMULADO] Fallo técnico de {role}; no hay respuesta real.",
            error="DEMO_ERROR: fallo simulado, sin llamada a servicios externos",
            data={"simulated": True, "scenario": scenario},
        )
    return {
        "specialist_results": {**state.get("specialist_results", {}), role: result},
        "debug_trace": [f"[SIMULADO] {role}: {scenario}"],
    }


def _sintetizar_demo(state: AgentState) -> dict:
    results = state.get("specialist_results", {})
    lines = [DEMO_NOTICE]
    for role in SPECIALIST_NAMES:
        result = results.get(role)
        lines.append(f"{role}: {result.answer}" if result is not None
                     else f"{role}: no ejecutado; sin resultado disponible en este recorrido.")
    plan = [
        "[SIMULADO] Revisar los resultados de prueba y sus estados, sin tomar decisiones municipales.",
        "[SIMULADO] Aprobar o rechazar este borrador para comprobar la pausa humana.",
    ]
    return {
        "final_answer": "\n".join(lines), "plan": plan,
        "debug_trace": ["[SIMULADO] síntesis: borrador de prueba listo"],
    }


def _aplicar_demo(state: AgentState) -> dict:
    if state["approved"]:
        return {"done": True,
                "final_answer": state["final_answer"] + "\n[SIMULADO] Borrador aprobado; ninguna acción externa ejecutada."}
    return {"done": False, "plan": [], "specialist_results": {}, "pending_action": None,
            "final_answer": DEMO_NOTICE + "\n[SIMULADO] Borrador rechazado. Puedes enviar otro pedido."}


def crear_servicio_demo(
    *, scenario: ToolStatus = "ok", settings: AgentSettings | None = None,
) -> AgentService:
    """Construye el servicio simulado que CLI/Streamlit pueden reutilizar.

    No hay sustitución automática por esta demo cuando falla un módulo real.
    Si no se inyecta settings, el servicio lee MAX_ITER del entorno.
    """
    if scenario not in get_args(ToolStatus):
        raise ValueError("scenario debe ser ok, abstained o error")
    return AgentService(
        documental_node=partial(_especialista_demo, role="documental", scenario=scenario),
        instalaciones_node=partial(_especialista_demo, role="instalaciones", scenario=scenario),
        sintetizar_node=_sintetizar_demo, aplicar_node=_aplicar_demo, settings=settings,
    )


def run_demo(
    mensaje: str = DEMO_MESSAGE, *, aprobado: bool | None = None,
    scenario: ToolStatus = "ok", settings: AgentSettings | None = None,
) -> dict[str, Any]:
    """Devuelve evidencia de simulación: pausa y resolución opcional explícita."""
    if aprobado is not None and type(aprobado) is not bool:
        raise TypeError("aprobado debe ser True, False o None")
    service = crear_servicio_demo(scenario=scenario, settings=settings)
    thread_id = service.nueva_conversacion()
    pending = service.procesar_turno(mensaje, thread_id)
    final = None
    if aprobado is not None:
        final = service.resolver_plan(thread_id, aprobado, plan_id=pending["plan_id"])
    return {"mode": "demo", "notice": DEMO_NOTICE, "scenario": scenario,
            "pending_state": pending, "final_state": final}


def _json_default(value):
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Tipo no serializable en la demo: {type(value).__name__}")


def _mostrar(report: dict[str, Any]) -> None:
    # ASCII escapado mantiene la salida legible también en consolas Windows.
    print(json.dumps(report, ensure_ascii=True, indent=2, default=_json_default))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=DEMO_NOTICE)
    parser.add_argument("--mensaje", default=DEMO_MESSAGE)
    parser.add_argument("--escenario", choices=get_args(ToolStatus), default="ok")
    parser.add_argument("--decision", choices=("pausa", "aprobar", "rechazar"), default="pausa")
    parser.add_argument("--interactivo", action="store_true", help="Pide una decisión humana para un pedido simulado")
    parser.add_argument("--max-iter", type=int, default=None)
    args = parser.parse_args(argv)
    if args.interactivo and args.decision != "pausa":
        parser.error("--interactivo requiere --decision pausa (o no indicar --decision)")
    try:
        settings = AgentSettings(max_iter=args.max_iter) if args.max_iter is not None else None
        if not args.interactivo:
            decision = {"pausa": None, "aprobar": True, "rechazar": False}[args.decision]
            _mostrar(run_demo(args.mensaje, aprobado=decision, scenario=args.escenario, settings=settings))
            return 0
        service = crear_servicio_demo(scenario=args.escenario, settings=settings)
        thread_id = service.nueva_conversacion()
        pending = service.procesar_turno(args.mensaje, thread_id)
        report = {"mode": "demo", "notice": DEMO_NOTICE, "scenario": args.escenario,
                  "pending_state": pending, "final_state": None}
        _mostrar(report)
        while True:
            try:
                choice = input("Decisión para la DEMO: aprobar / rechazar / salir: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nDEMO: salida sin aprobar; el checkpoint se pierde al finalizar el proceso.")
                return 0
            if choice == "salir":
                print("DEMO: salida sin aprobar; el checkpoint se pierde al finalizar el proceso.")
                return 0
            if choice in ("aprobar", "rechazar"):
                report["final_state"] = service.resolver_plan(
                    thread_id, choice == "aprobar", plan_id=pending["plan_id"])
                _mostrar(report)
                return 0
            print("Escribe aprobar, rechazar o salir.")
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
