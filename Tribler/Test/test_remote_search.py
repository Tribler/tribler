# see LICENSE.txt for license information

import unittest
import wx
from time import sleep

from Tribler.Test.test_gui_as_server import TestGuiAsServer
from Tribler.Main.globals import DefaultDownloadStartupConfig

DEBUG=True
class TestRemoteQuery(TestGuiAsServer):
    """ 
    Testing QUERY message of Social Network extension V1
    """
    def test_remotesearch(self):
        def do_assert():
            self.asserts.append((self.frame.searchlist.total_results > 0, 'no results'))
            self.asserts.append((self.guiUtility.torrentsearch_manager.gotRemoteHits, 'no remote results'))
            self.quit()
        
        def do_search():
            self.guiUtility.dosearch(u'mp3')
            wx.CallLater(10000, do_assert)
            
        self.startTest(do_search)
        
    def test_ffsearch(self):
        def do_assert():
            self.asserts.append((self.frame.searchlist.total_results == 0, 'got results'))
            self.quit()
        
        def do_search():
            self.guiUtility.toggleFamilyFilter(True)
            self.guiUtility.dosearch(u'xxx')
            wx.CallLater(10000, do_assert)
            
        self.startTest(do_search)
        
    def test_remotedownload(self):
        def do_assert():
            self.quit()
            
        def do_download():
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            defaultDLConfig.set_show_saveas(False)
        
            self.frame.top_bg.OnDownload()
            wx.CallLater(5000, do_assert)  
            
        def do_select():
            self.asserts.append((self.frame.searchlist.total_results > 0, 'no hits matching vodo + pioneer'))
            items = self.frame.searchlist.GetItems()
            keys = items.keys()
        
            self.frame.searchlist.Select(keys[0])
            wx.CallLater(5000, do_download)
        
        def do_filter():
            self.asserts.append((self.frame.searchlist.total_results > 0, 'no hits matching vodo'))
            self.frame.searchlist.GotFilter('pioneer')
            wx.CallLater(5000, do_select)
        
        def do_search():
            self.guiUtility.dosearch(u'vodo')
            wx.CallLater(10000, do_filter)
            
        self.startTest(do_search)  

if __name__ == "__main__":
    unittest.main()