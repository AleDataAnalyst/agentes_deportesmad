"""Cliente de terminal: pedidos, fuentes, errores y decisión humana.

Consumir la API común. Ofrecer modo interactivo, demo explícita, aprobar,
rechazar, nueva conversación y salida. Mostrar thread_id y trazas si se solicita.
No duplicar orquestación. Autoaprobación, si se implementa, solo para demo explícita.
"""

import argparse

from agentes.runtime import aviso_modo, crear_servicio


def mostrar(estado, *, debug=False):
    """La síntesis del servicio ya incluye fuentes y limitaciones declaradas."""
    print(estado.get("final_answer", ""))
    for paso in estado.get("plan", []):
        print(f"- {paso}")
    if debug:
        print("\n".join(estado.get("debug_trace", [])))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Asistente de deporte municipal")
    parser.add_argument("--modo", choices=("real", "demo"), default="real")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    print(aviso_modo(args.modo))
    try:
        service = crear_servicio(modo=args.modo)
    except Exception as exc:
        print(f"Error al iniciar: {exc}")
        return 1
    thread_id = service.nueva_conversacion()
    print("Comandos: /nueva, /salir. Con plan pendiente: /aprobar o /rechazar.")
    while True:
        try:
            mensaje = input("> ").strip()
            if mensaje == "/salir":
                return 0
            if mensaje == "/nueva":
                thread_id = service.nueva_conversacion()
                print("Nueva conversación.")
                continue
            estado = service.consultar_estado(thread_id)
            if mensaje in ("/aprobar", "/rechazar"):
                estado = service.resolver_plan(
                    thread_id, mensaje == "/aprobar", plan_id=estado.get("plan_id"))
            elif estado["pendiente_hitl"]:
                print("Plan pendiente: usa /aprobar o /rechazar antes de otro pedido.")
                continue
            else:
                estado = service.procesar_turno(mensaje, thread_id)
            mostrar(estado, debug=args.debug)
        except (EOFError, KeyboardInterrupt):
            print("\nSalida; los checkpoints viven solo en este proceso.")
            return 0
        except Exception as exc:
            # Se conserva el checkpoint; el usuario puede abrir otro hilo si
            # hubo una ejecución incompleta. No se inventa una respuesta.
            print(f"Error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
