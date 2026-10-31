"""Conservative, observation-based action identity and replay safeguards.

An HTTP method is evidence of a request, not proof of a database mutation.
The guard is deliberately conservative: a non-GET request is write-capable
until an independently verified isolation mechanism is available.
"""
from urllib.parse import urlsplit

from .state import digest, route_pattern, group_control_signature


def record_instance(observation):
    path = urlsplit(observation.url).path
    if route_pattern(observation.url).split("?", 1)[0] == path:
        return None
    return digest([path, observation.session_context, observation.session_markers], 20)


def template_identity(observation):
    """A structural hypothesis, never an assertion of behavioral equivalence."""
    return digest([observation.route_pattern, observation.session_context, observation.session_markers,
                   sorted(group_control_signature(c) for c in observation.controls if c.safe),
                   [(f.method, route_pattern(f.action), [(x.name, x.input_type, x.required) for x in f.fields])
                    for f in observation.forms]], 20)


def action_identity(observation, action):
    """Location and form structure prevent same-label controls being merged."""
    locator = (urlsplit(action.target).path if action.kind == "link" and action.target else action.css_path)
    return digest([route_pattern(observation.url), record_instance(observation),
                   observation.session_context, observation.session_markers,
                   locator, action.kind, action.role, action.interaction,
                   action.component, action.frame_index, action.behavior_revision,
                   route_pattern(action.target) if action.target else None,
                   [(f.name, f.input_type, f.required) for f in action.fields]], 24)


def classify_behavior(source, action, result, network):
    # A failed response does not prove that a server did not commit the write.
    write = any(e.method.upper() not in {"GET", "HEAD", "OPTIONS"} for e in network)
    # A navigation that leaves and returns to the same page with changed
    # content is suspicious. Ordinary search/XHR results also change content,
    # so that alone must not suppress their normal exploration and replay.
    ambiguous_get_change = (action.kind == "link" and source.url == result.url
                            and source.content_fingerprint != result.content_fingerprint
                            and any(e.method.upper() == "GET" and not e.failure
                                    and e.resource_type == "document"
                                    and urlsplit(e.url).path != urlsplit(source.url).path
                                    for e in network))
    return {
        "action_identity": action_identity(source, action),
        "request_methods": sorted({e.method.upper() for e in network if not e.failure}),
        "write_capable_request_observed": write,
        "visible_state_changed": source.state_signature != result.state_signature,
        "state_change_confirmed": False,
        "possible_state_change": ambiguous_get_change,
        "classification": ("write_capable_request_observed" if write else
                           "possible_state_change" if ambiguous_get_change else "unknown"),
        "replay_safety": "observed_once_not_safely_replayable" if write or ambiguous_get_change else "unknown",
        "reason": "HTTP method alone does not establish application state change",
    }
