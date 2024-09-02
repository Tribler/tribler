from asyncio import Future, ensure_future, sleep
from binascii import hexlify
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, call, patch

import libtorrent
from configobj import ConfigObj
from ipv8.test.base import TestBase
from ipv8.util import succeed
from validate import Validator

import tribler
from tribler.core.libtorrent.download_manager.download import Download, IllegalFileIndex, SaveResumeDataError
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.notifier import Notification, Notifier
from tribler.test_unit.core.libtorrent.mocks import TORRENT_UBUNTU_FILE_CONTENT, TORRENT_WITH_DIRS_CONTENT


class PermissionErrorDownloadConfig(DownloadConfig):
    """
    A mocked DownloadConfig that raises a PermissionError on write.
    """

    def write(self, filename: Path) -> None:
        """
        Perform a crash.
        """
        self.config["TEST_CRASH"] = True
        raise PermissionError


class TestDownload(TestBase):
    """
    Tests for the Download class.
    """

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

    def test_download_get_magnet_link_no_handle(self) -> None:
        """
        Test if a download without a handle does not have a magnet link.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertIsNone(download.get_magnet_link())

    def test_download_get_atp(self) -> None:
        """
        Test if the atp can be retrieved from a download.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        atp = download.get_atp()

        self.assertEqual(".", atp["save_path"])
        self.assertIn("flags", atp)
        self.assertIn("storage_mode", atp)
        self.assertIn("ti", atp)

    def test_download_resume(self) -> None:
        """
        Test if a download can be resumed.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.resume()

        self.assertFalse(download.config.get_user_stopped())
        self.assertEqual(call(False), download.handle.set_upload_mode.call_args)
        self.assertEqual(call(), download.handle.resume.call_args)

    async def test_save_resume(self) -> None:
        """
        Test if a download is resumed after fetching the save/resume data.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.futures["save_resume_data"] = succeed(True)

        future = ensure_future(download.save_resume_data())
        while "save_resume_data_alert" not in download.futures:
            await sleep(0)
        download.process_alert(Mock(), "save_resume_data_alert")
        await future

        self.assertTrue(future.done())

    def test_move_storage(self) -> None:
        """
        Test if storage can be moved.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        success = download.move_storage(Path("some_path"))

        self.assertTrue(success)
        self.assertEqual(Path("some_path"), download.config.get_dest_dir())
        self.assertEqual(call("some_path"), download.handle.move_storage.call_args)

    def test_move_storage_no_metainfo(self) -> None:
        """
        Test if storage is not moved for torrents without metainfo.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        success = download.move_storage(Path("some_path"))

        self.assertTrue(success)
        self.assertEqual(Path("some_path"), download.config.get_dest_dir())
        self.assertIsNone(download.handle.move_storage.call_args)

    async def test_save_checkpoint_disabled(self) -> None:
        """
        Test if checkpoints are not saved if checkpointing is disabled.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=False))

        value = await download.checkpoint()

        self.assertIsNone(value)

    async def test_save_checkpoint_handle_no_data(self) -> None:
        """
        Test if checkpoints are not saved if the handle specifies that it does not need resume data.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.checkpoint_disabled = False
        download.handle = Mock(is_valid=Mock(return_value=True), need_save_resume_data=Mock(return_value=False))

        value = await download.checkpoint()

        self.assertIsNone(value)

    async def test_save_checkpoint_no_handle_no_existing(self) -> None:
        """
        Test if checkpoints are saved for torrents without a handle and no existing checkpoint file.
        """
        alerts = []
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.checkpoint_disabled = False
        download.download_manager = Mock(get_checkpoint_dir=Mock(return_value=Path("foo")))
        download.alert_handlers["save_resume_data_alert"] = [alerts.append]

        with patch.dict(tribler.core.libtorrent.download_manager.download.__dict__,
                        {"Path": Mock(return_value=Mock(is_file=Mock(return_value=False)))}):
            value = await download.checkpoint()

        self.assertIsNone(value)
        self.assertEqual(None, alerts[0].category())
        self.assertEqual(b"libtorrent resume file", alerts[0].resume_data[b"file-format"])
        self.assertEqual(1, alerts[0].resume_data[b"file-version"])
        self.assertEqual(b"\x01" * 20, alerts[0].resume_data[b"info-hash"])

    async def test_save_checkpoint_no_handle_existing(self) -> None:
        """
        Test if existing checkpoints are not overwritten by checkpoints without data.
        """
        alerts = []
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.checkpoint_disabled = False
        download.download_manager = Mock(get_checkpoint_dir=Mock(return_value=Path("foo")))
        download.alert_handlers["save_resume_data_alert"] = [alerts.append]

        with patch.dict(tribler.core.libtorrent.download_manager.download.__dict__,
                        {"Path": Mock(return_value=Mock(is_file=Mock(return_value=True)))}):
            value = await download.checkpoint()

        self.assertIsNone(value)
        self.assertEqual([], alerts)

    def test_selected_files_default(self) -> None:
        """
        Test if the default selected files are no files.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(file_priorities=Mock(return_value=[0, 0]))

        self.assertEqual([], download.config.get_selected_files())
        self.assertEqual([0, 0], download.get_file_priorities())

    def test_selected_files_last(self) -> None:
        """
        Test if the last selected file in a list of files gets correctly selected.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(file_priorities=Mock(return_value=[0, 4]))

        download.set_selected_files([1])

        self.assertEqual([1], download.config.get_selected_files())
        self.assertEqual([0, 4], download.get_file_priorities())

    def test_selected_files_first(self) -> None:
        """
        Test if the first selected file in a list of files gets correctly selected.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(file_priorities=Mock(return_value=[4, 0]))

        download.set_selected_files([0])

        self.assertEqual([0], download.config.get_selected_files())
        self.assertEqual([4, 0], download.get_file_priorities())

    def test_selected_files_all(self) -> None:
        """
        Test if all files can be selected.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(file_priorities=Mock(return_value=[4, 4]))

        download.set_selected_files([0, 1])

        self.assertEqual([0, 1], download.config.get_selected_files())
        self.assertEqual([4, 4], download.get_file_priorities())

    def test_selected_files_all_through_none(self) -> None:
        """
        Test if all files can be selected by selecting None.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(file_priorities=Mock(return_value=[4, 4]))

        download.set_selected_files()

        self.assertEqual([], download.config.get_selected_files())
        self.assertEqual([4, 4], download.get_file_priorities())

    def test_selected_files_all_through_empty_list(self) -> None:
        """
        Test if all files can be selected by selecting an empty list.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(file_priorities=Mock(return_value=[4, 4]))

        download.set_selected_files([])

        self.assertEqual([], download.config.get_selected_files())
        self.assertEqual([4, 4], download.get_file_priorities())

    def test_get_share_mode_enabled(self) -> None:
        """
        Test if we forward the enabled share mode when requested in the download.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.config.set_share_mode(True)

        self.assertTrue(download.get_share_mode())

    def test_get_share_mode_disabled(self) -> None:
        """
        Test if we forward the disabled share mode when requested in the download.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.config.set_share_mode(False)

        self.assertFalse(download.get_share_mode())

    async def test_enable_share_mode(self) -> None:
        """
        Test if the share mode can be enabled in a download.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.set_share_mode(True)
        await sleep(0)

        self.assertTrue(download.config.get_share_mode())
        self.assertEqual(call(True), download.handle.set_share_mode.call_args)

    async def test_disable_share_mode(self) -> None:
        """
        Test if the share mode can be disabled in a download.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.set_share_mode(False)
        await sleep(0)

        self.assertFalse(download.config.get_share_mode())
        self.assertEqual(call(False), download.handle.set_share_mode.call_args)

    def test_get_num_connected_seeds_peers_no_handle(self) -> None:
        """
        Test if connected peers and seeds are 0 if there is no handle.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        num_seeds, num_peers = download.get_num_connected_seeds_peers()

        self.assertEqual(0, num_seeds)
        self.assertEqual(0, num_peers)

    def test_get_num_connected_seeds_peers(self) -> None:
        """
        Test if connected peers and seeds are correctly returned.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True), get_peer_info=Mock(return_value=[
            Mock(flags=140347, seed=1024),
            Mock(flags=140347, seed=128),
            Mock(flags=131242, seed=1024)
        ]))

        num_seeds, num_peers = download.get_num_connected_seeds_peers()

        self.assertEqual(1, num_seeds)
        self.assertEqual(2, num_peers)

    async def test_set_priority(self) -> None:
        """
        Test if setting the priority calls the right methods in download.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.set_priority(1234)
        await sleep(0)

        self.assertEqual(call(1234), download.handle.set_priority.call_args)

    def test_add_trackers(self) -> None:
        """
        Test if trackers are added to the libtorrent handle.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.add_trackers(["http://google.com"])

        self.assertEqual(call({"url": "http://google.com", "verified": False}),
                         download.handle.add_tracker.call_args)

    def test_process_error_alert(self) -> None:
        """
        Test if error alerts are processed correctly.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        download.process_alert(Mock(msg=None, status_code=123, url="http://google.com",
                                    category=Mock(return_value=libtorrent.alert.category_t.error_notification)),
                               "tracker_error_alert")

        self.assertEqual("HTTP status code 123", download.tracker_status["http://google.com"][1])

    def test_process_error_alert_timeout(self) -> None:
        """
        Test if timeout error alerts are processed correctly.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        download.process_alert(Mock(msg=None, status_code=0, url="http://google.com",
                                    category=Mock(return_value=libtorrent.alert.category_t.error_notification)),
                               "tracker_error_alert")

        self.assertEqual("Timeout", download.tracker_status["http://google.com"][1])

    def test_process_error_alert_not_working(self) -> None:
        """
        Test if not working error alerts are processed correctly.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        download.process_alert(Mock(msg=None, status_code=-1, url="http://google.com",
                                    category=Mock(return_value=libtorrent.alert.category_t.error_notification)),
                               "tracker_error_alert")

        self.assertEqual("Not working", download.tracker_status["http://google.com"][1])

    def test_tracker_warning_alert(self) -> None:
        """
        Test if a tracking warning alert is processed correctly.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        download.process_alert(Mock(message=Mock(return_value="test"), url="http://google.com",
                                    category=Mock(return_value=libtorrent.alert.category_t.error_notification)),
                               "tracker_warning_alert")

        self.assertEqual("Warning: test", download.tracker_status["http://google.com"][1])

    async def test_on_metadata_received_alert(self) -> None:
        """
        Test if the right operations happen when we receive metadata.
        """
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download = Download(tdef, None, checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(torrent_file=Mock(return_value=download.tdef.torrent_info),
                               trackers=Mock(return_value=[{"url": "http://google.com"}]))
        download.tdef = None

        download.on_metadata_received_alert(Mock())

        self.assertEqual(tdef.infohash, download.tdef.infohash)
        self.assertDictEqual(tdef.metainfo[b"info"], download.tdef.metainfo[b"info"])
        self.assertEqual(b"http://google.com", download.tdef.metainfo[b"announce"])

    def test_on_metadata_received_alert_unicode_error_encode(self) -> None:
        """
        Test if no exception is raised when the url is not unicode compatible.
        """
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download = Download(tdef, None, checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(trackers=Mock(return_value=[{"url": "\uD800"}]),
                               torrent_file=Mock(return_value=download.tdef.torrent_info),
                               get_peer_info=Mock(return_value=[]))
        download.tdef = None

        download.on_metadata_received_alert(Mock())

        self.assertEqual(tdef.infohash, download.tdef.infohash)
        self.assertDictEqual(tdef.metainfo[b"info"], download.tdef.metainfo[b"info"])
        self.assertNotIn(b"announce", download.tdef.metainfo)

    def test_on_metadata_received_alert_unicode_error_decode(self) -> None:
        """
        Test if no exception is raised when the url is not unicode compatible.

        See: https://github.com/Tribler/tribler/issues/7223
        """
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download = Download(tdef, None, checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(trackers=lambda: [{"url": b"\xFD".decode()}],
                               torrent_file=Mock(return_value=download.tdef.torrent_info),
                               get_peer_info=Mock(return_value=[]))
        download.tdef = None

        download.on_metadata_received_alert(Mock())

        self.assertEqual(tdef.infohash, download.tdef.infohash)
        self.assertDictEqual(tdef.metainfo[b"info"], download.tdef.metainfo[b"info"])
        self.assertNotIn(b"announce", download.tdef.metainfo)

    def test_metadata_received_invalid_torrent_with_error(self) -> None:
        """
        Test if no torrent def is loaded when a RuntimeError/ValueError occurs when parsing the metadata.
        """
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download = Download(tdef, None, checkpoint_disabled=True, config=self.create_mock_download_config())
        download.handle = Mock(trackers=Mock(return_value=[]),
                               torrent_file=Mock(return_value=Mock(metadata=Mock(return_value=b""))),
                               get_peer_info=Mock(return_value=[]))
        download.tdef = None

        download.on_metadata_received_alert(Mock())

        self.assertIsNone(download.tdef)

    def test_torrent_checked_alert_no_pause_no_checkpoint(self) -> None:
        """
        Test if no pause or checkpoint happens if the download state is such.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.checkpoint_disabled = False
        download.handle = Mock(is_valid=Mock(return_value=True), need_save_resume_data=Mock(return_value=False))
        download.pause_after_next_hashcheck = False
        download.checkpoint_after_next_hashcheck = False

        download.process_alert(Mock(), "torrent_checked_alert")

        self.assertIsNone(download.handle.pause.call_args)
        self.assertIsNone(download.handle.need_save_resume_data.call_args)
        self.assertFalse(download.pause_after_next_hashcheck)
        self.assertFalse(download.checkpoint_after_next_hashcheck)

    def test_torrent_checked_alert_no_pause_checkpoint(self) -> None:
        """
        Test if no pause but a checkpoint happens if the download state is such.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.checkpoint_disabled = False
        download.handle = Mock(is_valid=Mock(return_value=True), need_save_resume_data=Mock(return_value=False))
        download.pause_after_next_hashcheck = False
        download.checkpoint_after_next_hashcheck = True

        download.process_alert(Mock(), "torrent_checked_alert")

        self.assertIsNone(download.handle.pause.call_args)
        self.assertEqual(call(), download.handle.need_save_resume_data.call_args)
        self.assertFalse(download.pause_after_next_hashcheck)
        self.assertFalse(download.checkpoint_after_next_hashcheck)

    def test_torrent_checked_alert_pause_no_checkpoint(self) -> None:
        """
        Test if a pause but no checkpoint happens if the download state is such.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.checkpoint_disabled = False
        download.handle = Mock(is_valid=Mock(return_value=True), need_save_resume_data=Mock(return_value=False))
        download.pause_after_next_hashcheck = True
        download.checkpoint_after_next_hashcheck = False

        download.process_alert(Mock(), "torrent_checked_alert")

        self.assertEqual(call(), download.handle.pause.call_args)
        self.assertIsNone(download.handle.need_save_resume_data.call_args)
        self.assertFalse(download.pause_after_next_hashcheck)
        self.assertFalse(download.checkpoint_after_next_hashcheck)

    def test_torrent_checked_alert_pause_checkpoint(self) -> None:
        """
        Test if both a pause and a checkpoint happens if the download state is such.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.checkpoint_disabled = False
        download.handle = Mock(is_valid=Mock(return_value=True), need_save_resume_data=Mock(return_value=False))
        download.pause_after_next_hashcheck = True
        download.checkpoint_after_next_hashcheck = True

        download.process_alert(Mock(), "torrent_checked_alert")

        self.assertEqual(call(), download.handle.pause.call_args)
        self.assertEqual(call(), download.handle.need_save_resume_data.call_args)
        self.assertFalse(download.pause_after_next_hashcheck)
        self.assertFalse(download.checkpoint_after_next_hashcheck)

    def test_tracker_reply_alert(self) -> None:
        """
        Test if the tracker status is extracted from a reply alert.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        download.on_tracker_reply_alert(Mock(url="http://google.com", num_peers=42))

        self.assertEqual((42, "Working"), download.tracker_status["http://google.com"])

    def test_get_pieces_bitmask(self) -> None:
        """
        Test if a correct pieces bitmask is returned when requested.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(status=Mock(return_value=Mock(pieces=[True, False, True, False, False])))

        self.assertEqual(b"oA==", download.get_pieces_base64())

    async def test_resume_data_failed(self) -> None:
        """
        Test if an error is raised when loading resume data failed.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        future = download.wait_for_alert("save_resume_data_alert", None, "save_resume_data_failed_alert",
                                         lambda _: SaveResumeDataError())
        download.process_alert(Mock(msg="test error"), "save_resume_data_failed_alert")

        with self.assertRaises(SaveResumeDataError):
            await future

    async def test_on_state_changed_apply_ip_filter(self) -> None:
        """
        Test if the ip filter gets enabled when in torrent status seeding (5) when hops are not zero.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.config.set_hops(1)
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.on_state_changed_alert(type("state_changed_alert", (object,), {"state": 5}))
        await sleep(0)

        self.assertEqual(call(True), download.handle.apply_ip_filter.call_args)

    async def test_on_state_changed_no_filter(self) -> None:
        """
        Test if the ip filter does not get enabled when the hop count is zero.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.config.set_hops(0)
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.on_state_changed_alert(type("state_changed_alert", (object,), {"state": 5}))
        await sleep(0)

        self.assertEqual(call(False), download.handle.apply_ip_filter.call_args)

    async def test_on_state_changed_not_seeding(self) -> None:
        """
        Test if the ip filter does not get enabled when the hop count is zero.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.config.set_hops(1)
        download.handle = Mock(is_valid=Mock(return_value=True))

        download.on_state_changed_alert(type("state_changed_alert", (object,), {"state": 4}))
        await sleep(0)

        self.assertEqual(call(False), download.handle.apply_ip_filter.call_args)

    async def test_checkpoint_timeout(self) -> None:
        """
        Testing whether making a checkpoint times out when we receive no alert from libtorrent.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.futures["save_resume_data"] = [Future()]


        task = ensure_future(download.save_resume_data())
        await sleep(0)
        download.futures["save_resume_data_alert"][0][0].cancel()

        self.assertIsNone(await task)

    def test_on_save_resume_data_alert_permission_denied(self) -> None:
        """
        Test if permission error in writing the download config does not crash the save resume alert handler.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=PermissionErrorDownloadConfig(self.create_mock_download_config().config))
        download.checkpoint_disabled = False
        download.download_manager = Mock(get_checkpoint_dir=Mock(return_value=Path(__file__).absolute().parent))

        download.on_save_resume_data_alert(Mock(resume_data={b"info-hash": b"\x01" * 20}))

        self.assertTrue(download.config.config["TEST_CRASH"])
        self.assertEqual("name", download.config.config["download_defaults"]["name"])

    async def test_get_tracker_status_unicode_decode_error(self) -> None:
        """
        Test if a tracker status is returned when getting trackers leads to a UnicodeDecodeError.

        See: https://github.com/Tribler/tribler/issues/7036
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        fut = Future()
        fut.set_result(Mock(is_dht_running=Mock(return_value=False)))
        download.download_manager = Mock(get_session=Mock(return_value=fut))
        download.handle = Mock(is_valid=Mock(return_value=True),
                               get_peer_info=Mock(
                                   return_value=[Mock(source=1, dht=1, pex=0)] * 42 + [Mock(source=1, pex=1, dht=0)] * 7
                               ), trackers=Mock(side_effect=UnicodeDecodeError('', b'', 0, 0, '')))

        result = download.get_tracker_status()

        self.assertEqual((42, "Disabled"), result["[DHT]"])
        self.assertEqual((7, "Working"), result["[PeX]"])

    def test_get_tracker_status_get_peer_info_error(self) -> None:
        """
        Test if a tracker status is returned when getting peer info leads to a RuntimeError.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.download_manager = Mock(get_session=Mock(return_value=Mock(is_dht_running=Mock(return_value=True))))
        download.handle = Mock(is_valid=Mock(return_value=True), get_peer_info=Mock(side_effect=RuntimeError),
                               trackers=Mock(return_value=[]))

        result = download.get_tracker_status()

        self.assertEqual((0, "Working"), result["[DHT]"])
        self.assertEqual((0, "Working"), result["[PeX]"])

    async def test_shutdown(self) -> None:
        """
        Test if the shutdown method closes the stream and clears the futures dictionary.
        """
        download = Download(TorrentDefNoMetainfo(b"\x01" * 20, b"name"), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.stream = Mock()

        await download.shutdown()

        self.assertEqual({}, download.futures)
        self.assertEqual(call(), download.stream.close.call_args)

    def test_file_piece_range_flat(self) -> None:
        """
        Test if the piece range of a single-file torrent is correctly determined.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_UBUNTU_FILE_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        total_pieces = download.tdef.torrent_info.num_pieces()

        piece_range = download.file_piece_range(Path("ubuntu-15.04-desktop-amd64.iso"))

        self.assertEqual(piece_range, list(range(total_pieces)))

    def test_file_piece_range_minifiles(self) -> None:
        """
        Test if the piece range of a file is correctly determined if multiple files exist in the same piece.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        piece_range_a = download.file_piece_range(Path("torrent_create") / "abc" / "file2.txt")
        piece_range_b = download.file_piece_range(Path("torrent_create") / "abc" / "file3.txt")

        self.assertEqual([0], piece_range_a)
        self.assertEqual([0], piece_range_b)

    def test_file_piece_range_wide(self) -> None:
        """
        Test if the piece range of a multi-file torrent is correctly determined.
        """
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        tdef.metainfo[b"info"][b"files"][0][b"length"] = 60000
        tdef.metainfo[b"info"][b"pieces"] = b'\x01' * 80
        download = Download(tdef, None, checkpoint_disabled=True, config=self.create_mock_download_config())

        file1 = download.file_piece_range(Path("torrent_create") / "abc" / "file2.txt")
        other_indices = [download.file_piece_range(Path("torrent_create") / Path(
            *[p.decode() for p in tdef.metainfo[b"info"][b"files"][-1-i][b"path"]]
        )) for i in range(5)]

        self.assertEqual([0, 1, 2], file1)
        for piece_range in other_indices:
            self.assertEqual([3], piece_range)

    def test_file_piece_range_nonexistent(self) -> None:
        """
        Test if the piece range of a non-existent file is correctly determined.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        piece_range = download.file_piece_range(Path("I don't exist"))

        self.assertEqual([], piece_range)

    def test_file_completion_full(self) -> None:
        """
        Test if a complete file shows 1.0 completion.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True), have_piece=Mock(return_value=True))

        self.assertEqual(1.0, download.get_file_completion(Path("torrent_create") / "abc" / "file2.txt"))

    def test_file_completion_nonexistent(self) -> None:
        """
        Test if an unknown path (does not exist in a torrent) shows 1.0 completion.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True))

        self.assertEqual(1.0, download.get_file_completion(Path("I don't exist")))

    def test_file_completion_directory(self) -> None:
        """
        Test if a directory (does not exist in a torrent) shows 1.0 completion.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=True), have_piece=Mock(return_value=True))

        self.assertEqual(1.0, download.get_file_completion(Path("torrent_create")))

    def test_file_completion_nohandle(self) -> None:
        """
        Test if a file shows 0.0 completion if the torrent handle is not valid.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.handle = Mock(is_valid=Mock(return_value=False), have_piece=Mock(return_value=True))

        self.assertEqual(0.0, download.get_file_completion(Path("torrent_create") / "abc" / "file2.txt"))

    def test_file_completion_partial(self) -> None:
        """
        Test if a file shows 0.0 completion if the torrent handle is not valid.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_UBUNTU_FILE_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        total_pieces = download.tdef.torrent_info.num_pieces()
        expected = (total_pieces // 2) / total_pieces

        def fake_has_piece(piece_index: int) -> bool:
            return piece_index > total_pieces / 2  # total_pieces // 2 will return True

        download.handle = Mock(is_valid=Mock(return_value=True), have_piece=fake_has_piece)

        result = download.get_file_completion(Path("ubuntu-15.04-desktop-amd64.iso"))

        self.assertEqual(round(expected, 2), round(result, 2))  # Round to make sure we don't get float rounding errors

    def test_file_length(self) -> None:
        """
        Test if we can get the length of a file.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_UBUNTU_FILE_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertEqual(1150844928, download.get_file_length(Path("ubuntu-15.04-desktop-amd64.iso")))

    def test_file_length_two(self) -> None:
        """
        Test if we can get the length of a file in a multi-file torrent.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertEqual(6, download.get_file_length(Path("torrent_create") / "abc" / "file2.txt"))
        self.assertEqual(6, download.get_file_length(Path("torrent_create") / "abc" / "file3.txt"))

    def test_file_length_nonexistent(self) -> None:
        """
        Test if the length of a non-existent file is 0.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertEqual(0, download.get_file_length(Path("I don't exist")))

    def test_file_index_unloaded(self) -> None:
        """
        Test if a non-existent path leads to the special unloaded index.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertEqual(IllegalFileIndex.unloaded.value, download.get_file_index(Path("I don't exist")))

    def test_file_index_directory_collapsed(self) -> None:
        """
        Test if a collapsed-dir path leads to the special collapsed dir index.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertEqual(IllegalFileIndex.collapsed_dir.value, download.get_file_index(Path("torrent_create")))

    def test_file_index_directory_expanded(self) -> None:
        """
        Test if an expanded-dir path leads to the special expanded dir index.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.tdef.torrent_file_tree.expand(Path("torrent_create"))

        self.assertEqual(IllegalFileIndex.expanded_dir.value, download.get_file_index(Path("torrent_create")))

    def test_file_index_file(self) -> None:
        """
        Test if we can get the index of a file.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertEqual(1, download.get_file_index(Path("torrent_create") / "abc" / "file3.txt"))

    def test_file_selected_nonexistent(self) -> None:
        """
        Test if a non-existent file does not register as selected.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertFalse(download.is_file_selected(Path("I don't exist")))

    def test_file_selected_realfile(self) -> None:
        """
        Test if a file starts off as selected.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertTrue(download.is_file_selected(Path("torrent_create") / "abc" / "file3.txt"))

    def test_file_selected_directory(self) -> None:
        """
        Test if a directory does not register as selected.
        """
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())

        self.assertFalse(download.is_file_selected(Path("torrent_create") / "abc"))

    def test_on_torrent_finished_alert(self) -> None:
        """
        Test if the torrent_finished notification is called when the torrent finishes.
        """
        callback = Mock()
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, checkpoint_disabled=True,
                            config=self.create_mock_download_config())
        download.stream = Mock()
        download.handle = Mock(is_valid=Mock(return_value=True), status=Mock(return_value=Mock(total_download=7)))
        download.notifier = Notifier()
        download.notifier.add(Notification.torrent_finished, callback)

        download.on_torrent_finished_alert(Mock())

        self.assertEqual(call(infohash=hexlify(download.tdef.infohash).decode(), name="torrent_create", hidden=False),
                         callback.call_args)
