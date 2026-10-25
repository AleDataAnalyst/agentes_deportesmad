"""
tests/test_node_documental.py

Tests del nodo especialista documental (agentes/nodes/documental.py).

Contrato: nodo_documental(state) -> {"documental": {...}}
Solo se actualiza la clave autorizada "documental".
"""
import agentes.nodes.documental as nod
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