"""
A wrapper around a libtorrent download.

Author(s): Arno Bakker, Egbert Bouman
"""
from __future__ import annotations

import asyncio
import base64
import itertools
import logging
from asyncio import CancelledError, Future, sleep, wait_for
from binascii import hexlify
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

import libtorrent as lt
from ipv8.taskmanager import TaskManager, task
from ipv8.util import succeed

from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_state import DownloadState, DownloadStatus
from tribler.core.libtorrent.download_manager.stream import Stream
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.libtorrent.torrents import check_handle, get_info_from_handle, require_handle
from tribler.core.notifier import Notification, Notifier
from tribler.tribler_config import TriblerConfigManager

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
    from tribler.core.libtorrent.torrentdef import MetainfoDict

Getter = Callable[[Any], Any]


class SaveResumeDataError(Exception):
    """This error is used when the resume data of a download fails to save."""


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

        if self.download_manager.config.get("libtorrent/check_after_complete"):
            self.register_task("Recheck torrent after finish", self._recheck_after_finish)

        if config and config.get_stop_after_metainfo():
            self.stop_after_metainfo()

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

        self._logger.debug("Setup: %s", hexlify(self.tdef.infohash).decode())

        self.checkpoint()

    def __str__(self) -> str:
        """
        Convert this download to a human-readable string.
        """
        return (f"Download(name={self.tdef.name}, "
                f"hops={self.config.get_hops():d}, "
                f"checkpoint_disabled={self.checkpoint_disabled:d})")

    def __repr__(self) -> str:
        """
        Convert this download to a print-safe human-readable string.
        """
        return self.__str__()

    async def _recheck_after_finish(self) -> None:
        """
        Wait for the torrent to finish downloading, then recheck.

        Note: a finished recheck causes a ``torrent_finished_alert``: hooking into that causes an infinite loop!
        Note2: our own self.lt_status is too old.
        Note3: the state flip-flops too much to be reliable so we use completed_time instead.
        """
        await self.future_added
        handle = await self.get_handle()  # This should be available after adding the torrent
        if handle.status().completed_time != 0:
            self._logger.info("Skipping recheck of %s, already finished when added!", str(self))
            return
        await self.future_finished
        self._logger.info("Force rechecking %s after completion!", str(self))
        self.force_recheck()

    @task
    async def stop_after_metainfo(self) -> None:
        """
        Wait for the metadata to be received, then stop.
        """
        self.config.set_stop_after_metainfo(True)  # Persist between restarts
        await self.future_metainfo
        await self.stop()
        self.config.set_stop_after_metainfo(False)  # We succeeded without shutdown: no longer persist

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

    def on_add_torrent_alert(self, alert: lt.add_torrent_alert) -> None:
        """
        Handle an add torrent alert.
        """
        self._logger.info("On add torrent alert: %s", str(alert))

        if hasattr(alert, "error") and alert.error.value():
            self._logger.error("Failed to add torrent (%s)", self.tdef.name)
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
    def get_pieces_base64(self, handle: lt.torrent_handle) -> bytes:
        """
        Returns a base64 encoded bitmask of the pieces that we have.
        """
        pieces = handle.status().pieces
        return base64.b64encode(bytes(sum(piece << (7 - (index % 8)) for index, piece in enumerate(pieces[i:i+8]))
                                      for i in range(0, len(pieces), 8)))

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
                self._logger.debug("Got alert: %s", str(alert))

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
                                   e.__class__.__name__, str(e), str(alert))

    def on_torrent_error_alert(self, alert: lt.torrent_error_alert) -> None:
        """
        Handle a torrent error alert.
        """
        self._logger.info("On torrent error alert: %s", str(alert))

    def on_state_changed_alert(self, alert: lt.state_changed_alert) -> None:
        """
        Handle a state change alert.
        """
        self._logger.info("On state changed alert: %s", str(alert))

        if not self.handle:
            return
        self.update_lt_status(self.handle.status())

        enable = alert.state == lt.torrent_status.seeding and self.config.get_hops() > 0
        self._logger.debug("Setting IP filter for %s to %s", hexlify(self.tdef.infohash), enable)
        self.apply_ip_filter(enable)

        # On a rare occasion we don't get a metadata_received_alert. If this is the case, post an alert manually.
        if alert.state == lt.torrent_status.downloading and self.tdef.torrent_info is None:
            self.post_alert("metadata_received_alert")

    def on_save_resume_data_alert(self, alert: lt.save_resume_data_alert) -> None:
        """
        Callback for the alert that contains the resume data of a specific download.
        This resume data will be written to a file on disk.
        """
        self._logger.debug("On save resume data alert: %s", str(alert))
        if self.checkpoint_disabled:
            return

        resume_data = alert.params
        # Make save_path relative if the torrent is saved in the Tribler state directory
        if self.state_dir:
            save_path = Path(resume_data.save_path).absolute()
            resume_data.save_path = str(save_path)

        if self.tdef.torrent_info is not None:
            self.config.set_metainfo(self.tdef.get_metainfo())
        else:
            self.config.set_metainfo({
                "infohash": self.tdef.infohash,
                "name": self.tdef.name,
                "url": self.tdef.atp.url
            })
        self.config.set_engineresumedata(resume_data)

        # Save it to file
        basename = hexlify(self.tdef.infohash).decode() + ".conf"
        Path(self.download_manager.get_checkpoint_dir()).mkdir(parents=True, exist_ok=True)
        filename = self.download_manager.get_checkpoint_dir() / basename
        self.config.config["download_defaults"]["name"] = self.tdef.name  # store name (for debugging)
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
        self._logger.info("On tracker reply alert: %s", str(alert))

        self.tracker_status[alert.url] = (alert.num_peers, 'Working')

    def on_tracker_error_alert(self, alert: lt.tracker_error_alert) -> None:
        """
        This alert is generated on tracker timeouts, premature disconnects, invalid response
        or an HTTP response other than "200 OK". - From Libtorrent documentation.
        """
        self._logger.info("On tracker error alert: %s", str(alert))
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
        self._logger.warning("On tracker warning alert: %s", str(alert))

        peers = self.tracker_status[alert.url][0] if alert.url in self.tracker_status else 0
        status = "Warning: " + str(alert.message())

        self.tracker_status[alert.url] = (peers, status)

    @check_handle(None)
    def on_metadata_received_alert(self, handle: lt.torrent_handle, alert: lt.metadata_received_alert) -> None:
        """
        Handle a metadata received alert.
        """
        self._logger.info("On metadata received alert: %s", str(alert))

        torrent_info = get_info_from_handle(handle)
        if not torrent_info:
            return

        try:
            metadata = cast("MetainfoDict", {b"info": lt.bdecode(torrent_info.metadata())})
        except (RuntimeError, ValueError) as e:
            self._logger.warning(e)
            return

        tracker_urls = []
        trackers = []
        try:
            trackers = handle.trackers()
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
            self.set_def(TorrentDef.load_from_dict(metadata))
        except ValueError as ve:
            self._logger.exception(ve)
            return

        self.set_selected_files()
        self.checkpoint()

    def on_performance_alert(self, alert: lt.performance_alert) -> None:
        """
        Handle a performance alert.
        """
        self._logger.info("On performance alert: %s", str(alert))

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
        self._logger.info("On torrent remove alert: %s", str(alert))

        self._logger.debug("Removing %s", self.tdef.name)
        self.handle = None

    def on_torrent_checked_alert(self, alert: lt.torrent_checked_alert) -> None:
        """
        Handle a torrent checked alert.
        """
        self._logger.info("On torrent checked alert: %s", str(alert))

        if self.pause_after_next_hashcheck and self.handle:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    @check_handle(None)
    def on_torrent_finished_alert(self, handle: lt.torrent_handle, alert: lt.torrent_finished_alert) -> None:
        """
        Handle a torrent finished alert.
        """
        self._logger.info("On torrent finished alert: %s", str(alert))
        self.update_lt_status(handle.status())
        self.checkpoint()
        downloaded = self.get_state().total_download
        if downloaded > 0 and self.notifier is not None:
            name = self.tdef.name
            infohash = self.tdef.infohash.hex()
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
                                 infohash=hexlify(self.tdef.infohash).decode(),
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
    def set_selected_files(self, handle: lt.torrent_handle, selected_files: list[int] | None = None, prio: int = 4,
                           force: bool = False) -> int | None:
        """
        Set the selected files. If the selected files is None or empty, all files will be selected.
        """
        if not force and self.stream is not None:
            return None
        if self.tdef.torrent_info is not None and not self.get_share_mode():
            if selected_files is None:
                selected_files = self.config.get_selected_files()
            else:
                self.config.set_selected_files(selected_files)
            total_files = self.tdef.torrent_info.num_files()

            if not selected_files:
                selected_files = list(range(total_files))

            self.set_file_priorities([prio if index in selected_files else 0 for index in range(total_files)])
        return None

    @check_handle(False)
    def move_storage(self, handle: lt.torrent_handle, new_dir: Path) -> bool:
        """
        Move the output files to a different location.
        """
        if self.tdef.torrent_info is not None:
            handle.move_storage(str(new_dir))
        self.config.set_dest_dir(new_dir)
        self.config.set_completed_dir(new_dir)
        return True

    @check_handle(None)
    def force_recheck(self, handle: lt.torrent_handle) -> None:
        """
        Force libtorrent to validate the files.
        """
        if self.tdef.torrent_info is not None:
            if self.get_state().get_status() == DownloadStatus.STOPPED:
                self.pause_after_next_hashcheck = True
            self.checkpoint_after_next_hashcheck = True
            handle.resume()
            handle.force_recheck()

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
            peer_dict: PeerDict | PeerDictHave = cast("PeerDict", {
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
                "upload_only": bool(peer_info.flags & peer_info.upload_only),
                "from_dht": bool(peer_info.source & peer_info.dht),
                "from_pex": bool(peer_info.source & peer_info.pex),
                "from_lsd": bool(peer_info.source & peer_info.lsd)
            })
            if include_have:
                peer_dict = cast("PeerDictHave", peer_dict)
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
    def get_tracker_status(self, handle: lt.torrent_handle) -> dict[str, tuple[int, str]]:
        """
        Retrieve an overview of the trackers and their statuses.
        """
        # Make sure all trackers are in the tracker_status dict
        try:
            tracker_urls = {tracker["url"] for tracker in handle.trackers()}
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
            peer_info = handle.get_peer_info()
        except Exception as e:
            self._logger.exception(e)

        for info in peer_info:
            if info.source & info.dht:
                dht_peers += 1
            if info.source & info.pex:
                pex_peers += 1

        ltsession = self.download_manager.get_session(self.config.get_hops()).result()
        public = not (self.tdef and self.tdef.torrent_info and self.tdef.atp.ti.priv())

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
        self._logger.debug("Stopping %s", self.tdef.name)
        if self.stream is not None:
            self.stream.close()
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
        self._logger.debug("Resuming %s", self.tdef.name)

        self.config.set_user_stopped(False)

        if self.handle and self.handle.is_valid():
            self.handle.set_upload_mode(self.get_upload_mode())
            self.handle.resume()

    def get_content_dest(self) -> Path:
        """
        Returns the file to which the downloaded content is saved.
        """
        return self.config.get_dest_dir() / self.tdef.name

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
            basename = hexlify(self.tdef.infohash).decode() + ".conf"
            filename = Path(self.download_manager.get_checkpoint_dir() / basename)
            if not filename.is_file():
                # 2. If there is no saved data for this infohash, checkpoint it without data so we do not
                #    lose it when we crash or restart before the download becomes known.
                resume_data = self.config.get_engineresumedata()
                if resume_data is None:
                    resume_data = lt.add_torrent_params()
                    resume_data.info_hash = lt.sha1_hash(self.tdef.infohash)
                self.post_alert("save_resume_data_alert", {"params": resume_data})
            return succeed(None)
        return self.save_resume_data()

    def set_def(self, tdef: TorrentDef) -> None:
        """
        Set the torrent definition for this download.
        """
        if (self.tdef.torrent_info is None and tdef.torrent_info is not None
                and len(self.tdef.atp.info_hash.to_bytes()) != 20):
            # We store SHA-1 conf files. v2 torrents start with SHA-256 infohashes.
            basename = hexlify(self.tdef.atp.info_hash.to_bytes()).decode() + ".conf"
            Path(self.download_manager.get_checkpoint_dir() / basename).unlink(missing_ok=True)
        self.tdef = tdef

    @check_handle(None)
    def add_trackers(self, handle: lt.torrent_handle, trackers: list[bytes]) -> None:
        """
        Add the given trackers to the handle.
        """
        for tracker in trackers:
            handle.add_tracker({"url": tracker, "verified": False})
        handle.force_reannounce()

    @check_handle(None)
    def get_magnet_link(self, handle: lt.torrent_handle) -> str:
        """
        Generate a magnet link for our download.
        """
        return lt.make_magnet_uri(handle)

    @require_handle
    def add_peer(self, handle: lt.torrent_handle, addr: tuple[str, int]) -> None:
        """
        Add a peer address from 3rd source (not tracker, not DHT) to this download.

        :param addr: The (hostname_ip,port) tuple to connect to
        """
        handle.connect_peer(addr, 0)

    @require_handle
    def add_url_seed(self, handle: lt.torrent_handle, addr: str) -> None:
        """
        Add a URL seed to this download.

        :param addr: The URL address to connect to
        """
        handle.add_url_seed(addr)

    @require_handle
    def set_priority(self, handle: lt.torrent_handle, priority: int) -> None:
        """
        Set the priority of this download.
        """
        handle.set_priority(priority)

    @require_handle
    def set_max_upload_rate(self, handle: lt.torrent_handle, value: int) -> None:
        """
        Set the maximum upload rate of this download.
        """
        handle.set_upload_limit(value * 1024)

    @require_handle
    def set_max_download_rate(self, handle: lt.torrent_handle, value: int) -> None:
        """
        Set the maximum download rate of this download.
        """
        handle.set_download_limit(value * 1024)

    @require_handle
    def apply_ip_filter(self, handle: lt.torrent_handle, enable: bool) -> None:
        """
        Enable the IP filter on this download.
        """
        handle.apply_ip_filter(enable)

    def get_share_mode(self) -> bool:
        """
        Get whether this download is in sharing mode.
        """
        return self.config.get_share_mode()

    @require_handle
    def set_share_mode(self, handle: lt.torrent_handle, share_mode: bool) -> None:
        """
        Set whether this download is in sharing mode.
        """
        self.config.set_share_mode(share_mode)
        handle.set_share_mode(share_mode)

    def get_upload_mode(self) -> bool:
        """
        Get whether this download is in upload mode.
        """
        return self.config.get_upload_mode()

    @require_handle
    def set_upload_mode(self, handle: lt.torrent_handle, upload_mode: bool) -> None:
        """
        Set whether this download is in upload mode.
        """
        self.config.set_upload_mode(upload_mode)
        handle.set_upload_mode(upload_mode)

    @require_handle
    def force_dht_announce(self, handle: lt.torrent_handle) -> None:
        """
        Force announce thid download on the DHT.
        """
        handle.force_dht_announce()

    @require_handle
    def set_sequential_download(self, handle: lt.torrent_handle, enable: bool) -> None:
        """
        Set this download to sequential download mode.
        """
        handle.set_sequential_download(enable)

    @check_handle(None)
    def set_piece_priorities(self, handle: lt.torrent_handle, piece_priorities: list[int]) -> None:
        """
        Set the priority for all pieces in the download.
        """
        handle.prioritize_pieces(piece_priorities)

    @check_handle([])
    def get_piece_priorities(self, handle: lt.torrent_handle) -> list[int]:
        """
        Get the priorities of all pieces in the download.
        """
        return handle.piece_priorities()

    @check_handle(None)
    def set_file_priorities(self, handle: lt.torrent_handle, file_priorities: list[int]) -> None:
        """
        Set the priority for all files in the download.
        """
        handle.prioritize_files(file_priorities)

    @check_handle(None)
    def set_file_priority(self, handle: lt.torrent_handle, file_index: int, prio: int = 4) -> None:
        """
        Set the priority for a particular file in the download.
        """
        handle.file_priority(file_index, prio)

    @check_handle(None)
    def reset_piece_deadline(self, handle: lt.torrent_handle, piece: int) -> None:
        """
        Reset the deadline for the given piece.
        """
        handle.reset_piece_deadline(piece)

    @check_handle(None)
    def set_piece_deadline(self, handle: lt.torrent_handle, piece: int, deadline: int, flags: int = 0) -> None:
        """
        Set the deadline for a given piece.
        """
        handle.set_piece_deadline(piece, deadline, flags)

    @check_handle([])
    def get_file_priorities(self, handle: lt.torrent_handle) -> list[int]:
        """
        Get the priorities of all files in the download.
        """
        return handle.file_priorities()

    def file_piece_range(self, file_path: Path) -> list[int]:
        """
        Get the piece range of a given file, specified by the path.

        Calling this method with anything but a file path will return an empty list.
        """
        file_index = self.get_file_index(file_path)
        if file_index is None:
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
    def get_file_completion(self, handle: lt.torrent_handle, path: Path) -> float:
        """
        Calculate the completion of a given file or directory.
        """
        total = 0
        have = 0
        for piece_index in self.file_piece_range(path):
            have += handle.have_piece(piece_index)
            total += 1
        if total == 0:
            return 1.0
        return have / total

    def get_file_length(self, path: Path) -> int:
        """
        Get the length of a file or directory in bytes. Returns 0 if the given path does not point to an existing path.
        """
        result = self.get_file_index(path)
        if result is not None:
            return self.tdef.torrent_info.file_at(result).size
        return 0

    def get_file_index(self, path: Path) -> int | None:
        """
        Get the index of a file or directory in a torrent, or None if it does not exist.
        """
        if not self.tdef.torrent_info:
            return None
        num_files = self.tdef.torrent_info.num_files()
        if num_files > 1:
            for file_index in range(num_files):
                if (Path(self.tdef.torrent_info.file_at(file_index).path).relative_to(self.tdef.torrent_info.name())
                        == path):
                    return file_index
        elif Path(self.tdef.torrent_info.file_at(0).path) == path:
            return 0
        return None

    @check_handle(None)
    def set_selected_file_or_dir(self, handle: lt.torrent_handle, path: Path, selected: bool) -> None:
        """
        Set a single file or directory to be selected or not.
        """
        if not self.tdef.torrent_info:
            return

        previously_selected = self.config.get_selected_files()
        num_files = self.tdef.torrent_info.num_files()
        self.set_selected_files([
            (4 if selected else 0)
            if (Path(self.tdef.torrent_info.file_at(file_index).path).relative_to(self.tdef.torrent_info.name())
                if num_files > 1 else Path(self.tdef.torrent_info.file_at(file_index).path)).is_relative_to(path)
            else (4 if file_index in previously_selected else 0)
            for file_index in range(num_files)
        ])

    def is_file_selected(self, file_path: Path) -> bool:
        """
        Check if the given file path is selected.

        Calling this method with anything but a file path will lead to undefined behavior!
        """
        if not self.tdef.torrent_info:
            return False
        return (not self.config.get_selected_files()
                or self.get_file_index(file_path) in self.config.get_selected_files())

    async def set_upload_limit(self, value: int) -> None:
        """
        Set the upload bandwidth limit for this torrent.
        """
        handle = await self.get_handle()
        handle.set_upload_limit(value)
        self.config.set_upload_limit(value)

    def get_upload_limit(self) -> int:
        """
        Get the upload bandwidth limit for this torrent.
        """
        return self.config.get_upload_limit()

    async def set_download_limit(self, value: int) -> None:
        """
        Set the download bandwidth limit for this torrent.
        """
        handle = await self.get_handle()
        handle.set_download_limit(value)
        self.config.set_download_limit(value)

    def get_download_limit(self) -> int:
        """
        Get the download bandwidth limit for this torrent.
        """
        return self.config.get_download_limit()
