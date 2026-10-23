"""
rag/generate.py

Capa de generación: envía un prompt al LLM y devuelve la respuesta en texto.

Responsabilidad única:
    prompt -> LLM -> respuesta (str)

Este módulo NO recupera chunks (retrieve.py) ni construye el prompt
(prompts.py) ni orquesta el pipeline (logic.py).
"""

from __future__ import annotations

from google import genai
from google.genai import types

from .config import (
    GEN_MAX_TOKENS,
    GEN_MODEL,
    GEN_PROVIDER,
    GEN_TEMPERATURE,
    GEN_TIMEOUT,
    GOOGLE_API_KEY,
    HF_DEVICE,
    HF_TOKEN,
    OLLAMA_BASE_URL,
)

# Temperatura: si config.py no la define todavía, usamos 0.2 (apegado al contexto)
try:
    from .config import GEN_TEMPERATURE
except ImportError:
    GEN_TEMPERATURE = 0.1

import requests

import time

def _generar_google(prompt: str, max_intentos: int = 3) -> str:
    """Generación con Gemini vía SDK google-genai, con retry ante 503/429."""
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY no está definida en .env. "
            "Configúrala antes de generar respuestas."
        )
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    ultimo_error: Exception | None = None
    for intento in range(1, max_intentos + 1):
        try:
            response = client.models.generate_content(
                model=GEN_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=GEN_TEMPERATURE),
            )
            texto = (response.text or "").strip()
            if not texto:
                raise RuntimeError("Gemini devolvió una respuesta vacía.")
            return texto
        except Exception as e:
            ultimo_error = e
            mensaje = str(e)
            # Reintentar solo en errores transitorios
            es_transitorio = any(
                codigo in mensaje for codigo in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
            )
            if not es_transitorio or intento == max_intentos:
                raise
            espera = 2 ** intento  # 2s, 4s, 8s
            print(f"[RAG] [WARN] Error transitorio de Gemini ({intento}/{max_intentos}): reintentando en {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"Fallo tras {max_intentos} intentos: {ultimo_error}")

def _generar_ollama(prompt: str, max_intentos: int = 3) -> str:
    """Generación con Ollama local (offline): POST /api/chat, con retry."""
    ultimo_error: Exception | None = None
    for intento in range(1, max_intentos + 1):
        try:
            r = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEN_MODEL,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": GEN_TEMPERATURE},
                },
                timeout=GEN_TIMEOUT,
            )
            r.raise_for_status()
            texto = (r.json().get("message", {}).get("content") or "").strip()
            if not texto:
                raise RuntimeError("Ollama devolvió una respuesta vacía.")
            return texto
        except Exception as e:
            ultimo_error = e
            # Solo se reintenta si es transitorio (conexión/timeout/503/429).
            # Un NameError, ValueError o respuesta vacía NO es transitorio:
            # se levanta directamente, sin reintentos ni esperas.
            es_transitorio = isinstance(e, (requests.ConnectionError, requests.Timeout)) or any(
                codigo in str(e) for codigo in ("503", "429", "UNAVAILABLE")
            )
            if not es_transitorio or intento == max_intentos:
                raise
            espera = 4 ** intento
            print(f"[RAG] [WARN] Error transitorio de Ollama ({intento}/{max_intentos}): reintentando en {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"Fallo tras {max_intentos} intentos: {ultimo_error}")


# Caché: el pipeline de HF es caro de cargar; se reutiliza por modelo.
_HF_GEN_CACHE: dict[str, Any] = {}


def _generar_huggingface(prompt: str, max_intentos: int = 3) -> str:
    """Generación con HuggingFace (online): pipeline text-generation."""
    if GEN_MODEL not in _HF_GEN_CACHE:
        kwargs: dict[str, Any] = {
            "device": HF_DEVICE,
            "use_fast": True,
            "trust_remote_code": False,
        }
        if HF_TOKEN:  # solo para modelos gated
            kwargs["token"] = HF_TOKEN
        _HF_GEN_CACHE[GEN_MODEL] = pipeline("text-generation", model=GEN_MODEL, **kwargs)

    ultimo_error: Exception | None = None
    for intento in range(1, max_intentos + 1):
        try:
            out = _HF_GEN_CACHE[GEN_MODEL](
                prompt,
                max_new_tokens=GEN_MAX_TOKENS,
                do_sample=False,
                return_full_text=False,
            )
            texto = (out[0].get("generated_text") or "").strip()
            if not texto:
                raise RuntimeError("HuggingFace devolvió una respuesta vacía.")
            return texto
        except Exception as e:
            ultimo_error = e
            if intento == max_intentos:
                break
            time.sleep(2 ** intento)
    raise RuntimeError(f"Fallo tras {max_intentos} intentos: {ultimo_error}")


# Dispatch por proveedor: añadir uno nuevo = una función + una línea aquí
_PROVEEDORES = {
    "ollama": _generar_ollama,
    "huggingface": _generar_huggingface,
    "google": _generar_google,
}



def generar(prompt: str, provider: str | None = None) -> str:
    """
    Envía un prompt al LLM y devuelve la respuesta como texto plano.

    Args:
        prompt: prompt completo (instrucciones + contexto + pregunta).
        provider: override del proveedor. Por defecto, GEN_PROVIDER de config.

    Returns:
        Respuesta del LLM como string (nunca vacía; si lo fuera, lanza error).

    Raises:
        ValueError: si el proveedor no está soportado o el prompt está vacío.
        RuntimeError: si la API falla o devuelve respuesta vacía.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("El prompt no puede estar vacío.")

    proveedor = provider or GEN_PROVIDER
    fn = _PROVEEDORES.get(proveedor)
    if fn is None:
        raise ValueError(
            f"GEN_PROVIDER no soportado: {proveedor!r}. "
            f"Soportados: {list(_PROVEEDORES)}"
        )
    return fn(prompt.strip())