from Tribler.dispersy.payload import Payload

class EffortRecordPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, first_timestamp, second_timestamp, history):
            assert isinstance(first_timestamp, float)
            assert isinstance(second_timestamp, float)
            super(EffortRecordPayload.Implementation, self).__init__(meta)
            self._first_timestamp = first_timestamp
            self._second_timestamp = second_timestamp
            self._history = history

        @property
        def first_timestamp(self):
            return self._first_timestamp

        @property
        def second_timestamp(self):
            return self._second_timestamp

        @property
        def history(self):
            return self._history
