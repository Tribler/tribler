# Written by Niels Zeilemaker
from struct import pack, unpack_from

from Tribler.dispersy.conversion import NoDefBinaryConversion
from Tribler.dispersy.message import DropPacket
from Tribler.community.privatesemantic.conversion import long_to_bytes, \
    bytes_to_long
from Tribler.community.privatesemantic.rsa import get_bits

class SocialConversion(NoDefBinaryConversion):

    def __init__(self, community):
        super(NoDefBinaryConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(2), community.get_meta_message(u"encrypted"), self._encode_encrypted, self._decode_encrypted)

    def _encode_text(self, message):
        assert len(message.payload.text.encode("UTF-8")) < 512
        text = message.payload.text.encode("UTF-8")
        return pack("!B", len(text)), text[:512]

    def _decode_text(self, placeholder, offset, data):
        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size")

        text_length, = unpack_from("!B", data, offset)
        offset += 1

        try:
            text = data[offset:offset + text_length].decode("UTF-8")
            offset += text_length
        except UnicodeError:
            raise DropPacket("Unable to decode UTF-8")

        return offset, placeholder.meta.payload.implement(text)

    def _encode_encrypted(self, message):
        encypted_bytes = long_to_bytes(message.encrypted_long, get_bits(message.encrypted_long))
        return pack("!H%ds%ds" % (len(message.pubkey), len(encypted_bytes)), len(message.pubkey), message.pubkey, encypted_bytes),

    def _decode_encrypted(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size")

        pub_length, = unpack_from("!H", data, offset)
        offset += 2

        pubkey, encrypted_bytes = unpack_from("!%ds%ds" % (pub_length, len(data) - offset - 2 - pub_length), data, offset)
        offset += len(pubkey) + len(encrypted_bytes)

        encrypted_long = bytes_to_long(encrypted_bytes)
        return offset, placeholder.meta.payload.implement(pubkey, encrypted_long)
