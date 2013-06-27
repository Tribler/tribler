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
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo

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
        def do_quit():
            self.screenshot('Resulting channel')
            self.quit()

        def do_overview():
            self.screenshot('Playlist has been created')
            self.guiUtility.showChannel(self.managechannel.channel)

            do_quit()

        def do_modifications():
            self.guiUtility.ShowPage('my_files')
            time.sleep(1)
            self.frame.librarylist.Select(binascii.unhexlify('45a647b1120ed9fe7f793e17585efb4b0efdf1a5'))
            torrent = self.frame.top_bg.GetSelectedTorrents()[0]
            time.sleep(10)
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

            self.CallConditional(1, lambda: videoinfo_valid and swiftthumbnails_valid, do_overview, 'No valid channel modifications received')

        def do_thumbnails():
            thumb_dir = os.path.join(self.guiUtility.utility.session.get_torrent_collecting_dir(), 'thumbs-45a647b1120ed9fe7f793e17585efb4b0efdf1a5')

            self.CallConditional(120, lambda: os.path.isdir(thumb_dir) and len(os.listdir(thumb_dir)) > 0, do_modifications, 'No thumbnails were created')

        def do_download_torrent():
            torrentfilename = os.path.join(BASE_DIR, "data", 'Prebloc.2010.Xvid-VODO.torrent')
            download = self.guiUtility.frame.startDownload(torrentfilename=torrentfilename, destdir=self.getDestDir())

            self.CallConditional(300, lambda: download.get_progress() == 1.0, do_thumbnails, 'Failed to download torrent in time')

        def do_create_playlist():
            self.screenshot('Files have been added created')

            infohash = binascii.unhexlify('45a647b1120ed9fe7f793e17585efb4b0efdf1a5')  # prebloc

            manageplaylist = self.managechannel.playlistlist
            manager = manageplaylist.GetManager()
            manager.createPlaylist('Unittest', 'Playlist created for Unittest', [infohash, ])

            # switch to playlist tab
            mp_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage playlists")
            self.managechannel.notebook.SetSelection(mp_index)

            self.CallConditional(60, lambda: len(manageplaylist.GetItems()) == 1, do_download_torrent, 'Channel did not have a playlist')

        def do_add_torrent():
            self.screenshot('Channel is created')

            managefiles = self.managechannel.fileslist
            manager = managefiles.GetManager()
            manager.startDownload(os.path.join(BASE_DIR, "data", 'Prebloc.2010.Xvid-VODO.torrent'), fixtorrent=True)
            manager.startDownloadFromUrl(r'http://www.clearbits.net/get/1678-zenith-part-1.torrent', fixtorrent=True)
            manager.startDownloadFromMagnet(r'magnet:?xt=urn:btih:5ac55cf1b935291f6fc92ad7afd34597498ff2f7&dn=Pioneer+One+S01E01+Xvid-VODO&title=', fixtorrent=True)

            # switch to files tab
            mt_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage torrents")
            self.managechannel.notebook.SetSelection(mt_index)

            self.CallConditional(60, lambda: len(managefiles.GetItems()) == 3, do_create_playlist, 'Channel did not have 3 torrents')

        def do_create():
            self.screenshot('After selecting mychannel page')

            self.managechannel = self.frame.managechannel

            self.managechannel.name.SetValue('UNITTEST')
            self.managechannel.description.SetValue('Channel created for UNITTESTING purposes')

            self.managechannel.Save()
            self.screenshot('After clicking save')

            self.CallConditional(60, lambda: self.frame.managechannel.channel, do_add_torrent, 'Channel instance did not arrive at managechannel')

        def do_page():
            self.guiUtility.ShowPage('mychannel')
            self.Call(1, do_create)

        self.startTest(do_page, True)

    def startTest(self, callback, waitforpeers=False):

        def get_and_modify_dispersy():
            from Tribler.dispersy.endpoint import NullEndpoint

            print >> sys.stderr, "tgs: frame ready, replacing dispersy endpoint"
            dispersy = self.session.get_dispersy_instance()
            dispersy._endpoint = NullEndpoint()
            dispersy._endpoint.open(dispersy)


            if waitforpeers:
                from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
                ltmgr = LibtorrentMgr.getInstance()
                self.CallConditional(120, lambda: ltmgr.get_dht_nodes() > 25, callback)
            else:
                callback()

        TestGuiAsServer.startTest(self, get_and_modify_dispersy)
