from __future__ import absolute_import
import logging
import os
import shutil
from tempfile import mkdtemp

import six
from libtorrent import bdecode
from nose.tools import raises
from Tribler.Test.tools import trial_timeout
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.server import Site
from twisted.web.static import File

from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.utilities import create_valid_metainfo, valid_torrent_file
from Tribler.Core.exceptions import TorrentDefNotFinalizedException, HttpError
from Tribler.Core.simpledefs import INFOHASH_LENGTH
from Tribler.Test.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import BaseTestCase

TRACKER = 'http://www.tribler.org/announce'


class TestTorrentDef(BaseTestCase):

    VIDEO_FILE_NAME = "video.avi"

    """
    Testing TorrentDef version 0
    """
    def __init__(self, *argv, **kwargs):
        super(TestTorrentDef, self).__init__(*argv, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.file_server = None

    def setUpFileServer(self, port, path):
        # Create a local file server, can be used to serve local files. This is preferred over an external network
        # request in order to get files.
        resource = File(path)
        factory = Site(resource)
        self.file_server = reactor.listenTCP(port, factory)

    @inlineCallbacks
    def tearDown(self):
        super(TestTorrentDef, self).tearDown()
        if self.file_server:
            yield self.file_server.stopListening()

    def test_add_content_file_and_copy(self):
        """ Add a single file to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_DATA_DIR, self.VIDEO_FILE_NAME)
        t.add_content(fn)
        t.set_tracker(TRACKER)
        t.finalize()

        s = os.path.getsize(fn)

        metainfo = t.get_metainfo()
        self.general_check(metainfo)

        self.assertEqual(metainfo['info']['name'], self.VIDEO_FILE_NAME)
        self.assertEqual(metainfo['info']['length'], s)
        self.assertTrue(t.get_pieces())
        self.assertEqual(len(t.get_infohash()), INFOHASH_LENGTH)
        self.assertTrue(t.get_name())

        # test copy constructor
        nt = TorrentDef(t.input, t.metainfo, t.infohash)
        self.assertEqual(nt.input, t.input)
        self.assertEqual(nt.metainfo, t.metainfo)
        self.assertEqual(nt.infohash, t.infohash)

        # test removing content
        nt.remove_content("/test123")
        self.assertEqual(len(nt.input['files']), 1)
        nt.remove_content(six.text_type(fn))
        self.assertEqual(len(nt.input['files']), 0)
        nt.remove_content(six.text_type(fn))

    def test_add_content_dir(self):
        """ Add a single dir to a TorrentDef """
        t = TorrentDef()
        dn = os.path.join(TESTS_DATA_DIR, "contentdir")
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
            self._logger.debug("Expected size %s %d", f, s)

        self._logger.debug("Expected total size of files in torrent %d", exps)

        metainfo = t.get_metainfo()
        self.general_check(metainfo)

        self.assertEqual(metainfo['info']['name'], b'dirintorrent')
        reals = 0
        for file in metainfo['info']['files']:
            s = file['length']
            self._logger.debug("real size %s %d", file['path'], s)
            reals += s

        self._logger.debug("Real size of files in torrent %d", reals)

        self.assertEqual(exps, reals)

    def test_add_content_dir_and_file(self):
        """ Add a single dir and single file to a TorrentDef """
        t = TorrentDef()

        dn = os.path.join(TESTS_DATA_DIR, "contentdir")
        t.add_content(dn, "dirintorrent")

        fn = os.path.join(TESTS_DATA_DIR, self.VIDEO_FILE_NAME)
        t.add_content(fn, os.path.join("dirintorrent", self.VIDEO_FILE_NAME))

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
        self.assertEqual(metainfo['info']['name'], b'dirintorrent')

        reals = 0
        for file in metainfo['info']['files']:
            reals += file['length']
        self.assertEqual(exps, reals)

    def test_get_name_utf8(self):
        """ Add a TorrentDef with non-utf8 encoding"""
        t = TorrentDef()
        t.set_name('\xA1\xC0')
        t.set_encoding('euc_kr')
        t.set_tracker(TRACKER)
        t.finalize()

        self.assertEqual(t.get_name_utf8(), u'\xf7')

    def test_get_name_utf8_unknown(self):
        """ Add a TorrentDef with non-utf8 encoding"""
        t = TorrentDef()
        t.set_name('\xA1\xC0')
        t.set_tracker(TRACKER)
        t.finalize()

        self.assertEqual(t.get_name_utf8(), u'\xa1\xc0')

    def test_add_content_announce_list(self):
        """ Add a single file with announce-list to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_DATA_DIR, self.VIDEO_FILE_NAME)

        t.add_content(fn)
        t.set_tracker(TRACKER)
        exphier = [[TRACKER], ['http://tracker1.tribler.org:6969/announce', 'http://tracker2.tribler.org:7070/ann'],
                   ['http://www.cs.vu.nl', 'http://www.st.ewi.tudelft.nl', 'http://www.vuze.com']]
        t.set_tracker_hierarchy(exphier)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        realhier = metainfo['announce-list']
        self.assertEqual(realhier, exphier)

    def test_add_content_httpseeds(self):
        """ Add a single file with BitTornado httpseeds to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_DATA_DIR, self.VIDEO_FILE_NAME)
        t.add_content(fn)
        t.set_tracker(TRACKER)
        expseeds = ['http://www.cs.vu.nl/index.html', 'http://www.st.ewi.tudelft.nl/index.html']
        t.set_httpseeds(expseeds)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        realseeds = metainfo['httpseeds']
        self.assertEqual(realseeds, expseeds)

    def test_add_content_piece_length(self):
        """ Add a single file with piece length to a TorrentDef """
        t = TorrentDef()
        fn = os.path.join(TESTS_DATA_DIR, self.VIDEO_FILE_NAME)
        t.add_content(fn)
        t.set_piece_length(2 ** 16)
        t.set_tracker(TRACKER)
        t.finalize()

        metainfo = t.get_metainfo()
        self.general_check(metainfo)
        self.assertEqual(metainfo['info']['piece length'], 2 ** 16)

    def test_add_content_file_save(self):
        """ Add a single file to a TorrentDef and save the latter"""
        t = TorrentDef()
        fn = os.path.join(TESTS_DATA_DIR, self.VIDEO_FILE_NAME)
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
        self.assertEqual(metainfo, data)

    def test_is_private(self):
        privatefn = os.path.join(TESTS_DATA_DIR, "private.torrent")
        publicfn = os.path.join(TESTS_DATA_DIR, "bak_single.torrent")

        t1 = TorrentDef.load(privatefn)
        t2 = TorrentDef.load(publicfn)

        self.assertTrue(t1.is_private())
        self.assertFalse(t2.is_private())

    @trial_timeout(10)
    def test_load_from_url(self):
        # Setup file server to serve torrent file
        self.session_base_dir = mkdtemp(suffix="_tribler_test_load_from_url")
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(files_path, 'ubuntu.torrent'))

        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        def _on_load(torrent_def):
            torrent_def.metainfo = create_valid_metainfo(torrent_def.get_metainfo())
            self.assertTrue(valid_torrent_file(torrent_def.get_metainfo()))
            self.assertEqual(torrent_def.get_metainfo(), TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo())
            self.assertEqual(torrent_def.infohash, TorrentDef.load(TORRENT_UBUNTU_FILE).infohash)

        torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server_port
        deferred = TorrentDef.load_from_url(torrent_url)
        deferred.addCallback(_on_load)
        return deferred

    @trial_timeout(10)
    def test_load_from_url_404(self):
        # Setup file server to serve torrent file
        self.session_base_dir = mkdtemp(suffix="_tribler_test_load_from_url")
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        # Do not copy the torrent file to produce 404

        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        def _on_error(failure):
            failure.trap(HttpError)
            self.assertEqual(failure.value.response.code, 404)

        torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server_port
        deferred = TorrentDef.load_from_url(torrent_url)
        deferred.addErrback(_on_error)
        return deferred

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
        self.assertEqual(t.input['announce'], "http://tracker.org")

    @raises(ValueError)
    def test_set_trackers_no_list_hierarchy(self):
        t = TorrentDef()
        t.set_tracker_hierarchy("http://tracker.org")

    @raises(ValueError)
    def test_set_trackers_no_list_tier(self):
        t = TorrentDef()
        t.set_tracker_hierarchy(["http://tracker.org"])

    def test_set_trackers(self):
        t = TorrentDef()
        t.set_tracker_hierarchy([["http://tracker.org", "http://tracker2.org/", "http/tracker3.org"]])
        self.assertEqual(len(t.get_tracker_hierarchy()[0]), 2)
        self.assertEqual(t.get_tracker_hierarchy()[0][0], "http://tracker.org")
        self.assertEqual(t.get_tracker_hierarchy()[0][1], "http://tracker2.org")

        self.assertEqual(t.get_trackers_as_single_tuple(), ('http://tracker.org', 'http://tracker2.org'))

    def test_set_tracker(self):
        t = TorrentDef()
        self.assertFalse(t.get_trackers_as_single_tuple())
        t.set_tracker("http://tracker.org")
        self.assertEqual(t.get_trackers_as_single_tuple(), ('http://tracker.org',))

    @raises(ValueError)
    def test_set_dht_nodes_no_list(self):
        t = TorrentDef()
        t.set_dht_nodes(("127.0.0.1", 1234))

    @raises(ValueError)
    def test_set_dht_nodes_node_no_list(self):
        t = TorrentDef()
        t.set_dht_nodes([("127.0.0.1", 1234)])

    @raises(ValueError)
    def test_set_dht_nodes_node_no_string(self):
        t = TorrentDef()
        t.set_dht_nodes([[1234, "127.0.0.1"]])

    @raises(ValueError)
    def test_set_dht_nodes_node_no_int(self):
        t = TorrentDef()
        t.set_dht_nodes([["127.0.0.1", "1234"]])

    def test_set_dht_nodes(self):
        t = TorrentDef()
        t.set_dht_nodes([["127.0.0.1", 1234]])
        self.assertEqual(t.get_dht_nodes(), [["127.0.0.1", 1234]])

    def test_set_comment(self):
        t = TorrentDef()
        t.set_comment("lorem ipsum")
        self.assertEqual(t.get_comment(), "lorem ipsum")
        self.assertEqual(t.get_comment_as_unicode(), u"lorem ipsum")

    def test_set_created_by(self):
        t = TorrentDef()
        t.set_created_by("dolor sit")
        self.assertEqual(t.get_created_by(), "dolor sit")

    @raises(ValueError)
    def test_set_urllist_wrong_url(self):
        t = TorrentDef()
        t.set_urllist(["http/url.com"])

    def test_set_urllist_urls(self):
        t = TorrentDef()
        t.set_urllist(["http://url.com"])
        self.assertEqual(t.get_urllist(), ["http://url.com"])

    @raises(ValueError)
    def test_set_httpseeds_wrong_url(self):
        t = TorrentDef()
        t.set_httpseeds(["http/httpseed.com"])

    def test_set_httpseeds(self):
        t = TorrentDef()
        t.set_httpseeds(["http://httpseed.com"])
        self.assertEqual(t.get_httpseeds(), ["http://httpseed.com"])

    @raises(ValueError)
    def test_set_piece_length_invalid_type(self):
        t = TorrentDef()
        t.set_piece_length("20")

    def test_get_piece_length(self):
        t = TorrentDef()
        self.assertEqual(t.get_piece_length(), 0)

    @raises(TorrentDefNotFinalizedException)
    def test_get_infohash(self):
        t = TorrentDef()
        t.get_infohash()

    @raises(TorrentDefNotFinalizedException)
    def test_set_name(self):
        t = TorrentDef()
        t.set_name("lorem ipsum")
        t.get_name()

    def test_load_from_dict(self):
        metainfo = {"info": {"name": "my_torrent", "piece length": 12345, "pieces": "12345678901234567890",
                                   "files": []}}
        torrent = TorrentDef.load_from_dict(metainfo)
        self.assertTrue(valid_torrent_file(torrent.get_metainfo()))

    @raises(TorrentDefNotFinalizedException)
    def test_no_valid_metainfo(self):
        t = TorrentDef()
        t.get_metainfo()

    def test_initial_peers(self):
        t = TorrentDef()
        self.assertFalse(t.get_initial_peers())

    def test_set_initial_peers(self):
        t = TorrentDef()
        t.set_initial_peers([("127.0.0.1", 1234)])
        self.assertEqual(t.get_initial_peers(), [("127.0.0.1", 1234)])

    def test_torrent_no_metainfo(self):
        torrent = TorrentDefNoMetainfo("12345678901234567890", self.VIDEO_FILE_NAME, "http://google.com")
        self.assertEqual(torrent.get_name(), self.VIDEO_FILE_NAME)
        self.assertEqual(torrent.get_infohash(), "12345678901234567890")
        self.assertEqual(torrent.get_length(), 0) # there are no files
        self.assertFalse(torrent.get_metainfo())
        self.assertEqual(torrent.get_url(), "http://google.com")
        self.assertFalse(torrent.is_multifile_torrent())
        self.assertEqual(torrent.get_name_as_unicode(), six.text_type(self.VIDEO_FILE_NAME))
        self.assertFalse(torrent.get_files())
        self.assertFalse(torrent.get_files_with_length())
        self.assertFalse(torrent.get_trackers_as_single_tuple())
        self.assertFalse(torrent.is_private())

        torrent2 = TorrentDefNoMetainfo("12345678901234567890", self.VIDEO_FILE_NAME, "magnet:")
        self.assertFalse(torrent2.get_trackers_as_single_tuple())

    def general_check(self, metainfo):
        self.assertTrue(valid_torrent_file(metainfo))
        self.assertEqual(metainfo['announce'], TRACKER)

    def test_get_index(self):
        t = TorrentDef()
        t.metainfo_valid = True
        t.metainfo = {'info': {'files': [{'path': ['a.txt'], 'length': 123}]}}
        self.assertEqual(t.get_index_of_file_in_files('a.txt'), 0)
        self.assertRaises(ValueError, t.get_index_of_file_in_files, 'b.txt')
        self.assertRaises(ValueError, t.get_index_of_file_in_files, None)

        t.metainfo = {'info': {'files': [{'path': ['a.txt'], 'path.utf-8': ['b.txt'], 'length': 123}]}}
        self.assertEqual(t.get_index_of_file_in_files('b.txt'), 0)
