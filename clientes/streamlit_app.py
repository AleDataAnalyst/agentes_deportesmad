"""Cliente Streamlit: chat, imagen, plan, fuentes y controles HITL.

Conservar servicio y thread_id durante reruns, sin compartir sesiones personales
mediante una caché global. Nueva conversación cambia thread_id.
Mostrar Aprobar/Rechazar solo con plan pendiente y bloquear pedidos incompatibles.
Consumir agent.py; no implementar nodos, herramientas ni decisiones del grafo aquí.
"""

# Presentación basada en David: origin/feature/streamlit-ui@c6052b3.
# Se conserva sidebar, historial de chat, HITL y debug. La simulación de hilo
# y los toast se sustituyen por la API común, sin lógica del grafo en la UI.
import streamlit as st

from agentes.runtime import aviso_modo, crear_servicio
from clientes.debug import render_debug
from clientes.hitl import render_hitl


def _init_session(modo):
    """Cada sesión conserva una instancia; nunca se usa cache_resource global."""
    if "service" not in st.session_state:
        service = crear_servicio(modo=modo)
        st.session_state.service = service
        st.session_state.thread_id = service.nueva_conversacion()
        st.session_state.messages = []
        st.session_state.estado = None
        st.session_state.modo = modo


def _resolver(aprobado):
    try:
        estado = st.session_state.estado
        st.session_state.estado = st.session_state.service.resolver_plan(
            st.session_state.thread_id, aprobado, plan_id=estado["plan_id"])
        st.session_state.messages.append({
            "role": "assistant", "content": st.session_state.estado["final_answer"]})
    except Exception as exc:
        st.error(f"Error al resolver el plan: {exc}")
        return
    st.rerun()


def render():
    st.title("🏟️ Asistente Deporte Municipal Madrid")
    st.caption("Consulta sobre instalaciones, tarifas, reservas y normativa deportiva.")
    # El modo se elige una vez; cambiarlo exige una sesión nueva para no perder
    # un checkpoint pendiente ni mezclar mensajes reales y simulados.
    # Demo explícita mediante ?modo=demo; por defecto se usa el servicio real.
    modo = st.session_state.get("modo") or st.query_params.get("modo", "real")
    try:
        st.info(aviso_modo(modo))
        _init_session(modo)
    except Exception as exc:
        st.error(f"Error al iniciar el servicio: {exc}")
        return

    with st.sidebar:
        st.header("Conversación")
        st.caption(f"**thread_id:** `{st.session_state.thread_id}`")
        if st.button("Nueva conversación", use_container_width=True):
            st.session_state.thread_id = st.session_state.service.nueva_conversacion()
            st.session_state.messages = []
            st.session_state.estado = None
            st.rerun()
        st.divider()
        if st.session_state.estado and st.session_state.estado.get("pendiente_hitl"):
            render_hitl(st.session_state.estado,
                        on_aprobar=lambda: _resolver(True),
                        on_rechazar=lambda: _resolver(False))

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    estado = st.session_state.estado
    pending = bool(estado and estado.get("pendiente_hitl"))
    if prompt := st.chat_input("Escribe tu consulta...", disabled=pending):
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            estado = st.session_state.service.procesar_turno(
                prompt, st.session_state.thread_id)
            st.session_state.estado = estado
            # La síntesis presenta respuesta, fuentes y restricciones. No se
            # fabrica texto si un nodo lanza una excepción.
            st.session_state.messages.append({
                "role": "assistant", "content": estado["final_answer"]})
        except Exception as exc:
            st.error(f"Error al procesar la consulta: {exc}")
        else:
            st.rerun()
    if st.session_state.estado:
        render_debug(st.session_state.estado, st.session_state.thread_id)
