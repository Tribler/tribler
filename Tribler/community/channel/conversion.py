import zlib
from random import sample
from struct import pack, unpack_from

from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.message import DropPacket, Packet, DelayPacketByMissingMessage, DelayPacketByMissingMember


DEBUG = False


class ChannelConversion(BinaryConversion):

    def __init__(self, community):
        super(ChannelConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"channel"),
                                 lambda message:
                                 self._encode_decode(self._encode_channel, self._decode_channel, message),
                                 self._decode_channel)
        self.define_meta_message(chr(2), community.get_meta_message(u"torrent"),
                                 lambda message: self._encode_decode(self._encode_torrent,
                                                                     self._decode_torrent, message),
                                 self._decode_torrent)
        self.define_meta_message(chr(3), community.get_meta_message(u"playlist"),
                                 lambda message: self._encode_decode(self._encode_playlist,
                                                                     self._decode_playlist, message),
                                 self._decode_playlist)
        self.define_meta_message(chr(4), community.get_meta_message(u"comment"),
                                 lambda message: self._encode_decode(self._encode_comment,
                                                                     self._decode_comment, message),
                                 self._decode_comment)
        self.define_meta_message(chr(5),
                                 community.get_meta_message(u"modification"),
                                 lambda message: self._encode_decode(self._encode_modification,
                                                                     self._decode_modification,
                                                                     message),
                                 self._decode_modification)
        self.define_meta_message(chr(6),
                                 community.get_meta_message(u"playlist_torrent"),
                                 lambda message: self._encode_decode(self._encode_playlist_torrent,
                                                                     self._decode_playlist_torrent, message),
                                 self._decode_playlist_torrent)
        self.define_meta_message(chr(7),
                                 community.get_meta_message(u"missing-channel"),
                                 lambda message: self._encode_decode(self._encode_missing_channel,
                                                                     self._decode_missing_channel, message),
                                 self._decode_missing_channel)
        self.define_meta_message(chr(8),
                                 community.get_meta_message(u"moderation"),
                                 lambda message: self._encode_decode(self._encode_moderation,
                                                                     self._encode_moderation, message),
                                 self._decode_moderation)
        self.define_meta_message(chr(9), community.get_meta_message(u"mark_torrent"),
                                 lambda message: self._encode_decode(self._encode_mark_torrent,
                                                                     self._decode_mark_torrent, message),
                                 self._decode_mark_torrent)

    def _encode_decode(self, encode, decode, message):
        result = encode(message)
        try:
            decode(None, 0, result[0])

        except DropPacket:
            raise
        except:
            pass
        return result

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
