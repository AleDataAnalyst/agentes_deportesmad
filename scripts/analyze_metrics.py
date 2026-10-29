import json
import math
from pathlib import Path
from statistics import median

# Load evaluation data
EVAL = Path("tests/evaluation_questions.json")
preguntas = json.loads(EVAL.read_text(encoding="utf-8"))

# Add project to path and import rag modules
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.config import COLLECTION_NAME, RETRIEVAL_MODE, TOP_K
from rag.retrieve import recuperar_hibrido_debug

TOP_K = 5

def normalizar(texto):
    return " ".join(str(texto).lower().split())

def rank_de_fuente(chunks, fuente_esperada):
    if not fuente_esperada:
        return None
    esperada = normalizar(fuente_esperada)
    for i, chunk in enumerate(chunks, start=1):
        if esperada in normalizar(chunk.get("source", "")):
            return i
    return None

filas = []
for item in preguntas:
    pregunta = item["pregunta"]
    esperada = item.get("fuente_esperada")
    fuera = bool(item.get("out_of_corpus"))
    
    import time
    t0 = time.perf_counter()
    resultado = recuperar_hibrido_debug(pregunta, top_k=TOP_K)
    latencia = time.perf_counter() - t0
    
    coseno = resultado["coseno"]
    bm25 = resultado["bm25"]
    rrf = resultado["rrf"]
    
    mejor_dist = min(
        (c.get("distance", 1.0) for c in coseno),
        default=1.0,
    )
    
    mejor_bm25 = max(
        (c.get("bm25_score", 0.0) for c in bm25),
        default=0.0,
    )
    
    mejor_rrf = max(
        (s.get("rrf_score", 0.0) for s in resultado["rrf_scores"]),
        default=0.0,
    )
    
    filas.append({
        "pregunta": pregunta,
        "esperada": esperada,
        "out_of_corpus": fuera,
        "rank_coseno": rank_de_fuente(coseno, esperada),
        "rank_bm25": rank_de_fuente(bm25, esperada),
        "rank_rrf": rank_de_fuente(rrf, esperada),
        "mejor_distancia": mejor_dist,
        "mejor_bm25": mejor_bm25,
        "mejor_rrf": mejor_rrf,
        "latencia_s": latencia,
    })

# Now compute metrics
total = len(filas)
out_of_corpus = [f for f in filas if f["out_of_corpus"]]
in_corpus = [f for f in filas if not f["out_of_corpus"]]

# 1. Hit@1
hit1_coseno = sum(1 for f in in_corpus if f["rank_coseno"] == 1) / len(in_corpus) * 100 if in_corpus else 0
hit1_bm25 = sum(1 for f in in_corpus if f["rank_bm25"] == 1) / len(in_corpus) * 100 if in_corpus else 0
hit1_rrf = sum(1 for f in in_corpus if f["rank_rrf"] == 1) / len(in_corpus) * 100 if in_corpus else 0

# 2. Hit@k / Recall@k for k=3,5
for k in [3, 5]:
    hitk_coseno = sum(1 for f in in_corpus if f["rank_coseno"] is not None and f["rank_coseno"] <= k) / len(in_corpus) * 100 if in_corpus else 0
    hitk_bm25 = sum(1 for f in in_corpus if f["rank_bm25"] is not None and f["rank_bm25"] <= k) / len(in_corpus) * 100 if in_corpus else 0
    hitk_rrf = sum(1 for f in in_corpus if f["rank_rrf"] is not None and f["rank_rrf"] <= k) / len(in_corpus) * 100 if in_corpus else 0
    print(f"Hit@{k}: Cosino={hitk_coseno:.1f}%, BM25={hitk_bm25:.1f}%, RRF={hitk_rrf:.1f}%")

# 3. MRR
rr_coseno = sum(1 / f["rank_coseno"] for f in in_corpus if f["rank_coseno"] is not None) / len([f for f in in_corpus if f["rank_coseno"] is not None]) if in_corpus else 0
rr_bm25 = sum(1 / f["rank_bm25"] for f in in_corpus if f["rank_bm25"] is not None) / len([f for f in in_corpus if f["rank_bm25"] is not None]) if in_corpus else 0
rr_rrf = sum(1 / f["rank_rrf"] for f in in_corpus if f["rank_rrf"] is not None) / len([f for f in in_corpus if f["rank_rrf"] is not None]) if in_corpus else 0
mrr_coseno = rr_coseno * 100
mrr_bm25 = rr_bm25 * 100
mrr_rrf = rr_rrf * 100
print(f"MRR: Cosino={mrr_coseno:.2f}%, BM25={mrr_bm25:.2f}%, RRF={mrr_rrf:.2f}%")

# 4. nDCG@k
# DCG uses discount log2(1 + position), position is 1-indexed
for k in [3, 5]:
    dcg_coseno = sum(
        (1 / math.log2(f["rank_coseno"] + 1) if f["rank_coseno"] is not None and f["rank_coseno"] <= k else 0)
        for f in in_corpus
    )
    n_relevant = sum(1 for f in in_corpus if f["rank_coseno"] is not None)
    # IDCG: assume best case - first n_relevant items at positions 1..n_relevant
    # discount for position p (1-indexed) is log2(1 + p) = log2(p + 1)
    # with 0-indexed i, position = i + 1, so discount = log2((i+1)+1) = log2(i + 2)
    idcg_coseno = sum(1 / math.log2(i + 2) for i in range(min(k, n_relevant))) if n_relevant > 0 else 0
    ndcg_coseno = dcg_coseno / idcg_coseno * 100 if idcg_coseno > 0 else 0
    
    dcg_bm25 = sum(
        (1 / math.log2(f["rank_bm25"] + 1) if f["rank_bm25"] is not None and f["rank_bm25"] <= k else 0)
        for f in in_corpus
    )
    n_relevant = sum(1 for f in in_corpus if f["rank_bm25"] is not None)
    idcg_bm25 = sum(1 / math.log2(i + 2) for i in range(min(k, n_relevant))) if n_relevant > 0 else 0
    ndcg_bm25 = dcg_bm25 / idcg_bm25 * 100 if idcg_bm25 > 0 else 0
    
    dcg_rrf = sum(
        (1 / math.log2(f["rank_rrf"] + 1) if f["rank_rrf"] is not None and f["rank_rrf"] <= k else 0)
        for f in in_corpus
    )
    n_relevant = sum(1 for f in in_corpus if f["rank_rrf"] is not None)
    idcg_rrf = sum(1 / math.log2(i + 2) for i in range(min(k, n_relevant))) if n_relevant > 0 else 0
    ndcg_rrf = dcg_rrf / idcg_rrf * 100 if idcg_rrf > 0 else 0
    
    print(f"nDCG@{k}: Cosino={ndcg_coseno:.2f}%, BM25={ndcg_bm25:.2f}%, RRF={ndcg_rrf:.2f}%")

# 5. Average cosine distance
avg_dist = sum(f["mejor_distancia"] for f in filas) / len(filas)
print(f"Distancia coseno media: {avg_dist:.6f}")

# 6. Average BM25 score
avg_bm25 = sum(f["mejor_bm25"] for f in filas) / len(filas)
print(f"BM25 score medio: {avg_bm25:.4f}")

# 7. Average RRF score
avg_rrf = sum(f["mejor_rrf"] for f in filas) / len(filas)
print(f"RRF score medio: {avg_rrf:.6f}")

# 8. Correct abstentions
correct_abstentions = sum(1 for f in out_of_corpus if f["rank_coseno"] is None and f["rank_bm25"] is None and f["rank_rrf"] is None) / len(out_of_corpus) * 100 if out_of_corpus else 0
correct_abst = sum(1 for f in out_of_corpus if f["rank_coseno"] is None and f["rank_bm25"] is None and f["rank_rrf"] is None) / len(out_of_corpus) * 100 if out_of_corpus else 0
print(f"Abstenciones correctas: {correct_abst:.1f}%")

# 9. False positives
falsos_positivos = sum(1 for f in out_of_corpus if f["rank_coseno"] is not None or f["rank_bm25"] is not None or f["rank_rrf"] is not None) / len(out_of_corpus) * 100 if out_of_corpus else 0
falsos_pos = sum(1 for f in out_of_corpus if f["rank_coseno"] is not None or f["rank_bm25"] is not None or f["rank_rrf"] is not None) / len(out_of_corpus) * 100 if out_of_corpus else 0
print(f"Falsos positivos: {falsos_pos:.1f}%")

# 10. Latency p50/p95
lats = sorted([f["latencia_s"] for f in filas])
p50 = lats[len(lats)//2] * 1000  # convert to ms
p95_idx = int(len(lats) * 0.95) - 1
p95 = lats[max(0, p95_idx)] * 1000  # convert to ms
print(f"Latencia p50: {p50:.1f}ms, p95: {p95:.1f}ms")

# Print summary table
print("\n=== RESUMEN COMPLETO ===")
print(f"{'Meta':<25} {'Cosino':<12} {'BM25':<12} {'RRF':<12}")
print(f"{'Hit@1':<25} {hit1_coseno:<12.1f} {hit1_bm25:<12.1f} {hit1_rrf:<12.1f}")
print(f"{'MRR':<25} {mrr_coseno:<12.2f} {mrr_bm25:<12.2f} {mrr_rrf:<12.2f}")
print(f"{'nDCG@5':<25} {ndcg_coseno:<12.2f} {ndcg_bm25:<12.2f} {ndcg_rrf:<12.2f}")
print(f"{'DistCos media':<25} {avg_dist:<12.6f} {'':<12} {'':<12}")
print(f"{'BM25 media':<25} {'':<12} {avg_bm25:<12.4f} {'':<12}")
print(f"{'RRF media':<25} {'':<12} {'':<12} {avg_rrf:<12.6f}")
print(f"{'Abstenciones OK':<25} {correct_abstentions:<12.1f} {'':<12} {'':<12}")
print(f"{'Falsos Positivos':<25} {'':<12} {falsos_positivos:<12.1f} {'':<12}")
print(f"{'Latencia p50/p95':<25} {p50:<12.1f} {'':<12} {'':<12} p95={p95:.1f}ms")

# Detailed per-phrase report
print("\n=== INFORME POR FRASE (TODAS) ===")
print(f"{'#':<3} {'Pregunta':<55} {'Expected':<30} {'Out':<3} {'RankC':<6} {'RankB':<6} {'RankR':<6} {'Dist':<6} {'BM25':<6} {'RRF':<6} {'Latms':<7}")
print("-" * 145)
for i, f in enumerate(filas, 1):
    print(f"{i:<3} {f['pregunta'][:53]:<55} {str(f['esperada'])[:28]:<30} {str(f['out_of_corpus']):<3} {str(f['rank_coseno'] or '-'):<6} {str(f['rank_bm25'] or '-'):<6} {str(f['rank_rrf'] or '-'):<6} {f['mejor_distancia']:<6.4f} {f['mejor_bm25']:<6.2f} {f['mejor_rrf']:<6.4f} {f['latencia_s']*1000:<7.1f}")