"""Conexión del reloj a instalaciones por reglas, sin servicios reales."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from agentes.contracts import ToolResult
from agentes.nodes import instalaciones


@pytest.fixture
def municipal(monkeypatch):
    consulta = Mock(return_value={
        "ok": True, "modo": "catalogo",
        "datos": [{"pk": "101", "nombre": "Centro A", "distrito": "RETIRO",
                   "content_url": "test://centro"}],
        "fuente": "test://catalogo", "origen": "api",
        "fecha_consulta": "2026-10-27T11:00:00+01:00",
        "fecha_captura_fallback": None, "advertencias": [], "error": None,
    })
    monkeypatch.setattr(instalaciones, "consultar_instalaciones", consulta)
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", lambda texto: [])
    return consulta


@pytest.fixture
def reloj(monkeypatch):
    consulta = Mock(return_value={
        "ok": True,
        "resultado": {"iso": "2026-10-27T11:30:00+01:00", "fecha": "2026-10-27",
                      "hora": "11:30", "dia_semana": "martes", "zona": "Europe/Madrid"},
        "fuentes": ["reloj_del_sistema"], "abstained": False, "error": None,
    })
    monkeypatch.setattr(instalaciones, "hora_actual", consulta)
    return consulta


@pytest.mark.parametrize("mensaje", [
    "¿Qué centros hay hoy?", "¿Hay centros abiertos AHORA?",
    "Dime la hora actual", "Necesito la fecha actual", "Día actual",
    "¿Qué hora es?", "¿Qué fecha es?", "¿QUÉ DÍA ES?",
])
def test_peticion_temporal_guarda_contrato_y_procedencia(municipal, reloj, mensaje):
    update = instalaciones.nodo_instalaciones({"user_message": mensaje})
    reloj.assert_called_once_with(zona="Europe/Madrid")
    municipal.assert_called_once_with(modo="catalogo", centro_id=None)
    result = update["specialist_results"]["instalaciones"]
    assert result.data["hora_actual"] == reloj.return_value
    assert result.status == "ok" and result.error is None
    assert result.data["fuente"] == "test://catalogo"
    assert result.evidence[0].source == "test://centro"
    assert "abierto" not in result.answer.casefold()
    assert update["debug_trace"][-1] == (
        "instalaciones.tool: hora_actual zona=Europe/Madrid status=ok"
    )
    reloj.return_value["resultado"]["hora"] = "00:00"
    assert result.data["hora_actual"]["resultado"]["hora"] == "11:30"


@pytest.mark.parametrize("mensaje", [
    "Lista de centros", "Horarios del centro", "¿Está abierto el centro?",
    "Natación por la mañana", "¿Qué centros hay mañana?", "Actualiza el catálogo",
    "El centro Ahorama", "",  # No coincidencias parciales ni consultas vacías.
])
def test_peticion_no_temporal_no_consulta_reloj(municipal, reloj, mensaje):
    update = instalaciones.nodo_instalaciones({"user_message": mensaje})
    reloj.assert_not_called()
    assert "hora_actual" not in update["specialist_results"]["instalaciones"].data
    assert len(update["debug_trace"]) == 1


@pytest.mark.parametrize("excepcion", [False, True])
def test_fallo_reloj_no_invalida_consulta_municipal(municipal, reloj, excepcion):
    base = instalaciones.nodo_instalaciones({"user_message": "Lista de centros"})
    esperado = base["specialist_results"]["instalaciones"]
    if excepcion:
        reloj.side_effect = RuntimeError("detalle interno que no debe mostrarse")
    else:
        reloj.return_value = {
            "ok": False, "resultado": None, "fuentes": [],
            "abstained": False, "error": "Reloj no disponible",
        }
    update = instalaciones.nodo_instalaciones({"user_message": "Lista de centros hoy"})
    reloj.assert_called_once_with(zona="Europe/Madrid")
    result = update["specialist_results"]["instalaciones"]
    assert (result.status, result.error, result.answer, result.evidence) == (
        esperado.status, esperado.error, esperado.answer, esperado.evidence,
    )
    assert result.data["hora_actual"]["resultado"] is None
    assert result.data["hora_actual"]["fuentes"] == []
    assert any("Hora actual no disponible" in aviso for aviso in result.data["advertencias"])
    assert update["debug_trace"][-1].endswith("status=error")
    assert "detalle interno" not in str(update)


def test_conserva_resultados_anteriores_y_solo_emite_traza_nueva(municipal, reloj):
    previo = ToolResult(status="ok", answer="Normativa", evidence=[], data={"fuentes": ["test://norma"]})
    state = {
        "user_message": "Lista de centros ahora",
        "specialist_results": {"documental": previo},
        "debug_trace": ["supervisor: instalaciones"],
    }
    original = deepcopy(state)
    update = instalaciones.nodo_instalaciones(state)
    assert state == original
    assert update["specialist_results"]["documental"] is previo
    assert "instalaciones" in update["specialist_results"]
    assert len(update["debug_trace"]) == 2
    assert "supervisor: instalaciones" not in update["debug_trace"]
    assert set(update) == {"specialist_results", "debug_trace"}


def test_reloj_exitoso_no_convierte_fallo_municipal_en_exito(municipal, reloj):
    municipal.return_value.update(ok=False, datos=[], error="Fallo municipal")
    result = instalaciones.nodo_instalaciones({"user_message": "Centros ahora"})
    tr = result["specialist_results"]["instalaciones"]
    assert tr.status == "error" and tr.error == "Fallo municipal"
    assert tr.evidence == []
    assert tr.data["hora_actual"] == reloj.return_value


@pytest.mark.parametrize("respuesta", [
    None, [], {},
    {"ok": True, "resultado": "hora inventada", "fuentes": [],
     "abstained": False, "error": None},
    {"ok": True, "resultado": {}, "fuentes": [],
     "abstained": False, "error": None},
    {"ok": True, "resultado": {}, "fuentes": [None],
     "abstained": False, "error": None},
])
def test_reloj_malformado_se_limita_sin_romper_resultado(municipal, reloj, respuesta):
    reloj.return_value = respuesta
    update = instalaciones.nodo_instalaciones({"user_message": "Centros hoy"})
    result = update["specialist_results"]["instalaciones"]
    assert result.status == "ok" and result.error is None
    assert result.evidence[0].source == "test://centro"
    assert result.data["hora_actual"]["resultado"] is None
    assert result.data["hora_actual"]["ok"] is False
    assert result.data["advertencias"]
    assert update["debug_trace"][-1].endswith("status=error")


@pytest.mark.parametrize("falla", [False, True])
def test_reloj_conserva_data_y_traza_en_checkpoint_y_sintesis(municipal, reloj, falla):
    from agentes.agent import AgentService
    from agentes.nodes.sintetizar import sintetizar

    if falla:
        reloj.side_effect = RuntimeError("reloj no disponible")
    municipal.return_value["advertencias"] = ["Advertencia municipal previa"]

    def documental(state):
        return {"specialist_results": {
            **state.get("specialist_results", {}),
            "documental": ToolResult("abstained", "Sin consulta RAG; doble explícito"),
        }, "debug_trace": ["documental: doble"]}

    service = AgentService(
        documental_node=documental, instalaciones_node=instalaciones.nodo_instalaciones,
        sintetizar_node=sintetizar, aplicar_node=lambda state: {"done": state["approved"]},
    )
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("Lista de centros hoy", tid)
    snapshot = service.consultar_estado(tid)
    assert pending["pendiente_hitl"] and pending["approved"] is None
    assert snapshot["specialist_results"]["documental"].status == "abstained"
    result = snapshot["specialist_results"]["instalaciones"]
    assert result.status == "ok" and result.error is None
    assert "Advertencia municipal previa" in result.data["advertencias"]
    assert result.data["hora_actual"]["ok"] is (not falla)
    assert sum("instalaciones.tool: hora_actual" in e for e in snapshot["debug_trace"]) == 1
    assert "documental: doble" in snapshot["debug_trace"]
    assert "abierto" not in snapshot["final_answer"].casefold()
    if falla:
        assert "Hora actual no disponible" in snapshot["final_answer"]
    else:
        assert result.data["hora_actual"] == reloj.return_value
    service.consultar_estado(tid)
    reloj.assert_called_once_with(zona="Europe/Madrid")
    municipal.assert_called_once_with(modo="catalogo", centro_id=None)
