"""Work Engine — Production Sprint 005.

The execution layer of the Knowledge Operating System: it moves Knowledge
through the organization by executing **Knowledge Cases** along the canonical
lifecycle (KOS-REF-001) under mandatory governance (ADR-002 W1–W6).

    Repository stores Knowledge · Office SDK understands Knowledge ·
    the Work Engine moves Knowledge through the organization.

    from work import open_work_engine, Actor, Role, evidence

    engine = open_work_engine()                      # reads only via the Office SDK
    producer = Actor("alice", Role.PRODUCER)
    governor = Actor("dana", Role.GOVERNOR, is_human=True)

    case = engine.create_case("KNW-B01-0001", book_number=1,
                              opened_by=producer, owner="office.compilation")
    engine.register(case.id, actor=Actor("carl", Role.CUSTODIAN),
                    evidence=evidence.note("source in custody"))
    ...
    engine.approve(case.id, actor=governor, evidence=evidence.note("meets criteria"))
    engine.publish(case.id, actor=governor, evidence=evidence.note("released"))

Principles: Append-only · Immutable history · Deterministic · Evidence required
· Governance required · Human approval required · No silent transition. It never
reads the Repository, never parses JSON, and implements no business knowledge.
"""

from __future__ import annotations

from . import evidence
from .approval import PASSED, REJECTED, Actor, Decision, ReviewRecord
from .case import Case, KnowledgeRef, replay
from .event_log import Event, EventLog
from .evidence import Evidence
from .execution import WorkEngine, open_work_engine
from .exceptions import (
    CaseNotFound,
    DuplicateCase,
    EvidenceRequired,
    GateAuthorityError,
    HumanApprovalRequired,
    IllegalTransition,
    OwnershipError,
    ReviewRequired,
    SeparationOfDutiesError,
    TerminalState,
    WorkError,
)
from .gate import GATES, HUMAN_MANDATORY, Gate, get_gate
from .queue import WorkQueue
from .state_machine import Role, State

__all__ = [
    "open_work_engine",
    "WorkEngine",
    # core objects
    "Case",
    "KnowledgeRef",
    "Actor",
    "Decision",
    "ReviewRecord",
    "Evidence",
    "evidence",
    "Event",
    "EventLog",
    "WorkQueue",
    "Gate",
    "get_gate",
    "GATES",
    "HUMAN_MANDATORY",
    "replay",
    # enums / constants
    "State",
    "Role",
    "PASSED",
    "REJECTED",
    # exceptions
    "WorkError",
    "CaseNotFound",
    "DuplicateCase",
    "IllegalTransition",
    "TerminalState",
    "GateAuthorityError",
    "SeparationOfDutiesError",
    "HumanApprovalRequired",
    "EvidenceRequired",
    "ReviewRequired",
    "OwnershipError",
]
