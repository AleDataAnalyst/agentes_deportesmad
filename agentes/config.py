from dataclasses import dataclass
from os import environ

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

