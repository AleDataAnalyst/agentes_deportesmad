"""Cliente síncrono de AgentService, sin nodos, tools ni autoaprobación.

La factoría se carga al arrancar, después de validar argumentos: --help no
necesita importar el backend. El mismo bucle consume modo real y demo explícita.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from difflib import get_close_matches
import re
import sys
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentes.agent import AgentService

AYUDA = (
    "Escribe una consulta o usa /aprobar, /rechazar, /estado, /debug, "
    "/nueva, /ayuda, /salir."
    " Todos los comandos funcionan también sin barra; nuevo equivale a nueva."
)
ALIAS_COMANDOS = {palabra: "/" + palabra for palabra in (
    "aprobar", "rechazar", "estado", "debug", "nueva", "ayuda", "salir",
)}
ALIAS_COMANDOS["nuevo"] = "/nueva"
MAX_TRAZA = 30
MAX_EVENTOS_TOOL = 10
MAX_ENTRADA = 8000


def _validar_entrada(texto: str) -> None:
    if not isinstance(texto, str):
        raise ValueError("La entrada debe ser texto.")
    if len(texto) > MAX_ENTRADA:
        raise ValueError(f"Entrada demasiado larga: máximo {MAX_ENTRADA} caracteres; no se ha enviado.")
    if any(unicodedata.category(c) in ("Cc", "Cf") for c in texto):
        raise ValueError("Entrada con caracteres de control o formato invisible; no se ha enviado.")


def _validar_id(valor: object) -> None:
    if (not isinstance(valor, str) or not valor.strip() or len(valor) > 256
            or any(c.isspace() or unicodedata.category(c) in ("Cc", "Cf") for c in valor)):
        raise ValueError("Identificador inválido devuelto por el servicio.")


def _validar_estado(estado: dict, hilo: str) -> dict:
    """Falla antes de sustituir el estado conocido o mostrar un plan de otro hilo."""
    if not isinstance(estado, dict) or estado.get("thread_id") != hilo:
        raise ValueError("Estado incompatible con la conversación actual.")
    if type(estado.get("pendiente_hitl")) is not bool:
        raise ValueError("Estado HITL inválido: se requiere un booleano.")
    if estado["pendiente_hitl"]:
        _validar_id(estado.get("plan_id"))
        plan = estado.get("plan")
        if (not isinstance(plan, list) or not plan
                or any(not isinstance(p, str) or not p.strip() for p in plan)):
            raise ValueError("Plan pendiente inválido; no se permite decidir.")
    return estado


def _sin_secretos(valor: object) -> str:
    """Oculta credenciales reconocibles sin leer .env ni volcar configuración."""
    texto = str(valor)
    # Eliminar OSC/CSI antes del filtrado: no permitir enlaces, portapapeles,
    # borrado de terminal ni credenciales partidas por códigos de color.
    texto = re.sub(r"(?:\x1b\]|\x9d)[^\x07\x1b\x9c]*(?:\x07|\x1b\\|\x9c|$)", "", texto)
    texto = re.sub(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]", "", texto)
    texto = "".join(c for c in texto if c in "\n\t" or unicodedata.category(c) not in ("Cc", "Cf"))
    texto = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                   "[CLAVE PRIVADA OCULTA]", texto, flags=re.DOTALL)
    texto = re.sub(r"(?i)\b(Bearer|Basic)\s+[^\s,;]+", r"\1 [OCULTO]", texto)
    texto = re.sub(r"(?i)\b([a-z0-9_-]*api[_-]?key|[a-z0-9_-]*token|[a-z0-9_-]*secret|password|authorization|key)\b[\"']?\s*[:=]\s*(?:[\"'][^\"']*[\"']|[^\s,;&}]+)",
                   r"\1=[OCULTO]", texto)
    texto = re.sub(r"\b(?:AIza[\w-]{20,}|sk-[\w-]{16,})", "[OCULTO]", texto)
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[OCULTO]@", texto)


def _breve(valor, limite: int = 240) -> str:
    texto = " ".join(_sin_secretos(valor).split())
    return texto if len(texto) <= limite else texto[:limite] + "..."


def _mostrar_debug(estado: dict, escribir: Callable[[str], None]) -> None:
    escribir("Debug:")
    for clave in ("thread_id", "plan_id", "pendiente_hitl", "approved", "done", "iterations"):
        escribir(f"  {clave}={estado.get(clave)}")
    traza = estado.get("debug_trace", [])
    if len(traza) > MAX_TRAZA:
        escribir(f"  Traza: {len(traza) - MAX_TRAZA} eventos anteriores omitidos.")
    for evento in traza[-MAX_TRAZA:]:
        escribir(f"  {_breve(evento)}")
    for rol, resultado in estado.get("specialist_results", {}).items():
        if resultado.data.get("request_id"):
            escribir(f"  {rol}.request_id={_breve(resultado.data['request_id'])}")
        eventos = resultado.data.get("eventos", [])
        if len(eventos) > MAX_EVENTOS_TOOL:
            escribir(f"  {rol}: {len(eventos) - MAX_EVENTOS_TOOL} eventos de tools omitidos.")
        for evento in eventos[-MAX_EVENTOS_TOOL:]:
            resumen = {k: evento[k] for k in ("tool", "ok", "abstained", "ms") if k in evento}
            escribir(f"  {rol}.tool: {_breve(resumen)}")


def mostrar_estado(
    estado: dict, *, debug: bool = False, escribir: Callable[[str], None] = print,
) -> None:
    """Presenta el contrato interno sin modificarlo ni serializar su estado entero."""
    destino = escribir
    escribir = lambda texto: destino(_sin_secretos(texto))
    escribir("HITL: " + ("pendiente de decisión" if estado.get("pendiente_hitl") else "sin plan pendiente"))
    if estado.get("final_answer"):
        escribir(estado["final_answer"])
    for rol, resultado in estado.get("specialist_results", {}).items():
        escribir(f"Especialista {rol}: {resultado.status}")
        if resultado.error:
            escribir(f"  Error: {_breve(resultado.error)}")
        for evidencia in resultado.evidence:
            escribir(f"  Fuente: {evidencia.source}")
        datos = resultado.data
        if datos.get("fallback") or datos.get("origen") == "fallback":
            escribir("  Fallback histórico: no acredita condiciones actuales.")
        for clave in (
            "limitaciones", "advertencias", "warnings", "origen",
            "fecha_consulta", "fecha_captura_fallback", "fecha_captura", "captured_at",
        ):
            valor = datos.get(clave)
            if valor is not None and valor != [] and valor != "":
                texto = "; ".join(str(v) for v in valor) if isinstance(valor, list) else str(valor)
                escribir(f"  {clave}: {texto}")
    if estado.get("pendiente_hitl"):
        escribir(f"Plan pendiente de decisión (plan_id={estado['plan_id']}):")
        for paso in estado.get("plan", []):
            escribir(f"  - {paso}")
        escribir("Revisa la propuesta y escribe /aprobar o /rechazar.")
    elif not estado.get("final_answer"):
        escribir("Conversación sin propuesta pendiente.")
    if debug:
        _mostrar_debug(estado, escribir)


def ejecutar_interactivo(
    servicio: AgentService, *, mensaje: str | None = None, debug: bool = False,
    leer: Callable[[str], str] = input, escribir: Callable[[str], None] = print,
) -> int:
    """Conserva un servicio y el hilo actual; cada decisión usa el plan mostrado."""
    destino = escribir
    escribir = lambda texto: destino(_sin_secretos(texto))
    try:
        hilo = servicio.nueva_conversacion()
        _validar_id(hilo)
        estado = _validar_estado(servicio.consultar_estado(hilo), hilo)
    except (EOFError, KeyboardInterrupt):
        escribir("Salida sin decisiones automáticas.")
        return 0
    except Exception as exc:
        escribir(f"Error al iniciar conversación: {_breve(exc)}")
        return 1
    escribir(f"Conversación: {hilo}")
    escribir(AYUDA)
    inicial = mensaje
    estado_desconocido = False
    try:
        while True:
            es_mensaje_inicial = inicial is not None
            if es_mensaje_inicial:
                entrada, inicial = inicial, None
            else:
                entrada = leer("Tú> ")
            try:
                _validar_entrada(entrada)
            except ValueError as exc:
                escribir(str(exc))
                continue
            entrada = entrada.strip()
            if not entrada:
                continue
            comando = entrada.casefold() if entrada.startswith("/") and not es_mensaje_inicial else None
            if not es_mensaje_inicial and comando is None:
                comando = ALIAS_COMANDOS.get(entrada.casefold())
                # Una errata de una sola palabra se sugiere; nunca se ejecuta
                # una aprobación o salida por similitud ni se envía como pedido.
                if comando is None and len(entrada.split()) == 1:
                    candidatos = get_close_matches(entrada.casefold(), ALIAS_COMANDOS, n=1, cutoff=0.8)
                    if candidatos:
                        escribir(f"¿Querías escribir {ALIAS_COMANDOS[candidatos[0]]}? Repite el comando; no se ha enviado ninguna consulta.")
                        continue
            if comando == "/nuevo":
                comando = "/nueva"
            if comando == "/salir":
                break
            if comando == "/ayuda":
                escribir(AYUDA)
                continue
            if comando and comando not in ("/nueva", "/estado", "/debug", "/aprobar", "/rechazar"):
                escribir("Comando desconocido. Usa /ayuda.")
                continue
            try:
                if comando == "/nueva":
                    if estado_desconocido:
                        estado = _validar_estado(servicio.consultar_estado(hilo), hilo)
                        if estado["pendiente_hitl"]:
                            # El plan recuperado debe verse antes de decidir;
                            # la operación fallida pudo guardarlo sin mostrarlo.
                            mostrar_estado(estado, debug=debug, escribir=escribir)
                        estado_desconocido = False
                    if estado.get("pendiente_hitl"):
                        escribir("Hay un plan pendiente: usa /aprobar, /rechazar o /salir antes de /nueva.")
                        continue
                    nuevo_hilo = servicio.nueva_conversacion()
                    _validar_id(nuevo_hilo)
                    nuevo_estado = _validar_estado(servicio.consultar_estado(nuevo_hilo), nuevo_hilo)
                    hilo, estado = nuevo_hilo, nuevo_estado
                    estado_desconocido = False
                    escribir(f"Nueva conversación: {hilo}. El hilo anterior se conserva en este proceso.")
                elif comando in ("/estado", "/debug"):
                    estado = _validar_estado(servicio.consultar_estado(hilo), hilo)
                    estado_desconocido = False
                elif comando in ("/aprobar", "/rechazar"):
                    if estado_desconocido:
                        escribir("Estado sin confirmar tras un error: consulta /estado antes de decidir.")
                        continue
                    if not estado.get("pendiente_hitl"):
                        escribir("No hay un plan pendiente de decisión.")
                        continue
                    estado = _validar_estado(servicio.resolver_plan(
                        hilo, comando == "/aprobar", plan_id=estado["plan_id"],
                    ), hilo)
                else:
                    if estado_desconocido:
                        escribir("Estado sin confirmar tras un error: usa /estado o /nueva antes de consultar.")
                        continue
                    if estado.get("pendiente_hitl"):
                        escribir("Hay un plan pendiente: usa /aprobar, /rechazar o /salir.")
                        continue
                    estado = _validar_estado(servicio.procesar_turno(entrada, hilo), hilo)
                mostrar_estado(estado, debug=debug or comando == "/debug", escribir=escribir)
            except Exception as exc:
                estado_desconocido = True
                escribir(f"Error: {_breve(exc)}")
                escribir("Puedes consultar /estado, iniciar /nueva o usar /salir.")
    except (EOFError, KeyboardInterrupt):
        pass
    escribir("Salida sin decisiones automáticas. La memoria de la sesión termina con el proceso.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI del asistente de deporte municipal con HITL manual.", allow_abbrev=False)
    seleccion = parser.add_mutually_exclusive_group()
    seleccion.add_argument("--modo", choices=("real", "demo"), default="real", help="Montaje explícito (default: real)")
    seleccion.add_argument("--menu", action="store_true", help="Seleccionar demo o real interactivamente, sin opción por defecto")
    parser.add_argument("--mensaje", help="Consulta inicial; después continúa la sesión interactiva")
    parser.add_argument("--debug", action="store_true", help="Mostrar estado y trazas acotadas")
    args = parser.parse_args(argv)
    if args.mensaje is not None:
        try:
            _validar_entrada(args.mensaje)
        except ValueError as exc:
            parser.error(str(exc))
    if args.mensaje is not None and not args.mensaje.strip():
        parser.error("--mensaje no puede estar vacío")
    if args.menu:
        try:
            while True:
                opcion = input("Modo: 1) demo simulada  2) real (aceptación pendiente)  0) salir\nSelección> ")
                try:
                    _validar_entrada(opcion)
                except ValueError as exc:
                    print(str(exc))
                    continue
                opcion = opcion.strip().casefold()
                if opcion in ("0", "salir"):
                    return 0
                if opcion in ("1", "demo", "2", "real"):
                    args.modo = "demo" if opcion in ("1", "demo") else "real"
                    break
                print("Selección inválida. Escribe 1, 2 o 0; no hay selección por defecto.")
        except (EOFError, KeyboardInterrupt):
            print("Salida sin crear servicio ni tomar decisiones.")
            return 0
    print("DEMO SIMULADA: sin RAG, HTTP ni datos municipales reales." if args.modo == "demo"
          else "Modo real: utiliza los componentes disponibles del montaje y sus limitaciones.")
    try:
        from agentes.runtime import crear_servicio

        servicio = crear_servicio(modo=args.modo)
    except (EOFError, KeyboardInterrupt):
        print("Salida sin decisiones automáticas.")
        return 0
    except Exception as exc:
        print(f"Error al crear servicio: {_breve(exc)}", file=sys.stderr)
        return 1
    return ejecutar_interactivo(servicio, mensaje=args.mensaje, debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
