"""Sonda de TAG, sin indexación. Selección explícita; un subproceso por perfil.

--doble sustituye todo HTTP/hardware y bloquea sockets: no mide rendimiento real.
No importa pipeline/index/retrieve ni lee el .env del usuario.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import ctypes
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import types
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {name: ROOT / f"config/perfiles/rag_{name}.env.example"
            for name in ("ligero", "27b_acotado", "hector")}
CASES_PATH = Path(__file__).with_name("benchmark_rag_tag_casos.json")
RAG_KEYS = frozenset("""EMBED_PROVIDER OLLAMA_EMBED_MODEL EMBED_DIM EMBED_BATCH_SIZE
EMBED_TIMEOUT GEN_PROVIDER OLLAMA_GEN_MODEL GEN_TIMEOUT TAG_PROVIDER OLLAMA_TAG_MODEL
OLLAMA_BASE_URL CHUNK_SIZE CHUNK_OVERLAP TAG_SCORING_DEDUP DEDUP_UMBRAL DEDUP_AUDIT
DEDUP_AUDIT_RUTA EXPORT_EMBEDDINGS TOP_K MAX_CHUNKS RAG_RETRIEVAL_MODE CHROMA_DIR
COLLECTION_NAME""".split())
BENCH_KEYS = {"BENCH_MODE", "BENCH_TAG_NUM_CTX", "BENCH_TAG_NUM_PREDICT",
              "BENCH_TAG_TEMPERATURE", "BENCH_TAG_TIMEOUT"}
METRICS = ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
           "eval_count", "eval_duration", "prompt_eval_cached_count")


def write_new(path, value):
    def safe_numbers(item):
        if isinstance(item, float) and not math.isfinite(item):
            return {"non_finite_number": str(item)}
        if isinstance(item, dict):
            return {key: safe_numbers(v) for key, v in item.items()}
        if isinstance(item, list):
            return [safe_numbers(v) for v in item]
        return item
    with path.open("x", encoding="utf-8") as stream:
        json.dump(safe_numbers(value), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def profile_values(name):
    """Formato cerrado KEY=value, sin interpolar secretos ni leer .env."""
    values = {}
    for line in PROFILES[name].read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key not in RAG_KEYS | BENCH_KEYS or key in values:
            raise ValueError("Clave desconocida/duplicada o formato inválido en perfil")
        values[key] = value.strip().strip('"').strip("'")
    if not RAG_KEYS <= values.keys() or values.get("BENCH_MODE") not in {"adapter", "experimental"}:
        raise ValueError("Perfil incompleto")
    assert values["OLLAMA_BASE_URL"] == "http://127.0.0.1:11434", "Solo Ollama local sin credenciales"
    assert all(values[k] == "ollama" for k in ("TAG_PROVIDER", "GEN_PROVIDER", "EMBED_PROVIDER"))
    assert values["OLLAMA_EMBED_MODEL"] == "qwen3-embedding:0.6b" and values["EMBED_DIM"] == "1024"
    expected_extra = BENCH_KEYS if values["BENCH_MODE"] == "experimental" else {"BENCH_MODE"}
    assert values.keys() - RAG_KEYS == expected_extra
    if values["BENCH_MODE"] == "experimental":
        assert int(values["BENCH_TAG_NUM_CTX"]) > 0 and int(values["BENCH_TAG_NUM_PREDICT"]) > 0
        assert 0 < float(values["BENCH_TAG_TIMEOUT"]) <= 300
        assert math.isfinite(float(values["BENCH_TAG_TEMPERATURE"]))
    return values


def child_environment(values):
    # Solo infraestructura para Python/Windows; no hereda tokens, proxies ni RAG.
    infrastructure = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "TEMP", "TMP",
                      "LD_LIBRARY_PATH", "SYSTEMDRIVE", "HOME", "USERPROFILE", "HOMEDRIVE",
                      "HOMEPATH", "LOCALAPPDATA", "APPDATA"}
    result = {k: v for k, v in os.environ.items() if k.upper() in infrastructure}
    result.update({k: v for k, v in values.items() if k in RAG_KEYS})
    result.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                  HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    return result


def import_tag():
    # rag.__init__ importa logic/retrieve/index/Chroma. Se carga el MISMO fuente
    # de TAG bajo un paquete aislado para no ejecutar esos efectos laterales.
    for name, folder in (("_rag_benchmark", ROOT / "rag"),
                         ("_rag_benchmark.tsd", ROOT / "rag/tsd")):
        package = types.ModuleType(name)
        package.__path__ = [str(folder)]
        package.__package__ = name
        sys.modules[name] = package
    spec = importlib.util.spec_from_file_location("_rag_benchmark.tsd.tag", ROOT / "rag/tsd/tag.py")
    tag = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tag
    # Solo proceso hijo: evita que config complete valores desde .env.
    guard = patch("dotenv.load_dotenv", return_value=False) if importlib.util.find_spec("dotenv") else contextlib.nullcontext()
    with guard:
        spec.loader.exec_module(tag)
    return tag


def hardware(fake=False):
    if fake:
        return {"simulated": True, "gpus": [{"name": "GPU DOBLE", "total_mib": 6144,
                "used_mib": 1024, "free_mib": 5120}], "ram": {"total_bytes": 64 * 2**30, "available_bytes": 40 * 2**30}}
    result = {"simulated": False, "gpus": None, "ram": None}
    try:
        command = ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            result["gpus"] = [{"name": row[0].strip(), "total_mib": int(row[1]),
                               "used_mib": int(row[2]), "free_mib": int(row[3])}
                              for row in csv.reader(io.StringIO(proc.stdout)) if row]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    try:
        if os.name == "nt":
            class Memory(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (key, ctypes.c_ulonglong) for key in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
            memory = Memory()
            memory.length = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                result["ram"] = {"total_bytes": memory.total, "available_bytes": memory.available}
        elif Path("/proc/meminfo").is_file():
            fields = {line.split(":")[0]: int(line.split()[1]) * 1024
                      for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith(("MemTotal:", "MemAvailable:"))}
            result["ram"] = {"total_bytes": fields["MemTotal"], "available_bytes": fields["MemAvailable"]}
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    return result


def repository_state():
    def git(*args):
        return subprocess.run(["git", "-c", "safe.directory=" + ROOT.as_posix(), *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=10)
    try:
        commit, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
        return {"commit": commit.stdout.strip() if commit.returncode == 0 else None,
                "dirty": bool(status.stdout) if status.returncode == 0 else None}
    except (OSError, subprocess.TimeoutExpired):
        return {"commit": None, "dirty": None}


def assess(raw, case, tag, response, fallback_observed=False):
    """Calidad por ejes; nunca convierte un fallback en clasificación correcta."""
    result = {"json_valid": False, "parser_accepts": False, "schema_valid": False,
              "taxonomy_valid": False, "category_correct": False, "semantic_status": "fail",
              "fallback_observed": fallback_observed, "fallback_required": True,
              "truncation": True if response.get("done_reason") in {"length", "max_tokens"} else False if response.get("done_reason") == "stop" else None,
              "response_complete": response.get("done") is True and response.get("done_reason") == "stop"}
    try:
        def reject_constant(value):
            raise ValueError("Constante no JSON")
        result["json_valid"] = isinstance(json.loads(raw, parse_constant=reject_constant), dict)
    except (ValueError, TypeError):
        pass
    try:
        parsed = tag._parse_json(raw)
        result["interpreted"] = parsed
        result["parser_accepts"] = isinstance(parsed, dict)
    except (ValueError, TypeError, AttributeError) as exc:
        result["parser_error_type"] = type(exc).__name__
        parsed = None
    if isinstance(parsed, dict):
        category, tags, score = parsed.get("categoria"), parsed.get("tags"), parsed.get("relevancia")
        strings = isinstance(tags, list) and all(isinstance(t, str) for t in tags)
        result["schema_valid"] = {"categoria", "tags", "relevancia"} <= parsed.keys() and strings and 0 < len(tags) <= 8 and isinstance(score, (float, int)) and not isinstance(score, bool) and math.isfinite(score) and 0 <= score <= 1
        result["taxonomy_valid"] = category in tag.CATEGORIAS_VALIDAS if isinstance(category, str) else False
        result["taxonomy_valid"] &= strings and all(t in tag.TAGS_VALIDAS for t in tags)
        result["category_correct"] = category == case["expected_category"]
        result["fallback_required"] = not {"categoria", "tags", "relevancia"} <= parsed.keys() or not isinstance(category, str) or category not in tag.CATEGORIAS_VALIDAS
        if strings:
            result["supported_tags"] = [t for t in tags if t in case["supported_tags"]]
            result["unjustified_tags"] = [t for t in tags if t in case["unjustified_tags"]]
            result["review_tags"] = [t for t in tags if t not in case["supported_tags"] + case["unjustified_tags"]]
            if result["category_correct"] and tags and not result["unjustified_tags"]:
                result["semantic_status"] = "human_review" if result["review_tags"] else "pass"
    result["passed"] = all(result[k] for k in ("json_valid", "parser_accepts", "schema_valid", "taxonomy_valid", "category_correct", "response_complete")) and result["semantic_status"] == "pass" and not result["fallback_observed"] and not result["fallback_required"] and not result["truncation"]
    return result


class FakeTransport:
    """Doble explícito de todo HTTP. Solo se activa con --doble."""
    def __init__(self, cases, models):
        self.cases, self.models, self.loaded = cases, models, False
        self.scenario = "valid"

    def get(self, url, **kwargs):
        if url.endswith("/api/version"):
            return {"version": "DOBLE-NO-REAL"}
        if url.endswith("/api/tags"):
            return {"models": [{"name": m, "digest": "digest-doble", "size": 100} for m in self.models]}
        if url.endswith("/api/ps"):
            return {"models": [{"name": m, "size_vram": 100, "context_length": 4096} for m in self.models] if self.loaded else []}
        raise AssertionError("GET inesperado en doble")

    def post(self, url, **kwargs):
        import requests
        assert url.endswith("/api/chat")
        payload = kwargs["json"]
        assert "keep_alive" not in payload and "think" not in payload and "format" not in payload
        if self.scenario == "timeout":
            raise requests.ReadTimeout("doble")
        if self.scenario == "http_error":
            response = requests.Response()
            response.status_code = 500
            return response
        case = next(c for c in self.cases if c["text"] in payload["messages"][0]["content"])
        raw = json.dumps({"categoria": case["expected_category"], "tags": case["supported_tags"][:2], "relevancia": 0.8}, ensure_ascii=False)
        if self.scenario == "malformed":
            raw = '{"categoria":'
        if self.scenario == "missing_category":
            raw = '{"tags": [], "relevancia": 0.5}'
        self.loaded = True
        data = {"model": payload["model"], "message": {"role": "assistant", "content": raw},
                "done": True, "done_reason": "length" if self.scenario == "truncated" else "stop",
                "total_duration": 1000000, "load_duration": 100000, "eval_count": 20,
                "eval_duration": 500000, "prompt_eval_count": 100, "prompt_eval_duration": 400000}
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(data).encode()
        return response


def model_identity(model):
    return {key: model[key] for key in ("name", "model", "digest", "size", "capabilities") if key in model} | {
        "details": {key: model.get("details", {}).get(key) for key in ("family", "parameter_size", "quantization_level")}}


def installed_selection(models, selected):
    by_name = {m.get("name", m.get("model")): m for m in models}
    return ({m: model_identity(by_name[m]) for m in sorted(selected) if m in by_name},
            sorted(selected - by_name.keys()))


def resident_state(get, base, model):
    try:
        models = get(base + "/api/ps", timeout=10)["models"]
        return {"known": True, "selected_loaded": any(m.get("name", m.get("model")) == model for m in models),
                "residents": [{k: m[k] for k in ("name", "model", "size", "size_vram", "context_length") if k in m} for m in models]}
    except Exception as exc:
        return {"known": False, "error_type": type(exc).__name__}


def run_case(case, values, tag, post, get, fake):
    from langchain_core.documents import Document
    record = {"case": case["id"], "expected": case, "experimental": values["BENCH_MODE"] == "experimental",
              "request": None, "response": None, "error": None, "timeout": False}
    base, model = values["OLLAMA_BASE_URL"], values["OLLAMA_TAG_MODEL"]
    record["prior_model_state"] = resident_state(get, base, model)
    record["hardware_before"] = hardware(fake)

    def observed_post(url, **kwargs):
        # Observa el transporte original: no añade opciones al adaptador.
        record["request"] = {"endpoint": "/api/chat", "payload": kwargs["json"], "timeout_seconds": kwargs["timeout"]}
        response = post(url, **kwargs)
        record["http_status"] = response.status_code
        response.raise_for_status()
        data = response.json()
        record["response"] = {k: data[k] for k in ("model", "done", "done_reason", *METRICS) if k in data}
        record["response"]["message"] = {k: data.get("message", {}).get(k) for k in ("role", "content", "thinking")}
        return response

    log = io.StringIO()
    start = time.perf_counter()
    try:
        if record["experimental"]:
            payload = {"model": model, "stream": False,
                       "messages": [{"role": "user", "content": tag.PROMPT.replace("{text}", case["text"][:8000])}],
                       "options": {"num_ctx": int(values["BENCH_TAG_NUM_CTX"]),
                                   "num_predict": int(values["BENCH_TAG_NUM_PREDICT"]),
                                   "temperature": float(values["BENCH_TAG_TEMPERATURE"])}}
            observed_post(base + "/api/chat", json=payload, timeout=float(values["BENCH_TAG_TIMEOUT"]))
        else:
            with patch.object(tag.requests, "post", side_effect=observed_post), contextlib.redirect_stdout(log):
                docs = tag.etiquetar([Document(page_content=case["text"], metadata={"source": case["id"]})])
                record["adapter_metadata"] = docs[0].metadata
    except Exception as exc:
        import requests
        # No guarda URLs, rutas, cabeceras ni mensajes de error del servidor.
        record["error"] = {"type": type(exc).__name__}
        record["timeout"] = isinstance(exc, requests.Timeout)
    record["seconds"] = round(time.perf_counter() - start, 6)
    record["adapter_log"] = log.getvalue()
    fallback = any(marker in record["adapter_log"] for marker in ("JSON malformado", "fuera de taxonomía"))
    data = record["response"] or {}
    raw = data.get("message", {}).get("content") or ""
    record["quality"] = assess(raw, case, tag, data, fallback_observed=fallback)
    if not record["experimental"] and "adapter_metadata" in record and record["quality"]["fallback_required"]:
        record["quality"]["fallback_observed"] = True  # También defaults silenciosos.
    record["quality"]["passed"] &= record["error"] is None
    record["fallback_scope"] = "observed_real_adapter" if not record["experimental"] else "no_fallback_applied_isolated_parser"
    return record


def offline_checks(tag, transport, values, cases):
    """Regresiones de calidad y fallos de transporte con el adaptador real."""
    case = cases[0]
    complete = {"done": True, "done_reason": "stop"}
    def quality(obj, case=case, response=complete):
        return assess(json.dumps(obj), case, tag, response)
    good = {"categoria": "tarifas", "tags": ["precio"], "relevancia": 0.8}
    assert quality(good)["passed"]
    assert not quality(good, response={"done": True, "done_reason": "length"})["passed"]
    assert not assess('{"categoria":', case, tag, complete)["passed"]
    assert not quality(good | {"categoria": "agenda"})["passed"]
    assert not quality(good | {"tags": ["etiqueta_desconocida"]})["taxonomy_valid"]
    assert not quality(good | {"relevancia": float("nan")})["json_valid"]
    assert not quality(good | {"relevancia": 1.5})["schema_valid"]
    assert quality(good | {"tags": ["horario"]})["semantic_status"] == "human_review"
    assert quality(good | {"tags": ["empadronado"]})["semantic_status"] == "fail"
    assert quality({"tags": [], "relevancia": 0.5})["fallback_required"]
    installed, missing = installed_selection([], {"modelo_no_instalado"})
    assert not installed and missing == ["modelo_no_instalado"]
    fenced = assess("```json\n" + json.dumps(good) + "\n```", case, tag, complete)
    assert fenced["parser_accepts"] and not fenced["json_valid"]
    # Comprueba que no se acepta la categoría instalaciones de respaldo.
    for scenario in ("malformed", "missing_category", "truncated", "timeout", "http_error"):
        transport.scenario = scenario
        record = run_case(cases[2], values, tag, transport.post, transport.get, True)
        assert not record["quality"]["passed"], scenario
        if scenario == "malformed" and values["BENCH_MODE"] == "adapter":
            assert record["quality"]["fallback_observed"]
            assert record["adapter_metadata"]["doc_category"] == "instalaciones"
        if scenario == "timeout":
            assert record["timeout"]
    transport.scenario = "valid"
    return {"passed": True, "checks": ["valid", "malformed", "missing_category", "wrong_category", "taxonomy", "non_json_nan", "score_range", "ambiguous_tag", "unjustified_tag", "fenced_json", "truncation", "timeout", "http_error", "missing_installed_model", "fallback_not_success"]}


def worker(name, output, fake):
    values = profile_values(name)
    assert all(os.environ.get(k) == values[k] for k in RAG_KEYS), "Entorno hijo no coincide con perfil"
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    with contextlib.ExitStack() as guard:
        if fake:
            for target, attribute in ((socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "create_connection")):
                guard.enter_context(patch.object(target, attribute, side_effect=AssertionError("Red prohibida con --doble")))
        tag = import_tag()
        assert tag.TAG_PROVIDER == "ollama" and tag.TAG_MODEL == values["OLLAMA_TAG_MODEL"]
        assert "rag.pipeline" not in sys.modules and "chromadb" not in sys.modules
        assert len(cases) == 3
        for case in cases:
            groups = [set(case[k]) for k in ("supported_tags", "unjustified_tags", "review_tags")]
            assert set.union(*groups) == set(tag.TAGS_VALIDAS)
            assert all(not groups[i] & groups[j] for i in range(3) for j in range(i))
        report = {"profile": name, "pid": os.getpid(), "simulated": fake, "experimental": values["BENCH_MODE"] == "experimental",
                  "started_utc": datetime.now(timezone.utc).isoformat(), "repository": repository_state(),
                  "configuration": values, "profile_sha256": hashlib.sha256(PROFILES[name].read_bytes()).hexdigest(),
                  "cases_sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
                  "prompt_sha256": hashlib.sha256(tag.PROMPT.encode()).hexdigest(),
                  "rag_source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                        for name in ("rag/config.py", "rag/tsd/tag.py")},
                  "taxonomies": {"categories": sorted(tag.CATEGORIAS_VALIDAS), "tags": sorted(tag.TAGS_VALIDAS)},
                  "hardware_start": hardware(fake), "cases": [], "preflight_error": None,
                  "scope": "tag_only_no_embeddings_no_index_no_generation", "forced_unloads": False}
        import requests
        transport = FakeTransport(cases, {values[k] for k in ("OLLAMA_TAG_MODEL", "OLLAMA_EMBED_MODEL", "OLLAMA_GEN_MODEL")}) if fake else None
        def get(url, **kwargs):
            if fake:
                return transport.get(url, **kwargs)
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
        post = transport.post if fake else requests.post
        start = time.perf_counter()
        try:
            base = values["OLLAMA_BASE_URL"]
            report["ollama_version"] = get(base + "/api/version", timeout=10).get("version")
            models = get(base + "/api/tags", timeout=10)["models"]
            selected = {values[k] for k in ("OLLAMA_TAG_MODEL", "OLLAMA_EMBED_MODEL", "OLLAMA_GEN_MODEL")}
            report["models"], missing = installed_selection(models, selected)
            if missing:
                report["preflight_error"] = {"type": "MissingInstalledModel", "models": missing}
            else:
                report["tag_model_declared_parameters"] = None
                if not fake:
                    # /api/show no carga ni descarga pesos. No guarda Modelfile ni rutas.
                    response = post(base + "/api/show", json={"model": values["OLLAMA_TAG_MODEL"]}, timeout=10)
                    response.raise_for_status()
                    allowed = {"num_ctx", "num_predict", "temperature", "top_p", "top_k", "min_p", "repeat_penalty"}
                    parameters = {}
                    for line in (response.json().get("parameters") or "").splitlines():
                        fields = line.split()
                        if len(fields) == 2 and fields[0] in allowed:
                            try:
                                value = float(fields[1])
                                if math.isfinite(value):
                                    parameters[fields[0]] = value
                            except ValueError:
                                pass
                    report["tag_model_declared_parameters"] = parameters
                for index, case in enumerate(cases):
                    result = run_case(case, values, tag, post, get, fake)
                    result["call_number"] = index + 1
                    result["first_call_in_profile"] = index == 0
                    report["cases"].append(result)
                    write_new(output / f"{name}.{index + 1}.{case['id']}.json", result)
                    print(f"{name}: {case['id']} {result['seconds']:.3f}s quality={result['quality']['semantic_status']} passed={result['quality']['passed']}", flush=True)
                if fake:
                    report["offline_checks"] = offline_checks(tag, transport, values, cases)
        except Exception as exc:
            report["preflight_error"] = {"type": type(exc).__name__}
        report["seconds_total"] = round(time.perf_counter() - start, 6)
        report["hardware_end"] = hardware(fake)
        report["all_passed"] = len(report["cases"]) == 3 and all(c["quality"]["passed"] for c in report["cases"])
        write_new(output / f"{name}.json", report)
        if fake:
            assert report.get("offline_checks", {}).get("passed"), "Falló la autocomprobación con dobles"
        return 0 if report["all_passed"] else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", nargs="+", choices=tuple(PROFILES), help="Selección obligatoria; orden secuencial")
    parser.add_argument("--doble", action="store_true", help="Sin red ni hardware real; valida mecánica y fallos, no modelos")
    parser.add_argument("--_worker", choices=tuple(PROFILES), help=argparse.SUPPRESS)
    parser.add_argument("--_output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._worker:
        if args._output is None:
            parser.error("Falta salida del proceso hijo")
        return worker(args._worker, args._output, args.doble)
    if not args.perfil:
        parser.error("Debe seleccionar explícitamente --perfil")
    if len(set(args.perfil)) != len(args.perfil):
        parser.error("No repetir perfiles en una ejecución")
    profiles = {name: profile_values(name) for name in args.perfil}
    common = RAG_KEYS - {"OLLAMA_TAG_MODEL"}
    assert all({k: values[k] for k in common} == {k: next(iter(profiles.values()))[k] for k in common} for values in profiles.values())
    output = ROOT / "tmp/benchmark_rag_tag" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:12])
    output.mkdir(parents=True, exist_ok=False)
    summary = {"simulated": args.doble, "profiles_in_order": args.perfil, "executions": []}
    for name, values in profiles.items():
        print(f"Iniciando {name} ({'DOBLE SIN RED' if args.doble else values['BENCH_MODE']})", flush=True)
        command = [sys.executable, str(Path(__file__).resolve()), "--_worker", name, "--_output", str(output)]
        if args.doble:
            command.append("--doble")
        # run espera la finalización completa antes de iniciar el siguiente perfil.
        started = time.perf_counter()
        proc = subprocess.run(command, cwd=ROOT, env=child_environment(values), capture_output=True, text=True, encoding="utf-8")
        print(proc.stdout, end="")
        summary["executions"].append({"profile": name, "exit_code": proc.returncode,
                                      "process_seconds": round(time.perf_counter() - started, 6)})
        if proc.returncode not in (0, 2):
            # No persiste traceback/stderr: pueden contener rutas personales.
            print(f"{name}: error interno; revisar dependencias o ejecutar --doble", file=sys.stderr)
    if args.doble:
        reports = [json.loads((output / f"{name}.json").read_text(encoding="utf-8")) for name in args.perfil if (output / f"{name}.json").is_file()]
        summary["independent_processes_verified"] = len(reports) == len(args.perfil) and len({report["pid"] for report in reports}) == len(reports)
        if not summary["independent_processes_verified"]:
            summary["validation_error"] = "Faltan informes independientes de dobles"
    write_new(output / "resumen.json", summary)
    print("Resultados nuevos: " + output.relative_to(ROOT).as_posix())
    return 0 if all(e["exit_code"] == 0 for e in summary["executions"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
