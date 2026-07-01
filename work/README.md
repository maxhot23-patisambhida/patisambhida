# Work Engine

> Production Sprint 005 · Office of Enterprise Architecture
> The execution layer of the Knowledge Operating System.

```
Source → Compiler → Repository → Query Engine → Office SDK → Work Engine → future AI Offices
 stores ──────────────────────┘   understands ─┘            moves ────────┘
```

The backend kernel (Compiler · Repository · Query Engine · Office SDK) is frozen.
The next responsibility is not data — it is **work**. The Work Engine executes
**Knowledge Cases**: it moves a piece of knowledge through its permanent
lifecycle under mandatory governance, recording every step in an immutable
history.

> Repository **stores** Knowledge · Office SDK **understands** Knowledge ·
> the Work Engine **moves** Knowledge through the organization.

## The Case

A **Case** is the *episode of work* that carries one Knowledge Object through
the canonical lifecycle (KOS-REF-001). It is **derived, never stored** — the
current state is a deterministic fold of an append-only event log. Every case
carries the six Work invariants of ADR-002 §5.3:

| | Invariant | In the engine |
|---|---|---|
| **W1** | Identity | `case.id` |
| **W2** | Provenance | `knowledge_ref` + `opened_by` / `opened_at` |
| **W3** | Ownership | `owner` — never empty while the case is open |
| **W4** | Lifecycle | `state`, folded from the event log; history only grows |
| **W5** | Evidence | `evidence` — accumulated, never removed |
| **W6** | Governance | `decisions` + `reviews` — the immutable records gates emit |

## The lifecycle (KOS-REF-001)

```
① Identified ─reg→ ② Registered ─form→ ③ In Formation ─valid→ ④ Canonical
   ─integrate→ ⑤ Integrated ─approve★→ ⑥ Approved ─publish★→ ⑦ Published
   ─revise→ ⑧ Under Revision ─supersede→ ⑨ Superseded ─retire★→ ⑩ Retired & Archived

★ = human-mandatory gate (Approval · Publication · Retirement)
Retirement is the universal exit — any active state may descend to ⑩ "when the time comes".
```

Ten permanent states, eight governance gates, six generic roles
(Producer · Custodian · Reviewer · Governor · Consumer · Maintainer). Each gate
fixes the same four things — **Authority · Evidence · Decision · Traceability**.

## Usage

```python
from work import open_work_engine, Actor, Role, evidence

engine   = open_work_engine()                       # reads Knowledge only via the Office SDK
producer = Actor("alice", Role.PRODUCER)
custodian= Actor("carl",  Role.CUSTODIAN)
reviewer = Actor("rita",  Role.REVIEWER)
governor = Actor("dana",  Role.GOVERNOR, is_human=True)

case = engine.create_case("KNW-B01-0001", book_number=1,
                          opened_by=producer, owner="office.compilation")

engine.register(case.id,        actor=custodian, evidence=evidence.note("source in custody"))
engine.begin_formation(case.id, actor=producer,  evidence=evidence.note("forming from source"))
engine.validate(case.id,        actor=reviewer,  evidence=evidence.note("fidelity verified"))
engine.integrate(case.id,       actor=custodian, evidence=evidence.note("relationships + citations"))

engine.record_review(case.id, reviewer=reviewer, outcome="passed", criteria="permanence test")
engine.approve(case.id, actor=governor, evidence=evidence.note("meets criteria"))   # human gate
engine.publish(case.id, actor=governor, evidence=evidence.note("released"))         # human gate

engine.state(case.id)        # State.PUBLISHED
engine.history(case.id)      # the case's permanent, ordered event record
engine.queue().inbox("office.compilation")
```

Ownership: `assign_case` / `transfer_case`. Negative path: `reject(case_id, gate,
…)` records a permanent rejection Decision that **declines to advance** — it
never deletes or rewinds the case.

## The seven enforced rules

Every transition is planned in one place (`transition.py`) and refused with a
specific error if any rule fails — **No Silent Transition**:

| Rule | Error | Source |
|---|---|---|
| The gate must apply to the current state | `IllegalTransition` | KOS-REF-001 ภาค ๕ |
| A retired case never moves again | `TerminalState` | Retirement Invariant |
| The actor must hold the gate's role | `GateAuthorityError` | Authority |
| Approval/Publication/Retirement need a **human** | `HumanApprovalRequired` | W6 / มาตรา ๙ |
| Producer ≠ Reviewer ≠ Governor at a gate | `SeparationOfDutiesError` | ภาค ๔ |
| No transition without evidence | `EvidenceRequired` | มาตรา ๕, ๘ |
| Approval needs a passing review on record | `ReviewRequired` | ⑤→⑥ |

## The verb↔fact split (ADR-002 §5.1)

Reviewing and approving are *work* (mutable episodes). The **records they emit**
— `ReviewRecord`, `Decision` — are immutable Governance Objects, appended to the
event log and never rewritten. A rejection is itself a permanent Decision.

## Principles

Append-only · Immutable history · Deterministic · Evidence required · Governance
required · Human approval required · No silent transition.

The state of a case is a pure fold of its events, so the same history always
yields the same case. Timestamps are provenance and never affect derived state
(the determinism-vs-provenance split the Repository also uses); inject a `clock`
for reproducible runs.

## Integration boundary

The Work Engine **uses the Office SDK** and nothing below it. It never reads the
Repository, never imports the Query Engine, never parses JSON, and implements no
business knowledge — a boundary check in the test suite asserts this. Knowledge
changes only as the governed, evented effect of a Work transition (ADR-002 §7.4
— *runtime through Work alone*).

## What this engine is not

No AI · no UI · no dashboard · no runtime daemon. Only **execution**. The event
log exposes an optional `sink` so a future persistent runtime can observe the
stream, but persistence, scheduling and agents are out of scope by commission.

## Package layout

| File | Role |
|---|---|
| `state_machine.py` | the 10 states, 6 roles, 8 gates, transition table (pure) |
| `gate.py` | per-gate requirements (authority · human · evidence · SoD) |
| `evidence.py` | `Evidence` references (W5) |
| `approval.py` | `Actor`, `ReviewRecord`, `Decision` — governance records (W6) |
| `event_log.py` | the append-only immutable event log (W4) |
| `transition.py` | pure transition/rejection planning — every rule, one place |
| `case.py` | the `Case` Work Object + deterministic `replay` (fold) |
| `queue.py` | resting views over open cases (inbox / by-state / backlog) |
| `execution.py` | `WorkEngine` + `open_work_engine()` — the public API |
| `exceptions.py` | typed errors — no silent failure |
| `tests/` | real cases over real knowledge (no mocks) |

## Tests

```bash
python work/tests/test_work_engine.py     # compiles Book 1, drives real cases, 37 checks
```

Real repositories only — no mocks, no fabricated data.
