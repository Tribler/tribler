from twisted.internet.defer import inlineCallbacks

from nose.twistedtools import deferred

from Tribler.Test.Community.channel.test_channel_base import AbstractTestChannelCommunity
from Tribler.Test.Core.base_test import MockObject


class TestChannelCommunity(AbstractTestChannelCommunity):

    @deferred(timeout=10)
    @inlineCallbacks
    def test_initialize(self):
        def raise_runtime():
            raise RuntimeError()
        self.channel_community._get_latest_channel_message = raise_runtime
        yield self.channel_community.initialize()
        self.assertIsNone(self.channel_community._channelcast_db)

    @deferred(timeout=10)
    @inlineCallbacks
    def test_remove_playlist_torrents(self):
        """
        Testing whether the right methods are called when a torrent is removed from a playlist
        """
        def mocked_load_message(undone, community, packet_id):
            fake_message = MockObject()
            fake_message.undone = undone
            return fake_message

        def mocked_create_undo(_):
            mocked_create_undo.called = True
        mocked_create_undo.called = False

        def mocked_undo_playlist_torrent(_):
            mocked_undo_playlist_torrent.called = True
        mocked_undo_playlist_torrent.called = False

        self.channel_community.create_undo = mocked_create_undo
        self.channel_community._disp_undo_playlist_torrent = mocked_undo_playlist_torrent

        self.channel_community._dispersy.load_message_by_packetid = \
            lambda community, pid: mocked_load_message(False, community, pid)
        yield self.channel_community.remove_playlist_torrents(1234, [1234])
        self.assertTrue(mocked_create_undo.called)

        self.channel_community._dispersy.load_message_by_packetid = \
            lambda community, pid: mocked_load_message(True, community, pid)
        yield self.channel_community.remove_playlist_torrents(1234, [1234])
        self.assertTrue(mocked_undo_playlist_torrent.called)
