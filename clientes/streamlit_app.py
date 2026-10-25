"""Cliente Streamlit: chat, imagen, plan, fuentes y controles HITL.

Conservar servicio y thread_id durante reruns, sin compartir sesiones personales
mediante una caché global. Nueva conversación cambia thread_id.
Mostrar Aprobar/Rechazar solo con plan pendiente y bloquear pedidos incompatibles.
Consumir agent.py; no implementar nodos, herramientas ni decisiones del grafo aquí.
Las entradas se validan con agentes.validation y lo mostrado pasa por
agentes.secret_filter, igual que en la CLI.
"""

from __future__ import annotations

import streamlit as st

from agentes.runtime import crear_servicio
from agentes.secret_filter import sin_secretos
from agentes.validation import (
    MAX_ENTRADA,
    validar_decision,
    validar_estado,
    validar_id,
    validar_mensaje,
)
from clientes.hitl import mensaje_recuperacion, render_hitl
from clientes.debug import fuentes_de_estado, render_debug


def _error(prefijo: str, exc: BaseException) -> None:
    """Muestra un error sin exponer secretos."""
    st.error(f"{prefijo}: {sin_secretos(str(exc))}")


def _mostrar_fuentes(fuentes: list[str] | None) -> None:
    if fuentes:
        st.text("Fuentes:\n" + "\n".join(f"• {f}" for f in fuentes))


def _error_y_recuperar(prefijo: str, exc: BaseException) -> None:
    """Guarda el error y relanza: al volver se comprueba el estado real del hilo."""
    st.session_state.estado_desconocido = True
    st.session_state.error_pendiente = f"{prefijo}: {sin_secretos(str(exc))}"
    st.rerun()


def _recuperar_estado(service, thread_id: str) -> None:
    """Tras un error, relee el checkpoint antes de permitir nada más."""
    error = st.session_state.pop("error_pendiente", None)
    if error:
        st.error(error)
    try:
        estado = service.consultar_estado(thread_id)
        validar_estado(estado, thread_id)
    except Exception as exc:  # noqa: BLE001
        _error("No se pudo comprobar el estado", exc)
        return
    st.session_state.estado = estado
    st.session_state.estado_desconocido = False
    nivel, texto = mensaje_recuperacion(estado)
    getattr(st, nivel)(texto)


def _texto_aprobacion(anterior: str, final: str) -> str:
    """Devuelve solo lo que el cierre añade a la respuesta ya mostrada.

    El backend garantiza que final_answer conserva íntegra la respuesta
    revisada y solo añade texto al final.
    """
    if anterior and final.startswith(anterior):
        extra = final[len(anterior):].strip()
        return extra or "Plan aprobado."
    return final or "Plan aprobado."


def _nuevo_thread_id(service) -> str:
    thread_id = service.nueva_conversacion()
    validar_id(thread_id)
    return thread_id


def _init_session():
    if "service" not in st.session_state:
        st.session_state.service = crear_servicio(modo="real")
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = _nuevo_thread_id(st.session_state.service)
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "estado" not in st.session_state:
        st.session_state.estado = None
    if "estado_desconocido" not in st.session_state:
        st.session_state.estado_desconocido = False


def render():
    try:
        _init_session()
    except Exception as exc: 
        _error("No se pudo iniciar el servicio", exc)
        st.stop()

    service = st.session_state.service
    thread_id = st.session_state.thread_id
    if st.session_state.estado_desconocido:
        _recuperar_estado(service, thread_id)
    estado = st.session_state.estado

    # Sidebar
    with st.sidebar:
        st.header("Conversación")
        st.caption(f"**thread_id:** `{thread_id}`")

        if st.button("Nueva conversación", use_container_width=True):
            try:
                nuevo_id = _nuevo_thread_id(service)
            except Exception as exc:  # noqa: BLE001
                _error("No se pudo crear la conversación", exc)
            else:
                st.session_state.messages = []
                st.session_state.estado = None
                st.session_state.estado_desconocido = False
                st.session_state.thread_id = nuevo_id
                st.rerun()

        st.divider()

        # Controles HITL
        if estado and estado.get("pendiente_hitl"):

            def _resolver(aprobado: bool) -> None:
                accion = "aprobar" if aprobado else "rechazar"
                try:
                    validar_decision(aprobado)
                    validar_id(thread_id)
                    validar_id(estado.get("plan_id"))
                    resultado = service.resolver_plan(
                        thread_id, aprobado=aprobado, plan_id=estado["plan_id"]
                    )
                    validar_estado(resultado, thread_id)
                    st.session_state.estado = resultado

                    if aprobado:
                        texto = _texto_aprobacion(
                            estado.get("final_answer") or "",
                            resultado.get("final_answer") or "",
                        )
                    else:
                        texto = "Plan rechazado. Puedes enviar un nuevo mensaje."
                    st.session_state.messages.append(
                        {"role": "assistant", "content": texto}
                    )
                    st.rerun()
                except Exception as exc:
                    _error_y_recuperar(f"Error al {accion}", exc)

            def on_aprobar():
                _resolver(True)

            def on_rechazar():
                _resolver(False)

            render_hitl(estado=estado, on_aprobar=on_aprobar, on_rechazar=on_rechazar)

    # Título
    st.title("🏟️ Asistente Deporte Municipal Madrid")
    st.caption("Consulta sobre instalaciones, tarifas, reservas y normativa deportiva.")

    # Historial
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(sin_secretos(msg["content"]))
            _mostrar_fuentes(msg.get("fuentes"))

    # Chat input
    if st.session_state.estado_desconocido:
        st.warning("No se pudo confirmar el estado de la conversación. Reintenta o empieza una nueva.")
        st.button("Reintentar comprobación")
    elif estado and estado.get("ejecucion_incompleta"):
        st.warning("Ejecución incompleta: empieza una nueva conversación para continuar.")
    elif not (estado and estado.get("pendiente_hitl")):
        if prompt := st.chat_input("Escribe tu consulta...", max_chars=MAX_ENTRADA):
            try:
                validar_mensaje(prompt)
            except ValueError as exc:
                st.warning(sin_secretos(str(exc)))
            else:
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(sin_secretos(prompt))

                with st.spinner("Procesando..."):
                    try:
                        resultado = service.procesar_turno(prompt, thread_id)
                        validar_estado(resultado, thread_id)
                        st.session_state.estado = resultado

                        respuesta = resultado.get("final_answer") or ""
                        fuentes = fuentes_de_estado(resultado)
                        with st.chat_message("assistant"):
                            st.markdown(sin_secretos(respuesta))
                            _mostrar_fuentes(fuentes)
                            if resultado.get("pendiente_hitl"):
                                st.info("Plan pendiente de aprobación — revisa el sidebar.")

                        st.session_state.messages.append(
                            {"role": "assistant", "content": respuesta, "fuentes": fuentes}
                        )
                        st.rerun()

                    except Exception as exc:
                        _error_y_recuperar("Error", exc)
    else:
        st.info("Aprueba o rechaza el plan en el sidebar para continuar.")

    # Debug
    if st.session_state.estado:
        render_debug(estado=st.session_state.estado, thread_id=thread_id)