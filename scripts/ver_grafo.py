"""Muestra y guarda el dibujo ASCII del grafo simulado."""

from pathlib import Path

from agentes.demo import crear_servicio_demo


def main():
    servicio = crear_servicio_demo()
    dibujo = servicio._graph.get_graph().draw_ascii()

    # Calcula la ruta desde el archivo, independientemente
    # de la carpeta desde la que ejecutes el comando.
    raiz = Path(__file__).resolve().parents[1]
    destino = raiz / "docs" / "specs" / "grafo_actual.txt"

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(dibujo, encoding="utf-8")

    print(dibujo)
    print(f"\nGuardado en: {destino}")


if __name__ == "__main__":
    main()