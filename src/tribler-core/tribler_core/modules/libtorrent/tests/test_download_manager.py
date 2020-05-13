import shutil
from asyncio import Future, ensure_future, gather, get_event_loop, sleep
from unittest.mock import Mock

from libtorrent import bencode

from tribler_common.simpledefs import DLSTATUS_SEEDING, DLSTATUS_STOPPED_ON_ERROR

from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler_core.notifier import Notifier
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from tribler_core.tests.tools.test_as_server import AbstractServer
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.path_util import mkdtemp
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import succeed


def create_fake_download_and_state():
    """
    Create a fake download and state which can be passed to the global download callback.
    """
    tdef = TorrentDef()
    tdef.get_infohash = lambda: b'aaaa'
    fake_peer = {'extended_version': 'Tribler', 'id': 'a' * 20, 'dtotal': 10 * 1024 * 1024}
    fake_download = MockObject()
    fake_download.get_def = lambda: tdef
    fake_download.get_def().get_name_as_unicode = lambda: "test.iso"
    fake_download.get_peerlist = lambda: [fake_peer]
    fake_download.hidden = False
    fake_download.checkpoint = lambda: succeed(None)
    fake_download.stop = lambda: succeed(None)
    fake_download.shutdown = lambda: succeed(None)
    dl_state = MockObject()
    dl_state.get_infohash = lambda: b'aaaa'
    dl_state.get_status = lambda: DLSTATUS_SEEDING
    dl_state.get_download = lambda: fake_download
    fake_config = MockObject()
    fake_config.get_hops = lambda: 0
    fake_config.get_safe_seeding = lambda: True
    fake_download.config = fake_config

    return fake_download, dl_state


class TestDownloadManager(AbstractServer):

    LIBTORRENT_FILES_DIR = TESTS_DATA_DIR / "libtorrent"

    async def setUp(self):
        await super(TestDownloadManager, self).setUp()

        self.tribler_session = MockObject()
        self.tribler_session.notifier = Notifier()
        self.tribler_session.state_dir = self.session_base_dir
        self.tribler_session.trustchain_keypair = MockObject()
        self.tribler_session.trustchain_keypair.key_to_hash = lambda: b'a' * 20
        self.tribler_session.notify_shutdown_state = lambda _: None

        self.dlmgr = DownloadManager(self.tribler_session)
        self.dlmgr.metadata_tmpdir = mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        self.tribler_session.dlmgr = self.dlmgr
        self.tribler_session.tunnel_community = None
        self.tribler_session.credit_mining_manager = None

        self.tribler_session.config = MockObject()
        self.tribler_session.config.get_libtorrent_utp = lambda: True
        self.tribler_session.config.get_libtorrent_proxy_settings = lambda: (0, None, None)
        self.tribler_session.config.get_anon_proxy_settings = lambda: (2, ('127.0.0.1', [1338]), None)
        self.tribler_session.config.get_libtorrent_port = lambda: 1337
        self.tribler_session.config.get_anon_listen_port = lambda: 1338
        self.tribler_session.config.get_state_dir = lambda: self.session_base_dir
        self.tribler_session.config.set_listen_port_runtime = lambda: None
        self.tribler_session.config.get_libtorrent_max_upload_rate = lambda: 100
        self.tribler_session.config.get_libtorrent_max_download_rate = lambda: 120
        self.tribler_session.config.get_libtorrent_dht_enabled = lambda: False
        self.tribler_session.config.set_libtorrent_port_runtime = lambda _: None
        self.tribler_session.config.get_libtorrent_max_conn_download = lambda: 0
        self.tribler_session.config.get_default_number_hops = lambda: 1

    async def tearDown(self):
        await self.dlmgr.shutdown(timeout=0)
        self.assertTrue((self.session_base_dir / 'lt.state').exists())
        await super(TestDownloadManager, self).tearDown()

    def test_get_session_zero_hops(self):
        self.dlmgr.initialize()
        ltsession = self.dlmgr.get_session(0)
        self.assertTrue(ltsession)

    def test_get_session_one_hop(self):
        self.dlmgr.initialize()
        ltsession = self.dlmgr.get_session(1)
        self.assertTrue(ltsession)

    def test_get_session_zero_hops_corrupt_lt_state(self):
        with open(self.session_base_dir / 'lt.state', "w") as file:
            file.write("Lorem ipsum")

        self.dlmgr.initialize()
        ltsession = self.dlmgr.get_session(0)
        self.assertTrue(ltsession)

    def test_get_session_zero_hops_working_lt_state(self):
        shutil.copy(self.LIBTORRENT_FILES_DIR / 'lt.state',
                    self.session_base_dir / 'lt.state')
        self.dlmgr.initialize()
        ltsession = self.dlmgr.get_session(0)
        self.assertTrue(ltsession)

    @timeout(20)
    async def test_get_metainfo_valid_metadata(self):
        """
        Testing the get_metainfo method when the handle has valid metadata immediately
        """
        infohash = b"a" * 20
        metainfo = {b'info': {b'pieces': [b'a']}, b'leechers': 0,
                    b'nodes': [], b'seeders': 0}

        download_impl = Mock()
        download_impl.tdef.get_metainfo = lambda: None
        download_impl.future_metainfo = succeed(metainfo)

        self.dlmgr.initialize()
        self.dlmgr.start_download = Mock(return_value=download_impl)
        self.dlmgr.tribler_session.config.get_default_number_hops = lambda: 1
        self.dlmgr.remove_download = Mock(return_value=succeed(None))

        self.assertEqual(await self.dlmgr.get_metainfo(infohash), metainfo)
        self.dlmgr.start_download.assert_called_once()
        self.dlmgr.remove_download.assert_called_once()

    @timeout(20)
    async def test_get_metainfo_add_fail(self):
        """
        Test whether we try to add a torrent again if the atp is rejected
        """
        infohash = b"a" * 20
        metainfo = {'pieces': ['a']}

        download_impl = Mock()
        download_impl.future_metainfo = succeed(metainfo)
        download_impl.tdef.get_metainfo = lambda: None

        self.dlmgr.initialize()
        self.dlmgr.start_download = Mock()
        self.dlmgr.start_download.side_effect = TypeError
        self.dlmgr.tribler_session.config.get_default_number_hops = lambda: 1
        self.dlmgr.remove = Mock(return_value=succeed(None))

        self.assertEqual(await self.dlmgr.get_metainfo(infohash), None)
        self.dlmgr.start_download.assert_called_once()
        self.dlmgr.remove.assert_not_called()

    @timeout(20)
    async def test_get_metainfo_duplicate_request(self):
        """
        Test whether the same request is returned when invoking get_metainfo twice with the same infohash
        """
        infohash = b"a" * 20
        metainfo = {'pieces': ['a']}

        download_impl = Mock()
        download_impl.tdef.get_metainfo = lambda: None
        download_impl.future_metainfo = Future()
        get_event_loop().call_later(0.1, download_impl.future_metainfo.set_result, metainfo)

        self.dlmgr.initialize()
        self.dlmgr.start_download = Mock(return_value=download_impl)
        self.dlmgr.tribler_session.config.get_default_number_hops = lambda: 1
        self.dlmgr.remove_download = Mock(return_value=succeed(None))

        results = await gather(self.dlmgr.get_metainfo(infohash), self.dlmgr.get_metainfo(infohash))
        self.assertEqual(results, [metainfo, metainfo])
        self.dlmgr.start_download.assert_called_once()
        self.dlmgr.remove_download.assert_called_once()

    @timeout(20)
    async def test_get_metainfo_cache(self):
        """
        Testing whether cached metainfo is returned, if available
        """
        self.dlmgr.initialize()
        self.dlmgr.metainfo_cache[b"a" * 20] = {'meta_info': 'test', 'time': 0}

        self.assertEqual(await self.dlmgr.get_metainfo(b"a" * 20), "test")

    @timeout(20)
    async def test_get_metainfo_with_already_added_torrent(self):
        """
        Testing metainfo fetching for a torrent which is already in session.
        """
        sample_torrent = TESTS_DATA_DIR / "bak_single.torrent"
        torrent_def = TorrentDef.load(sample_torrent)

        download_impl = Mock()
        download_impl.future_metainfo = succeed(bencode(torrent_def.get_metainfo()))
        download_impl.checkpoint = lambda: succeed(None)
        download_impl.stop = lambda: succeed(None)
        download_impl.shutdown = lambda: succeed(None)

        self.dlmgr.initialize()
        self.dlmgr.downloads[torrent_def.infohash] = download_impl

        self.assertTrue(await self.dlmgr.get_metainfo(torrent_def.infohash))

    @timeout(20)
    async def test_start_download_while_getting_metainfo(self):
        """
        Testing adding a torrent while a metainfo request is running.
        """
        infohash = b"a" * 20

        metainfo_session = Mock()
        metainfo_session.get_torrents = lambda: []

        metainfo_dl = Mock()
        metainfo_dl.config.get_credit_mining = lambda: False
        metainfo_dl.get_def = lambda: Mock(get_infohash=lambda: infohash)

        self.dlmgr.initialize()
        self.dlmgr.get_session = lambda *_: metainfo_session
        self.dlmgr.downloads[infohash] = metainfo_dl
        self.dlmgr.metainfo_requests[infohash] = [metainfo_dl, 1]
        self.dlmgr.remove_download = Mock(return_value=succeed(None))

        tdef = TorrentDefNoMetainfo(infohash, 'name', 'magnet:?xt=urn:btih:%s&' % hexlify(infohash))
        download = self.dlmgr.start_download(tdef=tdef, checkpoint_disabled=True)
        self.assertNotEqual(metainfo_dl, download)
        await sleep(.1)
        self.assertEqual(self.dlmgr.downloads[infohash], download)
        self.dlmgr.remove_download.assert_called_once_with(metainfo_dl, remove_content=True, remove_checkpoint=False)

    @timeout(20)
    async def test_start_download(self):
        """
        Testing the addition of a torrent to the libtorrent manager
        """
        infohash = b'a' * 20

        mock_handle = Mock()
        mock_handle.info_hash = lambda: hexlify(infohash)
        mock_handle.is_valid = lambda: True

        mock_error = MockObject()
        mock_error.value = lambda: None

        mock_alert = type('add_torrent_alert', (object,), dict(handle=mock_handle,
                                                               error=mock_error,
                                                               category=lambda _: None))()

        mock_ltsession = Mock()
        mock_ltsession.get_torrents = lambda: []
        mock_ltsession.async_add_torrent = lambda _: self.dlmgr.register_task('post_alert',
                                                                              self.dlmgr.process_alert,
                                                                              mock_alert, delay=0.1)

        self.dlmgr.get_session = lambda *_: mock_ltsession

        download = self.dlmgr.start_download(tdef=TorrentDefNoMetainfo(infohash, ''), checkpoint_disabled=True)
        handle = await download.get_handle()
        self.assertEqual(handle, mock_handle)
        self.dlmgr.downloads.clear()

    @timeout(20)
    async def test_start_download_existing_handle(self):
        """
        Testing the addition of a torrent to the libtorrent manager, if there is a pre-existing handle.
        """
        infohash = b'a' * 20

        mock_handle = Mock()
        mock_handle.info_hash = lambda: hexlify(infohash)
        mock_handle.is_valid = lambda: True

        mock_ltsession = Mock()
        mock_ltsession.get_torrents = lambda: [mock_handle]

        self.dlmgr.get_session = lambda *_: mock_ltsession

        download = self.dlmgr.start_download(tdef=TorrentDefNoMetainfo(infohash, 'name'), checkpoint_disabled=True)
        handle = await download.get_handle()
        self.assertEqual(handle, mock_handle)
        self.dlmgr.downloads.clear()

    @timeout(20)
    async def test_start_download_existing_download(self):
        """
        Testing the addition of a torrent to the libtorrent manager, if there is a pre-existing download.
        """
        infohash = b'a' * 20

        mock_download = Mock()
        mock_download.config.get_credit_mining = lambda: False
        mock_download.get_def = lambda: Mock(get_trackers_as_single_tuple=lambda: ())

        mock_ltsession = Mock()

        self.dlmgr.downloads[infohash] = mock_download
        self.dlmgr.get_session = lambda *_: mock_ltsession

        download = self.dlmgr.start_download(tdef=TorrentDefNoMetainfo(infohash, 'name'), checkpoint_disabled=True)
        self.assertEqual(download, mock_download)
        self.dlmgr.downloads.clear()

    async def test_start_download_no_ti_url(self):
        """
        Test whether a ValueError is raised if we try to add a torrent without infohash or url
        """
        self.dlmgr.initialize()
        with self.assertRaises(ValueError):
            self.dlmgr.start_download()

    def test_remove_unregistered_torrent(self):
        """
        Tests a successful removal status of torrents which aren't known
        """
        self.dlmgr.initialize()
        mock_handle = MockObject()
        mock_handle.is_valid = lambda: False
        alert = type('torrent_removed_alert', (object, ), dict(handle=mock_handle, info_hash='0'*20))
        self.dlmgr.process_alert(alert())

        self.assertNotIn('0' * 20, self.dlmgr.downloads)

    def test_set_proxy_settings(self):
        """
        Test setting the proxy settings
        """
        def on_proxy_set(settings):
            self.assertTrue(settings)
            self.assertEqual(settings.hostname, 'a')
            self.assertEqual(settings.port, 1234)
            self.assertEqual(settings.username, 'abc')
            self.assertEqual(settings.password, 'def')

        def on_set_settings(settings):
            self.assertTrue(settings)
            self.assertEqual(settings['proxy_hostname'], 'a')
            self.assertEqual(settings['proxy_port'], 1234)
            self.assertEqual(settings['proxy_username'], 'abc')
            self.assertEqual(settings['proxy_password'], 'def')
            self.assertEqual(settings['proxy_peer_connections'], True)
            self.assertEqual(settings['proxy_hostnames'], True)

        mock_lt_session = MockObject()
        mock_lt_session.get_settings = lambda: {}
        mock_lt_session.set_settings = on_set_settings
        mock_lt_session.set_proxy = on_proxy_set  # Libtorrent < 1.1.0 uses set_proxy to set proxy settings
        self.dlmgr.set_proxy_settings(mock_lt_session, 0, ('a', "1234"), ('abc', 'def'))

    async def test_save_resume_preresolved_magnet(self):
        """
        Test whether a magnet link correctly writes save-resume data before it is resolved.

        This can happen when a magnet link is added when the user does not have internet.
        """
        self.dlmgr.initialize()
        dlcheckpoints_tempdir = mkdtemp(suffix=u'dlcheckpoints_tmpdir')
        self.dlmgr.get_download = lambda _: None
        self.dlmgr.tribler_session = self.tribler_session
        self.dlmgr.get_checkpoint_dir = lambda: dlcheckpoints_tempdir
        self.tribler_session.dlmgr = self.dlmgr

        download = await self.dlmgr.start_download_from_uri("magnet:?xt=urn:btih:" + ('1' * 40))
        basename = hexlify(download.get_def().get_infohash()) + '.conf'
        filename = self.dlmgr.get_checkpoint_dir() / basename
        self.assertTrue(filename.is_file())

    def test_payout_on_disconnect(self):
        """
        Test whether a payout is initialized when a peer disconnects
        """
        disconnect_alert = type('peer_disconnected', (object,), dict(pid=Mock(to_bytes=lambda: b'a' * 20)))()
        self.dlmgr.tribler_session.payout_manager = Mock()
        self.dlmgr.initialize()
        self.dlmgr.get_session(0).pop_alerts = lambda: [disconnect_alert]
        self.dlmgr._task_process_alerts()
        self.dlmgr.tribler_session.payout_manager.do_payout.is_called_with(b'a' * 20)

    async def test_post_session_stats(self):
        """
        Test whether post_session_stats actually updates the state of libtorrent readiness for clean shutdown.
        """
        self.dlmgr.default_alert_mask = 0xffffffff
        self.dlmgr.initialize()

        # Zero hop session should be initialized
        self.assertFalse(self.dlmgr.lt_session_shutdown_ready[0])

        # Check for status with session stats alert
        self.dlmgr.post_session_stats(hops=0)

        # Wait sometime to get the alert and check the status
        await sleep(0.01)
        self.dlmgr._task_process_alerts()
        self.assertTrue(self.dlmgr.lt_session_shutdown_ready[0])

    def test_load_checkpoint(self):
        good = []

        def mock_start_download(*_, **__):
            good.append(1)
        self.dlmgr.start_download = mock_start_download

        # Try opening real state file
        state = TESTS_DATA_DIR / "config_files/13a25451c761b1482d3e85432f07c4be05ca8a56.conf"
        self.dlmgr.load_checkpoint(state)
        self.assertTrue(good)

        # Try opening nonexistent file
        good = []
        self.dlmgr.load_checkpoint("nonexistent_file")
        self.assertFalse(good)

        # Try opening corrupt file
        config_file_path = TESTS_DATA_DIR / "config_files/corrupt_session_config.conf"
        self.dlmgr.load_checkpoint(config_file_path)
        self.assertFalse(good)

    def test_load_empty_checkpoint(self):
        """
        Test whether download resumes with faulty pstate file.
        """
        self.dlmgr.get_downloads_pstate_dir = lambda: self.session_base_dir
        self.dlmgr.start_download = Mock()

        # Empty pstate file
        pstate_filename = self.dlmgr.get_downloads_pstate_dir() / 'abcd.state'
        with open(pstate_filename, 'wb') as state_file:
            state_file.write(b"")

        self.dlmgr.load_checkpoint(pstate_filename)
        self.dlmgr.start_download.assert_not_called()

    async def test_load_checkpoints(self):
        """
        Test whether we are resuming downloads after loading checkpoints
        """
        def mocked_load_checkpoint(filename):
            self.assertTrue(str(filename).endswith('abcd.conf'))
            mocked_load_checkpoint.called = True

        mocked_load_checkpoint.called = False
        self.dlmgr.get_checkpoint_dir = lambda: self.session_base_dir

        with open(self.dlmgr.get_checkpoint_dir() / 'abcd.conf', 'wb') as state_file:
            state_file.write(b"hi")

        self.dlmgr.load_checkpoint = mocked_load_checkpoint
        await self.dlmgr.load_checkpoints()
        self.assertTrue(mocked_load_checkpoint.called)

    async def test_readd_download_safe_seeding(self):
        """
        Test whether a download is re-added when doing safe seeding
        """
        self.tribler_session.bootstrap = None
        readd_future = Future()

        async def mocked_update_hops(*_):
            readd_future.set_result(None)

        self.dlmgr.update_hops = mocked_update_hops

        fake_download, dl_state = create_fake_download_and_state()
        self.dlmgr.downloads = {'aaaa': fake_download}
        await self.dlmgr.sesscb_states_callback([dl_state])

        return readd_future

    @timeout(10)
    async def test_dlstates_cb_error(self):
        """
        Testing whether a download is stopped on error in the download states callback
        """

        error_stop_future = Future()

        async def mocked_stop(user_stopped=None):
            error_stop_future.set_result(None)

        fake_error_download, fake_error_state = create_fake_download_and_state()
        fake_error_download.stop = mocked_stop
        fake_error_state.get_status = lambda: DLSTATUS_STOPPED_ON_ERROR
        fake_error_state.get_error = lambda: "test error"

        self.dlmgr.downloads = {b'aaaa': fake_error_download}
        await self.dlmgr.sesscb_states_callback([fake_error_state])

        return error_stop_future

    def test_get_downloads_by_name(self):
        dl = self.dlmgr.start_download(torrent_file=TORRENT_UBUNTU_FILE, checkpoint_disabled=True)
        self.assertTrue(self.dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso"))
        self.assertFalse(self.dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso", channels_only=True))
        self.assertFalse(self.dlmgr.get_downloads_by_name("bla"))

        dl.config.set_channel_download(True)
        self.assertTrue(self.dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso", channels_only=True))

    @timeout(20)
    async def test_checkpoint_after_metainfo_cancel(self):
        """
        Test whether there is a checkpoint after starting a download that already a pending metainfo request
        """
        dlcheckpoints_tempdir = mkdtemp(suffix='dlcheckpoints_tmpdir')
        self.dlmgr.tribler_session = self.tribler_session
        self.dlmgr.get_checkpoint_dir = lambda: dlcheckpoints_tempdir
        infohash = b'\x00' * 20
        ensure_future(self.dlmgr.get_metainfo(infohash))
        await sleep(.1)
        await self.dlmgr.start_download_from_uri(f'magnet:?xt=urn:btih:{hexlify(infohash)}&dn=name')
        await sleep(.1)
        self.assertTrue((dlcheckpoints_tempdir / f'{hexlify(infohash)}.conf').exists())
