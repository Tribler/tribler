from Tribler.Core.Utilities import path_util
from Tribler.Core.Utilities.install_dir import determine_install_dir
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestInstallDir(TriblerCoreTest):

    def test_install_dir(self):
        install_dir = determine_install_dir()
        self.assertIsInstance(install_dir, path_util.Path)
        self.assertTrue(install_dir.is_dir())
        self.assertTrue((install_dir / 'Tribler').exists())
