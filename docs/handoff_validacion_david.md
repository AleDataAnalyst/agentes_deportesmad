# Validación y filtrado compartidos para David

## Inventario y alcance

La CLI contenía `_validar_entrada`, `_validar_id`, `_validar_estado`,
`_sin_secretos` y `_breve`. Las primeras cuatro son reutilizables por ambos
clientes: reciben texto, identificadores o el contrato de `AgentService` y no
dependen de la interfaz. Streamlit actualmente no implementa esas validaciones
ni ese filtrado; su adopción queda pendiente para David. No se ha modificado
`streamlit_app.py`, `debug.py` ni `hitl.py`.

`_breve` conserva el formato y truncado de consola y permanece en la CLI, junto
con `mostrar_estado`, `_mostrar_debug`, comandos, alias, sugerencias, argumentos,
menú, lectura y bucle de interacción. La CLI importa las funciones compartidas
con sus nombres privados anteriores para mantener compatibilidad sin wrappers
ni duplicación de reglas.

## API pública

```python
from agentes.validation import (
    MAX_ENTRADA, validar_entrada, validar_id, validar_estado,
    validar_mensaje, validar_decision,
)
from agentes.secret_filter import sin_secretos
```

| Función | Contrato conservado |
| --- | --- |
| `validar_entrada(texto: str) -> None` | Exige texto, máximo 8000 caracteres y ausencia de controles Unicode Cc/Cf. Lanza `ValueError`. No recorta y permite vacío o espacios para la lectura de terminal; para consultas se usa `validar_mensaje`. |
| `validar_mensaje(texto: str) -> None` | Reutiliza `validar_entrada` y rechaza vacío o espacios con `ValueError`. Usar antes de enviar una consulta; la línea vacía de terminal se sigue ignorando. |
| `validar_decision(aprobado: bool) -> None` | Solo acepta `True` o `False`, sin convertir 0, 1 ni cadenas. Lanza `TypeError`. `AgentService` la llama antes de consultar o modificar el checkpoint. |
| `validar_id(valor: object) -> None` | Texto no vacío de hasta 256 caracteres, sin espacios ni controles Cc/Cf. Lanza `ValueError`. |
| `validar_estado(estado: dict, hilo: str) -> dict` | Exige el hilo esperado y booleano HITL estricto; si está pendiente, identificador de plan válido y lista no vacía de pasos de texto no vacíos. Comprueba que `ejecucion_incompleta`, si existe, sea booleano y que `approved` sea booleano o `None`. Devuelve el mismo objeto sin modificarlo. Lanza `ValueError` o `TypeError` si la decisión tiene tipo inválido. |
| `sin_secretos(valor: object) -> str` | Recorre diccionarios, listas, tuplas y conjuntos antes de convertir a texto. Una clave sensible oculta su valor completo, incluidas estructuras anidadas. Neutraliza controles y filtra credenciales reconocibles sin mutar el objeto recibido. |

Los módulos solo usan biblioteca estándar: no importan Streamlit, leen terminal,
acceden a red ni cambian estado. Estas validaciones de presentación no acreditan
la vigencia o pertenencia real de un plan. Las guardias de autoridad siguen en
`AgentService` y el grafo, sin cambios.

## Ejemplos de integración futura en Streamlit

Validar antes de añadir un mensaje al historial o enviarlo al servicio:

```python
validar_mensaje(prompt)
resultado = validar_estado(service.procesar_turno(prompt, thread_id), thread_id)
st.session_state.estado = resultado  # Solo después de validar.
st.markdown(sin_secretos(resultado.get("final_answer", "")))
```

Validar el hilo recién creado y cada respuesta del servicio, también en los
callbacks de aprobación/rechazo y al recuperar estado:

```python
nuevo_hilo = service.nueva_conversacion()
validar_id(nuevo_hilo)
nuevo_estado = validar_estado(service.consultar_estado(nuevo_hilo), nuevo_hilo)
# Asignar nuevo_hilo/nuevo_estado a la sesión tras completar ambas validaciones.

resultado = validar_estado(
    service.resolver_plan(thread_id, aprobado=True, plan_id=estado["plan_id"]),
    thread_id,
)
st.session_state.estado = resultado
```

Los botones deben producir booleanos literales; con un valor externo, comprobar
`validar_decision(aprobado)` antes de llamar a `resolver_plan`. Esta comprobación
no sustituye la validación de plan vigente e idempotencia que hace el backend.

Capturar `ValueError` y `TypeError` antes de sustituir el estado o habilitar decisiones. Tras
una operación fallida, recuperar y validar el estado antes de permitir otra
decisión; el backend pudo guardar un checkpoint. Conservar las restricciones
HITL del cliente y enviar siempre el `plan_id` mostrado. No asignar `approved`
ni reanudar el grafo desde la UI.

`ejecucion_incompleta=True` significa que el checkpoint conserva trabajo fuera
de la pausa HITL. Mostrar el aviso de iniciar otra conversación y conservar el
hilo anterior; no presentarlo como una conversación disponible sin propuesta.
La guardia del servicio mantiene `REQUEST_INCOMPLETE` para nuevos pedidos en ese
hilo. Los errores del servicio conservan el formato `CÓDIGO: detalle`: para
orientar por código se puede usar `str(exc).partition(":")[0]`, sin comparar
frases completas. La CLI lo hace para los códigos HITL y de plan existentes;
un código desconocido conserva su diagnóstico sin inventar una operación.

Aplicar `sin_secretos` al texto mostrado o guardado para presentación: historial
(incluido el usuario), respuestas, pasos del plan, fuentes, trazas y errores:

```python
st.error(sin_secretos(exc))
st.markdown(sin_secretos(evento))
```

Pasar el objeto estructurado al filtro antes de convertirlo a texto:

```python
evento = {"datos": {"password": ["ejemplo", "otro ejemplo"]}, "nota": "Basic incluye piscina"}
st.text(sin_secretos(evento))  # Oculta la lista completa y conserva la nota.
```

No sustituir el estado operativo por una cadena filtrada ni filtrar identificadores
antes de enviarlos al servicio. El filtro no es un escape HTML ni un detector de
secretos arbitrarios; evitar volcar configuración o resultados enteros.

## Corrección de Basic

`El plan Basic incluye piscina` se conserva. Se oculta `Basic dXNlcjpwYXNz`
(Base64 de `user:pass`) por su contenido de credencial; también se ocultan valores
en cabeceras `Authorization`/`Proxy-Authorization`, aunque no sean Base64 válido.
Se mantienen las reglas previas de Bearer, asignaciones de claves/tokens,
claves privadas, prefijos reconocibles y credenciales en URL. Las pruebas usan
valores sintéticos con formatos reales, sin consultar secretos locales ni red.

## Validación ejecutada

Revisión del 21/10/2026: **577 pruebas pasadas** en Windows, con especialistas
dobles y sin consultas a servicios reales. La selección cubre los módulos
comunes, CLI y backend, importaciones sin UI/backend y ausencia de IO de las
utilidades; incluye filtrado anidado sin mutación, vacíos/límites, booleanos
estrictos, errores por código, recuperación con `/nueva` y preservación de la
respuesta aprobada con reintento e idempotencia.

Con el entorno activado según el README, ejecutar esta selección. En la
comprobación local se pasó además `--basetemp` con una carpeta nueva dentro de
`tmp/` para evitar permisos del directorio temporal del sistema:

```console
python -m pytest -q tests/test_validation.py tests/test_secret_filter.py tests/test_cli.py tests/test_cli_security.py tests/test_import_boundaries.py tests/test_agent_service.py tests/test_backend_cierre.py tests/test_graph_hitl.py tests/test_node_guards.py tests/test_infra_sintetizar_aplicar.py tests/test_sintetizar_aplicar.py tests/test_demo.py tests/test_supervisor.py tests/test_state.py tests/test_contracts.py tests/test_golden_graph.py tests/test_export_evidence.py tests/test_sync_integration.py
```

`git diff --check` de los archivos modificados no detectó errores de whitespace.
