"""Fan-out/fan-in de especialistas independientes.

Entradas: estado actual y dependencias de cada especialista.
Lanzar documental e instalaciones concurrentemente cuando el supervisor lo
permita; cada rama recibe una copia y presupuesto independiente.
Salidas: combinación por rol de resultados, visitados y eventos nuevos.
Evitar duplicar la traza previa o sobrescribir notas de otra rama.
Definir comportamiento ante excepción o cancelación antes de implementar.
No confundir orden estable de presentación con orden temporal de ejecución.
"""
