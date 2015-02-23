# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import os
import sys
import time

from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import dlstatus_strings

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
            self.CallConditional(
                60, lambda: len(managefiles.GetItems()) > 0, do_files_check, 'Channel did not have torrents')

        def do_rss():
            self.managechannel.rss_url.SetValue(r'http://torrent.fedoraproject.org/rss20.xml')
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
            self.CallConditional(60, lambda: self.frame.managechannel.rss_url,
                                 do_rss, 'Channel instance did not arrive at managechannel')

        def do_page():
            self.guiUtility.ShowPage('mychannel')
            self.Call(1, do_create)

        self.startTest(do_page)

    def test_add_torrents_playlists(self):

        def do_overview():
            self.guiUtility.showChannel(self.managechannel.channel)
            self.screenshot('Resulting channel')
            self.quit()

        def do_create_playlist(torrentfilename):
            self.screenshot('Files have been added created')

            infohash = TorrentDef.load(torrentfilename).get_infohash()

            manageplaylist = self.managechannel.playlistlist
            manager = manageplaylist.GetManager()
            manager.createPlaylist('Unittest', 'Playlist created for Unittest', [infohash, ])

            # switch to playlist tab
            mp_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage playlists")
            self.managechannel.notebook.SetSelection(mp_index)

            self.CallConditional(
                60, lambda: len(manageplaylist.GetItems()) == 1, do_overview, 'Channel did not have a playlist')

        def do_switch_tab(torrentfilename):
            # switch to files tab
            mt_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage torrents")
            self.managechannel.notebook.SetSelection(mt_index)

            self.CallConditional(120, lambda: len(self.managechannel.fileslist.GetItems()) == 3,
                                 lambda: do_create_playlist(torrentfilename), 'Channel did not have 3 torrents')

        def do_add_torrent(torrentfilename):
            self.screenshot('Channel is created')

            managefiles = self.managechannel.fileslist
            manager = managefiles.GetManager()
            manager.startDownload(torrentfilename, fixtorrent=True)
            manager.startDownloadFromUrl(
                r'http://torrent.fedoraproject.org/torrents/Fedora-20-i386-DVD.torrent', fixtorrent=True)
            manager.startDownloadFromMagnet(
                r'magnet:?xt=urn:btih:5ac55cf1b935291f6fc92ad7afd34597498ff2f7&dn=Pioneer+One+S01E01+Xvid-VODO&title=', fixtorrent=True)

            self.CallConditional(
                10, lambda: self.managechannel.notebook.GetPageCount() > 1, lambda: do_switch_tab(torrentfilename))

        def do_create_local_torrent():
            torrentfilename = self.createTorrent()
            do_add_torrent(torrentfilename)

        def do_create():
            self.screenshot('After selecting mychannel page')

            self.managechannel = self.frame.managechannel

            self.managechannel.name.SetValue('UNITTEST')
            self.managechannel.description.SetValue('Channel created for UNITTESTING purposes')

            self.managechannel.Save()
            self.screenshot('After clicking save')

            self.CallConditional(60, lambda: self.frame.managechannel.channel,
                                 do_create_local_torrent, 'Channel instance did not arrive at managechannel')

        def do_page():
            self.guiUtility.ShowPage('mychannel')
            self.Call(1, do_create)

        self.startTest(do_page)

    def startTest(self, callback):

        def get_and_modify_dispersy():
            from Tribler.dispersy.endpoint import NullEndpoint

            self._logger.debug("Frame ready, replacing dispersy endpoint")
            dispersy = self.session.get_dispersy_instance()
            dispersy._endpoint = NullEndpoint()
            dispersy._endpoint.open(dispersy)

            callback()

        TestGuiAsServer.startTest(self, get_and_modify_dispersy)

    def createTorrent(self):
        tdef = TorrentDef()
        tdef.add_content(os.path.join(BASE_DIR, "data", "video.avi"))
        tdef.set_tracker("http://fake.net/announce")
        tdef.finalize()
        torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)

        return torrentfn
