from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Community.channel.test_channel_base import AbstractTestChannelCommunity
from Tribler.Test.Core.base_test import MockObject


class TestChannelCommunity(AbstractTestChannelCommunity):

    def test_initialize(self):
        def raise_runtime():
            raise RuntimeError()
        self.channel_community._get_latest_channel_message = raise_runtime
        self.channel_community.initialize()
        self.assertIsNone(self.channel_community._channelcast_db)

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
        self.channel_community.remove_playlist_torrents(1234, [1234])
        self.assertTrue(mocked_create_undo.called)

        self.channel_community._dispersy.load_message_by_packetid = \
            lambda community, pid: mocked_load_message(True, community, pid)
        self.channel_community.remove_playlist_torrents(1234, [1234])
        self.assertTrue(mocked_undo_playlist_torrent.called)

    def test_create_torrent_from_def(self):
        """
        Testing whether a correct Dispersy message is created when we add a torrent to our channel
        """
        metainfo = {"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                             "files": [{'path': ['test.txt'], 'length': 1234}]}}
        torrent = TorrentDef.load_from_dict(metainfo)
        self.channel_community.initialize()

        message = self.channel_community._disp_create_torrent_from_torrentdef(torrent, 12345)
        self.assertEqual(message.payload.name, "my_torrent")
        self.assertEqual(len(message.payload.files), 1)
