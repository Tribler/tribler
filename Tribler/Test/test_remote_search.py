# Written by Niels Zeilemaker
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
        sleep(10)
        wx.CallAfter(self.guiUtility.dosearch, u'mp3')
        sleep(10)
        
        assert self.frame.searchlist.total_results > 0
        assert self.guiUtility.torrentsearch_manager.gotRemoteHits
        
    def test_ffsearch(self):
        sleep(10)
        wx.CallAfter(self.guiUtility.toggleFamilyFilter, True)
        wx.CallAfter(self.guiUtility.dosearch, u'xxx')
        sleep(10)
        
        assert self.frame.searchlist.total_results == 0
        
    def test_remotedownload(self):
        sleep(10)
        wx.CallAfter(self.guiUtility.dosearch, u'vodo')
        sleep(10)
        
        assert self.frame.searchlist.total_results > 0, 'no hits matching vodo'
        
        wx.CallAfter(self.frame.searchlist.GotFilter, 'pioneer')
        sleep(2)

        assert self.frame.searchlist.total_results > 0, 'no hits matching vodo + pioneer'
        items = self.frame.searchlist.GetItems()
        keys = items.keys()
        
        wx.CallAfter(self.frame.searchlist.Select, keys[0])
        sleep(5)
        
        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        defaultDLConfig.set_show_saveas(False)
        
        wx.CallAfter(self.frame.top_bg.OnDownload)
        sleep(5)

if __name__ == "__main__":
    unittest.main()

