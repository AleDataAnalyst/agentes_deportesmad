"""
tests/test_node_documental.py

Tests del nodo especialista documental (agentes/nodes/documental.py).

Contrato: nodo_documental(state) -> {"documental": {...}}
Solo se actualiza la clave autorizada "documental".
"""
import agentes.nodes.documental as nod
import pytest
from agentes.nodes.documental import nodo_documental

CLAVES_DOCUMENTAL = {
    "request_id", "resultado", "fuentes",
    "abstained", "errores", "limitaciones", "eventos",
}


def _obs_ok():
    return {
        "ok": True, "resultado": "El abono cuesta 45 €.",
        "fuentes": ["abonos.csv"], "abstained": False, "error": None,
    }


def test_salida_solo_campo_autorizado(monkeypatch):
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: _obs_ok())
    out = nodo_documental({"request_id": "r1", "pedido": "¿Cuánto cuesta el abono?"})
    assert set(out) == {"documental"}
    assert set(out["documental"]) == CLAVES_DOCUMENTAL
    d = out["documental"]
    assert d["request_id"] == "r1"
    assert d["abstained"] is False
    assert d["fuentes"] == ["abonos.csv"]
    assert [e["tool"] for e in d["eventos"]] == ["rag"]


def test_imagen_prevista_no_disponible(monkeypatch):
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: _obs_ok())
    monkeypatch.setitem(nod.REGISTRY, "imagen", None)
    out = nodo_documental({"request_id": "r2", "pedido": "¿Qué dice el cartel?", "image_id": "img_1"})
    d = out["documental"]
    assert any("imagen" in l for l in d["limitaciones"])
    assert [e["tool"] for e in d["eventos"]] == ["rag"]  # imagen no se llama


def test_presupuesto_agotado(monkeypatch):
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: _obs_ok())
    out = nodo_documental({"request_id": "r3", "pedido": "x", "presupuesto_tools": 0})
    d = out["documental"]
    assert d["eventos"] == []
    assert any("presupuesto" in l for l in d["limitaciones"])
    assert d["abstained"] is True


def test_contexto_permitido_filtra_fuentes(monkeypatch):
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: _obs_ok())
    out = nodo_documental({"request_id": "r4", "pedido": "x", "contexto_permitido": ["otro.pdf"]})
    d = out["documental"]
    assert d["fuentes"] == []
    assert d["abstained"] is True
    assert any("contexto permitido" in l for l in d["limitaciones"])


def test_error_de_tool_no_lanza(monkeypatch):
    def _falla(consulta):
        raise RuntimeError("boom")
    monkeypatch.setitem(nod.REGISTRY, "rag", _falla)
    out = nodo_documental({"request_id": "r5", "pedido": "x"})
    d = out["documental"]
    assert d["errores"]
    assert d["abstained"] is True
    assert d["resultado"] == ""
    assert d["eventos"][0]["ok"] is False


@pytest.mark.parametrize("cambio", [
    {"ok": False}, {"error": "Timeout del proveedor"},
    {"resultado": " "}, {"abstained": True},
])
def test_observacion_no_util_nunca_se_presenta_como_evidencia(monkeypatch, cambio):
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {**_obs_ok(), **cambio})
    d = nodo_documental({"request_id": "fallo", "pedido": "consulta"})["documental"]
    assert d["abstained"] is True
    assert d["resultado"] == ""
    assert d["fuentes"] == []


@pytest.mark.parametrize("observacion", [None, [], {"fuentes": None},
                                           {"fuentes": [], "resultado": 42}])
def test_observacion_malformada_se_registra_sin_lanzar(monkeypatch, observacion):
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: observacion)
    d = nodo_documental({"request_id": "malformada", "pedido": "consulta"})["documental"]
    assert d["errores"]
    assert d["abstained"] is True
    assert len(d["eventos"]) == 1
    assert d["eventos"][0]["ok"] is False


def test_fuentes_mixtas_no_filtran_texto_fuera_del_contexto(monkeypatch):
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        **_obs_ok(), "fuentes": ["permitida.csv", "privada.pdf"],
        "resultado": "Texto que incluye datos de privada.pdf",
    })
    d = nodo_documental({"request_id": "contexto", "pedido": "consulta",
                        "contexto_permitido": ["permitida.csv"]})["documental"]
    assert d["resultado"] == "" and d["fuentes"] == []
    assert d["abstained"] is True


def test_presupuesto_uno_limita_imagen_y_rag(monkeypatch, tmp_path):
    imagen = tmp_path / "cartel.png"
    imagen.write_bytes(b"doble")
    calls = []
    monkeypatch.setitem(nod.REGISTRY, "imagen", lambda **kwargs: (calls.append("imagen") or _obs_ok()))
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda **kwargs: (calls.append("rag") or _obs_ok()))
    d = nodo_documental({"request_id": "limite", "pedido": "consulta",
                        "image_id": str(imagen), "presupuesto_tools": 1})["documental"]
    assert calls == ["imagen"]
    assert len(d["eventos"]) == 1
    assert any("presupuesto" in l for l in d["limitaciones"])
