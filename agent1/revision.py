from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def code_revision(repository_root: Path) -> str:
    """Return Git HEAD plus a deterministic mapper-source fingerprint."""

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip() or "unknown"
    candidates = list((repository_root / "agent1").glob("*.py"))
    candidates += list((repository_root / "experiments").glob("*.py"))
    candidates += [
        repository_root / "pyproject.toml",
        repository_root / "requirements-agent1.txt",
        repository_root / "requirements-baselines.txt",
    ]
    digest = hashlib.sha256()
    for path in sorted(item for item in candidates if item.is_file()):
        digest.update(str(path.relative_to(repository_root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"{head}+mapper-{digest.hexdigest()[:12]}"
