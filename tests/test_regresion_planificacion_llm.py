"""Regresión offline: fallos del LLM, presupuesto y validación de observaciones.

Todo se prueba con dobles (adaptador LLM, RAG, visión, consulta municipal): sin
red, sin modelos reales y sin índice. Cada test activa el modo llm de forma
explícita, porque tests/conftest.py fuerza el modo reglas por defecto.
"""

import pytest
from copy import deepcopy
from unittest.mock import Mock

import agentes.especialista_llm as esp
import agentes.nodes.documental as nod
from agentes.llm import LlmResponse
from agentes.nodes import instalaciones


class AdapterQueFalla:
    """Devuelve las respuestas preparadas y lanza una excepción en la llamada indicada."""

    def __init__(self, respuestas, falla_en):
        self.respuestas = list(respuestas)
        self.falla_en = falla_en
        self.llamadas = 0

    def generate(self, messages, tools, **_):
        self.llamadas += 1
        if self.llamadas == self.falla_en:
            raise RuntimeError("modelo caído")
        if self.respuestas:
            return self.respuestas.pop(0)
        return LlmResponse(text="listo")


def _call(nombre, **args):
    return LlmResponse(tool_calls=[{"id": nombre, "name": nombre, "arguments": args}])


def _obs(resultado="Abono: 45 €", fuentes=("tarifas.pdf",), **extra):
    return {
        "ok": True, "resultado": resultado, "fuentes": list(fuentes),
        "abstained": False, "error": None, **extra,
    }


@pytest.fixture
def imagen_valida(tmp_path):
    ruta = tmp_path / "cartel.jpg"
    ruta.write_bytes(b"jpg")
    return str(ruta)


class Contador:
    """Cuenta las ejecuciones reales de una tool doble."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def __call__(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))
        return self.respuesta


def _preparar_documental(monkeypatch, adapter, *, rag=None, imagen=None):
    monkeypatch.setenv("ESPECIALISTAS_MODO", "llm")
    rag = rag or Contador(_obs())
    imagen = imagen or Contador(_obs("Cartel Verano Deportivo 2026", ("cartel.jpg",)))
    monkeypatch.setitem(nod.REGISTRY, "rag", rag)
    monkeypatch.setitem(nod.REGISTRY, "imagen", imagen)
    monkeypatch.setattr(esp, "crear_adapter", lambda: adapter)
    return rag, imagen


# ---------------------------------------------------------------------------
# Documental: el fallo del LLM no pierde lo ya hecho
# ---------------------------------------------------------------------------

def test_documental_conserva_la_llamada_ya_hecha_si_falla_el_llm(monkeypatch):
    adapter = AdapterQueFalla([_call("rag", consulta="precio abono")], falla_en=2)
    rag, _ = _preparar_documental(monkeypatch, adapter)

    out = nod.nodo_documental({"request_id": "r1", "pedido": "¿Cuánto cuesta el abono?"})["documental"]

    assert [e["tool"] for e in out["eventos"]] == ["rag"]
    assert out["eventos"][0]["args"] == {"consulta": "precio abono"}
    assert out["abstained"] is False
    assert "Abono: 45 €" in out["resultado"]
    assert out["fuentes"] == ["tarifas.pdf"]


def test_documental_no_repite_llamadas_ni_reinicia_el_presupuesto(monkeypatch, imagen_valida):
    adapter = AdapterQueFalla([_call("rag", consulta="abono")], falla_en=2)
    rag, imagen = _preparar_documental(monkeypatch, adapter)

    out = nod.nodo_documental({
        "request_id": "r1", "pedido": "¿Cuánto cuesta el abono?",
        "image_id": imagen_valida, "presupuesto_tools": 2,
    })["documental"]

    # El RAG se ejecutó una sola vez y las reglas no se relanzaron tras el fallo:
    # la imagen no se consulta aunque quedara presupuesto.
    assert len(rag.llamadas) == 1
    assert len(imagen.llamadas) == 0
    assert [e["tool"] for e in out["eventos"]] == ["rag"]


def test_documental_registra_el_fallo_en_el_diagnostico(monkeypatch):
    adapter = AdapterQueFalla([_call("rag", consulta="abono")], falla_en=2)
    _preparar_documental(monkeypatch, adapter)

    out = nod.nodo_documental({"request_id": "r1", "pedido": "abono"})["documental"]

    assert any("planificación LLM interrumpida" in x for x in out["limitaciones"])


def test_documental_sin_llamadas_previas_cae_a_reglas_una_sola_vez(monkeypatch, imagen_valida):
    adapter = AdapterQueFalla([], falla_en=1)
    rag, imagen = _preparar_documental(monkeypatch, adapter)

    out = nod.nodo_documental({
        "request_id": "r1", "pedido": "abono", "image_id": imagen_valida,
    })["documental"]

    assert len(rag.llamadas) == 1
    assert len(imagen.llamadas) == 1
    assert any("planificación LLM no disponible" in x for x in out["limitaciones"])


# ---------------------------------------------------------------------------
# Documental: validación de observaciones (modo reglas, sin LLM)
# ---------------------------------------------------------------------------

def _documental_reglas(monkeypatch, observacion, **estado):
    monkeypatch.setenv("ESPECIALISTAS_MODO", "reglas")
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: observacion)
    return nod.nodo_documental({"request_id": "r1", "pedido": "abono", **estado})["documental"]


def test_observacion_con_ok_false_no_es_evidencia(monkeypatch):
    out = _documental_reglas(monkeypatch, {**_obs(), "ok": False})
    assert out["abstained"] is True
    assert out["resultado"] == ""
    assert out["fuentes"] == []


def test_observacion_con_error_no_es_evidencia(monkeypatch):
    out = _documental_reglas(monkeypatch, {**_obs(), "error": "boom"})
    assert out["abstained"] is True
    assert out["resultado"] == ""
    assert "boom" in out["errores"]


def test_observacion_abstenida_no_es_evidencia(monkeypatch):
    out = _documental_reglas(monkeypatch, {**_obs(), "abstained": True})
    assert out["abstained"] is True
    assert out["resultado"] == ""


def test_observacion_con_fuentes_mezcladas_se_descarta_entera(monkeypatch):
    out = _documental_reglas(
        monkeypatch,
        _obs("Abono: 45 €", ("tarifas.pdf", "secreto.pdf")),
        contexto_permitido=["tarifas.pdf"],
    )
    # No basta con filtrar las citas: el texto pudo salir de la fuente excluida.
    assert out["abstained"] is True
    assert out["resultado"] == ""
    assert out["fuentes"] == []
    assert any("fuera del contexto permitido" in x for x in out["limitaciones"])


def test_observacion_con_todas_las_fuentes_permitidas_se_acepta(monkeypatch):
    out = _documental_reglas(
        monkeypatch, _obs(), contexto_permitido=["tarifas.pdf", "otra.pdf"],
    )
    assert out["abstained"] is False
    assert out["fuentes"] == ["tarifas.pdf"]


# ---------------------------------------------------------------------------
# Instalaciones: fallo del LLM y límite de herramientas
# ---------------------------------------------------------------------------

CONSULTA_OK = {
    "ok": True, "modo": "catalogo", "datos": [{"nombre": "Centro Deportivo Test", "distrito": "CENTRO"}],
    "fuente": "", "origen": "api",
    "fecha_consulta": "2026-10-27T10:00:00+01:00", "fecha_captura_fallback": None,
    "advertencias": [], "error": None, "requiere_aclaracion": False,
}


def _preparar_instalaciones(monkeypatch, adapter):
    monkeypatch.setenv("ESPECIALISTAS_MODO", "llm")
    consulta = Contador(CONSULTA_OK)
    monkeypatch.setattr(instalaciones, "consultar_instalaciones", consulta)
    monkeypatch.setattr(esp, "crear_adapter", lambda: adapter)
    return consulta


def test_instalaciones_conserva_la_consulta_ya_hecha_si_falla_el_llm(monkeypatch):
    adapter = AdapterQueFalla([_call("consultar_instalaciones", modo="catalogo")], falla_en=2)
    consulta = _preparar_instalaciones(monkeypatch, adapter)

    out = instalaciones.nodo_instalaciones({"user_message": "lista de centros"})

    # La consulta del LLM se ejecutó (la hace la herramienta del especialista)
    # y el nodo no la repite por reglas.
    assert len(consulta.llamadas) == 1
    assert out["specialist_results"]["instalaciones"].status == "ok"
    historial = out["specialist_results"]["instalaciones"].data["llamadas_tools"]
    assert len(historial) == 1 and historial[0]["resultado"] == CONSULTA_OK
    assert sum("instalaciones.tool:" in e for e in out["debug_trace"]) == 1


def test_instalaciones_registra_el_fallo_en_el_diagnostico(monkeypatch):
    adapter = AdapterQueFalla([_call("consultar_instalaciones", modo="catalogo")], falla_en=2)
    _preparar_instalaciones(monkeypatch, adapter)

    out = instalaciones.nodo_instalaciones({"user_message": "lista de centros"})

    resultado = out["specialist_results"]["instalaciones"]
    diagnostico = " ".join(out["debug_trace"] + list(resultado.data.get("advertencias") or []))
    assert "planificación LLM" in diagnostico


def test_instalaciones_agotado_el_limite_no_hace_otra_consulta_municipal(monkeypatch):
    # Tres peticiones al límite (MAX_STEPS_INSTALACIONES) y ninguna es la consulta municipal.
    respuestas = [_call("hora_actual") for _ in range(instalaciones.MAX_STEPS_INSTALACIONES)]
    adapter = AdapterQueFalla(respuestas, falla_en=99)
    consulta = _preparar_instalaciones(monkeypatch, adapter)

    instalaciones.nodo_instalaciones({"user_message": "lista de centros"})

    assert len(consulta.llamadas) == 0


def test_instalaciones_sin_llamadas_previas_cae_a_reglas_con_una_consulta(monkeypatch):
    adapter = AdapterQueFalla([], falla_en=1)
    consulta = _preparar_instalaciones(monkeypatch, adapter)

    out = instalaciones.nodo_instalaciones({"user_message": "lista de centros"})

    assert len(consulta.llamadas) == 1
    assert out["specialist_results"]["instalaciones"].status == "ok"


@pytest.mark.parametrize("respuestas", [
    [_call("consultar_instalaciones", modo="avisos", centro_id="114782")],
    [_call("hora_actual")] * instalaciones.MAX_STEPS_INSTALACIONES,
    [_call("no_autorizada")] * instalaciones.MAX_STEPS_INSTALACIONES,
])
def test_instalaciones_no_resuelve_nombres_tras_consulta_llm_o_limite(monkeypatch, respuestas):
    consulta = _preparar_instalaciones(monkeypatch, AdapterQueFalla(respuestas, falla_en=99))
    resolver = Mock(return_value=[{"pk": "114782"}])
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", resolver)

    instalaciones.nodo_instalaciones({"user_message": "¿hay algún cierre en La Elipa?"})

    resolver.assert_not_called()
    assert len(consulta.llamadas) == (1 if len(respuestas) == 1 else 0)


def test_instalaciones_resolucion_de_nombre_consume_el_presupuesto_restante(monkeypatch):
    adapter = AdapterQueFalla([_call("hora_actual"), _call("hora_actual")], falla_en=3)
    consulta = _preparar_instalaciones(monkeypatch, adapter)
    resolver = Mock(return_value=[{"pk": "114782"}])
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", resolver)

    out = instalaciones.nodo_instalaciones({"user_message": "¿hay algún cierre en La Elipa?"})

    resolver.assert_called_once()
    assert consulta.llamadas == []
    resultado = out["specialist_results"]["instalaciones"]
    assert resultado.status == "error"
    assert "Límite de herramientas" in resultado.error
    assert any("planificación LLM interrumpida" in e for e in out["debug_trace"])


@pytest.mark.parametrize("modo", ["reglas", "llm"])
def test_instalaciones_reglas_comparten_limite_con_resolver_y_reloj(monkeypatch, modo):
    # Una resolución requiere una consulta al catálogo: no es una operación local gratis.
    consulta = _preparar_instalaciones(monkeypatch, AdapterQueFalla([], falla_en=1))
    monkeypatch.setenv("ESPECIALISTAS_MODO", modo)
    monkeypatch.setattr(instalaciones, "MAX_STEPS_INSTALACIONES", 1)
    resolver = Mock(return_value=[{"pk": "114782"}])
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", resolver)

    out = instalaciones.nodo_instalaciones({"user_message": "cierre en La Elipa"})

    resolver.assert_called_once()
    assert consulta.llamadas == []
    assert out["specialist_results"]["instalaciones"].status == "error"


def test_instalaciones_reloj_por_reglas_consume_un_turno(monkeypatch):
    consulta = _preparar_instalaciones(monkeypatch, AdapterQueFalla([], falla_en=1))
    monkeypatch.setenv("ESPECIALISTAS_MODO", "reglas")
    monkeypatch.setattr(instalaciones, "MAX_STEPS_INSTALACIONES", 1)
    reloj = Mock(wraps=instalaciones.hora_actual)
    resolver = Mock(return_value=[])
    monkeypatch.setattr(instalaciones, "hora_actual", reloj)
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", resolver)

    out = instalaciones.nodo_instalaciones({"user_message": "cierre en La Elipa hoy"})

    reloj.assert_called_once_with(zona="Europe/Madrid")
    resolver.assert_not_called()
    assert consulta.llamadas == []
    assert out["specialist_results"]["instalaciones"].status == "error"


@pytest.mark.parametrize("falla", [False, True])
def test_instalaciones_conserva_varias_consultas_con_procedencia(monkeypatch, falla):
    respuestas = [
        _call("consultar_instalaciones", modo="catalogo"),
        _call("consultar_instalaciones", modo="avisos", centro_id="114782"),
    ]
    adapter = AdapterQueFalla(respuestas, falla_en=3 if falla else 99)
    _preparar_instalaciones(monkeypatch, adapter)
    catalogo = deepcopy(CONSULTA_OK)
    catalogo.update(fuente="test://catalogo")
    avisos = {
        **deepcopy(CONSULTA_OK), "modo": "avisos", "origen": "fallback",
        "fuente": "test://captura", "fecha_captura_fallback": "2026-10-26",
        "datos": [{"centro_id": "114782", "texto_aviso": "Obras",
                   "aviso_detectado": True, "url_ficha": "test://aviso"}],
    }
    consulta = Mock(side_effect=[catalogo, avisos])
    monkeypatch.setattr(instalaciones, "consultar_instalaciones", consulta)

    out = instalaciones.nodo_instalaciones({"user_message": "lista de centros"})
    resultado = out["specialist_results"]["instalaciones"]

    assert consulta.call_count == 2
    assert resultado.data["origen"] == "fallback"
    assert resultado.evidence[0].source == "test://aviso"
    historial = resultado.data["llamadas_tools"]
    assert [ll["resultado"] for ll in historial] == [catalogo, avisos]
    assert [ll["args"]["modo"] for ll in historial] == ["catalogo", "avisos"]
    assert [ll["paso"] for ll in historial] == [1, 2]
    assert any("solo la última consulta" in a for a in resultado.data["advertencias"])
    eventos = [e for e in out["debug_trace"] if "instalaciones.tool:" in e]
    assert len(eventos) == 2
    assert "catalogo" in eventos[0] and "114782" in eventos[1]
    assert all("status=ok" in e for e in eventos)
    if falla:
        assert any("planificación LLM interrumpida" in e for e in out["debug_trace"])
    catalogo["datos"].clear()
    assert historial[0]["resultado"]["datos"]  # Sin alias con el proveedor.


def test_ejecutor_conserva_resultado_y_evento_al_fallar_modelo():
    from agentes.especialista_llm import FalloPlanificacion, Herramienta, ejecutar_especialista

    tool = Mock(return_value=_obs())
    adapter = AdapterQueFalla([_call("eco", consulta="abono")], falla_en=2)
    with pytest.raises(FalloPlanificacion) as fallo:
        ejecutar_especialista(
            prompt_sistema="p", mensaje="m", max_steps=2, adapter=adapter,
            herramientas=[Herramienta("eco", "doble", {}, tool)],
        )
    tool.assert_called_once_with(consulta="abono")
    assert len(fallo.value.llamadas) == 1
    assert fallo.value.llamadas[0]["resultado"] == _obs()
    assert fallo.value.llamadas[0]["status"] == "ok"
    assert isinstance(fallo.value.__cause__, RuntimeError)


@pytest.mark.parametrize("modo", ["reglas", "llm"])
def test_instalaciones_limite_cero_no_ejecuta_ninguna_tool(monkeypatch, modo):
    consulta = _preparar_instalaciones(monkeypatch, AdapterQueFalla([], falla_en=1))
    monkeypatch.setenv("ESPECIALISTAS_MODO", modo)
    monkeypatch.setattr(instalaciones, "MAX_STEPS_INSTALACIONES", 0)
    reloj, resolver = Mock(), Mock()
    monkeypatch.setattr(instalaciones, "hora_actual", reloj)
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", resolver)

    out = instalaciones.nodo_instalaciones({"user_message": "cierre en La Elipa hoy"})

    reloj.assert_not_called()
    resolver.assert_not_called()
    assert consulta.llamadas == []
    assert out["specialist_results"]["instalaciones"].status == "error"


def test_instalaciones_resolver_fallido_no_repite_ni_expone_excepcion(monkeypatch):
    consulta = _preparar_instalaciones(monkeypatch, AdapterQueFalla([], falla_en=1))
    resolver = Mock(side_effect=RuntimeError("detalle interno"))
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", resolver)

    out = instalaciones.nodo_instalaciones({"user_message": "cierre en La Elipa"})

    resolver.assert_called_once()
    assert consulta.llamadas == []
    resultado = out["specialist_results"]["instalaciones"]
    assert resultado.status == "error"
    assert resultado.data["llamadas_tools"][0]["status"] == "error"
    assert "detalle interno" not in str(out)


def test_instalaciones_fallback_resuelve_y_consulta_dentro_del_limite(monkeypatch):
    adapter = AdapterQueFalla([_call("hora_actual")], falla_en=2)
    consulta = _preparar_instalaciones(monkeypatch, adapter)
    resolver = Mock(return_value=[{"pk": "114782"}])
    monkeypatch.setattr(instalaciones, "resolver_centro_por_nombre", resolver)

    out = instalaciones.nodo_instalaciones({"user_message": "cierre en La Elipa"})

    resolver.assert_called_once()
    assert consulta.llamadas == [((), {"modo": "avisos", "centro_id": "114782"})]
    historial = out["specialist_results"]["instalaciones"].data["llamadas_tools"]
    assert [ll["tool"] for ll in historial] == [
        "hora_actual", "resolver_centro_por_nombre", "consultar_instalaciones",
    ]
    assert [ll["paso"] for ll in historial] == [1, 2, 3]


def test_ejecutor_congela_resultados_si_una_tool_reutiliza_el_diccionario():
    from agentes.especialista_llm import Herramienta, ejecutar_especialista

    compartido = _obs()

    def tool(consulta):
        compartido["resultado"] = consulta
        return compartido

    llamadas = ejecutar_especialista(
        prompt_sistema="p", mensaje="m", max_steps=2,
        herramientas=[Herramienta("eco", "doble", {}, tool)],
        adapter=AdapterQueFalla([
            _call("eco", consulta="primero"), _call("eco", consulta="segundo"),
        ], falla_en=99),
    )
    assert [ll["resultado"]["resultado"] for ll in llamadas] == ["primero", "segundo"]
