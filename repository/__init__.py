"""Canonical Corpus Repository — Production Sprint 002.

The permanent storage layer between the Compiler and every future consumer.

    PDF -> Corpus Registration -> Compiler -> Canonical Corpus Repository -> consumers

The Repository is canonical; everything else is projection. It is technology
independent, deterministic, and append-only (version history). Consumers
(website, dashboard, runtime, AI offices, API) MUST read through ``loader.py``
and never touch the JSON files directly.
"""

from .schema import REPOSITORY_VERSION  # noqa: F401
from .loader import RepositoryLoader  # noqa: F401
from .manager import RepositoryManager  # noqa: F401
from .validator import validate_book, validate_repository  # noqa: F401
