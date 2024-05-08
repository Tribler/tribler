from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import libtorrent
from configobj import ConfigObj
from ipv8.test.base import TestBase

from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.download_manager.stream import Stream
from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.libtorrent.torrents import (
    check_handle,
    check_vod,
    common_prefix,
    create_torrent_file,
    get_info_from_handle,
    require_handle,
)
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT


class TestTorrents(TestBase):
    """
    Tests for the torrent-related functionality.
    """

    def test_check_handle_default_missing_handle(self) -> None:
        """
        Test if the default value is returned for missing handles.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))

        self.assertEqual("default", (check_handle("default")(Download.get_def)(download)))

    def test_check_handle_default_invalid_handle(self) -> None:
        """
        Test if the default value is returned for invalid handles.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=False))

        self.assertEqual("default", (check_handle("default")(Download.get_def)(download)))

    def test_check_handle_default_valid_handle(self) -> None:
        """
        Test if the given method is called for valid handles.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True))

        self.assertEqual(download.tdef, (check_handle("default")(Download.get_def)(download)))

    async def test_require_handle_invalid_handle(self) -> None:
        """
        Test if None is returned for invalid handles.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=False))

        result = await require_handle(Download.get_def)(download)

        self.assertIsNone(result)

    async def test_require_handle_valid_handle(self) -> None:
        """
        Test if the result of the given method is given for valid handles.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True))

        result = await require_handle(Download.get_def)(download)

        self.assertEqual(download.tdef, result)

    async def test_require_handle_ignore_runtime_errors(self) -> None:
        """
        Test if runtime errors are ignored in functions.
        """
        def callback(_: Download) -> None:
            """
            Raise a RuntimeError. NOTE: THIS IS LOGGED, THE TEST IS NOT FAILING.
            """
            raise RuntimeError

        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True))

        future = require_handle(callback)(download)
        await future

        self.assertIsNone(future.result())

    async def test_require_handle_set_exception(self) -> None:
        """
        Test if exceptions other than runtime errors are set on the future.
        """
        def callback(_: Download) -> None:
            """
            Raise a non-RuntimeError. NOTE: THIS IS LOGGED, THE TEST IS NOT FAILING.
            """
            raise ValueError

        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True))

        future = require_handle(callback)(download)
        with self.assertRaises(ValueError):
            await future

    async def test_check_vod_disabled(self) -> None:
        """
        Test if the default value is returned for disabled vod mode.
        """
        stream = Stream(Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                                 config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT)))))
        stream.close()

        result = check_vod("default")(Stream.enabled)(stream)

        self.assertEqual("default", result)

    async def test_check_vod_enabled(self) -> None:
        """
        Test if the function result is returned for enabled vod mode.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None,
                            checkpoint_disabled=True, config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True), file_priorities=Mock(return_value=[0]),
                               torrent_file=Mock(return_value=Mock(map_file=Mock(return_value=Mock(piece=0)))))
        stream = Stream(download)
        download.lt_status = Mock(state=3, paused=False, pieces=[])
        await stream.enable()

        result = check_vod("default")(Stream.bytetopiece)(stream, 0)

        self.assertEqual(0, result)

    def test_common_prefix_single(self) -> None:
        """
        Test if a single file can a prefix of nothing.
        """
        self.assertEqual(Path("."), common_prefix([Path("hello.txt")]))

    def test_common_prefix_single_many(self) -> None:
        """
        Test if a many single files have a prefix of nothing.
        """
        self.assertEqual(Path("."), common_prefix([Path("hello.txt"), Path("file.txt"), Path("foo.txt")]))

    def test_common_prefix_single_in_folder(self) -> None:
        """
        Test if a single file can a prefix of its parent directory.
        """
        self.assertEqual(Path("folder") / "directory", common_prefix([Path("folder") / "directory" / "hello.txt"]))

    def test_common_prefix_single_many_in_folder(self) -> None:
        """
        Test if many single files have a prefix of their parent directory.
        """
        result = common_prefix([
            Path("folder") / "directory" / "hello.txt",
            Path("folder") / "directory" / "subdirectory" / "hello.txt",
            Path("folder") / "directory" / "file.txt"
        ])

        self.assertEqual(Path("folder") / "directory", result)

    def test_get_info_from_handle_no_attribute(self) -> None:
        """
        Test if a handle has no torrent info attribute that None is returned.
        """
        self.assertIsNone(get_info_from_handle(object()))

    def test_get_info_from_handle_runtime_error(self) -> None:
        """
        Test if fetching a handle raise a RuntimeError that None is returned.
        """
        self.assertIsNone(get_info_from_handle(Mock(torrent_file=Mock(side_effect=RuntimeError("test")))))

    def test_get_info_from_handle_legacy(self) -> None:
        """
        Test if fetching a handle raise a RuntimeError that None is returned.
        """
        torrent_file = "I am a torrent file"

        self.assertEqual(torrent_file, get_info_from_handle(Mock(torrent_file=Mock(return_value=torrent_file))))

    def test_create_torrent_file_defaults(self) -> None:
        """
        Test if torrents can be created from an existing file without any parameters.
        """
        result = create_torrent_file([Path(__file__).absolute()], {})

        self.assertTrue(result["success"])
        self.assertIsNone(result["torrent_file_path"])
        self.assertEqual(b"test_torrents.py", libtorrent.bdecode(result["metainfo"])[b"info"][b"name"])

    def test_create_torrent_file_with_piece_length(self) -> None:
        """
        Test if torrents can be created with a specified piece length.
        """
        result = create_torrent_file([Path(__file__).absolute()], {b"piece length": 16})

        self.assertEqual(16, libtorrent.bdecode(result["metainfo"])[b"info"][b"piece length"])

    def test_create_torrent_file_with_comment(self) -> None:
        """
        Test if torrents can be created with a specified comment.
        """
        result = create_torrent_file([Path(__file__).absolute()], {b"comment": b"test"})

        self.assertEqual(b"test", libtorrent.bdecode(result["metainfo"])[b"comment"])

    def test_create_torrent_file_with_created_by(self) -> None:
        """
        Test if torrents can be created with a specified created by field.
        """
        result = create_torrent_file([Path(__file__).absolute()], {b"created by": b"test"})

        self.assertEqual(b"test", libtorrent.bdecode(result["metainfo"])[b"created by"])

    def test_create_torrent_file_with_announce(self) -> None:
        """
        Test if torrents can be created with a specified announce field.
        """
        result = create_torrent_file([Path(__file__).absolute()], {b"announce": b"http://127.0.0.1/announce"})

        self.assertEqual(b"http://127.0.0.1/announce", libtorrent.bdecode(result["metainfo"])[b"announce"])

    def test_create_torrent_file_with_announce_list(self) -> None:
        """
        Test if torrents can be created with a specified announce list.

        Note that the announce list becomes a list of lists after creating the torrent.
        """
        tracker_list = [[b"http://127.0.0.1/announce"], [b"http://10.0.0.2/announce"]]
        result = create_torrent_file([Path(__file__).absolute()], {b"announce-list": tracker_list})

        self.assertEqual(tracker_list, libtorrent.bdecode(result["metainfo"])[b"announce-list"])

    def test_create_torrent_file_with_nodes(self) -> None:
        """
        Test if torrents can be created with a specified node list.
        """
        node_list = [[b"127.0.0.1", 80], [b"10.0.0.2", 22]]
        result = create_torrent_file([Path(__file__).absolute()], {b"nodes": node_list})

        self.assertEqual(node_list, libtorrent.bdecode(result["metainfo"])[b"nodes"])

    def test_create_torrent_file_with_http_seed(self) -> None:
        """
        Test if torrents can be created with a specified http seed.
        """
        result = create_torrent_file([Path(__file__).absolute()], {b"httpseeds": b"http://127.0.0.1/file"})

        self.assertEqual(b"http://127.0.0.1/file", libtorrent.bdecode(result["metainfo"])[b"httpseeds"])

    def test_create_torrent_file_with_url_list(self) -> None:
        """
        Test if torrents can be created with a specified url list.
        """
        result = create_torrent_file([Path(__file__).absolute()], {b"urllist": b"http://127.0.0.1/file"})

        self.assertEqual(b"http://127.0.0.1/file", libtorrent.bdecode(result["metainfo"])[b"url-list"])
