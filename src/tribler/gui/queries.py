import re
from dataclasses import dataclass, field
from typing import Set

fts_query_re = re.compile(r'\w+', re.UNICODE)


@dataclass
class Query:
    original_query: str
    tags: Set[str] = field(default_factory=set)
    fts_text: str = ''


def to_fts_query(text):
    if not text:
        return None

    words = [f'"{w}"' for w in fts_query_re.findall(text) if w]
    if not words:
        return None

    return ' '.join(words)
