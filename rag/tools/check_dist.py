def normalizar(texto):
    return " ".join(str(texto).lower().split())

import sys
sys.path.insert(0, r'.')
from rag.retrieve import recuperar_hibrido_debug

pregunta = '¿Cuánto cuesta el bono de piscina de verano y cuantas sesiones tiene?'
resultado = recuperar_hibrido_debug(pregunta, top_k=5)

coseno = resultado['coseno']
bm25 = resultado['bm25']

def norm(t):
    return ' '.join(str(t).lower().split())

# Check if PreciosPublicos2026 appears in cosine results
for i, c in enumerate(coseno, 1):
    src = normalizar(c.get('source', ''))
    d = c.get('distance')
    print(f'Coseno #{i}: source={src}, distance={d}')

print()

# Check BM25
for i, c in enumerate(bm25, 1):
    src = normalizar(c.get('source', ''))
    s = c.get('bm25_score')
    print(f'BM25 #{i}: source={src}, bm25_score={s}')