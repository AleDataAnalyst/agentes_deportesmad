"""Tests de la tool de visión (agentes/tools/vision.py)."""
import agentes.nodes.documental as nod
import pytest
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


def test_nodo_documental_llama_a_imagen_con_invoke(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "x", "fuentes": [], "abstained": False, "error": None,
    })
    imagen = tmp_path / "cartel.jpg"
    imagen.write_bytes(b"imagen de prueba sin consultar la API")
    out = nodo_documental({"request_id": "r1", "pedido": "¿Qué dice el cartel?", "image_id": str(imagen)})
    eventos = out["documental"]["eventos"]
    assert [e["tool"] for e in eventos] == ["imagen", "rag"]
    assert eventos[0]["ok"] is False
    assert eventos[0]["abstained"] is True
    assert any("GOOGLE_API_KEY" in e for e in out["documental"]["errores"])


@pytest.mark.parametrize("extension,mime", [
    (".png", "image/png"), (".jpg", "image/jpeg"),
    (".jpeg", "image/jpeg"), (".webp", "image/webp"),
])
def test_vision_envia_mime_y_fuentes_compatibles_con_documental(monkeypatch, tmp_path, extension, mime):
    import agentes.tools.vision as vision
    from types import SimpleNamespace

    imagen = tmp_path / f"cartel{extension}"
    imagen.write_bytes(b"bytes transportados a un proveedor doble")
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-doble")
    llamadas = []

    def post(url, **kwargs):
        llamadas.append(kwargs)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"candidates": [{"content": {"parts": [{"text": "Cartel municipal"}]}}]},
        )

    monkeypatch.setattr(vision.requests, "post", post)
    r = imagen_preguntar.invoke({"image_id": str(imagen)})
    assert r["ok"] is True and r["error"] is None
    assert r["fuentes"] == [str(imagen)]
    parte = llamadas[0]["json"]["contents"][0]["parts"][1]
    assert parte["inline_data"]["mime_type"] == mime


def test_imagen_con_proveedor_doble_pasa_el_adaptador_comun(monkeypatch, tmp_path):
    import agentes.tools.vision as vision
    from agentes.documental_adapter import crear_adaptador_documental
    from agentes.state import initial_state
    from types import SimpleNamespace

    imagen = tmp_path / "cartel.png"
    imagen.write_bytes(b"doble")
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-doble")
    monkeypatch.setattr(vision.requests, "post", lambda *args, **kwargs: SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"candidates": [{"content": {"parts": [{"text": "Cartel municipal"}]}}]},
    ))
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "", "fuentes": [], "abstained": True, "error": None,
    })
    # La autorización de ruta tiene sus propias regresiones; aquí se comprueba
    # el contrato real tool → nodo → adaptador con una imagen temporal.
    import agentes.documental_adapter as adapter
    monkeypatch.setattr(adapter, "validar_image_id", lambda image_id: image_id)
    state = initial_state("Describe el cartel")
    state["image_id"] = str(imagen)
    node = crear_adaptador_documental(ejecutar_documental=nodo_documental)
    result = node(state)["specialist_results"]["documental"]
    assert result.status == "ok"
    assert result.evidence[0].source == str(imagen)
    assert "no acredita normativa vigente" in result.answer
