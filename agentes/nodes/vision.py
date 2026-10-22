from agentes.state import AgentState
from agentes.tools import imagen_preguntar


def vision_node(state: AgentState) -> dict:
    pregunta = state.get("user_message", "")

    resultado = imagen_preguntar.invoke(
        {
            "image_id": "assets/imagen_demo.jpg",
            "pregunta": pregunta,
        }
    )

    specialist_results = dict(state.get("specialist_results", {}))
    specialist_results["vision"] = resultado

    return {
        "specialist_results": specialist_results,
        "debug_trace": ["vision: imagen analizada"],
    }
    
    
    