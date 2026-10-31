#!/usr/bin/env python3
"""Run matched whiteboard arms against a disposable, separately named stack.

Requires pre-existing local images and the documented schema file. Credentials,
SQL output and Playwright storage state stay in a temporary directory; this
operator harness is not imported by Agent 1. No existing container is touched.
"""
from __future__ import annotations
import argparse, json, os, secrets, subprocess, tempfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = Path('/Users/sanskritisingh/takehome-sanskriti-singh/server/schema.sql')
PREFIX = 'engramsec-state-lab'
URL = 'http://127.0.0.1:45173/'


def docker(*args, data=None, check=True):
    result = subprocess.run(['docker', *args], input=data, capture_output=True, timeout=60)
    if check and result.returncode:
        raise RuntimeError(f"Docker {args[0]} failed (exit {result.returncode}); details withheld")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--seconds', type=int, default=150)
    parser.add_argument('--skip-baseline', action='store_true', help='repeat treatment arms against a saved baseline')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    existing = docker('ps', '-a', '--filter', f'name=^{PREFIX}', '--format', '{{.Names}}').stdout
    if existing.strip():
        raise SystemExit('Disposable names already exist; refusing to alter them.')
    made = []
    network = False
    with tempfile.TemporaryDirectory(prefix='engramsec-state-eval-') as scratch:
        tmp = Path(scratch)
        auth = tmp / 'session.json'
        base = tmp / 'baseline'
        base.mkdir()
        archive = subprocess.run(['git', 'archive', '6c76b56'], cwd=ROOT, capture_output=True, check=True).stdout
        subprocess.run(['tar', '-xf', '-', '-C', str(base)], input=archive, check=True)
        password, secret = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
        try:
            docker('network', 'create', PREFIX); network = True
            docker('run', '-d', '--name', PREFIX+'-db', '--network', PREFIX, '--network-alias', 'db',
                   '-e', 'POSTGRES_USER=lab', '-e', 'POSTGRES_DB=lab', '-e', 'POSTGRES_PASSWORD='+password,
                   'postgres:16-alpine'); made.append(PREFIX+'-db')
            for _ in range(60):
                if docker('exec', PREFIX+'-db', 'pg_isready', '-U', 'lab', check=False).returncode == 0: break
                time.sleep(.5)
            else: raise RuntimeError('disposable database did not start')
            docker('run', '-d', '--name', PREFIX+'-server', '--network', PREFIX,
                   '-p', '127.0.0.1:45173:45173', '-e', 'DATABASE_URL=postgresql://lab:'+password+'@db:5432/lab',
                   '-e', 'SECRET_KEY='+secret, 'takehome-sanskriti-singh-server'); made.append(PREFIX+'-server')
            docker('run', '-d', '--name', PREFIX+'-client', '--network', 'container:'+PREFIX+'-server',
                   'takehome-sanskriti-singh-client', 'npm', 'run', 'dev', '--', '--host', '0.0.0.0', '--port', '45173'); made.append(PREFIX+'-client')
            for _ in range(60):
                try:
                    with urllib.request.urlopen(URL, timeout=1): break
                except Exception: time.sleep(.5)
            else: raise RuntimeError('disposable client did not start')
            rows = []
            arms = ([] if args.skip_baseline else [('A_baseline', base, [])])
            arms += [('B_state', ROOT, ['--no-record-aware-graph'])]
            arms += [(f'C_state_record_{i+1}', ROOT, []) for i in range(args.repeats)]
            for name, code, extra in arms:
                docker('exec', PREFIX+'-db', 'psql', '-U', 'lab', '-d', 'lab', '-v', 'ON_ERROR_STOP=1',
                       '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
                docker('exec', '-i', PREFIX+'-db', 'psql', '-U', 'lab', '-d', 'lab', '-v', 'ON_ERROR_STOP=1', data=SCHEMA.read_bytes())
                subprocess.run([str(ROOT/'.venv/bin/python'), str(ROOT/'experiments/seed_whiteboard_session.py'), '--out', str(auth)],
                               capture_output=True, check=True, timeout=40)
                ids = set(docker('exec', PREFIX+'-db', 'psql', '-U', 'lab', '-d', 'lab', '-At',
                                 '-c', 'SELECT id FROM canvases').stdout.decode().splitlines())
                out = (args.output / name).resolve()
                cmd = [str(ROOT/'.venv/bin/python'), str(code/'experiments/run_resource_spider_ablation.py'),
                       '--app','external','--url',URL,'--storage-state',str(auth),'--context-label','authenticated',
                       '--root',str(out),'--variants','adaptive_readiness','--seconds',str(args.seconds),
                       '--max-transitions','120','--max-browser-actions','300','--max-resource-fetches','100',
                       '--document-budget','70','--script-budget','20','--stylesheet-budget','10','--asset-budget','20',
                       '--max-total-http-requests','1000','--exploration-policy','multidimensional',
                       '--resource-allocation','shared_http','--max-speculative-fetches','25','--http-verification-reserve','0.3',
                       '--resource-frontier-model','persistent','--passive-document-max-depth','6','--budget-aware-deepening',
                       '--hard-max-resource-depth','8','--html-extraction','standards','--response-body-reader','bounded_stream',
                       '--runtime-listener-observation','revisit','--replay-policy','structure','--framework-handler-probe','5000', *extra]
                env = os.environ.copy(); env['PYTHONPATH'] = str(code)
                start = time.monotonic()
                proc = subprocess.run(cmd, cwd=code, env=env, capture_output=True, timeout=args.seconds+60)
                if proc.returncode: raise RuntimeError(f'{name}: mapper failed (exit {proc.returncode}); raw diagnostics withheld')
                graph = json.loads((out/'adaptive_readiness'/'graph_a.json').read_text())
                metrics = json.loads((out/'adaptive_readiness'/'metrics.json').read_text())
                raw_run = json.loads((out/'adaptive_readiness'/'run.json').read_text())
                count = int(docker('exec', PREFIX+'-db', 'psql', '-U', 'lab', '-d', 'lab', '-At',
                                   '-c', 'SELECT count(*) FROM canvases').stdout)
                found = {i for i in ids if any('/'+i in o.get('url','') for o in raw_run.get('observations', []))}
                # Some graph versions expose observations on state nodes instead.
                found |= {i for i in ids if any('/'+i in s.get('url','') for s in graph['nodes']['states'])}
                row = {'arm':name, 'starting_records':len(ids), 'final_records':count, 'created_records':count-len(ids),
                       'existing_records_observed':len(found), 'elapsed_seconds':round(time.monotonic()-start,2),
                       'browser_actions':metrics.get('browser_actions'), 'observed_transitions':metrics.get('transitions_observed'),
                       'replay_attempts':metrics.get('replay_attempts'), 'replay_successes':metrics.get('replay_success_numerator'),
                       'untested_paths':metrics.get('replay_untested_paths'), 'missing_evidence':metrics.get('graph_connections_missing_evidence'),
                       'incorrect_merges_audit':metrics.get('incorrect_state_merges'),
                       'repeat_actions_suppressed':metrics.get('repeat_write_actions_suppressed'),
                       'unsafe_restorations_suppressed':metrics.get('unsafe_restorations_suppressed'),
                       'instance_references':len(graph['nodes'].get('record_instances',[])),
                       'write_capable_actions':sum(any(e.get('method','GET').upper() not in ('GET','HEAD','OPTIONS') and not e.get('failure') for e in t.get('network',[])) for t in raw_run['transitions']),
                       'observed_http_requests':metrics.get('observed_http_requests'),
                       'resource_gets':metrics.get('resource_fetches_attempted'),
                       'replay_excluded':metrics.get('replay_scheduler',{}).get('state_changing_workflows_not_replayed')}
                rows.append(row); (args.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
                print(json.dumps(row), flush=True)
        finally:
            for container in reversed(made): docker('rm','-f',container,check=False)
            if network: docker('network','rm',PREFIX,check=False)
    return 0

if __name__ == '__main__': raise SystemExit(main())
