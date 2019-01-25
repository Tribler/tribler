import os
from binascii import hexlify
from urllib import pathname2url

from pony.orm import db_session
from twisted.internet.defer import fail

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import UBUNTU_1504_INFOHASH, TESTS_DATA_DIR, TESTS_DIR
from Tribler.Test.tools import trial_timeout


class TestDownloadsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestDownloadsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_megacache_enabled(True)
        self.config.set_torrent_store_enabled(True)

    @trial_timeout(10)
    def test_get_downloads_no_downloads(self):
        """
        Testing whether the API returns an empty list when downloads are fetched but no downloads are active
        """
        return self.do_request('downloads?get_peers=1&get_pieces=1',
                               expected_code=200, expected_json={"downloads": []})

    @trial_timeout(20)
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
        return self.do_request('downloads?get_peers=1&get_pieces=1',
                               expected_code=200).addCallback(verify_download)

    @trial_timeout(20)
    def test_get_downloads_with_files(self):
        """
        Testing whether the API returns the right right filenames fpr each download
        """

        def verify_download(downloads):
            downloads_json = json.loads(downloads)
            self.assertEqual(len(downloads_json['downloads']), 2)
            self.assertEqual(downloads_json['downloads'][0][u'files'],
                             [{u'included': True, u'index': 0, u'size': 1583233,
                               u'name': u'Tribler_4.1.7_src.zip', u'progress': 0.0}])
            self.assertEqual(downloads_json['downloads'][1][u'files'],
                             [{u'included': True, u'index': 0, u'size': 1942100,
                               u'name': u'video.avi', u'progress': 0.0}])

        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        self.session.start_download_from_uri("file:" + pathname2url(
            os.path.join(TESTS_DATA_DIR, "bak_single.torrent")))

        self.should_check_equality = False
        return self.do_request('downloads?get_peers=1&get_pieces=1&&get_files=1',
                               expected_code=200).addCallback(verify_download)

    @trial_timeout(10)
    def test_start_download_no_uri(self):
        """
        Testing whether an error is returned when we start a torrent download and do not pass any URI
        """
        self.should_check_equality = False
        return self.do_request('downloads', expected_code=400, request_type='PUT')

    @trial_timeout(10)
    def test_start_download_bad_params(self):
        """
        Testing whether an error is returned when we start a torrent download and pass wrong data
        """
        self.should_check_equality = False
        post_data = {'anon_hops': 1, 'safe_seeding': 0, 'uri': 'abcd'}
        return self.do_request('downloads', expected_code=400, request_type='PUT', post_data=post_data)

    @trial_timeout(10)
    def test_start_download_bad_uri(self):
        """
        Testing whether an error is returned when we start a download from a bad URI
        """
        post_data = {'uri': 'abcd', 'destination': 'a/b/c', 'selected_files[]': '1'}
        return self.do_request('downloads', expected_code=500, request_type='PUT', post_data=post_data,
                               expected_json={'error': 'invalid uri'})

    @trial_timeout(10)
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

    @trial_timeout(10)
    def test_start_download_from_file_unicode(self):
        """
        Testing whether we can start a download from a file with a unicode name
        """

        def verify_download(response):
            self.assertTrue(json.loads(response)['started'])
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)
            dl = self.session.get_downloads()[0]
            dl.tracker_status[u"\u266b"] = [0, 'Not contacted yet']
            tdef = dl.get_def()
            tdef.input['name'] = u'video\u266b'
            return self.do_request('downloads?get_peers=1&get_pieces=1',
                                   expected_code=200)

        ufile = os.path.join(TESTS_DATA_DIR, u'video\u266b.avi.torrent')
        udest = os.path.join(self.session_base_dir, u'video\u266b')

        post_data = (u'uri=file:%s&destination=%s' % (ufile, udest)).encode('utf-8')
        self.should_check_equality = False
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               raw_data=True).addCallback(verify_download)

    def create_mock_status(self):
        status = MockObject()
        status.state = 3
        status.upload_rate = 123
        status.download_rate = 43
        status.upload_payload_rate = 123
        status.download_payload_rate = 43
        status.total_upload = 100
        status.total_download = 200
        status.all_time_upload = 100
        status.all_time_download = 200
        status.list_peers = 10
        status.list_seeds = 5
        status.progress = 0.75
        status.error = False
        status.paused = False
        status.state = 3
        status.num_pieces = 0
        status.pieces = []
        return status

    @trial_timeout(10)
    def test_get_peers_illegal_fields_ascii(self):
        """
        Testing whether illegal fields are stripped from the Libtorrent download info response.
        """

        def verify_download_list(response):
            response_dict = json.loads(response)
            self.assertIn("downloads", response_dict)
            self.assertEqual(1, len(response_dict["downloads"]))
            self.assertIn("peers", response_dict["downloads"][0])
            self.assertEqual(1, len(response_dict["downloads"][0]["peers"]))
            self.assertNotIn('have', response_dict["downloads"][0]["peers"][0])
            self.assertEqual('uTorrent 1.6.1', response_dict["downloads"][0]["peers"][0]['extended_version'])

        def verify_download(response):
            self.assertTrue(json.loads(response)['started'])
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)
            dl = self.session.get_downloads()[0]
            ds = DownloadState(dl, self.create_mock_status(), None)
            ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': 'uTorrent 1.6.1'}]
            dl.get_state = lambda: ds
            self.should_check_equality = False
            return self.do_request('downloads?get_peers=1&get_pieces=1',
                                   expected_code=200).addCallback(verify_download_list)

        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '42bb0a78d8a10bef4a5aee3a7d9f1edf9941cee4'}
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json).addCallback(verify_download)

    @trial_timeout(10)
    def test_get_peers_illegal_fields_unicode(self):
        """
        Testing whether illegal fields are stripped from the Libtorrent download info response.
        """

        def verify_download_list(response):
            response_dict = json.loads(response)
            self.assertIn("downloads", response_dict)
            self.assertEqual(1, len(response_dict["downloads"]))
            self.assertIn("peers", response_dict["downloads"][0])
            self.assertEqual(1, len(response_dict["downloads"][0]["peers"]))
            self.assertNotIn('have', response_dict["downloads"][0]["peers"][0])
            self.assertEqual(u'\xb5Torrent 1.6.1', response_dict["downloads"][0]["peers"][0]['extended_version'])

        def verify_download(response):
            self.assertTrue(json.loads(response)['started'])
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)
            dl = self.session.get_downloads()[0]
            ds = DownloadState(dl, self.create_mock_status(), None)
            ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': '\xb5Torrent 1.6.1'}]
            dl.get_state = lambda: ds
            self.should_check_equality = False
            return self.do_request('downloads?get_peers=1&get_pieces=1',
                                   expected_code=200).addCallback(verify_download_list)

        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '42bb0a78d8a10bef4a5aee3a7d9f1edf9941cee4'}
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json).addCallback(verify_download)

    @trial_timeout(10)
    def test_get_peers_illegal_fields_unknown(self):
        """
        Testing whether illegal fields are stripped from the Libtorrent download info response.
        """

        def verify_download_list(response):
            response_dict = json.loads(response)
            self.assertIn("downloads", response_dict)
            self.assertEqual(1, len(response_dict["downloads"]))
            self.assertIn("peers", response_dict["downloads"][0])
            self.assertEqual(1, len(response_dict["downloads"][0]["peers"]))
            self.assertNotIn('have', response_dict["downloads"][0]["peers"][0])
            self.assertEqual(u'', response_dict["downloads"][0]["peers"][0]['extended_version'])

        def verify_download(response):
            self.assertTrue(json.loads(response)['started'])
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)
            dl = self.session.get_downloads()[0]
            ds = DownloadState(dl, self.create_mock_status(), None)
            ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': None}]
            dl.get_state = lambda: ds
            self.should_check_equality = False
            return self.do_request('downloads?get_peers=1&get_pieces=1',
                                   expected_code=200).addCallback(verify_download_list)

        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '42bb0a78d8a10bef4a5aee3a7d9f1edf9941cee4'}
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json).addCallback(verify_download)

    @trial_timeout(10)
    def test_start_download_from_magnet(self):
        """
        Testing whether we can start a download from a magnet
        """

        def verify_download(_):
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)
            self.assertEqual(self.session.get_downloads()[0].get_def().get_name(), 'Unknown name')

        post_data = {'uri': 'magnet:?xt=urn:btih:%s' % (hexlify(UBUNTU_1504_INFOHASH))}
        expected_json = {'started': True, 'infohash': 'fc8a15a2faf2734dbb1dc5f7afdc5c9beaeb1f59'}
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json).addCallback(verify_download)

    @trial_timeout(10)
    def test_start_download_from_bad_url(self):
        """
        Testing whether starting a download from a unexisting URL gives an error
        """
        post_data = {'uri': 'http://localhost:%d/test.torrent' % get_random_port()}
        self.should_check_equality = False
        return self.do_request('downloads', expected_code=500, request_type='PUT', post_data=post_data)

    @trial_timeout(10)
    def test_remove_download_no_remove_data_param(self):
        """
        Testing whether the API returns error 400 if the remove_data parameter is not passed
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', expected_code=400, request_type='DELETE')

    @trial_timeout(10)
    def test_remove_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is removed
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', post_data={"remove_data": True},
                               expected_code=404, request_type='DELETE')

    @trial_timeout(10)
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
                                           expected_code=200, request_type='DELETE',
                                           expected_json={"removed": True,
                                                          "infohash": "8bb88a02da691636a7ed929b87d467f24700e490"})
        return request_deferred.addCallback(verify_removed)

    @trial_timeout(10)
    def test_stop_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is stopped
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', expected_code=404, post_data={"state": "stop"}, request_type='PATCH')

    @trial_timeout(10)
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
                                           expected_code=200, request_type='PATCH',
                                           expected_json={"modified": True,
                                                          "infohash": "8bb88a02da691636a7ed929b87d467f24700e490"})
        return request_deferred.addCallback(verify_removed)

    @trial_timeout(10)
    def test_select_download_file_range(self):
        """
        Testing whether an error is returned when we toggle a file for inclusion out of range
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        self.should_check_equality = False
        return self.do_request('downloads/%s' % infohash, expected_code=400, post_data={"selected_files[]": 1234},
                               request_type='PATCH')

    @trial_timeout(10)
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

        return self.do_request('downloads/%s' % infohash, post_data={"selected_files[]": 0},
                               expected_code=200, request_type='PATCH',
                               expected_json={"modified": True,
                                              "infohash": "8bb88a02da691636a7ed929b87d467f24700e490"}) \
            .addCallback(verify_method_called)

    @trial_timeout(10)
    def test_resume_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is resumed
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd', expected_code=404, post_data={"state": "resume"}, request_type='PATCH')

    @trial_timeout(10)
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
                                           expected_code=200, request_type='PATCH',
                                           expected_json={"modified": True,
                                                          "infohash": "8bb88a02da691636a7ed929b87d467f24700e490"})
        return request_deferred.addCallback(verify_resumed)

    @trial_timeout(10)
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
                                           expected_code=200, request_type='PATCH',
                                           expected_json={"modified": True,
                                                          "infohash": "8bb88a02da691636a7ed929b87d467f24700e490"})
        return request_deferred.addCallback(verify_rechecked)

    @trial_timeout(10)
    def test_change_hops_error(self):
        """
        Testing whether the API returns 400 if we supply both anon_hops and another parameter
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        self.should_check_equality = False
        return self.do_request('downloads/%s' % infohash, post_data={"state": "resume", 'anon_hops': 1},
                               expected_code=400, request_type='PATCH')

    @trial_timeout(10)
    def test_download_unknown_state(self):
        """
        Testing whether the API returns error 400 if an unknown state is passed when modifying a download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())

        self.should_check_equality = False
        return self.do_request('downloads/%s' % video_tdef.get_infohash().encode('hex'), expected_code=400,
                               post_data={"state": "abc"}, request_type='PATCH')

    @trial_timeout(10)
    def test_export_unknown_download(self):
        """
        Testing whether the API returns error 404 if a non-existent download is exported
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd/torrent', expected_code=404, request_type='GET')

    @trial_timeout(10)
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

    @trial_timeout(10)
    def test_get_files_unknown_download(self):
        """
        Testing whether the API returns error 404 if the files of a non-existent download are requested
        """
        self.should_check_equality = False
        return self.do_request('downloads/abcd/files', expected_code=404, request_type='GET')

    @trial_timeout(10)
    def test_get_download_files(self):
        """
        Testing whether the API returns file information of a specific download when requested
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())

        def verify_files_data(response):
            json_response = json.loads(response)
            self.assertIn('files', json_response)
            self.assertTrue(json_response['files'])

        self.should_check_equality = False
        return self.do_request('downloads/%s/files' % video_tdef.get_infohash().encode('hex'),
                               expected_code=200, request_type='GET').addCallback(verify_files_data)


class TestDownloadsDispersyEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestDownloadsDispersyEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_tunnel_community_enabled(True)

    @trial_timeout(10)
    def test_change_hops(self):
        """
        Testing whether the API returns 200 if we change the amount of hops of a download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        return download.get_handle().addCallback(
            lambda _: self.do_request('downloads/%s' % infohash, post_data={'anon_hops': 1},
                                      expected_code=200, request_type='PATCH',
                                      expected_json={'modified': True,
                                                     "infohash": "8bb88a02da691636a7ed929b87d467f24700e490"})
        )

    @trial_timeout(10)
    def test_change_hops_fail(self):
        def on_remove_download(d, remove_content=False, remove_state=True, hidden=False):
            return fail(RuntimeError())

        self.session.remove_download = on_remove_download

        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadStartupConfig())
        infohash = video_tdef.get_infohash().encode('hex')

        return self.do_request('downloads/%s' % infohash, post_data={"remove_data": True}, expected_code=500,
                               expected_json={u'error': {u'message': u'', u'code': u'RuntimeError', u'handled': True}},
                               request_type='DELETE')


class TestMetadataDownloadEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestMetadataDownloadEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_chant_enabled(True)

    @trial_timeout(10)
    def test_add_metadata_download(self):
        """
        Test adding a channel metadata download to the Tribler core
        """

        def verify_download(_):
            self.assertGreaterEqual(len(self.session.get_downloads()), 1)

        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DIR, 'Core/data/sample_channel/channel.mdblob')}
        expected_json = {'started': True, 'infohash': '02c146a1a3ffd96856a0319d1832cf70989e5a47'}
        return self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json).addCallback(verify_download)

    @trial_timeout(10)
    def test_add_metadata_download_invalid_sig(self):
        """
        Test whether adding metadata with an invalid signature results in an error
        """
        file_path = os.path.join(self.session_base_dir, "invalid.mdblob")
        with open(file_path, "wb") as out_file:
            with db_session:
                my_channel = self.session.lm.mds.ChannelMetadata.create_channel('test', 'test')
                my_channel.signature = "lalala"
            out_file.write(my_channel.serialized())

        post_data = {'uri': 'file:%s' % file_path, 'metadata_download': '1'}
        expected_json = {'error': "Metadata has invalid signature"}
        self.should_check_equality = True
        return self.do_request('downloads', expected_code=400, request_type='PUT', post_data=post_data,
                               expected_json=expected_json)

    @trial_timeout(10)
    def test_add_invalid_metadata_download(self):
        """
        Test adding an invalid metadata download to the Tribler core
        """
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'notexisting.mdblob'), 'metadata_download': '1'}
        self.should_check_equality = False
        return self.do_request('downloads', expected_code=400, request_type='PUT', post_data=post_data)
