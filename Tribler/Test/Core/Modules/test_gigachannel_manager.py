from __future__ import absolute_import

import os
from datetime import datetime

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from six import assertCountEqual

from twisted.internet.defer import Deferred, inlineCallbacks, succeed

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Modules.gigachannel_manager import GigaChannelManager
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.Core.simpledefs import DLSTATUS_SEEDING
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.tools import trial_timeout


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
        self.torrent_template = {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}
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
        channel_torrent_dict = chan.commit_channel_torrent()

        def mock_add(*_):
            self.torrents_added = 1

        self.mock_session.lm.add = mock_add
        self.mock_session.config = MockObject()
        self.mock_session.config.get_state_dir = lambda: None

        # Check add personal channel on startup
        self.mock_session.has_download = lambda _: False
        self.chanman.service_channels = lambda: None  # Disable looping call
        self.chanman.start()
        self.assertTrue(self.torrents_added)
        self.chanman.shutdown()

        # Check skip already added personal channel
        self.mock_session.has_download = lambda x: bytes(x) == bytes(chan.infohash)
        self.torrents_added = 0
        self.chanman.start()
        self.chanman.check_channels_updates()
        self.assertFalse(self.torrents_added)
        self.chanman.shutdown()

        # Test regenerating channel torrent
        self.mock_session.has_download = lambda _: False
        consolidated = []
        updated_my_channel = []

        def mock_consolidate(*_):
            consolidated.append(True)
            return channel_torrent_dict

        def mock_updated_my_channel(*_):
            updated_my_channel.append(True)

        self.mock_session.lm.mds.ChannelMetadata.consolidate_channel_torrent = mock_consolidate
        self.chanman.updated_my_channel = mock_updated_my_channel
        torrent_path = os.path.join(self.mock_session.lm.mds.channels_dir, chan.dirname + ".torrent")
        os.unlink(torrent_path)
        self.chanman.start()
        self.assertTrue(consolidated)
        self.assertTrue(updated_my_channel)

    @db_session
    @inlineCallbacks
    def test_check_channels_updates(self):
        # ACHTUNG! This test requires horribly complex mock objects. The reason for that is that the Libtorrent
        # wrapper itself is horribly complex at the moment. However, this test should be as fragile as possible,
        # as it is the most important part of the GigaChannel internals.

        # We add our personal channel in an inconsistent state to make sure the GigaChannel Manager will
        # not try to update it in the same way it should update others' channels
        chan = self.generate_personal_channel()
        chan.commit_channel_torrent()
        chan.local_version -= 1

        # Subscribed, not updated
        self.mock_session.lm.mds.ChannelMetadata(
            title="bla1",
            public_key=database_blob(b'123'),
            signature=database_blob(b'345'),
            skip_key_check=True,
            timestamp=123,
            local_version=123,
            subscribed=True,
            infohash=os.urandom(20),
        )
        # Not subscribed, updated
        self.mock_session.lm.mds.ChannelMetadata(
            title="bla2",
            public_key=database_blob(b'124'),
            signature=database_blob(b'346'),
            skip_key_check=True,
            timestamp=123,
            local_version=122,
            subscribed=False,
            infohash=os.urandom(20),
        )
        # Subscribed, updated - only this one should be downloaded
        chan3 = self.mock_session.lm.mds.ChannelMetadata(
            title="bla3",
            public_key=database_blob(b'125'),
            signature=database_blob(b'347'),
            skip_key_check=True,
            timestamp=123,
            local_version=122,
            subscribed=True,
            infohash=os.urandom(20),
        )
        mock_session_downloads_list = []

        def has_download(dl):
            return dl in mock_session_downloads_list

        self.mock_session.has_download = has_download
        self.torrents_added = 0

        def mock_download_channel(chan):
            self.torrents_added += 1
            self.assertEqual(chan, chan3)

        self.chanman.download_channel = mock_download_channel

        @db_session
        def fake_get_metainfo(infohash, timeout=30):
            return {'info': {'name': self.mock_session.lm.mds.
                    ChannelMetadata.get(infohash=database_blob(infohash)).dirname}}

        self.mock_session.lm.ltmgr = MockObject()
        self.mock_session.lm.ltmgr.get_metainfo = fake_get_metainfo
        self.mock_session.lm.ltmgr.metainfo_requests = {}

        # Manually fire the channel updates checking routine
        self.chanman.check_channels_updates()
        # download_channel should only fire once - for the original subscribed channel
        self.assertEqual(1, self.torrents_added)

        # Check that downloaded, but not yet processed channel torrent is added to the processing queue
        class MockDownload(object):
            def get_state(self):
                class MockState(object):
                    def get_status(self):
                        return DLSTATUS_SEEDING

                return MockState()

        self.mock_session.get_download = lambda c: MockDownload() if c in mock_session_downloads_list else None

        mock_session_downloads_list.append(bytes(chan3.infohash))
        dirs_processed = []

        def process_channel_dir(c):
            dirs_processed.append(c)
            # Only the subscribed, but not processed (with local_version < timestamp) channel should be processed
            self.assertEqual(c, chan3)

        self.chanman.process_channel_dir_threaded = process_channel_dir

        # Manually fire the channel updates checking routine
        self.chanman.check_channels_updates()
        yield self.chanman.process_queued_channels()

        # The queue should be empty afterwards
        self.assertEqual(0, len(self.chanman.channels_processing_queue))
        self.assertEqual(1, len(dirs_processed))

    @inlineCallbacks
    def test_remove_cruft_channels(self):
        with db_session:
            # Our personal chan is created, then updated, so there are 2 files on disk and there are 2 torrents:
            # the old one and the new one
            my_chan = self.generate_personal_channel()
            my_chan.commit_channel_torrent()
            my_chan_old_infohash = my_chan.infohash
            _ = self.mock_session.lm.mds.TorrentMetadata.from_dict(
                dict(self.torrent_template, origin_id=my_chan.id_, status=NEW)
            )
            my_chan.commit_channel_torrent()

            # Now we add an external channel we are subscribed to.
            chan2 = self.mock_session.lm.mds.ChannelMetadata(
                title="bla1",
                infohash=database_blob(b'123'),
                public_key=database_blob(b'123'),
                signature=database_blob(b'345'),
                skip_key_check=True,
                timestamp=123,
                local_version=123,
                subscribed=True,
            )

            # Another external channel, but there is a catch: we recently unsubscribed from it
            chan3 = self.mock_session.lm.mds.ChannelMetadata(
                title="bla2",
                infohash=database_blob(b'124'),
                public_key=database_blob(b'124'),
                signature=database_blob(b'346'),
                skip_key_check=True,
                timestamp=123,
                local_version=123,
                subscribed=False,
            )
            self.mock_session.lm.mds.TorrentMetadata(
                title='bla2 content', infohash=database_blob(random_infohash()), origin_id=chan3.id_
            )

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
            # Downloads for the personal channel
            MockDownload(database_blob(bytes(my_chan_old_infohash)), my_chan.dirname),
            MockDownload(database_blob(bytes(my_chan.infohash)), my_chan.dirname),
            # Downloads for the updated external channel: "old ones" and "recent"
            MockDownload(database_blob(b'12331244'), chan2.dirname),
            MockDownload(database_blob(bytes(chan2.infohash)), chan2.dirname),
            # Downloads for the unsubscribed external channel
            MockDownload(database_blob(b'1231551'), chan3.dirname),
            MockDownload(database_blob(bytes(chan3.infohash)), chan3.dirname),
            # Orphaned download
            MockDownload(database_blob(b'333'), u"blabla"),
        ]

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

        # Test cleaning unsubscribed channel.
        self.chanman.clean_unsubscribed_channels()
        yield self.chanman.process_queued_channels()
        with db_session:
            # chan3 is in the cache, so we need to update it from db to see the changes
            chan3 = self.mock_session.lm.mds.ChannelMetadata[chan3.rowid]
            self.assertEqual(chan3.local_version, 0)
            self.assertEqual(len(chan3.contents), 0)

        # Test removing cruft channels
        self.chanman.remove_cruft_channels()
        yield self.chanman.process_queued_channels()
        # We want to remove torrents for (a) deleted channels and (b) unsubscribed channels
        assertCountEqual(
            self,
            self.remove_list,
            [
                (mock_dl_list[0], False),
                (mock_dl_list[2], False),
                (mock_dl_list[4], True),
                (mock_dl_list[5], True),
                (mock_dl_list[6], True),
            ],
        )


    @trial_timeout(20)
    @inlineCallbacks
    def test_reject_malformed_channel(self):
        with db_session:
            channel = self.mock_session.lm.mds.ChannelMetadata(title="bla1", public_key=database_blob(b'123'),
                                                               infohash=os.urandom(20))
        self.mock_session.config = MockObject()
        self.mock_session.config.get_state_dir = lambda: None
        self.mock_session.lm.ltmgr = MockObject()

        def mock_get_metainfo_bad(_, timeout=None):
            return {b'info': {b'name': b'bla'}}

        def mock_get_metainfo_good(_, timeout=None):
            return {b'info': {b'name': channel.dirname.encode('utf-8')}}

        self.initiated_download = False

        def mock_download_from_tdef(_, __, hidden=None):
            self.initiated_download = True
            mock_dl = MockObject()
            mock_dl.finished_deferred = succeed(None)
            return mock_dl
        self.mock_session.start_download_from_tdef = mock_download_from_tdef

        # Check that we skip channels with incorrect dirnames
        self.mock_session.lm.ltmgr.get_metainfo = mock_get_metainfo_bad
        yield self.chanman.download_channel(channel)
        self.assertFalse(self.initiated_download)

        # Check that we download channels with correct dirname
        self.mock_session.lm.ltmgr.get_metainfo = mock_get_metainfo_good
        yield self.chanman.download_channel(channel)
        self.assertTrue(self.initiated_download)
