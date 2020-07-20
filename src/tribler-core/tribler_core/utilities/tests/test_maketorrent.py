from tribler_core.utilities.maketorrent import pathlist2filename
from tribler_core.utilities.path_util import Path


def test_pathlist2filename_utf8():
    path_list = [u"test", u"path"]
    path = pathlist2filename(path_list)
    assert path == Path(u"test") / u"path"


def test_pathlist2filename_not_utf8():
    part = u'\xb0\xe7'.encode("latin-1")
    path_list = ["test", part]
    path = pathlist2filename(path_list)
    assert path == Path(u"test") / u"\xb0\xe7"
