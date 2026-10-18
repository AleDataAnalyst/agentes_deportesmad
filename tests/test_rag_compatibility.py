"""Regresiones acotadas sin índices, descargas ni modelos reales."""
import ast
from pathlib import Path

import pytest


def function_namespace(path, name, namespace):
    # Aísla funciones de infraestructura de las importaciones pesadas del RAG.
    # Estos dobles prueban compatibilidad, nunca calidad ni retrieval real.
    module = ast.parse(Path(path).read_text(encoding="utf-8"))
    function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), path, "exec"), namespace)
    return namespace[name]


def test_hf_constructor_uses_model_device_and_optional_token():
    calls = []

    class Vectors:
        def tolist(self):
            return [[1.0]]

    class Model:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def encode(self, texts, **kwargs):
            return Vectors()

    import time
    ns = dict(_HF_CACHE={}, HF_EMBED_MODEL="test/model", HF_DEVICE="cpu", HF_TOKEN="test-token",
              EMBED_BATCH_SIZE=1, SentenceTransformer=Model, time=time)
    embed = function_namespace("rag/embed.py", "_embed_huggingface", ns)
    assert embed(["ejemplo"]) == [[1.0]]
    embed(["segundo"])
    assert calls == [(("test/model",), {"device": "cpu", "token": "test-token"})]


def test_query_does_not_create_storage_or_collection(tmp_path):
    calls = []

    class Client:
        def get_collection(self, *, name):
            calls.append(name)
            raise LookupError("Colección ausente de prueba")

        def get_or_create_collection(self, **kwargs):
            pytest.fail("Consultar nunca debe crear una colección")

    def client(path):
        calls.append("open")
        return Client()

    read = function_namespace("rag/retrieve.py", "obtener_coleccion", {
        "Path": Path, "CHROMA_DIR": str(tmp_path), "COLLECTION_NAME": "test",
        "obtener_cliente_chroma": client,
    })
    with pytest.raises(FileNotFoundError, match="RAG_INDEX_MISSING"):
        read()
    assert calls == []
    (tmp_path / "chroma.sqlite3").touch()
    with pytest.raises(LookupError, match="Colección ausente"):
        read()
    assert calls == ["open", "test"]
