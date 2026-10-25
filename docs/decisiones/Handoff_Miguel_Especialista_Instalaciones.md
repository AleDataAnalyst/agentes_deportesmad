# Handoff para Miguel: especialista de instalaciones y avisos

- **Responsable de continuar esta tarea:** Miguel
- **Investigación y recopilación de fuentes:** Alejandra
- **Corte de la comprobación:** 13/10/2026

## Alcance de este handoff

Este documento entrega las fuentes y resultados observados para el especialista de **Instalaciones y avisos** que continuará Miguel. Registra la API del catálogo, las fichas web enlazadas para cada centro y si en la captura se detectó el encabezado de avisos. No define contratos, herramientas adicionales ni decisiones de otros especialistas.

## Fuente 1: API oficial del catálogo

- Conjunto: [Deportes. Centros deportivos municipales (polideportivos)](https://datos.madrid.es/dataset/200186-0-polideportivos).
- API consultada: [CKAN `datastore_search`](https://datos.madrid.es/api/3/action/datastore_search?resource_id=200186-0-polideportivos-csv&limit=100).
- La respuesta observada devolvió `success=true`, `total=82` y 82 registros.
- Campos usados en este inventario: `PK`, `NOMBRE`, `DISTRITO` y `CONTENT-URL`.
- `CONTENT-URL` enlaza con la ficha web de cada centro. La página de aviso es HTML; no se identificó una API separada de avisos.

## Fuente 2: fichas municipales por centro

Se consultaron las 82 URLs de ficha derivadas de `CONTENT-URL` mediante HTTPS. El registro inicial fue 72 respuestas HTTP 200, un error en San Fermín y nueve fichas aún sin intentar. Después se reintentaron esos diez casos: los diez devolvieron HTTP 200. Resultado consolidado: 82 de 82 respuestas HTTP 200 en las consultas registradas el 13/10/2026.

La detección de aviso de esta tabla es textual: se buscó el encabezado visible “Aviso a usuarios/as”. “Sin encabezado detectado” no significa que no haya incidencia; tampoco una respuesta HTTP 200 certifica que el aviso siga vigente.

| ID (`PK`) | Centro y ficha oficial | Distrito | HTTP observado | Encabezado de aviso |
|---|---|---|---:|---|
| `10183549` | [Centro Deportivo Municipal Alcántara](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=a949235892f28510VgnVCM1000001d4a900aRCRD) | SALAMANCA | 200 | Sin encabezado detectado |
| `114782` | [Centro Deportivo Municipal Alfredo Goyeneche](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=789fe8ae8d81c010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Aviso detectado (1 bloque) |
| `4696` | [Centro Deportivo Municipal Aluche](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=4506b0c40971c010VgnVCM1000000b205a0aRCRD) | LATINA | 200 | Sin encabezado detectado |
| `4617960` | [Centro Deportivo Municipal Antiguo Canódromo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=dd6426521e7f3110VgnVCM1000000b205a0aRCRD) | CARABANCHEL | 200 | Sin encabezado detectado |
| `4624404` | [Centro Deportivo Municipal Antonio Díaz Miguel](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=c90342b9fda34110VgnVCM1000000b205a0aRCRD) | TETUAN | 200 | Aviso detectado (1 bloque) |
| `99578` | [Centro Deportivo Municipal Barajas](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=b86c79262ef5d010VgnVCM1000000b205a0aRCRD) | BARAJAS | 200 | Aviso detectado (1 bloque) |
| `10051058` | [Centro Deportivo Municipal Barceló](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=335b21f025d44510VgnVCM2000001f4a900aRCRD) | CENTRO | 200 | Sin encabezado detectado |
| `4695` | [Centro Deportivo Municipal Blanca Fernández Ochoa](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=930942be9971c010VgnVCM1000000b205a0aRCRD) | CARABANCHEL | 200 | Sin encabezado detectado |
| `4705` | [Centro Deportivo Municipal Casa de Campo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=3876b0c40971c010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Aviso detectado (1 bloque) |
| `12022187` | [Centro Deportivo Municipal Cea Bermúdez](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=40d41946bf658810VgnVCM2000001f4a900aRCRD) | CHAMBERI | 200 | Sin encabezado detectado |
| `78960` | [Centro Deportivo Municipal Centro Integrado Arganzuela](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=0fd38ed67151c010VgnVCM2000000c205a0aRCRD) | ARGANZUELA | 200 | Aviso detectado (1 bloque) |
| `4687` | [Centro Deportivo Municipal Cerro Almodóvar](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=8e96b0c40971c010VgnVCM1000000b205a0aRCRD) | VILLA DE VALLECAS | 200 | Sin encabezado detectado |
| `4700` | [Centro Deportivo Municipal Chamartín](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=5f8c79262ef5d010VgnVCM1000000b205a0aRCRD) | CHAMARTIN | 200 | Sin encabezado detectado |
| `6208448` | [Centro Deportivo Municipal Circuito Internacional BMX (Dirección General de Deporte)](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=48fbf0c99a833310VgnVCM1000000b205a0aRCRD) | ARGANZUELA | 200 | Sin encabezado detectado |
| `4702` | [Centro Deportivo Municipal Ciudad de los Poetas](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=2be6b0c40971c010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Sin encabezado detectado |
| `4672` | [Centro Deportivo Municipal Concepción](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=f5bc79262ef5d010VgnVCM1000000b205a0aRCRD) | CIUDAD LINEAL | 200 | Aviso detectado (1 bloque) |
| `12724992` | [Centro Deportivo Municipal Cuatro Caminos](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=5184a4ba934a5910VgnVCM1000001d4a900aRCRD) | TETUAN | 200 | Sin encabezado detectado |
| `134059` | [Centro Deportivo Municipal Daoíz y Velarde 1](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=380d5f463b81c010VgnVCM1000000b205a0aRCRD) | RETIRO | 200 | Sin encabezado detectado |
| `4726` | [Centro Deportivo Municipal Daoíz y Velarde 2](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=c737b0c40971c010VgnVCM1000000b205a0aRCRD) | RETIRO | 200 | Sin encabezado detectado |
| `140197` | [Centro Deportivo Municipal El Espinillo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=9cdc79262ef5d010VgnVCM1000000b205a0aRCRD) | VILLAVERDE | 200 | Sin encabezado detectado |
| `84661` | [Centro Deportivo Municipal El Olivillo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=61ff5c2cdc41c010VgnVCM2000000c205a0aRCRD) | LATINA | 200 | Sin encabezado detectado |
| `4685` | [Centro Deportivo Municipal El Quijote](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=01d7b0c40971c010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Sin encabezado detectado |
| `4676` | [Centro Deportivo Municipal Entrevías](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=1e57b0c40971c010VgnVCM1000000b205a0aRCRD) | PUENTE DE VALLECAS | 200 | Sin encabezado detectado |
| `6486044` | [Centro Deportivo Municipal Escuelas de San Antón](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=4f9aad5078828310VgnVCM1000000b205a0aRCRD) | CENTRO | 200 | Sin encabezado detectado |
| `10663007` | [Centro Deportivo Municipal Estadio de Atletismo Vallehermoso (Dirección General de Deporte)](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=10c0f41a5b442610VgnVCM2000001f4a900aRCRD) | CHAMBERI | 200 | Sin encabezado detectado |
| `4728` | [Centro Deportivo Municipal Estanque del Retiro](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=6487b0c40971c010VgnVCM1000000b205a0aRCRD) | RETIRO | 200 | Sin encabezado detectado |
| `4622862` | [Centro Deportivo Municipal Fabián Roncero](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=887e306502624110VgnVCM1000000b205a0aRCRD) | SAN BLAS-CANILLEJAS | 200 | Sin encabezado detectado |
| `120275` | [Centro Deportivo Municipal Faustina Valladolid](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=a64f79262ef5d010VgnVCM1000000b205a0aRCRD) | VICALVARO | 200 | Aviso detectado (1 bloque) |
| `50264232` | [Centro Deportivo Municipal Fernando Carro - Las Rosas](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=bbe24221a4f1d910VgnVCM100000891ecb1aRCRD) | SAN BLAS-CANILLEJAS | 200 | Sin encabezado detectado |
| `4703` | [Centro Deportivo Municipal Fernando Martín](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=baa7b0c40971c010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Aviso detectado (1 bloque) |
| `4623547` | [Centro Deportivo Municipal Francisco Fernández Ochoa](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=aea1249dbda24110VgnVCM1000000b205a0aRCRD) | CARABANCHEL | 200 | Aviso detectado (1 bloque) |
| `4623697` | [Centro Deportivo Municipal Fuente del Berro](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=f4a2318c05b24110VgnVCM1000000b205a0aRCRD) | SALAMANCA | 200 | Sin encabezado detectado |
| `124194` | [Centro Deportivo Municipal Félix Rubio](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=330d79262ef5d010VgnVCM1000000b205a0aRCRD) | VILLAVERDE | 200 | Sin encabezado detectado |
| `50257984` | [Centro Deportivo Municipal Fúcar](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=db853cfd927fc910VgnVCM200000f921e388RCRD) | CENTRO | 200 | Sin encabezado detectado |
| `4698` | [Centro Deportivo Municipal Gallur](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=d92d79262ef5d010VgnVCM1000000b205a0aRCRD) | LATINA | 200 | Sin encabezado detectado |
| `51661` | [Centro Deportivo Municipal Gimnasio Moscardó](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=c7cee7510551c010VgnVCM2000000c205a0aRCRD) | SALAMANCA | 200 | Sin encabezado detectado |
| `4680` | [Centro Deportivo Municipal Hortaleza](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=705d79262ef5d010VgnVCM1000000b205a0aRCRD) | HORTALEZA | 200 | Sin encabezado detectado |
| `4704` | [Centro Deportivo Municipal José María Cagigal](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=177d79262ef5d010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Sin encabezado detectado |
| `11580683` | [Centro Deportivo Municipal Juan de Dios Román](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=2ec21fc9c969e710VgnVCM1000001d4a900aRCRD) | VILLA DE VALLECAS | 200 | Sin encabezado detectado |
| `4623700` | [Centro Deportivo Municipal La Almudena](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=ff13318c05b24110VgnVCM1000000b205a0aRCRD) | CIUDAD LINEAL | 200 | Sin encabezado detectado |
| `4722` | [Centro Deportivo Municipal La Bombilla](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=5a6842be9971c010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Sin encabezado detectado |
| `11820127` | [Centro Deportivo Municipal La Cebada](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=b52f49ccf35d3810VgnVCM1000001d4a900aRCRD) | CENTRO | 200 | Sin encabezado detectado |
| `4697` | [Centro Deportivo Municipal La Chopera](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=a09842be9971c010VgnVCM1000000b205a0aRCRD) | RETIRO | 200 | Sin encabezado detectado |
| `4674` | [Centro Deportivo Municipal La Elipa](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=f6b842be9971c010VgnVCM1000000b205a0aRCRD) | MORATALAZ | 200 | Sin encabezado detectado |
| `4694` | [Centro Deportivo Municipal La Fundi](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=9b26b0c40971c010VgnVCM1000000b205a0aRCRD) | ARGANZUELA | 200 | Sin encabezado detectado |
| `104235` | [Centro Deportivo Municipal La Masó - Luis de la Fuente](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=15efe8ae8d81c010VgnVCM1000000b205a0aRCRD) | FUENCARRAL-EL PARDO | 200 | Sin encabezado detectado |
| `4834` | [Centro Deportivo Municipal Lago Casa de Campo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=cd9d79262ef5d010VgnVCM1000000b205a0aRCRD) | MONCLOA-ARAVACA | 200 | Sin encabezado detectado |
| `4538574` | [Centro Deportivo Municipal Las Cruces](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=6a6952ff55b41110VgnVCM1000000b205a0aRCRD) | LATINA | 200 | Sin encabezado detectado |
| `4619937` | [Centro Deportivo Municipal Los Prunos](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=e705dfa167204110VgnVCM1000000b205a0aRCRD) | HORTALEZA | 200 | Sin encabezado detectado |
| `4681` | [Centro Deportivo Municipal Luis Aragonés](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=64cd79262ef5d010VgnVCM1000000b205a0aRCRD) | HORTALEZA | 200 | Sin encabezado detectado |
| `4688` | [Centro Deportivo Municipal Margot Moles](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=4d6f79262ef5d010VgnVCM1000000b205a0aRCRD) | VICALVARO | 200 | Sin encabezado detectado |
| `121729` | [Centro Deportivo Municipal Marqués de Samaranch](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=6b00e8ae8d81c010VgnVCM1000000b205a0aRCRD) | ARGANZUELA | 200 | Sin encabezado detectado |
| `4707` | [Centro Deportivo Municipal María Jesús Rosa](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=e92942be9971c010VgnVCM1000000b205a0aRCRD) | FUENCARRAL-EL PARDO | 200 | Aviso detectado (2 bloques) |
| `4701827` | [Centro Deportivo Municipal Miguel Guillén Prim](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=ecd237c71d4a6110VgnVCM1000000b205a0aRCRD) | VILLA DE VALLECAS | 200 | Sin encabezado detectado |
| `12346116` | [Centro Deportivo Municipal Mistral](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=791cf0388f0ee810VgnVCM2000001f4a900aRCRD) | BARAJAS | 200 | Sin encabezado detectado |
| `4673` | [Centro Deportivo Municipal Moratalaz](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=dc9942be9971c010VgnVCM1000000b205a0aRCRD) | MORATALAZ | 200 | Aviso detectado (1 bloque) |
| `4691` | [Centro Deportivo Municipal Moscardó](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=23c942be9971c010VgnVCM1000000b205a0aRCRD) | USERA | 200 | Sin encabezado detectado |
| `4693` | [Centro Deportivo Municipal Orcasitas](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=a11e79262ef5d010VgnVCM1000000b205a0aRCRD) | USERA | 200 | Sin encabezado detectado |
| `4690` | [Centro Deportivo Municipal Orcasur](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=483e79262ef5d010VgnVCM1000000b205a0aRCRD) | USERA | 200 | Sin encabezado detectado |
| `4684794` | [Centro Deportivo Municipal Pabellón Villa de Madrid](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=6e67668e4a336110VgnVCM1000000b205a0aRCRD) | BARAJAS | 200 | Sin encabezado detectado |
| `4675` | [Centro Deportivo Municipal Palomeras](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=ee5e79262ef5d010VgnVCM1000000b205a0aRCRD) | PUENTE DE VALLECAS | 200 | Sin encabezado detectado |
| `12453713` | [Centro Deportivo Municipal Paseo de la Dirección](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=161b2f93cea51910VgnVCM1000001d4a900aRCRD) | TETUAN | 200 | Sin encabezado detectado |
| `4622991` | [Centro Deportivo Municipal Pepu Hernández](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=f86186e9a3624110VgnVCM1000000b205a0aRCRD) | SAN BLAS-CANILLEJAS | 200 | Sin encabezado detectado |
| `10630252` | [Centro Deportivo Municipal Peñagrande GoFit](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=6b2456babc1c1610VgnVCM1000001d4a900aRCRD) | FUENCARRAL-EL PARDO | 200 | Sin encabezado detectado |
| `4727` | [Centro Deportivo Municipal Peñuelas](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=6c5a42be9971c010VgnVCM1000000b205a0aRCRD) | ARGANZUELA | 200 | Sin encabezado detectado |
| `4719` | [Centro Deportivo Municipal Plata y Castañar](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=858e79262ef5d010VgnVCM1000000b205a0aRCRD) | VILLAVERDE | 200 | Sin encabezado detectado |
| `4718` | [Centro Deportivo Municipal Playa Victoria](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=c77e0a47f441f010VgnVCM2000000c205a0aRCRD) | TETUAN | 200 | Sin encabezado detectado |
| `4701` | [Centro Deportivo Municipal Pradillo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=2cae79262ef5d010VgnVCM1000000b205a0aRCRD) | CHAMARTIN | 200 | Sin encabezado detectado |
| `4720` | [Centro Deportivo Municipal Pueblo Nuevo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=a5fa42be9971c010VgnVCM1000000b205a0aRCRD) | CIUDAD LINEAL | 200 | Sin encabezado detectado |
| `106242` | [Centro Deportivo Municipal Raúl González](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=c2de79262ef5d010VgnVCM1000000b205a0aRCRD) | VILLAVERDE | 200 | Sin encabezado detectado |
| `4689` | [Centro Deportivo Municipal San Blas](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=424b42be9971c010VgnVCM1000000b205a0aRCRD) | SAN BLAS-CANILLEJAS | 200 | Sin encabezado detectado |
| `4686` | [Centro Deportivo Municipal San Cristóbal](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=69fe79262ef5d010VgnVCM1000000b205a0aRCRD) | VILLAVERDE | 200 | Sin encabezado detectado |
| `4692` | [Centro Deportivo Municipal San Fermín](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=ee8b42be9971c010VgnVCM1000000b205a0aRCRD) | USERA | 200 | Sin encabezado detectado |
| `4679` | [Centro Deportivo Municipal San Juan Bautista](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=35bb42be9971c010VgnVCM1000000b205a0aRCRD) | CIUDAD LINEAL | 200 | Sin encabezado detectado |
| `4706` | [Centro Deportivo Municipal Santa Ana](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=8bdb42be9971c010VgnVCM1000000b205a0aRCRD) | FUENCARRAL-EL PARDO | 200 | Sin encabezado detectado |
| `28525` | [Centro Deportivo Municipal Tenis Casa de Campo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=1ac06f065851c010VgnVCM2000000c205a0aRCRD) | MONCLOA-ARAVACA | 200 | Sin encabezado detectado |
| `4684` | [Centro Deportivo Municipal Triángulo de Oro](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=002f79262ef5d010VgnVCM1000000b205a0aRCRD) | TETUAN | 200 | Sin encabezado detectado |
| `4677` | [Centro Deportivo Municipal Vallecas Verano](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=282c42be9971c010VgnVCM1000000b205a0aRCRD) | PUENTE DE VALLECAS | 200 | Sin encabezado detectado |
| `7411340` | [Centro Deportivo Municipal Vallehermoso GoFit](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=28906e8a84805410VgnVCM2000000c205a0aRCRD) | CHAMBERI | 200 | Sin encabezado detectado |
| `4699` | [Centro Deportivo Municipal Vicente del Bosque](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=e156b0c40971c010VgnVCM1000000b205a0aRCRD) | FUENCARRAL-EL PARDO | 200 | Aviso detectado (1 bloque) |
| `49338` | [Centro Deportivo Municipal Wilfred Agbonavbare](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=2b7ee7510551c010VgnVCM2000000c205a0aRCRD) | PUENTE DE VALLECAS | 200 | Sin encabezado detectado |
| `4678` | [Centro Deportivo Municipal Ángel Nieto](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=fb1b42be9971c010VgnVCM1000000b205a0aRCRD) | PUENTE DE VALLECAS | 200 | Sin encabezado detectado |

## Fichas donde se detectó el encabezado

En la captura se detectó el encabezado en 12 fichas y 13 bloques de aviso; María Jesús Rosa tenía dos. Los siguientes resúmenes describen el texto almacenado en la consulta, no una verificación actual en la instalación:

| Centro y ficha oficial | Resumen literal/parafraseado del aviso capturado |
|---|---|
| [Centro Deportivo Municipal Alfredo Goyeneche](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=789fe8ae8d81c010VgnVCM1000000b205a0aRCRD) | Cierre completo por obras; inicio 01/07/2026, duración estimada cinco meses. |
| [Centro Deportivo Municipal Antonio Díaz Miguel](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=c90342b9fda34110VgnVCM1000000b205a0aRCRD) | Piscina cerrada por renovación de vestuarios; la ficha dice que no se prestan servicios de piscina. |
| [Centro Deportivo Municipal Barajas](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=b86c79262ef5d010VgnVCM1000000b205a0aRCRD) | CuboGym operativo desde 02/10/2026; pickleball y calistenia suspendidos por obras. |
| [Centro Deportivo Municipal Casa de Campo](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=3876b0c40971c010VgnVCM1000000b205a0aRCRD) | Piscina climatizada y vestuarios suspendidos desde 13/10/2026; plazo previsto de tres meses. |
| [Centro Deportivo Municipal Centro Integrado Arganzuela](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=0fd38ed67151c010VgnVCM2000000c205a0aRCRD) | Obras previstas desde 19/10/2026; aseos limitados durante los trabajos. |
| [Centro Deportivo Municipal Concepción](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=f5bc79262ef5d010VgnVCM1000000b205a0aRCRD) | Obras desde 01/10/2026; piscina y pabellón cerrados y actividades suspendidas en esas zonas. |
| [Centro Deportivo Municipal Faustina Valladolid](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=a64f79262ef5d010VgnVCM1000000b205a0aRCRD) | Pabellón cerrado desde 21/09 hasta nuevo aviso; el aviso no indica el año. |
| [Centro Deportivo Municipal Fernando Martín](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=baa7b0c40971c010VgnVCM1000000b205a0aRCRD) | Centro cerrado desde 16/07/2026 hasta la finalización de obras de climatización. |
| [Centro Deportivo Municipal Francisco Fernández Ochoa](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=aea1249dbda24110VgnVCM1000000b205a0aRCRD) | Pistas de pádel cerradas por rehabilitación hasta nuevo aviso. |
| [Centro Deportivo Municipal María Jesús Rosa](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=e92942be9971c010VgnVCM1000000b205a0aRCRD) | Dos avisos técnicos: cierre temporal de piscinas y ausencia de agua caliente. |
| [Centro Deportivo Municipal Moratalaz](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=dc9942be9971c010VgnVCM1000000b205a0aRCRD) | Pista de atletismo cerrada desde 14/01/2026 hasta nuevo aviso. |
| [Centro Deportivo Municipal Vicente del Bosque](https://www.madrid.es/sites/v/index.jsp?vgnextchannel=bfa48ab43d6bb410VgnVCM100000171f5a0aRCRD&vgnextoid=e156b0c40971c010VgnVCM1000000b205a0aRCRD) | Cierre de pistas de tenis y piscina climatizada por obras; sin fecha de reapertura indicada. |

## Límites de la evidencia

- La fecha de consulta es 13/10/2026. El contenido de las fichas puede cambiar o retirarse.
- Los 12 encabezados detectados son una observación de esa captura, no una medida estable de incidencias.
- Las fichas incluyen fechas futuras, fechas sin año o cierres “hasta nuevo aviso”; la extracción no permite certificar vigencia.
- La comprobación HTTP no valida un conector del proyecto, un parser integrado ni un fallback.
- Este documento no afirma que el sistema pueda confirmar apertura, disponibilidad, plazas o reservas.

## Referencias

- [Catálogo de Datos Abiertos](https://datos.madrid.es/dataset/200186-0-polideportivos)
- [Endpoint CKAN usado para la consulta](https://datos.madrid.es/api/3/action/datastore_search?resource_id=200186-0-polideportivos-csv&limit=100)
