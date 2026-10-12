"""Componentes de aprobación, rechazo y nueva conversación.

Entradas: ClientResult y callbacks de la API común.
Enviar decision, thread_id y plan_id vigente; no modificar done desde la UI.
Mostrar decisión aplicada o error recuperable. No reanudar con identificadores viejos.
"""
