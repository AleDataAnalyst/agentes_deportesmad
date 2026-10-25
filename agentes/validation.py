"""Validaciones puras de entrada y del contrato recibido por los clientes.

No sustituyen las guardias de autoridad de AgentService ni del grafo.
"""

import unicodedata

MAX_ENTRADA = 8000


def validar_entrada(texto: str) -> None:
    """Valida una línea de interfaz; permite vacío para ignorarlo en la terminal."""
    if not isinstance(texto, str):
        raise ValueError("La entrada debe ser texto.")
    if len(texto) > MAX_ENTRADA:
        raise ValueError(f"Entrada demasiado larga: máximo {MAX_ENTRADA} caracteres; no se ha enviado.")
    if any(unicodedata.category(c) in ("Cc", "Cf") for c in texto):
        raise ValueError("Entrada con caracteres de control o formato invisible; no se ha enviado.")


def validar_mensaje(texto: str) -> None:
    """Valida una consulta antes de enviarla, sin recortarla ni transformarla."""
    validar_entrada(texto)
    if not texto.strip():
        raise ValueError("El mensaje no puede estar vacío.")


def validar_decision(aprobado: bool) -> None:
    """Exige una decisión booleana explícita; 0, 1 y cadenas no son decisiones."""
    if type(aprobado) is not bool:
        raise TypeError("aprobado debe ser True o False")


def validar_id(valor: object) -> None:
    if (not isinstance(valor, str) or not valor.strip() or len(valor) > 256
            or any(c.isspace() or unicodedata.category(c) in ("Cc", "Cf") for c in valor)):
        raise ValueError("Identificador inválido devuelto por el servicio.")


def validar_estado(estado: dict, hilo: str) -> dict:
    """Falla antes de sustituir el estado conocido o mostrar un plan de otro hilo."""
    if not isinstance(estado, dict) or estado.get("thread_id") != hilo:
        raise ValueError("Estado incompatible con la conversación actual.")
    if type(estado.get("pendiente_hitl")) is not bool:
        raise ValueError("Estado HITL inválido: se requiere un booleano.")
    if "ejecucion_incompleta" in estado and type(estado["ejecucion_incompleta"]) is not bool:
        raise ValueError("Estado de ejecución inválido: se requiere un booleano.")
    if estado.get("approved") is not None:
        validar_decision(estado["approved"])
    if estado["pendiente_hitl"]:
        validar_id(estado.get("plan_id"))
        plan = estado.get("plan")
        if (not isinstance(plan, list) or not plan
                or any(not isinstance(p, str) or not p.strip() for p in plan)):
            raise ValueError("Plan pendiente inválido; no se permite decidir.")
    return estado


