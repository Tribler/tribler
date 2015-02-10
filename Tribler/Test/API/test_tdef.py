# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO:
#

import unittest
import os
import tempfile

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.bencode import bdecode
from Tribler.Core.Utilities.utilities import isValidTorrentFile
from Tribler.Test.test_as_server import BASE_DIR

DEBUG = False

TRACKER = 'http://www.tribler.org/announce'
PLAYTIME = "0:06"
PLAYTIME_SECS = 6  # PLAYTIME in seconds


class TestTorrentDef(unittest.TestCase):

    """
    Testing TorrentDef version 0
    """

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_add_content_file(self):
        self.subtest_add_content_file(merkle=False)
        self.subtest_add_content_file(merkle=True)

    def test_add_content_dir(self):
        self.subtest_add_content_dir(merkle=False)
        self.subtest_add_content_dir(merkle=True)

    def test_add_content_dir_and_file(self):
        self.subtest_add_content_dir_and_file(merkle=False)
        self.subtest_add_content_dir_and_file(merkle=True)

    def test_add_content_file_playtime(self):
        self.subtest_add_content_file_playtime(merkle=False)
        self.subtest_add_content_file_playtime(merkle=True)

    def test_add_content_dir_playtime(self):
        self.subtest_add_content_dir_playtime(merkle=False)
        self.subtest_add_content_dir_playtime(merkle=True)

    def test_add_content_file_thumbnail(self):
        self.subtest_add_content_file_thumbnail(merkle=False)
        self.subtest_add_content_file_thumbnail(merkle=True)

    def test_add_content_announce_list(self):
        self.subtest_add_content_announce_list(merkle=False)
        self.subtest_add_content_announce_list(merkle=True)

    def test_add_content_httpseeds(self):
        self.subtest_add_content_httpseeds(merkle=False)
        self.subtest_add_content_httpseeds(merkle=True)

    def test_add_content_piece_length(self):
        self.subtest_add_content_piece_length(merkle=False)
        self.subtest_add_content_piece_length(merkle=True)

    def test_add_content_file_save(self):
        self.subtest_add_content_file_save(merkle=False)
        self.subtest_add_content_file_save(merkle=True)

    def test_ns_metadata(self):
        dummydata = "HalloWereld"
        t = TorrentDef()
        t.set_metadata(dummydata)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
        t.add_content(fn)
        t.set_tracker(TRACKER)
        t.finalize()

        [handle, filename] = tempfile.mkstemp()
        os.close(handle)
        t.save(filename)

        t2 = TorrentDef.load(filename)
        self.assert_(t2.get_metadata() == dummydata)

    def test_is_private(self):
        privatefn = os.path.join(BASE_DIR, "data", "private.torrent")
        publicfn = os.path.join(BASE_DIR, "data", "bak_single.torrent")

        t1 = TorrentDef.load(privatefn)
        t2 = TorrentDef.load(publicfn)

        self.assert_(t1.is_private() == True)
        self.assert_(t2.is_private() == False)

    def subtest_add_content_file(self, merkle=True):
        """ Add a single file to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
        t.add_content(fn)
        t.set_tracker(TRACKER)
        t.finalize()

        s = os.path.getsize(fn)

        metainfo = t.get_metainfo()
        self.general_check(metainfo)

        self.assert_(metainfo['info']['name'] == "video.avi")
        self.assert_(metainfo['info']['length'] == s)

        """
        bdata = bencode(t.get_metainfo())
        f = open("gen.torrent","wb")
        f.write(bdata)
        f.close()
        """

    def subtest_add_content_dir(self, merkle=True):
        """ Add a single dir to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        dn = os.path.join(BASE_DIR, "API", "contentdir")
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

    def subtest_add_content_dir_and_file(self, merkle=True):
        """ Add a single dir and single file to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)

        dn = os.path.join(BASE_DIR, "API", "contentdir")
        t.add_content(dn, "dirintorrent")

        fn = os.path.join(BASE_DIR, "API", "video.avi")
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

    def subtest_add_content_file_playtime(self, merkle=True):
        """ Add a single file with playtime to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
        t.add_content(fn, playtime=PLAYTIME)
        t.set_tracker(TRACKER)
        t.finalize()

        s = os.path.getsize(os.path.join(BASE_DIR, "API", "video.avi"))

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        self.assert_(metainfo['info']['playtime'] == PLAYTIME)
        azprop = metainfo['azureus_properties']
        content = azprop['Content']
        realspeedbps = content['Speed Bps']
        expspeedbps = s / PLAYTIME_SECS
        self.assert_(realspeedbps == expspeedbps)

    def subtest_add_content_dir_playtime(self, merkle=True):
        """ Add a single dir to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn1 = os.path.join(BASE_DIR, "API", "contentdir", "video.avi")
        fn2 = os.path.join(BASE_DIR, "API", "contentdir", "file.txt")
        t.add_content(fn1, os.path.join("dirintorrent", "video.avi"), playtime=PLAYTIME)
        t.add_content(fn2, os.path.join("dirintorrent", "file.txt"))
        t.set_tracker(TRACKER)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        self.assert_(metainfo['info']['name'] == 'dirintorrent')

        s = os.path.getsize(fn1)

        files = metainfo['info']['files']
        for file in files:
            if file['path'][0] == "video.avi":
                self.assert_(file['playtime'] == PLAYTIME)

        azprop = metainfo['azureus_properties']
        content = azprop['Content']
        realspeedbps = content['Speed Bps']
        expspeedbps = s / PLAYTIME_SECS
        self.assert_(realspeedbps == expspeedbps)

    def subtest_add_content_file_thumbnail(self, merkle=True):
        """ Add a single file with thumbnail to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
        thumbfn = os.path.join(BASE_DIR, "API", "thumb.jpg")
        t.add_content(fn)
        t.set_thumbnail(thumbfn)
        t.set_tracker(TRACKER)
        t.finalize()

        f = open(thumbfn, "rb")
        expthumb = f.read()
        f.close()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        azprop = metainfo['azureus_properties']
        content = azprop['Content']
        realthumb = content['Thumbnail']
        self.assert_(realthumb == expthumb)

    def subtest_add_content_announce_list(self, merkle=True):
        """ Add a single file with announce-list to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
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

    def subtest_add_content_httpseeds(self, merkle=True):
        """ Add a single file with BitTornado httpseeds to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
        t.add_content(fn)
        t.set_tracker(TRACKER)
        expseeds = ['http://www.cs.vu.nl/index.html', 'http://www.st.ewi.tudelft.nl/index.html']
        t.set_httpseeds(expseeds)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        realseeds = metainfo['httpseeds']
        self.assert_(realseeds == expseeds)

    def subtest_add_content_piece_length(self, merkle=True):
        """ Add a single file with piece length to a TorrentDef """
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
        t.add_content(fn)
        t.set_piece_length(2 ** 16)
        t.set_tracker(TRACKER)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        self.assert_(metainfo['info']['piece length'] == 2 ** 16)

    def subtest_add_content_file_save(self, merkle=True):
        """ Add a single file to a TorrentDef and save the latter"""
        t = TorrentDef()
        t.set_create_merkle_torrent(merkle)
        fn = os.path.join(BASE_DIR, "API", "video.avi")
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
