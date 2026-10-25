import json
import sys
from pathlib import Path
sys.path.insert(0, r'E:\PROY_AGENTE_LANGGRAPH\agentes_deportesmad')

from agentes.tools.rag import rag_preguntar
from rag.logic import UMBRAL_ABSTENCION
import re

# Load evaluation questions
EVAL = Path('tests/evaluation_questions.json')
preguntas = json.loads(EVAL.read_text(encoding='utf-8'))

print("=== Probar preguntas de evaluación ===\n")

for item in preguntas:
    pregunta = item["pregunta"]
    out_of_corpus = bool(item.get("out_of_corpus"))
    fuente_esperada = item.get("fuente_esperada")
    
    r = rag_preguntar(pregunta)
    
    error = r.get("error")
    respuesta = r.get("respuesta", "")
    abstained = r.get("abstained", False)
    fuentes = r.get("fuentes", [])
    
    # Check expected source
    if fuente_esperada:
        esperada_norm = re.sub(r"\s+", " ", fuente_esperada).strip().lower()
        fuentes_norm = [re.sub(r"\s+", " ", str(f)).strip().lower() for f in fuentes]
        fuente_encontrada = any(esperada_norm in f for f in fuentes_norm)
    else:
        fuente_encontrada = True  # No source expected is OK
    
    status = "OK" if (
        (out_of_corpus and abstained) or
        (not out_of_corpus and respuesta and fuentes and fuente_encontrada and not error)
    ) else "FAIL"
    
    print(f"Q: {pregunta[:50]}...")
    print(f"  out_of_corpus={out_of_corpus}, abstained={abstained}")
    print(f"  respuesta={'OK' if respuesta else 'FAIL'}, fuentes={fuentes}")
    if fuente_esperada:
        print(f"  fuente_esperada={fuente_esperada}, encontrada={fuente_encontrada}")
    print(f"  --> {status}")
    print()