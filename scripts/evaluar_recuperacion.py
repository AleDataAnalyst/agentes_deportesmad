"""Informe TEST de recuperación: coseno, BM25 y RRF.

Ejecución desde la raíz del proyecto:

    python -m scripts.evaluar_recuperacion

Requiere:
- Índice ChromaDB ya generado.
- tests/evaluation_questions.json con este formato:

[
  {
    "pregunta": "¿Cuánto cuesta el abono anual?",
    "out_of_corpus": false,
    "fuente_esperada": "tarifas.pdf"
  }
]
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.config import (
    COLLECTION_NAME,
    RETRIEVAL_MODE,
    TOP_K,
)
from rag.logic import UMBRAL_ABSTENCION
from rag.retrieve import recuperar_hibrido_debug

EVAL_PATH = Path("tests/evaluation_questions.json")
OUTPUT_DIR = Path("output")
CANDIDATOS = 50


def _normalizar(texto: Any) -> str:
    return " ".join(str(texto or "").lower().split())


def _rank_de_fuente(
    chunks: list[dict[str, Any]],
    fuente_esperada: str | None,
) -> int | None:
    """Devuelve la posición 1-based de la primera fuente esperada."""
    if not fuente_esperada:
        return None

    esperada = _normalizar(fuente_esperada)

    for posicion, chunk in enumerate(chunks, start=1):
        fuente = _normalizar(chunk.get("source", ""))

        if esperada and esperada in fuente:
            return posicion

    return None


def _hit_at_k(rank: int | None, k: int) -> int:
    return int(rank is not None and 1 <= rank <= k)


def _reciprocal_rank(rank: int | None) -> float:
    return 1.0 / rank if rank else 0.0


def _dcg(rank: int | None, k: int) -> float:
    if rank is None or rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def _idcg(k: int) -> float:
    return sum(1.0 / math.log2(i + 1) for i in range(1, k + 1))


def _percentil(valores: list[float], percentil: float) -> float | None:
    if not valores:
        return None

    ordenados = sorted(valores)
    indice = round((len(ordenados) - 1) * percentil)
    return ordenados[indice]


def _evaluar_pregunta(
    item: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    pregunta = item["pregunta"]
    esperada = item.get("fuente_esperada")
    fuera_de_corpus = bool(item.get("out_of_corpus"))

    inicio = time.perf_counter()
    resultado = recuperar_hibrido_debug(
        pregunta,
        top_k=top_k,
        candidatos=CANDIDATOS,
    )
    latencia = time.perf_counter() - inicio

    coseno = resultado["coseno"]
    bm25 = resultado["bm25"]
    rrf = resultado["rrf"]
    rrf_scores = resultado["rrf_scores"]

    rank_coseno = _rank_de_fuente(coseno, esperada)
    rank_bm25 = _rank_de_fuente(bm25, esperada)
    rank_rrf = _rank_de_fuente(rrf, esperada)

    mejor_distancia = min(
        (chunk.get("distance", 1.0) for chunk in coseno),
        default=1.0,
    )

    mejor_bm25 = max(
        (chunk.get("bm25_score", 0.0) for chunk in bm25),
        default=0.0,
    )

    mejor_rrf = max(
        (score.get("rrf_score", 0.0) for score in rrf_scores),
        default=0.0,
    )

    abstencion_coseno = mejor_distancia > UMBRAL_ABSTENCION

    if fuera_de_corpus:
        resultado_coseno = "abstencion_correcta" if abstencion_coseno else "falso_positivo"
        resultado_bm25 = (
            "abstencion_correcta"
            if rank_bm25 is None
            else "falso_positivo"
        )
        resultado_rrf = (
            "abstencion_correcta"
            if rank_rrf is None
            else "falso_positivo"
        )
    else:
        resultado_coseno = "ok" if rank_coseno else "fallo"
        resultado_bm25 = "ok" if rank_bm25 else "fallo"
        resultado_rrf = "ok" if rank_rrf else "fallo"

    return {
        "pregunta": pregunta,
        "fuente_esperada": esperada,
        "out_of_corpus": fuera_de_corpus,
        "rank_coseno": rank_coseno,
        "rank_bm25": rank_bm25,
        "rank_rrf": rank_rrf,
        "mejor_distancia_coseno": round(mejor_distancia, 6),
        "mejor_bm25_score": round(mejor_bm25, 6),
        "mejor_rrf_score": round(mejor_rrf, 8),
        "abstencion_coseno": abstencion_coseno,
        "resultado_coseno": resultado_coseno,
        "resultado_bm25": resultado_bm25,
        "resultado_rrf": resultado_rrf,
        "latencia_s": round(latencia, 6),
        "n_coseno": len(coseno),
        "n_bm25": len(bm25),
        "n_rrf": len(rrf),
    }


def _resumen(
    filas: list[dict[str, Any]],
    metodo: str,
    top_k: int,
) -> dict[str, Any]:
    in_corpus = [fila for fila in filas if not fila["out_of_corpus"]]
    fuera = [fila for fila in filas if fila["out_of_corpus"]]

    if not in_corpus:
        raise ValueError("El conjunto de evaluación no tiene preguntas in-corpus.")

    ranks = [fila[f"rank_{metodo}"] for fila in in_corpus]
    latencias = [fila["latencia_s"] for fila in filas]

    idcg = _idcg(top_k)

    return {
        "metodo": metodo,
        "n_preguntas": len(filas),
        "n_in_corpus": len(in_corpus),
        "n_out_of_corpus": len(fuera),
        "hit_at_1": round(
            sum(_hit_at_k(rank, 1) for rank in ranks) / len(in_corpus),
            4,
        ),
        f"hit_at_{top_k}": round(
            sum(_hit_at_k(rank, top_k) for rank in ranks) / len(in_corpus),
            4,
        ),
        "mrr": round(
            sum(_reciprocal_rank(rank) for rank in ranks) / len(in_corpus),
            4,
        ),
        f"ndcg_at_{top_k}": round(
            sum(_dcg(rank, top_k) for rank in ranks) / (len(in_corpus) * idcg),
            4,
        ),
        "abstenciones_correctas": sum(
            1 for fila in fuera
            if fila[f"resultado_{metodo}"] == "abstencion_correcta"
        ),
        "falsos_positivos": sum(
            1 for fila in fuera
            if fila[f"resultado_{metodo}"] == "falso_positivo"
        ),
        "latencia_p50_s": _percentil(latencias, 0.50),
        "latencia_p95_s": _percentil(latencias, 0.95),
    }


def _tabla_resumen(resumenes: list[dict[str, Any]], top_k: int) -> list[str]:
    lineas = [
        "| Estrategia | Hit@1 | Hit@" + str(top_k) + " | MRR | nDCG@" + str(top_k)
        + " | Abstenciones correctas | Falsos positivos | p50 | p95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for resumen in resumenes:
        p50 = resumen["latencia_p50_s"]
        p95 = resumen["latencia_p95_s"]

        lineas.append(
            f"| {resumen['metodo'].upper()} "
            f"| {resumen['hit_at_1']:.2%} "
            f"| {resumen[f'hit_at_{top_k}']:.2%} "
            f"| {resumen['mrr']:.4f} "
            f"| {resumen[f'ndcg_at_{top_k}']:.4f} "
            f"| {resumen['abstenciones_correctas']}/{resumen['n_out_of_corpus']} "
            f"| {resumen['falsos_positivos']} "
            f"| {p50 * 1000:.1f} ms "
            f"| {p95 * 1000:.1f} ms |"
        )

    return lineas


def _tabla_por_pregunta(filas: list[dict[str, Any]], top_k: int) -> list[str]:
    lineas = [
        "| Pregunta | Esperada | Tipo | Coseno rank | BM25 rank | RRF rank "
        "| Mejor distancia | BM25 score | RRF score | Coseno | BM25 | RRF |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]

    for fila in filas:
        tipo = "fuera" if fila["out_of_corpus"] else "corpus"

        lineas.append(
            f"| {_normalizar(fila['pregunta'])[:90]} "
            f"| {_normalizar(fila['fuente_esperada']) or '—'} "
            f"| {tipo} "
            f"| {fila['rank_coseno'] or '—'} "
            f"| {fila['rank_bm25'] or '—'} "
            f"| {fila['rank_rrf'] or '—'} "
            f"| {fila['mejor_distancia_coseno']:.4f} "
            f"| {fila['mejor_bm25_score']:.4f} "
            f"| {fila['mejor_rrf_score']:.6f} "
            f"| {fila['resultado_coseno']} "
            f"| {fila['resultado_bm25']} "
            f"| {fila['resultado_rrf']} |"
        )

    return lineas


def _diagnostico(
    filas: list[dict[str, Any]],
    resumenes: list[dict[str, Any]],
    top_k: int,
) -> list[str]:
    por_metodo = {item["metodo"]: item for item in resumenes}
    coseno = por_metodo["coseno"]
    bm25 = por_metodo["bm25"]
    rrf = por_metodo["rrf"]

    lineas: list[str] = []

    if rrf["hit_at_1"] > coseno["hit_at_1"]:
        mejora = (rrf["hit_at_1"] - coseno["hit_at_1"]) * 100
        lineas.append(
            f"- **RRF mejora Hit@1 frente a coseno en {mejora:.1f} puntos porcentuales.**"
        )
    elif rrf["hit_at_1"] < coseno["hit_at_1"]:
        perdida = (coseno["hit_at_1"] - rrf["hit_at_1"]) * 100
        lineas.append(
            f"- **RRF empeora Hit@1 frente a coseno en {perdida:.1f} puntos porcentuales.**"
        )
    else:
        lineas.append("- **RRF y coseno empatan en Hit@1.**")

    if bm25["falsos_positivos"] > rrf["falsos_positivos"]:
        lineas.append(
            "- **BM25 tiene más falsos positivos en preguntas fuera de corpus:** "
            "su coincidencia léxica no garantiza evidencia semánticamente pertinente."
        )

    if rrf["falsos_positivos"] == 0:
        lineas.append(
            "- **RRF no introduce falsos positivos** en el conjunto actual."
        )

    if rrf["latencia_p95_s"] > coseno["latencia_p95_s"] * 1.5:
        lineas.append(
            "- **El híbrido RRF aumenta notablemente la latencia p95:** "
            "valora si la mejora de ranking justifica el coste."
        )

    fallos_rrf = [
        fila for fila in filas
        if not fila["out_of_corpus"] and fila["rank_rrf"] is None
    ]

    if fallos_rrf:
        lineas.append(
            f"- **{len(fallos_rrf)} preguntas in-corpus no recuperan la fuente esperada con RRF** "
            f"en los primeros {top_k} resultados."
        )

    if not lineas:
        lineas.append("- Sin observaciones automáticas relevantes.")

    return lineas


def generar_informe_recuperacion(
    top_k: int = TOP_K,
    eval_path: Path = EVAL_PATH,
) -> Path:
    if not eval_path.exists():
        raise FileNotFoundError(f"No existe el conjunto de evaluación: {eval_path}")

    items = json.loads(eval_path.read_text(encoding="utf-8"))

    if not items:
        raise ValueError("El conjunto de evaluación está vacío.")

    filas = [_evaluar_pregunta(item, top_k) for item in items]

    resumenes = [
        _resumen(filas, "coseno", top_k),
        _resumen(filas, "bm25", top_k),
        _resumen(filas, "rrf", top_k),
    ]

    fecha = datetime.now(timezone.utc).astimezone()
    nombre = f"informe_retrieval_{fecha:%Y%m%d_%H%M}.md"
    ruta_informe = OUTPUT_DIR / nombre
    ruta_jsonl = OUTPUT_DIR / nombre.replace(".md", ".jsonl")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lineas = [
        "# Informe TEST de recuperación",
        "",
        f"- **Fecha:** {fecha:%Y-%m-%d %H:%M:%S}",
        f"- **Colección:** `{COLLECTION_NAME}`",
        f"- **Modo configurado:** `{RETRIEVAL_MODE}`",
        f"- **TOP_K:** {top_k}",
        f"- **Candidatos por consulta:** {CANDIDATOS}",
        f"- **RRF_K:** 60",
        f"- **Umbral de abstención coseno:** {UMBRAL_ABSTENCION}",
        f"- **Preguntas evaluadas:** {len(items)}",
        "",
        "## 1. Criterios",
        "",
        "- **Hit@1:** la fuente esperada aparece en la primera posición.",
        f"- **Hit@{top_k}:** la fuente esperada aparece entre los primeros {top_k} resultados.",
        "- **MRR:** media del inverso de la posición de la primera fuente correcta.",
        f"- **nDCG@{top_k}:** calidad del ranking, dando más peso a las posiciones altas.",
        "- **Coseno:** menor distancia implica mayor cercanía semántica.",
        "- **BM25 y RRF:** mayor score implica mejor posición o mayor consenso entre rankings.",
        "- **Abstención correcta:** pregunta fuera de corpus sin evidencia admitida.",
        "- **Falso positivo:** pregunta fuera de corpus para la que el método devuelve evidencia.",
        "",
        "## 2. Resumen global",
        "",
        *_tabla_resumen(resumenes, top_k),
        "",
        "## 3. Resultados por pregunta",
        "",
        *_tabla_por_pregunta(filas, top_k),
        "",
        "## 4. Diagnóstico automático",
        "",
        *_diagnostico(filas, resumenes, top_k),
        "",
        "## 5. Criterios de decisión",
        "",
        "- Mantener **RRF** si mejora Hit@1, MRR o nDCG sin aumentar falsos positivos.",
        "- Usar **coseno puro** si RRF no aporta mejora relevante y aumenta latencia.",
        "- Revisar **BM25** si domina en consultas literales pero falla en formulaciones semánticas.",
        "- Ajustar `UMBRAL_ABSTENCION` si hay falsos positivos o abstenciones incorrectas.",
        "- Revisar chunking, metadatos de fuente o corpus si varias preguntas in-corpus fallan en los tres métodos.",
        "",
    ]

    ruta_informe.write_text("\n".join(lineas), encoding="utf-8")

    with ruta_jsonl.open("w", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    return ruta_informe


if __name__ == "__main__":
    ruta = generar_informe_recuperacion()
    print(f"Informe generado: {ruta}")