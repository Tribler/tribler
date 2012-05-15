from Tribler.dispersy.payload import Payload

class BarterRecordPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, first_upload, second_upload):
            assert isinstance(first_upload, (int, long))
            assert isinstance(second_upload, (int, long))
            super(BarterRecordPayload.Implementation, self).__init__(meta)
            self._first_upload = first_upload
            self._second_upload = second_upload

        @property
        def first_upload(self):
            return self._first_upload

        @property
        def second_upload(self):
            return self._second_upload
