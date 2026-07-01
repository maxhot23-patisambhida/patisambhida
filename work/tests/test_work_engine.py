"""Real integration tests for the Work Engine.

No mocks, no fabricated data: this compiles Book 1 from the actual PDF into a
temporary Canonical Corpus Repository, opens the Office SDK over it, and drives
real Knowledge Cases over real knowledge objects through the full lifecycle —
asserting every permanent governance rule. Runnable directly
(``python work/tests/test_work_engine.py``) — exits non-zero on any failure —
and discoverable by pytest (the ``test_*`` function).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from compiler.parser.extract import thai_digit_to_int  # noqa: E402
from compiler.pipeline import compile_book  # noqa: E402
from office import open_office  # noqa: E402
from repository.manager import RepositoryManager  # noqa: E402
from work import (  # noqa: E402
    Actor,
    Case,
    Role,
    State,
    WorkEngine,
    evidence,
    open_work_engine,
)
from work.exceptions import (  # noqa: E402
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
)

CORPUS = "patisambhidamagga"
PDF_DIR = _ROOT / "web" / "pdf"


class Checker:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, cond: bool, msg: str) -> None:
        if cond:
            self.passed += 1
        else:
            self.failed += 1
            print(f"  FAIL: {msg}")

    def eq(self, a, b, msg: str) -> None:
        self.check(a == b, f"{msg} (got {a!r}, expected {b!r})")

    def raises(self, exc, fn, msg: str) -> None:
        try:
            fn()
            self.check(False, f"{msg} (no error raised)")
        except exc:
            self.check(True, msg)


def _pdf_for(number: int) -> Path:
    for pdf in PDF_DIR.glob("*.pdf"):
        if (thai_digit_to_int(pdf.stem) or 0) == number:
            return pdf
    raise FileNotFoundError(f"no PDF for book {number}")


def build_repository(root: Path) -> None:
    manager = RepositoryManager(root)
    doc = compile_book(_pdf_for(1), fallback_number=1)
    manager.create_book(CORPUS, doc, corpus_title="ปฏิสัมภิทามรรค")


def _engine(root: Path) -> WorkEngine:
    # deterministic logical clock — replay must not depend on wall time
    counter = iter(range(1_000_000))
    office = open_office(root)
    return open_work_engine(office=office, clock=lambda: f"T{next(counter):06d}")


# role bearers reused across checks
PRODUCER = Actor("alice", Role.PRODUCER)
CUSTODIAN = Actor("carl", Role.CUSTODIAN)
REVIEWER = Actor("rita", Role.REVIEWER)
GOVERNOR = Actor("dana", Role.GOVERNOR, is_human=True)
AI_GOVERNOR = Actor("bot", Role.GOVERNOR, is_human=False)


def _drive_to_integrated(eng: WorkEngine, case: Case) -> Case:
    eng.register(case.id, actor=CUSTODIAN, evidence=evidence.note("source in custody"))
    eng.begin_formation(case.id, actor=PRODUCER, evidence=evidence.note("forming from source"))
    eng.validate(case.id, actor=REVIEWER, evidence=evidence.note("fidelity verified"))
    return eng.integrate(case.id, actor=CUSTODIAN, evidence=evidence.note("relationships + citations"))


def run_checks(root: Path) -> Checker:
    c = Checker()
    eng = _engine(root)

    # the case carries a REAL knowledge object, read through the Office SDK
    ko = eng.office.knowledge.list_knowledge(1)[0]

    # ── creation grounded in the corpus (W1, W2, W3, W5) ──────────────────
    case = eng.create_case(ko.id, book_number=1, opened_by=PRODUCER, owner="office.compilation")
    c.check(isinstance(case, Case), "create_case returns a Case")
    c.eq(case.state, State.IDENTIFIED, "new case opens at ① Identified")
    c.eq(case.knowledge_ref.knowledge_id, ko.id, "W2 provenance binds the knowledge object")
    c.eq(case.knowledge_ref.name, ko.names.primary, "provenance carries the knowledge name")
    c.eq(case.owner, "office.compilation", "W3 owner set at creation")
    c.check(len(case.evidence) >= 1, "W5 birth evidence seeded from canonical citation")
    c.raises(OwnershipError, lambda: eng.create_case(ko.id, book_number=1, opened_by=PRODUCER, owner=""),
             "create_case refuses an orphaned (ownerless) case")
    c.raises(DuplicateCase, lambda: eng.create_case(ko.id, book_number=1, opened_by=PRODUCER,
                                                    owner="x"), "duplicate case id refused")
    c.raises(CaseNotFound, lambda: eng.load_case("KC-NOPE"), "load_case raises on unknown id")

    # ── evidence is mandatory at every gate (No transition without evidence) ─
    c.raises(EvidenceRequired,
             lambda: eng.register(case.id, actor=CUSTODIAN, evidence=None),
             "register without evidence is refused")

    # ── wrong authority is refused ────────────────────────────────────────
    c.raises(GateAuthorityError,
             lambda: eng.register(case.id, actor=PRODUCER, evidence=evidence.note("x")),
             "registration requires the Custodian role")

    # ── drive the canonical path to ⑤ Integrated ──────────────────────────
    case = _drive_to_integrated(eng, case)
    c.eq(case.state, State.INTEGRATED, "case reaches ⑤ Integrated via the canonical gates")
    c.check("alice" in case.producers, "the formation actor is recorded as a producer (for SoD)")

    # ── approval preconditions (review · human · separation of duties) ────
    c.raises(ReviewRequired,
             lambda: eng.approve(case.id, actor=GOVERNOR, evidence=evidence.note("x")),
             "approval is refused without a passing review")

    # a producer cannot review their own work (SoD)
    producer_as_reviewer = Actor("alice", Role.REVIEWER)
    c.raises(SeparationOfDutiesError,
             lambda: eng.record_review(case.id, reviewer=producer_as_reviewer,
                                       outcome="passed", criteria="x"),
             "producer cannot review own work (separation of duties)")

    eng.record_review(case.id, reviewer=REVIEWER, outcome="passed",
                      criteria="constitution + permanence test")

    # AI may operate but never holds a human-mandatory gate (W6)
    c.raises(HumanApprovalRequired,
             lambda: eng.approve(case.id, actor=AI_GOVERNOR, evidence=evidence.note("x")),
             "AI governor cannot hold the human-mandatory Approval gate")

    # the producer cannot approve their own work either
    producer_as_governor = Actor("alice", Role.GOVERNOR, is_human=True)
    c.raises(SeparationOfDutiesError,
             lambda: eng.approve(case.id, actor=producer_as_governor, evidence=evidence.note("x")),
             "producer cannot approve own work (separation of duties)")

    # ── approve → publish (the two human gates) ───────────────────────────
    case = eng.approve(case.id, actor=GOVERNOR, evidence=evidence.note("meets criteria"))
    c.eq(case.state, State.APPROVED, "Approval gate advances to ⑥ Approved")
    case = eng.publish(case.id, actor=GOVERNOR, evidence=evidence.note("released to active life"))
    c.eq(case.state, State.PUBLISHED, "Publication gate advances to ⑦ Published")
    c.check(any(d.gate == "approval" and d.outcome == "passed" for d in case.decisions),
            "an immutable Decision was emitted at the Approval gate")

    # ── illegal transition is refused (No silent transition) ──────────────
    c.raises(IllegalTransition,
             lambda: eng.validate(case.id, actor=REVIEWER, evidence=evidence.note("x")),
             "a gate that does not apply to the current state is refused")

    # ── retirement: the human-gated universal exit; then terminal & frozen ─
    case = eng.retire(case.id, actor=GOVERNOR, evidence=evidence.note("end of active life"))
    c.eq(case.state, State.RETIRED, "Retirement gate reaches ⑩ Retired & Archived")
    c.check(case.is_terminal, "retired case is terminal")
    c.raises(TerminalState,
             lambda: eng.retire(case.id, actor=GOVERNOR, evidence=evidence.note("x")),
             "a retired case never transitions again (Retirement Invariant)")

    # ── append-only & deterministic replay ────────────────────────────────
    history = eng.history(case.id)
    c.check(len(history) >= 9, "every action left an event (append-only history)")
    c.check([e.seq for e in history] == sorted(e.seq for e in history), "events are ordered by seq")
    c.eq(eng.load_case(case.id).to_dict(), eng.load_case(case.id).to_dict(),
         "replay is deterministic — same events, same case")

    # ── rejection is a permanent decision, not a rewind ───────────────────
    case2 = eng.create_case(ko.id, book_number=1, opened_by=PRODUCER,
                            owner="office.compilation", case_id="KC-REJECT-DEMO")
    case2 = _drive_to_integrated(eng, case2)
    before = case2.state
    case2 = eng.reject(case2.id, "approval", actor=GOVERNOR,
                       rationale="insufficient cross-references")
    c.eq(case2.state, before, "a rejection does not change state (no rewind, no delete)")
    c.check(any(d.outcome == "rejected" for d in case2.decisions),
            "the rejection is recorded as a permanent Decision")
    c.raises(EvidenceRequired,
             lambda: eng.reject(case2.id, "approval", actor=GOVERNOR, rationale=""),
             "a rejection must state a rationale")

    # ── ownership: assign / transfer, never orphaned (W3) ─────────────────
    case2 = eng.assign_case(case2.id, "office.review", by=CUSTODIAN)
    c.eq(case2.owner, "office.review", "assign_case changes the accountable owner")
    case2 = eng.transfer_case(case2.id, "office.governance", by=CUSTODIAN)
    c.eq(case2.owner, "office.governance", "transfer_case moves ownership")
    c.raises(OwnershipError, lambda: eng.assign_case(case2.id, "", by=CUSTODIAN),
             "ownership can never be emptied on an open case")

    # ── queues: resting views over open cases ─────────────────────────────
    q = eng.queue()
    c.check("KC-REJECT-DEMO" in [x.id for x in q.inbox("office.governance")],
            "queue.inbox lists open cases by owner")
    c.check(case.id not in [x.id for x in q.open_cases()],
            "a retired case is no longer in the open queue")
    c.check(isinstance(q.backlog(), dict) and sum(q.backlog().values()) == len(q.open_cases()),
            "backlog counts every open case exactly once")

    # ── boundary: the engine reads only through the Office SDK ─────────────
    import work as work_pkg
    pkg_dir = Path(work_pkg.__file__).resolve().parent
    leak = []
    for src in pkg_dir.glob("*.py"):
        code = "\n".join(ln.split("#", 1)[0] for ln in src.read_text(encoding="utf-8").splitlines())
        if "import repository" in code or "from repository" in code:
            leak.append(src.name + " (repository)")
        if "import json" in code or "from query" in code or ".loader" in code:
            leak.append(src.name + " (json/query/loader)")
    c.eq(leak, [], "Work Engine imports no Repository, no Query Engine, no JSON parser")

    return c


def test_work_engine() -> None:
    """pytest entry point — builds a real repo in a temp dir and drives real cases."""
    tmp = Path(tempfile.mkdtemp(prefix="kos-work-test-"))
    try:
        build_repository(tmp)
        checker = run_checks(tmp)
        assert checker.failed == 0, f"{checker.failed} work-engine checks failed"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="kos-work-test-"))
    try:
        print("Building real repository (Book 1) ...")
        build_repository(tmp)
        checker = run_checks(tmp)
        print(f"\n{checker.passed} passed, {checker.failed} failed")
        return 0 if checker.failed == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
