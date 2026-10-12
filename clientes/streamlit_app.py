"""Cliente Streamlit: chat, imagen, plan, fuentes y controles HITL.

Conservar servicio y thread_id durante reruns, sin compartir sesiones personales
mediante una caché global. Nueva conversación cambia thread_id.
Mostrar Aprobar/Rechazar solo con plan pendiente y bloquear pedidos incompatibles.
Consumir agent.py; no implementar nodos, herramientas ni decisiones del grafo aquí.
"""
