import asyncio
from asyncio import Future, ensure_future, sleep
from binascii import hexlify
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import libtorrent
from configobj import ConfigObj
from configobj.validate import Validator, VdtParamError
from ipv8.test.base import TestBase
from ipv8.util import succeed

import tribler
from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.download_manager.download_manager import DownloadManager, MetainfoLookup
from tribler.core.libtorrent.download_manager.download_state import DownloadState
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.notifier import Notifier
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT
from tribler.test_unit.mocks import MockTriblerConfigManager


class TestDownloadManager(TestBase):
    """
    Tests for the DownloadManager class.
    """

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
        defaults = ConfigObj(StringIO(SPEC_CONTENT))
        conf = ConfigObj()
        conf.configspec = defaults
        conf.validate(Validator())
        config = DownloadConfig(conf)
        config.set_dest_dir(Path(""))
        return config

    async def test_get_metainfo_valid_metadata(self) -> None:
        """
        Testing if the metainfo is retrieved when the handle has valid metadata immediately.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))
        download.get_state = Mock(return_value=Mock(get_num_seeds_peers=Mock(return_value=(42, 7))))
        config = self.create_mock_download_config()

        with patch.object(self.manager, "start_download", AsyncMock(return_value=download)), \
                 patch.object(self.manager, "remove_download", AsyncMock()), \
                 patch.object(DownloadConfig, "from_defaults", Mock(return_value=config)):
            metainfo = await self.manager.get_metainfo(download.tdef.infohash)
            self.assertEqual(7, metainfo.pop(b"leechers"))
            self.assertEqual(42, metainfo.pop(b"seeders"))
            self.assertEqual(download.tdef.get_metainfo(), metainfo)

    async def test_get_metainfo_add_fail(self) -> None:
        """
        Test if invalid metainfo leads to a return value of None.
        """
        config = DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT)))

        with patch.object(self.manager, "start_download", AsyncMock(side_effect=TypeError)), \
                patch.object(DownloadConfig, "from_defaults", Mock(return_value=config)):
            self.assertIsNone(await self.manager.get_metainfo(b"\x00" * 20))

    async def test_get_metainfo_duplicate_request(self) -> None:
        """
        Test if the same request is returned when invoking get_metainfo twice with the same infohash.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True))
        config = DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT)))

        with patch.object(self.manager, "start_download", AsyncMock(return_value=download)), \
                patch.object(self.manager, "remove_download", AsyncMock()), \
                patch.object(DownloadConfig, "from_defaults", Mock(return_value=config)):
            results = await asyncio.gather(self.manager.get_metainfo(b"\x00" * 20),
                                           self.manager.get_metainfo(b"\x00" * 20))

        self.assertDictEqual(*results)

    async def test_get_metainfo_cache(self) -> None:
        """
        Testing if cached metainfo is returned, if available.
        """
        self.manager.metainfo_cache[b"a" * 20] = {'meta_info': 'test', 'time': 0}

        self.assertEqual("test", await self.manager.get_metainfo(b"a" * 20))

    async def test_get_metainfo_with_already_added_torrent(self) -> None:
        """
        Test if metainfo can be fetched for a torrent which is already in session.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True))
        self.manager.downloads[download.tdef.infohash] = download

        metainfo = await self.manager.get_metainfo(download.tdef.infohash)
        metainfo.pop(b"seeders")
        metainfo.pop(b"leechers")
        self.assertEqual(download.tdef.get_metainfo(), metainfo)

    async def test_start_download_while_getting_metainfo(self) -> None:
        """
        Test if a torrent can be added while a metainfo request is running.
        """
        info_download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                                 checkpoint_disabled=True, config=self.create_mock_download_config())
        info_download.handle = Mock(is_valid=Mock(return_value=True))
        self.manager.downloads[info_download.tdef.infohash] = info_download
        self.manager.metainfo_requests[info_download.tdef.infohash] = MetainfoLookup(info_download, 1)
        tdef = TorrentDef.load_only_sha1(info_download.tdef.infohash, "name",
                                         f"magnet:?xt=urn:btih:{hexlify(info_download.tdef.infohash).decode()}&")

        with patch.object(self.manager, "remove_download", AsyncMock()):
            download = await self.manager.start_download(tdef=tdef, config=info_download.config,
                                                         checkpoint_disabled=True)

        self.assertNotEqual(info_download, download)

    async def test_start_download(self) -> None:
        """
        Test if a torrent can be added to the download manager.
        """
        mock_handle = Mock(info_hash=Mock(return_value=Mock(to_bytes=Mock(return_value=b"\x01" * 20))),
                           is_valid=Mock(return_value=True))
        mock_alert = type("add_torrent_alert", (object,), {"handle": mock_handle,
                                                           "error": Mock(value=Mock(return_value=None)),
                                                           "category": MagicMock(return_value=None),
                                                           "params": Mock(added_time=0)})
        self.manager.ltsessions[0].result().async_add_torrent = lambda _: self.manager.process_alert(mock_alert())

        with patch.object(self.manager, "remove_download", AsyncMock()):
            download = await self.manager.start_download(tdef=TorrentDef.load_only_sha1(b"\x01" * 20, "", ""),
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

        self.assertIsNone(await self.manager.start_handle(download, Mock(save_path="")))

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
        mock_handle = Mock(info_hash=Mock(return_value=Mock(to_bytes=Mock(return_value=b"\x01" * 20))),
                           is_valid=Mock(return_value=True))
        self.manager.ltsessions[0].result().get_torrents = Mock(return_value=[mock_handle])
        download = await self.manager.start_download(tdef=TorrentDef.load_only_sha1(b"\x01" * 20, "name", ""),
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

        value = await self.manager.start_download(tdef=TorrentDef.load_only_sha1(download.tdef.infohash, "name", ""),
                                                  config=self.create_mock_download_config(),
                                                  checkpoint_disabled=True)

        self.assertEqual(download, value)

    async def test_start_download_no_ti_url(self) -> None:
        """
        Test if a ValueError is raised if we try to add a torrent without infohash or url.
        """
        config = DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT)))

        with self.assertRaises(ValueError), patch.object(DownloadConfig, "from_defaults", Mock(return_value=config)):
            await self.manager.start_download()

    def test_remove_unregistered_torrent(self) -> None:
        """
        Test if torrents which aren't known are succesfully removed.
        """
        mock_handle = Mock(is_valid=lambda: False)
        alert = type('torrent_removed_alert', (object,), {"handle": mock_handle,
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
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        {"ConfigObj": Mock(return_value=self.create_mock_download_config().config)}):
            value = await self.manager.load_checkpoint("foo.conf")

        self.assertFalse(value)

    async def test_load_checkpoint_empty_metainfo(self) -> None:
        """
        Test if no checkpoint can be loaded from a file with empty metainfo.
        """
        download_config = self.create_mock_download_config()
        download_config.set_metainfo({b"info": {}, b"url": ""})
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        {"ConfigObj": Mock(return_value=download_config.config)}):
            value = await self.manager.load_checkpoint("foo.conf")

        self.assertFalse(value)

    async def test_load_checkpoint_bad_url(self) -> None:
        """
        Test if no checkpoint can be loaded from a file with a bad url.
        """
        download_config = self.create_mock_download_config()
        download_config.set_metainfo({b"url": b"\x80", b"info": {
            b"name": b"torrent name",
            b"files": [{b"path": [b"a.txt"], b"length": 123}],
            b"piece length": 128,
            b"pieces": b"\x00" * 20
        }})
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        {"ConfigObj": Mock(return_value=download_config.config)}):
            value = await self.manager.load_checkpoint("foo.conf")

        self.assertFalse(value)

    async def test_load_checkpoint(self) -> None:
        """
        Test if a checkpoint can be loaded.
        """
        download_config = self.create_mock_download_config()
        download_config.set_metainfo({b"info": {
            b"name": b"torrent name",
            b"files": [{b"path": [b"a.txt"], b"length": 123}],
            b"piece length": 128,
            b"pieces": b"\x00" * 20
        }})
        download_config.set_dest_dir(Path(__file__).absolute().parent)
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        {"ConfigObj": Mock(return_value=download_config.config)}), \
                patch.object(self.manager, "start_download", AsyncMock()):
            value = await self.manager.load_checkpoint("foo.conf")

        self.assertTrue(value)

    async def test_load_checkpoint_zeroed_engineresumedata(self) -> None:
        """
        Test if no checkpoint is restored from uninitialized engineresumedata.
        """
        download_config = self.create_mock_download_config()
        download_config.set_metainfo({b"name": b"torrent name", b"infohash": b"\x01" * 20})
        download_config.set_dest_dir(Path(__file__).absolute().parent)
        download_config.set_engineresumedata(libtorrent.add_torrent_params())
        self.manager.start_download = AsyncMock()
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        {"ConfigObj": Mock(return_value=download_config.config)}):
            value = await self.manager.load_checkpoint("foo.conf")

        self.assertTrue(value)
        self.assertEqual(b"\x01" * 20, self.manager.start_download.call_args.kwargs["tdef"].infohash)

    async def test_load_checkpoint_file_not_found(self) -> None:
        """
        Test if no checkpoint can be loaded if a specified file is not found.
        """
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        {"ConfigObj": Mock(side_effect=OSError('Config file not found: "foo.conf".'))}):
            value = await self.manager.load_checkpoint("foo.conf")

        self.assertFalse(value)

    async def test_load_checkpoint_file_corrupt(self) -> None:
        """
        Test if no checkpoint can be loaded if the specified file is corrupt.
        """
        with patch.dict(tribler.core.libtorrent.download_manager.download_manager.__dict__,
                        {"ConfigObj": Mock(side_effect=VdtParamError("key", "value"))}):
            value = await self.manager.load_checkpoint("foo.conf")

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
        download = Download(TorrentDef.load_only_sha1(b"\x01" * 20, "name", ""), self.manager, checkpoint_disabled=True,
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
        download = Download(TorrentDef.load_only_sha1(b"\x01" * 20, "name", ""), self.manager, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        self.manager.downloads = {b"\x01" * 20: download}

        self.assertEqual([download], self.manager.get_downloads_by_name("name"))
        self.assertEqual([], self.manager.get_downloads_by_name("bla"))

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
        config = DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT)))
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
        config = DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT)))
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

        self.manager.update_trackers(download.tdef.infohash, [b"127.0.0.1/test-announce1"])

        self.assertEqual(b"127.0.0.1/test-announce1", download.tdef.get_metainfo()[b"announce"])
        self.assertListEqual([b"127.0.0.1/test-announce1"], download.tdef.get_metainfo()[b"announce-list"][0])

    def test_update_trackers_list(self) -> None:
        """
        Test if multiple trackers are correctly added as an announce list instead of a the singular announce.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        self.manager.downloads[download.tdef.infohash] = download

        self.manager.update_trackers(download.tdef.infohash, [f"127.0.0.1/test-announce{i}".encode() for i in range(2)])

        self.assertIn(download.tdef.get_metainfo()[b"announce"], [b"127.0.0.1/test-announce0",
                                                                  b"127.0.0.1/test-announce1"])
        self.assertSetEqual({f"127.0.0.1/test-announce{i}".encode() for i in range(2)},
                            {t[0] for t in download.tdef.get_metainfo()[b"announce-list"]})

    def test_update_trackers_list_append(self) -> None:
        """
        Test if trackers can be updated in sequence.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.manager,
                            checkpoint_disabled=True, config=self.create_mock_download_config())
        self.manager.downloads[download.tdef.infohash] = download

        self.manager.update_trackers(download.tdef.infohash, [b"127.0.0.1/test-announce0"])
        self.manager.update_trackers(download.tdef.infohash, [b"127.0.0.1/test-announce1"])

        self.assertIn(download.tdef.get_metainfo()[b"announce"],
                      [b"127.0.0.1/test-announce0", b"127.0.0.1/test-announce1"])
        self.assertSetEqual({f"127.0.0.1/test-announce{i}".encode() for i in range(2)},
                            {t[0] for t in download.tdef.get_metainfo()[b"announce-list"]})
