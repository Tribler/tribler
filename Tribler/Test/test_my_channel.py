# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import os
import sys
import json
import time
import binascii
import threading

from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef

DEBUG = True
class TestMyChannel(TestGuiAsServer):

    def test_rss_import(self):
        def do_files_check():
            self.screenshot('Torrents imported')
            self.quit()

        def added_rss():
            self.screenshot('Rssfeed added')

            # switch to files tab
            mt_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage torrents")
            self.managechannel.notebook.SetSelection(mt_index)

            managefiles = self.managechannel.fileslist
            self.CallConditional(60, lambda: len(managefiles.GetItems()) > 0, do_files_check, 'Channel did not have torrents')

        def do_rss():
            self.managechannel.rss_url.SetValue('http://www.clearbits.net/feeds/creator/184-pioneer-one.rss')
            self.managechannel.OnAddRss()

            # switch to manage tab
            m_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage")
            self.managechannel.notebook.SetSelection(m_index)

            self.Call(1, added_rss)

        def do_create():
            self.managechannel = self.frame.managechannel

            self.managechannel.name.SetValue('UNITTEST')
            self.managechannel.description.SetValue('Channel created for UNITTESTING purposes')

            self.managechannel.Save()
            self.CallConditional(60, lambda: self.frame.managechannel.channel, do_rss, 'Channel instance did not arrive at managechannel')

        def do_page():
            self.guiUtility.ShowPage('mychannel')
            self.Call(1, do_create)

        self.startTest(do_page)

    def test_add_torrents_playlists(self):

        def do_overview():
            self.guiUtility.showChannel(self.managechannel.channel)
            self.screenshot('Resulting channel')
            self.quit()

        def do_modifications(torrentfilename):
            infohash = TorrentDef.load(torrentfilename).get_infohash()

            self.frame.librarylist.Select(infohash)
            torrent = self.guiUtility.channelsearch_manager.getTorrentFromChannel(self.frame.managechannel.channel, infohash)

            def check_for_modifications():
                modifications = self.guiUtility.channelsearch_manager.getTorrentModifications(torrent)
                videoinfo_valid = False
                swiftthumbnails_valid = False
                for modification in modifications:
                    if modification.name == 'swift-thumbnails' and modification.value:
                        swiftthumbnails_valid = True
                    if modification.name == 'video-info' and modification.value:
                        videoinfo_dict = json.loads(modification.value)
                        if videoinfo_dict['duration'] and videoinfo_dict['resolution']:
                            videoinfo_valid = True

                return videoinfo_valid and swiftthumbnails_valid
            self.CallConditional(10, check_for_modifications, do_overview, 'No valid channel modifications received')

        def do_thumbnails(torrentfilename):
            thumb_dir = os.path.join(self.session.get_torrent_collecting_dir(), 'thumbs-8bb88a02da691636a7ed929b87d467f24700e490')
            self.CallConditional(120, lambda: os.path.isdir(thumb_dir) and len(os.listdir(thumb_dir)) > 0, lambda: do_modifications(torrentfilename), 'No thumbnails were created')

        def do_download_torrent(torrentfilename):
            self.screenshot('Playlist has been created')

            download = self.guiUtility.frame.startDownload(torrentfilename=torrentfilename, destdir=self.getDestDir())
            download.add_peer(("127.0.0.1", self.session2.get_listen_port()))

            self.guiUtility.ShowPage('my_files')
            self.CallConditional(10, lambda: download.get_progress() == 1.0, lambda: do_thumbnails(torrentfilename), 'Failed to download torrent in time')

        def do_create_playlist(torrentfilename):
            self.screenshot('Files have been added created')

            infohash = TorrentDef.load(torrentfilename).get_infohash()

            manageplaylist = self.managechannel.playlistlist
            manager = manageplaylist.GetManager()
            manager.createPlaylist('Unittest', 'Playlist created for Unittest', [infohash, ])

            # switch to playlist tab
            mp_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage playlists")
            if mp_index:
                self.managechannel.notebook.SetSelection(mp_index)

            self.CallConditional(60, lambda: len(manageplaylist.GetItems()) == 1, lambda: do_download_torrent(torrentfilename), 'Channel did not have a playlist')

        def do_add_torrent(torrentfilename):
            self.screenshot('Channel is created')

            managefiles = self.managechannel.fileslist
            manager = managefiles.GetManager()
            manager.startDownload(torrentfilename, fixtorrent=True)
            manager.startDownloadFromUrl(r'http://www.clearbits.net/get/1678-zenith-part-1.torrent', fixtorrent=True)
            manager.startDownloadFromMagnet(r'magnet:?xt=urn:btih:5ac55cf1b935291f6fc92ad7afd34597498ff2f7&dn=Pioneer+One+S01E01+Xvid-VODO&title=', fixtorrent=True)

            # switch to files tab
            mt_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage torrents")
            if mt_index:
                self.managechannel.notebook.SetSelection(mt_index)

            self.CallConditional(120, lambda: len(managefiles.GetItems()) == 3, lambda: do_create_playlist(torrentfilename), 'Channel did not have 3 torrents')

        def do_create_local_torrent():
            torrentfilename = self.setupSeeder()
            do_add_torrent(torrentfilename)

        def do_create():
            self.screenshot('After selecting mychannel page')

            self.managechannel = self.frame.managechannel

            self.managechannel.name.SetValue('UNITTEST')
            self.managechannel.description.SetValue('Channel created for UNITTESTING purposes')

            self.managechannel.Save()
            self.screenshot('After clicking save')

            self.CallConditional(60, lambda: self.frame.managechannel.channel, do_create_local_torrent, 'Channel instance did not arrive at managechannel')

        def do_page():
            self.guiUtility.ShowPage('mychannel')
            self.Call(1, do_create)

        self.startTest(do_page)

    def startTest(self, callback):

        def get_and_modify_dispersy():
            from Tribler.dispersy.endpoint import NullEndpoint

            print >> sys.stderr, "tgs: frame ready, replacing dispersy endpoint"
            dispersy = self.session.get_dispersy_instance()
            dispersy._endpoint = NullEndpoint()
            dispersy._endpoint.open(dispersy)

            callback()

        TestGuiAsServer.startTest(self, get_and_modify_dispersy)


    def setupSeeder(self):
        from Tribler.Core.Session import Session
        from Tribler.Core.TorrentDef import TorrentDef
        from Tribler.Core.DownloadConfig import DownloadStartupConfig

        self.setUpPreSession()
        self.config.set_libtorrent(True)

        self.session2 = Session(self.config, ignore_singleton=True)
        self.session2.start()

        tdef = TorrentDef()
        tdef.add_content(os.path.join(BASE_DIR, "data", "video.avi"))
        tdef.set_tracker("http://fake.net/announce")
        tdef.finalize()
        torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(os.path.join(BASE_DIR, "data"))  # basedir of the file we are seeding
        self.session2.start_download(tdef, dscfg)

        return torrentfn

    def setUp(self):
        TestGuiAsServer.setUp(self)
        self.session2 = None

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            time.sleep(10)

        TestGuiAsServer.tearDown(self)
