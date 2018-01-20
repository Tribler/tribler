import ctypes
import logging
import os

import sys

import libtorrent

logger = logging.getLogger(__name__)


class DownloadHandle:
    """
    Holds a libtorrent download handle and interacts with it.
    """
    def __init__(self, handle):
        if isinstance(handle, DownloadHandle):
            raise Exception("x")

        self.libtorrent_handle = handle

    def add_trackers(self, trackers):
        for tracker in trackers:
            self.libtorrent_handle.add_tracker({'url': tracker, 'verified': False})

    def force_recheck(self):
        self.libtorrent_handle.resume()
        self.libtorrent_handle.force_recheck()

    def get_magnet_link(self):
        return libtorrent.make_magnet_uri(self.libtorrent_handle)

    def is_valid(self):
        return self.libtorrent_handle.is_valid()

    def get_file_priority(self, index):
        return self.libtorrent_handle.file_priority(index)

    def get_info(self):
        # In libtorrent 0.16.18, the torrent_handle.torrent_file method is not available.
        # this method checks whether the torrent_file method is available on a given handle.
        # If not, fall back on the deprecated get_torrent_info
        try:
            if hasattr(self.libtorrent_handle, 'torrent_file'):
                return self.libtorrent_handle.torrent_file()
            return self.libtorrent_handle.get_torrent_info()
        except RuntimeError as e:  # This can happen when the torrent handle is invalid.
            logger.warning("Got exception when fetching info from handle: %s", str(e))
            return None

    def get_peer_info(self):
        self.libtorrent_handle.get_peer_info()

    def get_trackers(self):
        self.libtorrent_handle.trackers()

    def info_hash(self):
        """
        Info hash of the torrent pointed to by this handle.
        :return: hash in bytes
        """
        self.libtorrent_handle.info_hash()

    def move_storage(self, new_directory):
        self.libtorrent_handle.move_storage(new_directory)
        return True

    def pause(self):
        self.libtorrent_handle.pause()

    def prioritize_files(self, priorities):
        self.libtorrent_handle.prioritize_files(priorities)

    def get_save_path(self):
        # torrent_handle.save_path() is deprecated in newer versions of Libtorrent. We should use
        # self.handle.status().save_path to query the save path of a torrent. However, this attribute
        # is only included in libtorrent 1.0.9+
        status = self.libtorrent_handle.get_status()
        if hasattr(status, 'save_path'):
            return status.save_path
        return self.libtorrent_handle.save_path()

    def get_status(self):
        return self.libtorrent_handle.status()

    def resolve_countries(self, resolve):
        self.libtorrent_handle.resolve_countries(resolve)

    def set_max_connections(self, connections):
        self.libtorrent_handle.set_max_connections(connections)

    def set_priority(self, priority):
        self.libtorrent_handle.set_priority(priority)

    def set_sequential_download(self, sequential_download):
        self.libtorrent_handle.set_sequential_download(sequential_download)

    def set_share_mode(self, mode):
        self.libtorrent_handle.set_share_mode(mode)

    def update_path(self, index, save_path, unwanted_directory, new_path):
        absolute_unwanted_directory = os.path.join(save_path.decode('utf-8'), unwanted_directory)
        if not os.path.exists(absolute_unwanted_directory) and unwanted_directory in new_path:
            os.makedirs(absolute_unwanted_directory)
            if sys.platform == "win32":
                ctypes.windll.kernel32.SetFileAttributesW(
                    absolute_unwanted_directory, 2)  # 2 = FILE_ATTRIBUTE_HIDDEN

        # Path should be unicode if Libtorrent is using std::wstring (on Windows),
        # else we use str (on Linux).
        try:
            self.libtorrent_handle.rename_file(index, new_path)
        except TypeError:
            self.libtorrent_handle.rename_file(index, new_path.encode("utf-8"))
