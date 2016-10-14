import json
import os
from urllib import pathname2url

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.test_as_server import TESTS_DATA_DIR


class TestDownloadsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestDownloadsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_megacache_enabled(True)

    @deferred(timeout=10)
    def test_get_downloads_no_downloads(self):
        """
        Testing whether the API returns an empty list when downloads are fetched but no downloads are active
        """
        return self.do_request('downloads?get_peers=1', expected_code=200, expected_json={"downloads": []})

    @deferred(timeout=20)
    def test_get_downloads(self):
        """
        Testing whether the API returns the right download when a download is added
        """
        def verify_download(downloads):
            downloads_json = json.loads(downloads)
            self.assertEqual(len(downloads_json['downloads']), 2)

        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        self.session.start_download_from_uri("file:" + pathname2url(
            os.path.join(TESTS_DATA_DIR, "bak_single.torrent")))

        self.should_check_equality = False
        return self.do_request('downloads?get_peers=1', expected_code=200).addCallback(verify_download)

    @deferred(timeout=10)
    def test_remove_download_no_remove_data_param(self):
        """
        Testing whether the API returns error 400 if the remove_data parameter is not passed
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', expected_code=400, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is removed
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', post_data={"remove_data": True},
                               expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_download(self):
        """
        Testing whether the API returns 200 if a download is being removed
        """
        def verify_removed(_):
            self.assertEqual(len(self.session.get_downloads()), 0)

        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        request_deferred = self.do_request('downloads/%s' % infohash, post_data={"remove_data": True},
                                           expected_code=200, expected_json={"removed": True}, request_type='DELETE')
        return request_deferred.addCallback(verify_removed)

    @deferred(timeout=10)
    def test_stop_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is stopped
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', expected_code=404, post_data={"state": "stop"}, request_type='PATCH')

    @deferred(timeout=10)
    def test_stop_download(self):
        """
        Testing whether the API returns 200 if a download is being stopped
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        def mocked_stop():
            download.should_stop = True

        def verify_removed(_):
            self.assertEqual(len(self.session.get_downloads()), 1)
            download = self.session.get_downloads()[0]
            self.assertTrue(download.should_stop)

        download.stop = mocked_stop

        request_deferred = self.do_request('downloads/%s' % infohash, post_data={"state": "stop"},
                                           expected_code=200, expected_json={"modified": True}, request_type='PATCH')
        return request_deferred.addCallback(verify_removed)

    @deferred(timeout=10)
    def test_resume_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is resumed
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', expected_code=404, post_data={"state": "resume"}, request_type='PATCH')

    @deferred(timeout=10)
    def test_resume_download(self):
        """
        Testing whether the API returns 200 if a download is being resumed
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        def mocked_restart():
            download.should_restart = True

        def verify_resumed(_):
            self.assertEqual(len(self.session.get_downloads()), 1)
            download = self.session.get_downloads()[0]
            self.assertTrue(download.should_restart)

        download.restart = mocked_restart

        request_deferred = self.do_request('downloads/%s' % infohash, post_data={"state": "resume"},
                                           expected_code=200, expected_json={"modified": True}, request_type='PATCH')
        return request_deferred.addCallback(verify_resumed)

    @deferred(timeout=10)
    def test_recheck_download(self):
        """
        Testing whether the API returns 200 if a download is being rechecked
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        def mocked_recheck():
            mocked_recheck.called = True

        mocked_recheck.called = False
        download.force_recheck = mocked_recheck

        def verify_rechecked(_):
            self.assertEqual(len(self.session.get_downloads()), 1)
            self.assertTrue(mocked_recheck.called)

        request_deferred = self.do_request('downloads/%s' % infohash, post_data={"state": "recheck"},
                                           expected_code=200, expected_json={"modified": True}, request_type='PATCH')
        return request_deferred.addCallback(verify_rechecked)

    @deferred(timeout=10)
    def test_download_unknown_state(self):
        """
        Testing whether the API returns error 400 if an unknown state is passed when modifying a download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())

        self.should_check_equality = False
        return self.do_request('downloads/%s' % video_tdef.get_infohash().encode('hex'), expected_code=400,
                               post_data={"state": "abc"}, request_type='PATCH')

    @deferred(timeout=10)
    def test_export_unknown_download(self):
        """
        Testing whether the API returns error 404 if a non-existent download is exported
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd/torrent', expected_code=404, request_type='GET')

    @deferred(timeout=10)
    def test_export_download(self):
        """
        Testing whether the API returns the contents of the torrent file if a download is exported
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())

        with open(os.path.join(TESTS_DATA_DIR, 'bak_single.torrent')) as torrent_file:
            raw_data = torrent_file.read()
        self.session.get_collected_torrent = lambda _: raw_data

        def verify_exported_data(result):
            self.assertEqual(raw_data, result)

        self.should_check_equality = False
        return self.do_request('downloads/%s/torrent' % video_tdef.get_infohash().encode('hex'),
                               expected_code=200, request_type='GET').addCallback(verify_exported_data)

    @deferred(timeout=20)
    def test_start_download_hash(self):
        """
        Testing whether starting a download from an infohash works
        """
        self.session.get_collected_torrent = lambda _: None
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.getTorrent = lambda infohash, keys: {"name": "test", "infohash": infohash, "keys": keys}

        def verify_download(_):
            self.assertEqual(len(self.session.get_downloads()), 1)

        return self.do_request('downloads/%s' % ('a' * 40), expected_code=200,
                               expected_json={"started": True}, request_type='PUT').addCallback(verify_download)

    @deferred(timeout=20)
    def test_start_download_hash_anon(self):
        """
        Testing whether starting a download anonymously from an infohash works
        """
        self.session.get_collected_torrent = lambda _: None
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.getTorrent = lambda infohash, keys: {"name": "test", "infohash": infohash, "keys": keys}

        def verify_download(_):
            self.assertEqual(len(self.session.get_downloads()), 1)
            download = self.session.get_downloads()[0]
            self.assertEqual(download.get_hops(), 2)
            self.assertTrue(download.get_safe_seeding())

        post_data = {"anon_hops": 2, "safe_seeding": 1, "destination": self.session_base_dir}
        return self.do_request('downloads/%s' % ('a' * 40), expected_code=200,
                               expected_json={"started": True}, request_type='PUT', post_data=post_data)\
            .addCallback(verify_download)

    @deferred(timeout=20)
    def test_start_download_invalid_dir(self):
        """
        Testing whether starting a download with an invalid directory specified gives an error
        """
        self.session.get_collected_torrent = lambda _: None
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.getTorrent = lambda infohash, keys: {"name": "test", "infohash": infohash, "keys": keys}

        post_data = {"destination": "thispathdoesnotexist123"}
        self.should_check_equality = False
        return self.do_request('downloads/%s' % ('a' * 40), expected_code=400, request_type='PUT', post_data=post_data)

    @deferred(timeout=20)
    def test_start_down_no_anon_param(self):
        """
        Testing whether starting a safe-seeding download without anon download specified gives an error
        """
        self.session.get_collected_torrent = lambda _: None
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.getTorrent = lambda infohash, keys: {"name": "test", "infohash": infohash, "keys": keys}

        post_data = {"safe_seeding": 1}
        self.should_check_equality = False
        return self.do_request('downloads/%s' % ('a' * 40), expected_code=400, request_type='PUT', post_data=post_data)

    @deferred(timeout=20)
    def test_start_download_hash_cache(self):
        """
        Testing whether starting a download from an infohash present in the megacache works
        """
        with open(os.path.join(TESTS_DATA_DIR, 'private.torrent')) as torrent_file:
            raw_data = torrent_file.read()
        self.session.get_collected_torrent = lambda _: raw_data

        def verify_download(_):
            self.assertEqual(len(self.session.get_downloads()), 1)

        return self.do_request('downloads/%s' % ('a' * 40), expected_code=200,
                               expected_json={"started": True}, request_type='PUT').addCallback(verify_download)

    @deferred(timeout=20)
    def test_start_download_hash_twice(self):
        """
        Testing whether starting a download from an infohash twice raises error 409
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())

        return self.do_request('downloads/%s' % video_tdef.get_infohash().encode('hex'), expected_code=409,
                               request_type='PUT')
