"""Construcción del grafo LangGraph y coordinación asíncrona.

Nodos previstos: supervisor, documental, instalaciones, sintetizar y aplicar;
añadir un coordinador de especialistas para fan-out/fan-in cuando corresponda.
Usar checkpointer MemorySaver y thread_id; pausar antes de aplicar.
Para especialistas independientes, coordinar con asyncio.gather y combinar
actualizaciones una sola vez. Las llamadas dependientes dentro de cada rol
mantienen su orden. No compartir estado mutable entre ramas.
Entradas: modelo, registro de herramientas y configuración inyectados.
Salida prevista: grafo compilado, usado mediante ainvoke por AgentService.
MemorySaver mantiene memoria del proceso; no promete recuperación tras reinicio.
"""
