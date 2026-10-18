"""Presentación de rutas, llamadas de tools y estado del grafo.

Mostrar thread_id, request_id, fase HITL, done, presupuestos y trazas acotadas.
No mostrar claves ni contenido sensible completo. Distinguir datos simulados,
fallback y ejecución real. No contiene lógica de ejecución.
"""

# Diseño de David, origin/feature/streamlit-ui@c6052b3; traza acotada.
import streamlit as st


def render_debug(estado: dict, thread_id: str) -> None:
    with st.expander("Debug — estado del agente"):
        for key, value in {"thread_id": thread_id,
                           "done": estado.get("done"),
                           "pendiente_hitl": estado.get("pendiente_hitl"),
                           "iterations": estado.get("iterations")}.items():
            st.markdown(f"**{key}:** `{value}`")
        for evento in estado.get("debug_trace", [])[-40:]:
            st.text(evento)
