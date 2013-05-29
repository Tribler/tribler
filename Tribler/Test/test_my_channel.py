# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import os
import sys


from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR
import binascii

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
            # switch to manage tab
            m_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage")
            self.managechannel.notebook.SetSelection(m_index)

            self.managechannel.rss_url.SetValue('http://www.clearbits.net/feeds/creator/184-pioneer-one.rss')
            self.managechannel.OnAddRss()
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

        def do_create_playlist():
            self.screenshot('Files have been added created')

            # switch to playlist tab
            mp_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage playlists")
            self.managechannel.notebook.SetSelection(mp_index)

            infohash = binascii.unhexlify('66ED7F30E3B30FA647ABAA19A36E7503AA071535')  # pioneer one

            manageplaylist = self.managechannel.playlistlist
            manager = manageplaylist.GetManager()
            manager.createPlaylist('Unittest', 'Playlist created for Unittest', [infohash, ])

            self.CallConditional(60, lambda: len(manageplaylist.GetItems()) == 1, do_overview, 'Channel did not have a playlist')

        def do_add_torrent():
            self.screenshot('Channel is created')

            # switch to files tab
            mt_index = self.managechannel.GetPage(self.managechannel.notebook, "Manage torrents")
            self.managechannel.notebook.SetSelection(mt_index)

            managefiles = self.managechannel.fileslist
            manager = managefiles.GetManager()
            manager.startDownload(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"), fixtorrent=True)
            manager.startDownloadFromUrl(r'http://www.clearbits.net/get/1678-zenith-part-1.torrent', fixtorrent=True)
            manager.startDownloadFromMagnet(r'magnet:?xt=urn:btih:5ac55cf1b935291f6fc92ad7afd34597498ff2f7&dn=Pioneer+One+S01E01+Xvid-VODO&title=', fixtorrent=True)

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
