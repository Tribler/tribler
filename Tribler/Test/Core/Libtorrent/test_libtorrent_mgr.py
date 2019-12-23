import os
import shutil
import tempfile
from asyncio import Future, gather, get_event_loop, sleep
from binascii import unhexlify
from unittest.mock import Mock

from libtorrent import bencode

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.Core.Notifier import Notifier
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Utilities.utilities import succeed
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.tools import timeout


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
    dl_state = MockObject()
    dl_state.get_infohash = lambda: b'aaaa'
    dl_state.get_status = lambda: DLSTATUS_SEEDING
    dl_state.get_download = lambda: fake_download
    fake_config = MockObject()
    fake_config.get_hops = lambda: 0
    fake_config.get_safe_seeding = lambda: True
    fake_download.config = fake_config

    return fake_download, dl_state


class TestLibtorrentMgr(AbstractServer):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    LIBTORRENT_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"../data/libtorrent/"))

    async def setUp(self):
        await super(TestLibtorrentMgr, self).setUp()

        self.tribler_session = MockObject()
        self.tribler_session.notifier = Notifier()
        self.tribler_session.state_dir = self.session_base_dir
        self.tribler_session.trustchain_keypair = MockObject()
        self.tribler_session.trustchain_keypair.key_to_hash = lambda: b'a' * 20
        self.tribler_session.notify_shutdown_state = lambda _: None

        self.tribler_session.tunnel_community = None

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

        self.ltmgr = LibtorrentMgr(self.tribler_session)
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

    async def tearDown(self):
        await self.ltmgr.shutdown(timeout=0)
        self.assertTrue(os.path.exists(os.path.join(self.session_base_dir, 'lt.state')))
        await super(TestLibtorrentMgr, self).tearDown()

    def test_get_session_zero_hops(self):
        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(0)
        self.assertTrue(ltsession)

    def test_get_session_one_hop(self):
        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(1)
        self.assertTrue(ltsession)

    def test_get_session_zero_hops_corrupt_lt_state(self):
        with open(os.path.join(self.session_base_dir, 'lt.state'), "w") as file:
            file.write("Lorem ipsum")

        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(0)
        self.assertTrue(ltsession)

    def test_get_session_zero_hops_working_lt_state(self):
        shutil.copy(os.path.join(self.LIBTORRENT_FILES_DIR, 'lt.state'),
                    os.path.join(self.session_base_dir, 'lt.state'))
        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(0)
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
        download_impl.future_metainfo = succeed(metainfo)

        self.ltmgr.initialize()
        self.ltmgr.add = Mock(return_value=download_impl)
        self.ltmgr.tribler_session.config.get_default_number_hops = lambda: 1
        self.ltmgr.remove = Mock(return_value=succeed(None))

        self.assertEqual(await self.ltmgr.get_metainfo(infohash), metainfo)
        self.ltmgr.add.assert_called_once()
        self.ltmgr.remove.assert_called_once()

    @timeout(20)
    async def test_get_metainfo_add_fail(self):
        """
        Test whether we try to add a torrent again if the atp is rejected
        """
        infohash = b"a" * 20
        metainfo = {'pieces': ['a']}

        download_impl = Mock()
        download_impl.future_metainfo = succeed(metainfo)

        self.ltmgr.initialize()
        self.ltmgr.add = Mock()
        self.ltmgr.add.side_effect = TypeError
        self.ltmgr.tribler_session.config.get_default_number_hops = lambda: 1
        self.ltmgr.remove = Mock(return_value=succeed(None))

        self.assertEqual(await self.ltmgr.get_metainfo(infohash), None)
        self.ltmgr.add.assert_called_once()
        self.ltmgr.remove.assert_not_called()

    @timeout(20)
    async def test_get_metainfo_duplicate_request(self):
        """
        Test whether the same request is returned when invoking get_metainfo twice with the same infohash
        """
        infohash = b"a" * 20
        metainfo = {'pieces': ['a']}

        download_impl = Mock()
        download_impl.future_metainfo = Future()
        get_event_loop().call_later(0.1, download_impl.future_metainfo.set_result, metainfo)

        self.ltmgr.initialize()
        self.ltmgr.add = Mock(return_value=download_impl)
        self.ltmgr.tribler_session.config.get_default_number_hops = lambda: 1
        self.ltmgr.remove = Mock(return_value=succeed(None))

        results = await gather(self.ltmgr.get_metainfo(infohash), self.ltmgr.get_metainfo(infohash))
        self.assertEqual(results, [metainfo, metainfo])
        self.ltmgr.add.assert_called_once()
        self.ltmgr.remove.assert_called_once()

    @timeout(20)
    async def test_get_metainfo_cache(self):
        """
        Testing whether cached metainfo is returned, if available
        """
        self.ltmgr.initialize()
        self.ltmgr.metainfo_cache[b"a" * 20] = {'meta_info': 'test', 'time': 0}

        self.assertEqual(await self.ltmgr.get_metainfo(b"a" * 20), "test")

    @timeout(20)
    async def test_get_metainfo_with_already_added_torrent(self):
        """
        Testing metainfo fetching for a torrent which is already in session.
        """
        sample_torrent = os.path.join(TESTS_DATA_DIR, "bak_single.torrent")
        torrent_def = TorrentDef.load(sample_torrent)

        download_impl = Mock()
        download_impl.future_metainfo = succeed(bencode(torrent_def.get_metainfo()))

        self.ltmgr.initialize()
        self.ltmgr.torrents[hexlify(torrent_def.infohash)] = (download_impl, Mock())

        self.assertTrue(await self.ltmgr.get_metainfo(torrent_def.infohash))

    @timeout(20)
    async def test_add_torrent_while_already_getting_metainfo(self):
        """
        Testing adding a torrent while a metainfo request is running.
        """
        infohash_hex = "a" * 40

        metainfo_handle = Mock()
        metainfo_session = Mock()
        metainfo_session.get_torrents = Mock(return_value=[metainfo_handle])
        metainfo_dl = Mock()
        metainfo_dl.stop = Mock(return_value=succeed(None))

        self.ltmgr.initialize()
        self.ltmgr.get_session = lambda *_: metainfo_session
        self.ltmgr.torrents[infohash_hex] = (metainfo_dl, metainfo_session)
        self.ltmgr.metainfo_requests[infohash_hex] = [metainfo_dl, 1]

        other_handle = Mock()
        other_dl = Mock()
        other_dl.future_added = succeed(other_handle)

        result = await self.ltmgr.add_torrent(other_dl, {'url': 'magnet:?xt=urn:btih:%s&dn=%s' % (infohash_hex, 'name')})
        metainfo_dl.stop.assert_called_once_with(remove_state=True, remove_content=True)
        self.assertEqual(result, other_handle)
        self.assertEqual(self.ltmgr.torrents[infohash_hex], (other_dl, metainfo_session))

    @timeout(20)
    async def test_add_torrent(self):
        """
        Testing the addition of a torrent to the libtorrent manager
        """
        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20
        mock_handle.is_valid = lambda: False

        mock_error = MockObject()
        mock_error.value = lambda: None

        mock_alert = type('add_torrent_alert', (object,), dict(handle=mock_handle, error=mock_error))()

        mock_ltsession = MockObject()
        mock_ltsession.async_add_torrent = lambda _: get_event_loop().call_later(0.1, self.ltmgr.process_alert,
                                                                                 mock_alert)
        mock_ltsession.find_torrent = lambda _: mock_handle
        mock_ltsession.get_torrents = lambda: []
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.get_session = lambda *_: mock_ltsession

        infohash = MockObject()
        infohash.info_hash = lambda: 'a' * 20

        mock_download = MockObject()
        mock_download.future_added = Future()

        handle = await self.ltmgr.add_torrent(mock_download, {'ti': infohash})
        self.assertEqual(handle, mock_handle)

    @timeout(20)
    async def test_add_torrent_desync(self):
        """
        Testing the addition of a torrent to the libtorrent manager, if it already exists in the session.
        """
        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20
        mock_handle.is_valid = lambda: True

        mock_alert = type('add_torrent_alert', (object,), dict(handle=mock_handle))

        mock_ltsession = MockObject()
        mock_ltsession.async_add_torrent = lambda _: self.ltmgr.process_alert(mock_alert)
        mock_ltsession.find_torrent = lambda _: mock_handle
        mock_ltsession.get_torrents = lambda: [mock_handle]
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.get_session = lambda *_: mock_ltsession

        infohash = MockObject()
        infohash.info_hash = lambda: 'a' * 20

        mock_download = MockObject()
        mock_download.Future_added = Future()
        handle = await self.ltmgr.add_torrent(mock_download, {'ti': infohash})
        self.assertEqual(handle, mock_handle)

    async def test_add_torrent_no_ti_url(self):
        """
        Test whether a ValueError is raised if we try to add a torrent without infohash or url
        """
        self.ltmgr.initialize()
        with self.assertRaises(ValueError):
            await self.ltmgr.add_torrent(None, {})

    async def test_remove_invalid_torrent(self):
        """
        Tests a successful removal status of torrents without a handle
        """
        self.ltmgr.initialize()
        mock_dl = MockObject()
        mock_dl.handle = None
        self.assertTrue(self.ltmgr.remove_torrent(mock_dl).done())

    def test_remove_invalid_handle_torrent(self):
        """
        Tests a successful removal status of torrents with an invalid handle
        """
        self.ltmgr.initialize()
        mock_handle = MockObject()
        mock_handle.is_valid = lambda: False
        mock_dl = MockObject()
        mock_dl.handle = mock_handle
        self.assertTrue(self.ltmgr.remove_torrent(mock_dl).done())

    def test_remove_unregistered_torrent(self):
        """
        Tests a successful removal status of torrents which aren't known
        """
        self.ltmgr.initialize()
        mock_handle = MockObject()
        mock_handle.is_valid = lambda: False
        alert = type('torrent_removed_alert', (object, ), dict(handle=mock_handle, info_hash='0'*20))
        self.ltmgr.process_alert(alert())

        self.assertNotIn('0'*20, self.ltmgr.torrents)

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
        self.ltmgr.set_proxy_settings(mock_lt_session, 0, ('a', "1234"), ('abc', 'def'))

    async def test_save_resume_preresolved_magnet(self):
        """
        Test whether a magnet link correctly writes save-resume data before it is resolved.

        This can happen when a magnet link is added when the user does not have internet.
        """

        self.ltmgr.initialize()
        dlcheckpoints_tempdir = tempfile.mkdtemp(suffix=u'dlcheckpoints_tmpdir')
        self.ltmgr.get_download = lambda _: None
        self.ltmgr.tribler_session = self.tribler_session
        self.ltmgr.get_downloads_config_dir = lambda: dlcheckpoints_tempdir
        self.tribler_session.ltmgr = self.ltmgr

        def dl_from_tdef(tdef, _):
            dl = LibtorrentDownloadImpl(self.tribler_session, tdef)
            dl.setup()
            return dl
        self.ltmgr.add = dl_from_tdef

        download = self.ltmgr.start_download_from_magnet("magnet:?xt=urn:btih:" + ('1' * 40))
        await download.get_handle()
        basename = hexlify(download.get_def().get_infohash()) + '.conf'
        filename = os.path.join(self.ltmgr.get_downloads_config_dir(), basename)
        self.assertTrue(os.path.isfile(filename))

    @timeout(5)
    async def test_callback_on_alert(self):
        """
        Test whether the alert callback is called when a libtorrent alert is posted
        """
        self.ltmgr.default_alert_mask = 0xffffffff
        test_future = Future()

        def callback(*args):
            self.ltmgr.alert_callback = None
            test_future.set_result(None)

        callback.called = False
        self.ltmgr.alert_callback = callback
        self.ltmgr.initialize()
        self.ltmgr._task_process_alerts()
        return test_future

    def test_payout_on_disconnect(self):
        """
        Test whether a payout is initialized when a peer disconnects
        """
        class peer_disconnected_alert(object):
            def __init__(self):
                self.pid = MockObject()
                self.pid.to_bytes = lambda: b'a' * 20

        def mocked_do_payout(mid):
            self.assertEqual(mid, b'a' * 20)
            mocked_do_payout.called = True
        mocked_do_payout.called = False

        disconnect_alert = peer_disconnected_alert()
        self.ltmgr.tribler_session.payout_manager = MockObject()
        self.ltmgr.tribler_session.payout_manager.do_payout = mocked_do_payout
        self.ltmgr.initialize()
        self.ltmgr.get_session(0).pop_alerts = lambda: [disconnect_alert]
        self.ltmgr._task_process_alerts()

        self.assertTrue(mocked_do_payout.called)

    async def test_post_session_stats(self):
        """
        Test whether post_session_stats actually updates the state of libtorrent readiness for clean shutdown.
        """
        self.ltmgr.default_alert_mask = 0xffffffff
        self.ltmgr.initialize()

        # Zero hop session should be initialized
        self.assertFalse(self.ltmgr.lt_session_shutdown_ready[0])

        # Check for status with session stats alert
        self.ltmgr.post_session_stats(hops=0)

        # Wait sometime to get the alert and check the status
        await sleep(0.01)
        self.ltmgr._task_process_alerts()
        self.assertTrue(self.ltmgr.lt_session_shutdown_ready[0])

    def test_resume_download(self):
        good = []

        def mock_add(tdef, dscfg, delay=None):
            good.append(1)
        self.ltmgr.add = mock_add

        # Try opening real state file
        state = os.path.abspath(os.path.join(self.FILE_DIR, u"../data", u"config_files",
                                             u"13a25451c761b1482d3e85432f07c4be05ca8a56.conf"))
        print (state)
        self.ltmgr.resume_download(state)
        self.assertTrue(good)

        # Try opening nonexistent file
        good = []
        self.ltmgr.resume_download("nonexistent_file")
        self.assertFalse(good)

        # Try opening corrupt file
        config_file_path = os.path.abspath(os.path.join(self.FILE_DIR, u"../data", u"config_files",
                                                        u"corrupt_session_config.conf"))
        self.ltmgr.resume_download(config_file_path)
        self.assertFalse(good)

    def test_load_download_config(self):
        """
        Testing whether a DownloadConfig is successfully loaded
        """
        config_file_path = os.path.abspath(os.path.join(self.FILE_DIR, u"../data", u"config_files"))
        self.ltmgr.get_downloads_config_dir = lambda: config_file_path
        infohash = unhexlify("13a25451c761b1482d3e85432f07c4be05ca8a56")
        config = self.ltmgr.load_download_config_by_infohash(infohash)
        self.assertIsInstance(config, DownloadConfig)
        self.assertEqual(int(config.config['download_defaults']['time_added']), 1556724887)

    def test_resume_empty_download(self):
        """
        Test whether download resumes with faulty pstate file.
        """

        def mocked_add_download():
            mocked_add_download.called = True

        mocked_add_download.called = False
        self.ltmgr.get_downloads_pstate_dir = lambda: self.session_base_dir
        self.ltmgr.add = lambda tdef, dscfg: mocked_add_download()

        # Empty pstate file
        pstate_filename = os.path.join(self.ltmgr.get_downloads_pstate_dir(), 'abcd.state')
        with open(pstate_filename, 'wb') as state_file:
            state_file.write(b"")

        self.ltmgr.resume_download(pstate_filename)
        self.assertFalse(mocked_add_download.called)

    async def test_load_checkpoint(self):
        """
        Test whether we are resuming downloads after loading checkpoint
        """
        def mocked_resume_download(filename, delay=3):
            self.assertTrue(filename.endswith('abcd.conf'))
            self.assertEqual(delay, 0)
            mocked_resume_download.called = True

        mocked_resume_download.called = False
        self.ltmgr.get_downloads_config_dir = lambda: self.session_base_dir

        with open(os.path.join(self.ltmgr.get_downloads_config_dir(), 'abcd.conf'), 'wb') as state_file:
            state_file.write(b"hi")

        self.ltmgr.resume_download = mocked_resume_download
        self.ltmgr.load_checkpoint()
        self.assertTrue(mocked_resume_download.called)

    async def test_readd_download_safe_seeding(self):
        """
        Test whether a download is re-added when doing safe seeding
        """
        self.tribler_session.bootstrap = None
        readd_future = Future()

        async def mocked_update_download_hops(*_):
            readd_future.set_result(None)

        self.ltmgr.update_download_hops = mocked_update_download_hops

        fake_download, dl_state = create_fake_download_and_state()
        self.ltmgr.downloads = {'aaaa': fake_download}
        await self.ltmgr.sesscb_states_callback([dl_state])

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

        self.ltmgr.downloads = {b'aaaa': fake_error_download}
        await self.ltmgr.sesscb_states_callback([fake_error_state])

        return error_stop_future
