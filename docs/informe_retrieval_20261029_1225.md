# Informe TEST de recuperación

- **Fecha:** 2026-10-29 12:25:45
- **Colección:** `deporte_municipal`
- **Modo configurado:** `hibrido`
- **TOP_K:** 6
- **Candidatos por consulta:** 50
- **RRF_K:** 60
- **Umbral de abstención coseno:** 0.65
- **Preguntas evaluadas:** 24

## 1. Criterios

- **Hit@1:** la fuente esperada aparece en la primera posición.
- **Hit@6:** la fuente esperada aparece entre los primeros 6 resultados.
- **MRR:** media del inverso de la posición de la primera fuente correcta.
- **nDCG@6:** calidad del ranking, dando más peso a las posiciones altas.
- **Coseno:** menor distancia implica mayor cercanía semántica.
- **BM25 y RRF:** mayor score implica mejor posición o mayor consenso entre rankings.
- **Abstención correcta:** pregunta fuera de corpus sin evidencia admitida.
- **Falso positivo:** pregunta fuera de corpus para la que el método devuelve evidencia.

## 2. Resumen global

| Estrategia | Hit@1 | Hit@6 | MRR | nDCG@6 | Abstenciones correctas | Falsos positivos | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| COSENO | 57.89% | 73.68% | 0.6491 | 0.2033 | 0/5 | 5 | 559.9 ms | 604.0 ms |
| BM25 | 73.68% | 89.47% | 0.7982 | 0.2487 | 5/5 | 0 | 559.9 ms | 604.0 ms |
| RRF | 42.11% | 78.95% | 0.5746 | 0.1904 | 5/5 | 0 | 559.9 ms | 604.0 ms |

## 3. Resultados por pregunta

| Pregunta | Esperada | Tipo | Coseno rank | BM25 rank | RRF rank | Mejor distancia | BM25 score | RRF score | Coseno | BM25 | RRF |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| ¿tiene el centro deportivo de la cea bermudez pistas para practicar el padel? | 200186-0-polideportivos.csv | corpus | 1 | 2 | 2 | 0.2068 | 35.2190 | 0.037041 | ok | ok | ok |
| ¿hay descuentos para familia numerosa? | 300097-0-deportes-descuentos.csv | corpus | 1 | 1 | 1 | 0.3011 | 13.2198 | 0.030798 | ok | ok | ok |
| ¿cuánto cuesta una entrada para la piscina cubierta? | preciospublicos2026.pdf | corpus | — | — | — | 0.3661 | 20.5392 | 0.030886 | fallo | fallo | fallo |
| ¿quién ganó el mundial de fútbol en 2026? | — | fuera | — | — | — | 0.4238 | 26.4480 | 0.038703 | falso_positivo | abstencion_correcta | abstencion_correcta |
| ¿cómo se adquiere el abono deporte madrid (adm)? | 20250912_infografíacómoadquirirorenovarunadm.pdf | corpus | — | 1 | — | 0.2856 | 28.3770 | 0.029631 | fallo | ok | fallo |
| ¿puedo acceder con mi botella de agua de cristal al recinto deportivo o tengo que comprar  | reglamento_instalaciones.pdf | corpus | 1 | 1 | 1 | 0.2463 | 66.9090 | 0.070722 | ok | ok | ok |
| ¿puedo comprar el abono de deportes municipal de manera online? | 20250912_infografíacómoadquirirorenovarunadm.pdf | corpus | — | — | — | 0.3037 | 25.5573 | 0.031514 | fallo | fallo | fallo |
| ¿he perdido un objeto personal en el vestuario, cómo contacto con objetos perdidos para pr | reglamento_instalaciones.pdf | corpus | 1 | 1 | 1 | 0.2653 | 57.3669 | 0.065856 | ok | ok | ok |
| ¿cómo puedo hacer una dieta paleolítica? | — | fuera | — | — | — | 0.4802 | 11.5698 | 0.030886 | falso_positivo | abstencion_correcta | abstencion_correcta |
| ¿puedo cancelar una reserva para piscina cubierta tres horas antes? | decretoanulacionreservasconcoste.pdf | corpus | 1 | 1 | 2 | 0.2329 | 26.5352 | 0.050750 | ok | ok | ok |
| ¿cómo puedo hacer una anulación de reserva? | decretoanulacionreservasconcoste.pdf | corpus | — | 1 | 4 | 0.4313 | 23.7221 | 0.031281 | fallo | ok | ok |
| ¿puedo usar las instalaciones deportivas si no soy residente en madrid? | — | fuera | — | — | — | 0.2327 | 31.6409 | 0.051529 | falso_positivo | abstencion_correcta | abstencion_correcta |
| ¿se requiere supervisión en las salas de musculación? | reglamento_instalaciones.pdf | corpus | 1 | 2 | 1 | 0.3565 | 30.7095 | 0.061152 | ok | ok | ok |
| ¿cuándo ganó el real madrid su última liga? | — | fuera | — | — | — | 0.3876 | 23.3203 | 0.030777 | falso_positivo | abstencion_correcta | abstencion_correcta |
| ¿cómo recupero mis enseres del guardarropa si he perdido la ficha que me entregaron? | reglamento_instalaciones.pdf | corpus | 1 | 1 | 2 | 0.3780 | 28.8834 | 0.032192 | ok | ok | ok |
| ¿qué piscinas al aire libre están abiertas para el verano? | piscinasairelibre2026.pdf | corpus | 1 | 1 | 1 | 0.2778 | 40.8333 | 0.031054 | ok | ok | ok |
| ¿qué dias abre el centro deportivo de arganzuela? | 200186-0-polideportivos.csv | corpus | 2 | 1 | 2 | 0.1747 | 17.2608 | 0.033060 | ok | ok | ok |
| ¿hay instalaciones adaptadas para personas con movilidad reducida en el centro deportivo d | 200186-0-polideportivos.csv | corpus | 1 | 1 | 1 | 0.1936 | 43.6877 | 0.028571 | ok | ok | ok |
| ¿cuándo se celebran los juegos deportivos municipales? | basesdeportesequipo47jdm_1sp.pdf | corpus | 3 | 6 | 3 | 0.2784 | 25.3945 | 0.068572 | ok | ok | ok |
| ¿cómo se inscribe un club deportivo en las competiciones municipales? | normativageneral46jdm.pdf | corpus | 2 | 1 | 1 | 0.2433 | 38.0171 | 0.067571 | ok | ok | ok |
| ¿en qué fecha finalizan las jornadas de ajedrez en los parques? | 212504-0-agenda-actividades-deportes.csv | corpus | — | 1 | — | 0.3963 | 48.6573 | 0.031010 | fallo | ok | fallo |
| ¿cuál es la mejor marca de zapatillas para correr? | — | fuera | — | — | — | 0.4789 | 30.1851 | 0.030777 | falso_positivo | abstencion_correcta | abstencion_correcta |
| ¿qué servicios tiene el estadio municipal vallehermoso? | 200186-0-polideportivos.csv | corpus | 1 | 1 | 3 | 0.2310 | 16.9413 | 0.041982 | ok | ok | ok |
| ¿es posible acceder con sillas o tumbonas propias si las propias de las instalaciones ya h | reglamento_instalaciones.pdf | corpus | 1 | 1 | 1 | 0.2979 | 57.5354 | 0.045169 | ok | ok | ok |

## 4. Diagnóstico automático

- **RRF empeora Hit@1 frente a coseno en 15.8 puntos porcentuales.**
- **RRF no introduce falsos positivos** en el conjunto actual.
- **4 preguntas in-corpus no recuperan la fuente esperada con RRF** en los primeros 6 resultados.

## 5. Criterios de decisión

- Mantener **RRF** si mejora Hit@1, MRR o nDCG sin aumentar falsos positivos.
- Usar **coseno puro** si RRF no aporta mejora relevante y aumenta latencia.
- Revisar **BM25** si domina en consultas literales pero falla en formulaciones semánticas.
- Ajustar `UMBRAL_ABSTENCION` si hay falsos positivos o abstenciones incorrectas.
- Revisar chunking, metadatos de fuente o corpus si varias preguntas in-corpus fallan en los tres métodos.
