"""Especialista de instalaciones y organización deportiva.

Entradas: pedido, filtros documentados, candidatos o restricciones horarias
aportados y presupuesto de herramientas.
Salidas: resultados del catálogo, comparación o conflictos, procedencia,
limitaciones y trazas del request_id actual.
Tools previstas: buscar_instalaciones, comparar, detectar_conflictos y hora_actual.
No inferir plazas disponibles del catálogo ni inventar trayectos o citas.
No prescribe tratamiento ni ejercicio clínico; puede organizar citas ya elegidas.
"""

from copy import deepcopy

from agentes.contracts import ToolResult
from agentes.state import AgentState


def instalaciones_no_disponibles(state: AgentState) -> dict:
    """Declara la capacidad pendiente sin fabricar catálogo, centro ni avisos.

    La rama de Miguel implementa _consultar_catalogo_ckan, privada, pero no
    publica aún una operación consumible ni un nodo. No se llama a un detalle
    interno ni se copia su parser. Sustituir esta declaración cuando publique
    el contrato ejecutable. No es un doble ni un fallback de datos.
    """
    limitation = (
        "Instalaciones no disponibles: falta una operación pública ejecutable "
        "del especialista. Catálogo, avisos y comparación no están conectados."
    )
    result = ToolResult(
        status="abstained", answer=limitation,
        data={"available": False, "limitaciones": [limitation]},
    )
    return {
        "specialist_results": {
            **deepcopy(state.get("specialist_results", {})), "instalaciones": result,
        },
        "debug_trace": ["instalaciones: no disponible"],
    }
