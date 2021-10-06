from asyncio import Future, gather, get_event_loop, sleep
from unittest.mock import Mock

from ipv8.util import succeed

from libtorrent import bencode

import pytest

from tribler_common.simpledefs import DLSTATUS_SEEDING

from tribler_core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler_core.components.libtorrent.settings import LibtorrentSettings
from tribler_core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.unicode import hexlify


def create_fake_download_and_state():
    """
    Create a fake download and state which can be passed to the global download callback.
    """
    tdef = TorrentDef()
    tdef.get_infohash = lambda: b'aaaa'
    fake_peer = {'extended_version': 'Tribler', 'id': 'a' * 20, 'dtotal': 10 * 1024 * 1024}
    fake_download = Mock()
    fake_download.get_def = lambda: tdef
    fake_download.get_def().get_name_as_unicode = lambda: "test.iso"
    fake_download.get_peerlist = lambda: [fake_peer]
    fake_download.hidden = False
    fake_download.checkpoint = lambda: succeed(None)
    fake_download.stop = lambda: succeed(None)
    fake_download.shutdown = lambda: succeed(None)
    dl_state = Mock()
    dl_state.get_infohash = lambda: b'aaaa'
    dl_state.get_status = lambda: DLSTATUS_SEEDING
    dl_state.get_download = lambda: fake_download
    fake_config = Mock()
    fake_config.get_hops = lambda: 0
    fake_config.get_safe_seeding = lambda: True
    fake_download.config = fake_config

    return fake_download, dl_state


@pytest.fixture
async def fake_dlmgr(tmp_path):
    config = LibtorrentSettings(dht_readiness_timeout=0)
    dlmgr = DownloadManager(config=config, state_dir=tmp_path, notifier=Mock(), peer_mid=b"0000")
    dlmgr.metadata_tmpdir = tmp_path
    dlmgr.get_session = lambda *_, **__: Mock()
    yield dlmgr
    await dlmgr.shutdown(timeout=0)


@pytest.mark.asyncio
async def test_get_metainfo_valid_metadata(fake_dlmgr):
    """
    Testing the get_metainfo method when the handle has valid metadata immediately
    """
    infohash = b"a" * 20
    metainfo = {b'info': {b'pieces': [b'a']}, b'leechers': 0, b'nodes': [], b'seeders': 0}

    download_impl = Mock()
    download_impl.tdef.get_metainfo = lambda: None
    download_impl.future_metainfo = succeed(metainfo)

    fake_dlmgr.initialize()
    fake_dlmgr.start_download = Mock(return_value=download_impl)
    fake_dlmgr.download_defaults.number_hops = 1
    fake_dlmgr.remove_download = Mock(return_value=succeed(None))

    assert await fake_dlmgr.get_metainfo(infohash) == metainfo
    fake_dlmgr.start_download.assert_called_once()
    fake_dlmgr.remove_download.assert_called_once()


@pytest.mark.asyncio
async def test_get_metainfo_add_fail(fake_dlmgr):
    """
    Test whether we try to add a torrent again if the atp is rejected
    """
    infohash = b"a" * 20
    metainfo = {'pieces': ['a']}

    download_impl = Mock()
    download_impl.future_metainfo = succeed(metainfo)
    download_impl.tdef.get_metainfo = lambda: None

    fake_dlmgr.initialize()
    fake_dlmgr.start_download = Mock()
    fake_dlmgr.start_download.side_effect = TypeError
    fake_dlmgr.download_defaults.number_hops = 1
    fake_dlmgr.remove = Mock(return_value=succeed(None))

    assert await fake_dlmgr.get_metainfo(infohash) is None
    fake_dlmgr.start_download.assert_called_once()
    fake_dlmgr.remove.assert_not_called()


@pytest.mark.asyncio
async def test_get_metainfo_duplicate_request(fake_dlmgr):
    """
    Test whether the same request is returned when invoking get_metainfo twice with the same infohash
    """
    infohash = b"a" * 20
    metainfo = {'pieces': ['a']}

    download_impl = Mock()
    download_impl.tdef.get_metainfo = lambda: None
    download_impl.future_metainfo = Future()
    get_event_loop().call_later(0.1, download_impl.future_metainfo.set_result, metainfo)

    fake_dlmgr.initialize()
    fake_dlmgr.start_download = Mock(return_value=download_impl)
    fake_dlmgr.download_defaults.number_hops = 1
    fake_dlmgr.remove_download = Mock(return_value=succeed(None))

    results = await gather(fake_dlmgr.get_metainfo(infohash), fake_dlmgr.get_metainfo(infohash))
    assert results == [metainfo, metainfo]
    fake_dlmgr.start_download.assert_called_once()
    fake_dlmgr.remove_download.assert_called_once()


@pytest.mark.asyncio
async def test_get_metainfo_cache(fake_dlmgr):
    """
    Testing whether cached metainfo is returned, if available
    """
    fake_dlmgr.initialize()
    fake_dlmgr.metainfo_cache[b"a" * 20] = {'meta_info': 'test', 'time': 0}

    assert await fake_dlmgr.get_metainfo(b"a" * 20) == "test"


@pytest.mark.asyncio
async def test_get_metainfo_with_already_added_torrent(fake_dlmgr):
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

    fake_dlmgr.initialize()
    fake_dlmgr.downloads[torrent_def.infohash] = download_impl

    assert await fake_dlmgr.get_metainfo(torrent_def.infohash)


@pytest.mark.asyncio
async def test_start_download_while_getting_metainfo(fake_dlmgr):
    """
    Testing adding a torrent while a metainfo request is running.
    """
    infohash = b"a" * 20

    metainfo_session = Mock()
    metainfo_session.get_torrents = lambda: []

    metainfo_dl = Mock()
    metainfo_dl.get_def = lambda: Mock(get_infohash=lambda: infohash)

    fake_dlmgr.initialize()
    fake_dlmgr.get_session = lambda *_: metainfo_session
    fake_dlmgr.downloads[infohash] = metainfo_dl
    fake_dlmgr.metainfo_requests[infohash] = [metainfo_dl, 1]
    fake_dlmgr.remove_download = Mock(return_value=succeed(None))

    tdef = TorrentDefNoMetainfo(infohash, 'name', f'magnet:?xt=urn:btih:{hexlify(infohash)}&')
    download = fake_dlmgr.start_download(tdef=tdef, checkpoint_disabled=True)
    assert metainfo_dl != download
    await sleep(.1)
    assert fake_dlmgr.downloads[infohash] == download
    fake_dlmgr.remove_download.assert_called_once_with(metainfo_dl, remove_content=True, remove_checkpoint=False)


@pytest.mark.asyncio
async def test_start_download(fake_dlmgr):
    """
    Testing the addition of a torrent to the libtorrent manager
    """
    infohash = b'a' * 20

    mock_handle = Mock()
    mock_handle.info_hash = lambda: hexlify(infohash)
    mock_handle.is_valid = lambda: True

    mock_error = Mock()
    mock_error.value = lambda: None

    mock_alert = type('add_torrent_alert', (object,), dict(handle=mock_handle,
                                                           error=mock_error,
                                                           category=lambda _: None))()

    mock_ltsession = Mock()
    mock_ltsession.get_torrents = lambda: []
    mock_ltsession.async_add_torrent = lambda _: fake_dlmgr.register_task('post_alert',
                                                                          fake_dlmgr.process_alert,
                                                                          mock_alert, delay=0.1)

    fake_dlmgr.get_session = lambda *_: mock_ltsession

    download = fake_dlmgr.start_download(tdef=TorrentDefNoMetainfo(infohash, ''), checkpoint_disabled=True)
    handle = await download.get_handle()
    assert handle == mock_handle
    fake_dlmgr.downloads.clear()
    await download.shutdown()

    # Test waiting on DHT getting enough nodes and adding the torrent after timing out
    fake_dlmgr.dht_readiness_timeout = 0.5
    flag = []
    check_was_run = Mock()

    async def mock_check():
        while not flag:
            check_was_run()
            await sleep(0.1)
    fake_dlmgr._check_dht_ready = mock_check
    fake_dlmgr.initialize()

    mock_download = Mock()
    mock_download.get_def().get_infohash = lambda: b"1"*20
    mock_download.future_added = succeed(True)
    mock_ltsession.async_add_torrent = Mock()
    await fake_dlmgr.start_handle(mock_download, {})
    check_was_run.assert_called()
    fake_dlmgr.downloads.clear()

    # Test waiting on DHT getting enough nodes
    fake_dlmgr.dht_readiness_timeout = 100
    flag.append(True)
    mock_download.future_added = succeed(True)
    await fake_dlmgr.start_handle(mock_download, {})
    fake_dlmgr.downloads.clear()


@pytest.mark.asyncio
async def test_start_download_existing_handle(fake_dlmgr):
    """
    Testing the addition of a torrent to the libtorrent manager, if there is a pre-existing handle.
    """
    infohash = b'a' * 20

    mock_handle = Mock()
    mock_handle.info_hash = lambda: hexlify(infohash)
    mock_handle.is_valid = lambda: True

    mock_ltsession = Mock()
    mock_ltsession.get_torrents = lambda: [mock_handle]

    fake_dlmgr.get_session = lambda *_: mock_ltsession

    download = fake_dlmgr.start_download(tdef=TorrentDefNoMetainfo(infohash, 'name'), checkpoint_disabled=True)
    handle = await download.get_handle()
    assert handle == mock_handle
    fake_dlmgr.downloads.clear()
    await download.shutdown()


@pytest.mark.asyncio
async def test_start_download_existing_download(fake_dlmgr):
    """
    Testing the addition of a torrent to the libtorrent manager, if there is a pre-existing download.
    """
    infohash = b'a' * 20

    mock_download = Mock()
    mock_download.get_def = lambda: Mock(get_trackers_as_single_tuple=lambda: ())

    mock_ltsession = Mock()

    fake_dlmgr.downloads[infohash] = mock_download
    fake_dlmgr.get_session = lambda *_: mock_ltsession

    download = fake_dlmgr.start_download(tdef=TorrentDefNoMetainfo(infohash, 'name'), checkpoint_disabled=True)
    assert download == mock_download
    fake_dlmgr.downloads.clear()


def test_start_download_no_ti_url(fake_dlmgr):
    """
    Test whether a ValueError is raised if we try to add a torrent without infohash or url
    """
    fake_dlmgr.initialize()
    with pytest.raises(ValueError):
        fake_dlmgr.start_download()


def test_remove_unregistered_torrent(fake_dlmgr):
    """
    Tests a successful removal status of torrents which aren't known
    """
    fake_dlmgr.initialize()
    mock_handle = Mock()
    mock_handle.is_valid = lambda: False
    alert = type('torrent_removed_alert', (object, ), dict(handle=mock_handle, info_hash='0'*20))
    fake_dlmgr.process_alert(alert())

    assert '0' * 20 not in fake_dlmgr.downloads


def test_set_proxy_settings(fake_dlmgr):
    """
    Test setting the proxy settings
    """
    def on_proxy_set(settings):
        assert settings
        assert settings.hostname == 'a'
        assert settings.port == 1234
        assert settings.username == 'abc'
        assert settings.password == 'def'

    def on_set_settings(settings):
        assert settings
        assert settings['proxy_hostname'] == 'a'
        assert settings['proxy_port'] == 1234
        assert settings['proxy_username'] == 'abc'
        assert settings['proxy_password'] == 'def'
        assert settings['proxy_peer_connections']
        assert settings['proxy_hostnames']

    mock_lt_session = Mock()
    mock_lt_session.get_settings = lambda: {}
    mock_lt_session.set_settings = on_set_settings
    mock_lt_session.set_proxy = on_proxy_set  # Libtorrent < 1.1.0 uses set_proxy to set proxy settings
    fake_dlmgr.set_proxy_settings(mock_lt_session, 0, ('a', "1234"), ('abc', 'def'))


def test_payout_on_disconnect(fake_dlmgr):
    """
    Test whether a payout is initialized when a peer disconnects
    """
    disconnect_alert = type('peer_disconnected', (object,), dict(pid=Mock(to_bytes=lambda: b'a' * 20)))()
    fake_dlmgr.payout_manager = Mock()
    fake_dlmgr.initialize()
    fake_dlmgr.get_session(0).pop_alerts = lambda: [disconnect_alert]
    fake_dlmgr._task_process_alerts()
    fake_dlmgr.payout_manager.do_payout.is_called_with(b'a' * 20)


@pytest.mark.asyncio
async def test_post_session_stats(fake_dlmgr):
    """
    Test whether post_session_stats actually updates the state of libtorrent readiness for clean shutdown.
    """
    mock_lt_session = Mock()
    fake_dlmgr.ltsessions[0] = mock_lt_session

    # Check for status with session stats alert
    fake_dlmgr.post_session_stats(hops=0)
    mock_lt_session.post_session_stats.assert_called_once()


def test_load_checkpoint(fake_dlmgr):
    good = []

    def mock_start_download(*_, **__):
        good.append(1)
    fake_dlmgr.start_download = mock_start_download

    # Try opening real state file
    state = TESTS_DATA_DIR / "config_files/13a25451c761b1482d3e85432f07c4be05ca8a56.conf"
    fake_dlmgr.load_checkpoint(state)
    assert good

    # Try opening nonexistent file
    good = []
    fake_dlmgr.load_checkpoint("nonexistent_file")
    assert not good

    # Try opening corrupt file
    config_file_path = TESTS_DATA_DIR / "config_files/corrupt_session_config.conf"
    fake_dlmgr.load_checkpoint(config_file_path)
    assert not good


def test_load_empty_checkpoint(fake_dlmgr, tmpdir):
    """
    Test whether download resumes with faulty pstate file.
    """
    fake_dlmgr.get_downloads_pstate_dir = lambda: tmpdir
    fake_dlmgr.start_download = Mock()

    # Empty pstate file
    pstate_filename = fake_dlmgr.get_downloads_pstate_dir() / 'abcd.state'
    with open(pstate_filename, 'wb') as state_file:
        state_file.write(b"")

    fake_dlmgr.load_checkpoint(pstate_filename)
    fake_dlmgr.start_download.assert_not_called()


@pytest.mark.asyncio
async def test_load_checkpoints(fake_dlmgr, tmpdir):
    """
    Test whether we are resuming downloads after loading checkpoints
    """
    def mocked_load_checkpoint(filename):
        assert str(filename).endswith('abcd.conf')
        mocked_load_checkpoint.called = True

    mocked_load_checkpoint.called = False
    fake_dlmgr.get_checkpoint_dir = lambda: Path(tmpdir)

    with open(fake_dlmgr.get_checkpoint_dir() / 'abcd.conf', 'wb') as state_file:
        state_file.write(b"hi")

    fake_dlmgr.load_checkpoint = mocked_load_checkpoint
    await fake_dlmgr.load_checkpoints()
    assert mocked_load_checkpoint.called


@pytest.mark.asyncio
async def test_readd_download_safe_seeding(fake_dlmgr):
    """
    Test whether a download is re-added when doing safe seeding
    """
    fake_dlmgr.bootstrap = None
    readd_future = Future()

    async def mocked_update_hops(*_):
        readd_future.set_result(None)

    fake_dlmgr.update_hops = mocked_update_hops

    fake_download, dl_state = create_fake_download_and_state()
    fake_dlmgr.downloads = {'aaaa': fake_download}
    await fake_dlmgr.sesscb_states_callback([dl_state])
    await readd_future


def test_get_downloads_by_name(fake_dlmgr):
    dl = fake_dlmgr.start_download(torrent_file=TORRENT_UBUNTU_FILE, checkpoint_disabled=True)
    assert fake_dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso")
    assert not fake_dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso", channels_only=True)
    assert not fake_dlmgr.get_downloads_by_name("bla")

    dl.config.set_channel_download(True)
    assert fake_dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso", channels_only=True)


@pytest.mark.asyncio
async def test_check_for_dht_ready(fake_dlmgr):
    fake_dlmgr.get_session = Mock()
    fake_dlmgr.get_session().status().dht_nodes = 1000
    # If the session has enough peers, it should finish instantly
    await fake_dlmgr._check_dht_ready()
