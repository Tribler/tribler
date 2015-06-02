# see LICENSE.txt for license information

from Tribler.Test.test_as_server import TestGuiAsServer
from Tribler.Main.vwxGUI.list_item import ChannelListItem


class BaseRemoteTest(TestGuiAsServer):

    def startTest(self, callback, search_community=True,
                  use_torrent_search=True, use_channel_search=True):
        if search_community:
            def wait_for_search():
                self._logger.debug("Frame ready, starting to wait for search to be ready")
                self.CallConditional(300, lambda: self.frame.SRstatusbar.GetConnections() > 0.75, callback,
                                     'did not connect to 75% of expected peers within 300s',
                                     assertCallback=lambda *argv, **kwarg: callback())
            super(BaseRemoteTest, self).startTest(wait_for_search)

        else:
            def wait_for_chansearch():
                self._logger.debug("Frame ready, starting to wait for channelsearch to be ready")
                self.CallConditional(300, lambda: self.frame.SRstatusbar.GetChannelConnections() > 10, callback,
                                     'did not connect to more than 10 peers within 300s',
                                     assertCallback=lambda *argv, **kwarg: callback())
            super(BaseRemoteTest, self).startTest(wait_for_chansearch,
                                                  use_torrent_search=use_torrent_search,
                                                  use_channel_search=use_channel_search)


class TestRemoteTorrentSearch(BaseRemoteTest):
    """
    Only searches for remote torrents (using SearchCommunity).
    """
    def test_remote_torrent_search(self):
        def do_assert():
            self.screenshot('After doing mp3 search, got %d results' % self.frame.searchlist.GetNrResults())
            self.assert_(self.frame.searchlist.GetNrResults() > 0, 'no results',
                         tribler_session=self.guiUtility.utility.session, dump_statistics=True)
            self.assert_(self.guiUtility.torrentsearch_manager.gotRemoteHits, 'no remote results',
                         tribler_session=self.guiUtility.utility.session, dump_statistics=True)
            self.quit()

        def do_search():
            self.guiUtility.toggleFamilyFilter(newState=False, setCheck=True)
            self.guiUtility.dosearch(u'mp3')
            self.Call(10, do_assert)

        self.startTest(do_search, use_torrent_search=True, use_channel_search=False)


class TestRemoteChannelSearch(BaseRemoteTest):
    """
    Only searches for remote channels (using AllChannelCommunity).
    """
    def test_channel_search(self):
        def do_assert():
            self.assert_(self.guiUtility.guiPage == 'selectedchannel', 'no in selectedchannel page',
                         tribler_session=self.guiUtility.utility.session, dump_statistics=True)

            self.screenshot('After doubleclicking first channel')
            self.quit()

        def do_doubleclick():
            self.assert_(self.frame.searchlist.GetNrChannels() > 0, 'no channels matching tv',
                         tribler_session=self.guiUtility.utility.session, dump_statistics=True)

            self.screenshot('After doing tv search, got %d results' % self.frame.searchlist.GetNrResults())
            items = self.frame.searchlist.GetItems()
            for _, item in items.iteritems():
                if isinstance(item, ChannelListItem):
                    item.OnDClick()
                    break
            else:
                self.assert_(False, 'could not find ChannelListItem',
                             tribler_session=self.guiUtility.utility.session, dump_statistics=True)

            self.Call(10, do_assert)

        def do_search():
            self.guiUtility.toggleFamilyFilter(newState=False, setCheck=True)
            self.guiUtility.dosearch(u'tv')
            self.Call(15, do_doubleclick)

        self.startTest(do_search, search_community=False, use_torrent_search=False, use_channel_search=True)


class TestMixedRemoteSearch(BaseRemoteTest):

    def setUpPreSession(self):
        super(TestMixedRemoteSearch, self).setUpPreSession()
        self.config.set_torrent_store(True)
        self.config.set_enable_torrent_search(True)
        self.config.set_enable_channel_search(True)
        self.config.set_torrent_collecting(True)
        self.config.set_torrent_checking(True)

    def test_ffsearch(self):
        def do_assert():
            self.screenshot('After doing xxx search, got %d results' % self.frame.searchlist.GetNrResults())
            self.assert_(self.frame.searchlist.GetNrResults() == 0, 'got results',
                         tribler_session=self.guiUtility.utility.session, dump_statistics=True)
            self.quit()

        def do_search():
            self.guiUtility.toggleFamilyFilter(True)
            self.guiUtility.dosearch(u'xxx')
            self.Call(10, do_assert)

        self.startTest(do_search)

    def test_remotedownload(self):
        def do_assert():
            self.screenshot('After doing ubuntu search + desktop filter + selecting item + download')
            self.quit()

        def do_download():
            self.screenshot('After doing ubuntu search + desktop filter + selecting item')

            self.guiUtility.utility.write_config('showsaveas', 0)

            self.frame.top_bg.OnDownload()
            self.CallConditional(
                120, lambda: self.frame.librarylist.GetNrResults() > 0, do_assert, 'no download in librarylist',
                tribler_session=self.guiUtility.utility.session, dump_statistics=True)

        def do_select():
            self.assert_(self.frame.searchlist.GetNrResults() > 0, 'no hits matching ubuntu + desktop',
                         tribler_session=self.guiUtility.utility.session, dump_statistics=True)
            self.screenshot('After doing ubuntu search + desktop filter, got %d results' %
                            self.frame.searchlist.GetNrResults())
            items = self.frame.searchlist.GetItems()
            keys = items.keys()

            self.frame.searchlist.Select(keys[0])
            self.Call(5, do_download)

        def do_filter():
            self.assert_(self.frame.searchlist.GetNrResults() > 0, 'no hits matching ubuntu + desktop',
                         tribler_session=self.guiUtility.utility.session, dump_statistics=True)
            self.screenshot('After doing ubuntu search, got %d results' % self.frame.searchlist.GetNrResults())
            self.frame.searchlist.GotFilter('desktop')

            self.Call(5, do_select)

        def do_search():
            self.guiUtility.toggleFamilyFilter(newState=False, setCheck=True)
            self.guiUtility.dosearch(u'ubuntu')
            self.Call(10, do_filter)

        self.startTest(do_search)
