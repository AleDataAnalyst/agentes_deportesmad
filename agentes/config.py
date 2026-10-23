from dataclasses import dataclass
from os import environ
import os

GEN_PROVIDER = os.getenv("GEN_PROVIDER", "ollama").lower()
GEN_MODEL = os.getenv(
    "GOOGLE_GEN_MODEL" if GEN_PROVIDER == "google" else "OLLAMA_GEN_MODEL",
    "",
)
MAX_STEPS = int(os.getenv("MAX_STEPS", "4"))
GEN_TEMPERATURE = float(os.getenv("GEN_TEMPERATURE", "0"))
GEN_TIMEOUT = int(os.getenv("GEN_TIMEOUT", "240"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "4"))
MAX_ITER_DEFAULT = 10

@dataclass(frozen=True)
class AgentSettings:
    max_iter: int = MAX_ITER_DEFAULT

    def __post_init__(self) -> None:
        if type(self.max_iter) is not int or self.max_iter < 1:
            raise ValueError("MAX_ITER debe ser un entero positivo")

def load_settings() -> AgentSettings:
    raw = environ.get("MAX_ITER", "").strip()
    if not raw:
        return AgentSettings()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("MAX_ITER debe ser un entero positivo") from exc
    return AgentSettings(max_iter=value)

