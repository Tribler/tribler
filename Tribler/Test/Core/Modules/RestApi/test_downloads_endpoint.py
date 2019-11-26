import os
from asyncio import ensure_future
from binascii import unhexlify
from urllib.request import pathname2url

from pony.orm import db_session

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Utilities.utilities import fail, succeed
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TESTS_DATA_DIR, TESTS_DIR, UBUNTU_1504_INFOHASH
from Tribler.Test.tools import timeout


def get_hex_infohash(tdef):
    return hexlify(tdef.get_infohash())


class TestDownloadsEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestDownloadsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_chant_enabled(True)

    @timeout(10)
    async def test_get_downloads_no_downloads(self):
        """
        Testing whether the API returns an empty list when downloads are fetched but no downloads are active
        """
        await self.do_request('downloads?get_peers=1&get_pieces=1',
                               expected_code=200, expected_json={"downloads": []})

    @timeout(20)
    async def test_get_downloads(self):
        """
        Testing whether the API returns the right download when a download is added
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        await self.session.start_download_from_uri("file:" + pathname2url(os.path.join(TESTS_DATA_DIR,
                                                                                       "bak_single.torrent")))

        downloads = await self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200)
        self.assertEqual(len(downloads['downloads']), 2)

    @timeout(20)
    async def test_get_downloads_with_files(self):
        """
        Testing whether the API returns the right right filenames fpr each download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        await self.session.start_download_from_uri("file:" + pathname2url(os.path.join(TESTS_DATA_DIR,
                                                                                       "bak_single.torrent")))
        downloads = await self.do_request('downloads?get_peers=1&get_pieces=1&&get_files=1', expected_code=200)
        self.assertCountEqual([downloads['downloads'][0][u'files'],
                               downloads['downloads'][1][u'files']],
                        [[{u'included': True, u'index': 0, u'size': 1583233,
                           u'name': u'Tribler_4.1.7_src.zip', u'progress': 0.0}],
                         [{u'included': True, u'index': 0, u'size': 1942100,
                           u'name': u'video.avi', u'progress': 0.0}]])

    @timeout(10)
    async def test_start_download_no_uri(self):
        """
        Testing whether an error is returned when we start a torrent download and do not pass any URI
        """
        await self.do_request('downloads', expected_code=400, request_type='PUT')

    @timeout(10)
    async def test_start_download_bad_params(self):
        """
        Testing whether an error is returned when we start a torrent download and pass wrong data
        """
        post_data = {'anon_hops': 1, 'safe_seeding': 0, 'uri': 'abcd'}
        await self.do_request('downloads', expected_code=400, request_type='PUT', post_data=post_data)

    @timeout(10)
    async def test_start_download_bad_uri(self):
        """
        Testing whether an error is returned when we start a download from a bad URI
        """
        post_data = {'uri': 'abcd', 'destination': 'a/b/c', 'selected_files[]': '1'}
        await self.do_request('downloads', expected_code=500, request_type='PUT', post_data=post_data,
                               expected_json={'error': 'invalid uri'})

    @timeout(10)
    async def test_start_download_from_file(self):
        """
        Testing whether we can start a download from a file
        """
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '9d5b2dbc52807325bfc28d688f2bb03f8d1e7667'}
        await self.do_request('downloads', expected_code=200, request_type='PUT',
                              post_data=post_data, expected_json=expected_json)
        self.assertGreaterEqual(len(self.session.get_downloads()), 1)

    @timeout(10)
    async def test_start_download_from_file_unicode(self):
        """
        Testing whether we can start a download from a file with a unicode name
        """
        ufile = os.path.join(TESTS_DATA_DIR, u'video\u266b.avi.torrent')
        udest = os.path.join(self.session_base_dir, u'video\u266b')

        post_data = {'uri': 'file:' + ufile,
                     'destination': udest}
        response_dict = await self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data)
        self.assertTrue(response_dict['started'])
        self.assertGreaterEqual(len(self.session.get_downloads()), 1)
        dl = self.session.get_downloads()[0]
        dl.tracker_status[u"\u266b"] = [0, 'Not contacted yet']
        tdef = dl.get_def()
        tdef.torrent_parameters['name'] = u'video\u266b'
        await self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200)

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

    @timeout(10)
    async def test_get_peers_illegal_fields_ascii(self):
        """
        Testing whether illegal fields are stripped from the Libtorrent download info response.
        """
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '9d5b2dbc52807325bfc28d688f2bb03f8d1e7667'}
        response_dict = await self.do_request('downloads', expected_code=200, request_type='PUT',
                                              post_data=post_data, expected_json=expected_json)
        self.assertTrue(response_dict['started'])
        self.assertGreaterEqual(len(self.session.get_downloads()), 1)

        dl = self.session.get_downloads()[0]
        ds = DownloadState(dl, self.create_mock_status(), None)
        ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': 'uTorrent 1.6.1'}]
        dl.get_state = lambda: ds

        response_dict = await self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200)
        self.assertIn("downloads", response_dict)
        self.assertEqual(1, len(response_dict["downloads"]))
        self.assertIn("peers", response_dict["downloads"][0])
        self.assertEqual(1, len(response_dict["downloads"][0]["peers"]))
        self.assertNotIn('have', response_dict["downloads"][0]["peers"][0])
        self.assertEqual('uTorrent 1.6.1', response_dict["downloads"][0]["peers"][0]['extended_version'])

    @timeout(10)
    async def test_get_peers_illegal_fields_unicode(self):
        """
        Testing whether illegal fields are stripped from the Libtorrent download info response.
        """
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '9d5b2dbc52807325bfc28d688f2bb03f8d1e7667'}
        response_dict = await self.do_request('downloads', expected_code=200, request_type='PUT',
                                              post_data=post_data, expected_json=expected_json)
        self.assertTrue(response_dict['started'])
        self.assertGreaterEqual(len(self.session.get_downloads()), 1)

        dl = self.session.get_downloads()[0]
        ds = DownloadState(dl, self.create_mock_status(), None)
        ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': '\xb5Torrent 1.6.1'}]
        dl.get_state = lambda: ds

        response_dict = await self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200)
        self.assertIn("downloads", response_dict)
        self.assertEqual(1, len(response_dict["downloads"]))
        self.assertIn("peers", response_dict["downloads"][0])
        self.assertEqual(1, len(response_dict["downloads"][0]["peers"]))
        self.assertNotIn('have', response_dict["downloads"][0]["peers"][0])
        self.assertEqual(u'\xb5Torrent 1.6.1', response_dict["downloads"][0]["peers"][0]['extended_version'])

    @timeout(10)
    async def test_get_peers_illegal_fields_unknown(self):
        """
        Testing whether illegal fields are stripped from the Libtorrent download info response.
        """
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'video.avi.torrent')}
        expected_json = {'started': True, 'infohash': '9d5b2dbc52807325bfc28d688f2bb03f8d1e7667'}
        response_dict = await self.do_request('downloads', expected_code=200, request_type='PUT',
                                              post_data=post_data, expected_json=expected_json)

        self.assertTrue(response_dict['started'])
        self.assertGreaterEqual(len(self.session.get_downloads()), 1)

        dl = self.session.get_downloads()[0]
        ds = DownloadState(dl, self.create_mock_status(), None)
        ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': None}]
        dl.get_state = lambda: ds

        response_dict = await self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200)
        self.assertIn("downloads", response_dict)
        self.assertEqual(1, len(response_dict["downloads"]))
        self.assertIn("peers", response_dict["downloads"][0])
        self.assertEqual(1, len(response_dict["downloads"][0]["peers"]))
        self.assertNotIn('have', response_dict["downloads"][0]["peers"][0])
        self.assertEqual(u'', response_dict["downloads"][0]["peers"][0]['extended_version'])

    @timeout(10)
    async def test_start_download_from_magnet(self):
        """
        Testing whether we can start a download from a magnet
        """
        post_data = {'uri': 'magnet:?xt=urn:btih:%s' % hexlify(UBUNTU_1504_INFOHASH)}
        expected_json = {'started': True, 'infohash': 'fc8a15a2faf2734dbb1dc5f7afdc5c9beaeb1f59'}
        await self.do_request('downloads', expected_code=200, request_type='PUT',
                              post_data=post_data, expected_json=expected_json)
        self.assertGreaterEqual(len(self.session.get_downloads()), 1)
        self.assertEqual(self.session.get_downloads()[0].get_def().get_name(), 'Unknown name')

    @timeout(10)
    async def test_start_download_from_bad_url(self):
        """
        Testing whether starting a download from a unexisting URL gives an error
        """
        post_data = {'uri': 'http://localhost:%d/test.torrent' % self.get_port()}
        await self.do_request('downloads', expected_code=500, request_type='PUT', post_data=post_data)

    @timeout(10)
    async def test_remove_download_no_remove_data_param(self):
        """
        Testing whether the API returns error 400 if the remove_data parameter is not passed
        """
        await self.do_request('downloads/abcd', expected_code=400, request_type='DELETE')

    @timeout(10)
    async def test_remove_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is removed
        """
        await self.do_request('downloads/abcd', post_data={"remove_data": True},
                               expected_code=404, request_type='DELETE')

    @timeout(10)
    async def test_remove_download(self):
        """
        Testing whether the API returns 200 if a download is being removed
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)
        await self.do_request('downloads/%s' % infohash, post_data={"remove_data": True},
                                           expected_code=200, request_type='DELETE',
                                           expected_json={u"removed": True,
                                                          u"infohash": u"c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5"})
        self.assertEqual(len(self.session.get_downloads()), 0)

    @timeout(10)
    async def test_stop_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is stopped
        """
        await self.do_request('downloads/abcd', expected_code=404, post_data={"state": "stop"}, request_type='PATCH')

    @timeout(10)
    async def test_stop_download(self):
        """
        Testing whether the API returns 200 if a download is being stopped
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)
        original_stop = download.stop

        async def mocked_stop():
            download.should_stop = True
            download.stop = original_stop
        download.stop = mocked_stop

        await self.do_request('downloads/%s' % infohash, post_data={"state": "stop"},
                              expected_code=200, request_type='PATCH',
                              expected_json={u"modified": True,
                                             u"infohash": u"c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5"})
        self.assertEqual(len(self.session.get_downloads()), 1)
        download = self.session.get_downloads()[0]
        self.assertTrue(download.should_stop)

    @timeout(10)
    async def test_select_download_file_range(self):
        """
        Testing whether an error is returned when we toggle a file for inclusion out of range
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)

        await self.do_request('downloads/%s' % infohash, expected_code=400, post_data={"selected_files": 1234},
                               request_type='PATCH')

    @timeout(10)
    async def test_select_download_file(self):
        """
        Testing whether files can be correctly toggled in a download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)

        def mocked_set_selected_files(*_):
            mocked_set_selected_files.called = True
        mocked_set_selected_files.called = False
        download.set_selected_files = mocked_set_selected_files

        await self.do_request('downloads/%s' % infohash, post_data={"selected_files": 0},
                               expected_code=200, request_type='PATCH',
                               expected_json={u"modified": True,
                                              u"infohash": u"c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5"})
        self.assertTrue(mocked_set_selected_files.called)

    @timeout(10)
    async def test_resume_download_wrong_infohash(self):
        """
        Testing whether the API returns error 404 if a non-existent download is resumed
        """
        await self.do_request('downloads/abcd', expected_code=404, post_data={"state": "resume"}, request_type='PATCH')

    @timeout(10)
    async def test_resume_download(self):
        """
        Testing whether the API returns 200 if a download is being resumed
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)

        async def mocked_restart():
            download.should_restart = True
        download.restart = mocked_restart

        await self.do_request('downloads/%s' % infohash, post_data={"state": "resume"},
                              expected_code=200, request_type='PATCH',
                              expected_json={"modified": True,
                                             "infohash": "c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5"})
        self.assertEqual(len(self.session.get_downloads()), 1)
        download = self.session.get_downloads()[0]
        self.assertTrue(download.should_restart)

    @timeout(10)
    async def test_recheck_download(self):
        """
        Testing whether the API returns 200 if a download is being rechecked
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)

        def mocked_recheck():
            mocked_recheck.called = True
        mocked_recheck.called = False
        download.force_recheck = mocked_recheck

        await self.do_request('downloads/%s' % infohash, post_data={"state": "recheck"},
                                           expected_code=200, request_type='PATCH',
                                           expected_json={u"modified": True,
                                                          u"infohash": u"c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5"})
        self.assertEqual(len(self.session.get_downloads()), 1)
        self.assertTrue(mocked_recheck.called)

    @timeout(10)
    async def test_change_hops_error(self):
        """
        Testing whether the API returns 400 if we supply both anon_hops and another parameter
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)

        await self.do_request('downloads/%s' % infohash, post_data={"state": "resume", 'anon_hops': 1},
                               expected_code=400, request_type='PATCH')

    @timeout(10)
    async def test_download_unknown_state(self):
        """
        Testing whether the API returns error 400 if an unknown state is passed when modifying a download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())

        await self.do_request('downloads/%s' % get_hex_infohash(video_tdef), expected_code=400,
                               post_data={"state": "abc"}, request_type='PATCH')

    @timeout(10)
    async def test_move_to_non_existing_dir(self):
        """
        Testing whether moving the torrent storage to a non-existing directory works as expected.
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())

        dest_dir = os.path.join(self.temporary_directory(), "non-existing")
        self.assertFalse(os.path.exists(dest_dir))
        data = {"state": "move_storage", "dest_dir": dest_dir}

        response_dict = await self.do_request('downloads/%s' % get_hex_infohash(video_tdef),
                                              expected_code=200, post_data=data, request_type='PATCH')
        self.assertTrue("error" in response_dict)
        self.assertEqual("Target directory (%s) does not exist" % dest_dir, response_dict["error"])

    @timeout(10)
    async def test_move_to_existing_dir(self):
        """
        Testing whether moving the torrent storage to an existing directory works as expected.
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())

        dest_dir = os.path.join(self.temporary_directory(), "existing")
        os.mkdir(dest_dir)
        self.assertTrue(os.path.exists(dest_dir))
        data = {"state": "move_storage", "dest_dir": dest_dir}

        response_dict = await self.do_request('downloads/%s' % get_hex_infohash(video_tdef),
                                              expected_code=200, post_data=data, request_type='PATCH')
        self.assertTrue(response_dict.get("modified", False))
        self.assertEqual(hexlify(video_tdef.infohash), response_dict["infohash"])

    @timeout(10)
    async def test_export_unknown_download(self):
        """
        Testing whether the API returns error 404 if a non-existent download is exported
        """
        await self.do_request('downloads/abcd/torrent', expected_code=404, request_type='GET')

    @timeout(10)
    async def test_export_download(self):
        """
        Testing whether the API returns the contents of the torrent file if a download is exported
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadConfig())

        await download.get_handle()
        result = await self.do_request('downloads/%s/torrent' % get_hex_infohash(video_tdef),
                                       expected_code=200, request_type='GET', json_response=False)
        self.assertTrue(result)

    @timeout(10)
    async def test_get_files_unknown_download(self):
        """
        Testing whether the API returns error 404 if the files of a non-existent download are requested
        """
        await self.do_request('downloads/abcd/files', expected_code=404, request_type='GET')

    @timeout(10)
    async def test_get_download_files(self):
        """
        Testing whether the API returns file information of a specific download when requested
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        response_dict = await self.do_request('downloads/%s/files' % get_hex_infohash(video_tdef),
                                              expected_code=200, request_type='GET')
        self.assertIn('files', response_dict)
        self.assertTrue(response_dict['files'])


class TestDownloadsWithTunnelsEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestDownloadsWithTunnelsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_tunnel_community_enabled(True)

    @timeout(10)
    async def test_change_hops(self):
        """
        Testing whether the API returns 200 if we change the amount of hops of a download
        """
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        download = self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)
        await download.get_handle()
        await self.do_request('downloads/%s' % infohash, post_data={'anon_hops': 1},
                              expected_code=200, request_type='PATCH',
                              expected_json={'modified': True,
                                             "infohash": "c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5"})

    @timeout(10)
    async def test_change_hops_fail(self):
        def on_remove_download(d, remove_content=False, remove_state=True, hidden=False):
            return fail(RuntimeError())
        self.session.remove_download = on_remove_download

        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        infohash = get_hex_infohash(video_tdef)
        await self.do_request('downloads/%s' % infohash, post_data={"remove_data": True}, expected_code=500,
                               expected_json={u'error': {u'message': u'', u'code': u'RuntimeError', u'handled': True}},
                               request_type='DELETE')


class TestMetadataDownloadEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestMetadataDownloadEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_chant_enabled(True)

    @timeout(10)
    async def test_add_metadata_download(self):
        """
        Test adding a channel metadata download to the Tribler core
        """
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DIR, 'Core/data/sample_channel/channel.mdblob')}
        expected_json = {'started': True, 'infohash': 'ea95d47988b4dcb07667194c998d2c5b473132e5'}
        await self.do_request('downloads', expected_code=200, request_type='PUT',
                              post_data=post_data, expected_json=expected_json)
        with db_session:
            self.assertEqual(self.session.lm.mds.ChannelMetadata.select().count(), 1)
            self.assertTrue(self.session.lm.mds.ChannelMetadata.get().subscribed)

    @timeout(10)
    async def test_add_metadata_download_already_added(self):
        """
        Test adding a channel metadata download to the Tribler core
        """
        with db_session:
            self.session.lm.mds.process_mdblob_file(os.path.join(TESTS_DIR, 'Core/data/sample_channel/channel.mdblob'))
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DIR, 'Core/data/sample_channel/channel.mdblob')}
        expected_json = {u'error': u'Could not import Tribler metadata file'}
        await self.do_request('downloads', expected_code=200, request_type='PUT', post_data=post_data,
                               expected_json=expected_json)

    @timeout(10)
    async def test_add_metadata_download_invalid_sig(self):
        """
        Test whether adding metadata with an invalid signature results in an error
        """
        file_path = os.path.join(self.session_base_dir, u"invalid.mdblob")
        with open(file_path, "wb") as out_file:
            with db_session:
                my_channel = self.session.lm.mds.ChannelMetadata.create_channel('test', 'test')

            hexed = hexlify(my_channel.serialized()).encode('utf-8')[:-5] + b"aaaaa"
            out_file.write(unhexlify(hexed))

        post_data = {u'uri': u'file:%s' % file_path, u'metadata_download': u'1'}
        expected_json = {'error': "Metadata has invalid signature"}
        await self.do_request('downloads', expected_code=400, request_type='PUT', post_data=post_data,
                               expected_json=expected_json)

    @timeout(10)
    async def test_add_invalid_metadata_download(self):
        """
        Test adding an invalid metadata download to the Tribler core
        """
        post_data = {'uri': 'file:%s' % os.path.join(TESTS_DATA_DIR, 'notexisting.mdblob'), 'metadata_download': '1'}
        await self.do_request('downloads', expected_code=400, request_type='PUT', post_data=post_data)

    @timeout(20)
    async def test_get_downloads_with_channels(self):
        """
        Testing whether the API returns the right download when a download is added
        """
        test_channel_name = 'test_channel'
        video_tdef, _ = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.session.start_download_from_tdef(video_tdef, DownloadConfig())
        await self.session.start_download_from_uri("file:" + pathname2url(
            os.path.join(TESTS_DATA_DIR, "bak_single.torrent")))

        with db_session:
            channel = self.session.lm.mds.ChannelMetadata.create_channel(test_channel_name, 'bla')
            def fake_get_metainfo(infohash, timeout=30):
                return succeed({b'info': {b'name': channel.dirname.encode('utf-8')}})
            self.session.lm.ltmgr.get_metainfo = fake_get_metainfo
            ensure_future(self.session.lm.gigachannel_manager.download_channel(channel))

        downloads = await self.do_request('downloads?get_peers=1&get_pieces=1', expected_code=200)
        self.assertEqual(len(downloads['downloads']), 3)
        self.assertEqual(test_channel_name,
                         [d for d in downloads["downloads"] if d["channel_download"]][0]["name"])
