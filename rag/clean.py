"""
rag/clean.py
Quita ruido antes de trocear para producir chunks más homogéneos.
Además aplica un ROUTER de pre-procesamiento de datos: normaliza el contenido
según el formato del documento (PDF/CSV/JSON) para que llegue al LLM (TAG)
en un formato bien formado y evite JSON malformado en la fase de etiquetado.
"""

import re
from langchain_core.documents import Document

from .load import _formato_documento


def _normalizar_page_content(texto: str) -> str:
    """
    Reglas de limpieza (aplica todas en orden):
      1. Saltos de línea dobles o más → uno solo.
      2. Espacios de más (tabs, 3+ espacios) → uno.
      3. Líneas vacías repetidas → eliminar.
      4. Espacios al inicio/final de cada línea.
      5. BOM / caracteres de control invisibles.
    """
    # 1
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    # 2
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    # 3
    texto = re.sub(r"(\n\s*){2,}", "\n\n", texto)
    # 4
    texto = "\n".join(linea.strip() for linea in texto.split("\n"))
    # 5
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", texto)
    # Eliminar BOM
    texto = texto.lstrip("\ufeff")
    return texto.strip()

# ---------- Router de pre-procesamiento de datos ----------

def _limpiar_pdf(texto: str) -> str:
    """Limpia ruido de extracto de PDF: metadatos binarios, caracteres
    de control no imprimibles, saltos de línea extraños"""
    # 1) Caracteres de control invisibles y BOM.
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", texto)
    # 2) Caracteres binarios (controles C1 y U+FFFD); el resto de Unicode se queda.
    texto = re.sub(r"[\x80-\x9f\ufffd]", "", texto)
    # 3) Unificar saltos de línea múltiples.
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    # 4) Espacios/tabos de más.
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto.strip()


def _limpiar_csv(texto: str) -> str:
    """Limpia ruido de un CSV mal extraído: caracteres de control, saltos
    extraños y espacios de más. Produce texto legible para el LLM"""
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto.strip()


def normalizar_por_formato(documentos: list[Document]) -> list[Document]:
    """Aplica limpieza específica según el formato. Devuelve Nuevos Document
    con el metadato intacto para que TAG (etiquetar) reciba input limpio."""
    limpiados: list[Document] = []
    for doc in documentos:
        formato = doc.metadata.get("format", "otro")
        if formato == "pdf":
            texto = _limpiar_pdf(doc.page_content)
        elif formato == "csv":
            texto = _limpiar_csv(doc.page_content)
        elif formato == "json":
            texto = doc.page_content
        else:
            texto = _normalizar_page_content(doc.page_content)
        limpiados.append(Document(
            page_content=texto,
            metadata=dict(doc.metadata),
        ))
    return limpiados



def limpiar(documentos: list[Document] | str) -> list[Document] | str:
    """
    Recibe documentos crudos o un string, devuelve el texto normalizado.
    No modifica metadata.
    """
    # Si viene un string plano, normaliza y devuelve string (según docstring y firma)
    if isinstance(documentos, str):
        return _normalizar_page_content(documentos)

    # 1) Limpieza genérica (ruido, BOM, espacios).
    genericos: list[Document] = [Document(
        page_content=_normalizar_page_content(d.page_content),
        metadata=dict(d.metadata),
    ) for d in documentos]

    # 2) Router de formato: limpieza específica por PDF/CSV/JSON, encima de la
    #    limpieza genérica, para dejar el contenido en un formato bien formado.
    return normalizar_por_formato(genericos)