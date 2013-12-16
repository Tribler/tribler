import struct

from Tribler.dispersy.payload import Payload
from Tribler.Core.Utilities.encoding import decode, encode

__author__ = 'Chris'

class CreateMessage:
    pass


class BreakMessage:
    pass


class PingMessage:
    pass

class PongMessage:
    pass

class CreatedMessage:
    pass


class ExtendMessage:
    def __init__(self, extend_with):
        self.extend_with = extend_with
    
    @property
    def host(self):
        return self.extend_with[0] if self.extend_with else None

    @property
    def port(self):
        return self.extend_with[1] if self.extend_with else None

class PunctureMessage:
    def __init__(self, sock_addr):
        self.sock_addr = sock_addr

class ExtendedWithMessage:
    def __init__(self, extended_with):
        self.extended_with = extended_with
    
    @property
    def host(self):
        return self.extended_with[0]

    @property
    def port(self):
        return self.extended_with[1]

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