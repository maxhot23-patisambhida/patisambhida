"""Work queues — resting views over open cases.

Cases at rest are not lost; they wait in queues (KOS-RUN-002 F3 resting states).
This module derives queue *views* from the live set of cases — it stores nothing
of its own and decides nothing; ownership and state live in the event log.

Two views matter for the first engine:

* **inbox(owner)** — the open cases an owner is accountable for (a capacity-wait
  queue: work waiting for its owner to act).
* **by_state(state)** — every open case resting at a lifecycle state (a
  dependency-wait view: work waiting on a gate).
"""

from __future__ import annotations

from .case import Case
from .state_machine import State


class WorkQueue:
    def __init__(self, cases: list[Case]) -> None:
        # deterministic order: by case id
        self._cases = sorted(cases, key=lambda c: c.id)

    def open_cases(self) -> list[Case]:
        return [c for c in self._cases if c.is_open]

    def inbox(self, owner: str) -> list[Case]:
        """Open cases owned by ``owner`` — what is waiting on them to act."""
        return [c for c in self._cases if c.is_open and c.owner == owner]

    def by_state(self, state: State) -> list[Case]:
        return [c for c in self._cases if c.state == state]

    def owners(self) -> list[str]:
        """Distinct owners of open cases (deterministic, sorted)."""
        return sorted({c.owner for c in self._cases if c.is_open})

    def backlog(self) -> dict[str, int]:
        """Count of open cases per lifecycle state (stable key order)."""
        counts: dict[str, int] = {}
        for c in self.open_cases():
            counts[c.state.value] = counts.get(c.state.value, 0) + 1
        return counts
