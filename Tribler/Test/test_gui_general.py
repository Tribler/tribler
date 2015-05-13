# see LICENSE.txt for license information

import unittest

from Tribler.Test.test_as_server import TestGuiAsServer


class TestGuiGeneral(TestGuiAsServer):

    def test_debugpanel(self):
        def do_assert():
            self.assert_(self.guiUtility.guiPage == 'stats', 'Debug page is not selected')
            self.screenshot('After selecting debug page')
            self.quit()

        def do_page():
            self.guiUtility.ShowPage('stats')
            self.callLater(10, do_assert)

        self.startTest(do_page)

if __name__ == "__main__":
    unittest.main()
