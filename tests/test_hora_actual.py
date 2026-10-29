from datetime import datetime, timezone

from agentes.tools.auxiliares import hora_actual

CLAVES = {"ok", "resultado", "fuentes", "abstained", "error"}


def test_hora_actual_con_hora_fija():
    fija = datetime(2026, 10, 27, 10, 30, tzinfo=timezone.utc)
    out = hora_actual("Europe/Madrid", ahora=fija)
    assert set(out) == CLAVES
    assert out["ok"] is True
    assert out["resultado"]["fecha"] == "2026-10-27"
    assert out["resultado"]["hora"] == "11:30"      # UTC+1 en octubre
    assert out["resultado"]["dia_semana"] == "martes"


def test_hora_actual_zona_invalida():
    out = hora_actual("Marte/Olimpo")
    assert out["ok"] is False
    assert "no válida" in out["error"]


def test_hora_actual_zona_vacia():
    assert hora_actual("")["ok"] is False