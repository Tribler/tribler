from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReportedError:
    type: str
    text: str
    event: dict = field(repr=False)
    additional_information: dict = field(default_factory=lambda: {}, repr=False)

    long_text: str = field(default='', repr=False)
    context: str = field(default='', repr=False)
    last_core_output: str = field(default='', repr=False)
    should_stop: Optional[bool] = field(default=None)
