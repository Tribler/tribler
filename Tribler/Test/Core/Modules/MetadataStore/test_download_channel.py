import os

from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.channels import load_blob, download_channel
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout


class TestDownloadChannel(TestAsServer):
    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    TEST_FILES_DIR = os.path.abspath(os.path.join(
        FILE_DIR, u"../../data/MetadataStore/"))
    CHANNEL_BLOB_FILENAME = "Test channel 1.mdblob"
    CHANNEL_TORRENT_FILENAME = "Test channel 1.torrent"

    def setUpPreSession(self):
        super(TestDownloadChannel, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_megacache_enabled(True)

    @trial_timeout(20)
    def test_download_channel(self):
        tdef = TorrentDef.load(os.path.join(self.TEST_FILES_DIR, self.CHANNEL_TORRENT_FILENAME))
        self.setup_seeder(tdef, self.TEST_FILES_DIR, port=7000)
        with db_session:
            channel = load_blob(
                self.session.mds,
                os.path.join(
                    self.TEST_FILES_DIR,
                    self.CHANNEL_BLOB_FILENAME))
            channel_infohash = channel.infohash
            channel_title = channel.title

        dl_finished = download_channel(self.session, channel_infohash, channel_title)
        # FIXME: possible race condition here?
        dl = self.session.get_downloads()[0]
        dl.add_peer(('127.0.0.1', 7000))  # Used for testing

        def check_channel_contents(_):
            with db_session:
                md_list = channel.contents_list
                # TODO: add more sophisticated checks
                self.assertEqual(len(md_list), channel.version)
        dl_finished.addCallback(check_channel_contents)

        dl_finished.addCallback(lambda _: self.stop_seeder)

        return dl_finished
