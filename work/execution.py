"""The Work Engine — the living heart that moves Knowledge through the organization.

This is the execution layer. It reads Knowledge **only through the Office SDK**
(never the Repository, never JSON), holds the append-only event log, and offers
the case operations the organization performs: create · load · assign · transfer
· review · approve · reject · publish · retire, plus state, history and queues.

It contains no business knowledge of its own and no AI: it *executes* the
permanent rules defined in ``state_machine``/``gate`` and recorded through
``transition``. Knowledge changes only as the governed, evented effect of a case
transition (ADR-002 §7.4 — runtime through Work alone).
"""

from __future__ import annotations

from typing import Callable

from office import open_office

from . import event_log as log
from . import state_machine as sm
from . import transition as tr
from .approval import Actor, ReviewRecord
from .case import Case, KnowledgeRef, replay
from .evidence import Evidence
from . import evidence as ev
from .event_log import EventLog, utc_now
from .exceptions import (
    CaseNotFound,
    DuplicateCase,
    GateAuthorityError,
    OwnershipError,
    SeparationOfDutiesError,
    WorkError,
)
from .queue import WorkQueue
from .state_machine import Role, State


def _as_evidence(evidence) -> tuple[Evidence, ...]:
    if evidence is None:
        return ()
    if isinstance(evidence, Evidence):
        return (evidence,)
    return tuple(evidence)


class WorkEngine:
    """Executes Knowledge Cases over the Office SDK."""

    def __init__(self, office, *, clock: Callable[[], str] = utc_now, sink=None) -> None:
        self._office = office
        self._log = EventLog(clock=clock, sink=sink)

    # ── creation & loading ────────────────────────────────────────────────
    def create_case(self, knowledge_id: str, book_number: int, *, opened_by: Actor,
                    owner: str, corpus_id: str | None = None, case_id: str | None = None,
                    rationale: str = "case opened") -> Case:
        """Open a case to carry one Knowledge Object through its lifecycle.

        The Knowledge Object is read through the Office SDK to bind the case's
        provenance (W2) and to seed birth evidence (W5) from its canonical
        citation. The case opens at ① Identified, owned (W3) and never orphaned.
        """
        if not owner:
            raise OwnershipError("a case must be opened with an accountable owner")
        cid = corpus_id if corpus_id is not None else self._office.knowledge._corpus(None)
        ko = self._office.knowledge.get_knowledge(book_number, knowledge_id, corpus_id=cid)

        case_id = case_id or f"KC-{ko.id}"
        if case_id in set(self._log.case_ids()):
            raise DuplicateCase(case_id)

        ref = KnowledgeRef(corpus_id=cid, book_number=book_number, knowledge_id=ko.id,
                           code=ko.code, name=ko.names.primary)
        birth_evidence = []
        if ko.citation and ko.citation.citation_id:
            birth_evidence.append(ev.citation(ko.citation.citation_id, "provenance of carried knowledge"))
        birth_evidence.append(ev.knowledge(ko.id, rationale))

        self._log.append(case_id, log.CASE_CREATED, opened_by.id, payload={
            "knowledgeRef": ref.to_dict(),
            "owner": owner,
            "state": State.IDENTIFIED.value,
            "evidence": [e.to_dict() for e in birth_evidence],
        })
        return self.load_case(case_id)

    def load_case(self, case_id: str) -> Case:
        events = self._log.for_case(case_id)
        if not events:
            raise CaseNotFound(case_id)
        return replay(events)

    # ── ownership (W3 — never orphaned) ────────────────────────────────────
    def assign_case(self, case_id: str, owner: str, *, by: Actor) -> Case:
        return self._reassign(case_id, owner, by, log.OWNERSHIP_ASSIGNED)

    def transfer_case(self, case_id: str, to_owner: str, *, by: Actor) -> Case:
        return self._reassign(case_id, to_owner, by, log.OWNERSHIP_TRANSFERRED)

    def _reassign(self, case_id: str, owner: str, by: Actor, event_type: str) -> Case:
        case = self.load_case(case_id)
        if not owner:
            raise OwnershipError("cannot leave an open case without an owner")
        if case.is_terminal:
            raise WorkError(f"case {case_id} is retired; ownership is frozen")
        self._log.append(case_id, event_type, by.id, payload={"owner": owner, "from": case.owner})
        return self.load_case(case_id)

    # ── evidence (W5) ──────────────────────────────────────────────────────
    def attach_evidence(self, case_id: str, evidence, *, by: Actor) -> Case:
        items = _as_evidence(evidence)
        if not items:
            raise WorkError("attach_evidence requires at least one evidence item")
        case = self.load_case(case_id)
        self._log.append(case_id, log.EVIDENCE_ATTACHED, by.id,
                         payload={"evidence": [e.to_dict() for e in items]})
        return self.load_case(case_id)

    # ── review (the work; emits an immutable Review Record) ─────────────────
    def record_review(self, case_id: str, *, reviewer: Actor, outcome: str, criteria: str,
                      evidence=None) -> Case:
        """Record a Reviewer's evaluation. A passing review is the approval gate's precondition."""
        case = self.load_case(case_id)
        if reviewer.role != Role.REVIEWER:
            raise GateAuthorityError("review", Role.REVIEWER, reviewer.role)
        if reviewer.id in case.producers:
            raise SeparationOfDutiesError("review", reviewer.id)
        review = ReviewRecord(reviewer_id=reviewer.id, outcome=outcome, criteria=criteria,
                              recorded_in_state=case.state.value, evidence=_as_evidence(evidence))
        self._log.append(case_id, log.REVIEW_RECORDED, reviewer.id, payload={"review": review.to_dict()})
        return self.load_case(case_id)

    # ── governed transitions ───────────────────────────────────────────────
    def _fire(self, case_id: str, gate: str, actor: Actor, evidence, rationale: str) -> Case:
        case = self.load_case(case_id)
        plan = tr.plan_transition(case, gate, actor, _as_evidence(evidence), rationale)
        self._log.append(case_id, plan.event_type, actor.id, plan.payload)
        return self.load_case(case_id)

    def register(self, case_id: str, *, actor: Actor, evidence, rationale="registered") -> Case:
        return self._fire(case_id, sm.REGISTRATION, actor, evidence, rationale)

    def begin_formation(self, case_id: str, *, actor: Actor, evidence, rationale="formation begun") -> Case:
        return self._fire(case_id, sm.BEGIN_FORMATION, actor, evidence, rationale)

    def validate(self, case_id: str, *, actor: Actor, evidence, rationale="fidelity verified") -> Case:
        return self._fire(case_id, sm.VALIDATION, actor, evidence, rationale)

    def integrate(self, case_id: str, *, actor: Actor, evidence, rationale="integrated") -> Case:
        return self._fire(case_id, sm.INTEGRATION, actor, evidence, rationale)

    def approve(self, case_id: str, *, actor: Actor, evidence, rationale="approved for publication") -> Case:
        return self._fire(case_id, sm.APPROVAL, actor, evidence, rationale)

    def publish(self, case_id: str, *, actor: Actor, evidence, rationale="published") -> Case:
        return self._fire(case_id, sm.PUBLICATION, actor, evidence, rationale)

    def revise(self, case_id: str, *, actor: Actor, evidence, rationale="revision opened") -> Case:
        return self._fire(case_id, sm.REVISION, actor, evidence, rationale)

    def supersede(self, case_id: str, *, actor: Actor, evidence, rationale="superseded") -> Case:
        return self._fire(case_id, sm.SUPERSESSION, actor, evidence, rationale)

    def retire(self, case_id: str, *, actor: Actor, evidence, rationale="retired & archived") -> Case:
        return self._fire(case_id, sm.RETIREMENT, actor, evidence, rationale)

    def reject(self, case_id: str, gate: str, *, actor: Actor, rationale: str, evidence=None) -> Case:
        """Record a permanent rejection at a gate — declines to advance, never rewinds."""
        case = self.load_case(case_id)
        plan = tr.plan_rejection(case, gate, actor, rationale, _as_evidence(evidence))
        self._log.append(case_id, plan.event_type, actor.id, plan.payload)
        return self.load_case(case_id)

    # ── tracking, history, queues ──────────────────────────────────────────
    def state(self, case_id: str) -> State:
        return self.load_case(case_id).state

    def history(self, case_id: str) -> list[log.Event]:
        events = self._log.for_case(case_id)
        if not events:
            raise CaseNotFound(case_id)
        return events

    def cases(self) -> list[Case]:
        return [replay(self._log.for_case(cid)) for cid in self._log.case_ids()]

    def queue(self) -> WorkQueue:
        return WorkQueue(self.cases())

    @property
    def office(self):
        return self._office

    @property
    def event_log(self) -> EventLog:
        return self._log


def open_work_engine(office=None, *, root=None, validate: bool = True,
                     clock: Callable[[], str] = utc_now, sink=None) -> WorkEngine:
    """Open the Work Engine.

    Opens the Office SDK (and through it the validated Query Engine) unless an
    ``office`` is supplied, then builds the engine on top. ``clock`` and ``sink``
    are injectable for deterministic tests and for a future persistent runtime
    to observe the event stream.
    """
    off = office if office is not None else open_office(root, validate=validate)
    return WorkEngine(off, clock=clock, sink=sink)
