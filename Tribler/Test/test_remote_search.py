# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import wx
from time import sleep

from Tribler.Test.test_gui_as_server import TestGuiAsServer

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
        self.guiUtility.toggleFamilyFilter(True)
        
        wx.CallAfter(self.guiUtility.dosearch, u'xxx')
        sleep(10)
        
        assert self.frame.searchlist.total_results == 0

if __name__ == "__main__":
    unittest.main()

