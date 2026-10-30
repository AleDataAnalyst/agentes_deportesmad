
# Cómo ajustar las coordenadas cartesianas en un documento

## Origen del documento

El origen está en la esquina superior izquierda:

```text

(0, 0) ───────────────────────────→ x
  │
  │       izquierda         derecha
  │           ┌────────────────┐  ← arriba
  │           │     TABLA      │
  │           └────────────────┘  ← abajo
  ↓
  y

```
## Para ampliar el recorte

```python
bbox = (
    50,    # Mover el borde izquierdo hacia la izquierda.
    560,   # Mover el borde superior hacia arriba.
    1820,  # Mover el borde derecho hacia la derecha.
    1260,  # Mover el borde inferior hacia abajo.
)
```

Incluye en cada región:

- El título de la sección, si da significado a las tarifas.
- Todas las cabeceras de columna.
- Las filas completas.
- Las notas que modifiquen sus condiciones.

## Si se selecciona el rectángulo sobre la vista previa

No se deben copiar directamente sus coordenadas en píxeles a pagina.crop(). Convierte según el tamaño de la imagen:

```python
ancho_preview, alto_preview = vista.original.size

bbox_pixeles = (x0, y0, x1, y1)

bbox_pdf = (
    bbox_pixeles[0] * pagina.width / ancho_preview,
    bbox_pixeles[1] * pagina.height / alto_preview,
    bbox_pixeles[2] * pagina.width / ancho_preview,
    bbox_pixeles[3] * pagina.height / alto_preview,
)

region = pagina.crop(bbox_pdf)
```

Primero es preciso comprobar el recorte visualmente. Sólo cuando se vean completas las cabeceras, conceptos e importes se debe conectar esa región al OCR; un buen recorte evita perder relaciones antes incluso del reconocimiento.

