"""Work Engine errors — no silent failure, no silent transition.

Every refused transition raises a specific, typed error naming exactly which
permanent rule blocked it (illegal state move, wrong authority, separation of
duties, missing human gate, missing evidence, missing review). The engine never
advances a case quietly and never fails quietly.
"""

from __future__ import annotations


class WorkError(Exception):
    """Base class for all Work Engine errors."""


class CaseNotFound(WorkError):
    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        super().__init__(f"no such case: {case_id}")


class IllegalTransition(WorkError):
    """The requested gate does not apply to the case's current state."""

    def __init__(self, case_id: str, gate: str, state) -> None:
        self.case_id, self.gate, self.state = case_id, gate, state
        super().__init__(f"gate {gate!r} cannot fire from state {getattr(state, 'value', state)!r}")


class TerminalState(WorkError):
    """The case is retired & archived — a permanent terminal state."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        super().__init__(f"case {case_id} is retired & archived; no transition is possible")


class GateAuthorityError(WorkError):
    """The actor does not hold the role the gate requires."""

    def __init__(self, gate: str, required, held) -> None:
        super().__init__(
            f"gate {gate!r} requires role {getattr(required, 'value', required)!r}, "
            f"actor holds {getattr(held, 'value', held)!r}"
        )


class SeparationOfDutiesError(WorkError):
    """The actor produced this knowledge and may not review/approve it (REF-001 ภาค ๔)."""

    def __init__(self, gate: str, actor_id: str) -> None:
        super().__init__(
            f"separation of duties: actor {actor_id!r} produced this case and "
            f"cannot also act at gate {gate!r}"
        )


class HumanApprovalRequired(WorkError):
    """A human-mandatory gate (approval/publication/retirement) was driven by a non-human actor."""

    def __init__(self, gate: str, actor_id: str) -> None:
        super().__init__(
            f"gate {gate!r} is human-mandatory; actor {actor_id!r} is not human "
            f"(AI may operate but never holds the gate — ADR-002 W6)"
        )


class EvidenceRequired(WorkError):
    """A transition was attempted with no evidence (no transition without evidence)."""

    def __init__(self, gate: str) -> None:
        super().__init__(f"gate {gate!r} requires evidence; none supplied")


class ReviewRequired(WorkError):
    """Approval was attempted without a passing review on record."""

    def __init__(self, case_id: str) -> None:
        super().__init__(f"case {case_id} cannot be approved without a passing review")


class OwnershipError(WorkError):
    """An open case would be left without an accountable owner (W3)."""


class DuplicateCase(WorkError):
    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        super().__init__(f"case already exists: {case_id}")
