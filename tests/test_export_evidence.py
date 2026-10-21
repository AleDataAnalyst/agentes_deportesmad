"""Evidencia de integración con estímulos simulados, nunca RAG real."""

import json

from scripts.export_evidence import main
from tests.test_import_boundaries import run_python


def test_export_all_scenarios_with_real_synthesis_and_apply(tmp_path, capsys):
    target = tmp_path / "evidence.json"
    assert main(["--output", str(target)]) == 0
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["mode"] == "simulated"
    assert report["rag_validated"] is False and report["http_validated"] is False
    assert report["clients_validated"] is False
    assert len(report["cases"]) == 10
    assert "SIMULADA" in capsys.readouterr().out
    for case in report["cases"]:
        assert all(case["checks"].values())
        pending = case["pending_state"]
        assert pending["specialist_results"]["documental"]["data"]["simulated"] is True
        assert "[SIMULADO]" in pending["user_message"]
        answer = pending["final_answer"]
        if case["scenario"] == "historical":
            assert "Fallback histórico" in answer and "2026-10-13" in answer
        elif case["scenario"] == "partial":
            assert "Respuesta parcial" in answer and "Fallo de instalaciones" in answer
        elif case["scenario"] in ("error", "abstained"):
            assert "No hay resultados útiles" in answer
        else:
            assert "ambos especialistas" in answer


def test_single_scenario_stdout_is_valid_json(capsys):
    assert main(["--scenario", "partial"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["cases"]) == 2
    assert [case["simulated_approval"] for case in report["cases"]] == [True, False]


def test_export_runs_without_loading_documental_or_rag():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder
        class Block(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname in ("rag", "agentes.nodes.documental", "agentes.tools.rag",
                                "agentes.grafo_documental") or fullname.startswith("rag."):
                    raise AssertionError(fullname)
        sys.meta_path.insert(0, Block())
        from scripts.export_evidence import exportar_recorrido
        report = exportar_recorrido("partial", False)
        assert all(report["checks"].values())
    ''')
