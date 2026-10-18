"""Prueba acotada explícita, sin dobles ni ingesta: python -m scripts.smoke_real.

Usa exclusivamente una consulta sintética identificada, hasta cuatro llamadas
documentales (aislado, aprobación, rechazo y siguiente pedido). No se ejecuta
al recoger pytest. El perfil observa llamadas originales, sin sustituirlas.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from agentes.runtime import crear_servicio_real

QUERY = "¿Qué documentación se necesita para un abono deportivo municipal?"
WATCH = {
    ("agentes.tools.rag", "rag_preguntar"),
    ("rag.logic", "responder"),
    ("rag.retrieve", "recuperar_hibrido"),
    ("rag.retrieve", "recuperar"),
    ("rag.retrieve", "obtener_coleccion"),
    ("rag.embed", "embeddear_consulta"),
    ("rag.generate", "generar"),
}


def comprobar():
    from agentes.grafo_documental import obtener_grafo_documental
    from rag import config

    calls = Counter()

    def observe(frame, event, arg):
        key = (frame.f_globals.get("__name__"), frame.f_code.co_name)
        if event == "call" and key in WATCH:
            calls[".".join(key)] += 1

    report = {
        "mode": "real", "query_kind": "ejemplo sintético público de prueba",
        "embed_provider": config.EMBED_PROVIDER, "gen_provider": config.GEN_PROVIDER,
        "index_file_present": (Path(config.CHROMA_DIR) / "chroma.sqlite3").is_file(),
        "env_presence": {key: bool(getattr(config, key)) for key in ("GOOGLE_API_KEY", "HF_TOKEN")},
        "http_instalaciones": "no ejecutado: sin operación pública integrada",
    }
    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        isolated = obtener_grafo_documental().invoke({
            "request_id": "smoke-aislado", "pedido": QUERY, "presupuesto_tools": 1,
        })["documental"]
        report["isolated"] = {
            key: isolated[key] for key in ("abstained", "errores", "fuentes")}
        service = crear_servicio_real()
        tid = service.nueva_conversacion()
        other = service.nueva_conversacion()
        summaries = []
        old_plan = None
        for decision in (True, False):
            pending = service.procesar_turno(QUERY, tid)
            result = pending["specialist_results"]["documental"]
            assert result.answer == result.data["resultado"]
            assert [e.source for e in result.evidence] == result.data["fuentes"]
            assert result.data["request_id"]
            assert pending["pendiente_hitl"] and pending["approved"] is None
            assert not pending["done"]
            if old_plan:
                try:
                    service.resolver_plan(tid, True, plan_id=old_plan)
                except ValueError as exc:
                    assert "PLAN_NOT_CURRENT" in str(exc)
                else:
                    raise AssertionError("Se aceptó un plan antiguo")
            before_calls = dict(calls)
            final = service.resolver_plan(tid, decision, plan_id=pending["plan_id"])
            assert not final["pendiente_hitl"] and final["done"] is decision
            assert service.resolver_plan(tid, decision, plan_id=pending["plan_id"]) == final
            assert dict(calls) == before_calls
            assert sum(line.startswith("HITL ->") for line in final["debug_trace"]) == len(summaries) + 1
            summaries.append({"status": result.status, "fuentes": result.data["fuentes"],
                              "errores": result.data["errores"], "approved": decision,
                              "rag_events": len(result.data["eventos"])})
            old_plan = pending["plan_id"]
        # Pedido posterior al rechazo; queda pendiente, sin autoaprobarlo.
        last = service.procesar_turno(QUERY, tid)
        assert last["pendiente_hitl"] and last["plan_id"] != old_plan
        assert service.consultar_estado(other)["specialist_results"] == {}
        report["integrated"] = summaries
        report["hitl_lifecycle_ok"] = True
        report["retrieval_generation_success"] = (
            not isolated["errores"] and not isolated["abstained"]
            and all(s["status"] == "ok" for s in summaries)
        )
    finally:
        sys.setprofile(previous)
        report["original_calls"] = dict(calls)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Guardar informe sin claves ni rutas personales")
    args = parser.parse_args(argv)
    report = comprobar()
    text = json.dumps(report, ensure_ascii=True, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    # Distingue recorrido ejecutado de una respuesta con recuperación correcta.
    return 0 if report["retrieval_generation_success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
