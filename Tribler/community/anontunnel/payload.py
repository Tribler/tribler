from Tribler.dispersy.payload import Payload

__author__ = 'Chris'


#noinspection PyClassHasNoInit
class BaseMessage:
    pass


class PingMessage(BaseMessage):
    def __init__(self):
        pass


class PongMessage(BaseMessage):
    def __init__(self):
        pass


class CreateMessage(BaseMessage):
    def __init__(self, key=None):
        self.key = key


class CreatedMessage(BaseMessage):
    def __init__(self, candidate_list):
        self.key = None
        self.candidate_list = candidate_list


class ExtendMessage(BaseMessage):
    def __init__(self, extend_with):
        self.extend_with = extend_with
        self.key = None

    @property
    def host(self):
        return self.extend_with[0] if self.extend_with else None

    @property
    def port(self):
        return self.extend_with[1] if self.extend_with else None


class ExtendedMessage(BaseMessage):
    def __init__(self, key, candidate_list):
        self.key = key
        self.candidate_list = candidate_list


class DataMessage(BaseMessage):
    def __init__(self, destination, data, origin=None):
        self.destination = destination
        self.data = data
        self.origin = origin


class StatsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, stats):
            super(StatsPayload.Implementation, self).__init__(meta)
            self.stats = stats