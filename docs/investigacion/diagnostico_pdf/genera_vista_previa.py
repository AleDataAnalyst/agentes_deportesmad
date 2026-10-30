"""
Estee código genera vista previa de la tabla a recortar.

"""



from pathlib import Path

import pdfplumber

pdf_path = Path("data/corpus/PreciosPublicos2026.pdf")
salida = Path("diagnostico_pdf")
salida.mkdir(exist_ok=True)

with pdfplumber.open(pdf_path) as pdf:
    pagina = pdf.pages[0]

    print(f"Página: {pagina.width:.2f} × {pagina.height:.2f} puntos")

    vista = pagina.to_image(resolution=25)
    vista.save(str(salida / "precios_pagina.png"))