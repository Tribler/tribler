from Tribler.dispersy.message import Packet
from Tribler.dispersy.payload import Payload


class ChannelPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, name, description):
            assert isinstance(name, unicode)
            assert len(name) < 256
            assert isinstance(description, unicode)
            assert len(description) < 1024
            super(ChannelPayload.Implementation, self).__init__(meta)
            self._name = name
            self._description = description

        @property
        def name(self):
            return self._name

        @property
        def description(self):
            return self._description


class PlaylistPayload(ChannelPayload):
    pass


class TorrentPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, infohash, timestamp, name, files, trackers):
            assert isinstance(infohash, str), 'infohash is a %s' % type(infohash)
            assert len(infohash) == 20, 'infohash has length %d' % len(infohash)
            assert isinstance(timestamp, (int, long))

            assert isinstance(name, unicode)
            assert isinstance(files, tuple)
            for path, length in files:
                assert isinstance(path, unicode)
                assert isinstance(length, (int, long))

            assert isinstance(trackers, tuple)
            for tracker in trackers:
                assert isinstance(tracker, str), 'tracker is a %s' % type(tracker)

            super(TorrentPayload.Implementation, self).__init__(meta)
            self._infohash = infohash
            self._timestamp = timestamp
            self._name = name
            self._files = files
            self._trackers = trackers

        @property
        def infohash(self):
            return self._infohash

        @property
        def timestamp(self):
            return self._timestamp

        @property
        def name(self):
            return self._name

        @property
        def files(self):
            return self._files

        @property
        def trackers(self):
            return self._trackers


class CommentPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, text, timestamp, reply_to_mid, reply_to_global_time, reply_after_mid,
                     reply_after_global_time, playlist_packet, infohash):
            assert isinstance(text, unicode)
            assert len(text) < 1024
            assert isinstance(timestamp, (int, long))

            assert not reply_to_mid or isinstance(reply_to_mid, str), 'reply_to_mid is a %s' % type(reply_to_mid)
            assert not reply_to_mid or len(reply_to_mid) == 20, 'reply_to_mid has length %d' % len(reply_to_mid)
            assert not reply_to_global_time or isinstance(reply_to_global_time, (
                int, long)), 'reply_to_global_time is a %s' % type(reply_to_global_time)

            assert not reply_after_mid or isinstance(
                reply_after_mid, str), 'reply_after_mid is a %s' % type(reply_after_mid)
            assert not reply_after_mid or len(
                reply_after_mid) == 20, 'reply_after_mid has length %d' % len(reply_after_global_time)
            assert not reply_after_global_time or isinstance(reply_after_global_time, (
                int, long)), 'reply_after_global_time is a %s' % type(reply_to_global_time)

            assert not playlist_packet or isinstance(playlist_packet, Packet)

            assert not infohash or isinstance(infohash, str), 'infohash is a %s' % type(infohash)
            assert not infohash or len(infohash) == 20, 'infohash has length %d' % len(infohash)

            super(CommentPayload.Implementation, self).__init__(meta)
            self._text = text
            self._timestamp = timestamp
            self._reply_to_mid = reply_to_mid
            self._reply_to_global_time = reply_to_global_time

            self._reply_after_mid = reply_after_mid
            self._reply_after_global_time = reply_after_global_time

            self._playlist_packet = playlist_packet
            self._infohash = infohash

        @property
        def text(self):
            return self._text

        @property
        def timestamp(self):
            return self._timestamp

        @property
        def reply_to_mid(self):
            return self._reply_to_mid

        @property
        def reply_to_global_time(self):
            return self._reply_to_global_time

        @property
        def reply_after_mid(self):
            return self._reply_after_mid

        @property
        def reply_after_global_time(self):
            return self._reply_after_global_time

        @property
        def playlist_packet(self):
            return self._playlist_packet

        @property
        def infohash(self):
            return self._infohash


class ModerationPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, text, timestamp, severity, causepacket):

            assert isinstance(causepacket, Packet)

            assert isinstance(text, unicode)
            assert len(text) < 1024
            assert isinstance(timestamp, (int, long))
            assert isinstance(severity, (int, long))

            super(ModerationPayload.Implementation, self).__init__(meta)
            self._text = text
            self._timestamp = timestamp
            self._severity = severity
            self._causepacket = causepacket

            message = causepacket.load_message()
            self._mid = message.authentication.member.mid
            self._global_time = message.distribution.global_time

        @property
        def text(self):
            return self._text

        @property
        def timestamp(self):
            return self._timestamp

        @property
        def severity(self):
            return self._severity

        @property
        def causepacket(self):
            return self._causepacket

        @property
        def cause_mid(self):
            return self._mid

        @property
        def cause_global_time(self):
            return self._global_time


class MarkTorrentPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, infohash, type_str, timestamp):
            assert isinstance(infohash, str), 'infohash is a %s' % type(infohash)
            assert len(infohash) == 20, 'infohash has length %d' % len(infohash)

            assert isinstance(type_str, unicode)
            assert len(type_str) < 25
            assert isinstance(timestamp, (int, long))

            super(MarkTorrentPayload.Implementation, self).__init__(meta)
            self._infohash = infohash
            self._type = type_str
            self._timestamp = timestamp

        @property
        def infohash(self):
            return self._infohash

        @property
        def type(self):
            return self._type

        @property
        def timestamp(self):
            return self._timestamp


class ModificationPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, modification_type, modification_value, timestamp, modification_on, prev_modification_packet, prev_modification_mid, prev_modification_global_time):
            assert isinstance(modification_type, unicode)
            assert modification_value is not None
            assert isinstance(modification_value, unicode)
            assert len(modification_value) < 1024
            assert isinstance(modification_on, Packet)

            assert not prev_modification_packet or isinstance(prev_modification_packet, Packet)
            assert not prev_modification_mid or isinstance(
                prev_modification_mid, str), 'prev_modification_mid is a %s' % type(prev_modification_mid)
            assert not prev_modification_mid or len(
                prev_modification_mid) == 20, 'prev_modification_mid has length %d' % len(prev_modification_mid)
            assert not prev_modification_global_time or isinstance(prev_modification_global_time, (
                int, long)), 'prev_modification_global_time is a %s' % type(prev_modification_global_time)

            super(ModificationPayload.Implementation, self).__init__(meta)
            self._modification_type = modification_type
            self._modification_value = modification_value
            self._timestamp = timestamp

            self._modification_on = modification_on

            self._prev_modification_packet = prev_modification_packet
            self._prev_modification_mid = prev_modification_mid
            self._prev_modification_global_time = prev_modification_global_time

        @property
        def modification_type(self):
            return self._modification_type

        @property
        def modification_value(self):
            return self._modification_value

        @property
        def timestamp(self):
            return self._timestamp

        @property
        def modification_on(self):
            return self._modification_on

        @property
        def prev_modification_packet(self):
            return self._prev_modification_packet

        @property
        def prev_modification_id(self):
            if self._prev_modification_mid and self._prev_modification_global_time:
                return "%s@%d" % (self._prev_modification_mid, self._prev_modification_global_time)

        @property
        def prev_modification_mid(self):
            return self._prev_modification_mid

        @property
        def prev_modification_global_time(self):
            return self._prev_modification_global_time


class PlaylistTorrentPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, infohash, playlist):
            assert isinstance(infohash, str), 'infohash is a %s' % type(infohash)
            assert len(infohash) == 20, 'infohash has length %d' % len(infohash)
            assert isinstance(playlist, Packet), type(playlist)
            super(PlaylistTorrentPayload.Implementation, self).__init__(meta)
            self._infohash = infohash
            self._playlist = playlist

        @property
        def infohash(self):
            return self._infohash

        @property
        def playlist(self):
            return self._playlist


class MissingChannelPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, includeSnapshot=False):
            assert isinstance(includeSnapshot, bool), 'includeSnapshot is a %s' % type(includeSnapshot)
            super(MissingChannelPayload.Implementation, self).__init__(meta)

            self._includeSnapshot = includeSnapshot

        @property
        def includeSnapshot(self):
            return self._includeSnapshot
