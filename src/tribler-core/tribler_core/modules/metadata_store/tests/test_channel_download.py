from ipv8.database import database_blob
from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.serialization import ChannelMetadataPayload
from tribler_core.tests.tools.common import TESTS_DATA_DIR

CHANNEL_DIR = TESTS_DATA_DIR / 'sample_channel'
CHANNEL_TORRENT = CHANNEL_DIR / 'channel.torrent'
CHANNEL_TORRENT_UPDATED = CHANNEL_DIR / 'channel_upd.torrent'
CHANNEL_METADATA = CHANNEL_DIR / 'channel.mdblob'
CHANNEL_METADATA_UPDATED = CHANNEL_DIR / 'channel_upd.mdblob'


@pytest.mark.asyncio
@pytest.mark.timeout(20)
async def test_channel_update_and_download(
    enable_chant, enable_libtorrent, channel_tdef, channel_seeder_session, session
):
    """
    Test whether we can successfully update a channel and download the new version
    """
    # First we have to manually add the old version
    old_payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA)
    with db_session:
        old_channel = session.mds.ChannelMetadata.from_payload(old_payload)
        chan_dir = CHANNEL_DIR / old_channel.dirname

    session.mds.process_channel_dir(chan_dir, old_payload.public_key, old_payload.id_)

    payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA_UPDATED)
    # Download the channel in our session
    with db_session:
        session.mds.process_payload(payload)
        channel = session.mds.ChannelMetadata.get(signature=payload.signature)

    def fake_get_metainfo(*args, **kwargs):
        return succeed(channel_tdef.get_metainfo())

    session.dlmgr.get_metainfo = fake_get_metainfo
    # The leecher should be hinted to leech from localhost. Thus, we must extend start_download_from_tdef
    # and get_metainfo to provide the hint.
    original_start_download_from_tdef = session.dlmgr.start_download

    def hinted_start_download(tdef=None, config=None, hidden=False):
        download = original_start_download_from_tdef(tdef=tdef, config=config, hidden=hidden)
        download.add_peer(("127.0.0.1", channel_seeder_session.config.get_libtorrent_port()))
        return download

    session.dlmgr.start_download = hinted_start_download
    await session.gigachannel_manager.download_channel(channel)
    await session.gigachannel_manager.process_queued_channels()

    with db_session:
        # There should be 8 torrents + 1 channel torrent
        channel2 = session.mds.ChannelMetadata.get(public_key=database_blob(payload.public_key))
        assert channel2.timestamp == channel2.local_version
        assert channel2.timestamp == 1565621688018
        assert session.mds.ChannelNode.select().count() == 8
