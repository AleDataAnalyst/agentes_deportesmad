# rag/file_hash.py
import hashlib
from pathlib import Path
from datetime import datetime, timezone

def sha256_archivo(ruta: str | Path) -> str:
    digest = hashlib.sha256()

    with Path(ruta).open("rb") as archivo:
        while bloque := archivo.read(1 << 20):
            digest.update(bloque)
    
    
    return digest.hexdigest()

def verificar_archivos_al_final(
    archivos: list[dict],
) -> dict:
    resultados = []

    for archivo in archivos:
        resultado = {
            **archivo,
            "sha256_final": None,
            "sin_cambios": None,
            "error": None,
        }

        try:
            hash_final = sha256_archivo(archivo["ruta"])

            resultado["sha256_final"] = hash_final
            resultado["sin_cambios"] = (
                archivo["sha256_carga"] == hash_final
            )

        except OSError as exc:
            resultado["error"] = f"{type(exc).__name__}: {exc}"

        resultados.append(resultado)

    return {
        "algoritmo": "sha256",
        "verificado_en_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(resultados),
        "sin_cambios": sum(
            item["sin_cambios"] is True
            for item in resultados
        ),
        "modificados": sum(
            item["sin_cambios"] is False
            for item in resultados
        ),
        "errores": sum(
            item["error"] is not None
            for item in resultados
        ),
        "archivos": resultados,
    }