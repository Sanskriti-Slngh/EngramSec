from __future__ import annotations


# Evaluator-only truth. The mapper never imports this module or fixture implementation.
SEARCH_CASES = {
    "functional_literal": {
        "path": "/functional-literal",
        "functional": True,
        "reason": "the submitted query selects a distinct result record",
    },
    "echo_only": {
        "path": "/echo-only",
        "functional": False,
        "reason": "the page only repeats the submitted text",
    },
    "permanent_sidebar": {
        "path": "/permanent-sidebar",
        "functional": False,
        "reason": "Alpha and Beta links are permanent navigation and never respond to the query",
    },
    "functional_nonliteral": {
        "path": "/functional-nonliteral",
        "functional": True,
        "reason": "queries select different records whose titles use synonyms rather than query text",
    },
}
