"""Transporte y autoridad de referencias con documental doble; sin visión/RAG."""
from copy import deepcopy
from pathlib import Path

import pytest

from agentes import image_input
from agentes.agent import AgentService
from agentes.documental_adapter import crear_adaptador_documental
from agentes.node_guards import especialista_protegido
from agentes.nodes.aplicar import aplicar, aplicar_node
from agentes.nodes.sintetizar import sintetizar, sintetizar_node
from agentes.nodes.supervisor import supervisor_node
from agentes.state import initial_state
from tests.test_documental_adapter import envelope
from tests.test_agent_service import service


@pytest.fixture
def image_root(tmp_path, monkeypatch):
    monkeypatch.setattr(image_input, "ROOT", tmp_path)
    folder = tmp_path / "output" / "imagenes"
    folder.mkdir(parents=True)
    # Marcador explícito: no es imagen real ni validación de su contenido.
    (folder / "doble.png").write_bytes(b"[DOBLE: no ejecutar vision]")
    (folder / "otro.jpg").write_bytes(b"[DOBLE]")
    (folder / "no.gif").write_bytes(b"[DOBLE]")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "imagen_demo.jpg").write_bytes(b"[DEMO DOBLE]")
    return tmp_path


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        pytest.fail("Estas pruebas solo admiten dependencias externas dobles")
    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.mark.parametrize("raw", ["output/imagenes/doble.png", "output\\imagenes\\doble.png",
                                  "imagen_demo", "assets/imagen_demo.jpg"])
def test_authorized_reference_without_reading_bytes(image_root, raw, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("La validación no debe abrir la imagen")
    monkeypatch.setattr(Path, "open", forbidden)
    result = image_input.validar_image_id(raw)
    assert Path(result).is_absolute() and Path(result).is_file()
    assert image_input.validar_image_id(result) == result


@pytest.mark.parametrize("raw,code", [
    ("", "IMAGE_ID_INVALID"), (123, "IMAGE_ID_INVALID"),
    ("output/imagenes/../imagenes/doble.png", "IMAGE_PATH_FORBIDDEN"),
    ("output\\imagenes\\..\\imagenes\\doble.png", "IMAGE_PATH_FORBIDDEN"),
    ("assets/otro.png", "IMAGE_PATH_FORBIDDEN"),
    ("output/imagenes/falta.png", "IMAGE_NOT_FOUND"),
    ("output/imagenes/no.gif", "IMAGE_UNSUPPORTED"),
    ("output/imagenes", "IMAGE_UNSUPPORTED"),
])
def test_invalid_reference_does_not_touch_checkpoint(image_root, raw, code):
    agent = service()
    tid = agent.nueva_conversacion()
    before = agent.consultar_estado(tid)
    with pytest.raises(ValueError, match=code) as error:
        agent.procesar_turno("[DOBLE] Consulta", tid, image_id=raw)
    assert str(image_root) not in str(error.value)
    assert agent.consultar_estado(tid) == before


def test_external_absolute_path_and_directory_are_rejected(image_root, tmp_path):
    external = tmp_path / "personal.png"
    external.write_bytes(b"[DOBLE]")
    for raw in (str(external), str(image_root / "output" / "imagenes" / "carpeta.png")):
        if raw.endswith("carpeta.png"):
            Path(raw).mkdir()
        with pytest.raises(ValueError) as error:
            image_input.validar_image_id(raw)
        assert str(tmp_path) not in str(error.value)


def test_resolved_link_outside_allowed_folder_is_rejected(image_root):
    target = image_root / "personal.png"
    target.write_bytes(b"[DOBLE]")
    link = image_root / "output" / "imagenes" / "enlace.png"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Crear enlaces requiere privilegios en este Windows")
    with pytest.raises(ValueError, match="IMAGE_PATH_FORBIDDEN"):
        image_input.validar_image_id(str(link))


@pytest.mark.parametrize("decision", [True, False])
@pytest.mark.parametrize("patch,status", [({}, "ok"), ({"abstained": True}, "abstained"),
                                         ({"errores": ["[DOBLE] Fallo"]}, "error")])
def test_transport_lifecycle_isolation_and_envelope(image_root, decision, patch, status):
    calls = []
    outputs = []
    def documental_doble(request):
        calls.append(deepcopy(request))
        output = {"documental": envelope(request, **patch)}
        outputs.append(output)
        request["image_id"] = "suplantada-por-doble"
        return output
    agent = service(documental_node=crear_adaptador_documental(
        ejecutar_documental=documental_doble), sintetizar_node=sintetizar, aplicar_node=aplicar)
    first, second = agent.nueva_conversacion(), agent.nueva_conversacion()
    image = image_input.validar_image_id("output/imagenes/doble.png")
    pending = agent.procesar_turno("[DOBLE] Consulta", first, image_id=image)
    assert calls[0]["image_id"] == pending["image_id"] == image
    assert pending["pendiente_hitl"] and pending["approved"] is None and not pending["done"]
    result = pending["specialist_results"]["documental"]
    assert result.status == status and result.data == envelope(calls[0], **patch)
    assert result.evidence[0].source == "test://normativa"
    outputs[0]["documental"]["fuentes"].clear()
    pending["image_id"] = "alterada-por-cliente"
    assert agent.consultar_estado(first)["image_id"] == image
    other = agent.procesar_turno("[DOBLE] Otro hilo", second,
                                image_id="output/imagenes/otro.jpg")
    assert other["image_id"] != image
    assert agent.consultar_estado(first)["image_id"] == image
    assert calls[-1]["image_id"] == other["image_id"]
    final = agent.resolver_plan(first, decision, plan_id=pending["plan_id"])
    assert final["done"] is decision and len(calls) == 2
    next_order = agent.procesar_turno("[DOBLE] Sin imagen", first)
    assert next_order["image_id"] is None and calls[-1]["image_id"] is None
    assert agent.consultar_estado(second)["image_id"] == other["image_id"]


def test_adapter_precedence_and_revalidation(image_root):
    calls = []
    def invoke(request):
        calls.append(deepcopy(request))
        return {"documental": envelope(request)}
    node = crear_adaptador_documental(ejecutar_documental=invoke, image_id="imagen_demo")
    state = initial_state("[DOBLE] Consulta", image_id="output/imagenes/doble.png")
    before = deepcopy(state)
    node(state)
    assert state == before and calls[-1]["image_id"].endswith("doble.png")
    node(initial_state("[DOBLE] Sin imagen"))
    assert calls[-1]["image_id"] is None
    node({"user_message": "[DOBLE] Estado antiguo"})
    assert calls[-1]["image_id"].endswith("imagen_demo.jpg")
    with pytest.raises(ValueError, match="IMAGE_PATH_FORBIDDEN"):
        node(initial_state("[DOBLE] Consulta", image_id="personal.png"))
    (image_root / "output" / "imagenes" / "doble.png").unlink()
    with pytest.raises(ValueError, match="IMAGE_NOT_FOUND"):
        node(state)
    assert len(calls) == 3


@pytest.mark.parametrize("role", ["documental", "instalaciones", "sintetizar", "aplicar"])
def test_nodes_cannot_write_image_id(role):
    state = initial_state("[DOBLE] Consulta", image_id="imagen-original")
    state.update(final_answer="[DOBLE] Respuesta", plan=["Revisar"],
                 approved=True if role == "aplicar" else None)
    before = deepcopy(state)
    def spoof(s):
        return {"image_id": "imagen-ajena"}
    with pytest.raises(ValueError, match="CONTRACT"):
        if role in {"documental", "instalaciones"}:
            especialista_protegido(state, rol=role, node=spoof)
        elif role == "sintetizar":
            sintetizar_node(state, node=spoof)
        else:
            aplicar_node(state, node=spoof)
    assert state == before
    def mutate_image(s):
        s["image_id"] = "imagen-ajena"
        if role == "sintetizar":
            return {"final_answer": s["final_answer"], "plan": s["plan"]}
        return {"done": True} if role == "aplicar" else {}
    if role in {"documental", "instalaciones"}:
        especialista_protegido(state, rol=role, node=mutate_image)
    elif role == "sintetizar":
        sintetizar_node(state, node=mutate_image)
    else:
        aplicar_node(state, node=mutate_image)
    assert state == before
    def mutate(s):
        s["image_id"] = "imagen-ajena"
        return {}
    supervisor_node(state, route_provider=mutate)
    assert state == before


def test_construction_does_not_inspect_image_or_execute_callable(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Sin efectos durante construcción")
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "is_file", forbidden)
    node = crear_adaptador_documental(ejecutar_documental=forbidden, image_id="no-existe.png")
    assert isinstance(service(documental_node=node), AgentService)


def test_image_requires_nonempty_text_before_execution(image_root):
    agent = service(documental_node=lambda state: pytest.fail("No ejecutar"))
    for message in ("", "   "):
        with pytest.raises(ValueError, match="mensaje"):
            agent.procesar_turno(message, "hilo", image_id="imagen_demo")
