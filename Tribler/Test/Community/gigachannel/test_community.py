from twisted.internet.defer import inlineCallbacks

from Tribler.community.gigachannel.community import ChannelDownloadCache, GigaChannelCommunity
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.Test.mocking.channel import MockChannel
from Tribler.Test.mocking.download import MockDownload
from Tribler.Test.mocking.session import MockSession


class TestGigaChannelUnits(TestBase):

    """
    Unit tests for the GigaChannel community which do not need a real Session.
    """

    def setUp(self):
        super(TestGigaChannelUnits, self).setUp()
        self.session = MockSession()

        self.initialize(GigaChannelCommunity, 1)

    def create_node(self, *args, **kwargs):
        kwargs['tribler_session'] = self.session
        return super(TestGigaChannelUnits, self).create_node(*args, **kwargs)

    def _setup_fetch_next(self):
        """
        Setup phase for fetch_next() tests.

        Provides:
         - Database entry for a mocked Channel.
         - download_channel() functionality for the mocked channel.
         - Pending overlay.download_queue for the mocked channel.
        """
        channel, download = self._setup_download_completed()
        self.session.lm.set_download_channel(download)
        self.nodes[0].overlay.download_queue = [channel.infohash]

        return channel, download

    def _setup_download_completed(self):
        """
        Setup phase for the download_completed() tests.

        Provides:
         - Database entry for a mocked Channel.
         - Mocked (empty) download_channel() functionality.
        """
        channel = MockChannel('\x00' * 20, 'LibNaCLPK:' + '\x00' * 64, 'test', 1, 0)
        self.session.lm.mds.ChannelMetadata.add(channel)
        download = MockDownload()
        download.tdef.set_infohash(channel.infohash)

        return channel, download

    def test_select_random_none(self):
        """
        No entries in the database should yield no results.
        """
        channel_list = []
        self.session.lm.mds.ChannelMetadata.set_random_channels(channel_list)

        entries = self.nodes[0].overlay.get_random_entries()

        self.assertEqual(0, len(entries))

    def test_select_random_one(self):
        """
        One entry in the database should yield one result.
        """
        channel_list = [MockChannel('\x00' * 20, 'LibNaCLPK:' + '\x00' * 64, 'test', 1, 0)]
        self.session.lm.mds.ChannelMetadata.set_random_channels(channel_list)

        entries = self.nodes[0].overlay.get_random_entries()

        self.assertEqual(1, len(entries))
        self.assertEqual(entries[0].infohash, channel_list[0].infohash)
        self.assertEqual(entries[0].public_key, channel_list[0].public_key[10:])
        self.assertEqual(entries[0].title, channel_list[0].title)
        self.assertEqual(entries[0].version, channel_list[0].version)

    def test_select_random_many(self):
        """
        Six entries in the database should yield six results.
        """
        channel_list = [MockChannel('\x00' * 20, 'LibNaCLPK:' + '\x00' * 64, 'test', 1, 0)] * 6
        self.session.lm.mds.ChannelMetadata.set_random_channels(channel_list)

        entries = self.nodes[0].overlay.get_random_entries()

        self.assertEqual(6, len(entries))
        for entry in entries:
            self.assertEqual(entry.infohash, channel_list[0].infohash)
            self.assertEqual(entry.public_key, channel_list[0].public_key[10:])
            self.assertEqual(entry.title, channel_list[0].title)
            self.assertEqual(entry.version, channel_list[0].version)

    def test_select_random_too_many(self):
        """
        Ten entries in the database should be capped at seven results.
        """
        channel_list = [MockChannel('\x00' * 20, 'LibNaCLPK:' + '\x00' * 64, 'test', 1, 0)] * 10
        self.session.lm.mds.ChannelMetadata.set_random_channels(channel_list)

        entries = self.nodes[0].overlay.get_random_entries()

        self.assertEqual(7, len(entries))
        for entry in entries:
            self.assertEqual(entry.infohash, channel_list[0].infohash)
            self.assertEqual(entry.public_key, channel_list[0].public_key[10:])
            self.assertEqual(entry.title, channel_list[0].title)
            self.assertEqual(entry.version, channel_list[0].version)

    def test_update_with_download(self):
        """
        Test if an update with a download extracts the seeder count as votes.
        """
        channel, download = self._setup_download_completed()

        self.assertEqual(0, channel.votes)

        self.nodes[0].overlay.update_from_download(download)

        self.assertEqual(42, channel.votes)

    def test_download_completed_no_token(self):
        """
        Test if the download completed callback extracts the seeder count as votes.
        """
        channel, download = self._setup_download_completed()

        self.assertEqual(0, channel.votes)

        self.nodes[0].overlay.download_completed(download)

        self.assertEqual(42, channel.votes)

    def test_download_completed_with_token(self):
        """
        Test if the download completed callback releases the download token.
        """
        channel, download = self._setup_download_completed()

        token = ChannelDownloadCache(self.nodes[0].overlay.request_cache)
        self.nodes[0].overlay.request_cache.add(token)

        self.nodes[0].overlay.download_completed(download)

        self.assertFalse(self.nodes[0].overlay.request_cache.has(token.prefix, token.number))

    def test_fetch_next_no_token(self):
        """
        Test if nothing happens when we fetch the next download without holding the download token.
        """
        channel, download = self._setup_fetch_next()

        token = ChannelDownloadCache(self.nodes[0].overlay.request_cache)
        self.nodes[0].overlay.request_cache.add(token)

        self.nodes[0].overlay.fetch_next()

        self.nodes[0].overlay.request_cache.pop(token.prefix, token.number)

        self.assertEqual(1, len(self.nodes[0].overlay.download_queue))

    def test_fetch_next_already_known(self):
        """
        Test if we throw out a download when we fetch a download we already know.
        """
        channel, download = self._setup_fetch_next()
        self.session.add_known_infohash(channel.infohash)

        self.nodes[0].overlay.fetch_next()

        self.assertEqual(0, len(self.nodes[0].overlay.download_queue))

    @inlineCallbacks
    def test_fetch_next(self):
        """
        Test if we download a channel if we have nothing else to do.
        """
        channel, download = self._setup_fetch_next()

        self.nodes[0].overlay.fetch_next()

        self.assertTrue(self.session.lm.downloading)

        self.assertEqual(0, channel.votes)

        self.session.lm.finish_download_channel()

        yield self.session.lm.downloaded_channel_deferred

        self.assertFalse(self.session.lm.downloading)
        self.assertEqual(42, channel.votes)

    @inlineCallbacks
    def test_send_random_to_known_new(self):
        """
        Test if we do not add new downloads to the queue if we get sent a new channel.
        """
        channel = MockChannel('\x00' * 20, 'LibNaCLPK:' + '\x00' * 64, 'test', 1, 0)
        self.session.lm.mds.ChannelMetadata.set_random_channels([channel])

        self.nodes[0].overlay.send_random_to(Peer(self.nodes[0].my_peer.public_key, self.nodes[0].endpoint.wan_address))

        yield self.deliver_messages()

        self.assertEqual(1, len(self.nodes[0].overlay.download_queue))
        self.assertIn(channel.infohash, self.nodes[0].overlay.download_queue)

    @inlineCallbacks
    def test_send_random_to_known_update(self):
        """
        Test if we do not add new downloads to the queue if we get sent a new channel.
        """
        old_channel = MockChannel('\x00' * 20, 'LibNaCLPK:' + '\x00' * 64, 'test', 1, 0)
        self.session.lm.mds.ChannelMetadata.add(old_channel)
        new_channel = MockChannel('\x01' * 20, 'LibNaCLPK:' + '\x00' * 64, 'test', 2, 0)
        self.session.lm.mds.ChannelMetadata.set_random_channels([new_channel])

        self.nodes[0].overlay.send_random_to(Peer(self.nodes[0].my_peer.public_key, self.nodes[0].endpoint.wan_address))

        yield self.deliver_messages()

        self.assertEqual(1, len(self.nodes[0].overlay.download_queue))
        self.assertIn(old_channel.infohash, self.nodes[0].overlay.download_queue)
        self.assertEqual(old_channel.infohash, new_channel.infohash)
