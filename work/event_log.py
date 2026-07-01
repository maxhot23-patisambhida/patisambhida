"""The append-only event log — the immutable spine of the Work Engine.

History *only grows* (ADR-002 W4; OPS-001 I5/I7). The event log is the single
source of truth for all work: a case's current state is not stored, it is
*derived* by folding the case's events (see ``case.py``). There is no API to
edit or delete an event — the only mutation is ``append``.

This is the "Runtime History" of KOS-RUN-001: one ordered log, scoped per
engine. Ordering is by a monotonic sequence number, so replay is deterministic;
timestamps are provenance and never affect derived state (the same
determinism-vs-provenance split the Repository uses).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterator

# ── event types ────────────────────────────────────────────────────────────────
CASE_CREATED = "case_created"
OWNERSHIP_ASSIGNED = "ownership_assigned"
OWNERSHIP_TRANSFERRED = "ownership_transferred"
EVIDENCE_ATTACHED = "evidence_attached"
REVIEW_RECORDED = "review_recorded"
GATE_PASSED = "gate_passed"          # a transition fired; payload carries the Decision + to-state
GATE_REJECTED = "gate_rejected"      # authority declined to advance; payload carries the Decision


def utc_now() -> str:
    """Default clock — ISO-8601 UTC. Injectable for deterministic tests."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Event:
    """One immutable fact in the life of a case.

    ``seq`` is the engine-wide monotonic order (the basis for deterministic
    replay). ``payload`` is a frozen mapping describing what happened; transition
    events carry a ``decision`` and a ``to`` state inside it.
    """
    seq: int
    timestamp: str
    case_id: str
    type: str
    actor_id: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "caseId": self.case_id,
            "type": self.type,
            "actorId": self.actor_id,
            "payload": self.payload,
        }


class EventLog:
    """An append-only, ordered, immutable log of :class:`Event`.

    The only write operation is :meth:`append`. Events are never updated or
    removed; that is what makes case history permanent and auditable.
    """

    def __init__(self, clock: Callable[[], str] = utc_now,
                 sink: Callable[[Event], None] | None = None) -> None:
        self._events: list[Event] = []
        self._clock = clock
        self._sink = sink  # optional observer (e.g. a future persistent runtime); never reads back

    def append(self, case_id: str, type: str, actor_id: str, payload: dict | None = None) -> Event:
        event = Event(
            seq=len(self._events),
            timestamp=self._clock(),
            case_id=case_id,
            type=type,
            actor_id=actor_id,
            payload=dict(payload or {}),
        )
        self._events.append(event)
        if self._sink is not None:
            self._sink(event)
        return event

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def all(self) -> list[Event]:
        """Every event in append order (a copy — the log itself is never exposed mutably)."""
        return list(self._events)

    def for_case(self, case_id: str) -> list[Event]:
        """This case's history, in order — the case's permanent record."""
        return [e for e in self._events if e.case_id == case_id]

    def case_ids(self) -> list[str]:
        """Distinct case ids in first-seen order (deterministic)."""
        seen: dict[str, None] = {}
        for e in self._events:
            seen.setdefault(e.case_id, None)
        return list(seen)
