from __future__ import annotations

from asyncio import get_running_loop
from binascii import hexlify

import libtorrent as lt


def best_info_hash(info_hashes: lt.info_hash_t, info_hash: lt.sha1_hash) -> bytes:
    """
    Get the best bytes representation of available info hash material.
    """
    if not info_hashes.v2.is_all_zeros():
        return info_hashes.v2.to_bytes()
    if not info_hashes.v1.is_all_zeros():
        return info_hashes.v1.to_bytes()
    if not info_hash.is_all_zeros():
        return info_hash.to_bytes()
    return b"\x00" * 20


class TorrentDef:
    """
    This object acts as a wrapper around some libtorrent metadata.
    It can be used to create new torrents, or analyze existing ones.
    """

    def __init__(self, atp: lt.add_torrent_params) -> None:
        """
        Create a new TorrentDef object, possibly based on existing data.

        :param atp: User-defined parameters for the new TorrentDef.
        """
        self.atp = atp

    def __str__(self) -> str:
        """
        We are essentially the ATP dictionary itself.
        """
        return f"TorrentDef(name=\"{self.name}\", infohash={hexlify(self.infohash).decode()}, url=\"{self.atp.url}\")"

    @property
    def name(self) -> str:
        """
        Get the name of this torrent.
        """
        return self.atp.name or (self.torrent_info.name() if self.torrent_info else "Unknown name")

    @property
    def torrent_info(self) -> lt.torrent_info | None:
        """
        Get the libtorrent torrent info instance or load it from our metainfo.
        """
        return self.atp.ti

    @property
    def infohash(self) -> bytes:
        """
        Convenient way to get the info_hash as bytes.
        """
        return best_info_hash(self.atp.info_hashes, self.atp.info_hash)

    @staticmethod
    def _threaded_load_job(filepath: str) -> TorrentDef:
        """
        Perform the actual loading of the torrent.

        Called from a thread: don't call this directly!
        """
        try:
            return TorrentDef(lt.load_torrent_file(filepath))  # type: ignore[attr-defined]  # missing in lt .pyi
        except RuntimeError as e:
            raise ValueError from e

    @staticmethod
    async def load(filepath: str) -> TorrentDef:
        """
        Create a TorrentDef object from a .torrent file.

        :param filepath: The path to the .torrent file
        """
        return await get_running_loop().run_in_executor(None, TorrentDef._threaded_load_job, filepath)

    @staticmethod
    def load_from_memory(bencoded_data: bytes) -> TorrentDef:
        """
        Load some bencoded data into a TorrentDef.

        :param bencoded_data: The bencoded data to decode and use as metainfo
        """
        try:
            return TorrentDef(lt.load_torrent_buffer(bencoded_data))  # type: ignore[attr-defined]  # missing in lt .pyi
        except RuntimeError as e:
            raise ValueError from e

    def get_file_indices(self) -> list[int]:
        """
        Get the actual torrent file indices of our files.
        """
        if self.torrent_info is None:
            return []
        storage = self.torrent_info.files()
        return [i for i in range(storage.num_files()) if storage.file_flags(i) == 0]
