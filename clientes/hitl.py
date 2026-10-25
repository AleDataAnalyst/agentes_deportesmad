"""Componentes de aprobación, rechazo y nueva conversación.

Entradas: ClientResult y callbacks de la API común.
Enviar decision, thread_id y plan_id vigente; no modificar done desde la UI.
Mostrar decisión aplicada o error recuperable. No reanudar con identificadores viejos.
"""
from __future__ import annotations
import streamlit as st

from agentes.secret_filter import sin_secretos


def mensaje_recuperacion(estado: dict) -> tuple[str, str]:
    """Nivel y texto para avisar del estado real del hilo tras un error."""
    if estado.get("pendiente_hitl"):
        return "info", "El error ocurrió con un plan ya generado: revísalo en la barra lateral y apruébalo o recházalo."
    if estado.get("ejecucion_incompleta"):
        return "warning", "La ejecución quedó incompleta: empieza una nueva conversación para continuar."
    return "success", "Estado comprobado: no hay ningún plan pendiente. Puedes continuar."


def render_hitl(estado: dict, on_aprobar, on_rechazar, bloqueado: bool = False) -> None:
    """Muestra el plan pendiente y los botones de aprobación/rechazo.

    Con el estado sin confirmar (tras un error) no se enseña el plan anterior
    ni se puede decidir hasta recuperarlo.
    """
    st.subheader("Plan pendiente de aprobación")
    if bloqueado:
        st.warning("Estado sin confirmar: no se puede aprobar ni rechazar hasta comprobarlo.")
        return

    plan = estado.get("plan", [])
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