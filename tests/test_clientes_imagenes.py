"""Subida de imágenes: solo JPG y PNG reales, con nombre generado."""

import io
from pathlib import Path

import pytest
from PIL import Image

import clientes.imagenes as img

def _imagen(formato: str) -> bytes:
    """Imagen real (2x2) para que Pillow y Streamlit puedan abrirla."""
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, formato)
    return buffer.getvalue()


PNG = _imagen("PNG")
JPG = _imagen("JPEG")


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
    assert image_id.startswith("output/imagenes/")
    assert (_directorio / Path(image_id).name).read_bytes() == contenido


def test_no_usa_el_nombre_original(_directorio):
    image_id = img.guardar_imagen_subida("../../etc/passwd.png", PNG)
    assert Path(image_id).parent == Path("output/imagenes")
    assert (_directorio / Path(image_id).name).is_file()
    assert "passwd" not in image_id
    assert image_id != img.guardar_imagen_subida("../../etc/passwd.png", PNG)


@pytest.mark.parametrize("nombre,contenido,codigo", [
    ("doc.pdf", b"%PDF-1.4", "IMAGE_UNSUPPORTED"),
    ("sin_extension", PNG, "IMAGE_UNSUPPORTED"),
    ("", PNG, "IMAGE_UNSUPPORTED"),
    ("vacia.png", b"", "IMAGE_EMPTY"),
    ("falsa.png", b"no soy una imagen", "IMAGE_INVALID"),
    ("cambiada.png", JPG, "IMAGE_INVALID"),
    ("truncada.png", PNG[:20], "IMAGE_INVALID"),
    ("firma-sola.png", b"\x89PNG\r\n\x1a\ndatos", "IMAGE_INVALID"),
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


def test_la_raiz_no_depende_del_directorio_de_arranque(tmp_path, monkeypatch):
    import importlib

    raiz = Path(img.__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    recargado = importlib.reload(img)
    assert recargado.RAIZ == raiz
    assert recargado.DIRECTORIO_IMAGENES == raiz / "output" / "imagenes"
    assert recargado.DIRECTORIO_IMAGENES.is_absolute()


def test_image_id_relativo_y_ruta_real_solo_para_mostrar(tmp_path, monkeypatch):
    monkeypatch.setattr(img, "RAIZ", tmp_path)
    monkeypatch.setattr(img, "DIRECTORIO_IMAGENES", tmp_path / "output" / "imagenes")
    image_id = img.guardar_imagen_subida("foto.png", PNG)
    assert not Path(image_id).is_absolute()
    assert img.ruta_imagen(image_id) == (tmp_path / image_id).resolve()
    assert img.ruta_imagen("output/imagenes/no-existe.png") is None
    assert img.ruta_imagen("../fuera.png") is None
    assert img.ruta_imagen(str(tmp_path / image_id)) is None
    assert img.ruta_imagen(None) is None


def _app_envio_imagen(acepta: bool):
    import tempfile
    from pathlib import Path

    import streamlit as st
    import clientes.imagenes as imgmod
    import clientes.streamlit_app as m

    if "llamadas" not in st.session_state:
        raiz = Path(tempfile.mkdtemp())
        (raiz / "output" / "imagenes").mkdir(parents=True)
        import io as _io
        from PIL import Image as _Image

        buffer = _io.BytesIO()
        _Image.new("RGB", (2, 2), "white").save(buffer, "PNG")
        (raiz / "output" / "imagenes" / "a.png").write_bytes(buffer.getvalue())
        imgmod.RAIZ = raiz

        class Con:
            def nueva_conversacion(self):
                return "deportes-abc123"

            def procesar_turno(self, mensaje, thread_id, *, image_id=None):
                st.session_state.llamadas.append(image_id)
                return {"thread_id": thread_id, "pendiente_hitl": False, "done": False,
                        "final_answer": "ok", "iterations": 1, "specialist_results": {}}

        class Sin:
            def nueva_conversacion(self):
                return "deportes-abc123"

            def procesar_turno(self, mensaje, thread_id):
                st.session_state.llamadas.append("sin-soporte")
                return {"thread_id": thread_id, "pendiente_hitl": False, "done": False,
                        "final_answer": "ok", "iterations": 1, "specialist_results": {}}

        st.session_state.llamadas = []
        st.session_state.service = Con() if acepta else Sin()
        st.session_state.thread_id = "deportes-abc123"
        st.session_state.messages = []
        st.session_state.estado = None
        st.session_state.image_id = "output/imagenes/a.png"
    m.validar_estado = lambda e, t: e
    m.render()


def test_streamlit_envia_el_image_id_si_el_backend_lo_acepta():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app_envio_imagen, args=(True,), default_timeout=20).run()
    assert not at.exception
    assert at.sidebar.get("image"), "la vista previa debe mostrarse con una imagen válida"
    assert any("se enviará" in c.value for c in at.sidebar.caption)
    assert not any("/" in c.value and c.value.startswith(("/", "C:")) for c in at.sidebar.caption)
    at.chat_input[0].set_value("hola").run()
    assert at.session_state.llamadas == ["output/imagenes/a.png"]


def test_streamlit_avisa_y_no_envia_si_el_backend_no_lo_acepta():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app_envio_imagen, args=(False,), default_timeout=20).run()
    assert any("todavía no la recibe" in c.value for c in at.sidebar.caption)
    at.chat_input[0].set_value("hola").run()
    assert at.session_state.llamadas == ["sin-soporte"]


def _app_vista_previa_rota():
    import tempfile
    from pathlib import Path

    import streamlit as st
    import clientes.imagenes as imgmod
    import clientes.streamlit_app as m

    if "listo" not in st.session_state:
        raiz = Path(tempfile.mkdtemp())
        (raiz / "output" / "imagenes").mkdir(parents=True)
        (raiz / "output" / "imagenes" / "a.png").write_bytes(b"no es una imagen")
        imgmod.RAIZ = raiz

        class Falso:
            def nueva_conversacion(self):
                return "deportes-abc123"

            def procesar_turno(self, mensaje, thread_id, *, image_id=None):
                return {}

        st.session_state.service = Falso()
        st.session_state.thread_id = "deportes-abc123"
        st.session_state.messages = []
        st.session_state.estado = None
        st.session_state.image_id = "output/imagenes/a.png"
        st.session_state.listo = True

    def falla(*args, **kwargs):
        raise OSError("cannot identify image file")

    st.image = falla
    m.render()


def test_una_vista_previa_ilegible_no_rompe_la_pagina():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app_vista_previa_rota, default_timeout=20).run()
    assert not at.exception
    assert any("No se puede mostrar la vista previa" in c.value for c in at.sidebar.caption)
    assert any("se enviará" in c.value for c in at.sidebar.caption)
