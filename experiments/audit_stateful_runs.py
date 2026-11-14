#!/usr/bin/env python3
"""Reaudit saved runs without changing the original metrics or observations."""
import argparse
import json
from pathlib import Path
from agent1.explorer import Explorer
from agent1.schema import RunArtifact

p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
args = p.parse_args()
rows = []
for path in sorted(args.root.glob('*/adaptive_readiness/run.json')):
    artifact = RunArtifact.model_validate_json(path.read_text())
    explorer = object.__new__(Explorer)
    explorer.artifact = artifact
    claims = explorer._audit_connection_evidence()
    rows.append({'arm': path.parent.parent.name,
                 'recorded_missing_evidence': artifact.metrics.graph_connections_missing_evidence,
                 'reanalysis_missing_evidence': sum(not claim.complete for claim in claims),
                 'write_capable_actions': sum(any(event.method.upper() not in {'GET', 'HEAD', 'OPTIONS'} and not event.failure
                                                   for event in transition.network)
                                              for transition in artifact.transitions),
                 'resource_gets': artifact.metrics.resource_fetches_attempted,
                 'replay_failure_reasons': artifact.metrics.replay_failure_reasons})
(args.root / 'posthoc_reanalysis.json').write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps(rows))
