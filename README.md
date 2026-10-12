# PB02 · Estructura inicial de proyecto

Estructura de inicio sin implementación. Cada `.py` contiene únicamente un
docstring con responsabilidades, entradas/salidas y límites. No hay imports,
funciones, clases, llamadas, fixtures con datos ni pruebas desarrolladas.
Los nombres y contratos son propuestas para acordar antes de integrar.

## Mapa de módulos

| Carpeta / módulo | Responsabilidad |
|---|---|
| agentes/contracts.py y state.py | Contratos compartidos y estado |
| agentes/settings.py y llm.py | Configuración y proveedor |
| agentes/async_graph.py y agent.py | Grafo asyncio y API común |
| agentes/nodes/ | Supervisor, especialistas, coordinador, síntesis y aplicar |
| agentes/tools/ | Allowlist, conector RAG, HTTP, visión y auxiliares |
| clientes/ | CLI, Streamlit, HITL y debug |
| rag/ | Punto de montaje del RAG existente, sin contenidos |
| scripts/ | Preparación y verificación futuras |
| tests/ | Espacios para las pruebas futuras |
| data/, storage/, assets/ | Carpetas vacías para datos, índice e imágenes |
| docs/specs/ y entregables/ | Acuerdos y evidencia pendientes |

## Orden para empezar

1. Acordar alcance y contratos en docs/specs/contratos.md.
2. Definir state.py y settings.py.
3. Preparar ejemplos de contrato en tests/fixtures/, identificados como simulados.
4. Implementar tools y nodos por separado.
5. Conectar grafo, concurrencia e HITL.
6. Implementar API y clientes; verificar recorridos reales.

Cada responsable puede desarrollar su nodo/tool contra ejemplos acordados.
El coordinador asíncrono combina ramas independientes; cada especialista conserva
el orden de llamadas que dependan de resultados anteriores.

Esta estructura inicial no se ejecuta como aplicación ni acredita ningún requisito funcional.
requirements contiene comentarios orientativos, no un entorno instalable.
No se han creado datos de fallback, imágenes ni contenido del RAG.
