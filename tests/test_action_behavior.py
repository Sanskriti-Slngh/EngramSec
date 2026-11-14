from types import SimpleNamespace as N
from agent1.action_behavior import action_identity, classify_behavior, record_instance
from agent1.replay_scheduler import workflow_changes_state
from agent1.explorer import Explorer


def obs(url, content='a', session='user'):
    return N(url=url, session_context=session, session_markers={}, route_pattern='/records/{instance}',
             state_signature=content, content_fingerprint=content)


def button(css, revision=None):
    return N(kind='form_submit', css_path=css, role='button', interaction='click', component='main',
             frame_index=0, behavior_revision=revision, target=None, fields=[])


def test_same_label_controls_handler_revisions_and_record_context_remain_distinct():
    one, two = obs('http://localhost/records/1'), obs('http://localhost/records/2')
    assert record_instance(one) != record_instance(two)
    assert action_identity(one, button('#a')) != action_identity(one, button('#b'))
    assert action_identity(one, button('#a')) != action_identity(two, button('#a'))
    assert action_identity(one, button('#a')) != action_identity(one, button('#a', 'revised'))
    assert record_instance(one) != record_instance(obs('http://localhost/records/1', session='other'))


def test_methods_are_not_claimed_as_mutation_proof():
    source = obs('http://localhost/records/1')
    changed = obs('http://localhost/records/1', 'b')
    event = N(method='POST', failure=None, resource_type='fetch', url='http://localhost/counter')
    post = classify_behavior(source, button('#a'), changed, [event])
    assert post['write_capable_request_observed'] and not post['state_change_confirmed']
    event.failure = 'connection reset after send'
    assert classify_behavior(source, button('#a'), changed, [event])['write_capable_request_observed']
    event.failure = None
    event.method = 'GET'
    event.resource_type = 'document'
    link = button('#a'); link.kind = 'link'; link.target = 'http://localhost/counter'
    get = classify_behavior(source, link, changed, [event])
    assert not get['write_capable_request_observed'] and get['possible_state_change']
    assert not get['state_change_confirmed']


def test_recorded_write_during_restoration_blocks_replay_even_without_prefix_transition():
    transition = N(workflow_path=[], prerequisite_network=[N(network=[N(method='POST')])])
    assert workflow_changes_state(transition, set())


def test_old_checkpoint_write_evidence_is_recovered_without_a_result():
    source = obs('http://localhost/records/1')
    source.id = 'source'
    action = button('#create')
    transition = N(behavior={}, source_observation_id='source', result_observation_id=None,
                   action=action, network=[N(method='POST', failure='connection reset')])
    explorer = object.__new__(Explorer)
    explorer.artifact = N(transitions=[transition], observations=[source])
    assert explorer._known_write(source, action)
