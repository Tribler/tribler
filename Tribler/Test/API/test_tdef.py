# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO:
#

import os
from libtorrent import bdecode

from Tribler.Test.test_as_server import BaseTestCase, TESTS_DATA_DIR, TESTS_API_DIR

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.utilities import isValidTorrentFile


DEBUG = False

TRACKER = 'http://www.tribler.org/announce'
PLAYTIME = "0:06"
PLAYTIME_SECS = 6  # PLAYTIME in seconds


class TestTorrentDef(BaseTestCase):

    """
    Testing TorrentDef version 0
    """

    def test_add_content_file(self):
        self.subtest_add_content_file()

    def test_add_content_dir(self):
        self.subtest_add_content_dir()

    def test_add_content_dir_and_file(self):
        self.subtest_add_content_dir_and_file()

    def test_add_content_announce_list(self):
        self.subtest_add_content_announce_list()

    def test_add_content_httpseeds(self):
        self.subtest_add_content_httpseeds()

    def test_add_content_piece_length(self):
        self.subtest_add_content_piece_length()

    def test_add_content_file_save(self):
        self.subtest_add_content_file_save()

    def test_is_private(self):
        privatefn = os.path.join(TESTS_DATA_DIR, "private.torrent")
        publicfn = os.path.join(TESTS_DATA_DIR, "bak_single.torrent")

        t1 = TorrentDef.load(privatefn)
        t2 = TorrentDef.load(publicfn)

        self.assert_(t1.is_private() == True)
        self.assert_(t2.is_private() == False)

    def subtest_add_content_file(self):
        """ Add a single file to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_API_DIR, "video.avi")
        t.add_content(fn)
        t.set_tracker(TRACKER)
        t.finalize()

        s = os.path.getsize(fn)

        metainfo = t.get_metainfo()
        self.general_check(metainfo)

        self.assert_(metainfo['info']['name'] == "video.avi")
        self.assert_(metainfo['info']['length'] == s)

    def subtest_add_content_dir(self):
        """ Add a single dir to a TorrentDef """
        t = TorrentDef()
        dn = os.path.join(TESTS_API_DIR, "contentdir")
        t.add_content(dn, "dirintorrent")
        t.set_tracker(TRACKER)
        t.finalize()

        exps = 0
        for f in os.listdir(dn):
            if f.startswith('.'):
                continue
            p = os.path.join(dn, f)
            s = os.path.getsize(p)
            exps += s
            print "test: expected size", f, s

        print "test: expected total size of files in torrent", exps

        metainfo = t.get_metainfo()
        self.general_check(metainfo)

        self.assert_(metainfo['info']['name'] == 'dirintorrent')
        reals = 0
        for file in metainfo['info']['files']:
            s = file['length']
            print "test: real size", file['path'], s
            reals += s

        print "test: real size of files in torrent", reals

        self.assert_(exps == reals)

    def subtest_add_content_dir_and_file(self):
        """ Add a single dir and single file to a TorrentDef """
        t = TorrentDef()

        dn = os.path.join(TESTS_API_DIR, "contentdir")
        t.add_content(dn, "dirintorrent")

        fn = os.path.join(TESTS_API_DIR, "video.avi")
        t.add_content(fn, os.path.join("dirintorrent", "video.avi"))

        t.set_tracker(TRACKER)
        t.finalize()

        # Check
        exps = os.path.getsize(fn)
        for f in os.listdir(dn):
            if f.startswith('.'):
                continue
            p = os.path.join(dn, f)
            exps += os.path.getsize(p)

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        self.assert_(metainfo['info']['name'] == 'dirintorrent')

        reals = 0
        for file in metainfo['info']['files']:
            reals += file['length']
        self.assert_(exps == reals)

    def subtest_add_content_announce_list(self):
        """ Add a single file with announce-list to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_API_DIR, "video.avi")

        t.add_content(fn)
        t.set_tracker(TRACKER)
        exphier = [[TRACKER], ['http://tracker1.tribler.org:6969/announce', 'http://tracker2.tribler.org:7070/ann'],
                   ['http://www.cs.vu.nl', 'http://www.st.ewi.tudelft.nl', 'http://www.vuze.com']]
        t.set_tracker_hierarchy(exphier)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        realhier = metainfo['announce-list']
        self.assert_(realhier == exphier)

    def subtest_add_content_httpseeds(self):
        """ Add a single file with BitTornado httpseeds to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_API_DIR, "video.avi")
        t.add_content(fn)
        t.set_tracker(TRACKER)
        expseeds = ['http://www.cs.vu.nl/index.html', 'http://www.st.ewi.tudelft.nl/index.html']
        t.set_httpseeds(expseeds)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        realseeds = metainfo['httpseeds']
        self.assert_(realseeds == expseeds)

    def subtest_add_content_piece_length(self):
        """ Add a single file with piece length to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_API_DIR, "video.avi")
        t.add_content(fn)
        t.set_piece_length(2 ** 16)
        t.set_tracker(TRACKER)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        self.assert_(metainfo['info']['piece length'] == 2 ** 16)

    def subtest_add_content_file_save(self):
        """ Add a single file to a TorrentDef and save the latter"""
        t = TorrentDef()
        fn = os.path.join(TESTS_API_DIR, "video.avi")
        t.add_content(fn)
        t.set_tracker(TRACKER)
        t.finalize()

        tfn = os.path.join(os.getcwd(), "gen.torrent")
        t.save(tfn)

        f = open(tfn, "rb")
        bdata = f.read()
        f.close()
        os.remove(tfn)

        data = bdecode(bdata)
        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        self.assert_(metainfo == data)

    def general_check(self, metainfo):
        self.assert_(isValidTorrentFile(metainfo))
        self.assert_(metainfo['announce'] == TRACKER)
