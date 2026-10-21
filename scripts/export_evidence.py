"""Exportación de evidencia de recorridos autorizados.

Registrar modo real/simulado, versión, escenario, trazas y resultado verificable.
Usar datos de demostración; no volcar conversaciones o datos personales por defecto.
No completar informes con resultados de pruebas que no se han ejecutado.
"""

import argparse
from dataclasses import asdict
from functools import partial
import json
from pathlib import Path

from agentes.agent import AgentService
from agentes.contracts import Evidence, ToolResult
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.aplicar import aplicar
from agentes.nodes.sintetizar import sintetizar
from agentes.settings import AgentSettings

SCENARIOS = ("ok", "partial", "abstained", "error", "historical")
NOTICE = ("EVIDENCIA SIMULADA: síntesis/aplicar reales, especialistas y decisiones "
          "simulados. No valida RAG, HTTP ni clientes.")


def _documental_doble(request, *, scenario):
    """Emite el contrato documental sin importar el nodo ni ejecutar tools."""
    failed = scenario == "error"
    abstained = scenario == "abstained"
    return {"documental": {
        "request_id": request["request_id"],
        "resultado": "[SIMULADO] Evidencia documental de prueba." if not failed and not abstained else "",
        "fuentes": ["demo://documental"] if not failed and not abstained else [],
        "abstained": abstained,
        "errores": ["[SIMULADO] Fallo documental"] if failed else [],
        "limitaciones": ["[SIMULADO] No se ha consultado un corpus real"],
        "eventos": [], "simulated": True,
    }}


def _instalaciones_doble(state, *, scenario):
    """Emite el contrato común, incluyendo una captura histórica ficticia."""
    status = "error" if scenario in ("partial", "error") else "abstained" if scenario == "abstained" else "ok"
    historical = scenario == "historical"
    result = ToolResult(
        status=status,
        answer="[SIMULADO] Datos de instalaciones para revisión." if status == "ok" else "",
        error="[SIMULADO] Fallo de instalaciones" if status == "error" else None,
        evidence=[Evidence("demo://instalaciones", "")] if status == "ok" else [],
        data={"simulated": True, "warnings": ["[SIMULADO] No acredita plazas ni disponibilidad"],
              **({"origen": "fallback", "fecha_captura_fallback": "2026-10-13"} if historical else {})},
    )
    return {"specialist_results": {**state.get("specialist_results", {}), "instalaciones": result},
            "debug_trace": [f"[SIMULADO] instalaciones: {status}"]}


def exportar_recorrido(scenario: str, aprobado: bool) -> dict:
    """Ejecuta un caso reproducible en memoria y comprueba su ciclo de vida.

    La decisión es un estímulo de prueba, no una aprobación humana del producto.
    Solo se usan textos y fuentes ficticios; nunca recibe conversaciones reales.
    La evidencia describe comprobaciones observadas, no calidad de especialistas.
    """
    if scenario not in SCENARIOS or type(aprobado) is not bool:
        raise ValueError("Se requiere escenario conocido y decisión booleana")
    service = AgentService(
        documental_node=crear_adaptador_documental(
            ejecutar_documental=partial(_documental_doble, scenario=scenario)),
        instalaciones_node=partial(_instalaciones_doble, scenario=scenario),
        sintetizar_node=sintetizar, aplicar_node=aplicar,
        settings=AgentSettings(),
    )
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("[SIMULADO] Revisar información deportiva de prueba.", tid)
    final = service.resolver_plan(tid, aprobado, plan_id=pending["plan_id"])
    repeated = service.resolver_plan(tid, aprobado, plan_id=pending["plan_id"])
    checks = {
        "pause_before_apply": pending["pendiente_hitl"] and pending["approved"] is None and pending["done"] is False,
        "same_thread": pending["thread_id"] == final["thread_id"],
        "same_plan": pending["plan_id"] == final["plan_id"],
        "resolved": not final["pendiente_hitl"] and final["done"] is aprobado,
        "idempotent": final == repeated,
        "single_hitl_event": sum(event.startswith("HITL ->") for event in final["debug_trace"]) == 1,
        "rejection_clears_proposal": aprobado or (
            final["plan"] == [] and final["specialist_results"] == {} and final["pending_action"] is None),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Fallo del recorrido simulado: {checks}")
    return {"scenario": scenario, "simulated_approval": aprobado, "checks": checks,
            "pending_state": pending, "final_state": final}


def main(argv=None) -> int:
    """Exporta JSON a stdout o a la ruta explícita, sin instalar ni indexar."""
    parser = argparse.ArgumentParser(description=NOTICE)
    parser.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="all")
    parser.add_argument("--output", type=Path, help="Ruta del JSON con datos exclusivamente simulados")
    args = parser.parse_args(argv)
    scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
    report = {"notice": NOTICE, "mode": "simulated", "rag_validated": False,
              "http_validated": False, "clients_validated": False,
              "cases": [exportar_recorrido(scenario, decision)
                        for scenario in scenarios for decision in (True, False)]}
    output = json.dumps(report, ensure_ascii=True, indent=2, default=asdict) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"{NOTICE}\n{len(report['cases'])} casos guardados en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
