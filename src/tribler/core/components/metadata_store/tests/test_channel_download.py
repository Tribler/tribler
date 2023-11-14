from unittest.mock import MagicMock

import pytest
from ipv8.util import succeed
from pony.orm import db_session

from tribler.core.components.gigachannel_manager.gigachannel_manager import GigaChannelManager
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.settings import LibtorrentSettings
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.metadata_store.db.serialization import ChannelMetadataPayload
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.utilities.simpledefs import DownloadStatus

CHANNEL_DIR = TESTS_DATA_DIR / 'sample_channel'
CHANNEL_TORRENT = CHANNEL_DIR / 'channel.torrent'
CHANNEL_TORRENT_UPDATED = CHANNEL_DIR / 'channel_upd.torrent'
CHANNEL_METADATA = CHANNEL_DIR / 'channel.mdblob'
CHANNEL_METADATA_UPDATED = CHANNEL_DIR / 'channel_upd.mdblob'


# pylint: disable=redefined-outer-name

@pytest.fixture
async def channel_tdef():
    return await TorrentDef.load(TESTS_DATA_DIR / 'sample_channel' / 'channel_upd.torrent')


@pytest.fixture
async def channel_seeder(channel_tdef, tmp_path_factory):  # pylint: disable=unused-argument
    config = LibtorrentSettings()
    config.dht = False
    config.upnp = False
    config.natpmp = False
    config.lsd = False
    seeder_dlmgr = DownloadManager(state_dir=tmp_path_factory.mktemp('state_dir'), config=config, notifier=MagicMock(),
                                   peer_mid=b"0000")
    seeder_dlmgr.metadata_tmpdir = tmp_path_factory.mktemp('metadata_tmpdir')
    seeder_dlmgr.initialize()
    dscfg_seed = DownloadConfig()
    dscfg_seed.set_dest_dir(TESTS_DATA_DIR / 'sample_channel')
    upload = await seeder_dlmgr.start_download(tdef=channel_tdef, config=dscfg_seed)
    await upload.wait_for_status(DownloadStatus.SEEDING)
    yield seeder_dlmgr
    await seeder_dlmgr.shutdown()


@pytest.fixture
async def gigachannel_manager(metadata_store, download_manager: DownloadManager):
    manager = GigaChannelManager(
        state_dir=metadata_store.channels_dir.parent,
        download_manager=download_manager,
        metadata_store=metadata_store,
        notifier=MagicMock(),
    )
    yield manager
    await manager.shutdown()


@pytest.mark.looptime(False)
async def test_channel_update_and_download(
        channel_tdef, channel_seeder, metadata_store, download_manager, gigachannel_manager
):
    """
    Test whether we can successfully update a channel and download the new version
    """

    # First we have to manually add the old version
    old_payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA)
    with db_session:
        old_channel = metadata_store.ChannelMetadata.from_payload(old_payload)
        chan_dir = CHANNEL_DIR / old_channel.dirname

    metadata_store.process_channel_dir(chan_dir, old_payload.public_key, old_payload.id_)

    payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA_UPDATED)
    # Download the channel in our session
    with db_session:
        metadata_store.process_payload(payload)
        channel = metadata_store.ChannelMetadata.get(signature=payload.signature)

    def fake_get_metainfo(*args, **kwargs):
        return succeed(channel_tdef.get_metainfo())

    download_manager.get_metainfo = fake_get_metainfo
    # The leecher should be hinted to leech from localhost. Thus, we must extend start_download_from_tdef
    # and get_metainfo to provide the hint.
    original_start_download_from_tdef = download_manager.start_download

    async def hinted_start_download(tdef=None, config=None, hidden=False):
        download = await original_start_download_from_tdef(tdef=tdef, config=config, hidden=hidden)
        download.add_peer(("127.0.0.1", channel_seeder.libtorrent_port))
        return download

    download_manager.start_download = hinted_start_download
    await gigachannel_manager.download_channel(channel)
    await gigachannel_manager.process_queued_channels()

    with db_session:
        # There should be 8 torrents + 1 channel torrent
        channel2 = metadata_store.ChannelMetadata.get(public_key=payload.public_key)
        assert channel2.timestamp == channel2.local_version
        assert channel2.timestamp == 1565621688018
        assert metadata_store.ChannelNode.select().count() == 8
