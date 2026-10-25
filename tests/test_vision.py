"""Tests de la tool de visión (agentes/tools/vision.py)."""
import agentes.nodes.documental as nod
from agentes.nodes.documental import nodo_documental
from agentes.tools.vision import imagen_preguntar

CLAVES = {"ok", "resultado", "fuentes", "abstained", "error"}


def test_imagen_inexistente_devuelve_error(tmp_path):
    out = imagen_preguntar.invoke({"image_id": str(tmp_path / "no_existe.jpg")})
    assert set(out) == CLAVES
    assert out["ok"] is False
    assert "No hay imagen" in out["error"]


def test_formato_no_soportado(tmp_path):
    gif = tmp_path / "foto.gif"
    gif.write_bytes(b"GIF89a")
    out = imagen_preguntar.invoke({"image_id": str(gif)})
    assert out["ok"] is False
    assert "Formato no soportado" in out["error"]


def test_sin_api_key_visión_no_disponible(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    out = imagen_preguntar.invoke({"image_id": "imagen_demo", "pregunta": "¿Qué ves?"})
    assert out["ok"] is False
    assert out["abstained"] is True
    assert "GOOGLE_API_KEY" in out["error"]
    assert out["resultado"] == ""


def test_nodo_documental_llama_a_imagen_con_invoke(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "x", "fuentes": [], "abstained": False, "error": None,
    })
    out = nodo_documental({"request_id": "r1", "pedido": "¿Qué dice el cartel?", "image_id": "imagen_demo"})
    eventos = out["documental"]["eventos"]
    assert [e["tool"] for e in eventos] == ["imagen", "rag"]
    assert eventos[0]["ok"] is False
    assert eventos[0]["abstained"] is True
    assert any("GOOGLE_API_KEY" in e for e in out["documental"]["errores"])
