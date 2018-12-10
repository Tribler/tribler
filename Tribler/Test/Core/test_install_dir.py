from __future__ import absolute_import

import os

import six
from Tribler.Core.Utilities.install_dir import determine_install_dir
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestInstallDir(TriblerCoreTest):

    def test_install_dir(self):
        install_dir = determine_install_dir()
        self.assertIsInstance(install_dir, six.string_types)
        self.assertTrue(os.path.isdir(install_dir))
        self.assertTrue(os.path.exists(os.path.join(install_dir, 'Tribler')))
