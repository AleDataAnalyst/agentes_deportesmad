"""Cliente Streamlit: chat, imagen, plan, fuentes y controles HITL.

Conservar servicio y thread_id durante reruns, sin compartir sesiones personales
mediante una caché global. Nueva conversación cambia thread_id.
Mostrar Aprobar/Rechazar solo con plan pendiente y bloquear pedidos incompatibles.
Consumir agent.py; no implementar nodos, herramientas ni decisiones del grafo aquí.
"""

from __future__ import annotations

import streamlit as st

from agentes.demo import crear_servicio_demo
from clientes.hitl import render_hitl
from clientes.debug import render_debug

def _init_session():
    if "service" not in st.session_state:
        st.session_state.service = crear_servicio_demo()
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = st.session_state.service.nueva_conversacion()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "estado" not in st.session_state:
        st.session_state.estado = None


def render():
    _init_session()

    service = st.session_state.service
    estado = st.session_state.estado
    thread_id = st.session_state.thread_id
    
    # Sidebar
    with st.sidebar:
        st.header("Conversación")
        st.caption(f"**thread_id:** `{thread_id}`")

        if st.button("Nueva conversación", use_container_width=True):
            st.session_state.messages = []
            st.session_state.estado = None
            st.session_state.thread_id = service.nueva_conversacion()
            st.rerun()

        st.divider()

        # Controles HITL
        if estado and estado.get("pendiente_hitl"):
            def on_aprobar():
                resultado = service.resolver_plan(
                    thread_id, aprobado=True, plan_id=estado["plan_id"]
                )
                st.session_state.estado = resultado
                if resultado.get("final_answer"):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": resultado["final_answer"],
                    })

            def on_rechazar():
                resultado = service.resolver_plan(
                    thread_id, aprobado=False, plan_id=estado["plan_id"]
                )
                st.session_state.estado = resultado
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Plan rechazado. Puedes enviar un nuevo mensaje.",
                })

            render_hitl(estado=estado, on_aprobar=on_aprobar, on_rechazar=on_rechazar)
    # Título
    st.title("🏟️ Asistente Deporte Municipal Madrid")
    st.caption("Consulta sobre instalaciones, tarifas, reservas y normativa deportiva.")

    # Historial
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if not (estado and estado.get("pendiente_hitl")):  # ← 4 espacios, correcto
        if prompt := st.chat_input("Escribe tu consulta..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Procesando..."):
                try:
                    resultado = service.procesar_turno(prompt, thread_id)
                    st.session_state.estado = resultado

                    respuesta = resultado.get("final_answer", "")
                    with st.chat_message("assistant"):
                        st.markdown(respuesta)
                        if resultado.get("pendiente_hitl"):
                            st.info("Plan pendiente de aprobación — revisa el sidebar.")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": respuesta,
                    })
                    st.rerun()

                except Exception as exc:
                    st.error(f"Error: {exc}")
    else:
        st.info("Aprueba o rechaza el plan en el sidebar para continuar.")

    #debug
    if estado:
        render_debug(estado=estado, thread_id=thread_id)