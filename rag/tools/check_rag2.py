import sys
sys.path.insert(0, r'.')
from pathlib import Path
from agentes.tools.rag import rag_preguntar

q2 = '¿Hay descuentos para familia numerosa?'
r2 = rag_preguntar(q2)
print('Q:', q2)
print('abstained:', r2['abstained'])
print('fuentes:', r2['fuentes'])
print('respuesta:', r2['respuesta'][:80])

print()

q5 = '¿Cómo se adquiere el Abono Deporte Madrid (ADM)?'
r5 = rag_preguntar(q5)
print('Q:', q5)
print('abstained:', r5['abstained'])
print('fuentes:', r5['fuentes'])
print('respuesta:', r5['respuesta'][:80])