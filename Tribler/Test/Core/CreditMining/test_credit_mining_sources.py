"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""

from binascii import unhexlify, hexlify
from twisted.internet import reactor

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater

from Tribler.Core.CreditMining.CreditMiningSource import ChannelSource
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_DISCOVERED, NTFY_TORRENT
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.Test.test_as_server import TestAsServer


class TestCreditMiningSources(TestAsServer):
    """
    Class to test the credit mining sources
    """

    def __init__(self, *argv, **kwargs):
        super(TestCreditMiningSources, self).__init__(*argv, **kwargs)
        # Fake channel id for testing
        self.cid = '0' * 40

    def setUpPreSession(self):
        super(TestCreditMiningSources, self).setUpPreSession()
        self.config.set_megacache_enabled(True)
        self.config.set_dispersy_enabled(True)
        self.config.set_channel_search_enabled(True)

    def test_channel_lookup(self):
        source = ChannelSource(self.session, self.cid, lambda: None)
        source.start()
        self.assertIsInstance(source.community, ChannelCommunity, 'ChannelSource failed to create ChannelCommunity')
        source.stop()

    def test_existing_channel_lookup(self):
        # Find AllChannel
        for community in self.session.lm.dispersy.get_communities():
            if isinstance(community, AllChannelCommunity):
                allchannelcommunity = community

        # Load the channel
        community = ChannelCommunity.init_community(self.session.lm.dispersy,
                                                    self.session.lm.dispersy.get_member(mid=unhexlify(self.cid)),
                                                    allchannelcommunity.my_member,
                                                    self.session)

        # Check if we find the channel
        source = ChannelSource(self.session, self.cid, lambda: None)
        source.start()
        self.assertEqual(source.community, community, 'ChannelSource failed to find existing ChannelCommunity')
        source.stop()

    def test_torrent_discovered(self):
        torrent_inserteds = []
        torrent_insert_callback = lambda source, infohash, name: torrent_inserteds.append((source, infohash, name))
        source = ChannelSource(self.session, self.cid, torrent_insert_callback)
        source.start()

        source.on_torrent_discovered(NTFY_TORRENT, NTFY_DISCOVERED, self.cid, {'dispersy_cid': self.cid,
                                                                               'infohash': '\00' * 20,
                                                                               'name': 'torrent'})
        self.assertIn((self.cid, '\00' * 20, 'torrent'), torrent_inserteds, 'ChannelSource failed to insert torrent')

        source.on_torrent_discovered(NTFY_TORRENT, NTFY_DISCOVERED, self.cid, {'dispersy_cid': '1' * 40,
                                                                               'infohash': '\01' * 20,
                                                                               'name': 'torrent'})
        self.assertTrue(len(torrent_inserteds) == 1, 'ChannelSource inserted torrent with wrong dispersy_cid')

        source.stop()
