from Tribler.dispersy.payload import Payload
from Tribler.dispersy.revision import update_revision_information

# update version information directly from SVN
update_revision_information("$HeadURL$", "$Revision$")

class EffortRecordPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, first_timestamp, second_timestamp, history, first_up, first_down, second_up, second_down):
            assert isinstance(first_timestamp, float)
            assert isinstance(second_timestamp, float)
            assert isinstance(first_up, int)
            assert isinstance(first_down, int)
            assert isinstance(second_up, int)
            assert isinstance(second_down, int)
            super(EffortRecordPayload.Implementation, self).__init__(meta)
            self._first_timestamp = first_timestamp
            self._second_timestamp = second_timestamp
            self._history = history
            self.first_up = first_up
            self.first_down = first_down
            self.second_up = second_up
            self.second_down = second_down

        @property
        def first_timestamp(self):
            return self._first_timestamp

        @property
        def second_timestamp(self):
            return self._second_timestamp

        @property
        def history(self):
            return self._history

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

class DebugRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, source_address, members):
            """ Ask some predefined questions and the localy determined online time for MEMBERS """
            assert isinstance(source_address, tuple)
            assert isinstance(members, list)
            assert all(isinstance(mid, str) for mid in members)
            super(DebugRequestPayload.Implementation, self).__init__(meta)
            self.source_address = source_address
            self.members = members

class DebugResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, revision, now, observations, records, views):
            """ Answer some predefined questions and the localy determined online time for MEMBERS """
            assert isinstance(revision, int)
            assert isinstance(now, float)
            assert isinstance(observations, int)
            assert isinstance(records, int)
            assert isinstance(views, dict)
            assert all(isinstance(mid, str) and isinstance(view, tuple) and len(view) == 2 for mid, view in views.iteritems())
            super(DebugResponsePayload.Implementation, self).__init__(meta)
            self.revision = revision
            self.now = now
            self.observations = observations
            self.records = records
            self.views = views
