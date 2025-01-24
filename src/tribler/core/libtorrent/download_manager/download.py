"""
A wrapper around a libtorrent download.

Author(s): Arno Bakker, Egbert Bouman
"""
from __future__ import annotations

import asyncio
import base64
import itertools
import logging
from asyncio import CancelledError, Future, get_running_loop, sleep, wait_for
from binascii import hexlify
from collections import defaultdict
from contextlib import suppress
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypedDict, cast

import libtorrent as lt
from bitarray import bitarray
from ipv8.taskmanager import TaskManager, task
from ipv8.util import succeed

from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_state import DownloadState, DownloadStatus
from tribler.core.libtorrent.download_manager.stream import Stream
from tribler.core.libtorrent.torrent_file_tree import TorrentFileTree
from tribler.core.libtorrent.torrentdef import MetainfoDict, TorrentDef, TorrentDefNoMetainfo
from tribler.core.libtorrent.torrents import check_handle, get_info_from_handle, require_handle
from tribler.core.notifier import Notification, Notifier
from tribler.tribler_config import TriblerConfigManager

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager

Getter = Callable[[Any], Any]


class SaveResumeDataError(Exception):
    """This error is used when the resume data of a download fails to save."""


class IllegalFileIndex(Enum):
    """
    Error codes for Download.get_file_index(). These are used by the GUI to render directories.
    """

    collapsed_dir = -1
    expanded_dir = -2
    unloaded = -3


class PeerDict(TypedDict):
    """
    Information of another peer, connected through libtorrent.
    """

    id: str  # PeerID or 'http seed'
    extended_version: str  # Peer client version, as received during the extend handshake message
    ip: str  # IP address as string or URL of httpseed
    port: int
    pex_received: bool
    optimistic: bool
    direction: str  # 'L'/'R' (outgoing/incoming)
    uprate: float  # Upload rate in KB/s
    uinterested: bool  # Upload Interested: True/False
    uchoked: bool  # Upload Choked: True/False
    uhasqueries: bool  # Upload has requests in buffer and not choked
    uflushed: bool  # Upload is not flushed
    downrate: float  # Download rate in KB/s
    dinterested: bool  # Download interested: True/False
    dchoked: bool  # Download choked: True/False
    snubbed: bool  # Download snubbed: True/False
    utotal: float  # Total uploaded from peer in KB
    dtotal: float  # Total downloaded from peer in KB
    completed: float  # Fraction of download completed by peer (0-1.0)
    speed: float  # The peer's current total download speed (estimated)


class PeerDictHave(PeerDict):
    """
    Extended peer info that includes the "have" field.
    """

    have: list[bool]  # Bitfield object for this peer if not completed


class Download(TaskManager):
    """
    Download subclass that represents a libtorrent download.
    """

    def __init__(self,  # noqa: PLR0913
                 tdef: TorrentDef,
                 download_manager: DownloadManager,
                 config: DownloadConfig | None = None,
                 notifier: Notifier | None = None,
                 state_dir: Path | None = None,
                 checkpoint_disabled: bool = False,
                 hidden: bool = False) -> None:
        """
        Create a new download.
        """
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.tdef = tdef
        self.handle: lt.torrent_handle | None = None
        self.state_dir = state_dir
        self.download_manager = download_manager
        self.notifier = notifier

        # Libtorrent status
        self.lt_status: lt.torrent_status | None = None
        self.error = None
        self.pause_after_next_hashcheck = False
        self.checkpoint_after_next_hashcheck = False
        self.tracker_status: dict[str, tuple[int, str]] = {}  # {url: (num_peers, status_str)}

        self.futures: dict[str, list[tuple[Future, Callable, Getter | None]]] = defaultdict(list)
        self.alert_handlers: dict[str, list[Callable[[lt.torrent_alert], None]]] = defaultdict(list)

        self.future_added = self.wait_for_alert("add_torrent_alert", lambda a: a.handle)
        self.future_removed = self.wait_for_alert("torrent_removed_alert")
        self.future_finished = self.wait_for_alert("torrent_finished_alert")
        self.future_metainfo = self.wait_for_alert("metadata_received_alert", lambda a: self.tdef.get_metainfo())

        alert_handlers = {"tracker_reply_alert": self.on_tracker_reply_alert,
                          "tracker_error_alert": self.on_tracker_error_alert,
                          "tracker_warning_alert": self.on_tracker_warning_alert,
                          "metadata_received_alert": self.on_metadata_received_alert,
                          "performance_alert": self.on_performance_alert,
                          "torrent_checked_alert": self.on_torrent_checked_alert,
                          "torrent_finished_alert": self.on_torrent_finished_alert,
                          "save_resume_data_alert": self.on_save_resume_data_alert,
                          "state_changed_alert": self.on_state_changed_alert,
                          "torrent_error_alert": self.on_torrent_error_alert,
                          "add_torrent_alert": self.on_add_torrent_alert,
                          "torrent_removed_alert": self.on_torrent_removed_alert}

        for alert_type, alert_handler in alert_handlers.items():
            self.register_alert_handler(alert_type, alert_handler)
        self.stream: Stream | None = None

        # With hidden True download will not be in GET/downloads set, as a result will not be shown in GUI
        self.hidden = hidden
        self.checkpoint_disabled = checkpoint_disabled
        self.config: DownloadConfig = config
        if config is None and self.download_manager is not None:
            self.config = DownloadConfig.from_defaults(self.download_manager.config)
        elif config is None:
            self.config = DownloadConfig.from_defaults(TriblerConfigManager())

        self._logger.debug("Setup: %s", hexlify(self.tdef.get_infohash()).decode())

        self.checkpoint()

    def __str__(self) -> str:
        """
        Convert this download to a human-readable string.
        """
        return (f"Download(name={self.tdef.get_name()}, "
                f"hops={self.config.get_hops():d}, "
                f"checkpoint_disabled={self.checkpoint_disabled:d})")

    def __repr__(self) -> str:
        """
        Convert this download to a print-safe human-readable string.
        """
        return self.__str__()

    def add_stream(self) -> None:
        """
        Initialize a stream for this download.
        """
        assert self.stream is None
        self.stream = Stream(self)

    def get_torrent_data(self) -> dict[bytes, Any] | None:
        """
        Return torrent data, if the handle is valid and metadata is available.
        """
        if not self.handle or not self.handle.is_valid() or not self.handle.has_metadata():
            return None

        torrent_info = get_info_from_handle(self.handle)
        t = lt.create_torrent(torrent_info)
        return t.generate()

    def register_alert_handler(self, alert_type: str, handler: Callable[[lt.torrent_alert], None]) -> None:
        """
        Add (no replace) a callback for a given alert type.
        """
        self.alert_handlers[alert_type].append(handler)

    def wait_for_alert(self, success_type: str, success_getter: Getter | None = None,
                       fail_type: str | None = None, fail_getter: Getter | None = None) -> Future:
        """
        Create a future that fires when a certain alert is received.
        """
        future: Future[Any] = Future()
        if success_type:
            self.futures[success_type].append((future, future.set_result, success_getter))
        if fail_type:
            self.futures[fail_type].append((future, future.set_exception, fail_getter))
        return future

    async def wait_for_status(self, *status: DownloadStatus) -> None:
        """
        Wait for a given download status to occur.
        """
        while self.get_state().get_status() not in status:
            await sleep(0)
            await self.wait_for_alert("state_changed_alert")

    def get_def(self) -> TorrentDef:
        """
        Get the torrent def belonging to this download.
        """
        return self.tdef

    def get_handle(self) -> Future[lt.torrent_handle]:
        """
        Returns a deferred that fires with a valid libtorrent download handle.
        """
        if self.handle:
            # This block could be safely omitted because `self.future_added` does the same thing.
            # However, it is used in tests, therefore it is better to keep it for now.
            return succeed(self.handle)

        return self.future_added

    def get_atp(self) -> dict:
        """
        Get the libtorrent "add torrent parameters" instantiation dictionary.
        """
        save_path = self.config.get_dest_dir()
        atp = {"save_path": str(save_path),
               "storage_mode": lt.storage_mode_t.storage_mode_sparse,
               "flags": lt.add_torrent_params_flags_t.flag_paused
                        | lt.add_torrent_params_flags_t.flag_duplicate_is_error
                        | lt.add_torrent_params_flags_t.flag_update_subscribe}

        if self.config.get_share_mode():
            atp["flags"] = cast(int, atp["flags"]) | lt.add_torrent_params_flags_t.flag_share_mode
        if self.config.get_upload_mode():
            atp["flags"] = cast(int, atp["flags"]) | lt.add_torrent_params_flags_t.flag_upload_mode

        resume_data = self.config.get_engineresumedata()
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            metainfo = self.tdef.get_metainfo()
            torrentinfo = lt.torrent_info(metainfo)

            atp["ti"] = torrentinfo
            if resume_data and isinstance(resume_data, dict):
                # Rewrite save_path as a global path, if it is given as a relative path
                save_path = (resume_data[b"save_path"].decode() if b"save_path" in resume_data
                             else None)
                if save_path and not Path(save_path).is_absolute():
                    resume_data[b"save_path"] = str(self.state_dir / save_path)
                atp["resume_data"] = lt.bencode(resume_data)
        else:
            atp["url"] = self.tdef.get_url() or "magnet:?xt=urn:btih:" + hexlify(self.tdef.get_infohash()).decode()
            atp["name"] = self.tdef.get_name_as_unicode()

        return atp

    def on_add_torrent_alert(self, alert: lt.add_torrent_alert) -> None:
        """
        Handle an add torrent alert.
        """
        self._logger.info("On add torrent alert: %s", repr(alert))

        if hasattr(alert, "error") and alert.error.value():
            self._logger.error("Failed to add torrent (%s)", self.tdef.get_name_as_unicode())
            raise RuntimeError(alert.error.message())
        if not alert.handle.is_valid():
            self._logger.error("Received invalid torrent handle")
            return

        self.handle = alert.handle
        self._logger.debug("Added torrent %s", str(self.handle.info_hash()))
        # In LibTorrent auto_managed flag is now on by default, and as a result
        # any torrent"s state can change from Stopped to Downloading at any time.
        # Here we unset this flag to prevent auto-resuming of stopped torrents.
        if hasattr(self.handle, "unset_flags"):
            self.handle.unset_flags(lt.add_torrent_params_flags_t.flag_auto_managed)

        self.set_selected_files()

        user_stopped = self.config.get_user_stopped()

        # If we lost resume_data always resume download in order to force checking
        if not user_stopped or not self.config.get_engineresumedata():
            self.handle.resume()

            # If we only needed to perform checking, pause download after it is complete
            self.pause_after_next_hashcheck = user_stopped

        # Limit the amount of connections if we have specified that
        self.handle.set_max_connections(self.download_manager.config.get("libtorrent/max_connections_download"))

        # By default don't apply the IP filter
        self.apply_ip_filter(False)

        self.checkpoint()

    def get_anon_mode(self) -> bool:
        """
        Get whether this torrent is anonymized.
        """
        return self.config.get_hops() > 0

    @check_handle(b"")
    def get_pieces_base64(self) -> bytes:
        """
        Returns a base64 encoded bitmask of the pieces that we have.
        """
        binary_gen = (int(boolean) for boolean in cast(lt.torrent_handle, self.handle).status().pieces)
        try:
            bits = bitarray(binary_gen)
        except ValueError:
            return b""
        return base64.b64encode(bits.tobytes())

    def post_alert(self, alert_type: str, alert_dict: dict | None = None) -> None:
        """
        Manually post an alert.
        """
        alert_dict = alert_dict or {}
        alert_dict["category"] = lambda _: None
        alert = type("anonymous_alert", (object,), alert_dict)()
        self.process_alert(alert, alert_type)

    def process_alert(self, alert: lt.torrent_alert, alert_type: str) -> None:
        """
        Dispatch an alert to the appriopriate registered handlers.
        """
        try:
            if alert.category() in [lt.alert.category_t.error_notification, lt.alert.category_t.performance_warning]:
                self._logger.debug("Got alert: %s", repr(alert))

            for handler in self.alert_handlers.get(alert_type, []):
                try:
                    handler(alert)
                except UnicodeDecodeError as e:
                    self._logger.warning("UnicodeDecodeError in %s: %s", handler.__name__, str(e))

            for future, future_setter, getter in self.futures.pop(alert_type, []):
                if not future.done():
                    future_setter(getter(alert) if getter else alert)
        except Exception as e:
            self._logger.exception("process_alert failed with %s: %s for alert %s",
                                   e.__class__.__name__, str(e), repr(alert))

    def on_torrent_error_alert(self, alert: lt.torrent_error_alert) -> None:
        """
        Handle a torrent error alert.
        """
        self._logger.error("On torrent error alert: %s", repr(alert))

    def on_state_changed_alert(self, alert: lt.state_changed_alert) -> None:
        """
        Handle a state change alert.
        """
        self._logger.info("On state changed alert: %s", repr(alert))

        if not self.handle:
            return
        self.update_lt_status(self.handle.status())

        enable = alert.state == lt.torrent_status.seeding and self.config.get_hops() > 0
        self._logger.debug("Setting IP filter for %s to %s", hexlify(self.tdef.get_infohash()), enable)
        self.apply_ip_filter(enable)

        # On a rare occasion we don't get a metadata_received_alert. If this is the case, post an alert manually.
        if alert.state == lt.torrent_status.downloading and isinstance(self.tdef, TorrentDefNoMetainfo):
            self.post_alert("metadata_received_alert")

    def on_save_resume_data_alert(self, alert: lt.save_resume_data_alert) -> None:
        """
        Callback for the alert that contains the resume data of a specific download.
        This resume data will be written to a file on disk.
        """
        self._logger.debug("On save resume data alert: %s", repr(alert))
        if self.checkpoint_disabled:
            return

        resume_data = (cast(dict[bytes, Any], lt.bdecode(alert.resume_data))
                       if isinstance(alert.resume_data, bytes)  # Libtorrent 2.X
                       else alert.resume_data)  # Libtorrent 1.X
        # Make save_path relative if the torrent is saved in the Tribler state directory
        if self.state_dir and b"save_path" in resume_data:
            save_path = Path(resume_data[b"save_path"].decode()).absolute()
            resume_data[b"save_path"] = str(save_path)

        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.config.set_metainfo(self.tdef.get_metainfo())
        else:
            self.config.set_metainfo({
                "infohash": self.tdef.get_infohash(),
                "name": self.tdef.get_name_as_unicode(),
                "url": self.tdef.get_url()
            })
        self.config.set_engineresumedata(resume_data)

        # Save it to file
        basename = hexlify(resume_data[b"info-hash"]).decode() + ".conf"
        Path(self.download_manager.get_checkpoint_dir()).mkdir(parents=True, exist_ok=True)
        filename = self.download_manager.get_checkpoint_dir() / basename
        self.config.config["download_defaults"]["name"] = self.tdef.get_name_as_unicode()  # store name (for debugging)
        try:
            self.config.write(filename)
        except OSError as e:
            self._logger.warning("%s: %s", e.__class__.__name__, str(e))
        else:
            self._logger.debug("Resume data has been saved to: %s", filename)

    def on_tracker_reply_alert(self, alert: lt.tracker_reply_alert) -> None:
        """
        Handle a tracker reply alert.
        """
        self._logger.info("On tracker reply alert: %s", repr(alert))

        self.tracker_status[alert.url] = (alert.num_peers, 'Working')

    def on_tracker_error_alert(self, alert: lt.tracker_error_alert) -> None:
        """
        This alert is generated on tracker timeouts, premature disconnects, invalid response
        or an HTTP response other than "200 OK". - From Libtorrent documentation.
        """
        # The try-except block is added as a workaround to suppress UnicodeDecodeError in `repr(alert)`,
        # `alert.url` and `alert.msg`. See https://github.com/arvidn/libtorrent/issues/143
        self._logger.error("On tracker error alert: %s", repr(alert))
        url = alert.url

        if alert.msg:
            status = "Error: " + alert.msg
        elif alert.status_code > 0:
            status = f"HTTP status code {alert.status_code:d}"
        elif alert.status_code == 0:
            status = "Timeout"
        else:
            status = "Not working"

        peers = 0  # If there is a tracker error, alert.num_peers is not available. So resetting peer count to zero.
        self.tracker_status[url] = (peers, status)

    def on_tracker_warning_alert(self, alert: lt.tracker_warning_alert) -> None:
        """
        Handle a tracker warning alert.
        """
        self._logger.warning("On tracker warning alert: %s", repr(alert))

        peers = self.tracker_status[alert.url][0] if alert.url in self.tracker_status else 0
        status = "Warning: " + str(alert.message())

        self.tracker_status[alert.url] = (peers, status)

    @check_handle(None)
    def on_metadata_received_alert(self, alert: lt.metadata_received_alert) -> None:
        """
        Handle a metadata received alert.
        """
        self._logger.info("On metadata received alert: %s", repr(alert))
        self.handle = cast(lt.torrent_handle, self.handle)

        torrent_info = get_info_from_handle(self.handle)
        if not torrent_info:
            return

        try:
            metadata = cast(MetainfoDict, {b"info": lt.bdecode(torrent_info.metadata())})
        except (RuntimeError, ValueError) as e:
            self._logger.warning(e)
            return

        tracker_urls = []
        trackers = []
        try:
            trackers = self.handle.trackers()
        except UnicodeDecodeError as e:
            self._logger.warning(e)
        for tracker in trackers:
            url = tracker["url"]
            try:
                tracker_urls.append(url.encode())
            except UnicodeEncodeError as e:
                self._logger.warning(e)

        if len(tracker_urls) > 1:
            metadata[b"announce-list"] = [[tracker] for tracker in tracker_urls]
        elif tracker_urls:
            metadata[b"announce"] = tracker_urls[0]

        try:
            self.tdef = TorrentDef.load_from_dict(metadata)
            with suppress(RuntimeError):
                # Try to load the torrent info in the background if we have a loop.
                get_running_loop().run_in_executor(None, self.tdef.load_torrent_info)
        except ValueError as ve:
            self._logger.exception(ve)
            return

        self.set_selected_files()
        self.checkpoint()

    def on_performance_alert(self, alert: lt.performance_alert) -> None:
        """
        Handle a performance alert.
        """
        self._logger.info("On performance alert: %s", repr(alert))

        if self.get_anon_mode() or self.download_manager.ltsessions is None:
            return

        # When the send buffer watermark is too low, double the buffer size to a
        # maximum of 50MiB. This is the same mechanism as Deluge uses.
        lt_session = self.download_manager.get_session(self.config.get_hops()).result()
        settings = self.download_manager.get_session_settings(lt_session)
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            if settings["send_buffer_watermark"] <= 26214400:
                self._logger.info("Setting send_buffer_watermark to %s", 2 * settings["send_buffer_watermark"])
                settings["send_buffer_watermark"] *= 2
                self.download_manager.set_session_settings(self.download_manager.get_session().result(), settings)
        # When the write cache is too small, double the buffer size to a maximum
        # of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif (alert.message().endswith("max outstanding disk writes reached")
              and settings["max_queued_disk_bytes"] <= 33554432):
            self._logger.info("Setting max_queued_disk_bytes to %s", 2 * settings["max_queued_disk_bytes"])
            settings["max_queued_disk_bytes"] *= 2
            self.download_manager.set_session_settings(self.download_manager.get_session().result(), settings)

    def on_torrent_removed_alert(self, alert: lt.torrent_removed_alert) -> None:
        """
        Handle a torrent removed alert.
        """
        self._logger.info("On torrent remove alert: %s", repr(alert))

        self._logger.debug("Removing %s", self.tdef.get_name())
        self.handle = None

    def on_torrent_checked_alert(self, alert: lt.torrent_checked_alert) -> None:
        """
        Handle a torrent checked alert.
        """
        self._logger.info("On torrent checked alert: %s", repr(alert))

        if self.pause_after_next_hashcheck and self.handle:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    @check_handle(None)
    def on_torrent_finished_alert(self, alert: lt.torrent_finished_alert) -> None:
        """
        Handle a torrent finished alert.
        """
        self._logger.info("On torrent finished alert: %s", repr(alert))
        self.handle = cast(lt.torrent_handle, self.handle)
        self.update_lt_status(self.handle.status())
        self.checkpoint()
        downloaded = self.get_state().total_download
        if downloaded > 0 and self.notifier is not None:
            name = self.tdef.get_name_as_unicode()
            infohash = self.tdef.get_infohash().hex()
            self.notifier.notify(Notification.torrent_finished, infohash=infohash, name=name, hidden=self.hidden)

        if self.config.get_completed_dir() and self.config.get_completed_dir() != self.config.get_dest_dir():
            self.move_storage(Path(self.config.get_completed_dir()))

    def update_lt_status(self, lt_status: lt.torrent_status) -> None:
        """
        Update libtorrent stats and check if the download should be stopped.
        """
        old_status = self.get_state().get_status()

        self.lt_status = lt_status
        state = self.get_state()

        # Notify the GUI if the status has changed
        if self.notifier and not self.hidden and state.get_status() != old_status:
            self.notifier.notify(Notification.torrent_status_changed,
                                 infohash=hexlify(self.tdef.get_infohash()).decode(),
                                 status=state.get_status().name)

        if state.get_status() == DownloadStatus.SEEDING:
            mode = self.download_manager.config.get("libtorrent/download_defaults/seeding_mode")
            seeding_ratio = self.download_manager.config.get("libtorrent/download_defaults/seeding_ratio")
            seeding_time = self.download_manager.config.get("libtorrent/download_defaults/seeding_time")
            if (mode == "never" or
                    (mode == "ratio" and state.get_all_time_ratio() >= seeding_ratio) or
                    (mode == "time" and state.get_seeding_time() >= seeding_time)):
                self.stop()

    @check_handle(None)
    def set_selected_files(self, selected_files: list[int] | None = None, prio: int = 4,
                           force: bool = False) -> int | None:
        """
        Set the selected files. If the selected files is None or empty, all files will be selected.
        """
        if not force and self.stream is not None:
            return None
        if not isinstance(self.tdef, TorrentDefNoMetainfo) and not self.get_share_mode():
            if selected_files is None:
                selected_files = self.config.get_selected_files()
            else:
                self.config.set_selected_files(selected_files)

            tree = self.tdef.torrent_file_tree
            total_files = self.tdef.torrent_info.num_files()

            if not selected_files:
                selected_files = list(range(total_files))

            def map_selected(index: int) -> int:
                file_instance = tree.find(Path(tree.file_storage.file_path(index)))
                if index in selected_files:
                    file_instance.selected = True
                    return prio
                file_instance.selected = False
                return 0

            self.set_file_priorities(list(map(map_selected, range(total_files))))
        return None

    @check_handle(False)
    def move_storage(self, new_dir: Path) -> bool:
        """
        Move the output files to a different location.
        """
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.handle = cast(lt.torrent_handle, self.handle)
            self.handle.move_storage(str(new_dir))
        self.config.set_dest_dir(new_dir)
        self.config.set_completed_dir(new_dir)
        return True

    @check_handle(None)
    def force_recheck(self) -> None:
        """
        Force libtorrent to validate the files.
        """
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.handle = cast(lt.torrent_handle, self.handle)
            if self.get_state().get_status() == DownloadStatus.STOPPED:
                self.pause_after_next_hashcheck = True
            self.checkpoint_after_next_hashcheck = True
            self.handle.resume()
            self.handle.force_recheck()

    def get_state(self) -> DownloadState:
        """
        Returns a snapshot of the current state of the download.
        """
        return DownloadState(self, self.lt_status, self.error)

    @task
    async def save_resume_data(self, timeout: int = 10) -> None:
        """
        Save the resume data of a download. This method returns when the resume data is available.
        Note that this method only calls save_resume_data once on subsequent calls.
        """
        if "save_resume_data" not in self.futures:
            handle = await self.get_handle()
            handle.save_resume_data()

        try:
            await wait_for(self.wait_for_alert("save_resume_data_alert", None,
                                               "save_resume_data_failed_alert",
                                               lambda a: SaveResumeDataError(a.error.message())), timeout=timeout)
        except (CancelledError, SaveResumeDataError, TimeoutError, asyncio.exceptions.TimeoutError) as e:
            self._logger.exception("Resume data failed to save: %s", e)

    def get_peer_list(self, include_have: bool = True) -> list[PeerDict | PeerDictHave]:
        """
        Returns a list of dictionaries, one for each connected peer containing the statistics for that peer.
        In particular, the dictionary contains the keys.
        """
        peers = []
        peer_infos = self.handle.get_peer_info() if self.handle and self.handle.is_valid() else []
        for peer_info in peer_infos:
            try:
                extended_version = peer_info.client
            except UnicodeDecodeError:
                extended_version = b"unknown"
            peer_dict: PeerDict | PeerDictHave = cast(PeerDict, {
                "id": hexlify(peer_info.pid.to_bytes()).decode(),
                "extended_version": extended_version,
                "ip": peer_info.ip[0],
                "port": peer_info.ip[1],
                # optimistic_unchoke = 0x800 seems unavailable in python bindings
                "optimistic": bool(peer_info.flags & 0x800),
                "direction": "L" if bool(peer_info.flags & peer_info.local_connection) else "R",
                "uprate": peer_info.payload_up_speed,
                "uinterested": bool(peer_info.flags & peer_info.remote_interested),
                "uchoked": bool(peer_info.flags & peer_info.remote_choked),
                "uhasqueries": peer_info.upload_queue_length > 0,
                "uflushed": peer_info.used_send_buffer > 0,
                "downrate": peer_info.payload_down_speed,
                "dinterested": bool(peer_info.flags & peer_info.interesting),
                "dchoked": bool(peer_info.flags & peer_info.choked),
                "snubbed": bool(peer_info.flags & 0x1000),
                "utotal": peer_info.total_upload,
                "dtotal": peer_info.total_download,
                "completed": peer_info.progress,
                "speed": peer_info.remote_dl_rate,
                "connection_type": peer_info.connection_type,  # type: ignore[attr-defined] # shortcoming of stubs
                "seed": bool(peer_info.flags & peer_info.seed),
                "upload_only": bool(peer_info.flags & peer_info.upload_only)
            })
            if include_have:
                peer_dict = cast(PeerDictHave, peer_dict)
                peer_dict["have"] = peer_info.pieces
            peers.append(peer_dict)
        return peers

    def get_num_connected_seeds_peers(self) -> tuple[int, int]:
        """
        Return the number of connected seeders and leechers.
        """
        num_seeds = num_peers = 0
        if not self.handle or not self.handle.is_valid():
            return 0, 0

        for peer_info in self.handle.get_peer_info():
            if peer_info.flags & peer_info.seed:
                num_seeds += 1
            else:
                num_peers += 1

        return num_seeds, num_peers

    def get_torrent(self) -> dict[bytes, Any] | None:
        """
        Create the raw torrent data from this download.
        """
        if not self.handle or not self.handle.is_valid() or not self.handle.has_metadata():
            return None

        torrent_info = get_info_from_handle(self.handle)
        t = lt.create_torrent(torrent_info)
        return t.generate()

    @check_handle(default={})
    def get_tracker_status(self) -> dict[str, tuple[int, str]]:
        """
        Retrieve an overview of the trackers and their statuses.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        # Make sure all trackers are in the tracker_status dict
        try:
            tracker_urls = {tracker["url"] for tracker in self.handle.trackers()}
            for removed in (set(self.tracker_status.keys()) - tracker_urls):
                self.tracker_status.pop(removed)
            for tracker_url in tracker_urls:
                if tracker_url not in self.tracker_status:
                    self.tracker_status[tracker_url] = (0, "Not contacted yet")
        except UnicodeDecodeError:
            self._logger.warning("UnicodeDecodeError in get_tracker_status")

        # Count DHT and PeX peers
        dht_peers = pex_peers = 0
        peer_info = []

        try:
            peer_info = self.handle.get_peer_info()
        except Exception as e:
            self._logger.exception(e)

        for info in peer_info:
            if info.source & info.dht:
                dht_peers += 1
            if info.source & info.pex:
                pex_peers += 1

        ltsession = self.download_manager.get_session(self.config.get_hops()).result()
        public = self.tdef and not self.tdef.is_private()

        result = self.tracker_status.copy()
        result["[DHT]"] = (dht_peers, "Working" if ltsession.is_dht_running() and public else "Disabled")
        result["[PeX]"] = (pex_peers, "Working")
        return result

    async def shutdown(self) -> None:
        """
        Shut down the download.
        """
        self._logger.info("Shutting down...")
        self.alert_handlers.clear()
        if self.stream is not None:
            self.stream.close()

        active_futures = [f for f, _, _ in itertools.chain(*self.futures.values()) if not f.done()]
        for future in active_futures:
            future.cancel()
        with suppress(CancelledError):
            await asyncio.gather(*active_futures)  # wait for futures to be actually cancelled
        self.futures.clear()
        await self.shutdown_task_manager()

    def stop(self, user_stopped: bool | None = None) -> Awaitable[None]:
        """
        Stop downloading the download.
        """
        self._logger.debug("Stopping %s", self.tdef.get_name())
        if self.stream is not None:
            self.stream.disable()
        if user_stopped is not None:
            self.config.set_user_stopped(user_stopped)
        if self.handle and self.handle.is_valid():
            self.handle.pause()
            return self.checkpoint()
        return succeed(None)

    def resume(self) -> None:
        """
        Resume downloading the download.
        """
        self._logger.debug("Resuming %s", self.tdef.get_name())

        self.config.set_user_stopped(False)

        if self.handle and self.handle.is_valid():
            self.handle.set_upload_mode(self.get_upload_mode())
            self.handle.resume()

    def get_content_dest(self) -> Path:
        """
        Returns the file to which the downloaded content is saved.
        """
        return self.config.get_dest_dir() / self.tdef.get_name_as_unicode()

    def checkpoint(self) -> Awaitable[None]:
        """
        Checkpoint this download. Returns when the checkpointing is completed.
        """
        if self.checkpoint_disabled:
            self._logger.debug("Ignoring checkpoint() call as checkpointing is disabled for this download")
            return succeed(None)

        if self.handle and self.handle.is_valid() and not self.handle.need_save_resume_data():
            self._logger.debug("Ignoring checkpoint() call as checkpointing is not needed")
            return succeed(None)

        if not self.handle or not self.handle.is_valid():
            # Libtorrent hasn't received or initialized this download yet
            # 1. Check if we have data for this infohash already (don't overwrite it if we do!)
            basename = hexlify(self.tdef.get_infohash()).decode() + ".conf"
            filename = Path(self.download_manager.get_checkpoint_dir() / basename)
            if not filename.is_file():
                # 2. If there is no saved data for this infohash, checkpoint it without data so we do not
                #    lose it when we crash or restart before the download becomes known.
                resume_data = self.config.get_engineresumedata() or {
                    b"file-format": b"libtorrent resume file",
                    b"file-version": 1,
                    b"info-hash": self.tdef.get_infohash()
                }
                self.post_alert("save_resume_data_alert", {"resume_data": resume_data})
            return succeed(None)
        return self.save_resume_data()

    def set_def(self, tdef: TorrentDef) -> None:
        """
        Set the torrent definition for this download.
        """
        self.tdef = tdef

    @check_handle(None)
    def add_trackers(self, trackers: list[bytes]) -> None:
        """
        Add the given trackers to the handle.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        for tracker in trackers:
            self.handle.add_tracker({"url": tracker, "verified": False})
        self.handle.force_reannounce()

    @check_handle(None)
    def get_magnet_link(self) -> str:
        """
        Generate a magnet link for our download.
        """
        return lt.make_magnet_uri(cast(lt.torrent_handle, self.handle))  # Ensured by ``check_handle``

    @require_handle
    def add_peer(self, addr: tuple[str, int]) -> None:
        """
        Add a peer address from 3rd source (not tracker, not DHT) to this download.

        :param addr: The (hostname_ip,port) tuple to connect to
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.connect_peer(addr, 0)

    @require_handle
    def add_url_seed(self, addr: str) -> None:
        """
        Add a URL seed to this download.

        :param addr: The URL address to connect to
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.add_url_seed(addr)

    @require_handle
    def set_priority(self, priority: int) -> None:
        """
        Set the priority of this download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.set_priority(priority)

    @require_handle
    def set_max_upload_rate(self, value: int) -> None:
        """
        Set the maximum upload rate of this download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.set_upload_limit(value * 1024)

    @require_handle
    def set_max_download_rate(self, value: int) -> None:
        """
        Set the maximum download rate of this download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.set_download_limit(value * 1024)

    @require_handle
    def apply_ip_filter(self, enable: bool) -> None:
        """
        Enable the IP filter on this download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.apply_ip_filter(enable)

    def get_share_mode(self) -> bool:
        """
        Get whether this download is in sharing mode.
        """
        return self.config.get_share_mode()

    @require_handle
    def set_share_mode(self, share_mode: bool) -> None:
        """
        Set whether this download is in sharing mode.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.config.set_share_mode(share_mode)
        self.handle.set_share_mode(share_mode)

    def get_upload_mode(self) -> bool:
        """
        Get whether this download is in upload mode.
        """
        return self.config.get_upload_mode()

    @require_handle
    def set_upload_mode(self, upload_mode: bool) -> None:
        """
        Set whether this download is in upload mode.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.config.set_upload_mode(upload_mode)
        self.handle.set_upload_mode(upload_mode)

    @require_handle
    def force_dht_announce(self) -> None:
        """
        Force announce thid download on the DHT.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.force_dht_announce()

    @require_handle
    def set_sequential_download(self, enable: bool) -> None:
        """
        Set this download to sequential download mode.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.set_sequential_download(enable)

    @check_handle(None)
    def set_piece_priorities(self, piece_priorities: list[int]) -> None:
        """
        Set the priority for all pieces in the download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.prioritize_pieces(piece_priorities)

    @check_handle([])
    def get_piece_priorities(self) -> list[int]:
        """
        Get the priorities of all pieces in the download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        return self.handle.piece_priorities()

    @check_handle(None)
    def set_file_priorities(self, file_priorities: list[int]) -> None:
        """
        Set the priority for all files in the download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.prioritize_files(file_priorities)

    @check_handle(None)
    def set_file_priority(self, file_index: int, prio: int = 4) -> None:
        """
        Set the priority for a particular file in the download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.file_priority(file_index, prio)

    @check_handle(None)
    def reset_piece_deadline(self, piece: int) -> None:
        """
        Reset the deadline for the given piece.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.reset_piece_deadline(piece)

    @check_handle(None)
    def set_piece_deadline(self, piece: int, deadline: int, flags: int = 0) -> None:
        """
        Set the deadline for a given piece.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        self.handle.set_piece_deadline(piece, deadline, flags)

    @check_handle([])
    def get_file_priorities(self) -> list[int]:
        """
        Get the priorities of all files in the download.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        return self.handle.file_priorities()

    def file_piece_range(self, file_path: Path) -> list[int]:
        """
        Get the piece range of a given file, specified by the path.

        Calling this method with anything but a file path will return an empty list.
        """
        file_index = self.get_file_index(file_path)
        if file_index < 0:
            return []

        start_piece = self.tdef.torrent_info.map_file(file_index, 0, 1).piece
        # Note: next_piece contains the next piece that is NOT part of this file.
        if file_index < self.tdef.torrent_info.num_files() - 1:
            next_piece = self.tdef.torrent_info.map_file(file_index + 1, 0, 1).piece
        else:
            # There is no next file so the nex piece is the last piece index + 1 (num_pieces()).
            next_piece = self.tdef.torrent_info.num_pieces()

        if start_piece == next_piece:
            # A single piece with multiple files.
            return [start_piece]
        return list(range(start_piece, next_piece))

    @check_handle(0.0)
    def get_file_completion(self, path: Path) -> float:
        """
        Calculate the completion of a given file or directory.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        total = 0
        have = 0
        for piece_index in self.file_piece_range(path):
            have += self.handle.have_piece(piece_index)
            total += 1
        if total == 0:
            return 1.0
        return have / total

    def get_file_length(self, path: Path) -> int:
        """
        Get the length of a file or directory in bytes. Returns 0 if the given path does not point to an existing path.
        """
        result = self.tdef.torrent_file_tree.find(path)
        if result is not None:
            return result.size
        return 0

    def get_file_index(self, path: Path) -> int:
        """
        Get the index of a file or directory in a torrent. Note that directories do not have real file indices.

        Special cases ("error codes"):

         - ``-1`` (IllegalFileIndex.collapsed_dir): the given path is not a file but a collapsed directory.
         - ``-2`` (IllegalFileIndex.expanded_dir): the given path is not a file but an expanded directory.
         - ``-3`` (IllegalFileIndex.unloaded): the data structure is not loaded or the path is not found.
        """
        result = self.tdef.torrent_file_tree.find(path)
        if isinstance(result, TorrentFileTree.File):
            return self.tdef.torrent_file_tree.find(path).index
        if isinstance(result, TorrentFileTree.Directory):
            return (IllegalFileIndex.collapsed_dir.value if result.collapsed
                    else IllegalFileIndex.expanded_dir.value)
        return IllegalFileIndex.unloaded.value

    @check_handle(None)
    def set_selected_file_or_dir(self, path: Path, selected: bool) -> None:
        """
        Set a single file or directory to be selected or not.
        """
        self.handle = cast(lt.torrent_handle, self.handle)
        tree = self.tdef.torrent_file_tree
        prio = 4 if selected else 0
        for index in tree.set_selected(Path(path), selected):
            self.set_file_priority(index, prio)
            if not selected:
                with suppress(ValueError):
                    self.config.get_selected_files().remove(index)
            else:
                self.config.get_selected_files().append(index)

    def is_file_selected(self, file_path: Path) -> bool:
        """
        Check if the given file path is selected.

        Calling this method with anything but a file path will return False.
        """
        result = self.tdef.torrent_file_tree.find(file_path)
        if isinstance(result, TorrentFileTree.File):
            return result.selected
        return False
