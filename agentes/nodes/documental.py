"""
agentes/nodes/documental.py

Entradas (state):
    request_id: str                      — identificador del pedido vigente (obligatorio)
    pedido: str                          — texto del pedido actual
    contexto_permitido: list[str] | None — fuentes autorizadas (None = todas)
    image_id: str | None                 — ruta o identificador de la imagen adjunta
    presupuesto_tools: int               — máximo de llamadas a tools (default 4)
    preparar_borrador: bool              — si se pide un borrador (default False)

Salidas (solo la clave autorizada "documental"):
    documental: dict
        {
            "request_id":   str,
            "resultado":    str,         # síntesis de la evidencia (texto plano)
            "fuentes":      list[str],   # fuentes citadas, orden de aparición
            "abstained":    bool,
            "errores":      list[str],
            "limitaciones": list[str],   # tools no disponibles, presupuesto, contexto
            "eventos":      list[dict],  # uno por cada llamada a tool
        }

Reglas del especialista:
    - No inventar condiciones: si no hay evidencia útil, se abstiene.
    - Un cartel/imagen es evidencia visual, no normativa vigente.
    - Actualizar solo campos autorizados: la única clave devuelta es "documental".
    - El bucle está acotado por presupuesto_tools.

Tools (registry):
    rag              → implementada (agentes.tools.rag.rag_preguntar)
    imagen           → implementada: describe o responde sobre una imagen JPG/JPEG/PNG
    preparar_reporte → prevista (no disponible aún → limitación)
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable
from agentes.especialista_llm import Herramienta, ejecutar_especialista, modo_especialistas
from agentes.tools.rag import rag_preguntar
from agentes.tools.vision import imagen_preguntar

PRESUPUESTO_DEFECTO = 4

FORMATOS_IMAGEN = {".jpg", ".jpeg", ".png"}
DIRECTORIO_IMAGENES = Path("output") / "imagenes"

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Utilidades de imagen
# ---------------------------------------------------------------------------

def guardar_imagen_subida(nombre_archivo: str, contenido: bytes) -> str:
    """Guarda una imagen subida y devuelve el image_id utilizable por la tool."""
    extension = Path(nombre_archivo or "").suffix.lower()

    if extension not in FORMATOS_IMAGEN:
        raise ValueError(
            "IMAGE_UNSUPPORTED: solo se aceptan imágenes JPG, JPEG o PNG"
        )

    if not contenido:
        raise ValueError("IMAGE_EMPTY: el archivo de imagen está vacío")

    DIRECTORIO_IMAGENES.mkdir(parents=True, exist_ok=True)

    image_id = f"{uuid.uuid4().hex}{extension}"
    ruta = DIRECTORIO_IMAGENES / image_id
    ruta.write_bytes(contenido)

    return str(ruta)


# ---------------------------------------------------------------------------
# Registry de tools
# ---------------------------------------------------------------------------

def _tool_rag(consulta: str) -> dict[str, Any]:
    """Normaliza la salida de rag_preguntar al contrato de observación."""
    r = rag_preguntar(consulta)

    return {
        "ok": r["error"] is None,
        "resultado": r["respuesta"],
        "fuentes": list(r["fuentes"]),
        "abstained": bool(r["abstained"]),
        "error": r["error"],
    }


def _tool_imagen(image_id: str, pregunta: str) -> dict[str, Any]:
    """Normaliza la salida de imagen_preguntar al contrato de observación."""
    r = imagen_preguntar.invoke({"image_id": image_id, "pregunta": pregunta})

    return {
        "ok": bool(r.get("ok")),
        "resultado": str(r.get("resultado", "")),
        "fuentes": [
            str(f.get("ruta", "")) if isinstance(f, dict) else str(f)
            for f in r.get("fuentes", [])
        ],
        "abstained": bool(r.get("abstained")),
        "error": r.get("error"),
    }


REGISTRY: dict[str, Callable[..., dict[str, Any]] | None] = {
    "rag": _tool_rag,
    "imagen": _tool_imagen,
    "preparar_reporte": None,
}

PROMPT_DOCUMENTAL = """Eres el especialista documental del asistente de deporte municipal de Madrid.
Tu trabajo es decidir qué herramientas consultar para responder con evidencia.
- Usa rag para normativa, tarifas, abonos, reservas, servicios y centros.
- Si el usuario adjunta una imagen, usa imagen para leerla.
- Puedes reformular la consulta para el RAG, pero no inventes datos.
- Cuando tengas la evidencia necesaria, responde sin llamar a más herramientas."""


def _llamada(paso: int, tool: str, args: dict[str, Any], funcion) -> dict[str, Any]:
    """Ejecuta una tool del registro con el mismo formato que el bucle LLM."""
    observacion, error = _ejecutar_tool(tool, funcion, args)
    if error is not None:
        observacion = {"ok": False, "resultado": "", "fuentes": [], "abstained": False, "error": error}
    status = "error" if observacion.get("error") else "ok"
    return {"paso": paso, "tool": tool, "args": args, "status": status,
            "preview": str(observacion.get("resultado", ""))[:200], "resultado": observacion}


def _plan_reglas(pedido: str, image_id: str | None, presupuesto: int) -> list[dict[str, Any]]:
    """Plan fijo: primero el RAG y, si hay imagen y presupuesto, la visión."""
    llamadas = [_llamada(1, "rag", {"consulta": pedido}, REGISTRY["rag"])]
    if image_id and presupuesto > 1:
        llamadas.append(_llamada(
            2, "imagen", {"image_id": str(image_id), "pregunta": pedido}, REGISTRY["imagen"],
        ))
    return llamadas


def _plan_llm(pedido: str, image_id: str | None, presupuesto: int) -> list[dict[str, Any]]:
    """El LLM propone las llamadas; la ruta de la imagen la fija Python, no el modelo."""
    herramientas = [Herramienta(
        "rag", "Consulta los documentos y datos municipales indexados.",
        {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]},
        lambda consulta: REGISTRY["rag"](consulta),
    )]
    if image_id:
        herramientas.append(Herramienta(
            "imagen", "Responde una pregunta sobre la imagen adjunta por el usuario.",
            {"type": "object", "properties": {"pregunta": {"type": "string"}}, "required": ["pregunta"]},
            lambda pregunta: REGISTRY["imagen"](str(image_id), pregunta),
        ))
    return ejecutar_especialista(
        prompt_sistema=PROMPT_DOCUMENTAL, mensaje=pedido,
        herramientas=herramientas, max_steps=presupuesto,
    )


# ---------------------------------------------------------------------------
# Nodo del especialista documental
# ---------------------------------------------------------------------------

def _imagen_disponible(image_id: str | None) -> bool:
    """Comprueba que la imagen indicada existe y tiene un formato admitido."""
    if not image_id:
        return False

    ruta = Path(image_id)
    return ruta.is_file() and ruta.suffix.lower() in FORMATOS_IMAGEN


def _ejecutar_tool(
    nombre: str,
    funcion: Callable[..., dict[str, Any]],
    argumentos: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Ejecuta una tool sin propagar excepciones."""
    try:
        return funcion(**argumentos), None
    except Exception as exc:  # noqa: BLE001 - el nodo no debe lanzar
        return None, f"{nombre}: {type(exc).__name__}: {exc}"


def _normalizar_fuentes(fuentes: list[Any]) -> list[str]:
    """Normaliza fuentes tipo str o {'ruta': str} a una lista de rutas."""
    normalizadas: list[str] = []

    for fuente in fuentes or []:
        if isinstance(fuente, str):
            normalizadas.append(fuente)
        elif isinstance(fuente, dict) and fuente.get("ruta"):
            normalizadas.append(str(fuente["ruta"]))

    return normalizadas


def nodo_documental(state: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta el bucle acotado del especialista documental."""
    request_id = str(state.get("request_id") or "")
    pedido = str(state.get("pedido") or "").strip()
    contexto_permitido = state.get("contexto_permitido")
    image_id = state.get("image_id")
    presupuesto = state.get("presupuesto_tools", PRESUPUESTO_DEFECTO)
    preparar_borrador = bool(state.get("preparar_borrador", False))

    resultado = ""
    fuentes: list[str] = []
    errores: list[str] = []
    limitaciones: list[str] = []
    eventos: list[dict[str, Any]] = []
    abstained = True

    if not request_id:
        errores.append("REQUEST_ID_MISSING: falta request_id")

    if not pedido:
        errores.append("PEDIDO_MISSING: falta el texto del pedido")

    try:
        presupuesto = int(presupuesto)
    except (TypeError, ValueError):
        presupuesto = PRESUPUESTO_DEFECTO
        limitaciones.append("presupuesto_tools inválido; se usa el valor por defecto")

    if presupuesto <= 0:
        limitaciones.append("presupuesto agotado: no se puede consultar ninguna tool")

    if preparar_borrador:
        limitaciones.append("preparar_reporte no está disponible todavía")

    if image_id and not _imagen_disponible(str(image_id)):
        limitaciones.append("imagen no disponible o formato no admitido")
        image_id = None

    puede_consultar = bool(request_id and pedido and presupuesto > 0)

    usar_llm = puede_consultar and modo_especialistas() == "llm"
    llamadas: list[dict[str, Any]] = []

    if usar_llm:
        try:
            llamadas = _plan_llm(pedido, image_id, presupuesto)
        except Exception:
            logger.warning(
                "Planificación LLM no disponible; se usan reglas", exc_info=True
            )
            limitaciones.append(
                "planificación LLM no disponible; se usan reglas"
            )
            usar_llm = False

    if not usar_llm:
        # Priorizar la imagen adjunta evita que el RAG consuma el único turno.
        # Ambas tools comparten presupuesto y su evidencia es independiente:
        # la abstención del RAG no invalida una observación visual útil.
        llamadas = []
        if image_id:
            llamadas.append({
                "tool": "imagen",
                "args": {"image_id": str(image_id), "pregunta": pedido},
            })
        llamadas.append({
            "tool": "rag",
            "args": {"consulta": pedido},
        })

    for llamada in llamadas:
        nombre = llamada["tool"]
        argumentos = llamada.get("args", {})

        if not puede_consultar:
            break

        if presupuesto <= 0:
            limitaciones.append(
                f"presupuesto agotado: no se consultó {nombre}"
            )
            break

        if usar_llm:
            observacion = llamada.get("resultado")
            error = None
            if not isinstance(observacion, dict):
                error = f"{nombre}: observación inválida"
        else:
            funcion = REGISTRY.get(nombre)
            if funcion is None:
                limitaciones.append(f"{nombre} no disponible")
                continue
            observacion, error = _ejecutar_tool(nombre, funcion, argumentos)

        presupuesto -= 1

        if error is None:
            try:
                if not isinstance(observacion, dict):
                    raise TypeError("la observación debe ser un diccionario")

                fuentes_raw = observacion.get("fuentes", [])
                if not isinstance(fuentes_raw, list):
                    raise TypeError("fuentes debe ser una lista")

                texto = observacion.get("resultado", "")
                if not isinstance(texto, str):
                    raise TypeError("resultado debe ser texto")
            except (TypeError, ValueError) as exc:
                error = f"{nombre}: observación inválida: {exc}"

        if error is not None:
            errores.append(error)
            eventos.append({
                "tool": nombre,
                "args": argumentos,
                "ok": False,
                "error": error,
                "abstained": False,
            })
            continue

        tool_error = observacion.get("error")
        ok = observacion.get("ok") is True and not tool_error

        eventos.append({
            "tool": nombre,
            "args": argumentos,
            "ok": ok,
            "error": tool_error,
            "abstained": bool(observacion.get("abstained")),
        })

        if tool_error:
            errores.append(str(tool_error))

        fuentes_validas = fuentes_raw
        if contexto_permitido is not None:
            fuentes_validas = [
                f for f in fuentes_raw if f in contexto_permitido
            ]

            # No se puede separar qué parte del texto proviene de cada fuente:
            # si alguna no está autorizada, se omite toda la observación.
            if len(fuentes_validas) != len(fuentes_raw):
                limitaciones.append(
                    "fuentes fuera del contexto permitido; respuesta omitida"
                )
                continue

        if (
            not ok
            or observacion.get("abstained")
            or not texto.strip()
            or not fuentes_validas
        ):
            limitaciones.append(
                f"{nombre}: sin evidencia útil en las fuentes disponibles"
            )
            continue

        if nombre == "imagen":
            texto = (
                "Evidencia visual (no acredita normativa vigente):\n"
                f"{texto.strip()}"
            )

        resultado = "\n\n".join(filter(None, [resultado, texto.strip()]))

        for fuente in fuentes_validas:
            if fuente not in fuentes:
                fuentes.append(fuente)

        abstained = False


    return {
        "documental": {
            "request_id": request_id,
            "resultado": resultado,
            "fuentes": fuentes,
            "abstained": abstained,
            "errores": errores,
            "limitaciones": limitaciones,
            "eventos": eventos,
        }
    }
