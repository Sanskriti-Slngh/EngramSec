# Proposed application model: the Application Capability Graph (ACG)

Status: design proposal. No production code was changed.
Depends on: [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) (problems) and [RELATED_WORK_AND_METHOD_COMPARISON.md](RELATED_WORK_AND_METHOD_COMPARISON.md) (methods).
Consumed by: [EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) (which queries it) and [GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) (which scores it).

## 1. Purpose and principles

The ACG is Agent 1's **working model** of the application. It is updated after every observation and queried before every decision. Graph A becomes one export view of it. The ACG answers questions such as:
- What can a user do here?
- On which entities?
- From which interfaces?
- Under which conditions?
- With what observable effect?
- How sure are we, and why?

Design principles, each tied to an audited failure:

| Principle | Failure it addresses (audit §) |
|---|---|
| **P1. Separate concepts get separate node types.** Template ≠ runtime state ≠ entity instance ≠ capability ≠ concrete action. | One hash carries template, data and session (§2.2) |
| **P2. Every claim is a hypothesis with a status, evidence list and confidence.** Observation never silently becomes truth. | "Validated" conflated reproducibility with function (§2.7) |
| **P3. Identity is resolved, not hashed.** Merges are reversible `same_as` claims with evidence. Contradictions split them. | Whiteboard 5-canvas merge; ComfyUI 6-way split (§2.2) |
| **P4. Capabilities are defined by behavior (operations + effects on entity types), not by the control that triggers them.** | Two interfaces → two features; same shape, different behavior → one feature (§2.3) |
| **P5. The evidence log is append-only; the model is a materialized view over it.** | Post-hoc grouping in `_finalize` never fed back (§2.3) |
| **P6. No raw values.** Identity and dependency evidence uses keyed hashes and shapes, never stored values, credentials or bodies. | Existing constraint; preserved |

## 2. Layers and node types

```
 ┌──────────────────────────────── EPISTEMIC LAYER ────────────────────────────────────────┐
 │  Hypothesis ── tested_by ──► Experiment ── produced ──► Evidence (append-only log)       │
 │      ▲ every edge/node below carries {status, confidence, evidence_ids, provenance}      │
 └──────┼───────────────────────────────────────────────────────────────────────────────────┘
 ┌──────┴──────────────────────── CAPABILITY LAYER ────────────────────────────────────────┐
 │  FunctionalArea ─contains─► Capability ─realized_by─► Operation (request structure)      │
 │                               │  ▲  │                     │                              │
 │                     requires  │  │  └─has_effect─► EffectType ─on─► EntityType           │
 │                               ▼  │ enables                                               │
 │                            Condition (pre/post predicate over entity/session/view facts) │
 └───────────────────────────────┼──────────────────────────────────────────────────────────┘
 ┌───────────────────────────────┴──── INTERFACE LAYER ────────────────────────────────────┐
 │  EntryPoint ─exposes─► Binding(Affordance ⇄ Capability) ◄─offers─ Affordance            │
 │  PageTemplate ◄─instance_of─ ViewState ─contains─► ComponentState                        │
 │       ViewState ─offers─► Affordance ; Transition(ViewState, Affordance, inputs → ViewState)│
 └───────────────────────────────┬──────────────────────────────────────────────────────────┘
 ┌───────────────────────────────┴──────── DOMAIN LAYER ───────────────────────────────────┐
 │  EntityType ◄─instance_of─ EntityInstance ─displayed_in─► ViewState                      │
 │  Role / SessionContext  ─scopes─► everything above                                       │
 │  EnvironmentState (snapshot id, reset lineage) ─scopes─► Evidence                        │
 └──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Node type catalogue

| Node | What it denotes | Identity (key) | Example |
|---|---|---|---|
| `Observation` | One raw browser snapshot (existing type, unchanged) | sequence id | `obs_000123` |
| `PageTemplate` | A structural page kind: route pattern + stable control/form *skeleton*, excluding data | digest(route pattern, skeleton) | `/canvas/{uuid}` editor page |
| `ViewState` | An abstract runtime state of one template under one role: the template plus the *behavior-relevant* facts (open modal, active tab, selected tool, list empty/non-empty) | digest(template, abstraction predicates) under the current abstraction | canvas editor, share dialog open, 0 shapes |
| `ComponentState` | State of one region (dialog, drawer, tab panel, menu, toast) independent of the page | digest(template, region locator, region skeleton) | "Share" dialog |
| `Affordance` | An actionable element on a template plus interaction kind | digest(template, locator family, interaction, provenance) | "+ Create canvas" submit on dashboard |
| `EntryPoint` | Where a capability can be *started*: a template + affordance, or a direct URL/operation | `(template, affordance)` or `(operation)` | dashboard form; `/canvas/{uuid}` direct link |
| `Transition` | One executed affordance in one concrete state with input references → result | existing transition id | `t_0042` |
| `Operation` | A server interface: method + route pattern + parameter-name set + body encoding + response shape | `request_structure_key` (existing) + response-shape digest | `POST /api/canvases {name} json → {id,name,owner}` |
| `EntityType` | A kind of domain object | digest(identity-source family, response shape, template family); stored as `E1`, `E2`, …, with verbatim display-label candidates and their provenance (§5.6) | `E1` (label candidates: route segment `canvas`, JSON key `canvases`) |
| `EntityInstance` | One object | keyed-HMAC of its strongest identity value (§5.2) | canvas `ei_7f3…` |
| `Capability` | A behaviorally distinct function, identified by its **behavior signature** (§5.3). It may carry a *behavioral class* if a grounding rule fires (§5.6), and display labels with provenance. Otherwise it is an **unidentified operation** | digest(role, operation keys incl. dispatch values and WebSocket message classes, effect atoms with targets; entry template family when no operation) | stored as `cap_3f2a [instance_appeared(E1) via POST /api/canvases]`; display label "Create canvas" (from affordance text) is an annotation only |
| `FunctionalArea` | A cluster of capabilities over related entity types and templates | community id (§5.4) | `area_2` (display labels only from member capabilities' labels) |
| `Condition` | A predicate needed before, or established after, a capability | normalized predicate | `session.role ⊇ authenticated`, `exists(Canvas owned_by self)`, `cart.count ≥ 1` |
| `EffectType` | An observable effect atom (§5.3) | atom kind + target | `instance_appeared(E1)`, `collection_membership_changed(E3)`, `navigated(T4)`, `instance_fields_changed(E1.K2)`, `visual_region_changed(R1)`, `message_received(M2)`; adapter-reported external effects only via §6.4 |
| `Role` | Session context with its capabilities | operator-supplied label + marker-name digest | `anonymous`, `customer`, `admin` |
| `EnvironmentState` | A known application data state | adapter snapshot id + lineage | `wb-seed-2canvas@sha…` |
| `Hypothesis` | A claim not yet supported enough to be a fact | claim id | "Share requires an existing canvas" |
| `Experiment` | A planned or executed test of hypotheses | id | replay of t_0042 from snapshot S0 |
| `Evidence` | An immutable record: observation, network event, CDP snapshot, adapter fact, external report | id | existing ids where possible |

`Feature` and `FunctionalWorkflow` (current Graph A) are **not** carried forward as concepts. Each of them is a projection:
- `Feature` ≈ `(Capability, Binding)` pairs with observed status;
- `FunctionalWorkflow` ≈ a `Transition` path that witnesses a `Capability`.

### 2.2 Why ViewState and PageTemplate are separate (and how abstraction is chosen)

A template is *structure*; a view state is *behavior-relevant structure*. The abstraction function `α: Observation → ViewState` is **not fixed**. It starts coarse and is refined only when evidence shows two observations under one abstract state behave differently. This is the APE / CEGAR idea (related work §2.3, §3.2):
- the same affordance leads to different templates;
- an affordance present in one is absent in the other;
- or the same operation yields a different effect.

`α` is a sequence of predicates over the observation:

```python
@dataclass(frozen=True)
class AbstractionPredicate:
    id: str
    kind: Literal["route_param_present", "region_visible", "control_set_contains",
                  "collection_nonempty", "field_value_class", "behavior_revision",
                  "role_marker", "entity_bound"]
    argument: str                      # e.g. region locator family, control skeleton id
    introduced_by: str                 # evidence id of the split that justified it
    template_id: str                   # predicates are per template, not global
```

Page *content* (text) is **never** part of `α` by default. The ComfyUI 6-way split came from exactly that. Content enters `α` only through a typed predicate such as `collection_nonempty`, after a split is justified.

## 3. Relationships

Every edge has the same envelope (§4). Edge types:

| Edge | From → To | Meaning |
|---|---|---|
| `instance_of` | ViewState → PageTemplate; EntityInstance → EntityType | classification |
| `contains` | ViewState → ComponentState; FunctionalArea → Capability | composition |
| `offers` | ViewState → Affordance | affordance available in this abstract state |
| `binds` | Affordance → Capability (via `Binding` node, carrying input mapping) | this affordance invokes this capability |
| `exposes` | EntryPoint → Capability | capability can start here |
| `realized_by` | Capability → Operation | server interface used |
| `has_effect` | Capability → EffectType | observed or verified effect |
| `on` | EffectType → EntityType | effect target |
| `requires` | Capability → Condition | precondition |
| `establishes` / `invalidates` | Capability → Condition | postcondition |
| `enables` | Capability → Capability | derived: A establishes a condition B requires |
| `produces` / `consumes` | Operation → EntityType (field) | ID flow: response field later appears in a request/URL (RESTler producer–consumer) |
| `displays` | ViewState → EntityInstance | view shows this instance |
| `same_as` / `distinct_from` | entity, template, view or capability ↔ same kind | reversible identity claims |
| `equivalent_interface` | Binding ↔ Binding | two interfaces invoke the same capability (derived from `binds` to the same Capability) |
| `witnessed_by` | any claim → Transition/Experiment/Evidence | provenance |
| `available_to` | Capability → Role | role scoping |
| `observed_in` | Evidence → EnvironmentState | which data state the evidence came from |

## 4. Evidence, provenance and confidence

### 4.1 Claim envelope

```python
class ClaimStatus(StrEnum):
    HYPOTHESIZED = "hypothesized"   # inferred, never observed (e.g. from a static reference)
    OBSERVED = "observed"           # seen once in exploration
    REPRODUCED = "reproduced"       # re-observed from an independent starting state
    VERIFIED = "verified"           # an oracle confirmed the claimed effect (§4.3)
    REFUTED = "refuted"             # an experiment contradicted it
    BLOCKED = "blocked"             # could not be tested: safety, isolation or budget (reason kept)

class Claim(BaseModel):
    id: str
    subject: str; predicate: str; object: str        # e.g. cap_create_canvas requires cond_authenticated
    status: ClaimStatus
    support: float = 0.0       # weighted evidence for   (Beta α − 1)
    against: float = 0.0       # weighted evidence against (Beta β − 1)
    evidence_ids: list[str]    # append-only; never rewritten
    sources: set[Literal["dom", "cdp", "network", "resource", "framework_probe",
                         "adapter_ground_truth", "external_tool", "inference"]]
    role: str | None; environment_state: str | None
    derived_from: list[str] = []   # claim ids for inferred claims (e.g. `enables`)
    blocked_reason: str | None = None
    first_seen: int; last_seen: int  # observation sequence numbers
```

- **Confidence** is the posterior probability `p` that the claim is true. Each experiment updates it by Bayes' rule, using the error rates of the evidence channel that produced the outcome: a sensitivity and a false-positive rate per experiment kind ([EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) §5.2, table C). `support` and `against` count positive and negative outcomes for audit. There are no hand-set evidence weights.
- **Status and confidence are both reported** because they answer different questions:
  - status says what kind of test was passed;
  - the posterior says how strongly the outcomes support the claim, given the channel's known error rates.
- **`inference`-sourced claims** (for example `enables` derived from conditions) can never exceed `OBSERVED` until a transition witnesses them.

### 4.2 Privacy-preserving evidence extensions

Two new evidence kinds give entity and dependency inference what it needs without storing values.

1. **Response shape.** For JSON/XML responses to same-origin Fetch/XHR, record:
   - the *key-path skeleton* (key names, value types, array lengths bucketed to {0, 1, 2–10, >10});
   - which key paths look like identifiers (`id`, `*_id`, `uuid`, typed UUID/int values).

   No values. HTML documents get a shape of the form skeleton and repeated-item counts.
2. **Identifier flow tokens.** For identifier-like values in responses, URLs, request parameters and visible link targets, store `HMAC(run_key, value)` truncated to 64 bits. `run_key` is random per run and never written to disk. Matching tokens across evidence yields `produces`/`consumes` and `same_as` claims *within* a run. Tokens cannot be reversed or compared across runs.
3. **Canary inputs.** When a form field accepts free text, the engine submits a value it generated itself: a unique, non-sensitive token. It then records where that token's HMAC reappears: other views, responses, other roles. This is Black Widow's black-box inter-state dependency tracking (related work §2.4) in a value-free form. It also gives the cross-view and round-trip oracles something to look for when the application renders IDs only as text. Canaries are only submitted in fields whose submission the safety gate already permits.
4. **WebSocket message classes.** For same-origin WebSocket connections (not captured today), record per action window:
   - the connection URL pattern;
   - frame counts per direction;
   - for JSON frames, the key-path skeleton;
   - a **discriminator token** per frame: `HMAC(run_key, value)` of top-level string fields whose values are short, non-identifier constants repeated across frames (for example a `type` field).

   Frames with the same skeleton and discriminator form one *message class*. Sent message classes count as operations; received ones count as effects.
5. **Client-state changes.** Changed `localStorage`/`sessionStorage` *key names* (key names are already read today, as session markers), URL fragment changes, and title changes.
6. **Visual region digest.** For `<canvas>` elements, `<svg>` elements and elements with no accessible DOM content, a perceptual hash of the element's screenshot before and after an action. This is the only effect evidence for pure canvas operations. It is coarse by design: it records *that* the region changed, never what it shows.

### 4.3 What "verified" means (the oracle ladder)

`VERIFIED` requires an oracle stronger than "the same page shape came back". Admissible oracles, in increasing strength:

| Oracle | Applies to | Example |
|---|---|---|
| **Differential input** | read/query capabilities | Paired search (existing): two contrast inputs give consistently different result sets |
| **Cross-view consistency** | create/update | After `create Canvas`, a new instance token appears in the list view and opens on its own route |
| **Round-trip** | create/update/read | The value set in an update form is shown (by hash) on the detail view after reload in a fresh context |
| **Inverse operation** | add/remove pairs | `add to cart` then `remove from cart` returns the cart shape to its prior state |
| **Operation conformance** | any | The replay issues the same operation structures and the response shape matches |
| **Adapter ground truth** | authorized environments only | Adapter reports a DB row-count delta for the entity's table (§6.4) |

UI outcome signals (`role=alert`, `.success`) count as **observation evidence only**. They are not an oracle.

## 5. Identity resolution and update semantics

### 5.1 Event-sourced updates

```
Evidence log (append-only) ──► Incremental resolvers ──► ACG materialized view ──► Planner queries
      ▲                              │  (affordance, template, view abstraction,
      │                              │   entity, operation, capability, condition)
      └──── Experiments ◄────────────┘
```

Each resolver is a pure function `(view, new_evidence) → [claim deltas]`. Deltas never delete evidence. A split or merge is a new claim plus a re-materialization of the affected nodes, so the model is fully reproducible from the log and a resolver version. This replaces the current post-hoc `_finalize` grouping.

### 5.2 Entity identity

An `EntityInstance` exists when an identifier is observed from at least one of these sources, in decreasing strength:
1. a response identifier key path whose token later appears in a URL or request (ID flow);
2. a URL path or query value at an identifier position of a template (generalizes `INSTANCE_TOKEN` to query parameters and slugs: a segment position whose value varies across sibling links under the same template);
3. a visible key field (a heading or title bound to a detail template), as a *weak* identity.

Rules:
- **Same instance** requires matching tokens from a strong source (1 or 2), or a weak match corroborated by a strong one.
- **Template sharing never implies instance sameness.** Two canvases with the same layout stay distinct.
- **A view that displays instance X never restores a request for instance Y.** Planner restoration uses instance-keyed return paths (generalizing `f6744ba`).
- **Contradiction rule:** if two instances with a `same_as` claim later show different strong tokens in the same role and environment state, the claim is `REFUTED`. The instances are split and the downstream claims witnessed only through the merged node revert to `OBSERVED`.

### 5.3 Capability identity and interface equivalence

A capability is identified by its **behavior signature**, built only from observable quantities:

```python
class OperationKey(BaseModel):          # one per request or message the action caused
    channel: Literal["http", "websocket_send"]
    method: str | None                  # http only
    route_pattern: str                  # path with identifier positions abstracted
    parameter_names: tuple[str, ...]    # query + body names (existing request_structure_key)
    body_encoding: str | None
    dispatch: tuple[tuple[str, str], ...] = ()  # (parameter, HMAC(value)) for dispatch parameters, see below
    message_class: str | None = None    # websocket: skeleton digest + discriminator token
    response_shape: str | None = None   # key-path skeleton digest (§4.2)

class EffectAtom(BaseModel):            # observable, never interpreted
    kind: Literal[
        "navigated",                    # target = template id
        "instance_appeared",            # new identifier token of entity type E observed (target = E)
        "instance_disappeared",         # token previously listed in a collection view is absent
        "instance_fields_changed",      # same token, displayed field digest at key path K changed
        "collection_size_changed",      # bucketed cardinality of a repeated-item region changed
        "collection_membership_changed",# same size bucket, different member tokens
        "component_state_changed",      # region opened/closed/switched (target = region family)
        "client_state_changed",         # storage key names / URL fragment / title changed
        "visual_region_changed",        # canvas/svg digest changed (target = region family)
        "message_received",             # websocket message class received (target = class)
        "none_observed",
    ]
    target: str
    reproduced: bool = False

BehaviorSignature = tuple[str,                      # role
                          frozenset[OperationKey],
                          frozenset[EffectAtom],
                          str | None]               # entry template family, only when no operation
```

Identity rules:
- **Same signature on reproduced evidence ⇒ same capability.** Two bindings with the same signature are `equivalent_interface`. Example: whiteboard dashboard "+ Create canvas" and an empty-state create button both produce `{POST /api/canvases [name] json}` and `{instance_appeared(E1)}`.
- **Different operation keys, dispatch values, message classes or effect atoms ⇒ different capabilities**, even when the affordances look identical. A same-label "Submit" whose handler was revised (Crawl Maze) becomes two capabilities. The context predicate that separates them is learned (§2.2), so no special `behavior_revision` key is needed.
- **Dispatch parameters.** Many applications route by a parameter *value*: PrestaShop's `controller=`, ThinkPHP-style `s=/module/action` (SiyuCMS is a likely case; this is expected and unverified), a GraphQL `operationName`. Today's request-structure key drops query values, so every such request collapses into one operation. A parameter is treated as a dispatch parameter when all of these hold:
  - its values are short, non-identifier tokens;
  - the value is constant for a given affordance;
  - different affordances send different values;
  - it was not filled by the engine.

  Its value then enters the key as an HMAC token.
- **Capabilities with no operation** (client-side filtering, a panel toggle, a canvas tool) have signatures made of effect atoms only. They also carry the entry template family, so "toggle panel A" and "toggle panel B" stay distinct through their region targets.
- **Distinctness is limited by observability.** Two functions with identical observable signatures are one capability in the model, by construction. This is a stated limit (§5.7), not a bug to hide.

### 5.4 Functional areas

Areas are communities in a graph over capabilities, weighted by:
- shared entity types (strong);
- shared templates (medium);
- `enables` edges (medium);
- shared route prefix (weak; this is the only signal today's `area_key` uses).

A deterministic label-propagation pass with a fixed seed is sufficient. Areas are a *planning* abstraction: they decide where budget goes and never merge evidence.

### 5.5 Conditions and dependencies

Preconditions are inferred from three patterns:
1. **Availability contrast:** an affordance is present in views satisfying predicate p and absent otherwise (Daikon-style likely invariants over view facts).
2. **Role contrast:** a capability is available to role A but not role B.
3. **Failure contrast:** an experiment for capability C failed with a validation outcome or a 4xx until capability D had executed.

Postconditions are effect claims. `enables(D, C)` is derived when D `establishes` a condition C `requires`. Dependencies stay `HYPOTHESIZED` until an experiment shows C failing without D and succeeding with it (§[EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) §5.3).

### 5.6 Semantic grounding: observed behavior vs meaning

Every capability has three separate layers. Only the first defines identity, and only the first two may be used by the planner.

| Layer | Content | Source | Used for identity | Used by planner | Scored by evaluation |
|---|---|---|---|---|---|
| **1. Behavior signature** | Operation keys and effect atoms (§5.3) | Evidence only | yes | yes | yes (M1a) |
| **2. Behavioral class** | One of a closed set of classes, each produced by a grounding rule over layer 1 | Rule table below; never text | no | yes | yes (M1b) |
| **3. Display labels** | Affordance accessible names, headings, route segments, JSON collection key names | Verbatim strings with evidence ids | no | **no** | no |

**Grounding rules.** A class is asserted only when every listed piece of evidence is present at the listed status. Otherwise the capability has **no class** and is reported as an *unidentified operation*, with its signature.

| Behavioral class | Required evidence | Minimum status |
|---|---|---|
| `navigation(T)` | effect `navigated(T)`; no write-capable operation; no instance or collection effect | REPRODUCED |
| `instance_creation(E)` | `instance_appeared(E)`, and the new token then resolves: its detail template opens, or it joins a collection view of E (cross-view) | VERIFIED (cross-view) |
| `instance_removal(E)` | `instance_disappeared(E)` from a collection where it was listed, and its detail view no longer resolves | VERIFIED; requires L3+ isolation |
| `instance_modification(E.K)` | `instance_fields_changed(E, K)`, round-trip: the change survives a fresh-context reload | VERIFIED (round-trip) |
| `collection_query(E, field)` | differential input on one field gives consistently different `collection_membership_changed` (generalized paired search) | VERIFIED (differential) |
| `instance_view(E)` | navigated to a template that displays exactly one instance token of E, and the token matches the entry affordance's target | REPRODUCED |
| `client_view_change(region)` | only `component_state_changed` / `client_state_changed`; no operation | REPRODUCED |
| `server_job_submission` | write-capable operation followed by ≥ 1 `message_received` class that does not occur without the action (contrast) | REPRODUCED |

The class vocabulary is closed and small on purpose. There is no `share`, `publish`, `checkout`, `approve` or `add to cart` class. Those are business meanings, and nothing observable separates "publish" from "approve" when both change one status field. Such capabilities are reported as `instance_modification(E.K)` with their display labels attached.

**Entity type names** are layer-3 labels too. Each entity type is identified by its identifier source (§5.2) and response shape, and stored as `E1`, `E2`, …. Its candidate names, such as the route segment `canvas` or the JSON key `canvases`, are kept verbatim with provenance, never translated or normalized. When there is no candidate, it remains `E1`.

**When a capability must stay an unidentified operation:**
- no rule has fired at its minimum status;
- its effects are only `visual_region_changed` or `none_observed`;
- its operations are blocked (risk gate) and it was never executed;
- or the rule's evidence is contradicted (a refuted cross-view check reverts `instance_creation` to unidentified).

Reports and Graph A must show unidentified operations as such: signature, display labels and the reason no class was assigned. They are never hidden or given a guessed name.

**Examples:**
- *SiyuCMS.* The search box is grounded as `collection_query(E_article, field_q)` by the paired-search contrast already observed in `siyucms_search_integrated_v2`. Its label "搜索" is only a display label. A "删除" button in admin, blocked at L0 by its confirm dialog, stays an **unidentified operation** with `blocked_reason=destructive_possible` and display label "删除". The engine never asserts "delete"; it may assert `instance_removal` only after an L3 experiment shows the instance disappear.
- *ComfyUI (expected behavior, not yet observed).* Queueing a workflow (`POST /prompt`, then WebSocket progress messages) can be grounded as `server_job_submission`. Adding a node by dragging on the canvas yields only `visual_region_changed` and probably `client_state_changed`, so it is an unidentified operation. The engine cannot tell "add node" from "move node" unless their signatures differ.
- *Whiteboard.* "+ Create canvas" becomes `instance_creation(E1)` only after the cross-view check (new token in the dashboard list, and its `/canvas/{uuid}` opens). Before that it is `cap_… [instance_appeared(E1) via POST /api/canvases]`, unclassified.

### 5.7 Limits of behavioral inference without a model

What this design can establish from browser-level evidence alone:
- *that* an affordance causes particular requests, messages and observable effects;
- *which* entity instances are created, removed or changed, when they are observable through identifiers;
- *which* affordances are equivalent or different, *when* their signatures differ;
- *which* capabilities depend on others, through availability, role and failure contrasts.

What it cannot establish:
- **Purpose and business meaning.** "Publish" vs "approve" vs "archive", when each just changes one field.
- **Effects outside the observing role's view.** Emails, other users' views, admin logs, background jobs that never report back. These are `none_observed` unless an adapter reports them.
- **Delayed effects** that appear after the attribution window.
- **The internal structure of pure canvas operations.** These are visual digests only, unless a framework-generic, read-only provider exposes counts (for example nodes and links). Such a provider must pass the admissibility rule in [GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §1.2.
- **Distinctions between functions with identical observable signatures.** For example, two settings saved through the same endpoint with the same parameter names and no dispatch value. They remain one capability with several bindings.
- **Meaningful names.** Only verbatim display labels are available.

These limits are why the evaluation separates operation discovery (M1a) from behavioral identification (M1b), and why it never scores display labels as semantic correctness.

## 6. Stateful exploration: isolation and reset architecture

The current policy refuses every workflow with an observed write. That is safe and necessary today, but it makes *every* stateful capability (create, update, checkout, queue a workflow) untestable. The aim is containment, not permission. The architecture adds an **isolation boundary**, provided by the environment adapter. The engine may only issue a write-capable experiment when the adapter attests that the boundary exists and has been independently checked.

### 6.1 Isolation levels

| Level | Mechanism | Guarantees | Cost (estimates, unmeasured; to be measured in migration Phase 5) | Suits |
|---|---|---|---|---|
| L0 | None (current production default) | none; write-capable actions follow the first-observation rule in §6.2 | 0 | unknown or third-party targets |
| L1 | Fresh browser context | client state only (cookies, storage) | ~0 | read-only capabilities (current replay) |
| L2 | Per-run disposable application instance (container stack + fresh DB) | writes confined to one run; no per-experiment reset | 1–4 min per stack (whiteboard ≈ seconds; ComfyUI image build 4 min once) | exploration of writes, once each |
| L3 | Per-experiment DB snapshot restore (Postgres `CREATE DATABASE … TEMPLATE`, MySQL dump/restore, SQLite file copy, ZFS/btrfs or Docker volume snapshot) | identical starting data per experiment | ~0.1–5 s per restore depending on DB size | replay verification of writes |
| L4 | Full-stack snapshot (DB + filesystem + app process: container checkpoint/CRIU, VM snapshot) | includes caches, files, queues, in-memory state | seconds to tens of seconds | ComfyUI (output files, queue), apps with background workers |
| L5 | Transaction-scoped rollback (test-mode DB with rollback per request/session) | strongest isolation, lowest cost | requires app cooperation | only apps that ship a test mode |

Rules:
- **L3–L5 need an independently verified starting state** (§6.3).
- **The engine never assumes a level.** It reads it from the adapter's capability declaration.
- **HTTP methods alone never establish read-only status.** An experiment's risk class comes from effect evidence plus the adapter level, not from the method (§6.2).

### 6.2 Effect-risk classification

```python
class EffectRisk(StrEnum):
    NONE_OBSERVED = "none_observed"         # only GET/HEAD, no state predicate changed, no ID flow out
    CLIENT_ONLY = "client_only"             # storage/cookie/URL changes only
    SERVER_WRITE_POSSIBLE = "server_write_possible"   # non-GET, WebSocket send, or GET with state change
    SERVER_WRITE_CONFIRMED = "server_write_confirmed" # cross-view/round-trip oracle or adapter diff shows it
    DESTRUCTIVE_POSSIBLE = "destructive_possible"     # deletes/invalidates an entity, or lexical/ARIA/icon danger cue
    EXTERNAL_EFFECT = "external_effect"     # email, payment, outbound webhook signs (adapter-declared or observed)
```

`may_execute(capability_experiment, adapter)` is a total function:

| Risk ↓ / Isolation → | L0 | L1 | L2 | L3–L5 |
|---|---|---|---|---|
| none_observed | yes | yes | yes | yes |
| client_only | yes | yes | yes | yes |
| server_write_possible | first observation only, if the operator allowed exploratory writes; never replayed | same as L0 | explore; replay only on a fresh stack | explore and replay from a verified snapshot |
| server_write_confirmed | no repeat | no repeat | explore once per stack | replay from a verified snapshot |
| destructive_possible | no | no | adapter policy must allow | adapter policy must allow; snapshot required |
| external_effect | no | no | no, unless the adapter stubs the sink | no, unless the adapter stubs the sink |

Notes on the table:
- **First observations are still exploratory.** The first observation of an unknown action is always somewhat risky, because its effect is not known in advance. `f6744ba`'s guard limits the damage: defer untested non-search forms, never repeat a known write, refuse it as a restoration prerequisite. That guard stays the L0–L1 default.
- **The existing `DANGEROUS_ACTION` filter stays.** It becomes one input to `DESTRUCTIVE_POSSIBLE`, joined by ARIA, icon and confirm-dialog cues.

### 6.3 Independently verified starting states

A snapshot is usable for verification only when:
1. the adapter restores it;
2. the adapter's *independent* probe confirms its fingerprint (for example per-table row counts and a schema digest, read with adapter credentials Agent 1 never sees);
3. the engine's own read-only probe, a fixed set of `REPRODUCED` read-only capabilities, reproduces their recorded observations.

If either check fails, the experiment is `BLOCKED(reason="unverified_start_state")`. This separates "the operator reset something" from "this experiment began in a known state". The `f6744ba` report explicitly refused to conflate the two.

### 6.4 Adapter ground-truth effects

Where the operator authorizes it, the adapter may report an **effect digest** after an experiment: per-table row deltas and changed-column *names*, with no values. This gives the evaluation (not the planner) an independent oracle to score effect-classification precision and recall (§[GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §3).

Whether the planner may *consume* it is a per-environment switch, `adapter_effects_visible_to_engine`. It defaults to false for held-out evaluation, so the engine cannot become dependent on privileged signals.

### 6.5 What could go wrong

- **Snapshots miss state outside the DB.** Examples are file uploads, caches, search indexes and queued jobs (ComfyUI). Mitigation: L4 for such environments, plus a drift probe (§6.3 step 3) before each experiment.
- **Time-dependent or randomized state** (tokens, timestamps). Mitigation: oracles compare shapes and ID-flow structure, not values.
- **Background workers mutate state between restore and experiment.** Mitigation: the adapter quiesces them, or the experiment is marked `environment_nondeterministic` after a reproducibility check fails twice.
- **Cost.** Per-experiment restore could dominate. The planner budgets restores as actions with measured cost (§[EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) §6).

## 7. Worked examples

The examples combine Agent 1's actual observations (marked **observed**) with public architecture knowledge about each application (marked **expected**), which the engine would have to discover itself. Expected entries are illustrations of the model, not ground truth.

Names such as `create Canvas` or `Product` are **display labels used for readability**. Under §5.6 the stored capability is its behavior signature plus, at most, a grounded behavioral class, and entity types are stored as `E1`, `E2`, ….

### 7.1 Whiteboard (React 19 SPA + FastAPI)

- **EntityType `Canvas`**:
  - identity from `POST /api/canvases` response `id` (expected) whose HMAC token reappears in `/canvas/{uuid}` (observed route shape);
  - two seeded instances and one created instance (observed in `f6744ba` runs).
- **Capabilities:**
  - `create Canvas`: realized_by `POST /api/canvases` (observed). Requires `role ⊇ authenticated`. Effect atom `instance_appeared(E1)`, with risk `SERVER_WRITE_POSSIBLE`. It stays unclassified until a cross-view oracle shows the new token in the dashboard list; then it is grounded as `instance_creation(E1)` and its risk becomes `SERVER_WRITE_CONFIRMED`.
  - `open Canvas`: grounded as `instance_view(E1)`. Entry points are the dashboard card button (observed as buttons, not links) and the direct URL.
  - `draw shape`: a canvas gesture. Effect on ComponentState and a likely WebSocket/REST write (expected). Today it is `BLOCKED(reason="unsupported_interaction:canvas_gesture")`, which is explicit missing coverage rather than silence.
- **Interface equivalence:** dashboard "+ Create canvas" and any empty-state create button bind to the same capability.
- **Distinctness:** the 5-canvas merge becomes 5 `EntityInstance` nodes sharing one `PageTemplate`. Return paths are instance-keyed.
- **Old vs new:** the whiteboard's 13 → 43 transitions become ≈ 6–10 capabilities with explicit verification states instead of 36 untested transitions.

### 7.2 PrestaShop (e-commerce, PHP)

- **EntityTypes (expected):** `Product` (`id_product` query or `/{id}-{slug}.html`; needs the query/slug identity in §5.2), `Category`, `Cart`, `Customer`, `Order`.
- **Capabilities:**
  - `list Product by Category`;
  - `view Product`;
  - `search Product` (GET search, verifiable by the differential oracle);
  - `add Product to Cart`: write. Requires `exists(Product)`. Establishes `cart.count ≥ 1`;
  - `checkout`: requires `cart.count ≥ 1` and a customer or guest condition. Has `EXTERNAL_EFFECT` potential (order email). BLOCKED without an adapter mail sink.
- **Dependency chain:** `view Product` → `add to Cart` → `checkout`. This is exactly what a frontier over control shapes cannot express.
- **Observed blocker:** 50/64 controls were cross-origin (internal host). Adapter `origin_aliases` fixes this; it is not an engine change.

### 7.3 ComfyUI (node-based visual editor)

- **EntityTypes (expected):** `Workflow` (client-side graph, persisted via API/user data), `Node` (types from `GET /object_info`), `Link`, `QueueItem`/`PromptJob` (`POST /prompt`, `/queue`, `/history`), `OutputImage`.
- **Capabilities:**
  - `add Node`, `connect Node ports` (expected; observable only as `visual_region_changed` plus `client_state_changed` → unidentified operations unless a read-only count provider is admitted);
  - `queue Workflow` (`POST /prompt` then WebSocket progress messages; `SERVER_WRITE_POSSIBLE`; expensive compute, so adapter-declared cost; groundable as `server_job_submission`);
  - `view History`;
  - `load/save Workflow`.
- **The ComponentState and ViewState split is essential.** One route, many canvas states. The observed failure (6 groups for one route because of transient content) disappears when content leaves `α` and readiness gates observation.
- **The node-type catalogue (`/object_info`) is evidence of a list, not of capabilities.** It is recorded as an operation with a large response shape. It does **not** create hypothesized "add node of type T" capabilities: that would be inventing semantics (§5.6). Node-related capabilities exist in the model only once an executed affordance (search dialog, context menu, drag) shows a signature. Even then, without a framework-generic count provider, they remain unidentified operations with `visual_region_changed` effects. The planner samples a few node-type entries from the dialog rather than enumerating hundreds (§[EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) §4.2).

### 7.4 SiyuCMS (CMS, Chinese UI)

- **EntityTypes (expected):** `Article` (often slug or numeric id), `Category`, `Tag`; admin: `User`, `Setting`, `Media`.
- **Capabilities:**
  - `search Article by keyword`: **observed and VERIFIED** by the paired-search oracle in `siyucms_search_integrated_v2` (1 verified functional workflow);
  - `list Article by Category`, `view Article`;
  - admin `create/update Article` (role `admin`; not yet mapped).
- **Language independence:** behavioral classes come from effects (§5.6). A `删除` (delete) button is classified `DESTRUCTIVE_POSSIBLE` by its confirm dialog and observed request/effect, not by an English regex. Before any execution, it is held back by ARIA, icon or dialog cues plus an adapter-supplied lexicon (a multilingual danger lexicon is an adapter asset).

### 7.5 Crawl Maze (dynamic benchmark with hidden interactions)

- **Few entities.** Capabilities are mostly `navigation(T)` or unidentified operations (requests with no further observable effect), triggered by hidden interactions (listener-attached elements, handler revisions, delayed content).
- **The ACG degenerates gracefully** to `EntryPoint`, `Affordance`, `Operation` and `Transition`. The "Submit" handler-revision case is two bindings of one affordance to two capabilities, distinguished by a learned `behavior_revision` predicate (§5.3).
- **Score mapping.** The marker score maps to `Operation` recall. This is why Crawl Maze is one environment among several and not the objective (§[GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §5).

## 8. Why it should work, what could go wrong, how to validate

| Proposal | Why it should work | Risk | Validation |
|---|---|---|---|
| Layered nodes (template / view / component / entity / capability) | Removes the single-hash conflation; each failure in audit §2.2 maps to a mixed layer | More resolvers mean more places for bugs; materialization cost | Fixture checks: 5 canvases → 5 instances, 1 template; ComfyUI-like transient lab → 1 view state |
| Evidence-driven abstraction refinement | APE showed refined dynamic abstraction beats fixed abstraction in Android GUI testing (related work §2.3) | Over-refinement explodes states | Count views per template; regression on Crawl Maze state count; cap predicates per template |
| ID-flow tokens (HMAC) | Producer–consumer inference is the core of RESTler/Morest dependency inference; the HMAC keeps it value-free | IDs not exposed in responses (server-rendered HTML) | Fixture with HTML-only IDs; measure entity recall with and without response shapes |
| Capability identity from operations + effects | Labels are language- and app-specific; operation/effect structure is not | Client-only capabilities have no operations; effect inference may be noisy; identical signatures cannot be separated | Offline tests T1 (signature partition) and T3 (text invariance) in [GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §4.1 |
| Oracle ladder | Separates reproducibility from function; the paired search already demonstrates it | Some capabilities admit no cheap oracle (they stay `REPRODUCED`) | Report status distribution; adapter ground-truth precision of `VERIFIED` |
| Isolation levels and attested snapshots | Turns "never test writes" into "test writes where containment is proven" | Partial snapshots; nondeterminism | Stateful lab with SQLite snapshot: verify create/update with DB-diff ground truth; then whiteboard Postgres template DB |

## 9. Backward compatibility

Graph A remains an export:
- `states` ← `ViewState` (plus raw `Observation` ids);
- `page_templates`, `record_instances` ← `PageTemplate`, `EntityInstance`;
- `features` ← `(Capability, Binding)`;
- `functional_workflows` ← witnessing transition paths;
- `replay_evidence` ← `Experiment` records.

The existing connection-evidence audit runs unchanged against the projection, and existing scorers keep working during migration (§[ARCHITECTURAL_MIGRATION_PLAN.md](ARCHITECTURAL_MIGRATION_PLAN.md)).
