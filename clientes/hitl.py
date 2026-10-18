"""Componentes de aprobación, rechazo y nueva conversación.

Entradas: ClientResult y callbacks de la API común.
Enviar decision, thread_id y plan_id vigente; no modificar done desde la UI.
Mostrar decisión aplicada o error recuperable. No reanudar con identificadores viejos.
"""

# Diseño de David, origin/feature/streamlit-ui@c6052b3; callbacks del servicio.
import streamlit as st


def render_hitl(estado: dict, on_aprobar, on_rechazar) -> None:
    st.subheader("Plan pendiente de aprobación")
    for item in estado.get("plan", []):
        st.markdown(f"- {item}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Aprobar", use_container_width=True):
            on_aprobar()
    with col2:
        if st.button("❌ Rechazar", use_container_width=True):
            on_rechazar()
