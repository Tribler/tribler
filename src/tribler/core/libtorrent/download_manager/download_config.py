from __future__ import annotations

import base64
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Dict

import libtorrent as lt
from configobj import ConfigObj
from validate import Validator

if TYPE_CHECKING:
    from tribler.tribler_config import TriblerConfigManager

SPEC_FILENAME = 'download_config.spec'
SPEC_CONTENT = """[download_defaults]
hops = integer(default=0)
selected_files = string_list(default=list())
selected_file_indexes = int_list(default=list())
safe_seeding = boolean(default=False)
user_stopped = boolean(default=False)
share_mode = boolean(default=False)
upload_mode = boolean(default=False)
time_added = integer(default=0)
bootstrap_download = boolean(default=False)
channel_download = boolean(default=False)
add_download_to_channel = boolean(default=False)
saveas = string(default=None)

[state]
metainfo = string(default='ZGU=')
engineresumedata = string(default='ZGU=')
"""


def _from_dict(value: Dict) -> str:
    binary = lt.bencode(value)
    base64_bytes = base64.b64encode(binary)
    return base64_bytes.decode()


def _to_dict(value: str) -> dict | None:
    binary = value.encode()
    # b'==' is added to avoid incorrect padding
    base64_bytes = base64.b64decode(binary + b"==")
    return lt.bdecode(base64_bytes)


class DownloadConfig:
    """
    A configuration belonging to a specific download.
    """

    def __init__(self, config: ConfigObj | None = None) -> None:
        """
        Create a download config from the given ConfigObj.
        """
        self.config = config

    @staticmethod
    def get_spec_file_name(settings: TriblerConfigManager) -> str:
        """
        Get the file name of the download spec.
        """
        return str(Path(settings.get("state_dir")) / SPEC_FILENAME)

    @staticmethod
    def from_defaults(settings: TriblerConfigManager) -> DownloadConfig:
        """
        Create a new download config from the given Tribler configuration.
        """
        spec_file_name = DownloadConfig.get_spec_file_name(settings)
        defaults = ConfigObj(StringIO(SPEC_CONTENT))
        defaults["filename"] = spec_file_name
        with open(spec_file_name, "wb") as spec_file:
            defaults.write(spec_file)
        defaults = ConfigObj(StringIO(), configspec=spec_file_name)
        defaults.validate(Validator())
        config = DownloadConfig(defaults)

        config.set_hops(int(settings.get("libtorrent/download_defaults/number_hops")))
        config.set_safe_seeding(settings.get("libtorrent/download_defaults/safeseeding_enabled"))
        config.set_dest_dir(settings.get("libtorrent/download_defaults/saveas"))

        return config

    def copy(self) -> DownloadConfig:
        """
        Create a copy of this config.
        """
        return DownloadConfig(ConfigObj(self.config))

    def write(self, filename: Path) -> None:
        """
        Write the contents of this config to a file.
        """
        self.config.filename = Path(filename)
        self.config.write()

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
        dest_dir = self.config["download_defaults"]["saveas"]
        return Path(dest_dir)

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

    def set_selected_files(self, file_indexes: list[int]) -> None:
        """
        Select which files in the torrent to download.

        :param file_indexes: List of file indexes as ordered in the torrent (e.g. [0,1])
        """
        self.config["download_defaults"]["selected_file_indexes"] = file_indexes

    def get_selected_files(self) -> list[int]:
        """
        Returns the list of files selected for download.

        :return: A list of file indexes.
        """
        return self.config["download_defaults"]["selected_file_indexes"]

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

    def set_engineresumedata(self, engineresumedata: dict) -> None:
        """
        Set the engine resume data dict for this download.
        """
        self.config["state"]["engineresumedata"] = _from_dict(engineresumedata)

    def get_engineresumedata(self) -> dict | None:
        """
        Get the engine resume data dict for this download or None if it cannot be decoded.
        """
        return _to_dict(self.config["state"]["engineresumedata"])
