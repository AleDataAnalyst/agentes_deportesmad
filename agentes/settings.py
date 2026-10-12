"""Configuración central del agente, independiente de la del RAG.

Definir proveedor y modelo, claves desde variables de entorno, rutas del
proyecto, RAG_CALLABLE y límites MAX_STEPS, MAX_ITER, MAX_TURNS y timeout HTTP.
Resolver rutas sin depender del directorio desde el que se ejecute el programa.
No almacenar claves en código ni mostrarlas en las trazas.
Consumidores: modelo, registro de tools, grafo y servicio del agente.
"""
