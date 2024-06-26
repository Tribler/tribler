import asyncio
import itertools
from asyncio import Future
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from ipv8.util import succeed
from libtorrent import bencode

from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.settings import LibtorrentSettings
from tribler.core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import DownloadStatus
from tribler.core.utilities.unicode import hexlify


# pylint: disable=redefined-outer-name

def create_fake_download_and_state():
    """
    Create a fake download and state which can be passed to the global download callback.
    """
    tdef = TorrentDef()
    tdef.get_infohash = lambda: b"aaaa"
    fake_peer = {
        "extended_version": "Tribler",
        "id": "a" * 20,
        "dtotal": 10 * 1024 * 1024,
    }
    fake_download = MagicMock(
        get_def=MagicMock(return_value=tdef),
        get_peerlist=MagicMock(return_value=[fake_peer]),
        hidden=False,
        checkpoint=AsyncMock(),
        stop=AsyncMock(),
        shutdown=AsyncMock(),
        config=MagicMock(
            get_hops=MagicMock(return_value=0),
            get_safe_seeding=MagicMock(return_value=True),
        ),
    )
    fake_download.get_def().get_name_as_unicode = MagicMock(return_value="test.iso")
    dl_state = MagicMock(
        get_infohash=MagicMock(return_value=b"aaaa"),
        get_status=MagicMock(return_value=DownloadStatus.SEEDING),
        get_download=MagicMock(return_value=fake_download),
    )

    return (fake_download, dl_state)


@pytest.fixture(name="fake_dlmgr")
async def fixture_fake_dlmgr(tmp_path_factory):
    config = LibtorrentSettings(dht_readiness_timeout=0)
    dlmgr = DownloadManager(
        config=config,
        state_dir=tmp_path_factory.mktemp("state_dir"),
        notifier=MagicMock(),
        peer_mid=b"0000",
    )
    dlmgr.metadata_tmpdir = tmp_path_factory.mktemp("metadata_tmpdir")
    dlmgr.get_session = lambda *_, **__: MagicMock()
    yield dlmgr
    await dlmgr.shutdown()


async def test_get_metainfo_valid_metadata(fake_dlmgr):
    """
    Testing the get_metainfo method when the handle has valid metadata immediately
    """
    infohash = b"a" * 20
    metainfo = {b'info': {b'pieces': [b'a']}, b'leechers': 0, b'nodes': [], b'seeders': 0}

    download_impl = MagicMock()
    download_impl.tdef.get_metainfo = MagicMock(return_value=None)
    download_impl.future_metainfo = succeed(metainfo)

    fake_dlmgr.initialize()
    fake_dlmgr.start_download = AsyncMock(return_value=download_impl)
    fake_dlmgr.download_defaults.number_hops = 1
    fake_dlmgr.remove_download = MagicMock(return_value=succeed(None))

    assert await fake_dlmgr.get_metainfo(infohash) == metainfo
    fake_dlmgr.start_download.assert_called_once()
    fake_dlmgr.remove_download.assert_called_once()


async def test_get_metainfo_add_fail(fake_dlmgr):
    """
    Test whether we try to add a torrent again if the atp is rejected
    """
    infohash = b"a" * 20
    metainfo = {'pieces': ['a']}

    download_impl = MagicMock()
    download_impl.future_metainfo = succeed(metainfo)
    download_impl.tdef.get_metainfo = MagicMock(return_value=None)

    fake_dlmgr.initialize()
    fake_dlmgr.start_download = AsyncMock()
    fake_dlmgr.start_download.side_effect = TypeError
    fake_dlmgr.download_defaults.number_hops = 1
    fake_dlmgr.remove = MagicMock(return_value=succeed(None))

    assert await fake_dlmgr.get_metainfo(infohash) is None
    fake_dlmgr.start_download.assert_called_once()
    fake_dlmgr.remove.assert_not_called()


async def test_get_metainfo_duplicate_request(fake_dlmgr):
    """
    Test whether the same request is returned when invoking get_metainfo twice with the same infohash
    """
    infohash = b"a" * 20
    metainfo = {'pieces': ['a']}

    download_impl = MagicMock()
    download_impl.tdef.get_metainfo = MagicMock(return_value=None)
    download_impl.future_metainfo = Future()
    asyncio.get_event_loop().call_later(0.1, download_impl.future_metainfo.set_result, metainfo)

    fake_dlmgr.initialize()
    fake_dlmgr.start_download = AsyncMock(return_value=download_impl)
    fake_dlmgr.download_defaults.number_hops = 1
    fake_dlmgr.remove_download = MagicMock(return_value=succeed(None))

    results = await asyncio.gather(fake_dlmgr.get_metainfo(infohash), fake_dlmgr.get_metainfo(infohash))
    assert results == [metainfo, metainfo]
    fake_dlmgr.start_download.assert_called_once()
    fake_dlmgr.remove_download.assert_called_once()


async def test_get_metainfo_cache(fake_dlmgr):
    """
    Testing whether cached metainfo is returned, if available
    """
    fake_dlmgr.initialize()
    fake_dlmgr.metainfo_cache[b"a" * 20] = {'meta_info': 'test', 'time': 0}

    assert await fake_dlmgr.get_metainfo(b"a" * 20) == "test"


async def test_get_metainfo_with_already_added_torrent(fake_dlmgr):
    """
    Testing metainfo fetching for a torrent which is already in session.
    """
    sample_torrent = TESTS_DATA_DIR / "bak_single.torrent"
    torrent_def = await TorrentDef.load(sample_torrent)

    download_impl = MagicMock(
        future_metainfo=succeed(bencode(torrent_def.get_metainfo())),
        checkpoint=AsyncMock(),
        stop=AsyncMock(),
        shutdown=AsyncMock(),
    )

    fake_dlmgr.initialize()
    fake_dlmgr.downloads[torrent_def.infohash] = download_impl

    assert await fake_dlmgr.get_metainfo(torrent_def.infohash)


async def test_start_download_while_getting_metainfo(fake_dlmgr):
    """
    Testing adding a torrent while a metainfo request is running.
    """
    infohash = b"a" * 20

    metainfo_session = MagicMock(get_torrents=list)
    metainfo_dl = MagicMock(get_def=MagicMock())

    fake_dlmgr.initialize()
    fake_dlmgr.get_session = MagicMock(return_value=metainfo_session)
    fake_dlmgr.downloads[infohash] = metainfo_dl
    fake_dlmgr.metainfo_requests[infohash] = [metainfo_dl, 1]
    fake_dlmgr.remove_download = AsyncMock(return_value=succeed(None))

    tdef = TorrentDefNoMetainfo(
        infohash, b"name", f"magnet:?xt=urn:btih:{hexlify(infohash)}&"
    )
    download = await fake_dlmgr.start_download(tdef=tdef, checkpoint_disabled=True)
    assert metainfo_dl != download
    await asyncio.sleep(0.1)
    assert fake_dlmgr.downloads[infohash] == download
    fake_dlmgr.remove_download.assert_called_once_with(
        metainfo_dl, remove_content=True, remove_checkpoint=False
    )


async def test_start_download(fake_dlmgr):
    """
    Testing the addition of a torrent to the libtorrent manager
    """
    infohash = b"a" * 20

    mock_handle = MagicMock(
        info_hash=MagicMock(return_value=hexlify(infohash)),
        is_valid=MagicMock(return_value=True),
    )

    mock_error = MagicMock(value=MagicMock(return_value=None))
    mock_alert = type(
        "add_torrent_alert",
        (object,),
        dict(
            handle=mock_handle, error=mock_error, category=MagicMock(return_value=None)
        ),
    )()

    mock_ltsession = MagicMock(
        get_torrents=list,
        async_add_torrent=AsyncMock(
            return_value=fake_dlmgr.register_task(
                "post_alert", fake_dlmgr.process_alert, mock_alert, delay=0.1
            ),
        ),
    )

    fake_dlmgr.get_session = MagicMock(return_value=mock_ltsession)

    download = await fake_dlmgr.start_download(
        tdef=TorrentDefNoMetainfo(infohash, b""), checkpoint_disabled=True
    )
    handle = await download.get_handle()
    assert handle == mock_handle
    fake_dlmgr.downloads.clear()
    await download.shutdown()

    # Test waiting on DHT getting enough nodes and adding the torrent after timing out
    fake_dlmgr.dht_readiness_timeout = 0.5
    flag = []
    check_was_run = MagicMock()

    async def mock_check():
        while not flag:
            check_was_run()
            await asyncio.sleep(0.1)

    fake_dlmgr._check_dht_ready = mock_check
    fake_dlmgr.initialize()

    mock_download = MagicMock()
    mock_download.get_def().get_infohash = MagicMock(return_value=b"1" * 20)
    mock_download.future_added = succeed(True)
    mock_ltsession.async_add_torrent = MagicMock()

    await fake_dlmgr.start_handle(mock_download, {})
    await asyncio.sleep(0.1)

    check_was_run.assert_called()
    fake_dlmgr.downloads.clear()

    # Test waiting on DHT getting enough nodes
    fake_dlmgr.dht_readiness_timeout = 100
    flag.append(True)
    mock_download.future_added = succeed(True)
    await fake_dlmgr.start_handle(mock_download, {})
    fake_dlmgr.downloads.clear()


async def test_start_download_existing_handle(fake_dlmgr):
    """
    Testing the addition of a torrent to the libtorrent manager, if there is a pre-existing handle.
    """
    infohash = b"a" * 20

    mock_handle = MagicMock(
        info_hash=MagicMock(return_value=hexlify(infohash)),
        is_valid=MagicMock(return_value=True),
    )
    mock_ltsession = MagicMock(get_torrents=MagicMock(return_value=[mock_handle]))

    fake_dlmgr.get_session = MagicMock(return_value=mock_ltsession)

    download = await fake_dlmgr.start_download(
        tdef=TorrentDefNoMetainfo(infohash, b"name"), checkpoint_disabled=True
    )
    handle = await download.get_handle()
    assert handle == mock_handle
    fake_dlmgr.downloads.clear()
    await download.shutdown()


def test_convert_rate():
    assert DownloadManager.convert_rate(0) == -1  # 0 is a special value
    assert DownloadManager.convert_rate(-1) == 1  # -1 is a special value
    assert DownloadManager.convert_rate(1) == 1024
    assert DownloadManager.convert_rate(2) == 2048
    assert DownloadManager.convert_rate(-2) == -2048


def test_reverse_convert_rate():
    assert DownloadManager.reverse_convert_rate(-1) == 0  # -1 is a special value
    assert DownloadManager.reverse_convert_rate(1) == -1  # 1 is a special value
    assert DownloadManager.reverse_convert_rate(0) == 0
    assert DownloadManager.reverse_convert_rate(1024) == 1
    assert DownloadManager.reverse_convert_rate(-2048) == -2


async def test_start_download_existing_download(fake_dlmgr):
    """
    Testing the addition of a torrent to the libtorrent manager, if there is a pre-existing download.
    """
    infohash = b"a" * 20

    mock_download = MagicMock(
        get_def=MagicMock(return_value=MagicMock(get_trackers=set))
    )
    mock_ltsession = MagicMock()

    fake_dlmgr.downloads[infohash] = mock_download
    fake_dlmgr.get_session = lambda *_: mock_ltsession

    download = await fake_dlmgr.start_download(
        tdef=TorrentDefNoMetainfo(infohash, b"name"), checkpoint_disabled=True
    )
    assert download == mock_download
    fake_dlmgr.downloads.clear()


async def test_start_download_no_ti_url(fake_dlmgr):
    """
    Test whether a ValueError is raised if we try to add a torrent without infohash or url
    """
    fake_dlmgr.initialize()
    with pytest.raises(ValueError):
        await fake_dlmgr.start_download()


def test_remove_unregistered_torrent(fake_dlmgr):
    """
    Tests a successful removal status of torrents which aren't known
    """
    fake_dlmgr.initialize()
    mock_handle = MagicMock()
    mock_handle.is_valid = lambda: False
    alert = type('torrent_removed_alert', (object,), dict(handle=mock_handle, info_hash='0' * 20))
    fake_dlmgr.process_alert(alert())

    assert '0' * 20 not in fake_dlmgr.downloads


def test_set_proxy_settings(fake_dlmgr):
    """
    Test setting the proxy settings
    """
    session = Mock()
    fake_dlmgr.set_proxy_settings(session, 0, ('a', "1234"), ('abc', 'def'))
    settings, = session.method_calls[-1].args
    assert settings['proxy_hostname'] == 'a'
    assert settings['proxy_port'] == 1234
    assert settings['proxy_username'] == 'abc'
    assert settings['proxy_password'] == 'def'
    assert settings['proxy_peer_connections']
    assert settings['proxy_hostnames']


def test_payout_on_disconnect(fake_dlmgr):
    """
    Test whether a payout is initialized when a peer disconnects
    """
    disconnect_alert = type(
        'peer_disconnected',
        (object,),
        dict(pid=MagicMock(to_bytes=MagicMock(return_value=b'a' * 20))),
    )()
    fake_dlmgr.payout_manager = MagicMock()
    fake_dlmgr.initialize()
    fake_dlmgr.get_session(0).pop_alerts = MagicMock(return_value=[disconnect_alert])
    fake_dlmgr._task_process_alerts()
    fake_dlmgr.payout_manager.do_payout.is_called_with(b'a' * 20)


def test_post_session_stats(fake_dlmgr):
    """
    Test whether post_session_stats actually updates the state of libtorrent readiness for clean shutdown.
    """
    mock_lt_session = MagicMock()
    fake_dlmgr.ltsessions[0] = mock_lt_session

    # Check for status with session stats alert
    fake_dlmgr.post_session_stats()
    mock_lt_session.post_session_stats.assert_called_once()


async def test_load_checkpoint(fake_dlmgr):
    good = []

    async def mock_start_download(*_, **__):
        good.append(1)

    fake_dlmgr.start_download = mock_start_download

    # Try opening real state file
    state = TESTS_DATA_DIR / "config_files/13a25451c761b1482d3e85432f07c4be05ca8a56.conf"
    await fake_dlmgr.load_checkpoint(state)
    assert good

    # Try opening nonexistent file
    good = []
    await fake_dlmgr.load_checkpoint("nonexistent_file")
    assert not good

    # Try opening corrupt file
    config_file_path = TESTS_DATA_DIR / "config_files/corrupt_session_config.conf"
    await fake_dlmgr.load_checkpoint(config_file_path)
    assert not good


@pytest.mark.asyncio
async def test_download_manager_start(fake_dlmgr):
    fake_dlmgr.start()
    await asyncio.sleep(0.01)
    assert fake_dlmgr.all_checkpoints_are_loaded


async def test_load_empty_checkpoint(fake_dlmgr, tmpdir):
    """
    Test whether download resumes with faulty pstate file.
    """
    fake_dlmgr.get_downloads_pstate_dir = MagicMock(return_value=tmpdir)
    fake_dlmgr.start_download = MagicMock()

    # Empty pstate file
    pstate_filename = fake_dlmgr.get_downloads_pstate_dir() / 'abcd.state'
    with open(pstate_filename, 'wb') as state_file:
        state_file.write(b"")

    await fake_dlmgr.load_checkpoint(pstate_filename)
    fake_dlmgr.start_download.assert_not_called()


async def test_load_checkpoints(fake_dlmgr, tmpdir):
    """
    Test whether we are resuming downloads after loading checkpoints
    """

    async def mocked_load_checkpoint(filename):
        assert str(filename).endswith('abcd.conf')
        mocked_load_checkpoint.called = True

    mocked_load_checkpoint.called = False
    fake_dlmgr.get_checkpoint_dir = MagicMock(return_value=Path(tmpdir))

    with open(fake_dlmgr.get_checkpoint_dir() / 'abcd.conf', 'wb') as state_file:
        state_file.write(b"hi")

    fake_dlmgr.load_checkpoint = mocked_load_checkpoint
    assert fake_dlmgr.all_checkpoints_are_loaded is False
    assert fake_dlmgr.checkpoints_count is None
    assert fake_dlmgr.checkpoints_loaded == 0

    await fake_dlmgr.load_checkpoints()

    assert mocked_load_checkpoint.called
    assert fake_dlmgr.all_checkpoints_are_loaded is True
    assert fake_dlmgr.checkpoints_count == 1
    assert fake_dlmgr.checkpoints_loaded == 1


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


async def test_get_downloads_by_name(fake_dlmgr):
    await fake_dlmgr.start_download(torrent_file=TORRENT_UBUNTU_FILE, checkpoint_disabled=True)
    assert fake_dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso")
    assert not fake_dlmgr.get_downloads_by_name("bla")

    assert fake_dlmgr.get_downloads_by_name("ubuntu-15.04-desktop-amd64.iso")


async def test_check_for_dht_ready(fake_dlmgr):
    fake_dlmgr.get_session = MagicMock()
    fake_dlmgr.get_session().status().dht_nodes = 1000
    # If the session has enough peers, it should finish instantly
    await fake_dlmgr._check_dht_ready()


async def test_start_download_from_magnet_no_name(fake_dlmgr: DownloadManager):
    # Test whether a download is started with `Unknown name` name when the magnet has no name
    magnet = f'magnet:?xt=urn:btih:{"A" * 40}'
    download = await fake_dlmgr.start_download_from_uri(magnet)
    assert download.tdef.get_name() == b'Unknown name'


async def test_start_download_from_magnet_with_name(fake_dlmgr: DownloadManager):
    # Test whether a download is started with `Unknown name` name when the magnet has no name
    magnet = f'magnet:?xt=urn:btih:{"A" * 40}&dn=AwesomeTorrent'
    download = await fake_dlmgr.start_download_from_uri(magnet)
    assert download.tdef.get_name() == b'AwesomeTorrent'


def test_update_trackers(fake_dlmgr) -> None:
    fake_download, _ = create_fake_download_and_state()
    fake_dlmgr.downloads[fake_download.infohash] = fake_download
    fake_metainfo = {b"info": {b"name": b"test_download"}}
    fake_download.get_def().metainfo = fake_metainfo

    fake_tracker1 = "127.0.0.1/test-announce1"

    fake_dlmgr.update_trackers(fake_download.infohash, [fake_tracker1])

    assert fake_metainfo["announce"] == fake_tracker1
    assert "announce-list" not in fake_metainfo


def test_update_trackers_list(fake_dlmgr) -> None:
    fake_download, _ = create_fake_download_and_state()
    fake_dlmgr.downloads[fake_download.infohash] = fake_download
    fake_metainfo = {b"info": {b"name": b"test_download"}}
    fake_download.get_def().metainfo = fake_metainfo

    fake_tracker1 = "127.0.0.1/test-announce1"
    fake_tracker2 = "127.0.0.1/test-announce2"

    fake_dlmgr.update_trackers(fake_download.infohash, [fake_tracker1, fake_tracker2])

    assert "announce" not in fake_metainfo

    # The order of the results changes between OSes, so this is needed
    tracker_list = fake_metainfo["announce-list"]
    actual_trackers = set(itertools.chain.from_iterable(tracker_list))
    assert actual_trackers == {fake_tracker1, fake_tracker2}


def test_update_trackers_list_append(fake_dlmgr) -> None:
    fake_download, _ = create_fake_download_and_state()
    fake_dlmgr.downloads[fake_download.infohash] = fake_download
    fake_metainfo = {b"info": {b"name": b"test_download"}}
    fake_download.get_def().metainfo = fake_metainfo

    fake_tracker1 = "127.0.0.1/test-announce1"
    fake_tracker2 = "127.0.0.1/test-announce2"

    fake_dlmgr.update_trackers(fake_download.infohash, [fake_tracker1])
    fake_download.get_def().get_tracker = Mock(return_value=fake_tracker1)
    fake_dlmgr.update_trackers(fake_download.infohash, [fake_tracker2])

    assert fake_metainfo["announce"] == fake_tracker1

    # The order of the results changes between OSes, so this is needed

    tracker_list = fake_metainfo["announce-list"]
    actual_trackers = set(itertools.chain.from_iterable(tracker_list))
    assert actual_trackers == {fake_tracker1, fake_tracker2}


def test_set_proxy_settings_invalid_port(fake_dlmgr):
    # Test setting the proxy settings for an invalid port number. In this case port and host should not be set.
    session = Mock()
    proxy_type = 2

    fake_dlmgr.set_proxy_settings(session, proxy_type, ('host name', 'invalid port'))

    settings, = session.method_calls[-1].args
    assert 'proxy_port' not in settings
    assert 'proxy_hostname' not in settings
    assert settings['proxy_type'] == proxy_type


def test_set_proxy_defaults(fake_dlmgr):
    # Test setting the proxy settings with default values
    session = Mock()
    proxy_type = 2

    fake_dlmgr.set_proxy_settings(session, proxy_type)
    settings, = session.method_calls[-1].args
    assert 'proxy_port' not in settings
    assert 'proxy_hostname' not in settings
    assert settings['proxy_type'] == proxy_type


def test_set_proxy_corner_case(fake_dlmgr):
    # Test setting the proxy settings with None values
    session = Mock()

    fake_dlmgr._logger = Mock()
    fake_dlmgr.set_proxy_settings(session, 2)
    fake_dlmgr._logger.exception.assert_not_called()
    settings, = session.method_calls[-1].args
    assert settings['proxy_type'] == 2
    assert 'proxy_hostname' not in settings
    assert 'proxy_port' not in settings
    assert 'proxy_username' not in settings
    assert 'proxy_password' not in settings

    fake_dlmgr._logger.exception.reset_mock()
    fake_dlmgr.set_proxy_settings(session, 2, (None, None))
    fake_dlmgr._logger.exception.assert_called()
    settings, = session.method_calls[-1].args
    assert settings['proxy_type'] == 2
    assert 'proxy_port' not in settings

    fake_dlmgr._logger.exception.reset_mock()
    fake_dlmgr.set_proxy_settings(session, 3, (None,))
    fake_dlmgr._logger.exception.assert_called()
    settings, = session.method_calls[-1].args
    assert settings['proxy_type'] == 3
    assert 'proxy_port' not in settings

    fake_dlmgr._logger.exception.reset_mock()
    fake_dlmgr.set_proxy_settings(session, 3, (None, 123))
    fake_dlmgr._logger.exception.assert_called()
    settings, = session.method_calls[-1].args
    assert settings['proxy_type'] == 3
    assert 'proxy_port' not in settings

    fake_dlmgr._logger.exception.reset_mock()
    fake_dlmgr.set_proxy_settings(session, 3, (None, 123), ('name', None))
    fake_dlmgr._logger.exception.assert_called()
    settings, = session.method_calls[-1].args
    assert settings['proxy_type'] == 3
    assert 'proxy_port' not in settings
    assert 'proxy_username' not in settings
