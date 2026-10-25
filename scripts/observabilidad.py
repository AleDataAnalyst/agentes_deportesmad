#!/usr/bin/env python3
"""scripts/observabilidad.py - Informe de observabilidad RAG (mínimo)."""

import sys
import json
import os
from pathlib import Path

# Registrar el directorio del proyecto para importaciones
proj = str(Path(__file__).resolve().parents[1])
if proj not in sys.path:
    sys.path.insert(0, proj)

from rag.config import (
    ABSTENTION_MESSAGE,
    TOP_K,
    MAX_CHUNKS,
    RETRIEVAL_MODE,
    GEN_MAX_TOKENS,
    GEN_TIMEOUT,
    DEDUP_UMBRAL,
    COSINE_SPACE,
    COLLECTION_NAME,
    CHROMA_DIR,
)


try:
    from agents.tools.rag import rag_preguntar
    HAS_AGENT = True
except ModuleNotFoundError:
    HAS_AGENT = False


def main() -> None:
    """Punto de entrada: imprime estado actual del pipeline."""
    # Cargar preguntas de evaluación
    eval_path = Path("tests/evaluation_questions.json")
    if eval_path.exists():
        preguntas = json.loads(eval_path.read_text(encoding="utf-8"))
    else:
        print("❌ No se encuentra evaluation_questions.json")
        return

    total = len(preguntas)
    out_corpus = [p for p in preguntas if bool(p.get("out_of_corpus"))]
    in_corpus = [p for p in preguntas if not bool(p.get("out_of_corpus"))]

    print("=" * 50)
    print("REPORTE RÁPIDO - Pipeline RAG")
    print("=" * 50)
    print(f"Preguntas: {total} (in-corpus: {len(in_corpus)}, out-of-corpus: {len(out_corpus)})")
    print(f"Modo recuperación: {RETRIEVAL_MODE}")
    print(f"Top-K: {TOP_K}")
    print(f"Espacio similitud: {COSINE_SPACE}")
    print(f"Colección: {COLLECTION_NAME}")
    print(f"Dir Chroma: {CHROMA_DIR}")
    env_count = len([k for k in os.environ if k.startswith('RAG_') or k.startswith('EMBED_') or k.startswith('GEN_')])
    print(f"Variables .env detectadas: {env_count}")
    print(f"Agente disponible: {HAS_AGENT}")
    print()

    # Probar algunas preguntas con el agente si está disponible
    if HAS_AGENT:
        print("=== Pruebas de agente RAG ===")
        exitos = abstenciones = errores = 0

        for item in preguntas[:5]:
            pregunta = item["pregunta"]
            out_corpus = bool(item.get("out_of_corpus"))

            try:
                import time as _time
                t0 = _time.perf_counter()
                resp = rag_preguntar(pregunta)
                t1 = _time.perf_counter()
                lat = t1 - t0
            except Exception as e:
                resp = {"error": str(e), "abstained": False, "respuesta": "", "fuentes": []}
                lat = 0

            error = resp.get("error")
            abst = resp.get("abstained", False)
            fs = resp.get("fuentes", [])

            if out_corpus and abst:
                abstenciones += 1
                print(f"  [OUT] {pregunta[:40]:40s} -> abstención OK")
            elif not out_corpus and resp.get("respuesta") and fs:
                exitos += 1
                print(f"  [IN]  {pregunta[:40]:40s} -> respuesta OK")
            else:
                errores += 1
                print(f"  [?]   {pregunta[:40]:40s} -> problema")

        print()
        print(f"Tasa éxito: {exitos/len(preguntas)*100:.1f} %")
        print(f"Abstenciones out-of-corpus: {abstenciones}/{len(out_corpus)}")
    else:
        print("(Agente RAG no disponible - pule pruebas de agente)")
        print("(Instale o verifique el paquete 'agents' para habilitar pruebas)")

    print("=" * 50)


if __name__ == "__main__":
    main()