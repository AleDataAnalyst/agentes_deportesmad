from pathlib import Path
from types import SimpleNamespace

import pytest

import agentes.nodes.documental as nod
from agentes.nodes.documental import (
    guardar_imagen_subida,
    nodo_documental,
)


def test_imagen_adjunta_se_describe(monkeypatch, tmp_path):
    imagen = tmp_path / "cartel.jpg"
    imagen.write_bytes(b"imagen de prueba; la tool se sustituye por un doble")
    def _imagen_ok(image_id, pregunta):
        return {
            "ok": True,
            "resultado": "El cartel anuncia una actividad deportiva municipal.",
            "fuentes": [image_id],
            "abstained": False,
            "error": None,
        }

    def _rag_abstiene(consulta):
        return {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": True,
            "error": None,
        }

    monkeypatch.setitem(nod.REGISTRY, "imagen", _imagen_ok)
    monkeypatch.setitem(nod.REGISTRY, "rag", _rag_abstiene)

    out = nodo_documental(
        {
            "request_id": "img-1",
            "pedido": "¿Qué anuncia este cartel?",
            "image_id": str(imagen),
        }
    )
    d = out["documental"]

    # Primero el se describe la imagen, luego se consulta RAG
    assert [e["tool"] for e in d["eventos"]] == ["imagen", "rag"]
    assert d["abstained"] is False
    assert "cartel anuncia" in d["resultado"]
    assert str(imagen) in d["fuentes"]
    assert "no acredita normativa vigente" in d["resultado"]


@pytest.mark.parametrize("fuente_dict", [False, True])
def test_invoke_normaliza_fuentes_y_conserva_evidencia_si_rag_abstiene(
    monkeypatch, tmp_path, fuente_dict,
):
    from agentes.documental_adapter import crear_adaptador_documental
    from agentes.state import initial_state
    import agentes.documental_adapter as adapter

    imagen = tmp_path / "cartel.png"
    imagen.write_bytes(b"imagen para un proveedor doble")
    llamadas = []

    def invoke(argumentos):
        llamadas.append(argumentos)
        return {
            "ok": True, "resultado": "Actividad municipal",
            "fuentes": [{"ruta": str(imagen)}] if fuente_dict else [str(imagen)],
            "abstained": False, "error": None,
        }

    monkeypatch.setattr(nod, "imagen_preguntar", SimpleNamespace(invoke=invoke))
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "", "fuentes": [],
        "abstained": True, "error": None,
    })
    monkeypatch.setattr(adapter, "validar_image_id", lambda image_id: image_id)
    state = initial_state("Describe el cartel")
    state["image_id"] = str(imagen)
    result = crear_adaptador_documental(ejecutar_documental=nodo_documental)(state)
    documental = result["specialist_results"]["documental"]
    assert llamadas == [{"image_id": str(imagen), "pregunta": "Describe el cartel"}]
    assert documental.status == "ok"
    assert documental.data["fuentes"] == [str(imagen)]
    assert documental.evidence[0].source == str(imagen)
    assert [e["tool"] for e in documental.data["eventos"]] == ["imagen", "rag"]
    assert "Actividad municipal" in documental.answer


def test_imagen_invalida_genera_error(monkeypatch):
    def _imagen_error(image_id, pregunta):
        return {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": False,
            "error": "IMAGE_NOT_FOUND",
        }

    def _rag_abstiene(consulta):
        return {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": True,
            "error": None,
        }

    monkeypatch.setitem(nod.REGISTRY, "imagen", _imagen_error)
    monkeypatch.setitem(nod.REGISTRY, "rag", _rag_abstiene)

    out = nodo_documental(
        {
            "request_id": "img-2",
            "pedido": "Describe la imagen",
            "image_id": "no-existe.jpg",
        }
    )
    d = out["documental"]

    assert "imagen no disponible o formato no admitido" in d["limitaciones"]
    assert [e["tool"] for e in d["eventos"]] == ["rag"]
    assert d["abstained"] is True
    assert d["resultado"] == ""


def test_guardar_imagen_valida_formato(tmp_path, monkeypatch):
    monkeypatch.setattr(nod, "DIRECTORIO_IMAGENES", tmp_path)

    image_id = guardar_imagen_subida("cartel.png", b"contenido")

    assert image_id.endswith(".png")
    assert (tmp_path / Path(image_id).name).read_bytes() == b"contenido"


def test_guardar_imagen_rechaza_formato(tmp_path, monkeypatch):
    monkeypatch.setattr(nod, "DIRECTORIO_IMAGENES", tmp_path)

    try:
        guardar_imagen_subida("documento.pdf", b"contenido")
        raise AssertionError("Debía rechazar el formato PDF")
    except ValueError as exc:
        assert "IMAGE_UNSUPPORTED" in str(exc)
