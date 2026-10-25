import sys
sys.path.insert(0, r'E:\PROY_AGENTE_LANGGRAPH\agentes_deportesmad')

from rag.load import cargar_archivos
from rag.config import CHUNK_SIZE, CHUNK_OVERLAP
from rag.chunk import trocear
from pathlib import Path

documents = cargar_archivos(str(Path('data/corpus')))
chunks = trocear(documents, CHUNK_SIZE, CHUNK_OVERLAP)

# Find chunks that come from the TAB PDFs
for i, chunk in enumerate(chunks):
    src = chunk.metadata.get('source', '')
    if 'Piscinas' in src or 'PreciosPublicos' in src:
        print(f"--- Chunk {i} from {src} ---")
        print(f"Content: {chunk.page_content}")
        print(f"Metadata: {chunk.metadata}")
        print()