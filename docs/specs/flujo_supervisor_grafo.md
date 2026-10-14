# Flujo síncrono de supervisor y grafo

Flujo explicativo de coordinación, síntesis y aprobación humana.
Los especialistas se prueban actualmente con dobles, pendientes
de integrar sus contratos reales.

```text

CLIENTE: CLI / Streamlit / demo
              |
              v
    AgentService.procesar_turno()
              |
              +-- Comprueba que no haya un plan pendiente
              +-- Crea el estado limpio del pedido
              |
              v
    grafo.invoke(estado, config)
              |
              v
         SUPERVISOR <-----------------------------------+
              |                                         |
              | Propone una ruta                        |
              v                                         |
        ROUTER DE PYTHON                                |
              |                                         |
              +-- documental ------> resultado ----------+
              |                                         |
              +-- instalaciones ---> resultado ----------+
              |                                         |
              +-- sintetizar ------> respuesta + plan ---+
              |
              `-- FINISH
                    |
                    v
            ¿Respuesta y plan válidos?
                    |
                    +-- NO --> sintetizar --> supervisor
                    |
                    `-- SÍ
                         |
                         v
                PAUSA ANTES DE APLICAR
                ----------------------
                Checkpoint guardado
                approved = None
                pendiente_hitl = True
                         |
                         v
                  DECISIÓN HUMANA
                         |
                         v
             AgentService.resolver_plan()
                         |
                         +-- Valida thread_id y plan_id
                         +-- update_state(approved)
                         `-- invoke(None, mismo config)
                                      |
                                      v
                                   APLICAR
                                      |
                    +-----------------+-----------------+
                    |                                   |
              approved=True                       approved=False
                    |                                   |
               done=True                      done=False / reset
                    |                                   |
                    v                                   v
                   END                                 END
```

## Cómo interpretarlo

- FINISH termina la preparación y conduce hacia la revisión humana.
- La pausa ocurre antes de ejecutar aplicar.
- Aprobar y rechazar pasan por aplicar.
- END termina la ejecución; tras rechazar, done permanece en False.
- La pausa y la reanudación utilizan el mismo thread_id.