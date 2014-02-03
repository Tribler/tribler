__author__ = 'Chris'

from time import time

from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME


class RelayRoute(object):
    def __init__(self, circuit_id, candidate):
        self.candidate = candidate
        self.circuit_id = circuit_id

        self.timestamp = None

        self.times = []
        self.bytes_list = []
        self.bytes = [0, 0]
        self.speed = 0

        self.online = False

        self.last_incomming = time()

    @property
    def ping_time_remaining(self):
        too_old = time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incomming - too_old
        return diff if diff > 0 else 0