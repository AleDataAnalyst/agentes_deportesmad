# SPEC-DEMO-01 · Demostración del backend con dobles

**Fecha:** 13/10/2026 · **Alcance:** un pedido simulado, sin LLM, RAG, HTTP ni UI.

## Comportamiento acordado

- `crear_servicio_demo()` devuelve un `AgentService` con los cuatro nodos
  simulados. El cliente conserva la instancia y utiliza la API común.
- Los escenarios `ok`, `abstained` y `error` aplican a ambos especialistas.
  Sus respuestas, fuentes y trazas se identifican como simuladas; no contienen
  tarifas, horarios, disponibilidad ni condiciones municipales supuestamente reales.
- Cada especialista conserva el resultado del otro y no modifica el estado
  recibido. `error` y `abstained` también completan el intento del rol.
- La síntesis produce una respuesta y dos pasos de demostración. Explicita los
  roles omitidos si MAX_ITER corta el recorrido; no fabrica sus resultados.
- Aplicar aprueba el borrador simulado con done=True, o rechaza con done=False
  y limpia resultados y plan. Nunca ejecuta reservas, pagos ni envíos.
- `run_demo()` devuelve el estado de la pausa y, solo si se indica una decisión
  booleana, el de resolución. Por defecto deja el plan pendiente.
- `python -m agentes.demo` muestra la demostración como JSON. `--interactivo`
  solicita aprobar/rechazar/salir después de mostrar el plan. Salir o EOF conserva
  la pausa mientras vive la instancia; finalizar el proceso pierde MemorySaver.

Esta consola es un ejecutor de demostración del esqueleto, no la CLI final del
PB02. No cambia `main.py`, los clientes ni módulos de los responsables reales.

## Criterios de aceptación

| ID | Caso | Resultado |
|---|---|---|
| D1 | Demostración sin decisión | Ambos roles registrados; respuesta y plan; pendiente_hitl=True; approved=None; done=False |
| D2 | Aprobar / rechazar | Reanuda el mismo hilo y plan; done acorde con la decisión; rechazo permite otro pedido |
| D3 | Abstención / error | Estados preservados y limitaciones visibles; sin fuentes inventadas en esos escenarios |
| D4 | Fuentes y datos de éxito simulado | Origen demo:// y metadata/data simulated=True; no prueba de evidencia municipal real |
| D5 | Copias y conversaciones distintas | Una modificación del cliente no cambia el checkpoint ni contamina otro hilo |
| D6 | Límite temprano | Síntesis declara los roles sin ejecutar; no añade resultados ficticios de esos roles |
| D7 | Consola e interacción | Salida JSON serializable; decisión explícita; EOF no aprueba automáticamente |

Los tests de demo verifican estos dobles y su ejecutor. Las pruebas del servicio
siguen acreditando idempotencia, hilo y plan vigente. Ninguna prueba de demo
sustituye las pruebas de integración con especialistas reales.
