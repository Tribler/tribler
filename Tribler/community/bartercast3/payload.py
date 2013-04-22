from Tribler.dispersy.payload import Payload

class BarterRecordPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cycle, effort, upload_first_to_second, upload_second_to_first, first_timestamp, second_timestamp, first_upload, first_download, second_upload, second_download):
            if __debug__:
                from .efforthistory import EffortHistory
            assert isinstance(cycle, int)
            assert isinstance(effort, EffortHistory)
            assert isinstance(upload_first_to_second, int)
            assert isinstance(upload_second_to_first, int)
            assert isinstance(first_timestamp, float)
            assert isinstance(second_timestamp, float)
            assert isinstance(first_upload, int)
            assert isinstance(first_download, int)
            assert isinstance(second_upload, int)
            assert isinstance(second_download, int)
            super(BarterRecordPayload.Implementation, self).__init__(meta)
            self.cycle = cycle
            self.effort = effort
            self.upload_first_to_second = upload_first_to_second
            self.upload_second_to_first = upload_second_to_first
            # the following parameters are used for debugging only
            self.first_timestamp = first_timestamp
            self.second_timestamp = second_timestamp
            self.first_upload = first_upload
            self.first_download = first_download
            self.second_upload = second_upload
            self.second_download = second_download

class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, member):
            super(PingPayload.Implementation, self).__init__(meta)
            self.identifier = identifier
            self.member = member

class PongPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, member):
            super(PongPayload.Implementation, self).__init__(meta)
            self.identifier = identifier
            self.member = member

class MemberRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier):
            super(MemberRequestPayload.Implementation, self).__init__(meta)
            self.identifier = identifier

class MemberResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier):
            super(MemberResponsePayload.Implementation, self).__init__(meta)
            self.identifier = identifier
