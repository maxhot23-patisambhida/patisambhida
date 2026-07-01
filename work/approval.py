"""Governance records (W6) — the immutable facts a gate emits.

The verb↔fact split (ADR-002 §5.1): the *episode* of reviewing or approving is
work, but the **record it emits** — a Review Record, a Decision — is an
immutable Governance Object. Once emitted it is never rewritten; it is appended
to the case's event log and survives forever.

These dataclasses are those records. The Work Engine produces them at gates and
stores them inside events; it never edits one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import Evidence

# Decision / review outcomes.
PASSED = "passed"
REJECTED = "rejected"


@dataclass(frozen=True)
class Actor:
    """A bearer of a role at a gate. The bearer may be human or AI; only humans
    may hold a human-mandatory gate (W6)."""
    id: str
    role: object          # state_machine.Role
    is_human: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("actor.id is required")


@dataclass(frozen=True)
class ReviewRecord:
    """An immutable evaluation emitted by a Reviewer (Governance Object).

    A passing review against the integrated knowledge is the precondition the
    Approval gate consumes — review is the work, this record is the fact.
    """
    reviewer_id: str
    outcome: str                       # PASSED | REJECTED
    criteria: str                      # what was evaluated
    recorded_in_state: str             # the case state when the review was recorded
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "reviewerId": self.reviewer_id,
            "outcome": self.outcome,
            "criteria": self.criteria,
            "recordedInState": self.recorded_in_state,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True)
class Decision:
    """The immutable Decision a gate produces (Governance Object).

    Emitted at every gate firing — pass *or* reject. A rejection is itself a
    permanent decision (it does not delete or rewind the case); it records that
    authority declined to advance, and why.
    """
    gate: str
    outcome: str                       # PASSED | REJECTED
    actor_id: str
    actor_role: str
    rationale: str
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "outcome": self.outcome,
            "actorId": self.actor_id,
            "actorRole": self.actor_role,
            "rationale": self.rationale,
            "evidence": [e.to_dict() for e in self.evidence],
        }
