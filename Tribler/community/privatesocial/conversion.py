# Written by Niels Zeilemaker
from struct import pack, unpack_from

from Tribler.dispersy.conversion import NoDefBinaryConversion
from Tribler.dispersy.message import DropPacket
from Tribler.community.privatesemantic.conversion import long_to_bytes, \
    bytes_to_long
from Tribler.community.privatesemantic.rsa import get_bits

class SocialConversion(NoDefBinaryConversion):

    def __init__(self, community):
        super(SocialConversion, self).__init__(community, "\x01")
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
        keyhash = long_to_bytes(message.payload.keyhash, 20)
        return pack("!20s%ds" % len(message.payload.encrypted_message), keyhash, message.payload.encrypted_message),

    def _decode_encrypted(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size")

        keyhash, encrypted_message = unpack_from("!20s%ds" % (len(data) - offset - 20), data, offset)
        offset += len(keyhash) + len(encrypted_message)

        keyhash = bytes_to_long(keyhash)
        return offset, placeholder.meta.payload.implement(keyhash, encrypted_message)
