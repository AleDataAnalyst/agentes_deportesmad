"""Subida de imágenes: solo JPG y PNG reales, con nombre generado."""

from pathlib import Path

import pytest

import clientes.imagenes as img

PNG = b"\x89PNG\r\n\x1a\n" + b"datos"
JPG = b"\xff\xd8\xff\xe0" + b"datos"


@pytest.fixture(autouse=True)
def _directorio(tmp_path, monkeypatch):
    monkeypatch.setattr(img, "DIRECTORIO_IMAGENES", tmp_path)
    return tmp_path


@pytest.mark.parametrize("nombre,contenido,sufijo", [
    ("cartel.png", PNG, ".png"), ("foto.jpg", JPG, ".jpg"),
    ("foto.JPEG", JPG, ".jpeg"), ("CARTEL.PNG", PNG, ".png"),
])
def test_guarda_y_devuelve_image_id(_directorio, nombre, contenido, sufijo):
    image_id = img.guardar_imagen_subida(nombre, contenido)
    assert image_id.endswith(sufijo)
    assert Path(image_id).read_bytes() == contenido


def test_no_usa_el_nombre_original(_directorio):
    image_id = img.guardar_imagen_subida("../../etc/passwd.png", PNG)
    assert Path(image_id).parent == _directorio
    assert "passwd" not in image_id
    assert image_id != img.guardar_imagen_subida("../../etc/passwd.png", PNG)


@pytest.mark.parametrize("nombre,contenido,codigo", [
    ("doc.pdf", b"%PDF-1.4", "IMAGE_UNSUPPORTED"),
    ("sin_extension", PNG, "IMAGE_UNSUPPORTED"),
    ("", PNG, "IMAGE_UNSUPPORTED"),
    ("vacia.png", b"", "IMAGE_EMPTY"),
    ("falsa.png", b"no soy una imagen", "IMAGE_INVALID"),
    ("cambiada.png", JPG, "IMAGE_INVALID"),
])
def test_rechaza_lo_que_no_es_una_imagen_valida(_directorio, nombre, contenido, codigo):
    with pytest.raises(ValueError, match=codigo):
        img.guardar_imagen_subida(nombre, contenido)
    assert list(_directorio.iterdir()) == []


def test_rechaza_imagen_demasiado_grande(monkeypatch):
    monkeypatch.setattr(img, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match="IMAGE_TOO_LARGE"):
        img.guardar_imagen_subida("grande.png", PNG + b"x" * 20)


def _app_subida():
    import clientes.streamlit_app as m

    class Falso:
        def nueva_conversacion(self):
            return "deportes-abc123"

        def consultar_estado(self, thread_id):
            return {}

    m.crear_servicio = lambda modo="real": Falso()
    m.render()


def test_streamlit_ofrece_el_selector_solo_jpg_y_png():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app_subida, default_timeout=20).run()
    assert not at.exception
    selector = at.get("file_uploader")
    assert len(selector) == 1
    assert set(selector[0].proto.type) == {".jpg", ".jpeg", ".png"}
