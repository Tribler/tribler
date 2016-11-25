from struct import pack
import zlib

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Utilities.encoding import encode
from Tribler.Test.Community.channel.test_channel_base import AbstractTestChannelCommunity
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.channel.conversion import ChannelConversion
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestChannelConversion(AbstractTestChannelCommunity):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestChannelConversion, self).setUp(annotate=annotate)
        self.channel_community.initialize()
        self.conversion = ChannelConversion(self.channel_community)

        self.placeholder = MockObject()

    def test_decode_torrent(self):
        """
        Test the decoding of a torrent message
        """
        self.assertRaises(DropPacket, self.conversion._decode_torrent, None, 0, "abcd")
        self.assertRaises(DropPacket, self.conversion._decode_torrent, None, 0, zlib.compress("abcd"))

        # Test a successful decoding
        meta = self.channel_community.get_meta_message(u"torrent")
        msg = MockObject()
        msg.meta = meta

        torrent_msg = encode((pack('!20sQ', 'a' * 20, 12345), u'torrent', ((u'a', 1234),), ('http://track.er',)))
        _, msg = self.conversion._decode_torrent(msg, 0, zlib.compress(torrent_msg))

        self.assertEqual(msg.infohash, 'a' * 20)
        self.assertEqual(msg.name, u'torrent')
