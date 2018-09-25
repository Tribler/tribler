import os

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.test_as_server import TestAsServer


class TestChannelDownload(TestAsServer):

    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', 'data')
    CHANNEL_DIR = os.path.join(DATA_DIR, 'sample_channel')
    CHANNEL_TORRENT = os.path.join(CHANNEL_DIR, 'channel.torrent')
    CHANNEL_METADATA = os.path.join(CHANNEL_DIR, 'channel.mdblob')

    def setUpPreSession(self):
        super(TestChannelDownload, self).setUpPreSession()
        self.config.set_chant_enabled(True)
        self.config.set_libtorrent_enabled(True)

    @inlineCallbacks
    def test_channel_download(self):
        """
        Test whether we can successfully setup a channel and download it from another peer
        """
        channel_tdef = TorrentDef.load(self.CHANNEL_TORRENT)
        libtorrent_port = get_random_port()
        yield self.setup_seeder(channel_tdef, self.CHANNEL_DIR, libtorrent_port)

        payload = ChannelMetadataPayload.from_file(self.CHANNEL_METADATA)

        # Download the channel in our session
        download, finished_deferred = self.session.lm.update_channel(payload)
        download.add_peer(("127.0.0.1", self.seeder_session.config.get_libtorrent_port()))
        yield finished_deferred

        with db_session:
            self.assertTrue(list(self.session.lm.mds.ChannelMetadata.select()))
