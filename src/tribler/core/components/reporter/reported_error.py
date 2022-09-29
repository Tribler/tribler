from dataclasses import dataclass
from typing import Optional


@dataclass
class ReportedError:
    type: str
    text: str
    event: dict

    long_text: str = ''
    context: str = ''
    last_core_output: str = ''
    should_stop: Optional[bool] = None
