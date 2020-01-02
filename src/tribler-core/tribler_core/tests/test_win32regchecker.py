import sys

from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.utilities.win32regchecker import Win32RegChecker


class TriblerCoreTestInstallDir(TriblerCoreTest):

    def test_win32regchecker(self):
        if sys.platform != 'win32':
            self.assertIsNone(Win32RegChecker().readRootKey(".wmv"))
        else:
            self.assertTrue(Win32RegChecker().readRootKey(".wmv"))
            self.assertIsNone(Win32RegChecker().readRootKey("fdkaslfjsdakfdffdsakls"))
