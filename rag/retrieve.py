"""
rag/retrieve.py

Recuperación semántica desde ChromaDB.

Responsabilidad:
    pregunta -> embedding de consulta -> búsqueda vectorial -> top-k resultados

Este módulo NO genera respuestas con un LLM.
Solo recupera contexto relevante para que generate.py / logic.py
puedan utilizarlo posteriormente.
"""

from typing import Any

from .config import CHROMA_DIR, COLLECTION_NAME
from .embed import embeddear_consulta
from .index import obtener_cliente_chroma, crear_coleccion

import re
from rank_bm25 import BM25Okapi
from nltk.stem import SnowballStemmer

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_stemmer = SnowballStemmer("spanish")
_RRF_K = 60

def _tokenizar(texto: str) -> list[str]:
    return [_stemmer.stem(t) for t in _TOKEN_RE.findall(texto.lower())]

_bm25_cache: tuple[BM25Okapi | None, list[str], list[str], list[dict]] | None = None

def _obtener_bm25(coleccion):
    """
    Construye (y cachea) el índice BM25 sobre los documentos de Chroma.
    Se construye una única vez por proceso a partir de coleccion.get().
    Devuelve una tupla (bm25, ids, docs, metas) donde:
      - bm25: el índice BM25Okapi (o None si no hay docs tokenizables)
      - ids:  lista de IDs Chroma en el mismo orden
      - docs: lista de documentos (texto) en el mismo orden
      - metas: lista de metadatas en el mismo orden

    El cache permite que las consultas posteriores no reconstruyan el índice.
    """
    global _bm25_cache
    if _bm25_cache is not None:
        return _bm25_cache

    res = coleccion.get(include=["documents", "metadatas"])
    ids: list[str] = res.get("ids") or []
    docs: list[str] = res.get("documents") or []
    metas: list[dict] = res.get("metadatas") or []

    # Tokeniza todo el corpus (una sola vez)
    corpus_tokens = [_tokenizar(d) for d in docs]

    # Solo los docs con tokens válidos entran en el BM25
    ok = [i for i, t in enumerate(corpus_tokens) if t]
    bm25: BM25Okapi | None = (
        BM25Okapi([corpus_tokens[i] for i in ok]) if ok else None
    )
    _bm25_cache = (bm25, ids, docs, metas)
    return _bm25_cache   # ← esta línea es la que suele faltar
    
def _rrf_fusion(rankings: list[list[str]]) -> list[str]:
    """
    Fusiona varios rankings (listas de IDs ordenados por relevancia)
    usando Reciprocal Rank Fusion.

    Para cada doc, suma 1/(k + posición) sobre todos los rankings donde
    aparece. Devuelve los IDs ordenados por score descendente.

    Args:
        rankings: lista de rankings, cada uno una lista de doc_ids.

    Returns:
        Lista de doc_ids fusionados, ordenados por score RRF descendente.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for pos, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (_RRF_K + pos)
    return sorted(scores, key=scores.get, reverse=True)


def recuperar_hibrido(
    pregunta: str,
    top_k: int = 5,
    candidatos: int = 50,
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Recuperación híbrida: vectorial + BM25 fusionada con RRF.

    1. Ranking vectorial (Chroma, top `candidatos`).
    2. Ranking BM25 (top `candidatos`).
    3. Fusión RRF → top_k final.

    Devuelve la misma forma que recuperar(): lista de dicts con
    text, source, metadata y distance.
    """
    
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que 0.")

    coleccion = obtener_coleccion(persist_dir, collection_name)
    total = coleccion.count()
    if total == 0:
        return []

    # BM25 cache (IDs fiables, vienen de coleccion.get())
    bm25, corpus_ids, corpus_docs, corpus_metas = _obtener_bm25(coleccion)

    # Mapeo: texto de doc -> ID (para resolver IDs del query vectorial)
    # doc_a_id: dict[str, str] = {}
    # for cid, cdoc in zip(corpus_ids, corpus_docs):
    #     if cdoc not in doc_a_id:
    #         doc_a_id[cdoc] = cid

    # 1) Ranking vectorial
    n_vec = min(candidatos, total)
    embedding = embeddear_consulta(pregunta)
    res = coleccion.query(
        query_embeddings=[embedding],
        n_results=n_vec,
        include=["documents", "metadatas", "distances"],
    )
    
    ids_vec: list[str] = res.get("ids", [[]])[0]
    # docs_vec = res.get("documents", [[]])[0]
    dists_vec: list[float] = res.get("distances", [[]])[0]

    ranking_vector: list[str] = list(ids_vec)
    dists: dict[str, float] = dict(zip(ids_vec, dists_vec))

    # 2) Ranking BM25
    ranking_bm25: list[str] = []
    if bm25 is not None:
        scores = bm25.get_scores(_tokenizar(pregunta))
        ranking_bm25 = [
            corpus_ids[i]
            for i in sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
        ][:candidatos]

    # 3) RRF
    fusionado = _rrf_fusion([ranking_vector, ranking_bm25])[:top_k]

    # 4) Mapear IDs -> dicts (misma forma que recuperar())
    por_id: dict[str, tuple[str, dict]] = {}
    for cid, cdoc, cmeta in zip(corpus_ids, corpus_docs, corpus_metas):
        por_id[cid] = (cdoc, cmeta)

    out: list[dict[str, Any]] = []
    for doc_id in fusionado:
        cdoc, cmeta = por_id.get(doc_id, (None, None))
        if cdoc is None:
            continue
        cmeta = cmeta or {}
        out.append({
            "text": cdoc,
            "source": cmeta.get("source", "desconocido"),
            "metadata": cmeta,
            "distance": dists.get(doc_id, 1.0),
        })
    return out


def obtener_coleccion(
    persist_dir: str | None = None,
    collection_name: str | None = None,
):
    """
    Abre la colección persistente de ChromaDB utilizada por el índice.

    Args:
        persist_dir: directorio de Chroma. Si no se indica, usa CHROMA_DIR.
        collection_name: nombre de la colección. Si no se indica,
                         usa COLLECTION_NAME.

    Returns:
        Colección ChromaDB.
    """
    client = obtener_cliente_chroma(persist_dir or CHROMA_DIR)
    return crear_coleccion(
        client,
        collection_name or COLLECTION_NAME,
    )


def recuperar(
    pregunta: str,
    top_k: int = 5,
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Recupera los chunks más similares a una pregunta.

    Flujo:
        1. Genera embedding de la pregunta.
        2. Consulta ChromaDB mediante similitud vectorial.
        3. Devuelve los top-k resultados.

    Args:
        pregunta: consulta del usuario.
        top_k: número máximo de chunks a recuperar.
        persist_dir: directorio de ChromaDB.
        collection_name: colección que se consulta.

    Returns:
        Lista de diccionarios con:
            - text: contenido del chunk
            - source: fuente del chunk
            - metadata: metadata completa
            - distance: distancia devuelta por Chroma

    Raises:
        ValueError: si la pregunta está vacía o top_k no es válido.
    """

    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")

    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que 0.")

    # Embedding de consulta usando exactamente el mismo proveedor/modelo
    # configurado para los embeddings del índice.
    embedding = embeddear_consulta(pregunta.strip())

    collection = obtener_coleccion(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )

    if collection.count() == 0:
        return []

    # No tiene sentido pedir más resultados de los que existen.
    n_resultados = min(top_k, collection.count())

    resultado = collection.query(
        query_embeddings=[embedding],
        n_results=n_resultados,
        include=["documents", "metadatas", "distances"],
    )

    documents = resultado.get("documents", [[]])[0]
    metadatas = resultado.get("metadatas", [[]])[0]
    distances = resultado.get("distances", [[]])[0]

    recuperados: list[dict[str, Any]] = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        metadata = metadata or {}

        recuperados.append(
            {
                "text": document,
                "source": metadata.get("source", "desconocido"),
                "metadata": metadata,
                "distance": float(distance),
            }
        )

    return recuperados