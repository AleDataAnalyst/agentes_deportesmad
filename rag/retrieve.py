"""Recuperación híbrida: Chroma vectorial + BM25, fusionada con RRF.

`recuperar()` devuelve chunks vectoriales.
`recuperar_hibrido()` devuelve la lista final fusionada por RRF.
`recuperar_hibrido_debug()` devuelve además los rankings intermedios y los
scores RRF, para evaluación y generación del informe TEST de recuperación.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Any

import chromadb
import rank_bm25

from rag.index import obtener_cliente_chroma
from .config import COLLECTION_NAME


RRF_K = 60


def _tokenizar(texto: str) -> list[str]:
    return re.findall(r"\w+", texto.lower(), flags=re.UNICODE)


def _resolver_nombre(collection_name: str | None) -> str:
    return collection_name if collection_name is not None else COLLECTION_NAME


def obtener_coleccion(
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> chromadb.CollectionAPI:
    """Abre una colección existente; nunca la crea."""
    collection_name = _resolver_nombre(collection_name)
    client = obtener_cliente_chroma(persist_dir)
    return client.get_collection(name=collection_name)


def _chunk_key(chunk: dict[str, Any]) -> str:
    """Identificador estable para fusionar el mismo chunk entre rankings."""
    metadata = chunk.get("metadata") or {}
    source = chunk.get("source") or metadata.get("source") or ""
    chunk_id = metadata.get("chunk_id", metadata.get("doc_id"))

    if chunk_id is not None:
        return f"{source}::{chunk_id}"

    text = chunk.get("text") or ""
    return hashlib.sha256(f"{source}::{text}".encode("utf-8")).hexdigest()


def _rrf_fusion(
    rankings: list[list[dict[str, Any]]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Fusiona rankings por Reciprocal Rank Fusion y devuelve solo chunks."""
    fusion = _rrf_fusion_debug(rankings, top_k)
    return fusion["chunks"]


def _rrf_fusion_debug(
    rankings: list[list[dict[str, Any]]],
    top_k: int,
) -> dict[str, Any]:
    """Fusiona rankings por RRF conservando chunks y scores explicables.

    Cada ranking aporta `1 / (RRF_K + posicion)`. Un chunk presente en varios
    rankings acumula score. La posición es 0-based, igual que en la versión
    original.
    """
    combined: dict[str, dict[str, Any]] = {}

    for ranking in rankings:
        for pos, chunk in enumerate(ranking):
            cid = _chunk_key(chunk)

            if cid not in combined:
                combined[cid] = {
                    "score": 0.0,
                    "chunk": chunk,
                    "apariciones": 0,
                    "posiciones": [],
                }

            combined[cid]["score"] += 1.0 / (RRF_K + pos)
            combined[cid]["apariciones"] += 1
            combined[cid]["posiciones"].append(pos)

    ordered = sorted(
        combined.items(),
        key=lambda item: item[1]["score"],
        reverse=True,
    )[:top_k]

    chunks: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []

    for cid, data in ordered:
        chunk = data["chunk"]
        chunks.append(chunk)

        scores.append(
            {
                "chunk_key": cid,
                "rrf_score": round(data["score"], 8),
                "apariciones": data["apariciones"],
                "posiciones": data["posiciones"],
                "source": chunk.get("source", ""),
                "distance": chunk.get("distance"),
                "bm25_score": chunk.get("bm25_score"),
            }
        )

    return {
        "chunks": chunks,
        "scores": scores,
    }


@lru_cache(maxsize=8)
def _obtener_bm25(
    persist_dir: str | None,
    collection_name: str,
) -> "BM25Retriever":
    """Cachea el índice BM25 por colección para no reconstruirlo por consulta."""
    return BM25Retriever(persist_dir, collection_name)


def recuperar_hibrido(
    pregunta: str,
    top_k: int = 5,
    candidatos: int = 50,
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """Recupera candidatos vectoriales y BM25, y los fusiona con RRF.

    Mantiene el contrato usado por `rag/logic.py::responder`: devuelve una
    lista plana de chunks.
    """
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

    bm25 = _obtener_bm25(persist_dir, collection_name).search(
        pregunta,
        top_k=candidatos,
    )

    return _rrf_fusion([vector, bm25], top_k)


def recuperar_hibrido_debug(
    pregunta: str,
    top_k: int = 5,
    candidatos: int = 50,
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> dict[str, Any]:
    """Versión de evaluación: devuelve coseno, BM25, RRF y scores RRF.

    No sustituye a `recuperar_hibrido()` en producción: su salida es un dict,
    no la lista de chunks que espera el pipeline RAG.
    """
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")

    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que 0.")

    collection_name = _resolver_nombre(collection_name)
    coleccion = obtener_coleccion(persist_dir, collection_name)

    if coleccion.count() == 0:
        return {
            "coseno": [],
            "bm25": [],
            "rrf": [],
            "rrf_scores": [],
        }

    vector = VectorRetriever(persist_dir, collection_name).search(
        pregunta,
        top_k=candidatos,
        candidates=candidatos,
    )

    bm25 = _obtener_bm25(persist_dir, collection_name).search(
        pregunta,
        top_k=candidatos,
    )

    fusion = _rrf_fusion_debug([vector, bm25], top_k)

    return {
        "coseno": vector[:top_k],
        "bm25": bm25[:top_k],
        "rrf": fusion["chunks"],
        "rrf_scores": fusion["scores"],
    }


def recuperar(
    pregunta: str,
    top_k: int = 5,
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """Recuperación solo vectorial por distancia/similitud coseno."""
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no debe estar vacía.")

    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que 0.")

    collection_name = _resolver_nombre(collection_name)
    coleccion = obtener_coleccion(persist_dir, collection_name)

    if coleccion.count() == 0:
        return []

    return VectorRetriever(persist_dir, collection_name).search(
        pregunta,
        top_k=top_k,
        candidates=top_k,
    )


class VectorRetriever:
    """Recupera chunks por similitud/distancia coseno en Chroma."""

    def __init__(self, persist_dir: str | None, collection_name: str):
        self._client = obtener_cliente_chroma(persist_dir)
        self._collection = self._client.get_collection(name=collection_name)

    def _ordenar(self, hits: dict, top_k: int) -> list[dict[str, Any]]:
        if not hits or not hits.get("ids"):
            return []

        ids = hits["ids"][0]
        documents = hits.get("documents", [[]])[0]
        metadatas = hits.get("metadatas", [[]])[0]
        distances = hits.get("distances", [[]])[0]

        resultados: list[dict[str, Any]] = []

        for i in range(min(len(ids), top_k)):
            metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            texto = documents[i] if i < len(documents) and documents[i] else ""

            source = (
                metadata.get("source")
                or metadata.get("fuente")
                or metadata.get("file")
                or ""
            )

            distance = distances[i] if i < len(distances) else None

            resultados.append(
                {
                    "id": ids[i],
                    "text": texto,
                    "source": source,
                    "metadata": metadata,
                    "distance": distance,
                    # Compatibilidad con consumidores que esperan `score`.
                    # En Chroma con espacio coseno, menor distancia = más cercano.
                    "score": (1.0 - distance) if distance is not None else None,
                }
            )

        return resultados

    def search(self, query: str, top_k: int, candidates: int) -> list[dict[str, Any]]:
        hits = self._collection.query(
            query_embeddings=[self._embed_query(query)],
            n_results=candidates,
        )
        return self._ordenar(hits, candidates)

    def _embed_query(self, query: str) -> list[float]:
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
        if self._collection.count() == 0:
            return

        resultado = self._collection.get(
            include=["documents", "metadatas"]
        )

        self._docs = list(resultado.get("documents") or [])
        self._metas = list(resultado.get("metadatas") or [])

        corpus_tokens = [_tokenizar(doc) for doc in self._docs]
        self._bm25 = rank_bm25.BM25Okapi(corpus_tokens)

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self._bm25 is None or not self._docs:
            return []

        query_tokens = _tokenizar(query)
        scores = self._bm25.get_scores(query_tokens)

        orden = sorted(
            range(len(self._docs)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        resultados: list[dict[str, Any]] = []

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
                    "id": metadata.get("chunk_id", metadata.get("doc_id")),
                    "text": self._docs[i],
                    "source": source,
                    "metadata": metadata,
                    "bm25_score": float(scores[i]),
                    "score": float(scores[i]),
                }
            )

        return resultados