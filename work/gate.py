"""Governance-gate metadata (KOS-REF-001 ภาค ๕).

``state_machine.py`` fixes *which* state each gate moves to. This module fixes
*what each gate demands* before it may fire: which **authority** (role) holds
it, whether a **human** is mandatory, whether **evidence** is required, and
whether **separation of duties** applies.

Every gate in KOS-REF-001 defines the same four things — Authority · Evidence ·
Decision · Traceability. Authority + Evidence are checked here; the Decision and
Traceability (the event) are produced by ``transition.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import state_machine as sm
from .state_machine import Role


@dataclass(frozen=True)
class Gate:
    """Permanent requirements of one governance gate."""
    name: str
    authority: Role
    human_mandatory: bool        # one of approval/publication/retirement → a human must hold it
    evidence_required: bool
    separation_of_duties: bool   # the actor must not have produced this case
    description: str


# The eight gates plus the one ungated production move. Grounded line-by-line in
# KOS-REF-001 ภาค ๕ (the gate table) and ภาค ๔ (Separation of Duties).
GATES: dict[str, Gate] = {
    sm.REGISTRATION: Gate(
        sm.REGISTRATION, Role.CUSTODIAN, False, True, False,
        "① → ② seal identity + provenance; the birth of the enterprise object"),
    sm.BEGIN_FORMATION: Gate(
        sm.BEGIN_FORMATION, Role.PRODUCER, False, True, False,
        "② → ③ production begins (ungated, but evented — never silent)"),
    sm.VALIDATION: Gate(
        sm.VALIDATION, Role.REVIEWER, False, True, True,
        "③ → ④ fidelity to source verified; canonical meaning fixed"),
    sm.INTEGRATION: Gate(
        sm.INTEGRATION, Role.CUSTODIAN, False, True, True,
        "④ → ⑤ relationships + citations complete; no longer isolated"),
    sm.APPROVAL: Gate(
        sm.APPROVAL, Role.GOVERNOR, True, True, True,
        "⑤ → ⑥ human authority grants the right to publish (human-mandatory)"),
    sm.PUBLICATION: Gate(
        sm.PUBLICATION, Role.GOVERNOR, True, True, False,
        "⑥ → ⑦ released to active life (human-mandatory)"),
    sm.REVISION: Gate(
        sm.REVISION, Role.MAINTAINER, False, True, False,
        "⑦ → ⑧ open a successor version without ending the current one"),
    sm.SUPERSESSION: Gate(
        sm.SUPERSESSION, Role.GOVERNOR, False, True, False,
        "⑦/⑧ → ⑨ withdraw from currency, preserved with lineage (not deleted)"),
    sm.RETIREMENT: Gate(
        sm.RETIREMENT, Role.GOVERNOR, True, True, False,
        "→ ⑩ retire & archive; ends active life, history sealed (human-mandatory)"),
}

# The three points where a human must be in the loop (KOS-REF-001 ภาค ๕ note).
HUMAN_MANDATORY = frozenset(name for name, g in GATES.items() if g.human_mandatory)


def get_gate(name: str) -> Gate:
    try:
        return GATES[name]
    except KeyError:
        raise ValueError(f"unknown gate: {name!r}") from None
