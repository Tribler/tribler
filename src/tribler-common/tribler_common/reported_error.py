from dataclasses import dataclass
from typing import Optional


@dataclass
class ReportedError:
    type: str
    text: str
    event: dict

    long_text: str = ''
    context: str = ''
    should_stop: Optional[bool] = None
    requires_user_consent: bool = True
