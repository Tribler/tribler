import logging

from tick import Tick, MessageId


class Portfolio(object):
    def __init__(self):
        super(Portfolio, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._ticks = {}

    def add_tick(self, tick):
        assert isinstance(tick, Tick), type(tick)
        self._ticks[tick.message_id] = tick

    def find_tick(self, message_id):
        assert isinstance(message_id, MessageId), type(message_id)
        self._ticks.get(message_id)

    def delete_tick_by_id(self, message_id):
        assert isinstance(message_id, MessageId), type(message_id)
        del self._ticks[message_id]
