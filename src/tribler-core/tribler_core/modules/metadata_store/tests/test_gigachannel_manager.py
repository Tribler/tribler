from asyncio import Future
from datetime import datetime

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.gigachannel_manager import GigaChannelManager
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.utilities import succeed


class TestGigaChannelManager(TriblerCoreTest):
    @db_session
    def generate_personal_channel(self):
        chan = self.mock_session.mds.ChannelMetadata.create_channel(title="my test chan", description="test")
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        chan.add_torrent_to_channel(tdef, None)
        return chan

    async def setUp(self):
        await super(TestGigaChannelManager, self).setUp()
        self.torrent_template = {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}
        my_key = default_eccrypto.generate_key(u"curve25519")
        self.mock_session = MockObject()
        self.mock_session.mds = MetadataStore(":memory:", self.session_base_dir, my_key)
        self.mock_session.notifier = MockObject()
        self.mock_session.notifier.notify = lambda *_: None

        self.chanman = GigaChannelManager(self.mock_session)
        self.torrents_added = 0

    async def tearDown(self):
        self.mock_session.mds.shutdown()
        await super(TestGigaChannelManager, self).tearDown()

    async def test_update_my_channel(self):
        with db_session:
            chan = self.generate_personal_channel()
            chan.commit_channel_torrent()

            def mock_start_download(**_):
                self.torrents_added = 1

            self.mock_session.dlmgr = MockObject()
            self.mock_session.dlmgr.start_download = mock_start_download
            self.mock_session.config = MockObject()
            self.mock_session.config.get_state_dir = lambda: None
            #   self.mock_session.dlmgr.download_exists = lambda x: x == str(chan.infohash)

            # Check add personal channel on startup
            self.mock_session.dlmgr.download_exists = lambda _: False
            self.chanman.cancel_pending_task('service_channels')  # Disable looping call
            self.chanman.start()
            self.assertTrue(self.torrents_added)
            await self.chanman.shutdown()

            # Check skip already added personal channel
            self.mock_session.dlmgr.download_exists = lambda x: bytes(x) == bytes(chan.infohash)
            self.torrents_added = False
            self.chanman.start()
            self.chanman.check_channels_updates()
            self.assertFalse(self.torrents_added)
            await self.chanman.shutdown()

    async def test_check_channels_updates(self):
        # We add our personal channel in an inconsistent state to make sure the GigaChannel Manager will
        # not try to update it in the same way it should update other's channels
        with db_session:
            chan = self.generate_personal_channel()
            chan.commit_channel_torrent()
            chan.local_version -= 1

            # Subscribed, not updated
            self.mock_session.mds.ChannelMetadata(
                title="bla1",
                public_key=database_blob(b'123'),
                signature=database_blob(b'345'),
                skip_key_check=True,
                timestamp=123,
                local_version=123,
                subscribed=True,
                infohash=random_infohash(),
            )
            # Not subscribed, updated
            self.mock_session.mds.ChannelMetadata(
                title="bla2",
                public_key=database_blob(b'124'),
                signature=database_blob(b'346'),
                skip_key_check=True,
                timestamp=123,
                local_version=122,
                subscribed=False,
                infohash=random_infohash(),
            )
            # Subscribed, updated - only this one should be downloaded
            chan3 = self.mock_session.mds.ChannelMetadata(
                title="bla3",
                public_key=database_blob(b'125'),
                signature=database_blob(b'347'),
                skip_key_check=True,
                timestamp=123,
                local_version=122,
                subscribed=True,
                infohash=random_infohash(),
            )
            self.torrents_added = 0

            def mock_download_channel(chan1):
                self.torrents_added += 1
                self.assertEqual(chan1, chan3)

            self.chanman.download_channel = mock_download_channel

            @db_session
            def fake_get_metainfo(infohash, **_):
                return {
                    'info': {
                        'name': self.mock_session.mds.ChannelMetadata.get(infohash=database_blob(infohash)).dirname
                    }
                }

            self.mock_session.dlmgr = MockObject()
            self.mock_session.dlmgr.get_metainfo = fake_get_metainfo
            self.mock_session.dlmgr.metainfo_requests = {}
            self.mock_session.dlmgr.download_exists = lambda _: False

            # Manually fire the channel updates checking routine
            self.chanman.check_channels_updates()
            # download_channel should only fire once - for the original subscribed channel
            self.assertEqual(1, self.torrents_added)

            # Check that downloaded, but unprocessed channel torrent is added to the processing queue
            self.mock_session.dlmgr = MockObject()
            self.mock_session.dlmgr.download_exists = lambda _: True

            class MockDownload(object):
                def get_state(self):
                    class MockState(object):
                        def get_status(self):
                            return DLSTATUS_SEEDING

                    return MockState()

            self.mock_session.dlmgr.get_download = lambda _: MockDownload()

            def mock_process_channel_dir(c, _):
                # Only the subscribed, but not processed (with local_version < timestamp) channel should be processed
                self.assertEqual(c, chan3)

            self.chanman.process_channel_dir = mock_process_channel_dir

            # Manually fire the channel updates checking routine
            self.chanman.check_channels_updates()
            await self.chanman.process_queued_channels()

            # The queue should be empty afterwards
            self.assertEqual(0, len(self.chanman.channels_processing_queue))

    async def test_remove_cruft_channels(self):
        with db_session:
            # Our personal chan is created, then updated, so there are 2 files on disk and there are 2 torrents:
            # the old one and the new one
            my_chan = self.generate_personal_channel()
            my_chan.commit_channel_torrent()
            my_chan_old_infohash = my_chan.infohash
            _ = self.mock_session.mds.TorrentMetadata.from_dict(
                dict(self.torrent_template, origin_id=my_chan.id_, status=NEW)
            )
            my_chan.commit_channel_torrent()

            # Now we add an external channel we are subscribed to.
            chan2 = self.mock_session.mds.ChannelMetadata(
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
            chan3 = self.mock_session.mds.ChannelMetadata(
                title="bla2",
                infohash=database_blob(b'124'),
                public_key=database_blob(b'124'),
                signature=database_blob(b'346'),
                skip_key_check=True,
                timestamp=123,
                local_version=123,
                subscribed=False,
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

        def mock_get_channel_downloads(**_):
            return mock_dl_list

        self.remove_list = []

        def mock_remove(infohash, remove_content=False):
            d = Future()
            d.set_result(None)
            self.remove_list.append((infohash, remove_content))
            return d

        self.mock_session.dlmgr = MockObject()
        self.mock_session.dlmgr.get_channel_downloads = mock_get_channel_downloads
        self.chanman.session.dlmgr.remove_download = mock_remove

        self.chanman.remove_cruft_channels()
        await self.chanman.process_queued_channels()
        # We want to remove torrents for (a) deleted channels and (b) unsubscribed channels
        self.assertCountEqual(
            self.remove_list,
            [
                (mock_dl_list[0], False),
                (mock_dl_list[2], False),
                (mock_dl_list[4], True),
                (mock_dl_list[5], True),
                (mock_dl_list[6], True),
            ],
        )

    @timeout(20)
    async def test_reject_malformed_channel(self):
        with db_session:
            channel = self.mock_session.mds.ChannelMetadata(
                title="bla1", public_key=database_blob(b'123'), infohash=random_infohash()
            )
        self.mock_session.config = MockObject()
        self.mock_session.config.get_state_dir = lambda: None
        self.mock_session.dlmgr = MockObject()

        def mock_get_metainfo_bad(_, timeout=None):
            return succeed({b'info': {b'name': b'bla'}})

        def mock_get_metainfo_good(_, timeout=None):
            return succeed({b'info': {b'name': channel.dirname.encode('utf-8')}})

        self.initiated_download = False

        def mock_download_from_tdef(*_, **__):
            self.initiated_download = True
            mock_dl = MockObject()
            mock_dl.future_finished = succeed(None)
            return mock_dl

        self.mock_session.dlmgr.start_download = mock_download_from_tdef

        # Check that we skip channels with incorrect dirnames
        self.mock_session.dlmgr.get_metainfo = mock_get_metainfo_bad
        await self.chanman.download_channel(channel)
        self.assertFalse(self.initiated_download)

        # Check that we download channels with correct dirname
        self.mock_session.dlmgr.get_metainfo = mock_get_metainfo_good
        await self.chanman.download_channel(channel)
        self.assertTrue(self.initiated_download)
