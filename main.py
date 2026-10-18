"""Punto de entrada de la CLI del PB02.

Delega el arranque en clientes.cli.
No debe contener lógica de agentes, herramientas ni configuración del RAG.
Dependencia prevista: clientes/cli.py.
"""

from clientes.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
