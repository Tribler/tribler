from __future__ import absolute_import

import random
from datetime import datetime

from pony.orm import db_session
from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Modules.gigachannel_manager import GigaChannelManager
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestGigaChannelManager(TriblerCoreTest):

    @db_session
    def generate_personal_channel(self):
        chan = self.mock_session.lm.mds.ChannelMetadata.create_channel(title="my test chan", description="test")
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        chan.add_torrent_to_channel(tdef, None)
        return chan

    @inlineCallbacks
    def setUp(self):
        yield super(TestGigaChannelManager, self).setUp()
        self.torrent_template = {
            "title": "",
            "infohash": "",
            "torrent_date": datetime(1970, 1, 1),
            "tags": "video"
        }
        my_key = default_eccrypto.generate_key(u"curve25519")
        self.mock_session = MockObject()
        self.mock_session.lm = MockObject()
        self.mock_session.lm.mds = MetadataStore(":memory:", self.session_base_dir, my_key)

        self.chanman = GigaChannelManager(self.mock_session)
        self.torrents_added = 0

    @inlineCallbacks
    def tearDown(self):
        self.mock_session.lm.mds.shutdown()
        yield super(TestGigaChannelManager, self).tearDown()

    @db_session
    def test_update_my_channel(self):
        chan = self.generate_personal_channel()
        chan.commit_channel_torrent()

        def mock_add(*_):
            self.torrents_added = 1

        self.mock_session.lm.add = mock_add
        #   self.mock_session.has_download = lambda x: x == str(chan.infohash)

        # Check add personal channel on startup
        self.mock_session.has_download = lambda _: False
        self.chanman.service_channels = lambda: None  # Disable looping call
        self.chanman.start()
        self.chanman.check_channels_updates()
        self.assertTrue(self.torrents_added)
        self.chanman.shutdown()

        # Check skip already added personal channel
        self.mock_session.has_download = lambda x: x == str(chan.infohash)
        self.torrents_added = False
        self.chanman.start()
        self.chanman.check_channels_updates()
        self.assertFalse(self.torrents_added)
        self.chanman.shutdown()

    def test_check_channels_updates(self):
        with db_session:
            chan = self.generate_personal_channel()
            chan.commit_channel_torrent()
            chan.local_version -= 1
            _ = self.mock_session.lm.mds.ChannelMetadata(title="bla", public_key=database_blob(str(123)),
                                                         signature=database_blob(str(345)), skip_key_check=True,
                                                         timestamp=123, local_version=123, subscribed=True,
                                                         infohash=str(random.getrandbits(160)))
            _ = self.mock_session.lm.mds.ChannelMetadata(title="bla", public_key=database_blob(str(124)),
                                                         signature=database_blob(str(346)), skip_key_check=True,
                                                         timestamp=123, local_version=122, subscribed=False,
                                                         infohash=str(random.getrandbits(160)))
        self.mock_session.has_download = lambda _: False
        self.torrents_added = 0

        def mock_dl(_):
            self.torrents_added += 1

        self.chanman.download_channel = mock_dl

        self.chanman.check_channels_updates()
        # download_channel should only fire once - for the original subscribed channel
        self.assertEqual(1, self.torrents_added)

    def test_remove_cruft_channels(self):
        with db_session:
            # Our personal chan is created, then updated, so there are 2 files on disk and there are 2 torrents:
            # the old one and the new one
            my_chan = self.generate_personal_channel()
            my_chan.commit_channel_torrent()
            my_chan_old_infohash = my_chan.infohash
            _ = self.mock_session.lm.mds.TorrentMetadata.from_dict(dict(self.torrent_template, status=NEW))
            my_chan.commit_channel_torrent()

            # Now we add external channel we are subscribed to.
            chan2 = self.mock_session.lm.mds.ChannelMetadata(title="bla1", infohash=database_blob(str(123)),
                                                             public_key=database_blob(str(123)),
                                                             signature=database_blob(str(345)), skip_key_check=True,
                                                             timestamp=123, local_version=123, subscribed=True)

            # Another external channel, but there is a catch: we recently unsubscribed from it
            chan3 = self.mock_session.lm.mds.ChannelMetadata(title="bla2", infohash=database_blob(str(124)),
                                                             public_key=database_blob(str(124)),
                                                             signature=database_blob(str(346)), skip_key_check=True,
                                                             timestamp=123, local_version=123, subscribed=False)

        class MockDownload(MockObject):
            def __init__(self, infohash, dirname):
                self.infohash = infohash
                self.dirname = dirname
                self.tdef = MockObject()
                self.tdef.get_name_utf8 = lambda: self.dirname
                self.tdef.get_infohash = lambda: infohash

            def get_def(self):
                a = MockObject()
                a.infohash = self.infohash
                a.get_name_utf8 = lambda: self.dirname
                a.get_infohash = lambda: self.infohash
                return a

        # Double conversion is required to make sure that buffers signatures are not the same
        mock_dl_list = [
            # Downloads for our personal channel
            MockDownload(database_blob(bytes(my_chan_old_infohash)), my_chan.dir_name),
            MockDownload(database_blob(bytes(my_chan.infohash)), my_chan.dir_name),

            # Downloads for the updated external channel: "old ones" and "recent"
            MockDownload(database_blob(bytes(str(12331244))), chan2.dir_name),
            MockDownload(database_blob(bytes(chan2.infohash)), chan2.dir_name),

            # Downloads for the unsubscribed external channel
            MockDownload(database_blob(bytes(str(1231551))), chan3.dir_name),
            MockDownload(database_blob(bytes(chan3.infohash)), chan3.dir_name),
            # Orphaned download
            MockDownload(database_blob(str(333)), u"blabla")]

        def mock_get_channel_downloads():
            return mock_dl_list

        self.remove_list = []

        def mock_remove_download(infohash, remove_content=False):
            d = Deferred()
            d.callback(None)
            self.remove_list.append((infohash, remove_content))
            return d

        self.chanman.session.remove_download = mock_remove_download

        self.mock_session.lm.get_channel_downloads = mock_get_channel_downloads
        self.chanman.remove_cruft_channels()
        # We want to remove torrents for (a) deleted channels and (b) unsubscribed channels
        self.assertItemsEqual(self.remove_list,
                              [(mock_dl_list[0], False),
                               (mock_dl_list[2], False),
                               (mock_dl_list[4], True),
                               (mock_dl_list[5], True),
                               (mock_dl_list[6], True)])
