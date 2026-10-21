# debug_rag.py — ejecuta: python debug_rag.py
from rag.logic import responder

fallidas = [
    "¿Cuánto cuesta el bono de piscina para el verano?",
    "¿Hay descuentos para personas en paro?",
    "¿Cuánto cuesta una entrada suelta (por día) para la piscina cubierta?",
    "¿Cuándo se puede cancelar una reserva sin que se aplige coste?",
    "¿El bono de piscina en verano es ilimitado o tiene un número máximo de días?",
]

for p in fallidas:
    r = responder(p)
    print("=" * 70)
    print("P:", p)
    print(" error     :", r["error"])
    print(" abstained :", r["abstained"])
    print(" fuentes   :", r["fuentes"])
    print(" respuesta :", (r["respuesta"] or "")[:150])
    if r["chunks"]:
        print(" mejor distance:", round(min(c["distance"] for c in r["chunks"]), 3))