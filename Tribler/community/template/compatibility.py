from struct import pack, unpack_from

from Tribler.community.basecommunity import BaseConversion
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution
from Tribler.dispersy.message import BatchConfiguration, DropPacket, Message
from Tribler.dispersy.payload import Payload
from Tribler.dispersy.resolution import LinearResolution

"""Backward compatibility for Template.

    Usage:
        1. Create TemplateCompatibility(newcommunity)
        2. Register compatibility.deprecated_meta_messages()
        3. Register Conversion

"""

class TextPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, text):
            assert isinstance(text, unicode)
            assert len(text.encode("UTF-8")) <= 255
            super(TextPayload.Implementation, self).__init__(meta)
            self._text = text

        @property
        def text(self):
            return self._text

class Conversion(BaseConversion):

    def __init__(self, community):
        super(Conversion, self).__init__(community, "\x02")
        self.define_meta_message(chr(1), community.get_meta_message(u"text"), self._encode_text, self._decode_text)

    def _encode_text(self, message):
        assert len(message.payload.text.encode("UTF-8")) < 256
        text = message.payload.text.encode("UTF-8")
        return pack("!B", len(text)), text[:255]

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

class TemplateCompatibility:

    """Class for providing backward compatibility for
        the Template community.
    """

    def __init__(self, parent):
        self.parent = parent

    def deprecated_meta_messages(self):
        return [Message(self.parent, u"text",
                        MemberAuthentication(),
                        LinearResolution(),
                        FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128),
                        CommunityDestination(node_count=10),
                        TextPayload(),
                        self.check_text,
                        self.on_text,
                        batch=BatchConfiguration(max_window=5.0))
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

    def _reconstruct_text(self, message):
        mock_main = self.Mock()
        mock_main.put('text', message.payload.text)
        return mock_main

    def check_text(self, messages):
        for message in messages:
            out = self.parent.check_text(message, self._reconstruct_text(message)).next()
            yield out

    def on_text(self, messages):
        for message in messages:
            self.parent.on_text(message, self._reconstruct_text(message))
