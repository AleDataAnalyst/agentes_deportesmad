"""Cliente síncrono de AgentService, sin nodos, tools ni autoaprobación.

La factoría se carga al arrancar, después de validar argumentos: --help no
necesita importar el backend. El mismo bucle consume modo real y demo explícita.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from difflib import get_close_matches
import sys
from typing import TYPE_CHECKING

from agentes.secret_filter import sin_secretos as _sin_secretos
from agentes.validation import (
    MAX_ENTRADA,
    validar_entrada as _validar_entrada,
    validar_estado as _validar_estado,
    validar_id as _validar_id,
    validar_mensaje as _validar_mensaje,
)

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
AVISO_EJECUCION_INCOMPLETA = (
    "Ejecución incompleta en este hilo: usa /nueva para continuar en otra conversación. "
    "El hilo anterior se conserva; no se reintenta automáticamente."
)
AYUDA_ERRORES = {
    "REQUEST_INCOMPLETE": AVISO_EJECUCION_INCOMPLETA,
    "HITL_PENDING": "Hay un plan pendiente: consulta /estado y usa /aprobar o /rechazar.",
    "PLAN_NOT_CURRENT": "El plan ya no es el vigente: consulta /estado antes de decidir.",
    "PLAN_ALREADY_RESOLVED": "La decisión ya se aplicó y no se puede cambiar; consulta /estado.",
    "HITL_NOT_PENDING": "No hay un plan pendiente de decisión; consulta /estado.",
}


def _breve(valor, limite: int = 240) -> str:
    texto = " ".join(_sin_secretos(valor).split())
    return texto if len(texto) <= limite else texto[:limite] + "..."


def _mensaje_error(exc: Exception) -> str:
    """Conserva el diagnóstico y orienta por el código, independiente del detalle."""
    codigo, separador, _ = str(exc).partition(":")
    ayuda = AYUDA_ERRORES.get(codigo) if separador else None
    return _breve(exc) + (f"\n{ayuda}" if ayuda else "")


def _mostrar_debug(estado: dict, escribir: Callable[[str], None]) -> None:
    escribir("Debug:")
    for clave in ("thread_id", "plan_id", "pendiente_hitl", "ejecucion_incompleta", "approved", "done", "iterations"):
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
    if estado.get("ejecucion_incompleta"):
        escribir("Ejecución incompleta (REQUEST_INCOMPLETE).")
    else:
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
    if estado.get("ejecucion_incompleta"):
        escribir(AVISO_EJECUCION_INCOMPLETA)
    elif estado.get("pendiente_hitl"):
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
                    if estado.get("ejecucion_incompleta"):
                        escribir(AVISO_EJECUCION_INCOMPLETA)
                        continue
                    if estado.get("pendiente_hitl"):
                        escribir("Hay un plan pendiente: usa /aprobar, /rechazar o /salir.")
                        continue
                    estado = _validar_estado(servicio.procesar_turno(entrada, hilo), hilo)
                mostrar_estado(estado, debug=debug or comando == "/debug", escribir=escribir)
            except Exception as exc:
                estado_desconocido = True
                escribir(f"Error: {_mensaje_error(exc)}")
                escribir("Consulta /estado para confirmar si hay un plan pendiente. "
                         "Si la ejecución quedó incompleta, usa /nueva para continuar; "
                         "también puedes usar /salir.")
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
            _validar_mensaje(args.mensaje)
        except ValueError as exc:
            parser.error(str(exc))
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
