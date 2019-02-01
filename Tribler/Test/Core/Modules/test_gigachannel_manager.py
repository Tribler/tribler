import os

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Modules.gigachannel_manager import GigaChannelManager
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestGigaChannelManager(TriblerCoreTest):

    @db_session
    def generate_personal_channel(self):
        chan = self.mock_session.lm.mds.ChannelMetadata.create_channel(title="my test chan", description="test")
        my_dir = os.path.abspath(os.path.join(self.mock_session.lm.mds.channels_dir, chan.dir_name))
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        chan.add_torrent_to_channel(tdef, None)
        return chan

    @inlineCallbacks
    def setUp(self):
        yield super(TestGigaChannelManager, self).setUp()
        my_key = default_eccrypto.generate_key(u"curve25519")
        self.mock_session = MockObject()
        self.mock_session.lm = MockObject()
        self.mock_session.lm.mds = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir,
                                                 my_key)

        self.chanman = GigaChannelManager(self.mock_session)

    @inlineCallbacks
    def tearDown(self):
        self.mock_session.lm.mds.shutdown()
        yield super(TestGigaChannelManager, self).tearDown()

    @db_session
    def test_update_my_channel(self):
        chan = self.generate_personal_channel()
        chan.commit_channel_torrent()
        self.torrent_added = False

        def mock_add(a, b):
            self.torrent_added = True

        self.mock_session.lm.add = mock_add
        #   self.mock_session.has_download = lambda x: x == str(chan.infohash)

        # Check add personal channel on startup
        self.mock_session.has_download = lambda _: False
        self.chanman.start()
        self.chanman.check_channels_updates()
        self.assertTrue(self.torrent_added)
        self.chanman.shutdown()

        # Check skip already added personal channel
        self.mock_session.has_download = lambda x: x == str(chan.infohash)
        self.torrent_added = False
        self.chanman.start()
        self.chanman.check_channels_updates()
        self.assertFalse(self.torrent_added)
        self.chanman.shutdown()

    def test_check_channels_updates(self):
        with db_session:
            chan = self.generate_personal_channel()
            chan.commit_channel_torrent()
            chan.local_version -= 1
            chan2 = self.mock_session.lm.mds.ChannelMetadata(title="bla", public_key=database_blob(str(123)),
                                                             signature=database_blob(str(345)), skip_key_check=True,
                                                             timestamp=123, local_version=123, subscribed=True)
            chan3 = self.mock_session.lm.mds.ChannelMetadata(title="bla", public_key=database_blob(str(124)),
                                                             signature=database_blob(str(346)), skip_key_check=True,
                                                             timestamp=123, local_version=122, subscribed=False)
        self.mock_session.has_download = lambda _: False
        self.torrent_added = 0

        def mock_dl(a):
            self.torrent_added += 1

        self.chanman.download_channel = mock_dl

        self.chanman.check_channels_updates()
        # download_channel should only fire once - for the original subscribed channel
        self.assertEqual(1, self.torrent_added)

    def test_remove_cruft_channels(self):
        with db_session:
            chan = self.generate_personal_channel()
            chan.commit_channel_torrent()
            chan.local_version -= 1
            ih_chan2 = database_blob(str(123))
            chan2 = self.mock_session.lm.mds.ChannelMetadata(title="bla", infohash=ih_chan2,
                                                             public_key=database_blob(str(123)),
                                                             signature=database_blob(str(345)), skip_key_check=True,
                                                             timestamp=123, local_version=123, subscribed=True)
            ih_chan3 = database_blob(str(124))
            chan3 = self.mock_session.lm.mds.ChannelMetadata(title="bla", infohash=ih_chan3,
                                                             public_key=database_blob(str(124)),
                                                             signature=database_blob(str(346)), skip_key_check=True,
                                                             timestamp=123, local_version=122, subscribed=False)

        mock_dl_list = [MockObject() for _ in range(4)]
        mock_dl_list[0].infohash = chan.infohash
        mock_dl_list[1].infohash = ih_chan2
        mock_dl_list[2].infohash = ih_chan3
        mock_dl_list[3].infohash = database_blob(str(333))

        def mock_get_channel_downloads():
            return mock_dl_list

        self.remove_list = []

        def mock_remove_channels_downloads(remove_list):
            self.remove_list = remove_list

        self.chanman.remove_channels_downloads = mock_remove_channels_downloads
        self.mock_session.lm.get_channel_downloads = mock_get_channel_downloads
        self.chanman.remove_cruft_channels()
        # We want to remove torrents for (a) deleted channels and (b) unsubscribed channels
        self.assertListEqual(self.remove_list, [mock_dl_list[2], mock_dl_list[3]])
