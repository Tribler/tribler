import base64
import os
import shutil

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.common import TESTS_DATA_DIR
from nose.twistedtools import deferred


class TestMyChannelCreateTorrentEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestMyChannelCreateTorrentEndpoint, self).setUpPreSession()
        # Create temporary test directory with test files
        self.files_path = os.path.join(self.session_base_dir, 'TestMyChannelCreateTorrentEndpoint')
        if not os.path.exists(self.files_path):
            os.mkdir(self.files_path)
        shutil.copyfile(os.path.join(TESTS_DATA_DIR, 'video.avi'),
                        os.path.join(self.files_path, 'video.avi'))
        shutil.copyfile(os.path.join(TESTS_DATA_DIR, 'video.avi.torrent'),
                        os.path.join(self.files_path, 'video.avi.torrent'))
        self.config.set_libtorrent_enabled(True)

    @deferred(timeout=10)
    def test_create_torrent(self):
        """
        Testing whether the API returns a proper base64 encoded torrent
        """
        torrent_path = os.path.join(self.files_path, "video.avi.torrent")
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

            self.assertEqual(dir(expected_tdef), dir(tdef))

        post_data = {
            "name": "my-video.avi",
            "files[]": os.path.join(self.files_path, "video.avi"),
            "description": "Video of my cat",
            "trackers[]": "http://localhost/announce"
        }
        self.should_check_equality = False
        return self.do_request('createtorrent?download=1', 200, None, 'POST', post_data).addCallback(verify_torrent)

    @deferred(timeout=10)
    def test_torrent_name_is_as_specified(self):
        """
        Testing whether the torrent file is created with the name provided (with unicode support)
        """
        torrent_name = "\xca\x87u\xc7\x9d\xc9\xb9\xc9\xb9o\xca\x87-video.avi".decode("utf-8")
        torrent_path = os.path.join(self.files_path, "%s.torrent" % torrent_name)

        def verify_torrent_exists():
            self.assertTrue(os.path.exists(torrent_path))
            self.assertTrue(os.path.isfile(torrent_path))

        post_data = {
            "name": torrent_name.encode('utf-8'),
            "files[]": os.path.join(self.files_path, "video.avi"),
            "description": "Video of my cat",
            "trackers[]": "http://localhost/announce"
        }
        self.should_check_equality = False
        return self.do_request('createtorrent?download=1', 200, None, 'POST', post_data)\
            .addCallback(lambda response: verify_torrent_exists())

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
                    u"message": u"Path does not exist: %s" % post_data["files[]"]
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        post_data = {
            "files[]": "non_existing_file.avi"
        }
        self.should_check_equality = False
        return self.do_request('createtorrent', 500, None, 'POST', post_data).addCallback(verify_error_message)

    @deferred(timeout=10)
    def test_create_torrent_missing_files_parameter(self):
        expected_json = {"error": "files parameter missing"}
        return self.do_request('createtorrent', 400, expected_json, 'POST')
