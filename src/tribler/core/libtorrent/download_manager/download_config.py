from __future__ import annotations

import base64
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast, overload

import libtorrent as lt
from configobj import ConfigObj
from validate import Validator

if TYPE_CHECKING:
    from tribler.tribler_config import TriblerConfigManager


    class DownloadConfigDefaultsSection(TypedDict):
        """
        The default config settings for a download.
        """

        hops: int
        files: list[int] | None
        safe_seeding: bool
        user_stopped: bool
        share_mode: bool
        upload_mode: bool
        time_added: int
        bootstrap_download: bool
        channel_download: bool
        add_download_to_channel: bool
        saveas: str | None
        completed_dir: str | None
        stop_after_metainfo: bool
        upload_limit: int
        download_limit: int
        auto_managed: bool


    class StateConfigSection(TypedDict):
        """
        The runtime state info of a download.
        """

        metainfo: str
        engineresumedata: str


    class DownloadConfigDict(dict):
        """
        All config settings in the config file.
        """

        @overload  # type: ignore[override]
        def __getitem__(self, key: Literal["filename"]) -> str: ...

        @overload
        def __getitem__(self, key: Literal["download_defaults"]) -> DownloadConfigDefaultsSection: ...

        @overload
        def __getitem__(self, key: Literal["state"]) -> StateConfigSection: ...

        def __getitem__(self, key: str) -> Any: ...  # noqa: D105

        def write(self) -> None: ...  # noqa: D102
else:
    DownloadConfigDict = ConfigObj


SPEC_FILENAME = 'download_config.spec'
SPEC_CONTENT = """[download_defaults]
hops = integer(default=0)
files = int_list(default=None)
safe_seeding = boolean(default=False)
user_stopped = boolean(default=False)
share_mode = boolean(default=False)
upload_mode = boolean(default=False)
time_added = integer(default=0)
bootstrap_download = boolean(default=False)
channel_download = boolean(default=False)
add_download_to_channel = boolean(default=False)
saveas = string(default=None)
completed_dir = string(default=None)
stop_after_metainfo = boolean(default=False)
upload_limit =  integer(default=-1)
download_limit =  integer(default=-1)
auto_managed = boolean(default=False)

[state]
metainfo = string(default='ZGU=')
engineresumedata = string(default='ZGU=')
"""


def _from_dict(value: dict) -> str:
    binary = lt.bencode(value)
    base64_bytes = base64.b64encode(binary)
    return base64_bytes.decode()


def _to_dict(value: str) -> dict[bytes, Any]:
    """
    Convert a string value to a libtorrent dict.

    :raises RuntimeError: if the value could not be converted.
    """
    binary = value.encode()
    # b'==' is added to avoid incorrect padding
    base64_bytes = base64.b64decode(binary + b"==")
    return cast("dict[bytes, Any]", lt.bdecode(base64_bytes))


class DownloadConfig:
    """
    A configuration belonging to a specific download.
    """

    def __init__(self, config: ConfigObj) -> None:
        """
        Create a download config from the given ConfigObj.
        """
        self.config: DownloadConfigDict = cast("DownloadConfigDict", config)

    @staticmethod
    def get_spec_file_name(settings: TriblerConfigManager) -> str:
        """
        Get the file name of the download spec.
        """
        return str(Path(settings.get_version_state_dir()) / SPEC_FILENAME)

    @staticmethod
    def from_defaults(settings: TriblerConfigManager) -> DownloadConfig:
        """
        Create a new download config from the given Tribler configuration.
        """
        spec_file_name = DownloadConfig.get_spec_file_name(settings)
        defaults = ConfigObj(StringIO(SPEC_CONTENT), encoding="utf-8")
        defaults["filename"] = spec_file_name
        Path(spec_file_name).parent.mkdir(parents=True, exist_ok=True)  # Required for the next write
        with open(spec_file_name, "wb") as spec_file:
            defaults.write(spec_file)
        defaults = ConfigObj(StringIO(), configspec=spec_file_name, encoding="utf-8")
        defaults.validate(Validator())
        config = DownloadConfig(defaults)

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
        return DownloadConfig(ConfigObj(self.config, encoding="utf-8"))

    def write(self, filename: Path) -> None:
        """
        Write the contents of this config to a file.
        """
        config_obj = cast("ConfigObj", self.config)
        config_obj.filename = str(filename)
        config_obj.write()

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
        dest_dir = self.config["download_defaults"]["saveas"] or ""
        return Path(dest_dir)

    def set_completed_dir(self, path: Path | str) -> None:
        """
        Sets the directory where to move this Download upon completion.

        :param path: A path of a directory.
        """
        self.config["download_defaults"]["completed_dir"] = str(path)

    def get_completed_dir(self) -> str | None:
        """
        Gets the directory where to move this Download upon completed.
        """
        return self.config["download_defaults"].get("completed_dir")

    def set_hops(self, hops: int) -> None:
        """
        Set the number of hops for the download.
        """
        self.config["download_defaults"]["hops"] = hops

    def get_hops(self) -> int:
        """
        Get the set number of hops for the download.
        """
        return self.config["download_defaults"]["hops"]

    def set_safe_seeding(self, value: bool) -> None:
        """
        Set the safe seeding mode of the download.
        """
        self.config["download_defaults"]["safe_seeding"] = value

    def get_safe_seeding(self) -> bool:
        """
        Get the safe seeding mode of the download.
        """
        return self.config["download_defaults"]["safe_seeding"]

    def set_user_stopped(self, value: bool) -> None:
        """
        Set whether the download has been stopped by the user.
        """
        self.config["download_defaults"]["user_stopped"] = value

    def get_user_stopped(self) -> bool:
        """
        Get whether the download has been stopped by the user.
        """
        return self.config["download_defaults"]["user_stopped"]

    def set_share_mode(self, value: bool) -> None:
        """
        Set whether the download is in sharing mode.
        """
        self.config["download_defaults"]["share_mode"] = value

    def get_share_mode(self) -> bool:
        """
        Get whether the download is in sharing mode.
        """
        return self.config["download_defaults"]["share_mode"]

    def set_upload_mode(self, value: bool) -> None:
        """
        Set whether the download is in upload-only mode.
        """
        self.config["download_defaults"]["upload_mode"] = value

    def get_upload_mode(self) -> bool:
        """
        Get whether the download is in upload-only mode.
        """
        return self.config["download_defaults"]["upload_mode"]

    def set_time_added(self, value: int) -> None:
        """
        Set the UNIX timestamp for when this download was added.
        """
        self.config["download_defaults"]["time_added"] = value

    def get_time_added(self) -> int:
        """
        Get the UNIX timestamp for when this download was added.
        """
        return self.config["download_defaults"]["time_added"]

    def set_selected_files(self, file_indexes: list[int] | None) -> None:
        """
        Select which files in the torrent to download.

        :param file_indexes: List of file indexes as ordered in the torrent (e.g. [0,1])
        """
        config_obj = cast("ConfigObj", self.config)
        if file_indexes is None:
            config_obj["download_defaults"].restore_default("files")
        else:
            config_obj["download_defaults"]["files"] = file_indexes

    def get_selected_files(self) -> list[int] | None:
        """
        Returns the list of files selected for download.

        :return: A list of file indexes.
        """
        return self.config["download_defaults"]["files"]

    def set_bootstrap_download(self, value: bool) -> None:
        """
        Mark this download as a bootstrap download.
        """
        self.config["download_defaults"]["bootstrap_download"] = value

    def get_bootstrap_download(self) -> bool:
        """
        Get whether this download is a bootstrap download.
        """
        return self.config["download_defaults"]["bootstrap_download"]

    def set_metainfo(self, metainfo: dict) -> None:
        """
        Set the metainfo dict for this download.
        """
        self.config["state"]["metainfo"] = _from_dict(metainfo)

    def get_metainfo(self) -> dict | None:
        """
        Get the metainfo dict for this download or None if it cannot be decoded.
        """
        return _to_dict(self.config["state"]["metainfo"])

    def set_engineresumedata(self, engineresumedata: lt.add_torrent_params) -> None:
        """
        Set the engine resume data dict for this download.
        """
        self.config["state"]["engineresumedata"] = base64.b64encode(lt.write_resume_data_buf(engineresumedata)).decode()

    def get_engineresumedata(self) -> lt.add_torrent_params | None:
        """
        Get the engine resume data dict for this download or None if it cannot be decoded.
        """
        resume_data = self.config["state"]["engineresumedata"]
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
        self.config["download_defaults"]["stop_after_metainfo"] = value

    def get_stop_after_metainfo(self) -> bool:
        """
        Get whether the download should stop after receiving the metainfo.
        """
        return self.config["download_defaults"].get("stop_after_metainfo", False)

    def set_upload_limit(self, value: int) -> None:
        """
        Set the upload bandwidth limit for this torrent.
        """
        self.config["download_defaults"]["upload_limit"] = value

    def get_upload_limit(self) -> int:
        """
        Get the upload bandwidth limit for this torrent.
        """
        return self.config["download_defaults"].get("upload_limit", False)

    def set_download_limit(self, value: int) -> None:
        """
        Set the download bandwidth limit for this torrent.
        """
        self.config["download_defaults"]["download_limit"] = value

    def get_download_limit(self) -> int:
        """
        Get the download bandwidth limit for this torrent.
        """
        return self.config["download_defaults"].get("download_limit", False)

    def set_auto_managed(self, value: bool) -> None:
        """
        Set auto managed flag.
        """
        self.config["download_defaults"]["auto_managed"] = value

    def get_auto_managed(self) -> bool:
        """
        Get auto managed flag.
        """
        return self.config["download_defaults"].get("auto_managed", False)
