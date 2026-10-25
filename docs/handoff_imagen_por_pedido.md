# Imagen por pedido: contrato para David y cierre de validación

25/10/2026. Rama `feature/backend-imagen-por-pedido`, base
`60b076dc6d6d9895716689f529eacc6d8f57858b` de `origin/develop` tras fetch.
El contrato de imagen está confirmado con David. La preparación inicial fuelocal; se autoriza ahora su commit y publicación mediante PR hacia `develop`.

## Llamada del cliente

```python
def procesar_turno(
    self, mensaje: str, thread_id: str, *, image_id: str | None = None,
) -> dict[str, Any]: ...

# Se conserva esta construcción y su ciclo de vida por sesión.
servicio = crear_servicio(modo="real")
hilo = servicio.nueva_conversacion()
pendiente = servicio.procesar_turno(
    "¿Qué información aparece en el cartel?", hilo,
    image_id="output/imagenes/archivo_generado.png",  # Ya guardado por el cliente.
)
```

El contrato del backend está confirmado; David conecta esa llamada en Streamlit. No se ha editado ningún cliente. Las llamadas actuales de dos argumentos siguen funcionando.

`image_id` admite `str | None`: ruta relativa a la raíz del repositorio o absoluta a un archivo existente en `output/imagenes/`, con extensión `.jpg`, `.jpeg` o
`.png` (sin distinguir mayúsculas). El único asset demo autorizado es
`assets/imagen_demo.jpg`, también accesible con `imagen_demo`. No se acepta una URL, bytes, base64, una ruta arbitraria ni el resto de `assets/`.
El adaptador recibe una ruta absoluta canónica. Mensaje no vacío obligatorio.

Sin imagen se envía `None`. Un pedido posterior sin imagen reinicia ese campo; el cliente debe dejar de enviar la referencia anterior cuando no corresponda al pedido nuevo. Aprobar o rechazar usa el hilo y `plan_id` habituales, sin volver a ejecutar documental/visión. El campo permanece en el checkpoint del pedido hasta su próximo reset; el historial y la traza no reciben la imagen.

Precedencia del adaptador: el estado del pedido manda, incluido `None`; la opción `image_id` de construcción solo se usa con un estado antiguo sin la clave. Se valida también esa opción al ejecutar. Una referencia antigua opaca como `img-1` sin archivo autorizado no se admite como ruta de lectura.

## Errores presentables

Todos los errores nuevos son `ValueError`, con código estable antes de `:` y mensaje sin rutas personales. Se propagan para que el cliente los presente mediante su filtrado habitual; no hay reintento automático.

| Código | Significado |
| --- | --- |
| `IMAGE_ID_INVALID` | Se recibió algo distinto de texto no vacío o `None` |
| `IMAGE_PATH_FORBIDDEN` | Ubicación no autorizada, traversal o enlace externo |
| `IMAGE_UNSUPPORTED` | Extensión distinta de JPG/JPEG/PNG |
| `IMAGE_NOT_FOUND` | La referencia autorizada no es un archivo existente |
| `IMAGE_UNAVAILABLE` | No se pudo resolver o comprobar el archivo |

Continúan los errores de mensaje vacío/tipo, hilo, `HITL_PENDING`,
`REQUEST_INCOMPLETE` y resolución del plan. Una entrada inválida no cambia el checkpoint ni ejecuta especialistas. Si el archivo desaparece entre entrada y documental, la segunda validación falla y el cliente debe consultar el estado real del hilo como ante otros errores de ejecución.

Esta validación autoriza la referencia, no valida el contenido completo de una imagen. No abre ni codifica bytes en `AgentService`. Se mantienen los controles de contenido al guardar en el cliente; no se implementa otra tool de visión.
La resolución de enlaces se comprueba, pero no se garantiza atomicidad frente a modificaciones concurrentes del sistema de archivos.

## Supervisor real: bloqueo concreto

Configuración efectiva leída del entorno y `.env` existente, sin sobrescribirlo:

| Campo | Valor efectivo |
| --- | --- |
| `SUPERVISOR_MODE` | `reglas` (predeterminado) |
| `SUPERVISOR_PROVIDER` | Ausente |
| `SUPERVISOR_MODEL` | Ausente |
| `SUPERVISOR_TEMPERATURE` | `0` |
| `SUPERVISOR_MAX_OUTPUT_TOKENS` | `256` |
| `SUPERVISOR_TIMEOUT` | `30` segundos |
| `MAX_ITER` | `8` |

La credencial Google está presente; no se mostró su valor ni se usó para seleccionar un proveedor. Faltan `SUPERVISOR_PROVIDER` y `SUPERVISOR_MODEL`;
para el montaje LLM también debe seleccionarse `SUPERVISOR_MODE=llm`.
No se infiere el modelo desde `GEN_*`, no se modifica `.env`, no se descargan modelos ni se cambia proveedor. **Cero llamadas reales de inferencia**.
No se acredita ruta/motivo reales, conversión real a `SupervisorDecision` ni distinción real frente a fallback. Esas comprobaciones requieren configuración explícita; guardias, límites y HITL conservan la evidencia offline de #22.

## Git e integración pendiente

- [#22](https://github.com/AleDataAnalyst/agentes_deportesmad/pull/22) está mergeada;
  su commit de integración coincide con esta base.
- [#21](https://github.com/AleDataAnalyst/agentes_deportesmad/pull/21) sigue abierta,
  HEAD `a84e899a26870dec16cc4b90918a4d1ba9d5ddfc`, marcada con conflictos al revisar.
  Hay comentarios de Héctor anunciando correcciones y una revisión posterior solicitando cambios sobre imports, TAB/OCR, visión y pruebas. Estos comentarios no acreditan el estado final de su implementación; no se ha revalidado ni integrado esa rama. Al resolverla deben conservarse la carga diferida, la configuración del supervisor y este contrato por pedido.
- El worktree original conserva su modificación de `docs/specs/grafo_actual.txt`
  y los tres stashes previos; se trabaja en `tmp/backend_imagen_por_pedido`.

Pendientes externos: selección explícita del proveedor/modelo del supervisor, prueba real aislada con máximo tres inferencias sin reintentos, conexión del cliente por David, integración revisada de #21, visión real y aceptación conjunta con índice RAG compatible y fuentes reales. No se asumen los pendientes de Miguel.

## Validación offline

Se ejecutó solo la selección de imagen, adaptador, servicio, estado, runtime, imports y demo, con dobles explícitos. No se ejecutó toda la suite ni se consultó RAG, Chroma o visión reales. No se repitieron las baterías de guardias/límites de #22. Las nuevas pruebas comprueban el campo protegido y el ciclo HITL con imagen.

Comando reproducible desde la raíz del worktree (crear previamente `tmp/` si falta; usar un `--basetemp` nuevo y dedicado):

```console
python -B -m pytest -q -p no:cacheprovider --basetemp tmp/pytest_imagen_revision tests/test_image_por_pedido.py tests/test_documental_adapter.py tests/test_agent_service.py tests/test_state.py tests/test_runtime.py tests/test_import_boundaries.py tests/test_demo.py
```

Resultado consolidado: **186 casos distintos superados**, incluyendo 28 casos nuevos. La primera ejecución tuvo 22 errores de preparación por faltar el padre `tmp/` del basetemp; los otros 163 pasaron. Tras crear el padre, se corrigió una expectativa de código de error para un directorio sin extensión. La selección final de 27 casos de imagen y el nuevo caso de montaje pasó: **28/28**. El resto de pruebas ya superadas no se volvió a ejecutar. Tras reforzar la comprobación
de mutación in situ del campo, se repitieron sus cuatro casos: **4/4**.
Un aviso de deprecación del SDK Google apareció en la selección original; no implica una llamada real.

El transporte probado con dobles no acredita visión real ni aceptación conjunta.

## Propuesta de commit y PR hacia develop

Commit propuesto: `feat(backend): transportar imagen validada por pedido al documental`.

Título PR: `feat(backend): aceptar image_id por pedido sin arrastre entre conversaciones`.

Descripción propuesta:

> El servicio acepta `image_id` como argumento opcional por nombre, valida la
> referencia local y la transporta hasta la puerta pública documental. Un pedido
> posterior sin imagen reinicia el campo a `None`; los nodos no pueden suplantarlo.
> Las llamadas de dos argumentos y `crear_servicio(modo="real")` se conservan.
>
> Se documentan rutas, errores y precedencia del adaptador para David. No cambian
> clientes, herramientas, especialistas, RAG, dependencias ni topología.
>
> Validación: 186 casos offline distintos superados; transporte, aislamiento,
> fuentes/errores/abstenciones y HITL con dobles. Supervisor real bloqueado por
> falta de proveedor/modelo configurados (0 inferencias). Visión real y aceptación
> conjunta con RAG siguen pendientes.
