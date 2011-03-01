from Tribler.Core.dispersy.encoding import encode, decode
from Tribler.Core.dispersy.message import DropPacket, Packet
from Tribler.Core.dispersy.conversion import BinaryConversion

class ChannelConversion(BinaryConversion):
    def __init__(self, community):
        super(ChannelConversion, self).__init__(community, "\x00\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"channel"), self._encode_channel, self._decode_channel)
        self.define_meta_message(chr(2), community.get_meta_message(u"torrent"), self._encode_torrent, self._decode_torrent)
        self.define_meta_message(chr(3), community.get_meta_message(u"playlist"), self._encode_playlist, self._decode_playlist)
        self.define_meta_message(chr(4), community.get_meta_message(u"comment"), self._encode_comment, self._decode_comment)
        self.define_meta_message(chr(5), community.get_meta_message(u"modification"), self._encode_modification, self._decode_modification)

    def _encode_channel(self, message):
        return encode({"name":message.payload.name,
                       "description":message.payload.description}),

    def _decode_channel(self, meta_message, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "name" in dic:
            raise DropPacket("Missing 'name'")
        name = dic["name"]
        if not (isinstance(name, unicode) and len(name) < 256):
            raise DropPacket("Invalid 'name' type or value")

        if not "description" in dic:
            raise DropPacket("Missing 'description'")
        description = dic["description"]
        if not (isinstance(description, unicode) and len(description) < 1024):
            raise DropPacket("Invalid 'description' type or value")

        return offset, meta_message.payload.implement(name, description)

    def _encode_torrent(self, message):
        return encode({"infohash":message.payload.infohash,
                       "timestamp":message.payload.timestamp}),

    def _decode_torrent(self, meta_message, offset, data):
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
            raise DropPacket("Invalid 'timestamp' type")

        return offset, meta_message.payload.implement(infohash, timestamp)

    def _encode_playlist(self, message):
        return encode({"name":message.payload.name,
                       "description":message.payload.description}),

    def _decode_playlist(self, meta_message, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "name" in dic:
            raise DropPacket("Missing 'name'")
        name = dic["name"]
        if not (isinstance(name, unicode) and len(name) < 256):
            raise DropPacket("Invalid 'name' type or value")

        if not "description" in dic:
            raise DropPacket("Missing 'description'")
        description = dic["description"]
        if not (isinstance(description, unicode) and len(description) < 1024):
            raise DropPacket("Invalid 'description' type or value")

        return offset, meta_message.payload.implement(name, description)

    def _encode_comment(self, message):
        reply_to = message.payload.reply_to.load_message()
        reply_after = message.payload.reply_after.load_message()
        return encode({"text":message.payload.text,
                       "reply-to-mid":reply_to.authentication.member.mid,
                       "reply-to-global-time":reply_to.distribution.global_time,
                       "reply-from-mid":reply_from.authentication.member.mid,
                       "reply-from-global-time":reply_from.distribution.global_time})

    def _decode_comment(self, meta_message, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "text" in dic:
            raise DropPacket("Missing 'text'")
        text = dic["text"]
        if not (isinstance(text, unicode) and len(text) < 2^16):
            raise DropPacket("Invalid 'text' type or value")

        #
        # reply_to
        #

        if not "reply-to-mid" in dic:
            raise DropPacket("Missing 'reply-to-mid'")
        reply_to_mid = dic["reply-to-mid"]
        if not (isinstance(reply_to_mid, str) and len(reply_to_mid) == 20):
            raise DropPacket("Invalid 'reply-to-mid' type or value")

        if not "reply-to-global-time" in dic:
            raise DropPacket("Missing 'reply-to-global-time'")
        reply_to_global_time = dic["reply-to-global-time"]
        if not isinstance(reply_to_global_time, (int, long)):
            raise DropPacket("Invalid 'reply-to-global-time' type")

        try:
            packet_id, packet, message_name = self._dispersy_database.execute(u"""
                SELECT sync.id, sync.packet, name.value
                FROM sync
                JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                JOIN user ON (user.id = reference_user_sync.user)
                JOIN name ON (name.id = sync.name)
                WHERE sync.community = ? AND sync.global_time = ? AND user.mid = ?""",
                                                                              (self._community.database_id, reply_to_global_time, reply_to_mid)).next()
        except StopIteration:
            # todo: delay packet instead!
            raise DropPacket("Missing previous message")

        reply_to = Packet(self._community.get_meta_message(message_name), packet, packet_id)

        #
        # reply_from
        #

        if not "reply-from-mid" in dic:
            raise DropPacket("Missing 'reply-from-mid'")
        reply_from_mid = dic["reply-from-mid"]
        if not (isinstance(reply_from_mid, str) and len(reply_from_mid) == 20):
            raise DropPacket("Invalid 'reply-from-mid' type or value")

        if not "reply-from-global-time" in dic:
            raise DropPacket("Missing 'reply-from-global-time'")
        reply_from_global_time = dic["reply-from-global-time"]
        if not isinstance(reply_from_global_time, (int, long)):
            raise DropPacket("Invalid 'reply-from-global-time' type")

        try:
            packet_id, packet, message_name = self._dispersy_database.execute(u"""
                SELECT sync.id, sync.packet, name.value
                FROM sync
                JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                JOIN user ON (user.id = reference_user_sync.user)
                JOIN name ON (name.id = sync.name)
                WHERE sync.community = ? AND sync.global_time = ? AND user.mid = ?""",
                                                                              (self._community.database_id, reply_from_global_time, reply_from_mid)).next()
        except StopIteration:
            # todo: delay packet instead!
            raise DropPacket("Missing previous message")

        reply_from = Packet(self._community.get_meta_message(message_name), packet, packet_id)

        return offset, meta_message.payload.implement(text, reply_to, reply_from)

    def _encode_modification(self, message):
        modification_on = message.payload.modification_on.load_message()
        return encode({"modification":message.payload.modification,
                       "modification-on-mid":modification_on.authentication.member.mid,
                       "modification-on-global-time":modification_on.distribution.global_time})

    def _decode_modification(self, meta_message, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "modification" in dic:
            raise DropPacket("Missing 'modification'")
        modification = dic["modification"]
        if not isinstance(modification, dict):
            raise DropPacket("Invalid 'modification' type")

        #
        # modification_on
        #

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
            packet.id, packet, message_name = self._dispersy_database.execute(u"""
                SELECT sync.id, sync.packet, name.value
                FROM sync
                JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                JOIN user ON (user.id = reference_user_sync.user)
                JOIN name ON (name.id = sync.name)
                WHERE sync.community = ? AND sync.global_time = ? AND user.mid = ?""",
                                                      (self._community.database_id, modification_on_global_time, modification_on_mid)).next()
        except StopIteration:
            # todo: delay packet instead!
            raise DropPacket("Missing previous message")

        modification_on = Packet(self._community.get_meta_message(message_name), packet, packet_id)

        return offset, meta_message.payload.implement(modification, modification_on)
