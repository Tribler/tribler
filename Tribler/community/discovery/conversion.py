from socket import inet_aton, inet_ntoa
from struct import pack, unpack_from

from payload import UserMetadataPayload, CommunityMetadataPayload

from Tribler.Core.dispersy.conversion import BinaryConversion
from Tribler.Core.dispersy.message import DropPacket

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

# class DiscoveryDictionaryConversion01(DictionaryConversion):
#     def __init__(self, community):
#         super(DiscoveryDictionaryConversion01, self).__init__(community, "\x00\x01")
#         self.define_meta_message(community.get_meta_message(u"user-metadata"), self._encode_user_metadata_payload, self._decode_user_metadata_payload)
#         self.define_meta_message(community.get_meta_message(u"community-metadata"), self._encode_community_metadata_payload, self._decode_community_metadata_payload)

#     def _encode_user_metadata_payload(self, message):
#         return {"address":message.payload.address, "alias":message.payload.alias, "comment":message.payload.comment}

#     def _decode_user_metadata_payload(self, _, payload):
#         if not isinstance(payload, dict):
#             raise DropPacket("Invalid payload type")
#         if not len(payload) == 3:
#             raise DropPacket("Invalid payload length")

#         address = payload.get("address")
#         if not isinstance(address, tuple):
#             raise DropPacket("Invalid address type")
#         if not len(address) == 2:
#             raise DropPacket("Invalid address length")
#         if not isinstance(address[0], str):
#             raise DropPacket("Invalid host type")
#         if not isinstance(address, tuple):
#             raise DropPacket("Invalid port type")
#         if not address[1] > 1024:
#             raise DropPacket("Invalid port value")

#         alias = payload.get("alias")
#         if not isinstance(alias, unicode):
#             raise DropPacket("Invalid alias type")

#         comment = payload.get("comment")
#         if not isinstance(comment, unicode):
#             raise DropPacket("Invalid comment type")

#         return UserMetadataPayload(address, alias, comment)

#     def _encode_community_metadata_payload(self, message):
#         return {"cid":message.payload.cid, "alias":message.payload.alias, "comment":message.payload.comment}

#     def _decode_community_metadata_payload(self, _, payload):
#         if not isinstance(payload, dict):
#             raise DropPacket("Invalid payload type")
#         if not len(payload) == 3:
#             raise DropPacket("Invalid payload length")

#         cid = payload.get("cid")
#         if not isinstance(cid, str):
#             raise DropPacket("Invalid cid type")
#         if not len(cid) == 20:
#             raise DropPacket("Invalid cid length")

#         alias = payload.get("alias")
#         if not isinstance(alias, unicode):
#             raise DropPacket("Invalid unicode type")

#         comment = payload.get("comment")
#         if not isinstance(comment, unicode):
#             raise DropPacket("Invalid comment type")

#         return CommunityMetadataPayload(cid, alias, comment)

class DiscoveryBinaryConversion02(BinaryConversion):
    def __init__(self, community):
        super(DiscoveryBinaryConversion02, self).__init__(community, "\x00\x02")
        self.define_meta_message(chr(1), community.get_meta_message(u"user-metadata"), self._encode_user_metadata_payload, self._decode_user_metadata_payload)
        self.define_meta_message(chr(2), community.get_meta_message(u"community-metadata"), self._encode_community_metadata_payload, self._decode_community_metadata_payload)

    def _encode_user_metadata_payload(self, message):
        assert isinstance(message.payload, UserMetadataPayload.Implementation)
        alias = message.payload.alias.encode("UTF-8")
        comment = message.payload.comment.encode("UTF-8")
        return inet_aton(message.payload.address[0]), pack("!HBH", message.payload.address[1], len(alias), len(comment)), alias, comment

    def _decode_user_metadata_payload(self, meta_message, offset, data):
        if len(data) < offset + 9:
            raise DropPacket("Insufficient packet size")

        ip = inet_ntoa(data[offset:offset+4])
        offset += 4
        port, alias_length, comment_length = unpack_from("!HBH", data, offset)
        offset += 5

        if len(data) < offset + alias_length + comment_length:
            raise DropPacket("Insufficient packet size")

        try:
            alias = data[offset:offset+alias_length].decode("UTF-8")
        except UnicodeDecodeError:
            raise DropPacket("Invalid alias type")
        offset += alias_length

        try:
            comment = data[offset:offset+comment_length].decode("UTF-8")
        except UnicodeDecodeError:
            raise DropPacket("Invalid comment type")
        offset += comment_length

        return offset, meta_message.payload.implement((ip, port), alias, comment)

    def _encode_community_metadata_payload(self, message):
        assert isinstance(message.payload, CommunityMetadataPayload.Implementation)
        alias = message.payload.alias.encode("UTF-8")
        comment = message.payload.comment.encode("UTF-8")
        return message.payload.cid, pack("!BH", len(alias), len(comment)), alias, comment

    def _decode_community_metadata_payload(self, meta_message, offset, data):
        if len(data) < offset + 23:
            raise DropPacket("Insufficient packet size")

        cid = data[offset:offset+20]
        offset += 20

        alias_length, comment_length = unpack_from("!BH", data, offset)
        offset += 3

        if len(data) < offset + alias_length + comment_length:
            raise DropPacket("Insufficient packet size")

        try:
            alias = data[offset:offset+alias_length].decode("UTF-8")
        except UnicodeDecodeError:
            raise DropPacket("Invalid alias type")
        offset += alias_length

        try:
            comment = data[offset:offset+comment_length].decode("UTF-8")
        except UnicodeDecodeError:
            raise DropPacket("Invalid comment type")
        offset += comment_length

        return offset, meta_message.payload.implement(cid, alias, comment)
