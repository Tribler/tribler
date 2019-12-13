import logging
import os
import shutil
from tempfile import mkdtemp

from aiohttp import ClientResponseError, web

from libtorrent import bencode

from nose.tools import raises

from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.utilities import bdecode_compat
from Tribler.Test.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import BaseTestCase
from Tribler.Test.tools import timeout

TRACKER = 'http://www.tribler.org/announce'
VIDEO_FILE_NAME = "video.avi"


class TestTorrentDef(BaseTestCase):

    def __init__(self, *argv, **kwargs):
        super(TestTorrentDef, self).__init__(*argv, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.site = None

    async def setUpFileServer(self, port, path):
        # Create a local file server, can be used to serve local files. This is preferred over an external network
        # request in order to get files.
        app = web.Application()
        app.add_routes([web.static('/', path)])
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', port)
        await self.site.start()

    async def tearDown(self):
        super(TestTorrentDef, self).tearDown()
        if self.site:
            await self.site.stop()

    def test_tdef_init(self):
        """
        Test initializing a TorrentDef object
        """
        tdef_params = TorrentDef(torrent_parameters={'announce': 'http://test.com'})
        self.assertIn('announce', tdef_params.torrent_parameters)

    def test_create_invalid_tdef(self):
        """
        Test whether creating invalid TorrentDef objects result in ValueErrors
        """
        invalid_metainfo = {}
        self.assertRaises(ValueError, TorrentDef.load_from_memory, bencode(invalid_metainfo))
        invalid_metainfo = {b'info': {}}
        self.assertRaises(ValueError, TorrentDef.load_from_memory, bencode(invalid_metainfo))

    def test_add_content_dir(self):
        """
        Test whether adding a single content directory with two files is working correctly
        """
        t = TorrentDef()
        torrent_dir = os.path.join(TESTS_DATA_DIR, "contentdir")
        t.add_content(os.path.join(torrent_dir, "file.txt"))
        t.add_content(os.path.join(torrent_dir, "otherfile.txt"))
        t.save()

        metainfo = t.get_metainfo()
        self.assertEqual(len(metainfo[b'info'][b'files']), 2)

    def test_add_single_file(self):
        """
        Test whether adding a single file to a torrent is working correctly
        """
        t = TorrentDef()
        torrent_dir = os.path.join(TESTS_DATA_DIR, "contentdir")
        t.add_content(os.path.join(torrent_dir, "file.txt"))
        t.save()

        metainfo = t.get_metainfo()
        self.assertEqual(metainfo[b'info'][b'name'], b'file.txt')

    def test_get_name_utf8_unknown(self):
        """
        Test whether we can succesfully get the UTF-8 name
        """
        t = TorrentDef()
        t.set_name(b'\xA1\xC0')
        t.torrent_parameters[b'encoding'] = 'euc_kr'
        self.assertEqual(t.get_name_utf8(), u'\xf7')

    def test_get_name_utf8(self):
        """
        Check whether we can successfully get the UTF-8 encoded torrent name when using a different encoding
        """
        t = TorrentDef()
        t.set_name(b'\xA1\xC0')
        self.assertEqual(t.get_name_utf8(), u'\xa1\xc0')

    def test_add_content_piece_length(self):
        """
        Add a single file with piece length to a TorrentDef
        """
        t = TorrentDef()
        fn = os.path.join(TESTS_DATA_DIR, VIDEO_FILE_NAME)
        t.add_content(fn)
        t.set_piece_length(2 ** 16)
        t.save()

        metainfo = t.get_metainfo()
        self.assertEqual(metainfo[b'info'][b'piece length'], 2 ** 16)

    def test_is_private(self):
        """
        Test whether the private field from an existing torrent is correctly read
        """
        privatefn = os.path.join(TESTS_DATA_DIR, "private.torrent")
        publicfn = os.path.join(TESTS_DATA_DIR, "bak_single.torrent")

        t1 = TorrentDef.load(privatefn)
        t2 = TorrentDef.load(publicfn)

        self.assertTrue(t1.is_private())
        self.assertFalse(t2.is_private())

    @timeout(10)
    async def test_load_from_url(self):
        # Setup file server to serve torrent file
        self.session_base_dir = mkdtemp(suffix="_tribler_test_load_from_url")
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(files_path, 'ubuntu.torrent'))

        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server_port
        torrent_def = await TorrentDef.load_from_url(torrent_url)
        self.assertEqual(torrent_def.get_metainfo(), TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo())
        self.assertEqual(torrent_def.infohash, TorrentDef.load(TORRENT_UBUNTU_FILE).infohash)

    @timeout(10)
    async def test_load_from_url_404(self):
        # Setup file server to serve torrent file
        self.session_base_dir = mkdtemp(suffix="_tribler_test_load_from_url")
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        # Do not copy the torrent file to produce 404

        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server_port
        try:
            await TorrentDef.load_from_url(torrent_url)
        except ClientResponseError as e:
            self.assertEqual(e.status, 404)

    def test_torrent_encoding(self):
        t = TorrentDef()
        t.set_encoding("my_fancy_encoding")
        self.assertEqual(t.get_encoding(), "my_fancy_encoding")

    @raises(ValueError)
    def test_set_tracker_invalid_url(self):
        t = TorrentDef()
        t.set_tracker("http/tracker.org")

    def test_set_tracker_strip_slash(self):
        t = TorrentDef()
        t.set_tracker("http://tracker.org/")
        self.assertEqual(t.torrent_parameters[b'announce'], "http://tracker.org")

    def test_set_tracker(self):
        t = TorrentDef()
        self.assertFalse(t.get_trackers_as_single_tuple())
        t.set_tracker("http://tracker.org")
        self.assertEqual(t.get_trackers_as_single_tuple(), ('http://tracker.org',))

    def test_get_nr_pieces(self):
        """
        Test getting the number of pieces from a TorrentDef
        """
        tdef = TorrentDef()
        self.assertEqual(tdef.get_nr_pieces(), 0)

        tdef.metainfo = {b'info': {b'pieces': b'a' * 40}}
        self.assertEqual(tdef.get_nr_pieces(), 2)

    def test_is_multifile(self):
        """
        Test whether a TorrentDef is correctly classified as multifile torrent
        """
        tdef = TorrentDef()
        self.assertFalse(tdef.is_multifile_torrent())

        tdef.metainfo = {}
        self.assertFalse(tdef.is_multifile_torrent())

        tdef.metainfo = {b'info': {b'files': [b'a']}}
        self.assertTrue(tdef.is_multifile_torrent())

    @raises(ValueError)
    def test_set_piece_length_invalid_type(self):
        t = TorrentDef()
        t.set_piece_length("20")

    def test_get_piece_length(self):
        t = TorrentDef()
        self.assertEqual(t.get_piece_length(), 0)

    def test_load_from_dict(self):
        with open(os.path.join(TESTS_DATA_DIR, "bak_single.torrent"), mode='rb') as torrent_file:
            encoded_metainfo = torrent_file.read()
        self.assertTrue(TorrentDef.load_from_dict(bdecode_compat(encoded_metainfo)))

    def test_torrent_no_metainfo(self):
        torrent = TorrentDefNoMetainfo(b"12345678901234567890", VIDEO_FILE_NAME, "http://google.com")
        self.assertEqual(torrent.get_name(), VIDEO_FILE_NAME)
        self.assertEqual(torrent.get_infohash(), b"12345678901234567890")
        self.assertEqual(torrent.get_length(), 0) # there are no files
        self.assertFalse(torrent.get_metainfo())
        self.assertEqual(torrent.get_url(), "http://google.com")
        self.assertFalse(torrent.is_multifile_torrent())
        self.assertEqual(torrent.get_name_as_unicode(), VIDEO_FILE_NAME)
        self.assertFalse(torrent.get_files())
        self.assertFalse(torrent.get_files_with_length())
        self.assertFalse(torrent.get_trackers_as_single_tuple())
        self.assertFalse(torrent.is_private())

        torrent2 = TorrentDefNoMetainfo(b"12345678901234567890", VIDEO_FILE_NAME, "magnet:")
        self.assertFalse(torrent2.get_trackers_as_single_tuple())

    def test_files_no_metainfo(self):
        """
        Test whether a TorrentDef without metainfo has no files.
        """
        t = TorrentDef()
        self.assertEqual(0, len(t.get_files_with_length()))

    def test_get_length_no_metainfo(self):
        """
        Test whether a TorrentDef without metainfo has 0 length.
        """
        t = TorrentDef()
        self.assertEqual(0, t.get_length())

    def test_get_index(self):
        """
        Test whether we can successfully get the index of a file in a torrent.
        """
        t = TorrentDef()
        t.metainfo = {b'info': {b'files': [{b'path': [b'a.txt'], b'length': 123}]}}
        self.assertEqual(t.get_index_of_file_in_files('a.txt'), 0)
        self.assertRaises(ValueError, t.get_index_of_file_in_files, b'b.txt')
        self.assertRaises(ValueError, t.get_index_of_file_in_files, None)

        t.metainfo = {b'info': {b'files': [{b'path': [b'a.txt'], b'path.utf-8': [b'b.txt'], b'length': 123}]}}
        self.assertEqual(t.get_index_of_file_in_files('b.txt'), 0)

    def test_get_index_no_metainfo(self):
        """
        Test whether a ValueError is raised when attempting index access on TorrentDefs without metainfo.
        """
        t = TorrentDef()
        self.assertRaises(ValueError, t.get_index_of_file_in_files, u'?')
