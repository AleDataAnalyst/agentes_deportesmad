"""Utilidades deterministas, sin modelo, RAG ni consulta HTTP.

Tools previstas: hora_actual, comparar candidatos por criterios explícitos,
detectar conflictos con fechas ISO 8601 zonificadas y preparar reporte borrador.
Entradas y salidas siguen contratos de contracts.py. Validar duración, zona
horaria, límites y campos necesarios. Información desconocida se conserva como tal.
Preparar_reporte no envía nada; comparación no calcula rutas ni disponibilidad.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZONA_POR_DEFECTO = "Europe/Madrid"
_DIAS_SEMANA = (
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
)


def hora_actual(
    zona: str = ZONA_POR_DEFECTO,
    ahora: datetime | None = None,
) -> dict:
    """Devuelve la fecha y hora actuales en una zona horaria IANA.

    `ahora` solo sirve para los tests (inyectar una hora fija).
    Contrato de salida: ok, resultado, fuentes, abstained, error.
    """
    if not isinstance(zona, str) or not zona.strip():
        return _error("La zona horaria es obligatoria.")

    try:
        tz = ZoneInfo(zona.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return _error(f"Zona horaria no válida: {zona!r}.")

    momento = ahora.astimezone(tz) if ahora else datetime.now(tz)

    return {
        "ok": True,
        "resultado": {
            "iso": momento.isoformat(timespec="seconds"),
            "fecha": momento.date().isoformat(),
            "hora": momento.strftime("%H:%M"),
            "dia_semana": _DIAS_SEMANA[momento.weekday()],
            "zona": zona.strip(),
        },
        "fuentes": ["reloj_del_sistema"],
        "abstained": False,
        "error": None,
    }


def _error(mensaje: str) -> dict:
    return {
        "ok": False,
        "resultado": None,
        "fuentes": [],
        "abstained": False,
        "error": mensaje,
    }