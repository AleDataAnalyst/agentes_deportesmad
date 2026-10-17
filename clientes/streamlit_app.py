"""Cliente Streamlit: chat, imagen, plan, fuentes y controles HITL.

Conservar servicio y thread_id durante reruns, sin compartir sesiones personales
mediante una caché global. Nueva conversación cambia thread_id.
Mostrar Aprobar/Rechazar solo con plan pendiente y bloquear pedidos incompatibles.
Consumir agent.py; no implementar nodos, herramientas ni decisiones del grafo aquí.
"""
"""Cliente Streamlit del AgentService."""

from __future__ import annotations

import streamlit as st


def _init_session():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "estado" not in st.session_state:
        st.session_state.estado = None


def render():
    _init_session()

    estado = st.session_state.estado
    thread_id = st.session_state.thread_id
    
    # Sidebar
    with st.sidebar:
        st.header("Conversación")
        st.caption(f"**thread_id:** `{thread_id}`")
        if st.button("Nueva conversación", use_container_width=True):
            st.session_state.messages = []
            st.session_state.estado = None
            st.session_state.thread_id = "demo-simulado"  # Simulación de nuevo de thread_id; en producción, se generaría uno nuevo desde el backend.
            st.rerun()

        st.divider()

        # Controles HITL
        if estado and estado.get("pendiente_hitl"):
            render_hitl(
                estado=estado,
                on_aprobar=lambda: st.toast("Solicitud aprobada."),
                on_rechazar=lambda: st.toast("Solicitud rechazada.")) 

    # Título
    st.title("🏟️ Asistente Deporte Municipal Madrid")
    st.caption("Consulta sobre instalaciones, tarifas, reservas y normativa deportiva.")

    # Historial
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input (placeholder hasta conectar con AgentService)
    if prompt := st.chat_input("Escribe tu consulta..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
    #debug
    if estado:
        render_debug(estado=estado, thread_id=thread_id)