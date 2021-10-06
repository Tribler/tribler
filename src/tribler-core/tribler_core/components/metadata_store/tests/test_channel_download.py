from asynctest import Mock

from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler_core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler_core.components.libtorrent.settings import LibtorrentSettings
from tribler_core.components.libtorrent.torrentdef import TorrentDef
from tribler_core.components.gigachannel_manager.gigachannel_manager import GigaChannelManager
from tribler_core.components.metadata_store.db.serialization import ChannelMetadataPayload
from tribler_core.tests.tools.common import TESTS_DATA_DIR

CHANNEL_DIR = TESTS_DATA_DIR / 'sample_channel'
CHANNEL_TORRENT = CHANNEL_DIR / 'channel.torrent'
CHANNEL_TORRENT_UPDATED = CHANNEL_DIR / 'channel_upd.torrent'
CHANNEL_METADATA = CHANNEL_DIR / 'channel.mdblob'
CHANNEL_METADATA_UPDATED = CHANNEL_DIR / 'channel_upd.mdblob'


@pytest.fixture
def channel_tdef():
    return TorrentDef.load(TESTS_DATA_DIR / 'sample_channel' / 'channel_upd.torrent')


@pytest.fixture
async def channel_seeder(channel_tdef, tmp_path, loop):
    config = LibtorrentSettings()
    config.dht = False
    config.upnp = False
    config.natpmp = False
    config.lsd = False
    seeder_dlmgr = DownloadManager(state_dir=tmp_path, config=config, notifier=Mock(), peer_mid=b"0000")
    seeder_dlmgr.initialize()
    dscfg_seed = DownloadConfig()
    dscfg_seed.set_dest_dir(TESTS_DATA_DIR / 'sample_channel')
    upload = seeder_dlmgr.start_download(tdef=channel_tdef, config=dscfg_seed)
    await upload.wait_for_status(DLSTATUS_SEEDING)
    yield seeder_dlmgr
    await seeder_dlmgr.shutdown()


@pytest.fixture
async def gigachannel_manager(metadata_store, download_manager):
    gigachannel_manager = GigaChannelManager(
        state_dir=metadata_store.channels_dir.parent,
        download_manager=download_manager,
        metadata_store=metadata_store,
        notifier=Mock(),
    )
    yield gigachannel_manager
    await gigachannel_manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.timeout(20)
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

    def hinted_start_download(tdef=None, config=None, hidden=False):
        download = original_start_download_from_tdef(tdef=tdef, config=config, hidden=hidden)
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
