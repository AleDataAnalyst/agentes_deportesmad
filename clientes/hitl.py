"""Componentes de aprobación, rechazo y nueva conversación.

Entradas: ClientResult y callbacks de la API común.
Enviar decision, thread_id y plan_id vigente; no modificar done desde la UI.
Mostrar decisión aplicada o error recuperable. No reanudar con identificadores viejos.
"""
from __future__ import annotations
import streamlit as st

from agentes.secret_filter import sin_secretos


def render_hitl(estado: dict, on_aprobar, on_rechazar) -> None:
    """Muestra el plan pendiente y los botones de aprobación/rechazo."""
    plan = estado.get("plan", [])

    st.subheader("Plan pendiente de aprobación")
    if plan:
        for item in plan:
            st.markdown(f"- {sin_secretos(item)}")
    else:
        st.caption("Sin plan disponible.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Aprobar", use_container_width=True):
            on_aprobar()
    with col2:
        if st.button("❌ Rechazar", use_container_width=True):
            on_rechazar()