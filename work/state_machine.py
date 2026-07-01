"""The canonical Knowledge lifecycle state machine (KOS-REF-001).

This module encodes — and only encodes — the ratified lifecycle: the **ten
permanent states**, the **six generic roles**, and the **eight governance
gates** that move a state to its successor. It contains no execution, no
storage, no business knowledge — just the permanent shape of how knowledge
lives, expressed as deterministic data and pure functions.

    ① Identified → ② Registered → ③ In Formation → ④ Canonical →
    ⑤ Integrated → ⑥ Approved → ⑦ Published → ⑧ Under Revision →
    ⑨ Superseded → ⑩ Retired & Archived

Nothing here advances a case; ``transition.py`` plans transitions against this
table and ``execution.py`` records them. Changing the lifecycle means changing
this one module — exactly as KOS-REF-001 intends.
"""

from __future__ import annotations

from enum import Enum


class State(Enum):
    """The ten permanent lifecycle states (KOS-REF-001 ภาค ๑)."""
    IDENTIFIED = "identified"        # ๑ ระบุ
    REGISTERED = "registered"        # ๒ ขึ้นทะเบียน — birth: identity + provenance sealed
    IN_FORMATION = "in_formation"    # ๓ ก่อร่าง
    CANONICAL = "canonical"          # ๔ แก่น
    INTEGRATED = "integrated"        # ๕ บูรณาการ
    APPROVED = "approved"            # ๖ อนุมัติ
    PUBLISHED = "published"          # ๗ เผยแพร่
    UNDER_REVISION = "under_revision"  # ๘ ปรับปรุง
    SUPERSEDED = "superseded"        # ๙ ถูกแทนที่/เลิกใช้
    RETIRED = "retired"              # ๑๐ ปลดระวางและจัดเก็บ — terminal, never deleted


class Role(Enum):
    """The six generic lifecycle roles (KOS-REF-001 ภาค ๔).

    Roles are *functions*, not persons; a bearer may be human or AI. The
    Separation-of-Duties rule (below) binds the roles, never the bearers.
    """
    PRODUCER = "producer"        # ผู้ผลิต — forms/derives/reshapes; never approves own work
    CUSTODIAN = "custodian"      # ผู้พิทักษ์ — guards identity/provenance; nothing silently deleted
    REVIEWER = "reviewer"        # ผู้ทบทวน — evaluates against criteria, emits Reviews
    GOVERNOR = "governor"        # ผู้กำกับ — holds the gate; human-in-the-loop authority
    CONSUMER = "consumer"        # ผู้ใช้ — accesses published knowledge
    MAINTAINER = "maintainer"    # ผู้บำรุงรักษา — revision/supersession/retirement, keeps lineage


# Terminal and active state groupings.
TERMINAL_STATES = frozenset({State.RETIRED})
ACTIVE_STATES = frozenset(s for s in State if s not in TERMINAL_STATES)


# ── the eight governance gates (KOS-REF-001 ภาค ๕) ─────────────────────────────
# Each gate maps the (from → to) state transitions it authorizes. The gate
# *metadata* (authority role, human-mandatory, evidence) lives in gate.py; here
# we fix only which state moves to which, deterministically.

REGISTRATION = "registration"      # ① → ②
VALIDATION = "validation"          # ③ → ④
INTEGRATION = "integration"        # ④ → ⑤
APPROVAL = "approval"              # ⑤ → ⑥   (human-mandatory)
PUBLICATION = "publication"        # ⑥ → ⑦   (human-mandatory)
REVISION = "revision"              # ⑦ → ⑧
SUPERSESSION = "supersession"      # ⑦/⑧ → ⑨
RETIREMENT = "retirement"          # any active → ⑩  (human-mandatory; the universal exit)

# One ungated transition: production begins (state ๓ note "— อยู่ระหว่างผลิต").
# It carries no governance decision, but it is still an explicit, evented move —
# never silent (Principle: No Silent Transition).
BEGIN_FORMATION = "begin_formation"  # ② → ③


GATE_TRANSITIONS: dict[str, frozenset] = {
    REGISTRATION: frozenset({(State.IDENTIFIED, State.REGISTERED)}),
    BEGIN_FORMATION: frozenset({(State.REGISTERED, State.IN_FORMATION)}),
    VALIDATION: frozenset({(State.IN_FORMATION, State.CANONICAL)}),
    INTEGRATION: frozenset({(State.CANONICAL, State.INTEGRATED)}),
    APPROVAL: frozenset({(State.INTEGRATED, State.APPROVED)}),
    PUBLICATION: frozenset({(State.APPROVED, State.PUBLISHED)}),
    REVISION: frozenset({(State.PUBLISHED, State.UNDER_REVISION)}),
    SUPERSESSION: frozenset({
        (State.PUBLISHED, State.SUPERSEDED),
        (State.UNDER_REVISION, State.SUPERSEDED),
    }),
    # Retirement is the human-gated universal exit: any active state may descend
    # to ⑩ "เมื่อถึงเวลา" (KOS-REF-001 ภาค ๑ note + ภาคผนวก ก: ทุกสถานะ → ⑩).
    RETIREMENT: frozenset({(s, State.RETIRED) for s in ACTIVE_STATES}),
}


def target_state(gate: str, current: State) -> State | None:
    """The state ``gate`` moves ``current`` to, or ``None`` if it does not apply."""
    for src, dst in GATE_TRANSITIONS.get(gate, ()):  # deterministic: at most one match
        if src == current:
            return dst
    return None


def gates_from(current: State) -> list[str]:
    """Every gate that can legally fire from ``current`` (stable order)."""
    return [g for g in GATE_TRANSITIONS if target_state(g, current) is not None]


def is_terminal(state: State) -> bool:
    return state in TERMINAL_STATES
