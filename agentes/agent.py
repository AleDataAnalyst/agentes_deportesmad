"""API síncrona común para clientes y ciclo de vida del pedido.

Crear un AgentService con nodos inyectados y conservarlo entre turnos. El grafo
y los identificadores de plan pertenecen a esa instancia. MemorySaver y los
registros del servicio son locales al proceso; no prometen recuperación tras
reinicios. La integración de imágenes queda pendiente de su contrato.
"""

from threading import RLock
from typing import Any
from uuid import uuid4

from agentes.graph import Node, build_graph
from agentes.nodes.supervisor import RouteProvider
from agentes.settings import AgentSettings, load_settings
from agentes.state import initial_state, state_from_graph
from agentes.validation import validar_decision


class AgentService:
    """Un grafo compartido; serializa las operaciones de cada conversación.

    Los errores de validación e integración se propagan al cliente, que puede
    presentarlos sin fabricar respuestas. No contiene widgets ni llamadas LLM.
    """

    def __init__(
        self,
        *,
        documental_node: Node,
        instalaciones_node: Node,
        sintetizar_node: Node,
        aplicar_node: Node,
        vision_node: Node | None = None,
        route_provider: RouteProvider | None = None,
        settings: AgentSettings | None = None,
        checkpointer=None,
    ):
        self.settings = settings if settings is not None else load_settings()

        self._graph = build_graph(
            documental_node=documental_node,
            instalaciones_node=instalaciones_node,
            sintetizar_node=sintetizar_node,
            aplicar_node=aplicar_node,
            vision_node=vision_node,
            route_provider=route_provider,
            max_iter=self.settings.max_iter,
            checkpointer=checkpointer,
        )
        self._registry_lock = RLock()
        self._thread_locks: dict[str, RLock] = {}
        self._plan_ids: dict[str, str] = {}
        self._resolved: dict[str, tuple[str, bool]] = {}

    @staticmethod
    def _validate_thread(thread_id: str) -> None:
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError("thread_id debe ser un texto no vacío")

    def _lock(self, thread_id: str):
        self._validate_thread(thread_id)
        with self._registry_lock:
            return self._thread_locks.setdefault(thread_id, RLock())

    def _config(self, thread_id: str) -> dict[str, Any]:
        # Cada vuelta usa supervisor + rol. Reserva pasos para síntesis y cierre.
        return {"configurable": {"thread_id": thread_id},
                "recursion_limit": 2 * self.settings.max_iter + 6}

    def nueva_conversacion(self) -> str:
        """Devuelve un hilo nuevo; conserva los checkpoints de los anteriores."""
        return f"deportes-{uuid4().hex}"

    def _state(self, thread_id: str) -> dict[str, Any]:
        snapshot = self._graph.get_state(self._config(thread_id))
        state = state_from_graph(snapshot.values, initial_state("", thread_id))
        pending = "aplicar" in (snapshot.next or ())
        state["pendiente_hitl"] = pending
        # Diagnóstico de lectura, derivado del checkpoint; no reanuda ni borra trabajo.
        state["ejecucion_incompleta"] = bool(snapshot.next) and not pending
        state["plan_id"] = self._plan_ids.get(thread_id)
        if pending:
            state["done"] = False
        return state

    def consultar_estado(self, thread_id: str) -> dict[str, Any]:
        """Lee el checkpoint y devuelve una copia independiente para el cliente."""
        with self._lock(thread_id):
            return self._state(thread_id)

    def procesar_turno(self, mensaje: str, thread_id: str) -> dict[str, Any]:
        """Reinicia el pedido, ejecuta y devuelve el plan pendiente de decisión.

        Un mensaje vacío falla antes de tocar el checkpoint. Si un nodo falló
        y hay trabajo pendiente, usar otro hilo para un pedido nuevo; no borrar
        silenciosamente una ejecución incompleta.
        initial_state aporta solo una marca nueva a debug_trace. El acumulador
        conserva la traza de pedidos anteriores del mismo thread_id, que antes
        se sustituía por pedido; los datos operativos sí se reinician.
        """
        if not isinstance(mensaje, str):
            raise TypeError("mensaje debe ser un texto")
        if not mensaje.strip():
            raise ValueError("mensaje no puede estar vacío")
        with self._lock(thread_id):
            snapshot = self._graph.get_state(self._config(thread_id))
            if "aplicar" in (snapshot.next or ()):
                raise ValueError("HITL_PENDING: aprobar o rechazar el plan antes de otro mensaje")
            if snapshot.next:
                raise ValueError("REQUEST_INCOMPLETE: hay una ejecución pendiente en este hilo")
            self._plan_ids.pop(thread_id, None)
            self._resolved.pop(thread_id, None)
            self._graph.invoke(initial_state(mensaje.strip(), thread_id), self._config(thread_id))
            snapshot = self._graph.get_state(self._config(thread_id))
            if "aplicar" in (snapshot.next or ()):
                self._plan_ids[thread_id] = uuid4().hex
            return self._state(thread_id)

    def resolver_plan(
        self, thread_id: str, aprobado: bool, *, plan_id: str,
    ) -> dict[str, Any]:
        """Guarda la decisión humana y reanuda el mismo checkpoint.

        Una repetición idéntica devuelve el estado sin ejecutar aplicar otra
        vez. Una decisión diferente o un identificador antiguo se rechazan.
        """
        validar_decision(aprobado)
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise ValueError("plan_id debe ser un texto no vacío")
        with self._lock(thread_id):
            if self._plan_ids.get(thread_id) != plan_id:
                raise ValueError("PLAN_NOT_CURRENT: el plan no pertenece al pedido vigente")
            resolved = self._resolved.get(thread_id)
            if resolved is not None:
                if resolved != (plan_id, aprobado):
                    raise ValueError("PLAN_ALREADY_RESOLVED: no se puede cambiar la decisión aplicada")
                return self._state(thread_id)
            cfg = self._config(thread_id)
            if "aplicar" not in (self._graph.get_state(cfg).next or ()):
                raise ValueError("HITL_NOT_PENDING: no hay un plan pendiente de decisión")
            self._graph.update_state(cfg, {"approved": aprobado})
            self._graph.invoke(None, cfg)
            self._resolved[thread_id] = (plan_id, aprobado)
            return self._state(thread_id)
