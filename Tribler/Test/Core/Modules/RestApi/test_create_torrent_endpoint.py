import base64
import os
import shutil

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.tools import timeout


class TestMyChannelCreateTorrentEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestMyChannelCreateTorrentEndpoint, self).setUpPreSession()
        # Create temporary test directory with test files
        self.files_path = self.session_base_dir / 'TestMyChannelCreateTorrentEndpoint'
        if not self.files_path.exists():
            os.mkdir(self.files_path)
        shutil.copyfile(TESTS_DATA_DIR / 'video.avi',
                        self.files_path / 'video.avi')
        shutil.copyfile(TESTS_DATA_DIR / 'video.avi.torrent',
                        self.files_path / 'video.avi.torrent')
        self.config.set_libtorrent_enabled(True)

    @timeout(10)
    async def test_create_torrent(self):
        """
        Testing whether the API returns a proper base64 encoded torrent
        """
        torrent_path = self.files_path / "video.avi.torrent"
        expected_tdef = TorrentDef.load(torrent_path)
        export_dir = self.temporary_directory()

        post_data = {
            "files": [self.files_path / "video.avi",
                      self.files_path / "video.avi.torrent"],
            "description": "Video of my cat",
            "trackers": "http://localhost/announce",
            "name": "test_torrent",
            "export_dir": export_dir
        }
        response_dict = await self.do_request('createtorrent?download=1', 200, None, 'POST', post_data)
        torrent = base64.b64decode(response_dict["torrent"])
        tdef = TorrentDef.load_from_memory(torrent)

        # Copy expected creation date and created by (Tribler version) from actual result
        creation_date = tdef.get_creation_date()
        expected_tdef.metainfo[b"creation date"] = creation_date
        expected_tdef.metainfo[b"created by"] = tdef.metainfo[b'created by']

        self.assertEqual(dir(expected_tdef), dir(tdef))
        self.assertTrue((export_dir / "test_torrent.torrent").exists())

    @timeout(10)
    async def test_create_torrent_io_error(self):
        """
        Testing whether the API returns a formatted 500 error if IOError is raised
        """
        post_data = {
            "files": "non_existing_file.avi"
        }
        error_response = await self.do_request('createtorrent', 500, None, 'POST', post_data)
        expected_response = {
            u"error": {
                u"handled": True,
                u"message": u"Path does not exist: %s" % post_data["files"]
            }
        }
        self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])
        self.assertIn(error_response[u"error"][u"code"], [u"IOError", u"OSError"])

    @timeout(10)
    async def test_create_torrent_missing_files_parameter(self):
        expected_json = {"error": "files parameter missing"}
        await self.do_request('createtorrent', 400, expected_json, 'POST')
