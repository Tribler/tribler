import zlib
from random import sample
from struct import pack, unpack_from

from Tribler.community.basecommunity import BaseConversion
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.dispersy.message import (BatchConfiguration, DropPacket, Packet, DelayPacketByMissingMessage,
                                      DelayPacketByMissingMember, Message)
from Tribler.dispersy.payload import Payload
from Tribler.dispersy.resolution import LinearResolution, PublicResolution, DynamicResolution

"""Backward compatibility for Channel.

    Usage:
        1. Create ChannelCompatibility(newcommunity)
        2. Register compatibility.deprecated_meta_messages()
        3. Register ChannelConversion

"""

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

DEBUG = False


class ChannelConversion(BaseConversion):

    def __init__(self, community):
        super(ChannelConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"channel"),
                                 self._encode_channel,
                                 self._decode_channel)
        self.define_meta_message(chr(2), community.get_meta_message(u"torrent"),
                                 self._encode_torrent,
                                 self._decode_torrent)
        self.define_meta_message(chr(3), community.get_meta_message(u"playlist"),
                                 self._encode_playlist,
                                 self._decode_playlist)
        self.define_meta_message(chr(4), community.get_meta_message(u"comment"),
                                 self._encode_comment,
                                 self._decode_comment)
        self.define_meta_message(chr(5),
                                 community.get_meta_message(u"modification"),
                                 self._encode_modification,
                                 self._decode_modification)
        self.define_meta_message(chr(6),
                                 community.get_meta_message(u"playlist_torrent"),
                                 self._encode_playlist_torrent,
                                 self._decode_playlist_torrent)
        self.define_meta_message(chr(7),
                                 community.get_meta_message(u"missing-channel"),
                                 self._encode_missing_channel,
                                 self._decode_missing_channel)
        self.define_meta_message(chr(8),
                                 community.get_meta_message(u"moderation"),
                                 self._encode_moderation,
                                 self._decode_moderation)
        self.define_meta_message(chr(9), community.get_meta_message(u"mark_torrent"),
                                 self._encode_mark_torrent,
                                 self._decode_mark_torrent)

    def _encode_channel(self, message):
        return encode((message.payload.name, message.payload.description)),

    def _decode_channel(self, placeholder, offset, data):
        try:
            offset, values = decode(data, offset)
            if len(values) != 2:
                raise ValueError
        except ValueError:
            raise DropPacket("Unable to decode the channel-payload")

        name = values[0]
        if not (isinstance(name, unicode) and len(name) < 256):
            raise DropPacket("Invalid 'name' type or value")

        description = values[1]
        if not (isinstance(description, unicode) and len(description) < 1024):
            raise DropPacket("Invalid 'description' type or value")

        return offset, placeholder.meta.payload.implement(name, description)

    def _encode_playlist(self, message):
        return self._encode_channel(message)

    def _decode_playlist(self, placeholder, offset, data):
        return self._decode_channel(placeholder, offset, data)

    def _encode_torrent(self, message):
        max_len = self._community.dispersy_sync_bloom_filter_bits / 8

        files = message.payload.files
        trackers = message.payload.trackers

        def create_msg():
            normal_msg = (pack('!20sQ', message.payload.infohash, message.payload.timestamp), message.payload.name,
                          tuple(files), tuple(trackers))
            normal_msg = encode(normal_msg)
            return zlib.compress(normal_msg)

        compressed_msg = create_msg()
        while len(compressed_msg) > max_len:
            if len(trackers) > 10:
                # only use first 10 trackers, .torrents in the wild have been seen to have 1000+ trackers...
                trackers = trackers[:10]
            else:
                # reduce files by the amount we are currently to big
                reduce_by = max_len / (len(compressed_msg) * 1.0)
                nr_files_to_include = int(len(files) * reduce_by)
                files = sample(files, nr_files_to_include)

            compressed_msg = create_msg()
        return compressed_msg,

    def _decode_torrent(self, placeholder, offset, data):
        uncompressed_data = zlib.decompress(data[offset:])
        offset = len(data)

        try:
            _, values = decode(uncompressed_data)
        except ValueError:
            raise DropPacket("Unable to decode the torrent-payload")

        infohash_time, name, files, trackers = values
        if len(infohash_time) != 28:
            raise DropPacket("Unable to decode the torrent-payload, got %d bytes expected 28" % (len(infohash_time)))
        infohash, timestamp = unpack_from('!20sQ', infohash_time)

        if not isinstance(name, unicode):
            raise DropPacket("Invalid 'name' type")

        if not isinstance(files, tuple):
            raise DropPacket("Invalid 'files' type")

        if len(files) == 0:
            raise DropPacket("Should have at least one file")

        for file in files:
            if len(file) != 2:
                raise DropPacket("Invalid 'file_len' type")

            path, length = file
            if not isinstance(path, unicode):
                raise DropPacket("Invalid 'files_path' type is %s" % type(path))
            if not isinstance(length, (int, long)):
                raise DropPacket("Invalid 'files_length' type is %s" % type(length))

        if not isinstance(trackers, tuple):
            raise DropPacket("Invalid 'trackers' type")
        for tracker in trackers:
            if not isinstance(tracker, str):
                raise DropPacket("Invalid 'tracker' type")

        return offset, placeholder.meta.payload.implement(infohash, timestamp, name, files, trackers)

    def _encode_comment(self, message):
        dict = {"text": message.payload.text,
                "timestamp": message.payload.timestamp}

        playlist_packet = message.payload.playlist_packet
        infohash = message.payload.infohash

        if message.payload.reply_to_mid:
            dict["reply-to-mid"] = message.payload.reply_to_mid
            dict["reply-to-global-time"] = message.payload.reply_to_global_time

        if message.payload.reply_after_mid:
            dict["reply-after-mid"] = message.payload.reply_after_mid
            dict["reply-after-global-time"] = message.payload.reply_after_global_time

        if playlist_packet:
            message = playlist_packet.load_message()
            dict["playlist-mid"] = message.authentication.member.mid
            dict["playlist-global-time"] = message.distribution.global_time

        if infohash:
            dict['infohash'] = infohash
        return encode(dict),

    def _decode_comment(self, placeholder, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "text" in dic:
            raise DropPacket("Missing 'text'")
        text = dic["text"]
        if not (isinstance(text, unicode) and len(text) < 1024):
            raise DropPacket("Invalid 'text' type or value")

        if not "timestamp" in dic:
            raise DropPacket("Missing 'timestamp'")
        timestamp = dic["timestamp"]
        if not isinstance(timestamp, (int, long)):
            raise DropPacket("Invalid 'timestamp' type or value")

        reply_to_mid = dic.get("reply-to-mid", None)
        if reply_to_mid and not (isinstance(reply_to_mid, str) and len(reply_to_mid) == 20):
            raise DropPacket("Invalid 'reply-to-mid' type or value")

        reply_to_global_time = dic.get("reply-to-global-time", None)
        if reply_to_global_time and not isinstance(reply_to_global_time, (int, long)):
            raise DropPacket("Invalid 'reply-to-global-time' type")

        reply_after_mid = dic.get("reply-after-mid", None)
        if reply_after_mid and not (isinstance(reply_after_mid, str) and len(reply_after_mid) == 20):
            raise DropPacket("Invalid 'reply-after-mid' type or value")

        reply_after_global_time = dic.get("reply-after-global-time", None)
        if reply_after_global_time and not isinstance(reply_after_global_time, (int, long)):
            raise DropPacket("Invalid 'reply-after-global-time' type")

        playlist_mid = dic.get("playlist-mid", None)
        if playlist_mid and not (isinstance(playlist_mid, str) and len(playlist_mid) == 20):
            raise DropPacket("Invalid 'playlist-mid' type or value")

        playlist_global_time = dic.get("playlist-global-time", None)
        if playlist_global_time and not isinstance(playlist_global_time, (int, long)):
            raise DropPacket("Invalid 'playlist-global-time' type")

        if playlist_mid and playlist_global_time:
            try:
                packet_id, packet, message_name = self._get_message(playlist_global_time, playlist_mid)
                playlist = Packet(self._community.get_meta_message(message_name), packet, packet_id)
            except DropPacket:
                member = self._community.get_member(mid=playlist_mid)
                if not member:
                    raise DelayPacketByMissingMember(self._community, playlist_mid)
                raise DelayPacketByMissingMessage(self._community, member, playlist_global_time)
        else:
            playlist = None

        infohash = dic.get("infohash", None)
        if infohash and not (isinstance(infohash, str) and len(infohash) == 20):
            raise DropPacket("Invalid 'infohash' type or value")
        return offset, placeholder.meta.payload.implement(text, timestamp, reply_to_mid, reply_to_global_time, reply_after_mid, reply_after_global_time, playlist, infohash)

    def _encode_moderation(self, message):
        dict = {"text": message.payload.text,
                "timestamp": message.payload.timestamp,
                "severity": message.payload.severity}

        dict["cause-mid"] = message.payload.cause_mid
        dict["cause-global-time"] = message.payload.cause_global_time
        return encode(dict),

    def _decode_moderation(self, placeholder, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "text" in dic:
            raise DropPacket("Missing 'text'")
        text = dic["text"]
        if not (isinstance(text, unicode) and len(text) < 1024):
            raise DropPacket("Invalid 'text' type or value")

        if not "timestamp" in dic:
            raise DropPacket("Missing 'timestamp'")
        timestamp = dic["timestamp"]
        if not isinstance(timestamp, (int, long)):
            raise DropPacket("Invalid 'timestamp' type or value")

        if not "severity" in dic:
            raise DropPacket("Missing 'severity'")
        severity = dic["severity"]
        if not isinstance(severity, (int, long)):
            raise DropPacket("Invalid 'severity' type or value")

        cause_mid = dic.get("cause-mid", None)
        if not (isinstance(cause_mid, str) and len(cause_mid) == 20):
            raise DropPacket("Invalid 'cause-mid' type or value")

        cause_global_time = dic.get("cause-global-time", None)
        if not isinstance(cause_global_time, (int, long)):
            raise DropPacket("Invalid 'cause-global-time' type")

        try:
            packet_id, packet, message_name = self._get_message(cause_global_time, cause_mid)
            cause_packet = Packet(self._community.get_meta_message(message_name), packet, packet_id)

        except DropPacket:
            member = self._community.get_member(mid=cause_mid)
            if not member:
                raise DelayPacketByMissingMember(self._community, cause_mid)
            raise DelayPacketByMissingMessage(self._community, member, cause_global_time)

        return offset, placeholder.meta.payload.implement(text, timestamp, severity, cause_packet)

    def _encode_mark_torrent(self, message):
        dict = {"infohash": message.payload.infohash,
                "timestamp": message.payload.timestamp,
                "type": message.payload.type}

        return encode(dict),

    def _decode_mark_torrent(self, placeholder, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "infohash" in dic:
            raise DropPacket("Missing 'infohash'")
        infohash = dic["infohash"]
        if not (isinstance(infohash, str) and len(infohash) == 20):
            raise DropPacket("Invalid 'infohash' type or value")

        if not "timestamp" in dic:
            raise DropPacket("Missing 'timestamp'")
        timestamp = dic["timestamp"]
        if not isinstance(timestamp, (int, long)):
            raise DropPacket("Invalid 'timestamp' type or value")

        if not "type" in dic:
            raise DropPacket("Missing 'type'")
        type = dic["type"]
        if not (isinstance(type, unicode) and len(type) < 25):
            raise DropPacket("Invalid 'type' type or value")

        return offset, placeholder.meta.payload.implement(infohash, type, timestamp)

    def _encode_modification(self, message):
        modification_on = message.payload.modification_on.load_message()
        dict = {"modification-type": message.payload.modification_type,
                "modification-value": message.payload.modification_value,
                "timestamp": message.payload.timestamp,
                "modification-on-mid": modification_on.authentication.member.mid,
                "modification-on-global-time": modification_on.distribution.global_time}

        prev_modification = message.payload.prev_modification_packet
        if prev_modification:
            message = prev_modification.load_message()
            dict["prev-modification-mid"] = message.authentication.member.mid
            dict["prev-modification-global-time"] = message.distribution.global_time

        return encode(dict),

    def _decode_modification(self, placeholder, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "modification-type" in dic:
            raise DropPacket("Missing 'modification-type'")
        modification_type = dic["modification-type"]
        if not isinstance(modification_type, unicode):
            raise DropPacket("Invalid 'modification_type' type")

        if not "modification-value" in dic:
            raise DropPacket("Missing 'modification-value'")
        modification_value = dic["modification-value"]
        if not (isinstance(modification_value, unicode) and len(modification_value) < 1024):
            raise DropPacket("Invalid 'modification_value' type or value")

        if not "timestamp" in dic:
            raise DropPacket("Missing 'timestamp'")
        timestamp = dic["timestamp"]
        if not isinstance(timestamp, (int, long)):
            raise DropPacket("Invalid 'timestamp' type or value")

        if not "modification-on-mid" in dic:
            raise DropPacket("Missing 'modification-on-mid'")
        modification_on_mid = dic["modification-on-mid"]
        if not (isinstance(modification_on_mid, str) and len(modification_on_mid) == 20):
            raise DropPacket("Invalid 'modification-on-mid' type or value")

        if not "modification-on-global-time" in dic:
            raise DropPacket("Missing 'modification-on-global-time'")
        modification_on_global_time = dic["modification-on-global-time"]
        if not isinstance(modification_on_global_time, (int, long)):
            raise DropPacket("Invalid 'modification-on-global-time' type")

        try:
            packet_id, packet, message_name = self._get_message(modification_on_global_time, modification_on_mid)
            modification_on = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        except DropPacket:
            member = self._community.get_member(mid=modification_on_mid)
            if not member:
                raise DelayPacketByMissingMember(self._community, modification_on_mid)
            raise DelayPacketByMissingMessage(self._community, member, modification_on_global_time)

        prev_modification_mid = dic.get("prev-modification-mid", None)
        if prev_modification_mid and not (isinstance(prev_modification_mid, str) and len(prev_modification_mid) == 20):
            raise DropPacket("Invalid 'prev-modification-mid' type or value")

        prev_modification_global_time = dic.get("prev-modification-global-time", None)
        if prev_modification_global_time and not isinstance(prev_modification_global_time, (int, long)):
            raise DropPacket("Invalid 'prev-modification-global-time' type")

        try:
            packet_id, packet, message_name = self._get_message(prev_modification_global_time, prev_modification_mid)
            prev_modification_packet = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        except:
            prev_modification_packet = None

        return offset, placeholder.meta.payload.implement(modification_type, modification_value, timestamp, modification_on, prev_modification_packet, prev_modification_mid, prev_modification_global_time)

    def _encode_playlist_torrent(self, message):
        playlist = message.payload.playlist.load_message()
        return pack('!20s20sQ', message.payload.infohash, playlist.authentication.member.mid, playlist.distribution.global_time),

    def _decode_playlist_torrent(self, placeholder, offset, data):
        if len(data) < offset + 48:
            raise DropPacket("Unable to decode the payload")

        infohash, playlist_mid, playlist_global_time = unpack_from('!20s20sQ', data, offset)
        try:
            packet_id, packet, message_name = self._get_message(playlist_global_time, playlist_mid)

        except DropPacket:
            member = self._community.dispersy.get_member(mid=playlist_mid)
            if not member:
                raise DelayPacketByMissingMember(self._community, playlist_mid)
            raise DelayPacketByMissingMessage(self._community, member, playlist_global_time)

        playlist = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        return offset + 48, placeholder.meta.payload.implement(infohash, playlist)

    def _get_message(self, global_time, mid):
        assert isinstance(global_time, (int, long))
        assert isinstance(mid, str)
        assert len(mid) == 20
        if global_time and mid:
            try:
                packet_id, packet, message_name = self._community.dispersy.database.execute(
                    u""" SELECT sync.id, sync.packet, meta_message.name
                    FROM sync
                    JOIN member ON (member.id = sync.member)
                    JOIN meta_message ON (meta_message.id = sync.meta_message)
                    WHERE sync.community = ? AND sync.global_time = ? AND member.mid = ?""",
                    (self._community.database_id, global_time, buffer(mid))).next()
            except StopIteration:
                raise DropPacket("Missing message")

            return packet_id, str(packet), message_name

    def _encode_missing_channel(self, message):
        return pack('!B', int(message.payload.includeSnapshot)),

    def _decode_missing_channel(self, placeholder, offset, data):
        if len(data) < offset + 1:
            raise DropPacket("Unable to decode the payload")

        includeSnapshot, = unpack_from('!B', data, offset)
        if not (includeSnapshot == 0 or includeSnapshot == 1):
            raise DropPacket("Unable to decode includeSnapshot")
        includeSnapshot = bool(includeSnapshot)

        return offset + 1, placeholder.meta.payload.implement(includeSnapshot)

class ChannelCompatibility:

    """Class for providing backward compatibility for
        the Channel community.
    """

    def __init__(self, parent):
        self.parent = parent

    def deprecated_meta_messages(self):
        return [
            Message(self.parent, u"channel",
                    MemberAuthentication(),
                    LinearResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=130),
                    CommunityDestination(node_count=10),
                    ChannelPayload(),
                    self._disp_check_channel,
                    self._disp_on_channel),
            Message(self.parent, u"torrent",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=129),
                    CommunityDestination(node_count=10),
                    TorrentPayload(),
                    self._disp_check_torrent,
                    self._disp_on_torrent,
                    self._disp_undo_torrent,
                    batch=BatchConfiguration(max_window=3.0)),
            Message(self.parent, u"playlist",
                    MemberAuthentication(),
                    LinearResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    PlaylistPayload(),
                    self._disp_check_playlist,
                    self._disp_on_playlist,
                    self._disp_undo_playlist,
                    batch=BatchConfiguration(max_window=3.0)),
            Message(self.parent, u"comment",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    CommentPayload(),
                    self._disp_check_comment,
                    self._disp_on_comment,
                    self._disp_undo_comment,
                    batch=BatchConfiguration(max_window=3.0)),
            Message(self.parent, u"modification",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False,
                                         synchronization_direction=u"DESC",
                                         priority=127),
                    CommunityDestination(node_count=10),
                    ModificationPayload(),
                    self._disp_check_modification,
                    self._disp_on_modification,
                    self._disp_undo_modification,
                    batch=BatchConfiguration(max_window=3.0)),
            Message(self.parent, u"playlist_torrent",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    PlaylistTorrentPayload(),
                    self._disp_check_playlist_torrent,
                    self._disp_on_playlist_torrent,
                    self._disp_undo_playlist_torrent,
                    batch=BatchConfiguration(max_window=3.0)),
            Message(self.parent, u"moderation",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    ModerationPayload(),
                    self._disp_check_moderation,
                    self._disp_on_moderation,
                    self._disp_undo_moderation,
                    batch=BatchConfiguration(max_window=3.0)),
            Message(self.parent, u"mark_torrent",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    MarkTorrentPayload(),
                    self._disp_check_mark_torrent,
                    self._disp_on_mark_torrent,
                    self._disp_undo_mark_torrent,
                    batch=BatchConfiguration(max_window=3.0)),
            Message(self.parent, u"missing-channel",
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    MissingChannelPayload(),
                    self._disp_check_missing_channel,
                    self._disp_on_missing_channel),
            ]

    class Mock:
        innerdict = {}
        def put(self, field, value):
            self.innerdict[field] = value
        def __getattr__(self, name):
            if name in self.innerdict:
                return self.innerdict[name]
            else:
                raise AttributeError

    def _reconstruct_channel(self, message):
        mock_main = self.Mock()
        mock_main.put('name', message.payload.name)
        mock_main.put('description', message.payload.description)
        return mock_main

    def _reconstruct_torrent(self, message):
        mock_main = self.Mock()
        mock_files = []
        for path, length in message.payload.files:
            mock_file = self.Mock()
            mock_file.put('path', path)
            mock_file.put('len', length)
            mock_files.append(mock_file)
        mock_main.put('infohash', message.payload.infohash)
        mock_main.put('timestamp', message.payload.timestamp)
        mock_main.put('name', message.payload.name)
        mock_main.put('files', mock_files)
        mock_main.put('trackers', list(message.payload.trackers))
        return mock_main

    def _reconstruct_comment(self, message):
        mock_main = self.Mock()
        mock_main.put('text', message.payload.text)
        mock_main.put('timestamp', message.payload.timestamp)
        mock_main.put('playlistpacket', message.payload.playlist_packet.packet_id)
        mock_main.put('infohash', message.payload.infohash)
        mock_main.put('replytomid', message.payload.reply_to_mid)
        mock_main.put('replytoglobaltime', message.payload.reply_to_global_time)
        mock_main.put('replyaftermid', message.payload.reply_after_mid)
        mock_main.put('replyafterglobaltime', message.payload.reply_after_global_time)
        mock_main.put('playlistmid', message.authentication.member.mid)
        mock_main.put('playlistglobaltime', message.distribution.global_time)
        return mock_main

    def _reconstruct_modification(self, message):
        mock_main = self.Mock()
        modification_on = message.payload.modification_on.load_message()
        mock_main.put('modificationtype', message.payload.modification_type)
        mock_main.put('modificationvalue', message.payload.modification_value)
        mock_main.put('timestamp', message.payload.timestamp)
        mock_main.put('mid', modification_on.authentication.member.mid)
        mock_main.put('globaltime', modification_on.distribution.global_time)
        mock_main.put('prevmid', message.authentication.member.mid)
        mock_main.put('prevglobaltime', message.distribution.global_time)
        return mock_main

    def _reconstruct_playlisttorrent(self, message):
        mock_main = self.Mock()
        playlist = message.payload.playlist.load_message()
        mock_main.put('infohash', message.payload.infohash)
        mock_main.put('mid', playlist.authentication.member.mid)
        mock_main.put('globaltime', playlist.distribution.global_time)
        return mock_main

    def _reconstruct_missingchannel(self, message):
        mock_main = self.Mock()
        mock_main.put('includeSnapshot', message.payload.includeSnapshot)
        return mock_main

    def _reconstruct_moderation(self, message):
        mock_main = self.Mock()
        mock_main.put('text', message.payload.text)
        mock_main.put('timestamp', message.payload.timestamp)
        mock_main.put('severity', message.payload.severity)
        mock_main.put('causemid', message.payload.mid)
        mock_main.put('causeglobaltime', message.payload.cause_global_time)
        return mock_main

    def _reconstruct_marktorrent(self, message):
        mock_main = self.Mock()
        mock_main.put('infohash', message.payload.infohash)
        mock_main.put('timestamp', message.payload.timestamp)
        mock_main.put('type', message.payload.type)
        return mock_main

    def _reconstruct_playlist(self, message):
        return self._reconstruct_channel(message)

    def _disp_check_channel(self, messages):
        for message in messages:
            out = self.parent.check_channel(message, self._reconstruct_channel(message)).next()
            yield out

    def _disp_on_channel(self, messages):
        for message in messages:
            self.parent.on_channel(message, self._reconstruct_channel(message))

    def _disp_check_torrent(self, messages):
        for message in messages:
            out = self.parent.check_torrent(message, self._reconstruct_torrent(message)).next()
            yield out

    def _disp_on_torrent(self, messages):
        for message in messages:
            self.parent.on_torrent(message, self._reconstruct_torrent(message))

    def _disp_undo_torrent(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_torrent(message, self._reconstruct_torrent(message), redo)

    def _disp_check_playlist(self, messages):
        for message in messages:
            out = self.parent.check_playlist(message, self._reconstruct_playlist(message)).next()
            yield out

    def _disp_on_playlist(self, messages):
        for message in messages:
            self.parent.on_playlist(message, self._reconstruct_playlist(message))

    def _disp_undo_playlist(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_playlist(message, self._reconstruct_playlist(message), redo)

    def _disp_check_comment(self, messages):
        for message in messages:
            out = self.parent.check_comment(message, self._reconstruct_comment(message)).next()
            yield out

    def _disp_on_comment(self, messages):
        for message in messages:
            self.parent.on_comment(message, self._reconstruct_comment(message))

    def _disp_undo_comment(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_comment(message, self._reconstruct_comment(message), redo)

    def _disp_check_modification(self, messages):
        for message in messages:
            out = self.parent.check_modification(message, self._reconstruct_modification(message)).next()
            yield out

    def _disp_on_modification(self, messages):
        for message in messages:
            self.parent.on_modification(message, self._reconstruct_modification(message))

    def _disp_undo_modification(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_modification(message, self._reconstruct_modification(message), redo)

    def _disp_check_playlist_torrent(self, messages):
        for message in messages:
            out = self.parent.check_playlisttorrent(message, self._reconstruct_playlisttorrent(message)).next()
            yield out

    def _disp_on_playlist_torrent(self, messages):
        for message in messages:
            self.parent.on_playlisttorrent(message, self._reconstruct_playlisttorrent(message))

    def _disp_undo_playlist_torrent(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_playlisttorrent(message, self._reconstruct_playlisttorrent(message), redo)

    def _disp_check_moderation(self, messages):
        for message in messages:
            out = self.parent.check_moderation(message, self._reconstruct_moderation(message)).next()
            yield out

    def _disp_on_moderation(self, messages):
        for message in messages:
            self.parent.on_moderation(message, self._reconstruct_moderation(message))

    def _disp_undo_moderation(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_moderation(message, self._reconstruct_moderation(message), redo)

    def _disp_check_mark_torrent(self, messages):
        for message in messages:
            out = self.parent.check_marktorrent(message, self._reconstruct_marktorrent(message)).next()
            yield out

    def _disp_on_mark_torrent(self, messages):
        for message in messages:
            self.parent.on_marktorrent(message, self._reconstruct_marktorrent(message))

    def _disp_undo_mark_torrent(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_marktorrent(message, self._reconstruct_marktorrent(message), redo)

    def _disp_check_missing_channel(self, messages):
        for message in messages:
            yield message

    def _disp_on_missing_channel(self, messages):
        for message in messages:
            self.parent.on_missingchannel(message, self._reconstruct_missingchannel(message))
