"""
rag/config.py

Todas las constantes del proyecto. Se leen de variables de entorno (.env)
con valores por defecto: se cambia de proveedor sin tocar el código.

Interruptores independientes:
- EMBED: embeddings (offline + consulta)
- GEN: generación (online)
- TAG: etiquetado (offline; por defecto hereda GEN)
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

MAX_ITER = int(os.getenv("MAX_ITER", "8"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "5"))
MAX_TURNS = int(os.getenv("MAX_TURNS", "20"))

RAG_INDEX_DIR = Path(os.getenv("RAG_INDEX_DIR", BASE_DIR / "data" / "index"))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", BASE_DIR / "assets"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Interruptor 1: embeddings ---
EMBED_PROVIDER: str = os.getenv("EMBED_PROVIDER", "ollama")

OLLAMA_EMBED_MODEL: str = os.getenv(
    "OLLAMA_EMBED_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
HF_EMBED_MODEL: str = os.getenv(
    "HF_EMBED_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
GOOGLE_EMBED_MODEL: str = os.getenv(
    "GOOGLE_EMBED_MODEL",
    "gemini-embedding-2",
)

# --- Interruptor 2: generación ---
GEN_PROVIDER: str = os.getenv("GEN_PROVIDER", "ollama")

OLLAMA_GEN_MODEL: str = os.getenv("OLLAMA_GEN_MODEL", "llama3.2")
HF_GEN_MODEL: str = os.getenv("HF_GEN_MODEL", "mistralai/Mistral-7B-v0.1")
GOOGLE_GEN_MODEL: str = os.getenv("GOOGLE_GEN_MODEL", "gemini-2.0-flash")

# --- Interruptor 3: tagging ---
TAG_PROVIDER: str = os.getenv("TAG_PROVIDER") or GEN_PROVIDER

OLLAMA_TAG_MODEL: str = os.getenv("OLLAMA_TAG_MODEL") or OLLAMA_GEN_MODEL
HF_TAG_MODEL: str = os.getenv("HF_TAG_MODEL") or HF_GEN_MODEL
GOOGLE_TAG_MODEL: str = os.getenv("GOOGLE_TAG_MODEL") or GOOGLE_GEN_MODEL


def _resolver(
    provider: str,
    ollama_model: str,
    hf_model: str,
    google_model: str,
    switch: str,
) -> str:
    """Devuelve el modelo efectivo de un interruptor según su proveedor."""
    modelo = {
        "ollama": ollama_model,
        "huggingface": hf_model,
        "google": google_model,
    }.get(provider)

    if modelo is None:
        raise ValueError(f"{switch} no soportado: {provider!r}")

    return modelo


EMBED_MODEL: str = _resolver(
    EMBED_PROVIDER,
    OLLAMA_EMBED_MODEL,
    HF_EMBED_MODEL,
    GOOGLE_EMBED_MODEL,
    "EMBED_PROVIDER",
)

GEN_MODEL: str = _resolver(
    GEN_PROVIDER,
    OLLAMA_GEN_MODEL,
    HF_GEN_MODEL,
    GOOGLE_GEN_MODEL,
    "GEN_PROVIDER",
)

TAG_MODEL: str = _resolver(
    TAG_PROVIDER,
    OLLAMA_TAG_MODEL,
    HF_TAG_MODEL,
    GOOGLE_TAG_MODEL,
    "TAG_PROVIDER",
)

# --- Recuperación ---
RETRIEVAL_MODE: str = os.getenv("RAG_RETRIEVAL_MODE", "hibrido")

# --- Ollama ---
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# --- HuggingFace ---
HF_DEVICE: str = os.getenv("HF_DEVICE", "cpu")
HF_TOKEN: str | None = os.getenv("HF_TOKEN") or None

# --- Google ---
GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY") or None

# --- Chunking ---
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))

# --- Checkpoint de embeddings ---
EMBED_CHECKPOINT_FILE: str = os.getenv(
    "EMBED_CHECKPOINT_FILE",
    str(BASE_DIR / "output" / "embeddings_checkpoint.jsonl"),
)

EMBED_CHECKPOINT_ENABLED: bool = os.getenv(
    "EMBED_CHECKPOINT_ENABLED", "true"
).lower() == "true"

EMBED_MAX_ATTEMPTS: int = int(os.getenv("EMBED_MAX_ATTEMPTS", "8"))
EMBED_RETRY_BASE_DELAY: float = float(os.getenv("EMBED_RETRY_BASE_DELAY", "5"))

# --- Retrieval ---
TOP_K: int = int(os.getenv("TOP_K", "5"))
MAX_CHUNKS: int = int(os.getenv("MAX_CHUNKS", "5"))

# --- Generación ---
GEN_TEMPERATURE: float = float(os.getenv("GEN_TEMPERATURE", "0.1"))
GEN_MAX_TOKENS: int = int(os.getenv("GEN_MAX_TOKENS", "1024"))

ABSTENTION_MESSAGE: str = os.getenv(
    "ABSTENTION_MESSAGE",
    "No dispongo de esa información en los documentos proporcionados.",
)

# --- Embeddings ---
EMBED_DIM: int = int(os.getenv("EMBED_DIM", "384"))
EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "30"))
EMBED_TIMEOUT: int = int(os.getenv("EMBED_TIMEOUT", "600"))
EXPORT_EMBEDDINGS: bool = os.getenv(
    "EXPORT_EMBEDDINGS", "true"
).lower() == "true"


def _dim_max(proveedor: str) -> int | None:
    """Lee EMBED_DIM_MAX_<PROVEEDOR> desde el entorno."""
    abrev = {
        "ollama": "OLLAMA",
        "huggingface": "HF",
        "google": "GOOGLE",
    }[proveedor]

    raw = (os.getenv(f"EMBED_DIM_MAX_{abrev}") or "").strip()
    return int(raw) if raw else None


EMBED_DIM_MAX_OLLAMA: int | None = _dim_max("ollama")
EMBED_DIM_MAX_HF: int | None = _dim_max("huggingface")
EMBED_DIM_MAX_GOOGLE: int | None = _dim_max("google")

# --- Tagging, scoring y dedup ---
TAG_SCORING_DEDUP: bool = os.getenv(
    "TAG_SCORING_DEDUP", "true"
).lower() == "true"

TAG_MAX_TOKENS: int = int(os.getenv("TAG_MAX_TOKENS", "1024"))

DEDUP_UMBRAL: float = float(os.getenv("DEDUP_UMBRAL", "0.93"))
DEDUP_AUDIT: bool = os.getenv("DEDUP_AUDIT", "true").lower() == "true"
DEDUP_AUDIT_RUTA: str = os.getenv(
    "DEDUP_AUDIT_RUTA", "output/dedup_audit.jsonl"
)

# --- Set de preguntas ---
QUESTION_SET: str = os.getenv("QUESTION_SET", "")
MAX_QUESTIONS: int = int(os.getenv("MAX_QUESTIONS", "1"))
QUESTION_SET_RUTA: str = os.getenv(
    "QUESTION_SET_RUTA", "output/question_set.json"
)
GEN_TIMEOUT: int = int(os.getenv("GEN_TIMEOUT", "140"))

# --- ChromaDB ---
CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./output/chroma_db")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "deporte_municipal")
COSINE_SPACE: str = "cosine"

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# --- Imágenes / OCR / multimodal ---
IMAGEN_DEFAULT_PATH = ASSETS_DIR / "imagen_demo.png"

IMAGE_OCR_ENABLED: bool = os.getenv(
    "IMAGE_OCR_ENABLED", "true"
).lower() == "true"

IMAGE_VISION_ENABLED: bool = os.getenv(
    "IMAGE_VISION_ENABLED", "false"
).lower() == "true"

IMAGE_OCR_LANG: str = os.getenv("IMAGE_OCR_LANG", "spa+eng")

# Modelo de visión independiente. Si no se declara, hereda GEN_MODEL.
IMAGE_VISION_MODEL: str = os.getenv("IMAGE_VISION_MODEL") or GEN_MODEL

IMAGE_MAX_DESCRIPTION_CHARS: int = int(
    os.getenv("IMAGE_MAX_DESCRIPTION_CHARS", "1200")
)