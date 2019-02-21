from __future__ import absolute_import

import os
import shutil
from binascii import hexlify
from urllib import pathname2url, quote_plus

from twisted.internet.defer import inlineCallbacks

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE, UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TESTS_DATA_DIR, TESTS_DIR
from Tribler.Test.tools import trial_timeout

SAMPLE_CHANNEL_FILES_DIR = os.path.join(TESTS_DIR, "Core", "data", "sample_channel")


class TestTorrentInfoEndpoint(AbstractApiTest):

    @inlineCallbacks
    def test_get_torrentinfo(self):
        """
        Testing whether the API returns a correct dictionary with torrent info.
        """
        # We intentionally put the file path in a folder with a:
        # - "+" which is a reserved URI character
        # - "\u0191" which is a unicode character
        files_path = os.path.join(self.session_base_dir, u'http_torrent_+\u0191files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(files_path, 'ubuntu.torrent'))

        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        def verify_valid_dict(data):
            metainfo_dict = json.loads(data, encoding='latin_1')
            self.assertTrue('metainfo' in metainfo_dict)
            self.assertTrue('info' in metainfo_dict['metainfo'])

        self.should_check_equality = False
        yield self.do_request('torrentinfo', expected_code=400)
        yield self.do_request('torrentinfo?uri=def', expected_code=400)

        path = "file:" + pathname2url(os.path.join(TESTS_DATA_DIR, "bak_single.torrent")).encode('utf-8')
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=200).addCallback(verify_valid_dict)

        # Corrupt file
        path = "file:" + pathname2url(os.path.join(TESTS_DATA_DIR, "test_rss.xml")).encode('utf-8')
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

        path = "http://localhost:%d/ubuntu.torrent" % file_server_port
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=200).addCallback(verify_valid_dict)

        def get_metainfo(infohash, callback, **_):
            with open(os.path.join(TESTS_DATA_DIR, "bak_single.torrent"), mode='rb') as torrent_file:
                torrent_data = torrent_file.read()
            tdef = TorrentDef.load_from_memory(torrent_data)
            callback(tdef.get_metainfo())

        def get_metainfo_timeout(*args, **kwargs):
            timeout_cb = kwargs.get('timeout_callback')
            timeout_cb('a' * 20)

        path = 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH), quote_plus('test torrent'))
        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo
        self.session.lm.ltmgr.shutdown = lambda: None
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=200).addCallback(verify_valid_dict)

        # mdblob file
        path_blob = "file:" + pathname2url(os.path.join(SAMPLE_CHANNEL_FILES_DIR, "channel.mdblob")).encode('utf-8')
        yield self.do_request('torrentinfo?uri=%s' % path_blob, expected_code=200).addCallback(verify_valid_dict)

        path = 'magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1'  # No infohash
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=400)

        path = 'magnet:?xt=urn:btih:%s&dn=%s' % ('a' * 40, quote_plus('test torrent'))
        self.session.lm.ltmgr.get_metainfo = get_metainfo_timeout
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=408)

        self.session.lm.ltmgr.get_metainfo = get_metainfo
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=200).addCallback(verify_valid_dict)

        path = 'http://fdsafksdlafdslkdksdlfjs9fsafasdf7lkdzz32.n38/324.torrent'
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

    @trial_timeout(10)
    def test_on_got_invalid_metainfo(self):
        """
        Test whether the right operations happen when we receive an invalid metainfo object
        """
        def get_metainfo(infohash, callback, **_):
            callback("abcd")

        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo
        self.session.lm.ltmgr.shutdown = lambda: None
        path = 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH), quote_plus('test torrent'))

        self.should_check_equality = False
        return self.do_request('torrentinfo?uri=%s' % path, expected_code=500)
