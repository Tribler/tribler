# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import os
import json
import time
from unittest.case import skip

from Tribler.Test.test_as_server import TestGuiAsServer, TESTS_DATA_DIR

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import dlstatus_strings

DEBUG = True


class TestMetadataCommunity(TestGuiAsServer):

    @skip("Automatic thumbnail generation has been disabled and this test will never pass")
    def test_add_metadata(self):
        def do_overview():
            self.screenshot('Resulting metadata')
            self.quit()

        def do_modifications(torrentfilename):
            infohash = TorrentDef.load(torrentfilename).get_infohash()

            self.frame.librarylist.Select(infohash)
            torrent = self.guiUtility.torrentsearch_manager.getTorrentByInfohash(infohash)

            def check_for_modifications():
                modifications = self.guiUtility.torrentsearch_manager.getTorrentModifications(torrent)
                videoinfo_valid = False
                swiftthumbnails_valid = False
                for modification in modifications:
                    if modification.name == 'swift-thumbs' and modification.value:
                        swiftthumbnails_valid = True
                    if modification.name == 'video-info' and modification.value:
                        videoinfo_dict = json.loads(modification.value)
                        if videoinfo_dict['duration'] and videoinfo_dict['resolution']:
                            videoinfo_valid = (videoinfo_dict['resolution'] == [640, 480]) and (
                                videoinfo_dict['duration'] == 6)

                return videoinfo_valid and swiftthumbnails_valid
            self.CallConditional(10, check_for_modifications, lambda: self.Call(
                5, do_overview), 'No valid channel modifications received')

        def do_thumbnails(torrentfilename):
            # FIXME(lipu): fix the thumbnail path to use metadata
            thumb_dir = os.path.join(u"", '8bb88a02da691636a7ed929b87d467f24700e490')
            self.CallConditional(120, lambda: os.path.isdir(thumb_dir) and len(
                os.listdir(thumb_dir)) > 0, lambda: do_modifications(torrentfilename), 'No thumbnails were created')

        def do_download_torrent(torrentfilename):
            download = self.guiUtility.frame.startDownload(torrentfilename=torrentfilename, destdir=self.getDestDir())

            self.guiUtility.ShowPage('my_files')
            self.Call(5, lambda: download.add_peer(("127.0.0.1", self.session2.get_listen_port())))
            self.CallConditional(10, lambda: download.get_progress() == 1.0, lambda:
                                 do_thumbnails(torrentfilename), 'Failed to download torrent in time')

        def do_create_local_torrent():
            torrentfilename = self.setupSeeder()
            do_download_torrent(torrentfilename)

        self.startTest(do_create_local_torrent)

    def startTest(self, callback):
        def get_and_modify_dispersy():
            from Tribler.dispersy.endpoint import NullEndpoint

            self._logger.debug("Frame ready, replacing dispersy endpoint")
            dispersy = self.session.get_dispersy_instance()
            dispersy._endpoint = NullEndpoint()
            dispersy._endpoint.open(dispersy)

            callback()

        super(TestMetadataCommunity, self).startTest(get_and_modify_dispersy)

    def setupSeeder(self):
        from Tribler.Core.Session import Session
        from Tribler.Core.TorrentDef import TorrentDef
        from Tribler.Core.DownloadConfig import DownloadStartupConfig

        self.setUpPreSession()
        self.config.set_libtorrent(True)

        self.config2 = self.config.copy()

        self.session2 = Session(self.config2, ignore_singleton=True)
        upgrader = self.session2.prestart()
        while not upgrader.is_done:
            time.sleep(0.1)
        assert not upgrader.failed, upgrader.current_status
        self.session2.start()

        tdef = TorrentDef()
        tdef.add_content(os.path.join(TESTS_DATA_DIR, "video.avi"))
        tdef.set_tracker("http://fake.net/announce")
        tdef.finalize()
        torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(TESTS_DATA_DIR)  # basedir of the file we are seeding
        d = self.session2.start_download(tdef, dscfg)
        d.set_state_callback(self.seeder_state_callback)

        return torrentfn

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("seeder: %s %s %s", repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()], ds.get_progress())
        return 5.0, False

    def setUp(self):
        super(TestMetadataCommunity, self).setUp()
        self.session2 = None

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            time.sleep(10)

        super(TestMetadataCommunity, self).tearDown()
