from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import libtorrent
from configobj import ConfigObj
from ipv8.test.base import TestBase

from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.download_manager.download_state import DOWNLOAD, UPLOAD, DownloadState, DownloadStatus
from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT


class TestDownloadState(TestBase):
    """
    Tests for the DownloadState class.
    """

    base_peer_info = {"client": "unknown", "pid": Mock(to_bytes=Mock(return_value=b"\x01")), "ip": ("127.0.0.1", 42),
                      "flags":0, "local_connection": 1, "remote_interested": 0, "remote_choked": 0, "upload_only": 1,
                      "upload_queue_length": 1, "used_send_buffer": 1, "interesting": 1, "choked": 0, "seed": 1}

    def test_initialize(self) -> None:
        """
        Test if DownloadState gets properly initialized from a download without a status.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download_state = DownloadState(download, None, None)

        self.assertEqual(download, download_state.get_download())
        self.assertEqual(0, download_state.get_progress())
        self.assertIsNone(download_state.get_error())
        self.assertEqual(0, download_state.get_current_speed(UPLOAD))
        self.assertEqual(0, download_state.total_upload)
        self.assertEqual(0, download_state.total_download)
        self.assertEqual(0, download_state.total_payload_download)
        self.assertEqual(0, download_state.total_payload_upload)
        self.assertEqual(0, download_state.all_time_upload)
        self.assertEqual(0, download_state.all_time_download)
        self.assertEqual((0, 0), download_state.get_num_seeds_peers())
        self.assertEqual([], download_state.get_peer_list())

    def test_initialize_with_status(self) -> None:
        """
        Test if DownloadState gets properly initialized from a download with a status.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download_state = DownloadState(download, libtorrent.torrent_status(), None)

        self.assertEqual(DownloadStatus.HASHCHECKING, download_state.get_status())
        self.assertEqual(0, download_state.get_current_speed(UPLOAD))
        self.assertEqual(0, download_state.get_current_speed(DOWNLOAD))

        self.assertEqual(0, download_state.get_eta())
        self.assertEqual((0, 0), download_state.get_num_seeds_peers())
        self.assertEqual([], download_state.get_pieces_complete())
        self.assertEqual((0, 0), download_state.get_pieces_total_complete())
        self.assertEqual(0, download_state.get_seeding_time())
        self.assertEqual([], download_state.get_peer_list())

    def test_initialize_with_mocked_status(self) -> None:
        """
        Test if DownloadState gets properly initialized from a download with a mocked status.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.config.set_selected_files(["test"])
        download_state = DownloadState(download, Mock(num_pieces=6, pieces=[1, 1, 1, 0, 0, 0], progress=0.75,
                                                      total_upload=100, total_download=200, total_payload_upload=30,
                                                      total_payload_download=100, all_time_upload=200,
                                                      all_time_download=1000), None)

        self.assertEqual([1, 1, 1, 0, 0, 0], download_state.get_pieces_complete())
        self.assertEqual((6, 3), download_state.get_pieces_total_complete())
        self.assertEqual(["test"], download_state.get_selected_files())
        self.assertEqual(0.75, download_state.get_progress())
        self.assertEqual(100, download_state.total_upload)
        self.assertEqual(200, download_state.total_download)
        self.assertEqual(30, download_state.total_payload_upload)
        self.assertEqual(100, download_state.total_payload_download)
        self.assertEqual(200, download_state.all_time_upload)
        self.assertEqual(1000, download_state.all_time_download)

    def test_all_time_ratio_no_lt_status(self) -> None:
        """
        Test if the all-time ratio is 0 when the libtorrent status is None.
        """
        state = DownloadState(Mock(), None, None)

        self.assertEqual(0, state.get_all_time_ratio())

    def test_all_time_ratio(self) -> None:
        """
        Test if the all-time ratio is the fraction of the all-time up and down.
        """
        tdef = Mock(get_length=Mock(return_value=1000))
        state = DownloadState(Mock(tdef=tdef), Mock(progress=1, all_time_upload=200), None)

        self.assertEqual(0.2, state.get_all_time_ratio())

    def test_all_time_ratio_no_all_time_download(self) -> None:
        """
        Test if the all-time ratio is 0 when the all-time up and down are both 0.
        """
        tdef = Mock(get_length=Mock(return_value=1000))
        state = DownloadState(Mock(tdef=tdef), Mock(progress=0, all_time_upload=0), None)

        self.assertEqual(0, state.get_all_time_ratio())

    def test_all_time_ratio_no_all_time_download_inf(self) -> None:
        """
        Test if the all-time ratio is 0 when the all-time download is 0.
        """
        tdef = Mock(get_length=Mock(return_value=1000))
        state = DownloadState(Mock(tdef=tdef), Mock(progress=0, all_time_upload=1000), None)

        self.assertEqual(-1, state.get_all_time_ratio())

    def test_get_files_completion(self) -> None:
        """
        Testing if the right completion of files is returned.

        Each file is 6 bytes, so a file progress of 3 bytes is 0.5 completion.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None,
                            checkpoint_disabled=True, config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True), file_progress=Mock(return_value=[3] * 6))
        download_state = DownloadState(download, Mock(), None)

        self.assertEqual([(Path('abc/file2.txt'), 0.5), (Path('abc/file3.txt'), 0.5),
                          (Path('abc/file4.txt'), 0.5), (Path('def/file6.avi'), 0.5),
                          (Path('def/file5.txt'), 0.5), (Path('file1.txt'), 0.5)],
                         download_state.get_files_completion())

    def test_get_files_completion_no_progress(self) -> None:
        """
        Testing if file progress is not given if no file progress is available.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None,
                            checkpoint_disabled=True, config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True), file_progress=Mock(return_value=[]))
        download_state = DownloadState(download, Mock(), None)

        self.assertEqual([], download_state.get_files_completion())

    def test_get_files_completion_zero_length_file(self) -> None:
        """
        Testing if file progress is 100% for a file of 0 bytes.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None,
                            checkpoint_disabled=True, config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        for file_spec in download.tdef.metainfo[b"info"][b"files"]:
            file_spec[b"length"] = 0
        download.handle = Mock(is_valid=Mock(return_value=True), file_progress=Mock(return_value=[]))
        download_state = DownloadState(download, Mock(), None)

        for _, progress in download_state.get_files_completion():
            self.assertEqual(1.0, progress)

    def test_get_availability_incomplete(self) -> None:
        """
        Testing if the right availability of a file is returned if another peer has no pieces.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True), file_progress=Mock(return_value=[]),
                               get_peer_info=Mock(return_value=[Mock(**TestDownloadState.base_peer_info,
                                                                     pieces=[False] * 6, completed=0)]))
        download_state = DownloadState(download, Mock(pieces=[]), 0.6)

        self.assertEqual(0, download_state.get_availability())

    def test_get_availability_complete(self) -> None:
        """
        Testing if the right availability of a file is returned if another peer has all pieces.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True), file_progress=Mock(return_value=[]),
                               get_peer_info=Mock(return_value=[Mock(**TestDownloadState.base_peer_info,
                                                                     pieces=[True] * 6, completed=1)]))
        download_state = DownloadState(download, Mock(pieces=[]), 0.6)

        self.assertEqual(1.0, download_state.get_availability())

    def test_get_availability_mixed(self) -> None:
        """
        Testing if the right availability of a file is returned if one peer is complete and the other is not.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name", None), None, checkpoint_disabled=True,
                            config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True), file_progress=Mock(return_value=[]),
                               get_peer_info=Mock(return_value=[Mock(**TestDownloadState.base_peer_info,
                                                                     pieces=[True] * 6, completed=1),
                                                                Mock(**TestDownloadState.base_peer_info,
                                                                     pieces=[False] * 6, completed=0)]))
        download_state = DownloadState(download, Mock(pieces=[]), 0.6)

        self.assertEqual(1.0, download_state.get_availability())

    def test_get_files_completion_semivalid_handle(self) -> None:
        """
        Testing whether no file completion is returned for valid handles that have invalid file_progress.

        This case mirrors https://github.com/Tribler/tribler/issues/6454
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None,
                            checkpoint_disabled=True, config=DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT))))
        download.handle = Mock(is_valid=Mock(return_value=True),
                               file_progress=Mock(side_effect=RuntimeError("invalid torrent handle used")))
        download_state = DownloadState(download, Mock(), None)

        self.assertEqual([], download_state.get_files_completion())
