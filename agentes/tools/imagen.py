"""Validación de imágenes y adaptación de visión a ToolResult.

Entrada: image_id autorizado ligado al pedido, no una ruta elegida por el modelo.
Comprobar formato PNG/JPEG y tamaño; definir almacenamiento y limpieza de sesión.
Salida: texto u observaciones con incertidumbres y evidencia de imagen aportada.
No certificar vigencia de carteles ni diagnosticar causa de averías.
Dependencia: adaptador de modelo de visión. No incluir imágenes personales aquí.
"""
