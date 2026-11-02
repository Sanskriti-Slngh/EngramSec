"""Static check for application-specific knowledge in engine/model code.

Flags string literals (docstrings excluded) that contain a fixture or
ground-truth route, a fixture selector, a ground-truth label, or a
language-dependent action word. The ACG package must be clean; legacy modules
are scanned only to record the known baseline.
Run: .venv/bin/python -m evaluation.purity_check agent1/model
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION_WORDS = {"create", "save", "delete", "remove", "publish", "share", "search", "submit", "login", "logout",
                "signin", "signup", "cart", "checkout", "update", "edit", "upload", "invite", "approve",
                "删除", "保存", "搜索", "提交", "登录"}
ROUTE = re.compile(r"^/[A-Za-z][\w\-/{}.]*[A-Za-z]$")
SELECTOR = re.compile(r"^[#.][A-Za-z][\w\-]{2,}$|\[[a-z\-]+[\^$*]?=")


def _literals(tree: ast.AST) -> list[tuple[int, str]]:
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings]


def deny_lists() -> tuple[set[str], set[str], set[str]]:
    routes, selectors, labels = set(), set(), set()
    for source in sorted((ROOT / "development_apps").glob("*.py")):
        for _, text in _literals(ast.parse(source.read_text(encoding="utf-8"))):
            for match in re.findall(r"""(?:href|action|fetch\()\s*[=(]?\s*['"](/[A-Za-z][^'"?#]*)""", text):
                routes.add(match.rstrip("/"))
            for match in re.findall(r"""id=['"]?([A-Za-z][\w\-]{3,})""", text):
                selectors.add("#" + match)
            if ROUTE.match(text):
                routes.add(text.rstrip("/"))
            if SELECTOR.search(text):
                selectors.add(text)
    for gt in sorted((ROOT / "evaluation" / "annotations").glob("*.json")):
        data = json.loads(gt.read_text(encoding="utf-8"))
        routes.update(t for t in data.get("templates", []) if len(t) > 1)
        for cap in data.get("capabilities", []):
            routes.update(op["route"] for op in cap.get("operations", []) if len(op["route"]) > 1)
            labels.update(ep["label"] for ep in cap.get("entry_points", []) if ep.get("label"))
    return {r for r in routes if len(r) >= 4}, {s for s in selectors if len(s) >= 4}, {l for l in labels if len(l) >= 3}


def scan(paths: list[Path]) -> list[dict[str, object]]:
    routes, selectors, labels = deny_lists()
    hits = []
    for path in paths:
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for file in files:
            for line, text in _literals(ast.parse(file.read_text(encoding="utf-8"))):
                reasons = []
                if any(route in text for route in routes):
                    reasons.append("fixture_route")
                if any(selector in text for selector in selectors):
                    reasons.append("fixture_selector")
                if text in labels:
                    reasons.append("ground_truth_label")
                # Whole identifiers: contract values such as "form_submit" are schema
                # vocabulary, not UI text; standalone words are flagged.
                words = {w.lower() for w in re.findall(r"\w+", text)}
                if words & ACTION_WORDS:
                    reasons.append("language_dependent_word")
                if reasons:
                    hits.append({"file": str(file.relative_to(ROOT)), "line": line, "reasons": reasons,
                                 "literal": text[:80]})
    return hits


if __name__ == "__main__":
    targets = [ROOT / arg for arg in sys.argv[1:]] or [ROOT / "agent1" / "model"]
    found = scan(targets)
    for hit in found:
        print(f"{hit['file']}:{hit['line']} {','.join(hit['reasons'])} {hit['literal']!r}")
    print(f"{len(found)} hit(s)")
    raise SystemExit(1 if found else 0)
