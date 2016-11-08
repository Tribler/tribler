from binascii import hexlify
import json
import os
from urllib import pathname2url, quote_plus
import shutil
from twisted.internet.defer import inlineCallbacks
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TORRENT_FILE, UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TESTS_DATA_DIR
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTorrentInfoEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_get_torrentinfo(self):
        """
        Testing whether the API returns a correct dictionary with torrent info.
        """
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_FILE, os.path.join(files_path, 'ubuntu.torrent'))

        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        def verify_valid_dict(data):
            metainfo_dict = json.loads(data)
            self.assertTrue('metainfo' in metainfo_dict)
            self.assertTrue('info' in metainfo_dict['metainfo'])

        self.should_check_equality = False
        yield self.do_request('torrentinfo', expected_code=400)
        yield self.do_request('torrentinfo?uri=def', expected_code=400)

        path = "file:" + pathname2url(os.path.join(TESTS_DATA_DIR, "bak_single.torrent")).encode('utf-8')

        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=200).addCallback(verify_valid_dict)

        path = "http://localhost:%d/ubuntu.torrent" % file_server_port
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=200).addCallback(verify_valid_dict)

        def call_cb(infohash, callback, **_):
            callback({"info": {"pieces": "abc"}})

        path = 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH), quote_plus('test torrent'))
        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = call_cb
        self.session.lm.ltmgr.shutdown = lambda: None
        yield self.do_request('torrentinfo?uri=%s' % path, expected_code=200).addCallback(verify_valid_dict)
