
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.path_util import Path
from Tribler.Core.Utilities.utilities import succeed
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout
from Tribler.pyipv8.ipv8.database import database_blob

DATA_DIR = Path(__file__).parent / '..' / '..' / 'data'
CHANNEL_DIR = DATA_DIR / 'sample_channel'
CHANNEL_TORRENT = CHANNEL_DIR / 'channel.torrent'
CHANNEL_METADATA = CHANNEL_DIR / 'channel.mdblob'
CHANNEL_TORRENT_UPDATED = CHANNEL_DIR / 'channel_upd.torrent'
CHANNEL_METADATA_UPDATED = CHANNEL_DIR / 'channel_upd.mdblob'


class TestChannelDownload(TestAsServer):
    def setUpPreSession(self):
        super(TestChannelDownload, self).setUpPreSession()
        self.config.set_chant_enabled(True)
        self.config.set_libtorrent_enabled(True)

    @timeout(20)
    async def test_channel_update_and_download(self):
        """
        Test whether we can successfully update a channel and download the new version
        """
        # First we have to manually add the old version
        old_payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA)
        with db_session:
            old_channel = self.session.mds.ChannelMetadata.from_payload(old_payload)
            chan_dir = CHANNEL_DIR / old_channel.dirname

        self.session.mds.process_channel_dir(chan_dir, old_payload.public_key, old_payload.id_)

        channel_tdef = TorrentDef.load(CHANNEL_TORRENT_UPDATED)
        libtorrent_port = self.get_port()
        await self.setup_seeder(channel_tdef, CHANNEL_DIR, libtorrent_port)

        payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA_UPDATED)
        # Download the channel in our session
        with db_session:
            self.session.mds.process_payload(payload)
            channel = self.session.mds.ChannelMetadata.get(signature=payload.signature)

        def fake_get_metainfo(infohash, timeout=30):
            return succeed({b'info': {b'name': channel.dirname.encode('utf-8')}})

        self.session.ltmgr.get_metainfo = fake_get_metainfo
        # The leecher should be hinted to leech from localhost. Thus, we must extend start_download_from_tdef
        # and get_metainfo to provide the hint.
        original_start_download_from_tdef = self.session.ltmgr.start_download

        def hinted_start_download(tdef=None, config=None, hidden=False, original_call=True):
            download = original_start_download_from_tdef(tdef=tdef, config=config, hidden=hidden)
            download.add_peer(("127.0.0.1", self.seeder_session.config.get_libtorrent_port()))
            return download

        self.session.ltmgr.start_download = hinted_start_download
        await self.session.gigachannel_manager.download_channel(channel)
        await self.session.gigachannel_manager.process_queued_channels()

        with db_session:
            # There should be 8 torrents + 1 channel torrent
            channel2 = self.session.mds.ChannelMetadata.get(public_key=database_blob(payload.public_key))
            self.assertEqual(channel2.timestamp, channel2.local_version)
            self.assertEqual(1565621688018, channel2.timestamp)
            self.assertEqual(8, self.session.mds.ChannelNode.select().count())
