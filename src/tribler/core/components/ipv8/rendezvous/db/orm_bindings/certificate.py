import dataclasses
from typing import TYPE_CHECKING

from pony.orm import Required

if TYPE_CHECKING:
    @dataclasses.dataclass
    class PeerScore:
        public_key: bytes
        total: float
        count: int
        last_updated: int


def define_binding(db):
    class PeerScore(db.Entity):
        public_key = Required(bytes, index=True)
        total = Required(float)
        count = Required(int)
        last_updated = Required(int)

    return PeerScore
