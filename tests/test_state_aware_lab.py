"""Black-box browser checks against a disposable SQLite application."""
from pathlib import Path
import sqlite3

from agent1.explorer import Explorer
from agent1.exporter import build_graph_a
from agent1.schema import RunConfig
from development_apps.stateful_lab import start_stateful_lab

ROOT = Path(__file__).resolve().parents[1]


def test_stateful_exploration_keeps_records_and_does_not_repeat_post(tmp_path):
    database = tmp_path / 'lab.sqlite'
    server, url, reset, log = start_stateful_lab(database)
    try:
        artifact = Explorer(RunConfig(start_url=url, output_dir=tmp_path / 'out',
            policy='multidimensional', exploration_mode='persistent',
            max_seconds=35, max_transitions=30, max_browser_actions=100,
            settle_ms=60, action_timeout_ms=1500, allow_post_forms=True,
            replay_policy='structure', state_aware_exploration=True), ROOT).run()
        posts = [path for method, path in log if method == 'POST']
        assert posts.count('/api/records') == 1, posts
        assert sum(method == 'GET' and path == '/counter' for method, path in log) <= 1
        assert '/api/delete' not in posts
        assert posts.count('/api/search') == 1
        assert posts.count('/api/records/1') <= 1
        with sqlite3.connect(database) as db:
            records = db.execute('SELECT id, name FROM records ORDER BY id').fetchall()
        assert any(i == 1 for i, _ in records) and any(i == 2 for i, _ in records)
        seen = {o.url.rsplit('/', 1)[-1] for o in artifact.observations if '/records/' in o.url}
        assert {'1', '2'} <= seen
        graph = build_graph_a(artifact)
        instances = graph['nodes']['record_instances']
        assert len(instances) >= 2
        first = next(i for i in instances if i['url'].endswith('/records/1'))
        second = next(i for i in instances if i['url'].endswith('/records/2'))
        edges = graph['edges']
        first_templates = {e['target'] for e in edges if e['source'] == first['id'] and e['type'] == 'observed_with_template'}
        second_templates = {e['target'] for e in edges if e['source'] == second['id'] and e['type'] == 'observed_with_template'}
        assert first_templates & second_templates
        assert any(t.behavior.get('write_capable_request_observed') for t in artifact.transitions)
        readonly_search = next(t for t in artifact.transitions if any(e.url.endswith('/api/search') for e in t.network))
        assert readonly_search.behavior['write_capable_request_observed']
        assert not readonly_search.behavior['state_change_confirmed']
        assert all(not t.behavior.get('state_change_confirmed') for t in artifact.transitions)
        # Non-GET operations remain untested even when exploration permits POST.
        for t in artifact.transitions:
            if t.behavior.get('write_capable_request_observed'):
                assert not any(r.transition_id == t.id for r in artifact.replays)
        assert any(t.action.label == 'Submit' and '/records/' in next(o.url for o in artifact.observations if o.id == t.source_observation_id) for t in artifact.transitions)
        assert any(t.behavior.get('possible_state_change') for t in artifact.transitions)
        assert any(t.status == 'not_tested' and 'UnsafeRestoration' in (t.error or '') for t in artifact.transitions)
        reset()
        with sqlite3.connect(database) as db:
            assert db.execute('SELECT COUNT(*) FROM records').fetchone()[0] == 2
    finally:
        server.shutdown()
        server.server_close()
