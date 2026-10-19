"""Presentación de rutas, llamadas de tools y estado del grafo.

Mostrar thread_id, request_id, fase HITL, done, presupuestos y trazas acotadas.
No mostrar claves ni contenido sensible completo. Distinguir datos simulados,
fallback y ejecución real. No contiene lógica de ejecución.
"""

from __future__ import annotations
import streamlit as st


def render_debug(estado: dict, thread_id: str) -> None: 
    with st.expander("Debug — estado del agente"):
        st.markdown(f"**thread_id:** `{thread_id}`")
        st.markdown(f"**done:** `{estado.get('done')}`")
        st.markdown(f"**pendiente_hitl:** `{estado.get('pendiente_hitl')}`")
        st.markdown(f"**iterations:** `{estado.get('iterations')}`")

        trace = estado.get("debug_trace", [])
        if trace:
            st.markdown("**Traza:**")
            for evento in trace:
                st.markdown(f"- {evento}")

        results = estado.get("specialist_results", {})
        if results:
            st.markdown("**Resultados especialistas:**")
            for key, val in results.items():
                st.markdown(f"- **{key}:** {val}")