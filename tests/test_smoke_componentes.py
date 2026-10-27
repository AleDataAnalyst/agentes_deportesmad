"""
Test de humo: LLM, RAG y vision.

- LLM: llamada mínima a Gemini; requiere GOOGLE_API_KEY.
- RAG: consulta real al pipeline; valida el contrato.
- Vision: no llama a la API y usa una imagen temporal real.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agentes.tools.rag import rag_preguntar
from agentes.tools.vision import imagen_preguntar


REQUIERE_GOOGLE_API_KEY = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY no está definida",
)


# PNG válido de 1x1 pixel, generado en memoria.
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c626001000000ffff030000060005"
    "57bfabd40000000049454e44ae426082"
)


@pytest.mark.integration
@REQUIERE_GOOGLE_API_KEY
def test_llm_responde_texto():
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    respuesta = client.models.generate_content(
        model="gemini-3.6-flash",
        contents="Responde únicamente con la palabra: OK",
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=512,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    texto = (respuesta.text or "").strip()

    if not texto:
        candidatos = respuesta.candidates or []
        detalle = [
            {
                "finish_reason": str(getattr(c, "finish_reason", None)),
                "parts": [
                    str(getattr(p, "text", ""))
                    for p in (getattr(c.content, "parts", None) or [])
                ],
            }
            for c in candidatos
        ]
        pytest.fail(
            "El LLM no devolvió texto. Respuesta cruda:\n"
            f"{detalle}"
        )

    assert "OK" in texto.upper()


@pytest.mark.integration
def test_rag_devuelve_contrato():
    resultado = rag_preguntar("¿Cuál es el horario del polideportivo?")

    assert isinstance(resultado, dict)

    for clave in ("respuesta", "fuentes", "abstained", "error"):
        assert clave in resultado, f"Falta la clave '{clave}' en el contrato RAG"

    assert isinstance(resultado["respuesta"], str)
    assert isinstance(resultado["fuentes"], list)
    assert isinstance(resultado["abstained"], bool)

    if resultado["error"] is not None:
        pytest.fail(f"El RAG devolvió un error: {resultado['error']}")

    assert resultado["abstained"] or resultado["respuesta"].strip()


def test_vision_no_incordia_y_mantiene_contrato(monkeypatch, tmp_path):
    """
    Sin API, visión informa de su indisponibilidad sin simular éxito.
    """
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    imagen = tmp_path / "test_imagen.png"
    imagen.write_bytes(PNG_1X1)

    resultado = imagen_preguntar.invoke(
        {
            "image_id": str(imagen),
            "pregunta": "¿Qué aparece en la imagen?",
        }
    )

    print("\nVISION RESULT:", resultado)

    assert isinstance(resultado, dict)

    for clave in ("ok", "resultado", "fuentes", "abstained", "error"):
        assert clave in resultado, f"Falta la clave '{clave}' en el contrato vision"

    assert isinstance(resultado["ok"], bool)
    assert isinstance(resultado["resultado"], str)
    assert isinstance(resultado["fuentes"], list)
    assert isinstance(resultado["abstained"], bool)

    assert "GOOGLE_API_KEY" in resultado["error"]
    assert resultado["ok"] is False
    assert resultado["abstained"] is True
    assert resultado["resultado"] == ""
