"""Estado de conversación, pedido y ejecución del grafo.

Campos previstos: thread_id, request_id, message, image_id, messages, results,
visited, iterations, next_node, trace, answer, plan, plan_id, sources,
limitations, decision, phase, done, error y modo de ejecución.
Documentar quién actualiza cada campo y si reemplaza, fusiona o acumula.
Cada pedido reinicia resultados, plan, decisión y contadores; conserva solo
historial conversacional acotado. Evitar evidencias de pedidos anteriores.
En el diseño concurrente, las ramas trabajan sobre copias y el coordinador
combina sus resultados; no introducir reducers sin definir su semántica.
"""
