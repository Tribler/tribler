import asyncio
from asyncio import Future
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from ipv8.database import database_blob
from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.gigachannel_manager import GigaChannelManager
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.utilities.random_utils import random_infohash

update_metainfo = None


@pytest.fixture
def torrent_template():
    return {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}


@pytest.fixture
def personal_channel(session):
    global update_metainfo
    with db_session:
        chan = session.mds.ChannelMetadata.create_channel(title="my test chan", description="test")
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        chan.add_torrent_to_channel(tdef, None)
        update_metainfo = chan.commit_channel_torrent()
        return chan


@pytest.fixture
async def channel_manager(session):
    chanman = GigaChannelManager(session)
    yield chanman
    await chanman.shutdown()


@pytest.mark.asyncio
async def test_regen_personal_channel_no_torrent(enable_chant, personal_channel, channel_manager, mock_dlmgr, session):
    """
    Test regenerating a non-existing personal channel torrent at startup
    """
    session.dlmgr.get_download = lambda _: None
    channel_manager.regenerate_channel_torrent = Mock()
    await channel_manager.check_and_regen_personal_channels()
    channel_manager.regenerate_channel_torrent.assert_called_once()


@pytest.mark.asyncio
async def test_regen_personal_channel_damaged_torrent(
    enable_chant, personal_channel, channel_manager, mock_dlmgr, session
):
    """
    Test regenerating a damaged personal channel torrent at startup
    """
    complete = Future()

    async def mock_regen(*_, **__):
        complete.set_result(True)

    channel_manager.check_and_regen_personal_channel_torrent = mock_regen
    channel_manager.start()
    await complete


@pytest.mark.asyncio
async def test_regenerate_channel_torrent(enable_chant, personal_channel, channel_manager, mock_dlmgr, session):
    with db_session:
        chan_pk, chan_id = personal_channel.public_key, personal_channel.id_
        channel_dir = Path(session.mds.ChannelMetadata._channels_dir) / Path(personal_channel.dirname)
        for f in channel_dir.iterdir():
            f.unlink()

    # Test trying to regenerate a non-existing channel
    assert await channel_manager.regenerate_channel_torrent(chan_pk, chan_id + 1) is None

    # Mock existing downloads removal-related functions
    session.dlmgr.get_downloads_by_name = lambda *_: [Mock()]
    downloads_to_remove = []

    async def mock_remove_download(download_obj, **_):
        downloads_to_remove.append(download_obj)

    session.dlmgr.remove_download = mock_remove_download

    # Test regenerating an empty channel
    session.mds.ChannelMetadata.consolidate_channel_torrent = lambda *_: None
    assert await channel_manager.regenerate_channel_torrent(chan_pk, chan_id) is None
    assert len(downloads_to_remove) == 1

    # Test regenerating a non-empty channel
    channel_manager.updated_my_channel = Mock()
    session.mds.ChannelMetadata.consolidate_channel_torrent = lambda *_: Mock()
    with patch("tribler_core.modules.libtorrent.torrentdef.TorrentDef.load_from_dict"):
        await channel_manager.regenerate_channel_torrent(chan_pk, chan_id)
        channel_manager.updated_my_channel.assert_called_once()


def test_updated_my_channel(enable_chant, personal_channel, channel_manager, mock_dlmgr, session, tmpdir):
    tdef = TorrentDef.load_from_dict(update_metainfo)
    session.dlmgr.start_download = Mock()
    session.dlmgr.download_exists = lambda *_: False
    session.mds.channels_dir = "bla"
    session.config.get_state_dir = lambda: Path(tmpdir / "foo")
    channel_manager.updated_my_channel(tdef)
    session.dlmgr.start_download.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_regen_personal_channel_torrent(
    enable_chant, personal_channel, channel_manager, mock_dlmgr, session
):
    with db_session:
        chan_pk, chan_id = personal_channel.public_key, personal_channel.id_
        chan_download = Mock()

        async def mock_wait(*_):
            pass

        chan_download.wait_for_status = mock_wait
        # Test wait for status OK
        await channel_manager.check_and_regen_personal_channel_torrent(chan_pk, chan_id, chan_download, timeout=0.5)

        async def mock_wait_2(*_):
            await asyncio.sleep(3)

        chan_download.wait_for_status = mock_wait_2
        # Test timeout waiting for seeding state and then regen

        f = Mock()

        async def mock_regen(*_):
            f()

        channel_manager.regenerate_channel_torrent = mock_regen
        await channel_manager.check_and_regen_personal_channel_torrent(chan_pk, chan_id, chan_download, timeout=0.5)
        f.assert_called_once()


@pytest.mark.asyncio
async def test_check_channels_updates(enable_chant, personal_channel, channel_manager, mock_dlmgr, session):
    torrents_added = 0
    # We add our personal channel in an inconsistent state to make sure the GigaChannel Manager will
    # not try to update it in the same way it should update other's channels
    with db_session:
        my_channel = session.mds.ChannelMetadata.get_my_channels().first()
        my_channel.local_version -= 1

        # Subscribed, not updated
        session.mds.ChannelMetadata(
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
        session.mds.ChannelMetadata(
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
        chan3 = session.mds.ChannelMetadata(
            title="bla3",
            public_key=database_blob(b'125'),
            signature=database_blob(b'347'),
            skip_key_check=True,
            timestamp=123,
            local_version=122,
            subscribed=True,
            infohash=random_infohash(),
        )

        def mock_download_channel(chan1):
            nonlocal torrents_added
            torrents_added += 1
            assert chan1 == chan3

        channel_manager.download_channel = mock_download_channel

        @db_session
        def fake_get_metainfo(infohash, **_):
            return {'info': {'name': session.mds.ChannelMetadata.get(infohash=database_blob(infohash)).dirname}}

        session.dlmgr.get_metainfo = fake_get_metainfo
        session.dlmgr.metainfo_requests = {}
        session.dlmgr.download_exists = lambda _: False

        # Manually fire the channel updates checking routine
        channel_manager.check_channels_updates()
        # download_channel should only fire once - for the original subscribed channel
        assert torrents_added == 1

        # Check that downloaded, but unprocessed channel torrent is added to the processing queue
        session.dlmgr = MockObject()
        session.dlmgr.download_exists = lambda _: True

        mock_download = Mock()
        mock_download.get_state.get_status = DLSTATUS_SEEDING

        session.dlmgr.get_download = lambda _: mock_download

        def mock_process_channel_dir(c, _):
            # Only the subscribed, but not processed (with local_version < timestamp) channel should be processed
            assert c == chan3

        channel_manager.process_channel_dir = mock_process_channel_dir

        # Manually fire the channel updates checking routine
        channel_manager.check_channels_updates()
        await channel_manager.process_queued_channels()

        # The queue should be empty afterwards
        assert not channel_manager.channels_processing_queue


@pytest.mark.asyncio
async def test_remove_cruft_channels(
    torrent_template, enable_chant, personal_channel, channel_manager, mock_dlmgr, session
):
    remove_list = []
    with db_session:
        # Our personal chan is created, then updated, so there are 2 files on disk and there are 2 torrents:
        # the old one and the new one
        personal_channel = session.mds.ChannelMetadata.get_my_channels().first()
        my_chan_old_infohash = personal_channel.infohash
        _ = session.mds.TorrentMetadata.from_dict(dict(torrent_template, origin_id=personal_channel.id_, status=NEW))
        personal_channel.commit_channel_torrent()

        # Now we add an external channel we are subscribed to.
        chan2 = session.mds.ChannelMetadata(
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
        chan3 = session.mds.ChannelMetadata(
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
        MockDownload(database_blob(bytes(my_chan_old_infohash)), personal_channel.dirname),
        MockDownload(database_blob(bytes(personal_channel.infohash)), personal_channel.dirname),
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

    def mock_remove(infohash, remove_content=False):
        nonlocal remove_list
        d = Future()
        d.set_result(None)
        remove_list.append((infohash, remove_content))
        return d

    session.dlmgr.get_channel_downloads = mock_get_channel_downloads
    session.dlmgr.remove_download = mock_remove

    channel_manager.remove_cruft_channels()
    await channel_manager.process_queued_channels()
    # We want to remove torrents for (a) deleted channels and (b) unsubscribed channels
    assert remove_list == [
        (mock_dl_list[0], False),
        (mock_dl_list[2], False),
        (mock_dl_list[4], True),
        (mock_dl_list[5], True),
        (mock_dl_list[6], True),
    ]


initiated_download = False


@pytest.mark.asyncio
async def test_reject_malformed_channel(enable_chant, channel_manager, mock_dlmgr, session):
    global initiated_download
    with db_session:
        channel = session.mds.ChannelMetadata(
            title="bla1", public_key=database_blob(b'123'), infohash=random_infohash()
        )
    session.config = Mock()
    session.config.get_state_dir = lambda: None

    def mock_get_metainfo_bad(*args, **kwargs):
        return succeed({b'info': {b'name': b'bla'}})

    def mock_get_metainfo_good(*args, **kwargs):
        return succeed({b'info': {b'name': channel.dirname.encode('utf-8')}})

    initiated_download = False

    def mock_download_from_tdef(*_, **__):
        global initiated_download
        initiated_download = True
        mock_dl = MockObject()
        mock_dl.future_finished = succeed(None)
        return mock_dl

    session.dlmgr.start_download = mock_download_from_tdef

    # Check that we skip channels with incorrect dirnames
    session.dlmgr.get_metainfo = mock_get_metainfo_bad
    await channel_manager.download_channel(channel)
    assert not initiated_download

    with patch.object(TorrentDef, "__init__", lambda *_, **__: None):
        # Check that we download channels with correct dirname
        session.dlmgr.get_metainfo = mock_get_metainfo_good
        await channel_manager.download_channel(channel)
        assert initiated_download
