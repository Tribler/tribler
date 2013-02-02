# see LICENSE.txt for license information

import unittest

from Tribler.Test.test_gui_as_server import TestGuiAsServer

DEBUG=True
class TestRemoteQuery(TestGuiAsServer):
    """ 
    Testing QUERY message of Social Network extension V1
    """
    def test_debugpanel(self):
        def do_assert():
            self.assert_(self.guiUtility.guiPage == 'stats', 'Debug page is not selected')
            self.screenshot('After selecting debug page')
            self.quit()
        
        def do_page():
            self.guiUtility.ShowPage('stats')
            self.Call(10, do_assert)
            
        self.startTest(do_page)

if __name__ == "__main__":
    unittest.main()