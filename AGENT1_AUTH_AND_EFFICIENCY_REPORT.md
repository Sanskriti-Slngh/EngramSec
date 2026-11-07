# Agent 1 — Authenticated Functional Coverage & Exploration Efficiency

Written for: the EngramSec research owner and anyone continuing Agent 1, read alongside the code on
branch `agent1-browser-mapper-20261028` (this milestone continues after `f150b0c`).

Agent 1 is a **functionality mapper**, not a vulnerability detector. Everything below optimizes for
independently observable, executed, and reproducible application functionality — never
vulnerability-location overlap or raw URL counts.

This milestone asked two questions: how much does authenticated exploration widen what Agent 1 can map,
and is redundant resource exploration blocking further discovery? The work is in five phases: an audit of
the existing authentication implementation, a matched three-role experiment on a fixture with genuine
authorization enforcement, a diagnosis of ComfyUI's HTTP-budget exhaustion from frozen traces, one
general efficiency improvement justified by that diagnosis, and this write-up.

All runs are loopback-only, in a git-ignored experiments tree; no production default was changed, and the
one new behavior (static-asset dedup) is opt-in and off by default. No WebExploitBench vulnerability
metadata was read for optimization, no exploits were run, and no credentials or session tokens appear in
Graph A, the ACG, logs, this report, or any commit.

---

## 1. Phase 1 — audit of the existing authentication implementation (`f150b0c`)

**How authentication appears today.** A session is provisioned **outside** the agent
(`evaluation/auth_provision.py`): the harness logs in with its own browser and hands the agent only a
Playwright storage-state file via `RunConfig.storage_state_path`. Every exploration, restoration and
replay context is created from that same file
([explorer.py:724](agent1/explorer.py#L724)), so the authenticated session is used uniformly and is
never re-created by the agent. The login is recorded for Graph A as a prerequisite descriptor
(`auth_prerequisite.json`): method, login route, field **names**, role, and an opaque `account_ref`
(a SHA-256 prefix) — no secret values. Session identity inside Graph A is the observation's
`session_markers`, which record cookie **names** and storage **key names** only, never their values.

**Verified properties.**
- *Session survives navigation, restoration and replay.* Every `BrowserSession` is built from the same
  `config` ([explorer.py:1824](agent1/explorer.py#L1824)); `reset_context()` re-enters from the same
  `storage_state_path` ([explorer.py:843](agent1/explorer.py#L843)); replay builds its session the same
  way. The restoration contract and the strict restore both refuse to act when `session_markers` change
  ([restoration.py:242](agent1/restoration.py#L242); strict guards at
  [explorer.py:2514](agent1/explorer.py#L2514)/`2908`/`2934`), so an expired or downgraded session cannot
  cause a pending action to fire in the wrong session. This is already covered by
  `test_two_sessions_with_identical_visible_pages_are_refused`.
- *No secret leakage.* The provisioned secrets live only under git-ignored `agent1/.auth/` (chmod 600).
  The public auth record and `session_markers` carry names, not values. Inspection of the existing
  White-Jotter authenticated run confirmed cookie **names** (`JSESSIONID`, `rememberMe`) and a localStorage
  **key name** (`username`) — no values — in Graph A.

**One concrete defect found (and fixed).** The role was **not** carried into the run. An authenticated
run inherited `context_label="anonymous"`, so its `session_context` in Graph A — and the `role` field of
the ACG's `SessionRef` ([live/grounded.py:56](agent1/live/grounded.py#L56)) — read literally
`"anonymous"`, identical to the anonymous control. The true role (`registered_user`) was computed in
provisioning and written to the sidecar, but never propagated to the run config. `session_context` and
the ACG `role` are part of action/template/hierarchical identity
([action_behavior.py:30](agent1/action_behavior.py#L30)), so this matters most for the three-role
experiment: a regular user and an administrator on the same app **share the same cookie name** (one
session id), so `session_markers` alone cannot separate them — only the role label can. Left unfixed,
user and admin capabilities would be indistinguishable by session identity and could merge if combined.

The fix propagates the provisioned role into `context_label` in both harnesses
(`evaluation/recovery_transfer.py`, the new `evaluation/role_experiment.py`). It is evaluation wiring
only; no agent default changed. New regression tests assert role separation and credential hygiene
(`tests/test_auth_session_representation.py`): the same route+control under `registered_user` vs `admin`
produces different action identities even when cookie names are identical, and the public auth record
contains the field name `password` but never a username value or token.

**Missing coverage identified and added.** Before this milestone there were no tests for role
representation or credential hygiene. Added: `tests/test_auth_session_representation.py` (role
separation, no-secret hygiene, opaque stable `account_ref`) and `tests/test_role_lab.py` (the fixture's
server-side authorization is genuine, not cosmetic).

---

## 2. Phase 2 — matched three-role exploration experiment

**Why a dedicated fixture.** White-Jotter supplies an ordinary user by self-registration, but no
administrator credentials are available, and the milestone forbids guessing or privilege escalation. So
the three-role comparison runs on a new development fixture, `development_apps/role_lab.py`, with **real**
server-side authorization: anonymous sees only the public catalog; a logged-in user reaches
`/dashboard`, `/orders`, `/order/new`, `/profile`; an administrator additionally reaches `/admin`,
`/admin/users`, `/admin/settings`, `/admin/user/<id>/delete`. Non-admins are refused `/admin*` with 403
and anonymous requests to user pages are redirected to `/login` — enforced from the session cookie, never
from anything the client asserts. The fixture ships ground-truth annotations (`CAPABILITIES`,
`role_inventory`) and a server-side executed-function ledger (`STATE.functions`), so recall and precision
are measured, not invented.

**Design.** Three arms — anonymous, authenticated user, authenticated admin — identical in start URL,
exploration policy, and browser-action / wall-clock / HTTP budgets; the authenticated session is the only
variable. Each arm runs in its own child process (fixture state is created from code per process, so a
fresh interpreter is the reset). Seeded account passwords are random per process and reach provisioning
only through the environment; the agent receives only the storage-state file and the role label. Three
trials per arm after a smoke test froze the protocol.

Results were identical across all three trials of every arm (deterministic fixture); the table shows
that common value.

| metric | anonymous | user | admin |
|---|---|---|---|
| `session_context` in Graph A | `anonymous` | `registered_user` | `admin` |
| ACG `SessionRef.role` | `anonymous` | `registered_user+rolelab_session` | `admin+rolelab_session` |
| functional areas reached | 5 | 8 | 8 |
| capabilities **executed** (server ledger) | 3 | 6 | 8 |
| executed recall vs role inventory | 3/3 = 1.00 | 6/8 = 0.75 | 8/12 = 0.67 |
| capabilities replay-reproduced | 6 | 9 | 11 |
| login prerequisite recorded | n/a | yes (`operator_credentials`) | yes (`operator_credentials`) |
| executed **above** role (must be 0) | 0 | 0 | 0 |
| server-side out-of-role refusals | 30 | 12 | 0 |
| write capabilities discovered-but-deferred | 0 | 2 | 3 |
| write capabilities safety-blocked | 0 | 0 | 1 (`.../delete`) |
| termination | reserve boundary | reserve boundary | reserve boundary |
| actions / executed capability | 62.7 | 32.7 | 25.2 |

**What authentication unlocks (executed functionality).** Executed capability grows monotonically with
privilege: anonymous executes 3 (browse catalog, view item, search); the user adds three authenticated
GET capabilities (`dashboard_view`, `orders_view`, `profile_view`); the admin adds two more
(`admin_panel_view`, `admin_users_view`). The same shows in functional areas: anonymous touches `/admin`
and `/login` but is refused/redirected there (they appear as areas, not as executed capability), whereas
the user and admin arms genuinely resolve `/dashboard`, `/orders`, `/order`, `/profile`, and the admin arm
additionally resolves `/admin*`. So authentication is what converts a touched-but-refused area into
executed functionality.

**Role representation and no cross-role access.** With the Phase 1 fix, every arm's `session_context`
equals its role and the ACG role matches (previously all three would have read `anonymous`). No arm ever
executed a capability above its role (`executed_above_role = 0` in all nine runs), and the fixture's
server-side ledger confirms it: anonymous was refused 30 out-of-role attempts, the user 12 (every
`/admin*` try returned 403), and the admin 0 (allowed everywhere it reached). Enforcement is genuine, and
Agent 1 respects it — it attempts out-of-role links (correct: it cannot know the boundary a priori) but
the server refuses them and nothing out-of-role is ever executed.

**The three-way distinction (undiscovered / discovered-but-not-executed / executed).** The milestone asks
to keep these apart, and the run does. Executed GET capabilities are in the server ledger. The write
capabilities are **discovered but not executed**: `order_create` and `profile_update` (both roles),
`admin_settings_update` (admin) appear as *safe* form-submit controls in Graph A but are left queued; the
admin's `/admin/user/<id>/delete` is **discovered and safety-blocked** (`dangerous_label_or_target`, so it
is never submitted even in disposable mode). Nothing in any role's inventory was *undiscovered*. This is
why executed recall is below 1.0 for user and admin: the gap is exactly the deferred and blocked writes,
not missed discovery — see Q4 for why they stay deferred.

---

## 3. Phase 3 — why ComfyUI exhausts its HTTP budget (frozen traces only)

Measured from the existing frozen ComfyUI runs with `evaluation/comfyui_request_breakdown.py` — no reruns,
no vulnerability metadata.

| trace | actions | observed HTTP (cap) | unique paths | repeat ratio | static share | wasted refetches |
|---|---|---|---|---|---|---|
| frozen, 600 s | 29 | 2,059 (2,000) | 532 | 3.9× | 93% | 1,408 (68% of all) |
| generous budget | 217 | 18,768 (20,000) | 533 | 35.1× | 93% | 16,887 (90% of all) |

**The requests are overwhelmingly repeated static assets.** In the generous-budget run, 16,788 of 18,696
stored browser requests are `script`, 93% are static assets, and only 533 distinct paths were fetched
18,696 times — a 35× average refetch. The top repeats are the SPA's own module/style bundle
(`/materialdesignicons.min.css`, `/assets/vendor-*.css`, each once per navigation) and polling XHRs.

**The producing component is normal page-loading and replay, not the spider.** Budget by source:
`browser` 12,515, `browser_verification` (replay) 6,000, `passive_document` 1,363, `resource_spider` only
97. So the storm is Chromium loading each page's module graph, re-charged on every navigation and every
replay, **not** the typed resource spider.

**Mechanism (general, not ComfyUI-specific).** The scope router fetches every request itself
(`route.fetch`), which defeats Chromium's HTTP cache, and restored pages start from a cold context — so a
module-heavy SPA re-downloads its entire bundle on each navigation. All of it is charged against the one
shared HTTP budget, which is consumed by redundant refetches long before functional exploration finishes.
The stop is a real budget cap, but it is reached through redundant refetching (an efficiency problem),
not through genuinely diverse content. The earliest causal bottleneck is therefore refetch of identical
static assets, not depth, not the frontier model, not the spider.

**Reproduced on a synthetic fixture.** `development_apps/asset_storm_lab.py` is a generic module-heavy
SPA (44 script modules + 8 stylesheets linked by every page, a few genuine functional controls). It
reproduces the pattern without any ComfyUI-specific path or rule — see Phase 4 for the numbers.

---

## 4. Phase 4 — one general improvement: static-asset dedup

The evidence points at exactly one problem: identical static assets are refetched and re-charged on every
navigation and replay. The single focused improvement is a **per-run response cache for static-asset GETs**
in the route interceptor (`agent1.bounded_http.ResourceCache`, wired at
[explorer.py:736](agent1/explorer.py#L736)): a repeated GET of a `script`/`stylesheet`/`font`/`image` URL
is served from memory, is **not** refetched, and is **not** charged to the HTTP budget. It never caches
documents or XHR/fetch, never caches non-200 or `no-store`/`private` responses, and is bounded by entry
count and bytes. It is opt-in (`RunConfig.resource_cache`, default off) and compared against a matched
baseline, per the milestone's rule about production defaults.

Matched baseline (off) vs treatment (on) on `asset_storm_lab`, HTTP budget 1,500 so the storm is binding:

Results were identical across all three trials of each arm.

| metric | baseline (cache off) | treatment (cache on) |
|---|---|---|
| HTTP budget **used** (cap 1,500) | 1,500 — **exhausted** | 294 (80% headroom) |
| static-asset requests served from cache | 0 | 9,360 (5.3 MB) |
| server-side asset refetch waste | 1,412 | 52 (−96%) |
| functional capabilities executed | 9/9 | 9/9 |
| workflows replay-validated | **0** | **10** |
| browser actions (depth) | 31 | 200 |
| wall seconds | 16 | 96 |
| scope enforcement / write policy | unchanged | unchanged |

The gain is **not** "fewer requests." Recall of the small fixture's nine functional capabilities
saturates in both arms, so the honest headline is **reproduction**: the baseline exhausts its HTTP budget
during discovery and validates **zero** workflows by replay, while the treatment frees the budget and
independently replay-validates the full set — and explores substantially deeper (more browser actions)
within the same wall-clock and budget. Scope enforcement and the write policy are unchanged.

---

## 5. Phase 5 — conclusions

1. **How much functionality becomes discoverable after authentication?** Substantially, and it is the
   single largest lever for anything behind a login wall. On the fixture, executed capability doubled
   from anonymous to user (3 → 6) and rose to 8 for admin, and reachable functional areas went from 5 to
   8; the admin arm is the only one that resolves `/admin*` instead of being refused. On the real app
   (White-Jotter, prior milestone) authentication unlocked the user dashboard that anonymous is redirected
   away from. Anonymous exploration cannot see this surface at all — it is refused or redirected — so the
   authenticated arms do not merely map *more*, they map a region the anonymous arm provably cannot enter.
2. **Does Agent 1 correctly distinguish anonymous, user, and administrator sessions?** After the Phase 1
   fix, yes: each arm's `session_context` equals its role and the ACG `SessionRef.role` matches, so the
   three permission contexts are distinct even when they share a cookie name. Before the fix they all
   read `"anonymous"`.
3. **Can it record and reproduce authenticated workflows without leaking credentials or crossing roles?**
   For authenticated read workflows, yes. The login is recorded as a Graph A prerequisite (method, route,
   field names, role, opaque `account_ref` — no values), and authenticated workflows (login → dashboard →
   orders/profile) are replay-reproduced (user 9 and admin 11 capabilities reproduced; 12/12 replay
   navigations succeeded in the user arm). No credential or session-token value appears in Graph A, the
   ACG, the sidecar, or this report, and no capability above role was ever executed. The caveat is scope:
   this is demonstrated for authenticated *read* workflows; authenticated *write* workflows are deferred
   rather than executed (Q4), so their reproduction is not demonstrated.
4. **Does the frontier terminate for lack of eligible actions, or because it fails to generate/prioritize
   them?** It fails to *prioritize* them; it does not run out. Every arm ended below all three budget caps
   (55/180 transitions, ~196/260 actions, ~90/110 s), at the discovery→replay reserve boundary
   ([explorer.py:2351](agent1/explorer.py#L2351)), with 2–3 eligible write actions **still queued**. Those
   write form-submits are generated and present in Graph A as safe controls, but the conservative −45
   deprioritization of a non-search submission when any other control is visible
   ([explorer.py:2226](agent1/explorer.py#L2226)) keeps them behind all navigation, and discovery yields
   its remaining budget to replay before reaching them. This is deliberate conservatism (avoid premature
   state changes), but its consequence is that, on a realistic page where the write form shares the page
   with a nav bar, authenticated writes are mapped structurally yet essentially never executed — so
   `disposable` write mode rarely gets to exercise a write. That is a prioritization/budget-policy limit,
   not a frontier-generation failure and not genuine exhaustion.
5. **What actually causes HTTP-budget exhaustion in resource-heavy applications?** Redundant refetching of
   a small set of identical static assets on every navigation and replay (68–90% of all requests in the
   ComfyUI traces), because the route interceptor's own fetch defeats the browser cache and restored
   pages start cold — not depth, not the spider, not the frontier model.
6. **Does the improvement increase functional discovery or only reduce resource consumption?** It
   increases functional *reproduction* and exploration depth, not just request count. On the fixture both
   arms discover all nine functional capabilities (the fixture is small, so discovery saturates), but the
   baseline exhausts its HTTP budget during discovery and replay-validates **zero** workflows, whereas the
   treatment validates **ten** and explores ~6× deeper (200 vs 31 actions) within the same budget and
   wall-clock. So the honest claim is: the improvement converts budget that was spent refetching identical
   assets into executed-and-reproduced functionality. Where discovery is *not* saturated (a larger app
   like ComfyUI), freeing 68–90% of the budget is expected to raise discovery too, but that is an
   inference from the frozen traces, not measured here, and is stated as such.
7. **The single strongest remaining architectural bottleneck.** For a functionality *mapper*, it is that
   **state-changing capabilities are mapped but not executed or reproduced**. Across roles the agent
   reliably discovers and replay-reproduces read functionality, but the −45 write deferral plus the
   discovery/replay budget split means create/update/delete — often the most role-defining behaviors — are
   recorded structurally and left unverified. Closing it is not a tuning change: it needs a budget policy
   that, once discovery is otherwise drained, spends reserved capacity to execute the queued safe writes
   on an attested disposable environment (and to replay-validate them), without weakening the premature-
   state-change guard elsewhere. The strongest *efficiency* bottleneck — redundant static-asset refetching
   — is addressed by Phase 4; what remains on that axis is dynamic XHR polling and replay cold-starts,
   which the static-asset cache does not touch.

---

## 6. Deviations and honesty notes

- Administrator credentials for a real WebExploitBench app were unavailable; the three-role comparison
  therefore runs on an isolated fixture with genuine authorization, as the milestone permits, and
  White-Jotter remains the real-app anonymous-vs-user data point (admin reported as a barrier, not
  explored).
- No independent completeness percentage is invented; recall/precision are reported only where the
  fixture's own annotations exist.
