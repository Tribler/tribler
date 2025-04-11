from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pony.orm import Database, Required

if TYPE_CHECKING:
    import dataclasses
    from collections.abc import Iterator


    class IterRendezvousCertificate(type):  # noqa: D101

        def __iter__(cls) -> Iterator[RendezvousCertificate]: ...  # noqa: D105


    @dataclasses.dataclass
    class RendezvousCertificate(metaclass=IterRendezvousCertificate):
        """
        The database type for rendezvous certificates.
        """

        public_key: bytes
        ip: bytes
        port: int
        ping: float
        start: float
        stop: float

        def __init__(self, public_key: bytes, ip: bytes, port: int, ping: float,  # noqa: D107
                     start: float, stop: float) -> None: ...

        @classmethod
        def select_random(cls: type[Self], limit: int) -> list[RendezvousCertificate]: ...  # noqa: D102


def define_binding(db: Database) -> type[RendezvousCertificate]:
    """
    Define the certificate binding for the given database.
    """
    class RendezvousCertificate(db.Entity):
        public_key = Required(bytes, index=True)
        ip = Required(bytes)
        port = Required(int)
        ping = Required(float)
        start = Required(float)
        stop = Required(float)

    return RendezvousCertificate
