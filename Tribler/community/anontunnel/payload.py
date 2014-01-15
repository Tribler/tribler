import struct

from Tribler.dispersy.payload import Payload
from Tribler.Core.Utilities.encoding import decode, encode

__author__ = 'Chris'

class BreakMessage:
    pass

class PingMessage:
    pass

class PongMessage:
    pass

class CreateMessage:
    def __init__(self, key):
        self.key = key

class CreatedMessage:
    def __init__(self, key, candidate_list):
        self.key = key
        self.candidate_list = candidate_list

class ExtendMessage:
    def __init__(self, extend_with, key):
        self.extend_with = extend_with
        self.key = key
    
    @property
    def host(self):
        return self.extend_with[0] if self.extend_with else None

    @property
    def port(self):
        return self.extend_with[1] if self.extend_with else None

class ExtendedMessage:
    def __init__(self, key, candidate_list):
        self.key = key
        self.candidate_list = candidate_list

class PunctureMessage:
    def __init__(self, sock_addr):
        self.sock_addr = sock_addr

class DataMessage:
    def __init__(self, destination, data, origin=None):
        self.destination = destination
        self.data = data
        self.origin = origin

class StatsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, stats):
            super(StatsPayload.Implementation, self).__init__(meta)
            self.stats = stats