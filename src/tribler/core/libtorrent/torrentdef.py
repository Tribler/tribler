from __future__ import annotations

from asyncio import get_running_loop
from binascii import hexlify
from hashlib import sha256
from typing import TYPE_CHECKING

import libtorrent as lt

if TYPE_CHECKING:
    from collections.abc import Sequence

BLOCK_SIZE = 2 ** 14


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
        return f'TorrentDef(name="{self.name}", infohash={hexlify(self.infohash).decode()}, url="{self.atp.url}")'

    @property
    def name(self) -> str:
        """
        Get the name of this torrent.
        """
        return self.atp.name or (self.torrent_info.name() if self.torrent_info else "Unknown name")

    @property
    def description(self) -> str:
        """
        Get the description of this torrent.
        """
        return self.torrent_info.comment() if self.torrent_info else ""

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
        return [i for i in range(storage.num_files())
                if (storage.file_flags(i) & int(lt.file_flags_t.flag_pad_file)) == 0]

    def _get_piece_range_from_file_idx(self, fstorage: lt.file_storage, file_idx: int) -> Sequence[int]:
        """
        Get the piece range from a file index.
        """
        start_idx = fstorage.piece_index_at_file(file_idx)  # type: ignore[attr-defined]
        div, rem = divmod(fstorage.file_size(file_idx), fstorage.piece_length())
        return range(start_idx, start_idx + div + (rem > 0))

    def get_v2_piece_hash(self, piece_index: int, piece_buffer: bytes) -> bytes:
        """
        Get the (32-byte) SHA-256 hash for the specified piece from its buffer.
        """
        if self.torrent_info is None:
            return b""

        storage = self.torrent_info.files()
        file_idx = storage.file_index_at_piece(piece_index)  # type: ignore[attr-defined]
        piece_range = list(self._get_piece_range_from_file_idx(storage, file_idx))
        max_blocks = len(piece_buffer) // BLOCK_SIZE

        if piece_index == piece_range[-1]:
            # We are the last piece, don't consume the full buffer
            len_remainder = storage.file_size(file_idx) % storage.piece_length()
            piece_buffer = piece_buffer[:len_remainder]
            actual_blocks = len_remainder // BLOCK_SIZE
            if actual_blocks * BLOCK_SIZE < len_remainder:
                actual_blocks += 1
        else:
            actual_blocks = max_blocks

        # Calculate the Merkle root.
        hashes = [sha256(piece_buffer[(i * BLOCK_SIZE): ((i + 1) * BLOCK_SIZE)]).digest() for i in range(actual_blocks)]
        hashes.extend([bytes(32) for _ in range(max_blocks - actual_blocks)])
        while len(hashes) > 1:
            hashes = [sha256(l + r).digest() for l, r in zip(*[iter(hashes)] * 2, strict=False)]
        return hashes[0]

    def get_v2_piece_indices_per_layer(self) -> dict[bytes, list[int]]:
        """
        Get the piece indices per file root hash.
        """
        if self.torrent_info is None:
            return {}

        storage = self.torrent_info.files()
        return {
            storage.root(f).to_bytes():  # type: ignore[attr-defined]
                list(self._get_piece_range_from_file_idx(storage, f))
            for f in self.get_file_indices()
            if storage.file_size(f) > storage.piece_length()
        }
