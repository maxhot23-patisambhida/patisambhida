"""Evidence (W5) — the bridge between Knowledge and Governance.

Every action a case takes accumulates Evidence linking it to its justification
and to its sources (ADR-002 W5; KOS-001 ภาค ๕). No transition is legitimate
without it. Evidence here is a small, immutable reference object — it points at
*where the justification lives* (a citation in the canonical corpus, a review
record, a prior event) rather than copying knowledge into the work layer.
"""

from __future__ import annotations

from dataclasses import dataclass


# Evidence kinds the first engine understands.
CITATION = "citation"      # points at a canonical Citation id (provenance from the corpus)
KNOWLEDGE = "knowledge"    # points at a Knowledge Object id this case carries
REVIEW = "review"          # points at a Review Record emitted by a reviewer
DOCUMENT = "document"      # an external justification reference (URL/id), opaque to the engine
NOTE = "note"              # a recorded human rationale with no external referent


@dataclass(frozen=True)
class Evidence:
    """An immutable justification reference attached to a case action."""
    kind: str
    ref: str           # the identifier this evidence points at (citation id, knowledge id, …)
    note: str = ""     # short human-readable justification

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("evidence.kind is required")
        if not self.ref and self.kind != NOTE:
            raise ValueError(f"evidence of kind {self.kind!r} requires a ref")

    def to_dict(self) -> dict:
        return {"kind": self.kind, "ref": self.ref, "note": self.note}


def citation(citation_id: str, note: str = "") -> Evidence:
    """Evidence grounded in a canonical Citation (the strongest, source-anchored kind)."""
    return Evidence(kind=CITATION, ref=citation_id, note=note)


def knowledge(knowledge_id: str, note: str = "") -> Evidence:
    return Evidence(kind=KNOWLEDGE, ref=knowledge_id, note=note)


def note(text: str) -> Evidence:
    return Evidence(kind=NOTE, ref="", note=text)
