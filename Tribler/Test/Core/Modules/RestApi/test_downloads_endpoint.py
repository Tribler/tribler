from binascii import hexlify
import json
import os
from urllib import pathname2url, quote_plus

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.common import UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TESTS_DATA_DIR


class TestDownloadsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestDownloadsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent(True)
        self.config.set_megacache(True)

    @deferred(timeout=10)
    def test_get_downloads_no_downloads(self):
        """
        Testing whether the API returns an empty list when downloads are fetched but no downloads are active
        """
        return self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200, expected_json={"downloads": []})

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
        return self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200).addCallback(verify_download)

    @deferred(timeout=10)
    def test_start_download_no_uri(self):
        """
        Testing whether an error is returned when we start a torrent download and do not pass any URI
        """
        self.should_check_equality = False
        return self.do_request('downloads', expected_code=400, request_type='PUT')

    @deferred(timeout=10)
    def test_start_download_bad_params(self):
        """
        Testing whether an error is returned when we start a torrent download and pass wrong data
        """
        self.should_check_equality = False
        post_data = {'anon_hops': 1, 'safe_seeding': 0, 'uri': 'abcd'}
        return self.do_request('downloads', expected_code=400, request_type='PUT', post_data=post_data)

    @deferred(timeout=10)
    def test_start_download_bad_uri(self):
        """
        Testing whether an error is returned when we start a download from a bad URI
        """
        post_data = {'uri': 'abcd', 'selected_files[]': 'a.txt'}
        return self.do_request('downloads', expected_code=500, request_type='PUT', post_data=post_data,
                               expected_json={'error': 'invalid uri'})

    @deferred(timeout=10)
    def test_start_download_from_file(self):
        """
        Testing whether we can start a download from a file
        """
        def verify_download(_):
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)

        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '42bb0a78d8a10bef4a5aee3a7d9f1edf9941cee4'}
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json).addCallback(verify_download)

    @deferred(timeout=10)
    def test_start_download_from_magnet(self):
        """
        Testing whether we can start a download from a magnet
        """
        def verify_download(_):
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)
            self.assertEqual(self.session.get_downloads()[0].get_def().get_name(), 'test torrent')

        post_data = {'uri': 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH),
                                                              quote_plus('test torrent'))}
        expected_json = {'started': True, 'infohash': 'fc8a15a2faf2734dbb1dc5f7afdc5c9beaeb1f59'}
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json).addCallback(verify_download)

    @deferred(timeout=10)
    def test_start_download_from_bad_url(self):
        """
        Testing whether starting a download from a unexisting URL gives an error
        """
        post_data = {'uri': 'http://localhost:%d/test.torrent' % get_random_port()}
        self.should_check_equality = False
        return self.do_request('downloads', expected_code=500, request_type='PUT', post_data=post_data)

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
        original_stop = download.stop

        def mocked_stop():
            download.should_stop = True
            download.stop = original_stop

        def verify_removed(_):
            self.assertEqual(len(self.session.get_downloads()), 1)
            download = self.session.get_downloads()[0]
            self.assertTrue(download.should_stop)

        download.stop = mocked_stop

        request_deferred = self.do_request('downloads/%s' % infohash, post_data={"state": "stop"},
                                           expected_code=200, expected_json={"modified": True}, request_type='PATCH')
        return request_deferred.addCallback(verify_removed)

    @deferred(timeout=10)
    def test_select_download_file(self):
        """
        Testing whether files can be correctly toggled in a download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        def mocked_set_selected_files(*_):
            mocked_set_selected_files.called = True

        mocked_set_selected_files.called = False

        def verify_method_called(_):
            self.assertTrue(mocked_set_selected_files.called)

        download.set_selected_files = mocked_set_selected_files

        return self.do_request('downloads/%s' % infohash, post_data={"selected_files[]": ""},
                               expected_code=200, expected_json={"modified": True}, request_type='PATCH')\
            .addCallback(verify_method_called)

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
        Testing whether starting an anon download without safe seeding specified gives an error
        """
        self.session.get_collected_torrent = lambda _: None
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.getTorrent = lambda infohash, keys: {"name": "test", "infohash": infohash, "keys": keys}

        post_data = {"anon_hops": 1, "safe_seeding": 0}
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
