import asyncio
import os
from asyncio import Future, ensure_future, sleep
from binascii import hexlify
from contextlib import AbstractContextManager, ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import libtorrent
from aiohttp import ClientResponseError
from ipv8.test.base import TestBase
from ipv8.util import succeed

import tribler
from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_manager import DownloadManager, MetainfoLookup
from tribler.core.libtorrent.download_manager.download_state import DownloadState
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.notifier import Notifier
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT, FakeTDef
from tribler.test_unit.mocks import MockTriblerConfigManager


class TestDownloadManager(TestBase):
    """
    Tests for the DownloadManager class.
    """

    MOCK_CONF_PATH = "01" * 20 + ".conf"
    BASE_DLCONFIG = tribler.core.libtorrent.download_manager.download_manager.DownloadConfig

    def setUp(self) -> None:
        """
        Create a download manager.
        """
        super().setUp()
        self.manager = DownloadManager(MockTriblerConfigManager(), Notifier(), Mock())
        for i in range(4):
            fut = Future()
            fut.set_result(Mock(status=Mock(dht_nodes=0), get_torrents=Mock(return_value=[])))
            self.manager.ltsessions[i] = fut
        self.manager.set_download_states_callback(self.manager.sesscb_states_callback)
        # Just in case some patch fails, point this to a non-existent directory
        self.manager.config.set("libtorrent/download_defaults/saveas", "__TEST__")

    async def tearDown(self) -> None:
        """
        Shut down the download manager.
        """
        await self.manager.shutdown_task_manager()
        await super().tearDown()

    def create_mock_download_config(self) -> DownloadConfig:
        """
        Create a mocked DownloadConfig.
        """
        config = DownloadConfig(DownloadConfig.get_parser())
        config.set_dest_dir(Path(""))
        config.write = Mock(return_value=None)
        return config

    def _patch_dlconfig(self, download_config: DownloadConfig, err: Exception | None = None) -> AbstractContextManager:
        main = ExitStack()
        main.enter_context(patch.object(self.BASE_DLCONFIG, "from_defaults", Mock(return_value=download_config)))
        main.enter_context(patch.object(self.BASE_DLCONFIG, "read", Mock(return_value=None, side_effect=err)))
        return main

    def atp_from_dict(self, tinfo_dict: "libtorrent._Entry") -> libtorrent.add_torrent_params:
        """
        Create an add_torrent_params object with correct info hash.
        """
        atp = libtorrent.add_torrent_params()
        atp.ti = libtorrent.torrent_info(tinfo_dict)
        atp.info_hash = atp.ti.info_hash()
        atp.info_hashes = atp.ti.info_hashes()
        return atp

    async def test_get_metainfo_valid_metadata(self) -> None:
        """
        Testing if the metainfo is retrieved when the handle has valid metadata immediately.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))
        download.future_metainfo = succeed(None)
        download.get_state = Mock(return_value=Mock(get_num_seeds_peers=Mock(return_value=(42, 7))))
        config = self.create_mock_download_config()

        with patch.object(self.manager, "start_download", AsyncMock(return_value=download)), \
                 patch.object(self.manager, "remove_download", AsyncMock()), \
                 self._patch_dlconfig(config):
            metainfo = await self.manager.get_metainfo(download.tdef.infohash)
            self.assertEqual(7, metainfo.get("leechers"))
            self.assertEqual(42, metainfo.get("seeders"))
            self.assertEqual(download.tdef.infohash, metainfo["tdef"].infohash)

    async def test_get_metainfo_add_fail(self) -> None:
        """
        Test if invalid metainfo leads to a return value of None.
        """
        config = DownloadConfig(DownloadConfig.get_parser())

        with patch.object(self.manager, "start_download", AsyncMock(side_effect=TypeError)), \
                self._patch_dlconfig(config):
            self.assertIsNone(await self.manager.get_metainfo(b"\x00" * 20))

    async def test_get_metainfo_duplicate_request(self) -> None:
        """
        Test if the same request is returned when invoking get_metainfo twice with the same infohash.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=DownloadConfig(DownloadConfig.get_parser()))
        download.handle = Mock(is_valid=Mock(return_value=True))
        download.future_metainfo = succeed(None)
        config = DownloadConfig(DownloadConfig.get_parser())

        with patch.object(self.manager, "start_download", AsyncMock(return_value=download)), \
                patch.object(self.manager, "remove_download", AsyncMock()), \
                self._patch_dlconfig(config):
            results = await asyncio.gather(self.manager.get_metainfo(download.tdef.infohash),
                                           self.manager.get_metainfo(download.tdef.infohash))

        self.assertDictEqual(*results)

    async def test_get_metainfo_cache(self) -> None:
        """
        Testing if cached metainfo is returned, if available.
        """
        atp = libtorrent.add_torrent_params()
        atp.name = "test"
        self.manager.metainfo_cache[b"a" * 20] = {
            "tdef": TorrentDef(atp),
            "time": 0,
            "seeders": 1,
            "leechers": 2
        }

        self.assertEqual("test", (await self.manager.get_metainfo(b"a" * 20))["tdef"].name)

    async def test_get_metainfo_with_already_added_torrent(self) -> None:
        """
        Test if metainfo can be fetched for a torrent which is already in session.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=DownloadConfig(DownloadConfig.get_parser()))
        download.handle = Mock(is_valid=Mock(return_value=True))
        download.future_metainfo = succeed(None)
        self.manager.downloads[download.tdef.infohash] = download

        metainfo = await self.manager.get_metainfo(download.tdef.infohash)

        self.assertEqual(download.tdef, metainfo["tdef"])

    async def test_start_download_while_getting_metainfo(self) -> None:
        """
        Test if a torrent can be added while a metainfo request is running.
        """
        info_download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                                 checkpoint_disabled=True, config=self.create_mock_download_config())
        info_download.handle = Mock(is_valid=Mock(return_value=True))
        self.manager.downloads[info_download.tdef.infohash] = info_download
        self.manager.metainfo_requests[info_download.tdef.infohash] = MetainfoLookup(info_download, 1)
        tdef = FakeTDef(info_hash=info_download.tdef.infohash,
                        url=f"magnet:?xt=urn:btih:{hexlify(info_download.tdef.infohash).decode()}&")

        with patch.object(self.manager, "remove_download", AsyncMock()):
            download = await self.manager.start_download(tdef=tdef, config=info_download.config,
                                                         checkpoint_disabled=True)

        self.assertNotEqual(info_download, download)

    async def test_start_download(self) -> None:
        """
        Test if a torrent can be added to the download manager.
        """
        infohashes = libtorrent.info_hash_t(libtorrent.sha1_hash(b"\x01" * 20))
        mock_handle = Mock(info_hashes=Mock(return_value=infohashes), is_valid=Mock(return_value=True),
                           flags=Mock(return_value=0))
        mock_alert = type("add_torrent_alert", (object,), {"handle": mock_handle,
                                                           "error": Mock(value=Mock(return_value=None)),
                                                           "category": MagicMock(return_value=None),
                                                           "params": libtorrent.add_torrent_params()})
        mock_alert.params.info_hashes = infohashes
        self.manager.ltsessions[0].result().async_add_torrent = lambda _: self.manager.process_alert(mock_alert())

        with patch.object(self.manager, "remove_download", AsyncMock()):
            download = await self.manager.start_download(tdef=FakeTDef(),
                                                         config=self.create_mock_download_config(),
                                                         checkpoint_disabled=True)

        self.assertEqual(mock_handle, await download.get_handle())

    async def test_start_handle_wait_for_dht_timeout(self) -> None:
        """
        Test if start handle waits no longer than the set timeout for the DHT to be ready.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))
        self.manager.dht_ready_task = Future()
        self.manager.dht_readiness_timeout = 0.001

        self.assertIsNone(await self.manager.start_handle(download, Mock(save_path="", flags=0)))

    async def test_start_handle_wait_for_dht(self) -> None:
        """
        Test if start handle waits for the DHT to be ready.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))
        self.manager.dht_ready_task = Future()
        self.manager.dht_readiness_timeout = 10

        task = ensure_future(self.manager.start_handle(download, Mock(save_path="")))
        self.manager.dht_ready_task.set_result(None)
        await task

        self.assertTrue(task.done())

    async def test_start_download_existing_handle(self) -> None:
        """
        Test if torrents can be added when there is a pre-existing handle.
        """
        infohashes = libtorrent.info_hash_t(libtorrent.sha1_hash(b"\x01" * 20))
        mock_handle = Mock(info_hashes=Mock(return_value=infohashes), is_valid=Mock(return_value=True),
                           flags=Mock(return_value=0))
        self.manager.ltsessions[0].result().get_torrents = Mock(return_value=[mock_handle])
        download = await self.manager.start_download(tdef=FakeTDef(),
                                                     config=self.create_mock_download_config(),
                                                     checkpoint_disabled=True)

        handle = await download.get_handle()

        self.assertEqual(mock_handle, handle)

    async def test_start_download_existing_download(self) -> None:
        """
        Test if torrents can be added when there is a pre-existing download.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        self.manager.downloads[download.tdef.infohash] = download

        value = await self.manager.start_download(tdef=FakeTDef(info_hash=download.tdef.infohash),
                                                  config=self.create_mock_download_config(),
                                                  checkpoint_disabled=True)

        self.assertEqual(download, value)

    async def test_start_download_no_ti_url(self) -> None:
        """
        Test if a ValueError is raised if we try to add a torrent without infohash or url.
        """
        config = DownloadConfig(DownloadConfig.get_parser())

        with self.assertRaises(ValueError), self._patch_dlconfig(config):
            await self.manager.start_download()

    def test_remove_unregistered_torrent(self) -> None:
        """
        Test if torrents which aren't known are succesfully removed.
        """
        mock_handle = Mock(is_valid=lambda: False)
        alert = type("torrent_removed_alert", (object,), {"handle": mock_handle,
                                                          "info_hash": Mock(to_bytes=Mock(return_value=b"00" * 20))})
        self.manager.process_alert(alert())

        self.assertNotIn(b"\x00" * 20, self.manager.downloads)

    def test_set_proxy_settings(self) -> None:
        """
        Test if the proxy settings can be set.
        """
        self.manager.set_proxy_settings(self.manager.get_session(0).result(), 0, ("a", "1234"), ("abc", "def"))

        self.assertEqual(call({"proxy_type": 0, "proxy_hostnames": True, "proxy_peer_connections": True,
                               "proxy_hostname": "a", "proxy_port": 1234, "proxy_username": "abc",
                               "proxy_password": "def"}), self.manager.ltsessions[0].result().apply_settings.call_args)

    async def test_load_checkpoint_no_metainfo(self) -> None:
        """
        Test if no checkpoint can be loaded from a file with no metainfo.
        """
        with self._patch_dlconfig(self.create_mock_download_config().config):
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertFalse(value)

    async def test_load_checkpoint_empty_metainfo(self) -> None:
        """
        Test if no checkpoint can be loaded from a file with empty metainfo.
        """
        download_config = self.create_mock_download_config()
        download_config.set_engineresumedata(libtorrent.add_torrent_params())
        with self._patch_dlconfig(download_config), patch("os.remove") as remove_mock:
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertFalse(value)
        self.assertEqual(call(self.MOCK_CONF_PATH), remove_mock.call_args)

    async def test_load_checkpoint_bad_url(self) -> None:
        """
        Test if no checkpoint can be loaded from a file with a bad url.
        """
        download_config = self.create_mock_download_config()
        atp = self.atp_from_dict({b"url": b"\x80", b"info": {
            b"name": b"torrent name",
            b"files": [{b"path": [b"a.txt"], b"length": 123}],
            b"piece length": 128,
            b"pieces": b"\x00" * 20
        }})
        atp.url = b"\x80"
        download_config.set_engineresumedata(atp)
        with self._patch_dlconfig(download_config):
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertFalse(value)

    async def test_load_checkpoint(self) -> None:
        """
        Test if a checkpoint can be loaded.
        """
        download_config = self.create_mock_download_config()
        download_config.set_engineresumedata(self.atp_from_dict({b"info": {
            b"name": b"torrent name",
            b"files": [{b"path": [b"a.txt"], b"length": 123}],
            b"piece length": 128,
            b"pieces": b"\x00" * 20
        }}))
        download_config.set_dest_dir(Path(__file__).absolute().parent)  # noqa: ASYNC240
        with self._patch_dlconfig(download_config), patch.object(self.manager, "start_download", AsyncMock()):
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertTrue(value)
        self.assertTrue(download_config.get_engineresumedata().info_hashes.has_v1())
        self.assertFalse(download_config.get_engineresumedata().info_hashes.has_v2())

    async def test_load_checkpoint_hybrid(self) -> None:
        """
        Test if a hybrid torrent checkpoint can be loaded.
        """
        download_config = self.create_mock_download_config()
        download_config.set_engineresumedata(self.atp_from_dict({
            b"info": {
                b"name": b"torrent name",
                b"meta version": 2,
                b"files": [{b"path": [b"a.txt"], b"length": 123},
                           {b"path": [b".pad", b"524165"], b"length": 524165, b"attr": b"p"}],
                b"file tree": {
                    b"a.txt": {
                        b"": {
                            b"length": 123,
                            b"pieces root": b"\x01" * 32
                        }
                    }
                },
                b"piece length": 524288,
                b"pieces": b"\x01" * 20,
            },
            b"piece layers": [b"\x01" * 32]
        }))
        download_config.set_dest_dir(Path(__file__).absolute().parent)  # noqa: ASYNC240
        with self._patch_dlconfig(download_config), patch.object(self.manager, "start_download", AsyncMock()):
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertTrue(value)
        self.assertTrue(download_config.get_engineresumedata().info_hashes.has_v1())
        self.assertTrue(download_config.get_engineresumedata().info_hashes.has_v2())

    async def test_load_checkpoint_v2(self) -> None:
        """
        Test if a v2 torrent checkpoint can be loaded.
        """
        download_config = self.create_mock_download_config()
        download_config.set_engineresumedata(self.atp_from_dict({
            b"info": {
                b"name": b"torrent name",
                b"meta version": 2,
                b"file tree": {
                    b"a.txt": {
                        b"": {
                            b"length": 123,
                            b"pieces root": b"\x01" * 32
                        }
                    }
                },
                b"piece length": 524288,
            },
            b"piece layers": [b"\x01" * 32]
        }))
        download_config.set_dest_dir(Path(__file__).absolute().parent)  # noqa: ASYNC240
        with self._patch_dlconfig(download_config), patch.object(self.manager, "start_download", AsyncMock()):
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertTrue(value)
        self.assertFalse(download_config.get_engineresumedata().info_hashes.has_v1())
        self.assertTrue(download_config.get_engineresumedata().info_hashes.has_v2())

    async def test_load_checkpoint_zeroed_engineresumedata(self) -> None:
        """
        Test if no checkpoint is restored from uninitialized engineresumedata.
        """
        download_config = self.create_mock_download_config()
        atp = libtorrent.add_torrent_params()
        atp.name = "torrent name"
        atp.info_hashes = libtorrent.info_hash_t(libtorrent.sha1_hash(b"\x01" * 20))
        download_config.set_engineresumedata(atp)
        download_config.set_dest_dir(Path(__file__).absolute().parent)  # noqa: ASYNC240
        self.manager.start_download = AsyncMock()
        with self._patch_dlconfig(download_config):
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertTrue(value)
        self.assertEqual(b"\x01" * 20, self.manager.start_download.call_args.kwargs["tdef"].infohash)

    async def test_load_checkpoint_file_not_found(self) -> None:
        """
        Test if no checkpoint can be loaded if a specified file is not found.
        """
        err = OSError(f'Config file not found: "{self.MOCK_CONF_PATH}".')
        with self._patch_dlconfig(self.create_mock_download_config().config, err):
            value = await self.manager.load_checkpoint(self.MOCK_CONF_PATH)

        self.assertFalse(value)

    async def test_download_manager_start(self) -> None:
        """
        Test if all (zero) checkpoints are loaded when starting without downloads.
        """
        self.manager.start()
        await sleep(0)

        await self.manager.get_task("start")

        self.assertTrue(self.manager.all_checkpoints_are_loaded)

    async def test_readd_download_safe_seeding(self) -> None:
        """
        Test if a download is re-added when doing safe seeding.

        Safe seeding should be turned off and the number of hops should be retrieved from the defaults.
        """
        config = self.create_mock_download_config()
        config.set_safe_seeding(True)
        download = Download(FakeTDef(), self.manager, checkpoint_disabled=True,
                            config=config)
        download.futures["save_resume_data"] = succeed(True)
        download_state = DownloadState(download, Mock(state=4, paused=False, moving_storage=False, error=None), None)
        self.manager.downloads = {b"\x01" * 20: download}
        self.manager.config.set("libtorrent/download_defaults/number_hops", 42)

        with patch.object(self.manager, "start_download", AsyncMock(return_value=download)) as start_download, \
                patch.object(self.manager, "remove_download", AsyncMock()) as remove_download:
            future = ensure_future(self.manager.sesscb_states_callback([download_state]))
            while "save_resume_data_alert" not in download.futures:
                await sleep(0)
            download.process_alert(Mock(), "save_resume_data_alert")
            await future

        self.assertEqual(call(download), remove_download.call_args)
        self.assertEqual(download.tdef, start_download.call_args.kwargs["tdef"])
        self.assertFalse(start_download.call_args.kwargs["config"].get_safe_seeding())
        self.assertEqual(42, start_download.call_args.kwargs["config"].get_hops())

    def test_get_downloads_by_name(self) -> None:
        """
        Test if downloads can be retrieved by name.
        """
        download = Download(FakeTDef(), self.manager, checkpoint_disabled=True,
                            config=DownloadConfig(DownloadConfig.get_parser()))
        self.manager.downloads = {b"\x01" * 20: download}

        self.assertEqual([download], self.manager.get_downloads_by_name("test"))
        self.assertEqual([], self.manager.get_downloads_by_name("bla"))

    async def test_start_download_from_url(self) -> None:
        """
        Test if torrents can be loaded from a URL.
        """
        with (patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                         get_url=AsyncMock(return_value=TORRENT_WITH_DIRS_CONTENT),
                         unshorten=lambda x: succeed((x, True))),
              patch.object(self.manager, "start_download", AsyncMock(return_value=Mock()))):
            await self.manager.start_download_from_uri("http://127.0.0.1:1234/ubuntu.torrent")
            tdef = self.manager.start_download.call_args.kwargs["tdef"]

        self.assertEqual(b"\xb3\xba\x19\xc93\xda\x95\x84k\xfd\xf7Z\xd0\x8a\x94\x9cl\xea\xc7\xbc", tdef.infohash)

    async def test_start_download_from_url_404(self) -> None:
        """
        Test if 404 errors are not caught.
        """
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        get_url=AsyncMock(side_effect=ClientResponseError(None, None, status=404)),
                        unshorten=lambda x: succeed((x, True))), self.assertRaises(ClientResponseError):
            await self.manager.start_download_from_uri("http://127.0.0.1:1234/ubuntu.torrent")

    async def test_start_download_from_magnet_no_name(self) -> None:
        """
        Test if a download is started with `Unknown name` name when the magnet has no name.
        """
        magnet = f'magnet:?xt=urn:btih:{"A" * 40}'

        with (patch.object(self.manager, "start_download", AsyncMock(return_value=Mock(get_handle=AsyncMock())))
              as start_download):
            await self.manager.start_download_from_uri(magnet)

        self.assertEqual("Unknown name", start_download.call_args.kwargs["tdef"].name)

    async def test_start_download_from_magnet_with_name(self) -> None:
        """
        Test if a download is started with `Unknown name` name when the magnet has no name.
        """
        magnet = f'magnet:?xt=urn:btih:{"A" * 40}&dn=AwesomeTorrent'

        with (patch.object(self.manager, "start_download", AsyncMock(return_value=Mock(get_handle=AsyncMock())))
              as start_download):
            await self.manager.start_download_from_uri(magnet)

        self.assertEqual("AwesomeTorrent", start_download.call_args.kwargs["tdef"].name)

    async def test_start_download_from_magnet_with_all_extras(self) -> None:
        """
        Test if a download is started with all six supported extras in the URI.

        NOTE: libtorrent only uses the first (x.pe) peer and ignores additional initial peers.
        """
        magnet = (f'magnet:?xt=urn:btih:{"A" * 40}'  # 1. [required] infohash
                  "&dn=AwesomeTorrent"  # 2. name
                  "&tr=tracker1&tr=tracker2"  # 3. tracker list
                  "&ws=http%3A%2F%2Flocalhost%2Ffile&ws=http%3A%2F%2Flocalhost%2Fcdn"  # 4. initial URL seeds
                  "&so=0,2,4,6-8"  # 5. selected files
                  "&x.pe=1.2.3.4:5&x.pe=6.7.8.9:0")  # 6. initial peers (see NOTE)
        config = DownloadConfig(DownloadConfig.get_parser())
        config.set_selected_files([])
        handle = Mock(is_valid=Mock(return_value=True))
        download = Download(Mock(infohash=b"a" * 20), self.manager, config, checkpoint_disabled=True)
        download.handle = handle

        with patch.object(self.manager, "start_download", AsyncMock(return_value=download)) as start_download:
            await self.manager.start_download_from_uri(magnet, config)
            await sleep(0)  # Schedule handler awaiter.
            await sleep(0)  # Run callback after handle is available.

        self.assertEqual("AwesomeTorrent", start_download.call_args.kwargs["tdef"].name)
        self.assertEqual(["tracker1", "tracker2"], start_download.call_args.kwargs["tdef"].atp.trackers)
        self.assertEqual(["http://localhost/file", "http://localhost/cdn"],
                         start_download.call_args.kwargs["tdef"].atp.url_seeds)
        self.assertEqual([0, 2, 4, 6, 7, 8], config.get_selected_files())
        self.assertEqual([("1.2.3.4", 5)], start_download.call_args.kwargs["tdef"].atp.peers)  # See NOTE

    async def test_start_download_from_magnet_keep_preselected(self) -> None:
        """
        Test if a magnet link's selected files do not overwrite the user's selected files.
        """
        magnet = f'magnet:?xt=urn:btih:{"A" * 40}&so=0-8'
        config = DownloadConfig(DownloadConfig.get_parser())
        config.set_selected_files([0, 1, 2])
        handle = Mock(is_valid=Mock(return_value=True))
        download = Download(Mock(infohash=b"a" * 20), self.manager, config,
                            checkpoint_disabled=True)
        download.handle = handle

        with patch.object(self.manager, "start_download", AsyncMock(return_value=download)):
            await self.manager.start_download_from_uri(magnet, config)
        await sleep(0)  # Schedule handler awaiter.
        await sleep(0)  # Run callback after handle is available.

        self.assertEqual([0, 1, 2], config.get_selected_files())

    def test_update_trackers(self) -> None:
        """
        Test if trackers can be updated for an existing download.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        self.manager.downloads[download.tdef.infohash] = download

        self.manager.update_trackers(download.tdef.infohash, ["127.0.0.1/test-announce1"])

        self.assertEqual(download.tdef.atp.trackers, ["127.0.0.1/test-announce1"])

    def test_update_trackers_list(self) -> None:
        """
        Test if multiple trackers are correctly added as an announce list instead of a the singular announce.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        self.manager.downloads[download.tdef.infohash] = download

        self.manager.update_trackers(download.tdef.infohash, [f"127.0.0.1/test-announce{i}" for i in range(2)])

        self.assertEqual(sorted(download.tdef.atp.trackers),
                         sorted(["127.0.0.1/test-announce0", "127.0.0.1/test-announce1"]))

    def test_update_trackers_list_append(self) -> None:
        """
        Test if trackers can be updated in sequence.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        self.manager.downloads[download.tdef.infohash] = download

        self.manager.update_trackers(download.tdef.infohash, ["127.0.0.1/test-announce0"])
        self.manager.update_trackers(download.tdef.infohash, ["127.0.0.1/test-announce1"])

        self.assertEqual(download.tdef.atp.trackers, ["127.0.0.1/test-announce0", "127.0.0.1/test-announce1"])

    def test_resume_from_legacy_complete(self) -> None:
        """
        Check if we can load legacy format with complete torrent info.

        Deprecated functionality, remove later.
        """
        atp = self.manager.resume_from_legacy("ZDg6YW5ub3VuY2UwOjEzOmFubm91bmNlLWxpc3RsZTc6Y29tbWVudDA6MTA6"
                                              "Y3JlYXRlZCBieTA6MTM6Y3JlYXRpb24gZGF0ZWkwZTg6ZW5jb2Rpbmc1OlVU"
                                              "Ri04OTpodHRwc2VlZHNsZTQ6aW5mb2Q2Omxlbmd0aGkzNTE0N2U0Om5hbWUx"
                                              "MTpncGwtMy4wLnR4dDEyOnBpZWNlIGxlbmd0aGkzMjc2OGU2OnBpZWNlczQw"
                                              "Ok5AiJjjmd4Pmm396qLN9JJN54SOmqVGlilmIiYdASJg1UiK5X4C/Hc3OnBy"
                                              "aXZhdGVpMGVlNTpub2Rlc2xlNzp1cmxsaXN0bGVl",
                                              "1f739d935676111cfff4b4693e3816e664797050.conf")

        self.assertEqual(352440, atp.flags)
        self.assertEqual(b"\x1fs\x9d\x93Vv\x11\x1c\xff\xf4\xb4i>8\x16\xe6dypP", atp.info_hashes.v1.to_bytes())
        self.assertEqual("gpl-3.0.txt", atp.ti.name())

    def test_resume_from_legacy_no_info(self) -> None:
        """
        Check if we can load legacy format without torrent info.

        Deprecated functionality, remove later.
        """
        atp = self.manager.resume_from_legacy("ZDg6YW5ub3VuY2UwOjEzOmFubm91bmNlLWxpc3RsZTc6Y29tbWVudDA6MTA6"
                                              "Y3JlYXRlZCBieTA6MTM6Y3JlYXRpb24gZGF0ZWkwZTg6ZW5jb2Rpbmc1OlVU"
                                              "Ri04OTpodHRwc2VlZHNsZTQ6bmFtZTExOmdwbC0zLjAudHh0NTpub2Rlc2xl"
                                              "Nzp1cmxsaXN0bGVl",
                                              "1f739d935676111cfff4b4693e3816e664797050.conf")

        self.assertEqual(b"\x1fs\x9d\x93Vv\x11\x1c\xff\xf4\xb4i>8\x16\xe6dypP", atp.info_hashes.v1.to_bytes())
        self.assertEqual("gpl-3.0.txt", atp.name)
        self.assertIsNone(atp.ti)

    def test_resume_from_legacy_pre_start(self) -> None:
        """
        Check if we can load legacy format that has not started yet.

        Deprecated functionality, remove later.
        """
        atp = self.manager.resume_from_legacy("ZDg6aW5mb2hhc2g0MDoxZjczOWQ5MzU2NzYxMTFjZmZmNGI0NjkzZTM4MTZl"
                                              "NjY0Nzk3MDUwNDpuYW1lMTE6Z3BsLTMuMC50eHRl",
                                              "1f739d935676111cfff4b4693e3816e664797050.conf")

        self.assertEqual(b"\x1fs\x9d\x93Vv\x11\x1c\xff\xf4\xb4i>8\x16\xe6dypP", atp.info_hashes.v1.to_bytes())
        self.assertEqual("gpl-3.0.txt", atp.name)
        self.assertIsNone(atp.ti)

    def test_load_legacy_checkpoint_full_legacy(self) -> None:
        """
        Check if missing resume data treats the checkpoint as fully legacy.

        Deprecated functionality, remove later.
        """
        config = self.create_mock_download_config()
        config.config["state"]["metainfo"] = ("ZDg6aW5mb2hhc2g0MDoxZjczOWQ5MzU2NzYxMTFjZmZmNGI0NjkzZTM4MTZl"
                                              "NjY0Nzk3MDUwNDpuYW1lMTE6Z3BsLTMuMC50eHRl")
        atp = self.manager.load_legacy_checkpoint(None, config, "dir/1f739d935676111cfff4b4693e3816e664797050.conf")

        self.assertEqual(b"\x1fs\x9d\x93Vv\x11\x1c\xff\xf4\xb4i>8\x16\xe6dypP", atp.info_hashes.v1.to_bytes())
        self.assertEqual("gpl-3.0.txt", atp.name)
        self.assertIsNone(atp.ti)

    def test_load_legacy_checkpoint_enrich(self) -> None:
        """
        Check if resume data with missing torrent info fetches its info from legacy metainfo.

        Deprecated functionality, remove later.
        """
        existing = libtorrent.add_torrent_params()
        existing.name = "test name"
        existing.info_hashes = libtorrent.info_hash_t(libtorrent.sha1_hash(b"\x01" * 20))
        config = self.create_mock_download_config()
        config.config["state"]["metainfo"] = ("ZDg6YW5ub3VuY2UwOjEzOmFubm91bmNlLWxpc3RsZTc6Y29tbWVudDA6MTA6"
                                              "Y3JlYXRlZCBieTA6MTM6Y3JlYXRpb24gZGF0ZWkwZTg6ZW5jb2Rpbmc1OlVU"
                                              "Ri04OTpodHRwc2VlZHNsZTQ6aW5mb2Q2Omxlbmd0aGkzNTE0N2U0Om5hbWUx"
                                              "MTpncGwtMy4wLnR4dDEyOnBpZWNlIGxlbmd0aGkzMjc2OGU2OnBpZWNlczQw"
                                              "Ok5AiJjjmd4Pmm396qLN9JJN54SOmqVGlilmIiYdASJg1UiK5X4C/Hc3OnBy"
                                              "aXZhdGVpMGVlNTpub2Rlc2xlNzp1cmxsaXN0bGVl")
        atp = self.manager.load_legacy_checkpoint(existing, config, "dir/1f739d935676111cfff4b4693e3816e664797050.conf")

        self.assertEqual(b"\x01" * 20, atp.info_hashes.v1.to_bytes())
        self.assertEqual("test name", atp.name)
        self.assertIsNotNone(atp.ti)
        self.assertEqual(b"\x1fs\x9d\x93Vv\x11\x1c\xff\xf4\xb4i>8\x16\xe6dypP", atp.ti.info_hashes().v1.to_bytes())
        self.assertEqual("gpl-3.0.txt", atp.ti.name())

    def test_clear_orphaned_parts_empty(self) -> None:
        """
        Check if nothing is getting removed if there are no files.
        """
        with patch("os.listdir", Mock(return_value=[])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertIsNone(remove_mock.call_args)

    def test_clear_orphaned_parts_no_parts(self) -> None:
        """
        Check if nothing is getting removed if there are no parts files.
        """
        with patch("os.listdir", Mock(return_value=["hello.txt"])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertIsNone(remove_mock.call_args)

    def test_clear_orphaned_parts_bad_len_parts(self) -> None:
        """
        Check if nothing is getting removed if there are only odd-length parts files.
        """
        filename = ".1234.parts"
        with patch("os.listdir", Mock(return_value=[filename])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertIsNone(remove_mock.call_args)

    def test_clear_orphaned_parts_bad_hex_parts(self) -> None:
        """
        Check if nothing is getting removed if there are only non-hex parts files.
        """
        filename = ".123456789G1234567890.parts"
        with patch("os.listdir", Mock(return_value=[filename])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertIsNone(remove_mock.call_args)

    def test_clear_orphaned_parts_sha1_parts_orphaned(self) -> None:
        """
        Check if SHA-1 parts are getting removed.
        """
        filename = "." + "01" * 20 + ".parts"
        with patch("os.listdir", Mock(return_value=[filename])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertEqual(call(os.path.join(self.manager.config.get("libtorrent/download_defaults/saveas"), filename)),
                         remove_mock.call_args)

    def test_clear_orphaned_parts_sha256_parts_orphaned(self) -> None:
        """
        Check if SHA-1 parts are getting removed.
        """
        filename = "." + "01" * 32 + ".parts"
        with patch("os.listdir", Mock(return_value=[filename])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertEqual(call(os.path.join(self.manager.config.get("libtorrent/download_defaults/saveas"), filename)),
                         remove_mock.call_args)

    def test_clear_orphaned_parts_sha1_parts_nonorphaned(self) -> None:
        """
        Check if SHA-1 parts that are used for downloads are not getting removed.
        """
        filename = "." + "01" * 20 + ".parts"
        self.manager.downloads[b"\01" * 20] = Mock()
        with patch("os.listdir", Mock(return_value=[filename])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertIsNone(remove_mock.call_args)

    def test_clear_orphaned_parts_sha256_parts_nonorphaned(self) -> None:
        """
        Check if SHA-1 parts that are used for downloads are not getting removed.
        """
        filename = "." + "01" * 32 + ".parts"
        self.manager.downloads[b"\01" * 32] = Mock()
        with patch("os.listdir", Mock(return_value=[filename])), patch("os.remove", Mock()) as remove_mock:
            self.manager.clear_orphaned_parts()

        self.assertIsNone(remove_mock.call_args)
