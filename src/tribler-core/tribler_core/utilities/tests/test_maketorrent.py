from pathlib import Path

from tribler_core.tests.tools.test_as_server import BaseTestCase
from tribler_core.utilities.maketorrent import pathlist2filename


class TestMakeTorrent(BaseTestCase):

    def test_pathlist2filename_utf8(self):
        path_list = ["test", "path"]
        path = pathlist2filename(path_list)
        self.assertEqual(path, Path("test") / "path")

    def test_pathlist2filename_not_utf8(self):
        part = '\xb0\xe7'.encode("latin-1")
        path_list = ["test", part]
        path = pathlist2filename(path_list)
        self.assertEqual(path, Path("test") / "\xb0\xe7")
