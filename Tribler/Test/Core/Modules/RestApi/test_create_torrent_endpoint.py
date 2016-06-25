import json
import base64
import os

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.test_as_server import TESTS_DATA_DIR


class TestMyChannelCreateTorrentEndpoint(AbstractApiTest):

    def tearDown(self):
        super(TestMyChannelCreateTorrentEndpoint, self).tearDown()
        torrent_path = os.path.join(TESTS_DATA_DIR, os.path.basename(TESTS_DATA_DIR) + ".torrent")
        if os.path.exists(torrent_path):
            os.remove(torrent_path)

    @deferred(timeout=10)
    def test_create_torrent(self):
        """
        Testing whether the API returns a proper base64 encoded torrent
        """
        torrent_path = os.path.join(TESTS_DATA_DIR, "video.avi.torrent")
        expected_tdef = TorrentDef.load(torrent_path)

        def verify_torrent(body):
            response = json.loads(body)
            torrent = base64.b64decode(response["torrent"])
            tdef = TorrentDef.load_from_memory(torrent)

            # Copy expected creation date and created by (Tribler version) from actual result
            creation_date = tdef.get_creation_date()
            expected_tdef.metainfo["creation date"] = creation_date
            created_by = tdef.get_created_by()
            expected_tdef.metainfo["created by"] = created_by

            self.assertEqual(expected_tdef, tdef)

        post_data = {
            "files": [os.path.join(TESTS_DATA_DIR, "video.avi")],
            "description": "Video of my cat",
            "trackers": ["http://localhost/announce"]
        }
        self.should_check_equality = False
        return self.do_request('createtorrent', 200, None, 'GET', post_data).addCallback(verify_torrent)

    @deferred(timeout=10)
    def test_create_torrent_io_error(self):
        """
        Testing whether the API returns a formatted 500 error if IOError is raised
        """

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": True,
                    u"code": u"IOError",
                    u"message": u"Path does not exist: %s" % post_data["files"][0]
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        post_data = {
            "files": ["non_existing_file.avi"]
        }
        self.should_check_equality = False
        return self.do_request('createtorrent', 500, None, 'GET', post_data).addCallback(verify_error_message)

    @deferred(timeout=10)
    def test_create_torrent_missing_files_parameter(self):
        expected_json = {"error": "files parameter missing"}
        return self.do_request('createtorrent', 400, expected_json, 'GET')
