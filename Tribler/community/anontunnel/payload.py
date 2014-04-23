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
    def __init__(self, key="\0"*336, public_key=""):
        assert isinstance(key, basestring)
        assert isinstance(public_key, basestring)

        self.key = key
        self.public_key = public_key


class CreatedMessage(BaseMessage):
    def __init__(self, candidate_list, reply_to=None):
        # Assert candidate_list is a list and that all items are strings
        assert all(isinstance(key, basestring) for key in candidate_list)
        assert reply_to is None or isinstance(reply_to, CreateMessage)

        self.key = ""
        self.candidate_list = candidate_list
        self.reply_to = reply_to


class ExtendMessage(BaseMessage):
    def __init__(self, extend_with):
        assert extend_with is None or isinstance(extend_with, basestring)

        self.extend_with = extend_with
        self.key = ""


class ExtendedMessage(BaseMessage):
    def __init__(self, key, candidate_list):
        assert isinstance(key, basestring)
        assert all(isinstance(key, basestring) for key in candidate_list)

        self.key = key
        self.candidate_list = candidate_list


class DataMessage(BaseMessage):
    def __init__(self, destination, data, origin=None):
        assert isinstance(destination[0], basestring) and isinstance(destination[1], int)
        assert isinstance(data, basestring)
        assert origin is None or isinstance(origin[0], basestring) and isinstance(origin[1], int)

        self.destination = destination
        self.data = data
        self.origin = origin


class StatsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, stats):
            super(StatsPayload.Implementation, self).__init__(meta)
            self.stats = stats