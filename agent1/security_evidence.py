"""Security-oriented capability evidence: a derived view over an `acg/1` export (kept outside the language-independent model package).

The frozen ACG contract is unchanged. This view turns each capability into a record
a downstream assessment agent can reason about:

    trigger            what the agent operated (control kind, label, interaction)
    network_effect     the requests the capability issued (method, route shape, parameter names)
    response           response statuses observed for those requests
    state_change       "possible_confirm_separately" | "blocked_by_policy" | "none_observed"
    security_relevance heuristic categories, with the matched terms (never a finding)
    vulnerability_status always "not_assessed": Agent 1 maps; it does not judge

Only the agent's own evidence is used. No values, bodies or cookies are read: parameter
names, methods, route shapes and status codes only.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .state import route_pattern

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
POLICY_BLOCK = "net::ERR_ACCESS_DENIED"      # the write policy's abort reason (see BrowserSession)

# Heuristic, keyword-based relevance. The categories describe what a downstream assessor may
# want to examine; they are hypotheses from names, not observations of security behaviour.
RELEVANCE = {
    "authentication": r"log[-_ ]?in|sign[-_ ]?in|log[-_ ]?out|sign[-_ ]?out|auth|session|token|password|passwd|otp|mfa|2fa|登录|登出|密码",
    "account_lifecycle": r"regist|sign[-_ ]?up|account|profile|user(?:name)?s?\b|member|invite|注册|账号|用户",
    "authorization_admin": r"admin|role|permission|privilege|grant|acl|manage|管理|权限",
    "file_handling": r"upload|file|import|export|download|attachment|avatar|image|上传|下载|文件",
    "search_query": r"search|query|filter|keyword|\bq\b|find|搜索|查询",
    "payment_order": r"cart|checkout|order|payment|invoice|coupon|voucher|price|购物车|订单|支付",
    "content_mutation": r"create|update|edit|save|comment|post|publish|delete|remove|新增|编辑|保存|删除",
    "configuration": r"setting|config|preference|option|设置|配置",
}
_RELEVANCE = {k: re.compile(v, re.I) for k, v in RELEVANCE.items()}


def _relevance(texts: list[str]) -> dict[str, list[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for text in texts:
        for name, pattern in _RELEVANCE.items():
            for m in pattern.finditer(text or ""):
                found[name].add(m.group(0).lower())
    return {k: sorted(v) for k, v in sorted(found.items())}


def capability_evidence(export: dict[str, Any], run: dict[str, Any]) -> list[dict[str, Any]]:
    """One security evidence record per capability in ``export`` (an ``acg/1`` dict)."""
    ops = {o["id"]: o for o in export.get("operations", [])}
    affs = {a["id"]: a for a in export.get("affordances", [])}
    trans = {t["id"]: t for t in run.get("transitions", [])}
    records = []
    for cap in export.get("capabilities", []):
        actions = [trans[a] for a in cap.get("action_ids", []) if a in trans]
        triggers = []
        for binding in cap.get("bindings", []):
            aff = affs.get(binding["affordance_id"]) or {}
            fam = aff.get("family") or {}
            label = next((l["text"] for l in aff.get("labels", [])), None)
            triggers.append({"kind": fam.get("kind"), "interaction": fam.get("interaction"), "label": label,
                             "provenance": fam.get("provenance", "snapshot")})
        if not triggers:
            triggers = [{"kind": t["action"].get("kind"), "interaction": t["action"].get("interaction"),
                         "label": t["action"].get("label"), "provenance": t["action"].get("provenance")}
                        for t in actions[:1]]
        effects = []
        statuses: dict[str, set] = defaultdict(set)
        blocked = []
        for op_id in cap.get("operation_ids", []):
            op = ops.get(op_id)
            if not op:
                continue
            effects.append({"channel": op.get("channel"), "method": op.get("method"), "route": op.get("route"),
                            "params": op.get("params", [])})
        for t in actions:
            for e in t.get("network", []):
                key = f"{(e.get('method') or 'GET').upper()} {route_pattern(e.get('url', '')).split('?')[0]}"
                if e.get("failure") == POLICY_BLOCK:
                    blocked.append(key)
                elif e.get("status") is not None:
                    statuses[key].add(int(e["status"]))
        write_routes = {f"{(x['method'] or '').upper()} {x['route']}" for x in effects
                        if (x["method"] or "").upper() in WRITE_METHODS}
        succeeded_writes = [k for k in write_routes if any(200 <= s < 400 for s in statuses.get(k, ()))]
        if blocked:
            state_change = "blocked_by_policy"
        elif succeeded_writes:
            state_change = "possible_confirm_separately"
        elif write_routes:
            state_change = "write_attempted_outcome_unknown"
        else:
            state_change = "none_observed"
        texts = [x.get("route") or "" for x in effects] + [p for x in effects for p in x.get("params", [])] \
            + [t.get("label") or "" for t in triggers]
        records.append({
            "capability_id": cap["id"],
            "status": cap.get("status"),
            "role": cap.get("role"),
            "trigger": triggers,
            "network_effect": effects,
            # Statuses of the capability's own operations only (not page subresources).
            "response": {k: sorted(v) for k, v in sorted(statuses.items())
                         if k in {f"{(x['method'] or 'GET').upper()} {x['route']}" for x in effects}},
            "blocked_requests": sorted(set(blocked)),
            "state_change": state_change,
            "visible_effects": [f"{e['kind']}:{e['target']}" for e in cap.get("effects", [])],
            "security_relevance": _relevance(texts),
            "security_relevance_basis": "heuristic keyword match on route, parameter names and trigger labels",
            "vulnerability_status": "not_assessed",
            "evidence_ids": cap.get("evidence_ids", []),
        })
    return records
