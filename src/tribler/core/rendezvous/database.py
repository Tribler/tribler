from __future__ import annotations

import socket
from pathlib import Path
from typing import TYPE_CHECKING

from ipv8.messaging.interfaces.udp.endpoint import UDPv6Address
from pony.orm import Database, db_session, select

from tribler.core.rendezvous.orm_bindings import certificate

if TYPE_CHECKING:
    from os import PathLike

    from ipv8.peer import Peer

    from tribler.core.rendezvous.orm_bindings.certificate import RendezvousCertificate


class RendezvousDatabase:
    """
    The database to keep track of rendezvous info.
    """

    def __init__(self, db_path: PathLike) -> None:
        """
        Create a new database.
        """
        create_db = db_path == ":memory:" or not Path(db_path).exists()
        db_path_string = ":memory:" if db_path == ":memory:" else str(db_path)

        self.database = Database()
        self.Certificate = certificate.define_binding(self.database)
        self.database.bind(provider="sqlite", filename=db_path_string, create_db=create_db, timeout=120.0)
        self.database.generate_mapping(create_tables=create_db)

    def add(self, peer: Peer, start_timestamp: float, stop_timestamp: float) -> None:
        """
        Write a peer's session time to the database.
        """
        with db_session(immediate=True):
            address = peer.address
            family = socket.AF_INET6 if isinstance(address, UDPv6Address) else socket.AF_INET
            self.Certificate(public_key=peer.public_key.key_to_bin(),
                             ip=socket.inet_pton(family, address[0]),
                             port=address[1],
                             ping=peer.get_median_ping() or -1.0,
                             start=start_timestamp,
                             stop=stop_timestamp)

    def get(self, peer: Peer) -> list[RendezvousCertificate]:
        """
        Get the certificates for the given peer.
        """
        with db_session():
            return select(certificate for certificate in self.Certificate
                          if certificate.public_key == peer.public_key.key_to_bin()).fetch()

    def random(self) -> RendezvousCertificate | None:
        """
        Get a random certificate.
        """
        with db_session():
            results = self.Certificate.select_random(limit=1)
            if not results:
                return None
            return results[0]

    def shutdown(self) -> None:
        """
        Disconnect from the database.
        """
        self.database.disconnect()
