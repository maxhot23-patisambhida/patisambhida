"""Transition planning — every permanent rule, checked in one place.

A transition is *planned* here (pure, no side effects) and *recorded* by
``execution.py``. Planning validates a gate firing against all of KOS-REF-001's
guarantees and either returns the event to append or raises a specific error.
Nothing advances unless every rule passes — **No Silent Transition.**

Order of checks (each maps to a permanent rule):

    terminal?         → a retired case never moves          (Retirement Invariant)
    gate applies?     → state machine                       (KOS-REF-001 ภาค ๕)
    authority?        → actor holds the gate's role          (Authority)
    human present?    → human-mandatory gates                (W6 / ภาค ๕ note)
    separation?       → producer ≠ reviewer ≠ governor       (ภาค ๔ SoD)
    evidence?         → no transition without evidence       (มาตรา ๕, ๘)
    review on record? → approval needs a passing review      (⑤→⑥)
"""

from __future__ import annotations

from dataclasses import dataclass

from . import event_log as log
from . import gate as gates
from . import state_machine as sm
from .approval import PASSED, REJECTED, Actor, Decision
from .case import Case
from .evidence import Evidence
from .exceptions import (
    EvidenceRequired,
    GateAuthorityError,
    HumanApprovalRequired,
    IllegalTransition,
    ReviewRequired,
    SeparationOfDutiesError,
    TerminalState,
)


@dataclass(frozen=True)
class TransitionPlan:
    """The event to append for a validated transition (produced, not yet recorded)."""
    event_type: str
    payload: dict


def _require_applicable(case: Case, gate_name: str) -> sm.State:
    if case.is_terminal:
        raise TerminalState(case.id)
    target = sm.target_state(gate_name, case.state)
    if target is None:
        raise IllegalTransition(case.id, gate_name, case.state)
    return target


def _check_authority_and_human(gate, actor: Actor) -> None:
    if actor.role != gate.authority:
        raise GateAuthorityError(gate.name, gate.authority, actor.role)
    if gate.human_mandatory and not actor.is_human:
        raise HumanApprovalRequired(gate.name, actor.id)


def plan_transition(case: Case, gate_name: str, actor: Actor,
                    evidence: tuple[Evidence, ...], rationale: str) -> TransitionPlan:
    """Validate and plan a *passing* gate firing. Raises on any rule violation."""
    target = _require_applicable(case, gate_name)
    gate = gates.get_gate(gate_name)

    _check_authority_and_human(gate, actor)

    if gate.separation_of_duties and actor.id in case.producers:
        raise SeparationOfDutiesError(gate.name, actor.id)

    if gate.evidence_required and not evidence:
        raise EvidenceRequired(gate.name)

    if gate_name == sm.APPROVAL and not case.has_passing_review():
        raise ReviewRequired(case.id)

    decision = Decision(
        gate=gate.name, outcome=PASSED, actor_id=actor.id,
        actor_role=actor.role.value, rationale=rationale, evidence=tuple(evidence))

    return TransitionPlan(
        event_type=log.GATE_PASSED,
        payload={
            "gate": gate.name,
            "from": case.state.value,
            "to": target.value,
            "decision": decision.to_dict(),
        },
    )


def plan_rejection(case: Case, gate_name: str, actor: Actor,
                   rationale: str, evidence: tuple[Evidence, ...]) -> TransitionPlan:
    """Validate and plan a *rejection* at a gate.

    A rejection is a permanent Decision that declines to advance — it does not
    move, delete, or rewind the case. It still requires the gate to be otherwise
    applicable and the proper authority (a human at human-mandatory gates), and
    it requires a rationale.
    """
    _require_applicable(case, gate_name)
    gate = gates.get_gate(gate_name)
    _check_authority_and_human(gate, actor)
    if not rationale:
        raise EvidenceRequired(gate.name)  # a rejection must state why

    decision = Decision(
        gate=gate.name, outcome=REJECTED, actor_id=actor.id,
        actor_role=actor.role.value, rationale=rationale, evidence=tuple(evidence))

    return TransitionPlan(
        event_type=log.GATE_REJECTED,
        payload={"gate": gate.name, "from": case.state.value, "decision": decision.to_dict()},
    )
