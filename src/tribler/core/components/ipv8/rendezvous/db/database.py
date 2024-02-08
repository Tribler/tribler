from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Union, Optional

from ipv8.peer import Peer
from pony.orm import Database, db_session, select

from tribler.core.components.ipv8.rendezvous.db.orm_bindings import certificate
from tribler.core.utilities.utilities import MEMORY_DB

if TYPE_CHECKING:
    from tribler.core.components.ipv8.rendezvous.db.orm_bindings.certificate import PeerScore


class RendezvousDatabase:

    @property
    def current_time(self) -> float:
        return time.time()

    def __init__(self, db_path: Union[Path, type(MEMORY_DB)], decay_coefficient: float,
                 decay_granularity: float, stale_timeout: float) -> None:
        create_db = db_path is MEMORY_DB or not db_path.is_file()
        db_path_string = ":memory:" if db_path is MEMORY_DB else str(db_path)

        self.decay_coefficient = decay_coefficient
        self.decay_granularity = decay_granularity
        self.stale_timeout = stale_timeout

        self.database = Database()
        self.PeerScore = certificate.define_binding(self.database)
        self.database.bind(provider='sqlite', filename=db_path_string, create_db=create_db, timeout=120.0)
        self.database.generate_mapping(create_tables=create_db)

    def calculate_decay(self, last_updated_time: float) -> float:
        if last_updated_time > self.current_time:
            logging.exception("RendezvousDatabase corrupted. Clock is set to the past.")
            return 0
        time_passed = (self.current_time - last_updated_time) / self.decay_granularity
        return math.exp(- time_passed * self.decay_coefficient)

    def add(self, peer: Peer, start_timestamp: float, stop_timestamp: float) -> None:
        with (db_session(immediate=True)):
            peer_score = self.PeerScore.get(public_key=peer.public_key.key_to_bin())
            duration = stop_timestamp - start_timestamp
            if peer_score:
                decay_coef = self.calculate_decay(peer_score.last_updated)
                peer_score.total = decay_coef * peer_score.total + duration
                peer_score.count = 1 if decay_coef == 0 else peer_score.count + 1
                peer_score.last_updated = self.current_time
            else:
                self.PeerScore(public_key=peer.public_key.key_to_bin(), total=duration, count=1,
                               last_updated=self.current_time)

    def get(self, peer: Peer) -> Optional[PeerScore]:
        with db_session(immediate=True):
            peer_score = self.PeerScore.get(public_key=peer.public_key.key_to_bin())
            if peer_score:
                if self.current_time - peer_score.last_updated > self.stale_timeout:
                    # Decay and update the peer_score
                    decay_coef = self.calculate_decay(peer_score.last_updated)
                    peer_score.total *= decay_coef
                    peer_score.count = 1 if decay_coef == 0 else peer_score.count
                    peer_score.last_updated = self.current_time
            return peer_score

    def shutdown(self) -> None:
        self.database.disconnect()
