from Tribler.Core.dispersy.encoding import encode, decode
from Tribler.Core.dispersy.message import DropPacket, Packet
from Tribler.Core.dispersy.conversion import BinaryConversion
from traceback import print_exc

class ChannelConversion(BinaryConversion):
    def __init__(self, community):
        super(ChannelConversion, self).__init__(community, "\x00\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"channel"), self._encode_channel, self._decode_channel)
        self.define_meta_message(chr(2), community.get_meta_message(u"torrent"), self._encode_torrent, self._decode_torrent)
        self.define_meta_message(chr(3), community.get_meta_message(u"playlist"), self._encode_playlist, self._decode_playlist)
        self.define_meta_message(chr(4), community.get_meta_message(u"comment"), self._encode_comment, self._decode_comment)
        self.define_meta_message(chr(5), community.get_meta_message(u"modification"), self._encode_modification, self._decode_modification)
        self.define_meta_message(chr(6), community.get_meta_message(u"playlist_torrent"), self._encode_playlist_torrent, self._decode_playlist_torrent)
        self.define_meta_message(chr(7), community.get_meta_message(u"missing-channel"), self._encode_missing_channel, self._decode_missing_channel)

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
        dict = {"text":message.payload.text,
                "timestamp":message.payload.timestamp}
        
        reply_to_packet = message.payload.reply_to_packet
        reply_after_packet = message.payload.reply_after_packet
        playlist_packet = message.payload.playlist_packet
        infohash = message.payload.infohash
        
        if reply_to_packet:
            dict["reply-to-mid"] = message.payload.reply_to_mid
            dict["reply-to-global-time"] = message.payload.reply_to_global_time
            
        if reply_after_packet:
            dict["reply-after-mid"] = message.payload.reply_after_mid
            dict["reply-after-global-time"] = message.payload.reply_after_global_time
            
        if playlist_packet:
            message = playlist_packet.load_message()
            dict["playlist-mid"] = message.authentication.member.mid
            dict["playlist-global-time"] = message.distribution.global_time
            
        if infohash:
            dict['infohash'] = infohash
        return encode(dict),

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

        try:
            packet_id, packet, message_name = self._get_message(reply_to_global_time, reply_to_mid)
            reply_to = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        except:
            if __debug__:
                print_exc()
            reply_to = None

        reply_after_mid = dic.get("reply-after-mid", None)
        if reply_after_mid and not (isinstance(reply_after_mid, str) and len(reply_after_mid) == 20):
            raise DropPacket("Invalid 'reply-after-mid' type or value")
        
        reply_after_global_time = dic.get("reply-after-global-time", None)
        if reply_after_global_time and not isinstance(reply_after_global_time, (int, long)):
            raise DropPacket("Invalid 'reply-after-global-time' type")
        
        try:
            packet_id, packet, message_name = self._get_message(reply_after_global_time, reply_after_mid)
            reply_after = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        except:
            if __debug__:
                print_exc()
            reply_after = None
            
        playlist_mid = dic.get("playlist-mid", None)
        if playlist_mid and not (isinstance(playlist_mid, str) and len(playlist_mid) == 20):
            raise DropPacket("Invalid 'playlist-mid' type or value")
        
        playlist_global_time = dic.get("playlist-global-time", None)
        if playlist_global_time and not isinstance(playlist_global_time, (int, long)):
            raise DropPacket("Invalid 'playlist-global-time' type")
        
        try:
            packet_id, packet, message_name = self._get_message(playlist_mid, playlist_global_time)
            playlist = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        except:
            if __debug__:
                print_exc()
            playlist = None
        
        infohash = dic.get("infohash", None)
        if infohash and not (isinstance(infohash, str) and len(infohash) == 20):
            raise DropPacket("Invalid 'infohash' type or value")
        return offset, meta_message.payload.implement(text, timestamp, reply_to, reply_to_mid, reply_to_global_time, reply_after, reply_after_mid, reply_after_global_time, playlist, infohash)

    def _encode_modification(self, message):
        modification_on = message.payload.modification_on.load_message()
        dict = {"modification":message.payload.modification,
                "modification-on-mid":modification_on.authentication.member.mid,
                "modification-on-global-time":modification_on.distribution.global_time}
        
        latest_modification = message.payload.latest_modification
        if latest_modification:
            message = latest_modification.load_message()
            dict["latest-modification-mid"] = message.authentication.member.mid
            dict["latest-modification-global-time"] = message.distribution.global_time
        
        return encode(dict),

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
        
        packet_id, packet, message_name = self._get_message(modification_on_global_time, modification_on_mid)
        modification_on = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        
        latest_modification_mid = dic.get("latest-modification-mid", None)
        if latest_modification_mid and not (isinstance(latest_modification_mid, str) and len(latest_modification_mid) == 20):
            raise DropPacket("Invalid 'latest-modification-mid' type or value")
        
        latest_modification_global_time = dic.get("latest-modification-global-time", None)
        if latest_modification_global_time and not isinstance(latest_modification_global_time, (int, long)):
            raise DropPacket("Invalid 'atest-modification-global-time' type")
        
        try:
            packet_id, packet, message_name = self._get_message(latest_modification_global_time, latest_modification_mid)
            latest_modification = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        except:
            if __debug__:
                print_exc()
                
            latest_modification = None

        return offset, meta_message.payload.implement(modification, modification_on, latest_modification, latest_modification_mid, latest_modification_global_time)

    def _encode_playlist_torrent(self, message):
        playlist = message.payload.playlist.load_message()
        return encode({"infohash":message.payload.infohash,
                       "playlist-mid":playlist.authentication.member.mid,
                       "playlist-global-time":playlist.distribution.global_time}),

    def _decode_playlist_torrent(self, meta_message, offset, data):
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not "infohash" in dic:
            raise DropPacket("Missing 'infohash'")
        infohash = dic["infohash"]
        if not (isinstance(infohash, str) and len(infohash) == 20):
            raise DropPacket("Invalid 'infohash' type or value")

        if not "playlist-mid" in dic:
            raise DropPacket("Missing 'playlist-mid'")
        playlist_mid = dic["playlist-mid"]
        if not (isinstance(playlist_mid, str) and len(playlist_mid) == 20):
            raise DropPacket("Invalid 'playlist-mid' type or value")
        
        if not "playlist-global-time" in dic:
            raise DropPacket("Missing 'playlist-global-time'")
        playlist_global_time = dic["playlist-global-time"]
        if not isinstance(playlist_global_time, (int, long)):
            raise DropPacket("Invalid 'playlist-global-time' type")
        
        packet_id, packet, message_name = self._get_message(playlist_global_time, playlist_mid)
        playlist = Packet(self._community.get_meta_message(message_name), packet, packet_id)
        return offset, meta_message.payload.implement(infohash, playlist)
    
    def _get_message(self, global_time, mid):
        if global_time and mid:
            try:
                packet_id, packet, message_name = self._dispersy_database.execute(u"""
                    SELECT sync.id, sync.packet, name.value
                    FROM sync
                    JOIN user ON (user.id = sync.user)
                    JOIN name ON (name.id = sync.name)
                    WHERE sync.community = ? AND sync.global_time = ? AND user.mid = ?""",
                                                          (self._community.database_id, global_time, buffer(mid))).next()
            except StopIteration:
                raise DropPacket("Missing previous message")
            
            return packet_id, str(packet), message_name
        raise DropPacket("Global_time or mid missing")

    def _encode_missing_channel(self, message):
        return ()

    def _decode_missing_channel(self, meta_message, offset, data):
        return offset, meta_message.payload.implement()
