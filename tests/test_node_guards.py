"""Fronteras del grafo con callables adversos explícitos; sin modelos ni red."""
from copy import deepcopy

import pytest
from langgraph.types import Command

from agentes.agent import AgentService
from agentes.contracts import Evidence, PendingAction, SupervisorDecision, ToolResult
from agentes.node_guards import especialista_protegido
from agentes.nodes.aplicar import aplicar, aplicar_node
from agentes.nodes.sintetizar import sintetizar, sintetizar_node
from agentes.nodes.supervisor import supervisor_node
from agentes.settings import AgentSettings
from agentes.state import initial_state


def estado_pendiente():
    return {**initial_state('[DOBLE] Consulta', 'hilo-original'),
            'final_answer': '[DOBLE] Borrador', 'plan': ['[DOBLE] Revisar'],
            'specialist_results': {'instalaciones': ToolResult(
                'ok', '[DOBLE] Instalaciones', data={'notas': ['original']})}}


@pytest.mark.parametrize('rol', ['documental', 'instalaciones'])
@pytest.mark.parametrize('campo,valor', [
    ('approved', True), ('done', True), ('thread_id', 'hilo-ajeno'),
    ('user_message', 'pedido-ajeno'), ('iterations', 0), ('plan', ['otro']),
    ('final_answer', 'otra'), ('supervisor_decision', SupervisorDecision('FINISH', 'otra')),
    ('pending_action', PendingAction('otra', 'otra')), ('plan_id', 'otro'),
])
def test_specialist_cannot_write_protected_fields(rol, campo, valor):
    state = estado_pendiente()
    before = deepcopy(state)
    with pytest.raises(ValueError, match='SPECIALIST_CONTRACT'):
        especialista_protegido(state, rol=rol, node=lambda s: {campo: valor})
    assert state == before


@pytest.mark.parametrize('resultado', [None, [], Command(goto='aplicar'), {'specialist_results': []},
                                      {'specialist_results': {'otro': ToolResult('ok', 'dato')}}])
def test_specialist_rejects_non_patch_commands_and_unknown_roles(resultado):
    with pytest.raises(ValueError, match='SPECIALIST_CONTRACT'):
        especialista_protegido(estado_pendiente(), rol='documental', node=lambda s: resultado)


@pytest.mark.parametrize('resultado', [
    None, {'status': 'ok', 'answer': 'dato'}, ToolResult('inventado', 'dato'),
    ToolResult('ok', None), ToolResult('ok', 'dato', error=1),
    ToolResult('ok', 'dato', data=[]), ToolResult('ok', 'dato', evidence=['fuente']),
    ToolResult('ok', 'dato', evidence=[Evidence(None, 'dato')]),
])
def test_specialist_result_has_runtime_type_checks(resultado):
    with pytest.raises(ValueError, match='SPECIALIST_CONTRACT'):
        especialista_protegido(estado_pendiente(), rol='documental',
                               node=lambda s: {'specialist_results': {'documental': resultado}})


@pytest.mark.parametrize('tipo', ['sustituir', 'mutar'])
def test_specialist_cannot_replace_or_mutate_other_role(tipo):
    state = estado_pendiente()
    before = deepcopy(state)

    def node(s):
        if tipo == 'sustituir':
            s['specialist_results']['instalaciones'] = ToolResult('ok', 'ajeno')
        else:
            s['specialist_results']['instalaciones'].data['notas'].append('ajeno')
        return {'specialist_results': s['specialist_results']}

    with pytest.raises(ValueError, match='SPECIALIST_CONTRACT'):
        especialista_protegido(state, rol='documental', node=node)
    assert state == before


@pytest.mark.parametrize('completo', [False, True])
def test_role_patch_preserves_others_and_detaches_returned_objects(completo):
    state = estado_pendiente()
    before = deepcopy(state)
    own = ToolResult('abstained', '', evidence=[Evidence('test://fuente', '')], data={'notas': []})
    update = {'specialist_results': {'documental': own}, 'debug_trace': ['documental: nuevo']}
    if completo:
        update['specialist_results']['instalaciones'] = deepcopy(state['specialist_results']['instalaciones'])
    result = especialista_protegido(state, rol='documental', node=lambda s: update)
    own.data['notas'].append('mutación posterior')
    result['specialist_results']['instalaciones'].data['notas'].append('solo salida')
    assert result['specialist_results']['documental'].data['notas'] == []
    assert state == before


def test_empty_result_map_does_not_delete_other_roles():
    state = estado_pendiente()
    result = especialista_protegido(state, rol='documental', node=lambda s: {'specialist_results': {}})
    assert result['specialist_results'] == state['specialist_results']
    assert especialista_protegido(state, rol='documental', node=lambda s: {}) == {}


@pytest.mark.parametrize('fase', ['especialista', 'sintetizar', 'aplicar'])
@pytest.mark.parametrize('falla', [False, True])
def test_inplace_mutation_is_isolated_even_when_callable_raises(fase, falla):
    state = estado_pendiente()
    if fase == 'aplicar':
        state['approved'] = True
    before = deepcopy(state)

    def node(s):
        s['approved'] = not bool(s.get('approved'))
        s['thread_id'] = 'ajeno'
        s['plan'].append('ajeno')
        s['specialist_results']['instalaciones'].data['notas'].clear()
        if falla:
            raise RuntimeError('Fallo sintético tras mutar')
        return {'especialista': {},
                'sintetizar': {'final_answer': 'Borrador', 'plan': ['Revisar']},
                'aplicar': {'done': True}}[fase]

    def ejecutar():
        if fase == 'especialista':
            return especialista_protegido(state, rol='documental', node=node)
        return (sintetizar_node if fase == 'sintetizar' else aplicar_node)(state, node=node)

    if falla:
        with pytest.raises(RuntimeError, match='tras mutar'):
            ejecutar()
    else:
        ejecutar()
    assert state == before


@pytest.mark.parametrize('fase', ['sintetizar', 'aplicar'])
@pytest.mark.parametrize('campo,valor', [('thread_id', 'ajeno'), ('iterations', 0),
                                      ('user_message', 'ajeno'), ('supervisor_decision', None)])
def test_synthesis_and_apply_cannot_write_coordination_fields(fase, campo, valor):
    state = estado_pendiente()
    update = {'final_answer': 'Respuesta', 'plan': ['Paso']} if fase == 'sintetizar' else {'done': True}
    if fase == 'aplicar':
        state['approved'] = True
    update[campo] = valor
    with pytest.raises(ValueError, match='SYNTHESIS_CONTRACT|APPLY_CONTRACT'):
        (sintetizar_node if fase == 'sintetizar' else aplicar_node)(state, node=lambda s: update)


@pytest.mark.parametrize('fase', ['especialista', 'sintetizar', 'aplicar'])
@pytest.mark.parametrize('traza', [None, 'evento', [None], [123]])
def test_trace_contract_rejects_non_text_events(fase, traza):
    state = estado_pendiente()
    if fase == 'aplicar':
        state['approved'] = True
    update = {'debug_trace': traza}
    if fase == 'sintetizar':
        update.update(final_answer='Respuesta', plan=['Paso'])
    if fase == 'aplicar':
        update['done'] = True
    with pytest.raises(ValueError, match='CONTRACT'):
        if fase == 'especialista':
            especialista_protegido(state, rol='documental', node=lambda s: update)
        else:
            (sintetizar_node if fase == 'sintetizar' else aplicar_node)(state, node=lambda s: update)


@pytest.mark.parametrize('patch', [
    {'approved': False}, {'plan': ['otra propuesta']}, {'specialist_results': {}},
    {'pending_action': PendingAction('externa', 'Otra acción')}, {'final_answer': 123},
])
def test_approved_close_cannot_replace_human_decision_plan_or_action(patch):
    state = {**estado_pendiente(), 'approved': True}
    with pytest.raises(ValueError, match='APPLY_CONTRACT'):
        aplicar_node(state, node=lambda s: {'done': True, **patch})


@pytest.mark.parametrize('respuesta', [
    'Texto arbitrario', '', '[DOBLE] Borrador'[:-1],
    'Prefacio\n[DOBLE] Borrador', '[DOBLE] Borrador'.replace('Borrador', 'Respuesta'),
])
def test_approved_answer_cannot_be_replaced_truncated_or_prefixed(respuesta):
    state = {**estado_pendiente(), 'approved': True}
    before = deepcopy(state)
    with pytest.raises(ValueError, match='APPLY_CONTRACT.*final_answer'):
        aplicar_node(state, node=lambda s: {'done': True, 'final_answer': respuesta})
    assert state == before


@pytest.mark.parametrize('patch', [
    {}, {'final_answer': '[DOBLE] Borrador'},
    {'final_answer': '[DOBLE] Borrador\nCierre informativo.'},
])
def test_approved_answer_can_be_omitted_preserved_or_extended(patch):
    state = {**estado_pendiente(), 'approved': True}
    before = deepcopy(state)
    result = aplicar_node(state, node=lambda s: {'done': True, **patch})
    assert result == {'done': True, **patch, 'debug_trace': ['HITL -> plan aprobado']}
    assert state == before


def test_mutating_injected_copy_cannot_replace_approved_answer():
    state = {**estado_pendiente(), 'approved': True}
    before = deepcopy(state)

    def reemplazar(s):
        s['final_answer'] = 'Texto ajeno'
        return {'done': True, 'final_answer': s['final_answer'] + '\nCierre'}

    with pytest.raises(ValueError, match='APPLY_CONTRACT.*final_answer'):
        aplicar_node(state, node=reemplazar)
    assert state == before


def test_rejected_answer_can_be_replaced_by_rejection_message():
    state = {**estado_pendiente(), 'approved': False}
    before = deepcopy(state)
    result = aplicar_node(state, node=lambda s: {
        'done': False, 'final_answer': 'Propuesta rechazada.',
        'plan': [], 'specialist_results': {},
    })
    assert result['final_answer'] == 'Propuesta rechazada.'
    assert result['done'] is False and result['plan'] == [] and result['specialist_results'] == {}
    assert state == before


def test_service_keeps_approved_answer_when_apply_replaces_it_and_allows_valid_retry():
    calls = []

    def cerrar(state):
        calls.append(state['final_answer'])
        return {'done': True, 'final_answer': (
            'RESPUESTA_NO_APROBADA' if len(calls) == 1
            else state['final_answer'] + '\nCierre informativo.'
        )}

    service = AgentService(
        documental_node=lambda s: {}, instalaciones_node=lambda s: {},
        sintetizar_node=sintetizar, aplicar_node=cerrar,
        settings=AgentSettings(max_iter=8),
    )
    hilo = service.nueva_conversacion()
    pending = service.procesar_turno('Consulta simulada', hilo)
    with pytest.raises(ValueError, match='APPLY_CONTRACT.*final_answer'):
        service.resolver_plan(hilo, True, plan_id=pending['plan_id'])
    failed = service.consultar_estado(hilo)
    assert failed['pendiente_hitl'] is True and failed['done'] is False
    assert failed['approved'] is True
    for campo in ('final_answer', 'plan', 'specialist_results', 'debug_trace', 'plan_id'):
        assert failed[campo] == pending[campo]
    final = service.resolver_plan(hilo, True, plan_id=pending['plan_id'])
    assert final['final_answer'] == pending['final_answer'] + '\nCierre informativo.'
    assert final['done'] is True and final['pendiente_hitl'] is False
    assert service.resolver_plan(hilo, True, plan_id=pending['plan_id']) == final
    assert calls == [pending['final_answer'], pending['final_answer']]


@pytest.mark.parametrize('valor', [True, 0, 'cerrado'])
def test_rejection_cannot_publish_invalid_or_foreign_plan(valor):
    state = {**estado_pendiente(), 'approved': False}
    with pytest.raises(ValueError, match='APPLY_CONTRACT'):
        aplicar_node(state, node=lambda s: {'done': False, 'plan': valor})


@pytest.mark.parametrize('tipo', ['valido', 'invalido', 'excepcion'])
def test_provider_mutation_cannot_escape_into_state_or_fallback(tipo):
    state = estado_pendiente()
    before = deepcopy(state)
    retained = []

    def provider(s):
        retained.append(s)
        s['approved'] = True
        s['iterations'] = 999
        s['specialist_results']['instalaciones'].data['notas'].clear()
        s['plan'].clear()
        if tipo == 'excepcion':
            raise RuntimeError('No copiar este detalle')
        return SupervisorDecision('documental', 'Propuesta') if tipo == 'valido' else None

    update = supervisor_node(state, route_provider=provider)
    assert state == before and update['iterations'] == 1
    assert update['supervisor_decision'].specialist == 'documental'
    retained[0]['specialist_results'].clear()
    assert state == before
    assert 'No copiar este detalle' not in str(update)


@pytest.mark.parametrize('campo,valor', [('approved', True), ('done', True), ('thread_id', 'ajeno'),
                                      ('iterations', 0), ('specialist_results', {
                                          'instalaciones': ToolResult('ok', 'resultado ajeno')})])
def test_real_service_rejects_adversarial_specialist_before_checkpoint_merge(campo, valor):
    calls = []

    def unexpected(state):
        calls.append(True)
        return aplicar(state)

    service = AgentService(documental_node=lambda s: {campo: valor}, instalaciones_node=lambda s: {},
                           sintetizar_node=sintetizar, aplicar_node=unexpected,
                           settings=AgentSettings(max_iter=8))
    hilo = service.nueva_conversacion()
    with pytest.raises(ValueError, match='SPECIALIST_CONTRACT'):
        service.procesar_turno('Consulta adversa simulada', hilo)
    state = service.consultar_estado(hilo)
    assert state['thread_id'] == hilo
    assert state['approved'] is None and state['done'] is False
    assert state['plan_id'] is None and not state['pendiente_hitl']
    assert state['specialist_results'] == {} and calls == []
    with pytest.raises(ValueError, match='REQUEST_INCOMPLETE'):
        service.procesar_turno('No sobrescribir el fallo', hilo)
