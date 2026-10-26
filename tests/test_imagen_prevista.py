from pathlib import Path

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

    assert [e["tool"] for e in d["eventos"]] == ["imagen", "rag"]
    assert d["abstained"] is False
    assert "cartel anuncia" in d["resultado"]
    assert str(imagen) in d["fuentes"]
    assert "no acredita normativa vigente" in d["resultado"]


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
