from __future__ import absolute_import

import random
import time


class Base(object):
    def __init__(self):
        self.bytes_up = random.randint(0, 1024**3)
        self.bytes_down = random.randint(0, 1024**3)

    def to_dictionary(self):
        return {"bytes_up": self.bytes_up, "bytes_down": self.bytes_down, "creation_time": time.time()}


class Circuit(Base):
    def __init__(self):
        super(Circuit, self).__init__()
        self.circuit_id = random.getrandbits(32)
        self.goal_hops = random.randint(1, 3)
        self.actual_hops = random.randint(0, self.goal_hops)
        self.type = random.choice(['DATA', 'IP', 'RP', 'RENDEZVOUS'])
        self.state = random.choice(['READY', 'EXTENDING', 'TO_BE_EXTENDED', 'CLOSING'])

    def to_dictionary(self):
        result = super(Circuit, self).to_dictionary()
        result.update({"circuit_id": self.circuit_id, "goal_hops": self.goal_hops,
                       "actual_hops": self.actual_hops, "type": self.type, "state": self.state,
                       "unverified_hop": ""})
        return result


class Relay(Base):
    def __init__(self):
        super(Relay, self).__init__()
        self.circuit_from = random.getrandbits(32)
        self.circuit_to = random.getrandbits(32)
        self.is_rendezvous = random.choice([True, False])

    def to_dictionary(self):
        result = super(Relay, self).to_dictionary()
        result.update({"circuit_from": self.circuit_from, "circuit_to": self.circuit_to,
                       "is_rendezvous": self.is_rendezvous})
        return result


class Exit(Base):
    def __init__(self):
        super(Exit, self).__init__()
        self.circuit_from = random.getrandbits(32)
        self.enabled = random.choice([True, False])

    def to_dictionary(self):
        result = super(Exit, self).to_dictionary()
        result.update({"circuit_from": self.circuit_from, "enabled": self.enabled})
        return result
