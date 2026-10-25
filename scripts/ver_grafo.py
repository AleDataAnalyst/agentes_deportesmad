"""Exporta topología ASCII/Mermaid y una vista SVG del montaje inspeccionado.

Compila la demo con el mismo build_graph; no ejecuta pedidos ni importa el RAG.
El SVG es un esquema explicativo de clientes, controles y estado de integración.
"""

from pathlib import Path

from agentes.demo import crear_servicio_demo


def _vista_svg():
    """Vista documental; router, pausa y decisión se distinguen de los nodos."""
    partes = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1380" viewBox="0 0 1500 1380">
<title>Supervisor y grafo: clientes, montaje y revisión humana</title>
<desc>Flujo síncrono actual. Los especialistas y síntesis retornan al supervisor.
FINISH con plan listo conduce a la pausa antes de aplicar. CLI y Streamlit conectados.
Supervisor LLM o reglas e instalaciones conectados; aceptación real pendiente.
La imagen de Streamlit todavía no se envía al servicio.</desc>
<defs><marker id="flecha" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#43627e"/></marker>
<marker id="retorno" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#157a80"/></marker></defs>
<rect width="1500" height="1380" fill="#f5f8fc"/>
''']

    def texto(x, y, lineas, size=19, fill="#233c55", bold=False, center=False):
        from html import escape
        anchor = ' text-anchor="middle"' if center else ''
        weight = ' font-weight="700"' if bold else ''
        for i, linea in enumerate(lineas):
            partes.append(f'<text x="{x}" y="{y+i*(size+9)}" font-family="Arial, sans-serif" font-size="{size}" fill="{fill}"{weight}{anchor}>{escape(linea)}</text>')

    def caja(x, y, w, alto, titulo, lineas, color="#ffffff", borde="#9fb5c9", size=19):
        partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{alto}" rx="14" fill="{color}" stroke="{borde}" stroke-width="2"/>')
        texto(x+20, y+33, [titulo], 22, bold=True)
        texto(x+20, y+64, lineas, size)

    def flecha(d, regreso=False, discontinua=False):
        import math
        import re

        color = "#157a80" if regreso else "#43627e"
        dash = ' stroke-dasharray="8 6"' if discontinua else ''
        partes.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.8"{dash}/>')
        # Punta explícita: algunos rasterizadores SVG no interpretan marker-end.
        x = y = 0
        previo = (0, 0)
        for comando, a, b in re.findall(r'([MLHV])\s*(-?\d+)(?:\s+(-?\d+))?', d):
            previo = (x, y)
            if comando in ("M", "L"):
                x, y = float(a), float(b)
            elif comando == "H":
                x = float(a)
            else:
                y = float(a)
        dx, dy = x - previo[0], y - previo[1]
        longitud = math.hypot(dx, dy)
        ux, uy = dx / longitud, dy / longitud
        puntos = [(x, y), (x-12*ux-6*uy, y-12*uy+6*ux), (x-12*ux+6*uy, y-12*uy-6*ux)]
        partes.append(f'<polygon points="{" ".join(f"{a},{b}" for a,b in puntos)}" fill="{color}"/>')

    texto(55, 55, ["Supervisor y grafo: del pedido a la decisión"], 32, bold=True)
    texto(55, 90, ["Montaje #22 + #23 · 25/10/2026 · síncrono · aceptación con servicios reales pendiente"], 18)
    caja(65, 130, 610, 112, "CLI · conectada a runtime", ["Consultas, fuentes, debug y decisión HITL", "crear_servicio(modo=real)"], "#e5f4ed", "#5e9c7d")
    caja(825, 130, 610, 112, "Streamlit · conectado a runtime", ["Chat, fuentes, avisos por estado y decisión HITL", "JPG/PNG guardado; image_id aún no llega al agente"], "#e5f4ed", "#5e9c7d")
    flecha("M370 242 V265 H650 V285")
    flecha("M1130 242 V265 H850 V285")
    caja(420, 285, 660, 115, "AgentService · API común", ["Conserva instancia, thread_id y plan vigente", "procesar_turno / consultar_estado / resolver_plan"])
    flecha("M750 400 V440")
    texto(775, 428, ["START"], 16)
    caja(485, 440, 530, 105, "Supervisor · configuración desde runtime", ["LLM Google/Ollama o reglas; inyección manual", "Fallback y MAX_ITER controlados en Python"], "#e9edff", "#909bd1", 18)
    texto(750, 580, ["Router Python: valida destino y plan"], 18, bold=True, center=True)
    # Destinos alternativos. Los tres retornan al supervisor.
    flecha("M560 545 V605 H270 V650")
    flecha("M750 590 V650")
    flecha("M940 545 V605 H1230 V650")
    caja(65, 650, 410, 160, "Documental", ["Adaptador → puerta pública diferida", "→ nodo documental → tool RAG", "Mejoras de #21: por integrar", "Índice y aceptación real pendientes"], "#e9f2fc", "#6a9fcb", 18)
    caja(545, 650, 410, 160, "Instalaciones · conectado", ["Nodo público de catálogo y avisos", "Fuentes, error o abstención", "Conserva fallback histórico", "Aceptación externa pendiente"], "#e9f2fc", "#6a9fcb", 18)
    caja(1025, 650, 410, 160, "Sintetizar", ["Implementación determinista", "Respuesta + plan informativo", "Conserva fuentes y limitaciones", "No aprueba ni cierra"], "#e5f4ed", "#5e9c7d", 18)
    flecha("M65 730 H35 V495 H485", regreso=True)
    flecha("M545 775 H510 V635 H450 V520 H485", regreso=True)
    flecha("M1435 730 H1465 V495 H1015", regreso=True)
    texto(55, 850, ["Retornos al supervisor"], 18, "#157a80", bold=True)
    texto(55, 877, ["Documental, instalaciones y síntesis", "devuelven el control; no hay paralelismo."], 17)
    # Rama FINISH: pausa, decisión humana y aplicar.
    flecha("M1015 460 H1480 V915 H1140 V950")
    texto(1150, 910, ["FINISH + plan válido"], 18, bold=True)
    caja(825, 950, 610, 103, "PAUSA antes de aplicar", ["Checkpoint guardado · approved=None", "pendiente_hitl=True · done=False"], "#fff0e8", "#c98e6c", 18)
    flecha("M1130 1053 V1090")
    caja(825, 1090, 610, 102, "Decisión humana desde CLI / Streamlit", ["resolver_plan(hilo, bool, plan_id=...)", "update_state + invoke(None), mismo hilo"], "#fff0e8", "#c98e6c", 18)
    flecha("M825 1140 H745")
    caja(380, 1090, 365, 102, "Aplicar → END", ["Aprobar: done=True", "Rechazar: done=False"], "#e5f4ed", "#5e9c7d", 18)
    texto(55, 956, ["Controles importantes"], 23, bold=True)
    texto(55, 991, ["• FINISH sin plan válido → sintetizar.", "• Router, pausa y decisión son controles;", "  no son nodos extra de StateGraph.", "• Un rechazo permite otro pedido.", "• Estado en memoria del proceso."], 18)
    partes.append('<rect x="55" y="1230" width="1380" height="105" rx="12" fill="#e7eef6"/>')
    texto(75, 1260, ["Lectura de esta vista"], 20, bold=True)
    texto(75, 1291, ["Verde: retorno al supervisor. #21 conserva la topología; image_id y la aceptación multimodal siguen pendientes.", "Topología exportada con nodos demo: no acredita modelo, RAG ni HTTP reales. Visión no tiene ruta propia."], 18)
    partes.append('</svg>')
    return "\n".join(partes) + "\n"


def main():
    servicio = crear_servicio_demo()
    dibujo = servicio._graph.get_graph().draw_ascii()
    dibujo = "\n".join(linea.rstrip() for linea in dibujo.splitlines()) + "\n"

    # Calcula la ruta desde el archivo, independientemente
    # de la carpeta desde la que ejecutes el comando.
    raiz = Path(__file__).resolve().parents[1]
    destino = raiz / "docs" / "specs" / "grafo_actual.txt"

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(dibujo, encoding="utf-8", newline="\n")
    mermaid = destino.with_suffix(".mmd")
    mermaid.write_text(servicio._graph.get_graph().draw_mermaid().rstrip() + "\n", encoding="utf-8", newline="\n")
    visual = destino.with_name("grafo_visual.svg")
    visual.write_text(_vista_svg(), encoding="utf-8", newline="\n")

    print(dibujo)
    print(f"\nGuardado en: {destino}")
    print(f"Topología Mermaid: {mermaid}")
    print(f"Vista explicativa SVG: {visual}")


if __name__ == "__main__":
    main()
