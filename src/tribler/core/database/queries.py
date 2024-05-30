from __future__ import annotations

import re
from dataclasses import dataclass, field

fts_query_re = re.compile(r"\w+", re.UNICODE)


@dataclass
class Query:
    """
    A simple unpacking of a user query.
    """

    original_query: str
    tags: set[str] = field(default_factory=set)
    fts_text: str = ""


def to_fts_query(text: str | None) -> str | None:
    """
    Convert the given text to FTS-compatible text.
    """
    if not text:
        return None

    words = [f'"{w}"' for w in fts_query_re.findall(text) if w]
    if not words:
        return None

    return " ".join(words)
