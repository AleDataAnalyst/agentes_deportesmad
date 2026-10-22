"""
rag/retrieve.py
Pipeline de recuperación híbrida (vectorial + BM25) para el
corpus del Ayuntamiento de Madrid.

Responsabilidades:
- Construir el índice BM25 y DEVOLVERLO (antes no lo devolvía).
- Construir el índice vectorial (Chroma).
- Fusionar ambos con RRF y devolver top-k.
No genera respuestas (eso es prompts.py / generate.py).
"""
from __future__ import annotations

#import os
import re
import tempfile
#import json
from typing import Any

import rank_bm25

import chromadb
from rag.index import obtener_cliente_chroma
from .config import COLLECTION_NAME

def _tokenizar(texto: str) -> list[str]:
    """Tokenización simple multilingüe para BM25."""
    return re.findall(r"\w+", texto.lower(), flags=re.UNICODE)

def _resolver_nombre(collection_name: str | None) -> str:
    """Devuelve el nombre real de la colección, nunca None."""
    return collection_name if collection_name is not None else COLLECTION_NAME

def obtener_coleccion(
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> chromadb.CollectionAPI:
    """
    Solo ABRIR la colección existente — NUNCA la crea.

    Si collection_name es None, se usa el nombre configurado
    (COLLECTION_NAME). Así Chroma nunca recibe None.
    """
    if collection_name is None:
        collection_name = COLLECTION_NAME
    client = obtener_cliente_chroma(persist_dir)
    return client.get_collection(name=collection_name)

def _rrf_fusion(rankings: list[list[dict]], top_k: int) -> list[dict]:
    """
    RAngo de fusión dsobre N rangos.

    score(i) = sum(1 / (k + pos_i))
    """
    combined: dict[int, dict] = {}
    k = 60

    for ranking in rankings:
        for pos, chunk in enumerate(ranking):
            cid = id(chunk)

            if cid not in combined:
                combined[cid] = {
                    "score": 0.0,
                    "chunk": chunk,
                }

            combined[cid]["score"] += 1.0 / (k + pos)

    ordered = sorted(
        combined.values(),
        key=lambda item: item["score"],
        reverse=True,
    )

    return [item["chunk"] for item in ordered[:top_k]]


def recuperar_hibrido(
    pregunta: str,
    top_k: int = 5,
    candidatos: int = 50,
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que 0.")

    collection_name = _resolver_nombre(collection_name)

    coleccion = obtener_coleccion(persist_dir, collection_name)
    if coleccion.count() == 0:
        return []

    vector = VectorRetriever(persist_dir, collection_name).search(
        pregunta,
        top_k=candidatos,
        candidates=candidatos,
    )
    
    bm25 = BM25Retriever(persist_dir, collection_name).search(
        pregunta,
        top_k=candidatos,
    )
    
    return _rrf_fusion([vector, bm25], top_k)


def recuperar(
    pregunta: str,
    top_k: int = 5,
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> list[dict]:
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no debe estar vacía.")
    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que 0.")

    collection_name = _resolver_nombre(collection_name)

    coleccion = obtener_coleccion(persist_dir, collection_name)
    if coleccion.count() == 0:
        return []

    return VectorRetriever(persist_dir, collection_name).search(
        pregunta, top_k=top_k, candidates=top_k
    )

# ---------------------------------------------------------------------------
# Retrievers
# ---------------------------------------------------------------------------

class VectorRetriever:
    """Recupera chunks por similitud coseno en Chroma."""

    def __init__(self, persist_dir: str | None, collection_name: str):
        self._client = obtener_cliente_chroma(persist_dir)
        self._collection = self._client.get_collection(
            name=collection_name
        )

    def _ordenar(self, hits: dict, top_k: int) -> list[dict]:
        """
        Convierte la respuesta de Chroma en una lista de chunks normalizada.
    
        Chroma devuelve listas paralelas:
        ids[0], documents[0], metadatas[0], distances[0]
        """
        if not hits or not hits.get("ids"):
            return []
    
        ids = hits["ids"][0]
        documents = hits.get("documents", [[]])[0]
        metadatas = hits.get("metadatas", [[]])[0]
        distances = hits.get("distances", [[]])[0]
    
        resultados: list[dict] = []
    
        for i in range(min(len(ids), top_k)):
            metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            texto = documents[i] if i < len(documents) and documents[i] else ""
    
            source = (
                metadata.get("source")
                or metadata.get("fuente")
                or metadata.get("file")
                or ""
            )
    
            resultados.append(
                {
                    "text": texto,
                    "source": source,
                    "metadata": metadata,
                    "distance": distances[i] if i < len(distances) else None,
                }
            )
    
        return resultados

    def search(self, query: str, top_k: int, candidates: int) -> list[dict]:
        hits = self._collection.query(
            query_embeddings=[self._embed_query(query)],
            n_results=candidates,
        )
        return self._ordenar(hits, candidates)
    
    def _embed_query(self, query: str) -> list[float]:
        """Vectoriza la consulta en el MISMO espacio que el índice.

        Reutiliza `embeddear()` como puerta única de embeddings: la consulta
        queda en el mismo proveedor/modelo/dimensión que los documentos
        indexados, así las distancias coseno de Chroma tienen sentido
        (in-corp ~0.43-0.55, out-of-corp >0.73).
        """
        from .embed import embeddear
        return embeddear([query])[0]


class BM25Retriever:
    """Recuperación dispersa BM25 construida desde los documentos de Chroma."""

    def __init__(self, persist_dir: str | None, collection_name: str):
        self._client = obtener_cliente_chroma(persist_dir)
        self._collection = self._client.get_collection(name=collection_name)

        self._bm25 = None
        self._docs: list[str] = []
        self._metas: list[dict] = []

        self._cargar()

    def _cargar(self) -> None:
        total = self._collection.count()
        if total == 0:
            return

        resultado = self._collection.get(
            include=["documents", "metadatas"]
        )

        self._docs = list(resultado.get("documents") or [])
        self._metas = list(resultado.get("metadatas") or [])

        corpus_tokens = [_tokenizar(doc) for doc in self._docs]
        self._bm25 = rank_bm25.BM25Okapi(corpus_tokens)

    def search(self, query: str, top_k: int) -> list[dict]:
        if self._bm25 is None or not self._docs:
            return []

        query_tokens = _tokenizar(query)
        scores = self._bm25.get_scores(query_tokens)

        orden = sorted(
            range(len(self._docs)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        resultados: list[dict] = []

        for i in orden:
            metadata = self._metas[i] if i < len(self._metas) else {}
            source = (
                metadata.get("source")
                or metadata.get("fuente")
                or metadata.get("file")
                or ""
            )

            resultados.append(
                {
                    "text": self._docs[i],
                    "source": source,
                    "metadata": metadata,
                    # En BM25, mayor puntuación = mejor.
                    "distance": float(scores[i]),
                }
            )

        return resultados