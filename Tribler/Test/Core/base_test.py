from tempfile import mkdtemp

import shutil

from Tribler.Test.test_as_server import BaseTestCase


class TriblerCoreTest(BaseTestCase):

    def setUp(self):
        self.temp_dir = mkdtemp(suffix="_tribler_test_session")

    def tearDown(self):
        shutil.rmtree(unicode(self.temp_dir), ignore_errors=True)
