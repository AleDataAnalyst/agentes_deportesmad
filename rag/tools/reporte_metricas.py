import json
import math
from pathlib import Path
import sys, time

sys.path.insert(0, str(Path('.').resolve().parents[1]))
from rag.retrieve import recuperar_hibrido_debug

EVAL = Path('tests/evaluation_questions.json')
preguntas = json.loads(EVAL.read_text(encoding='utf-8'))

filas = []
for item in preguntas:
    pregunta = item['pregunta']
    esperada = item.get('fuente_esperada')
    fuera = bool(item.get('out_of_corpus'))
    t0 = time.perf_counter()
    resultado = recuperar_hibrido_debug(pregunta, top_k=5)
    latencia = time.perf_counter() - t0
    coseno = resultado['coseno']
    bm25 = resultado['bm25']
    rrf = resultado['rrf']

    def norm(t):
        return ' '.join(str(t).lower().split())

    def rank(chunks, att):
        if not att:
            return None
        for i, c in enumerate(chunks, 1):
            if att in norm(c.get('source', '')):
                return i
        return None

    e = norm(esperada) if esperada else None
    mc = min((c.get('distance', 1.0) for c in coseno), default=1.0)
    mb = max((c.get('bm25_score', 0.0) for c in bm25), default=0.0)
    mr = max((s.get('rrf_score', 0.0) for s in resultado['rrf_scores']), default=0.0)

    filas.append({
        'pregunta': pregunta,
        'esperada': esperada,
        'out_of_corpus': fuera,
        'rank_coseno': rank(coseno, e),
        'rank_bm25': rank(bm25, e),
        'rank_rrf': rank(rrf, e),
        'mejor_distancia': mc,
        'mejor_bm25': mb,
        'mejor_rrf': mr,
        'latencia_s': latencia
    })

total = len(filas)
oc = [f for f in filas if f['out_of_corpus']]
ic = [f for f in filas if not f['out_of_corpus']]


def hitk(rank_key, k):
    return sum(1 for f in ic if f[rank_key] is not None and f[rank_key] <= k) / len(ic) * 100 if ic else 0


mrr = {
    'coseno': sum(1 / f['rank_coseno'] for f in ic if f['rank_coseno']) / sum(1 for f in ic if f['rank_coseno'] is not None) * 100 if ic else 0,
    'bm25': sum(1 / f['rank_bm25'] for f in ic if f['rank_bm25']) / sum(1 for f in ic if f['rank_bm25'] is not None) * 100 if ic else 0,
    'rrf': sum(1 / f['rank_rrf'] for f in ic if f['rank_rrf'] is not None) / sum(1 for f in ic if f['rank_rrf'] is not None) * 100 if ic else 0,
}


def ndcg(rank_key, k):
    rels = [f for f in ic if f[rank_key] is not None]
    dcg = sum(1 / math.log2(f[rank_key] + 1) for f in rels if f[rank_key] <= k)
    nrel = len(rels)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(k, nrel))) if nrel > 0 else 0
    return dcg / idcg * 100 if idcg > 0 else 0


print('=== INFORME METRICAS RECUPERACION ===')
print(f'Total preguntas: {total} (in-corpus: {len(ic)}, out-of-corpus: {len(oc)})')
print()
print('Hit@1:')
print(f'  Cosino: {hitk("rank_coseno", 1):.1f}%')
print(f'  BM25:  {hitk("rank_bm25", 1):.1f}%')
print(f'  RRF:   {hitk("rank_rrf", 1):.1f}%')
print()
print('Hit@3:')
print(f'  Cosino: {hitk("rank_coseno", 3):.1f}%')
print(f'  BM25:  {hitk("rank_bm25", 3):.1f}%')
print(f'  RRF:   {hitk("rank_rrf", 3):.1f}%')
print()
print('Hit@5:')
print(f'  Cosino: {hitk("rank_coseno", 5):.1f}%')
print(f'  BM25:  {hitk("rank_bm25", 5):.1f}%')
print(f'  RRF:   {hitk("rank_rrf", 5):.1f}%')
print()
print(f'MRR: Cosino={mrr["coseno"]:.2f}%, BM25={mrr["bm25"]:.2f}%, RRF={mrr["rrf"]:.2f}%')
print(f'Distancia coseno media: {sum(f["mejor_distancia"] for f in filas) / len(filas):.6f}')
print(f'BM25 score medio: {sum(f["mejor_bm25"] for f in filas) / len(filas):.4f}')
print(f'RRF score medio: {sum(f["mejor_rrf"] for f in filas) / len(filas):.6f}')
print(f'Abstenciones correctas: {sum(1 for f in oc if f["rank_coseno"] is None and f["rank_bm25"] is None and f["rank_rrf"] is None) / len(oc) * 100:.1f}%')
print(f'Falsos positivos: {sum(1 for f in oc if f["rank_coseno"] is not None or f["rank_bm25"] is not None or f["rank_rrf"] is not None) / len(oc) * 100:.1f}%')
lats = sorted([f['latencia_s'] for f in filas])
p50 = lats[len(lats) // 2] * 1000
p95 = lats[int(len(lats) * 0.95) - 1] * 1000 if len(lats) > 0 else 0
print(f'Latencia p50: {p50:.1f}ms, p95: {p95:.1f}ms')

print()
print('=== INFORME POR FRASE (TODAS) ===')
print(f'{"#":<3} {"Pregunta":<55} {"Expected":<30} {"Out":<3} {"RankC":<6} {"RankB":<6} {"RankR":<6} {"Dist":<6} {"BM25":<6} {"RRF":<6} {"Latms":<7}')
print('-' * 145)
for i, f in enumerate(filas, 1):
    passed_c = 'OK' if f['rank_coseno'] == 1 else 'FAL'
    passed_b = 'OK' if f['rank_bm25'] == 1 else 'FAL'
    passed_r = 'OK' if f['rank_rrf'] == 1 else 'FAL'
    print(f'{i:<3} {f["pregunta"][:53]:<55} {str(f["esperada"])[:28]:<30} {str(f["out_of_corpus"]):<3} {str(f["rank_coseno"] or "-"):<6} {str(f["rank_bm25"] or "-"):<6} {str(f["rank_rrf"] or "-"):<6} {f["mejor_distancia"]:<6.4f} {f["mejor_bm25"]:<6.2f} {f["mejor_rrf"]:<6.4f} {f["latencia_s"]*1000:<7.1f}')