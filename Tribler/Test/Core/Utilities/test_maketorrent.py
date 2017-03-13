import os

from Tribler.Core.Utilities.maketorrent import pathlist2filename
from Tribler.Test.test_as_server import BaseTestCase


class TestMakeTorrent(BaseTestCase):

    def test_pathlist2filename_utf8(self):
        path_list = [u"test", u"path"]
        path = pathlist2filename(path_list)
        self.assertEqual(path, os.path.join(u"test", u"path"))

    def test_pathlist2filename_not_utf8(self):
        part = u'\xb0\xe7'.encode("latin-1")
        path_list = ["test", part]
        path = pathlist2filename(path_list)
        self.assertEqual(path, os.path.join(u"test", u"\xb0\xe7"))
