import json
import os
from urllib import pathname2url

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.test_as_server import TESTS_DATA_DIR


class TestDownloadsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestDownloadsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent(True)

    @deferred(timeout=10)
    def test_get_downloads_no_downloads(self):
        """
        Testing whether the API returns an empty list when downloads are fetched but no downloads are active
        """
        return self.do_request('downloads', expected_code=200, expected_json={"downloads": []})

    @deferred(timeout=20)
    def test_get_downloads(self):
        """
        Testing whether the API returns the right download when a download is added
        """
        def verify_download(downloads):
            downloads_json = json.loads(downloads)
            self.assertEqual(len(downloads_json['downloads']), 2)

        video_tdef, self.torrent_path = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        self.session.start_download_from_uri("file:" + pathname2url(
            os.path.join(TESTS_DATA_DIR, "bak_multiple.torrent")))

        self.should_check_equality = False
        return self.do_request('downloads', expected_code=200).addCallback(verify_download)
