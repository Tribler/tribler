from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Union

from pony.orm import Database, db_session, select

from ipv8.peer import Peer
from tribler.core.components.ipv8.rendezvous.db.orm_bindings import certificate
from tribler.core.utilities.utilities import MEMORY_DB

if TYPE_CHECKING:
    from tribler.core.components.ipv8.rendezvous.db.orm_bindings.certificate import RendezvousCertificate


class RendezvousDatabase:

    def __init__(self, db_path: Union[Path, type(MEMORY_DB)]) -> None:
        create_db = db_path is MEMORY_DB or not db_path.is_file()
        db_path_string = ":memory:" if db_path is MEMORY_DB else str(db_path)

        self.database = Database()
        self.Certificate = certificate.define_binding(self.database)
        self.database.bind(provider='sqlite', filename=db_path_string, create_db=create_db, timeout=120.0)
        self.database.generate_mapping(create_tables=create_db)

    def add(self, peer: Peer, start_timestamp: float, stop_timestamp: float) -> None:
        with db_session(immediate=True):
            self.Certificate(public_key=peer.public_key.key_to_bin(),
                             start=start_timestamp,
                             stop=stop_timestamp)

    def get(self, peer: Peer) -> list[RendezvousCertificate]:
        with db_session():
            return select(certificate for certificate in self.Certificate
                          if certificate.public_key == peer.public_key.key_to_bin()).fetch()

    def shutdown(self) -> None:
        self.database.disconnect()
