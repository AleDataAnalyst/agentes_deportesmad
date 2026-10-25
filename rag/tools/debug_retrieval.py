import sys
sys.path.insert(0, r'.')
from pathlib import Path
from rag.load import cargar_archivos
from rag.chunk import trocear
from rag.retrieve import recuperar_hibrido_debug

docs = cargar_archivos(str(Path('data/corpus')))
chunks = trocear(docs, 1356, 150)

# Check chunks from PreciosPublicos2026
print("=== Chunks from PreciosPublicos2026.md ===")
for i, chunk in enumerate(chunks):
    src = chunk.metadata.get('source', '')
    if 'PreciosPublicos' in src:
        print(f"Chunk {i}:")
        print(f"  Full content: {chunk.page_content}")
        print(f"  Metadata: {chunk.metadata}")
        print()

print()
print("=== Testing retrieval for pool bonus question ===")
pregunta = '¿Cuánto cuesta el bono de piscina de verano y cuantas sesiones tiene?'
resultado = recuperar_hibrido_debug(pregunta, top_k=5)
coseno = resultado['coseno']
bm25 = resultado['bm25']
rrf = resultado['rrf']

def norm(t): return ' '.join(str(t).lower().split())

print("Cosene results (top 5):")
for i, c in enumerate(coseno, 1):
    src = norm(c.get('source', ''))
    d = c.get('distance')
    print(f"  {i}. {src} (dist={d:.4f})")

print("BM25 results (top 5):")
for i, c in enumerate(bm25, 1):
    src = norm(c.get('source', ''))
    s = c.get('bm25_score')
    print(f"  {i}. {src} (bm25={s:.2f})")

print("RRF results (top 5):")
for i, s in enumerate(rrf['scores'], 1):
    src = norm(s.get('source', ''))
    rrf_s = s.get('rrf_score')
    print(f"  {i}. {src} (rrf={rrf_s:.4f})")