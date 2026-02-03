from __future__ import annotations

import base64
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast

import libtorrent as lt

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from tribler.tribler_config import TriblerConfigManager


class DownloadConfigDefaultsSection(TypedDict):
    """
    The default config settings for a download.
    """

    hops: NotRequired[int]
    files: NotRequired[list[int]]
    safe_seeding: NotRequired[bool]
    user_stopped: NotRequired[bool]
    share_mode: NotRequired[bool]
    upload_mode: NotRequired[bool]
    time_added: NotRequired[int]
    bootstrap_download: NotRequired[bool]
    channel_download: NotRequired[bool]
    add_download_to_channel: NotRequired[bool]
    saveas: NotRequired[str]
    completed_dir: NotRequired[str]
    stop_after_metainfo: NotRequired[bool]
    upload_limit: NotRequired[int]
    download_limit: NotRequired[int]
    auto_managed: NotRequired[bool]
    name: NotRequired[str]
    seeding_ratio: NotRequired[float]


class StateConfigSection(TypedDict):
    """
    The runtime state info of a download.
    """

    metainfo: NotRequired[str]
    engineresumedata: NotRequired[str]
    post_handle_ops: NotRequired[int]


class DownloadConfigSection(TypedDict):
    """
    The config info of a download.
    """

    download_defaults: DownloadConfigDefaultsSection
    state: StateConfigSection


@dataclass
class PostHandleOp:
    """
    Human-readable post-download operations.
    """

    ADD_DEFAULT_TRACKERS = 1  # 2**0
    WRITE_BACKUP_TORRENT = 2  # 2**1


DEFAULTS = DownloadConfigSection(
    download_defaults=DownloadConfigDefaultsSection(
        hops=0, safe_seeding=False, user_stopped=False, share_mode=False, upload_mode=False, time_added=0,
        bootstrap_download=False, channel_download=False, add_download_to_channel=False, stop_after_metainfo=False,
        upload_limit=-1, download_limit=-1, auto_managed=False
    ),
    state=StateConfigSection(engineresumedata="ZGU=", post_handle_ops=0)
)
"""
The default values of the StateConfigSection dict. Missing keys have a default of ``None``.
"""


class DownloadConfig:
    """
    A configuration belonging to a specific download.

    A step-by-step to add to the config:
    1. Add your new config value somewhere in the ``DownloadConfigSection`` TypedDict hierarchy.
    2. Is your default value NOT None? Add the default to DEFAULTS.
    3. Create a getter and setter in this class.
    4. Is your default value NOT None? Add a fallback from DEFAULTS to your getter.

    Step (4) is to guarantee mypy that - even if a programmer forgets ``get_parser()`` - the output is correct.
    """

    def __init__(self, config: ConfigParser) -> None:
        """
        Create a download config from the given ConfigObj.
        """
        self.config = config

    @staticmethod
    def get_parser() -> ConfigParser:
        """
        Get a new  parser for Download config files.
        """
        parser = ConfigParser(default_section="download_defaults")
        parser.read_dict(cast("Mapping[str, Mapping[str, Any]]", DEFAULTS))
        return parser

    @staticmethod
    def read(file_path: str, into: DownloadConfig | None = None) -> DownloadConfig:
        """
        Get the file name of the download spec. Optionally, read into an existing DownloadConfig.
        """
        parser = into.config if into is not None else DownloadConfig.get_parser()
        with open(file_path) as f:
            parser.read_string(f.read())
        return into if into is not None else DownloadConfig(parser)

    @staticmethod
    def from_defaults(settings: TriblerConfigManager) -> DownloadConfig:
        """
        Create a new download config from the given Tribler configuration.
        """
        parser = DownloadConfig.get_parser()
        config = DownloadConfig(parser)

        if settings.get("libtorrent/download_defaults/anonymity_enabled"):
            config.set_hops(int(settings.get("libtorrent/download_defaults/number_hops")))
        else:
            config.set_hops(0)
        config.set_safe_seeding(settings.get("libtorrent/download_defaults/safeseeding_enabled"))
        config.set_dest_dir(settings.get("libtorrent/download_defaults/saveas"))
        if settings.get("libtorrent/download_defaults/completed_dir"):
            config.set_completed_dir(settings.get("libtorrent/download_defaults/completed_dir"))
        config.set_auto_managed(bool(settings.get("libtorrent/download_defaults/auto_managed")))

        return config

    def copy(self) -> DownloadConfig:
        """
        Create a copy of this config.
        """
        parser = DownloadConfig.get_parser()
        parser.read_dict(self.config)
        return DownloadConfig(parser)

    def write(self, filename: str) -> None:
        """
        Write the contents of this config to a file.
        """
        with open(filename, "w") as f:
            self.config.write(f)

    def set_dest_dir(self, path: Path | str) -> None:
        """
        Sets the directory where to save this Download.

        :param path: A path of a directory.
        """
        self.config["download_defaults"]["saveas"] = str(path)

    def get_dest_dir(self) -> Path:
        """
        Gets the directory where to save this Download.
        """
        return Path(self.config["download_defaults"].get("saveas") or "")

    def set_completed_dir(self, path: Path | str) -> None:
        """
        Sets the directory where to move this Download upon completion.

        :param path: A path of a directory.
        """
        self.config["download_defaults"]["completed_dir"] = str(path)

    def get_completed_dir(self) -> Path | None:
        """
        Gets the directory where to move this Download upon completed.
        """
        completed_dir = self.config["download_defaults"].get("completed_dir")
        return Path(completed_dir) if completed_dir else None

    def set_hops(self, hops: int) -> None:
        """
        Set the number of hops for the download.
        """
        self.config["download_defaults"]["hops"] = str(hops)

    def get_hops(self) -> int:
        """
        Get the set number of hops for the download.
        """
        return self.config["download_defaults"].getint("hops", fallback=DEFAULTS["download_defaults"]["hops"])

    def set_safe_seeding(self, value: bool) -> None:
        """
        Set the safe seeding mode of the download.
        """
        self.config["download_defaults"]["safe_seeding"] = str(value)

    def get_safe_seeding(self) -> bool:
        """
        Get the safe seeding mode of the download.
        """
        return self.config["download_defaults"].getboolean("safe_seeding",
                                                           fallback=DEFAULTS["download_defaults"]["safe_seeding"])

    def set_user_stopped(self, value: bool) -> None:
        """
        Set whether the download has been stopped by the user.
        """
        self.config["download_defaults"]["user_stopped"] = str(value)

    def get_user_stopped(self) -> bool:
        """
        Get whether the download has been stopped by the user.
        """
        return self.config["download_defaults"].getboolean("user_stopped",
                                                           fallback=DEFAULTS["download_defaults"]["user_stopped"])

    def set_share_mode(self, value: bool) -> None:
        """
        Set whether the download is in sharing mode.
        """
        self.config["download_defaults"]["share_mode"] = str(value)

    def get_share_mode(self) -> bool:
        """
        Get whether the download is in sharing mode.
        """
        return self.config["download_defaults"].getboolean("share_mode",
                                                           fallback=DEFAULTS["download_defaults"]["share_mode"])

    def set_upload_mode(self, value: bool) -> None:
        """
        Set whether the download is in upload-only mode.
        """
        self.config["download_defaults"]["upload_mode"] = str(value)

    def get_upload_mode(self) -> bool:
        """
        Get whether the download is in upload-only mode.
        """
        return self.config["download_defaults"].getboolean("upload_mode",
                                                           fallback=DEFAULTS["download_defaults"]["upload_mode"])

    def set_time_added(self, value: int) -> None:
        """
        Set the UNIX timestamp for when this download was added.
        """
        self.config["download_defaults"]["time_added"] = str(value)

    def get_time_added(self) -> int:
        """
        Get the UNIX timestamp for when this download was added.
        """
        return self.config["download_defaults"].getint("time_added",
                                                       fallback=DEFAULTS["download_defaults"]["time_added"])

    def set_selected_files(self, file_indexes: list[int] | None) -> None:
        """
        Select which files in the torrent to download.

        :param file_indexes: List of file indexes as ordered in the torrent (e.g. [0,1])
        """
        if file_indexes is None:
            self.config.remove_option("download_defaults", "files")
        else:
            self.config["download_defaults"]["files"] = ",".join(str(i) for i in file_indexes) + ","

    def get_selected_files(self) -> list[int] | None:
        """
        Returns the list of files selected for download.

        :return: A list of file indexes.
        """
        if self.config["download_defaults"].get("files"):
            return [int(i) for i in self.config["download_defaults"]["files"].split(",") if i]
        return None

    def set_bootstrap_download(self, value: bool) -> None:
        """
        Mark this download as a bootstrap download.
        """
        self.config["download_defaults"]["bootstrap_download"] = str(value)

    def get_bootstrap_download(self) -> bool:
        """
        Get whether this download is a bootstrap download.
        """
        return self.config["download_defaults"].getboolean("bootstrap_download",
                                                           fallback=DEFAULTS["download_defaults"]["bootstrap_download"])

    def set_engineresumedata(self, engineresumedata: lt.add_torrent_params) -> None:
        """
        Set the engine resume data dict for this download.
        """
        self.config["state"]["engineresumedata"] = base64.b64encode(lt.write_resume_data_buf(engineresumedata)).decode()

    def get_engineresumedata(self) -> lt.add_torrent_params | None:
        """
        Get the engine resume data dict for this download or None if it cannot be decoded.
        """
        resume_data = self.config["state"].get("engineresumedata")
        if resume_data:
            try:
                return lt.read_resume_data(base64.b64decode(resume_data))
            except RuntimeError:
                return None
        return None

    def set_stop_after_metainfo(self, value: bool) -> None:
        """
        Set the download to stop after receiving the metainfo.
        """
        self.config["download_defaults"]["stop_after_metainfo"] = str(value)

    def get_stop_after_metainfo(self) -> bool:
        """
        Get whether the download should stop after receiving the metainfo.
        """
        return self.config["download_defaults"].getboolean(
            "stop_after_metainfo",
            fallback=DEFAULTS["download_defaults"]["stop_after_metainfo"]
        )

    def set_upload_limit(self, value: int) -> None:
        """
        Set the upload bandwidth limit for this torrent.
        """
        self.config["download_defaults"]["upload_limit"] = str(value)

    def get_upload_limit(self) -> int:
        """
        Get the upload bandwidth limit for this torrent.
        """
        return self.config["download_defaults"].getint("upload_limit",
                                                       fallback=DEFAULTS["download_defaults"]["upload_limit"])

    def set_download_limit(self, value: int) -> None:
        """
        Set the download bandwidth limit for this torrent.
        """
        self.config["download_defaults"]["download_limit"] = str(value)

    def get_download_limit(self) -> int:
        """
        Get the download bandwidth limit for this torrent.
        """
        return self.config["download_defaults"].getint("download_limit",
                                                       fallback=DEFAULTS["download_defaults"]["download_limit"])

    def set_auto_managed(self, value: bool) -> None:
        """
        Set auto managed flag.
        """
        self.config["download_defaults"]["auto_managed"] = str(value)

    def get_auto_managed(self) -> bool:
        """
        Get auto managed flag.
        """
        return self.config["download_defaults"].getboolean("auto_managed",
                                                           fallback=DEFAULTS["download_defaults"]["auto_managed"])

    def set_seeding_ratio(self, value: float | None) -> None:
        """
        Set auto managed flag.
        """
        if value is None:
            self.config.remove_option("download_defaults", "seeding_ratio")
        else:
            self.config["download_defaults"]["seeding_ratio"] = str(value)

    def get_seeding_ratio(self) -> float | None:
        """
        Get auto managed flag.
        """
        return self.config["download_defaults"].getfloat("seeding_ratio")

    def set_post_handle_ops(self, value: int | list[int]) -> None:
        """
        Set the post-handle operations flag for this torrent.
        """
        if isinstance(value, int):
            self.config["state"]["post_handle_ops"] = str(value)
        else:
            self.config["state"]["post_handle_ops"] = str(sum(value))  # Same as bitwise or: all flags are 2**i

    def add_post_handle_op(self, value: int) -> None:
        """
        Add a single post-handle operation to the existing ones.
        """
        self.config["state"]["post_handle_ops"] = str(self.get_post_handle_ops() | value)

    def get_post_handle_ops(self) -> int:
        """
        Get the post-handle operations flag for this torrent.
        """
        return self.config["state"].getint("post_handle_ops", fallback=DEFAULTS["state"]["post_handle_ops"])
