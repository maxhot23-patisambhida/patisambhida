"""The Knowledge Case — the Work Object the engine moves through the lifecycle.

A Case is the *episode of work* that carries one Knowledge Object through
KOS-REF-001. It is **derived, never stored**: the engine folds the case's events
(``event_log.py``) into this immutable snapshot. That is what guarantees W4 —
state is a function of history, and history only grows.

The snapshot carries all six Work invariants (ADR-002 §5.3):

    W1 Identity     case_id
    W2 Provenance   knowledge_ref + opened_by/at (why the case was opened)
    W3 Ownership    owner (never None while the case is open)
    W4 Lifecycle    state (folded from the event log)
    W5 Evidence     evidence (accumulated, never removed)
    W6 Governance   decisions + reviews (the immutable records gates emitted)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import event_log as log
from . import state_machine as sm
from .approval import PASSED, Decision, ReviewRecord
from .evidence import Evidence
from .state_machine import State


@dataclass(frozen=True)
class KnowledgeRef:
    """W2 provenance: the canonical knowledge this case carries (read via Office SDK)."""
    corpus_id: str
    book_number: int
    knowledge_id: str
    code: str = ""
    name: str = ""

    def to_dict(self) -> dict:
        return {
            "corpusId": self.corpus_id,
            "bookNumber": self.book_number,
            "knowledgeId": self.knowledge_id,
            "code": self.code,
            "name": self.name,
        }


@dataclass(frozen=True)
class Case:
    """An immutable snapshot of a case, folded from its event log."""
    id: str                                    # W1
    knowledge_ref: KnowledgeRef                # W2
    opened_by: str                             # W2
    opened_at: str                             # W2
    owner: str                                 # W3
    state: State                               # W4
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)        # W5
    reviews: tuple[ReviewRecord, ...] = field(default_factory=tuple)     # W6
    decisions: tuple[Decision, ...] = field(default_factory=tuple)       # W6
    producers: frozenset = field(default_factory=frozenset)             # actors who produced (SoD)
    last_seq: int = -1

    # -- derived helpers -------------------------------------------------------
    @property
    def is_terminal(self) -> bool:
        return sm.is_terminal(self.state)

    @property
    def is_open(self) -> bool:
        return not self.is_terminal

    def has_passing_review(self) -> bool:
        """A passing review recorded while the case was Integrated (approval precondition)."""
        return any(r.outcome == PASSED and r.recorded_in_state == State.INTEGRATED.value
                   for r in self.reviews)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "knowledgeRef": self.knowledge_ref.to_dict(),
            "openedBy": self.opened_by,
            "openedAt": self.opened_at,
            "owner": self.owner,
            "state": self.state.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "reviews": [r.to_dict() for r in self.reviews],
            "decisions": [d.to_dict() for d in self.decisions],
        }


def replay(events: list[log.Event]) -> Case:
    """Fold a case's events into its current snapshot (deterministic, pure).

    This is the only place that interprets event payloads into state. Because it
    is a pure fold over an append-only log, the same events always yield the same
    Case — the heart of the engine's determinism.
    """
    if not events:
        raise ValueError("cannot replay an empty event stream")

    case: Case | None = None
    for e in events:
        case = _apply(case, e)
    assert case is not None
    return case


def _apply(case: Case | None, e: log.Event) -> Case:
    p = e.payload

    if e.type == log.CASE_CREATED:
        ref = p["knowledgeRef"]
        return Case(
            id=e.case_id,
            knowledge_ref=KnowledgeRef(
                corpus_id=ref["corpusId"], book_number=ref["bookNumber"],
                knowledge_id=ref["knowledgeId"], code=ref.get("code", ""),
                name=ref.get("name", "")),
            opened_by=e.actor_id,
            opened_at=e.timestamp,
            owner=p["owner"],
            state=State(p["state"]),
            evidence=tuple(_evidence(p.get("evidence", []))),
            last_seq=e.seq,
        )

    assert case is not None, "first event of a case must be CASE_CREATED"

    if e.type in (log.OWNERSHIP_ASSIGNED, log.OWNERSHIP_TRANSFERRED):
        return replace(case, owner=p["owner"], last_seq=e.seq)

    if e.type == log.EVIDENCE_ATTACHED:
        return replace(case, evidence=case.evidence + tuple(_evidence(p.get("evidence", []))),
                       last_seq=e.seq)

    if e.type == log.REVIEW_RECORDED:
        review = _review(p["review"])
        return replace(case, reviews=case.reviews + (review,), last_seq=e.seq)

    if e.type == log.GATE_PASSED:
        decision = _decision(p["decision"])
        producers = case.producers
        if p.get("gate") == sm.BEGIN_FORMATION:
            producers = producers | {e.actor_id}
        return replace(
            case,
            state=State(p["to"]),
            decisions=case.decisions + (decision,),
            evidence=case.evidence + tuple(decision.evidence),
            producers=producers,
            last_seq=e.seq,
        )

    if e.type == log.GATE_REJECTED:
        decision = _decision(p["decision"])
        # A rejection is a permanent decision; state does not change (no rewind).
        return replace(case, decisions=case.decisions + (decision,),
                       evidence=case.evidence + tuple(decision.evidence), last_seq=e.seq)

    raise ValueError(f"unknown event type during replay: {e.type!r}")


# ── payload → object rebuilders (the only payload-aware code) ──────────────────

def _evidence(items) -> list[Evidence]:
    return [Evidence(kind=i["kind"], ref=i.get("ref", ""), note=i.get("note", "")) for i in items]


def _review(d: dict) -> ReviewRecord:
    return ReviewRecord(
        reviewer_id=d["reviewerId"], outcome=d["outcome"], criteria=d["criteria"],
        recorded_in_state=d["recordedInState"], evidence=tuple(_evidence(d.get("evidence", []))))


def _decision(d: dict) -> Decision:
    return Decision(
        gate=d["gate"], outcome=d["outcome"], actor_id=d["actorId"],
        actor_role=d["actorRole"], rationale=d["rationale"],
        evidence=tuple(_evidence(d.get("evidence", []))))
