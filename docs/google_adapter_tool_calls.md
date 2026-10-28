# Evidencia: adaptador Google con herramientas

**Fecha:** 28/10/2026. **Entorno:** Windows, Python 3.14.2, pytest 8.4.2,
google-genai 2.22.0. **Commit probado:** `919d939c234e1c1d21d693cf7ce7628ff03d2ee5`.
Los cambios posteriores son documentación; el código y las regresiones se conservan.

Al reconstruir el historial después de ejecutar una herramienta, el adaptador
pasaba un objeto posicional a `Part.from_function_call`, que exige `name` y
`args` por nombre. La regresión se añadió antes del arreglo y reprodujo:

```text
TypeError: Part.from_function_call() takes 1 positional argument but 2 were given
```

Se corrigió únicamente esa construcción. La prueba `tests/test_llm_google.py`
recorre los bucles RAG y de especialistas con cliente doble, sin API key ni red.
Comprueba una ejecución de la herramienta, dos llamadas al cliente y conservación
de nombre, argumentos, respuesta, instrucciones y roles `user → model → user`.

## Comandos y resultados

Variables de proceso usadas para la validación offline:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:ESPECIALISTAS_MODO='reglas'
$env:SUPERVISOR_MODE='reglas'
```

```powershell
# Antes del arreglo: 2 failed por el TypeError.
python -m pytest -q -p no:cacheprovider tests/test_llm_google.py

# Sobre el commit probado: 130 passed, 1 warning, 6.07 s.
python -m pytest -q -p no:cacheprovider --basetemp=tmp/pytest-google-pr-afectadas tests/test_llm_google.py tests/test_llm_supervisor_real.py tests/test_supervisor_llm.py tests/test_documental_adapter.py tests/test_especialistas_llm.py tests/test_regresion_planificacion_llm.py

# Sobre el commit probado: 937 passed, 50 skipped, 2 warnings, 30.16 s.
python -m pytest -q -p no:cacheprovider --basetemp=tmp/pytest-google-pr-offline tests
```

Para repetir en Windows, crear `tmp/` si falta y usar un temporal nuevo.
`git diff --check` pasó. Los avisos son deprecaciones de dependencias.

## Límites

Las 50 omisiones requieren integración real explícita. Estos resultados con
dobles y tipos del SDK no acreditan aceptación con Google, RAG, índice, visión
ni fuentes municipales reales. Sigue pendiente el recorrido real de dos turnos
con el modelo configurado y resultados verificables.

El SDK local 2.22.0 es inferior al mínimo declarado `google-genai>=2.30.1`;
la instalación limpia con las versiones declaradas queda pendiente. No se
cambiaron dependencias, modelos, `.env` ni índices.
