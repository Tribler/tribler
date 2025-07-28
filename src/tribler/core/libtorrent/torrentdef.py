from __future__ import annotations

from asyncio import get_running_loop
from binascii import hexlify
from typing import TYPE_CHECKING, Any

import libtorrent as lt

if TYPE_CHECKING:
    from typing import Literal, overload

    ###############
    # V1 torrents #
    ###############

    class FileDict(dict):  # noqa: D101

        @overload  # type: ignore[override]
        def __getitem__(self, key: Literal[b"length"]) -> int: ...

        @overload
        def __getitem__(self, key: Literal[b"path"]) -> list[bytes]: ...

        @overload
        def __getitem__(self, key: Literal[b"path.utf-8"]) -> list[bytes] | None: ...

        def __getitem__(self, key: bytes) -> Any: ...  # noqa: D105


    class InfoDict(dict):  # noqa: D101

        @overload  # type: ignore[override]
        def __getitem__(self, key: Literal[b"files"]) -> list[FileDict]: ...

        @overload
        def __getitem__(self, key: Literal[b"length"]) -> int: ...

        @overload
        def __getitem__(self, key: Literal[b"name"]) -> bytes: ...

        @overload
        def __getitem__(self, key: Literal[b"name.utf-8"]) -> bytes: ...

        @overload
        def __getitem__(self, key: Literal[b"piece length"]) -> int: ...

        @overload
        def __getitem__(self, key: Literal[b"pieces"]) -> bytes: ...

        def __getitem__(self, key: bytes) -> Any: ...  # noqa: D105


    class MetainfoDict(dict):  # noqa: D101

        @overload  # type: ignore[override]
        def __getitem__(self, key: Literal[b"announce"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"announce-list"]) -> list[list[bytes]] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"comment"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"created by"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"creation date"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"encoding"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"info"]) -> InfoDict: ...

        @overload
        def __getitem__(self, key: Literal[b"httpseeds"]) -> list[bytes] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"nodes"]) -> list[bytes] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"urllist"]) -> list[bytes] | None: ...

        def __getitem__(self, key: bytes) -> Any: ...  # noqa: D105

    ###############
    # V2 torrents #
    ###############
    class FileSpecV2(dict):  # noqa: D101

        @overload
        def __getitem__(self, key: Literal[b"length"]) -> int: ...

        @overload
        def __getitem__(self, key: Literal[b"pieces root"]) -> bytes | None: ...

        def __getitem__(self, key: bytes) -> Any: ...  # noqa: D105


    class FileV2(dict):  # noqa: D101

        def __getitem__(self, key: Literal[b""]) -> FileSpecV2: ...  # noqa: D105


    class DirectoryV2(dict):  # noqa: D101

        def __getitem__(self, key: bytes) -> DirectoryV2 | FileV2: ...  # noqa: D105


    class InfoDictV2(dict):  # noqa: D101

        @overload  # type: ignore[override]
        def __getitem__(self, key: Literal[b"file tree"]) -> DirectoryV2: ...

        @overload
        def __getitem__(self, key: Literal[b"meta version"]) -> int: ...

        @overload
        def __getitem__(self, key: Literal[b"name"]) -> bytes: ...

        @overload
        def __getitem__(self, key: Literal[b"piece length"]) -> int: ...

        def __getitem__(self, key: bytes) -> Any: ...  # noqa: D105


    class MetainfoV2Dict(dict):  # noqa: D101

        @overload  # type: ignore[override]
        def __getitem__(self, key: Literal[b"announce"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"announce-list"]) -> list[list[bytes]] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"comment"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"created by"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"creation date"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"encoding"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"info"]) -> InfoDictV2: ...

        @overload
        def __getitem__(self, key: Literal[b"httpseeds"]) -> list[bytes] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"nodes"]) -> list[bytes] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"piece layers"]) -> dict[bytes, bytes] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"urllist"]) -> list[bytes] | None: ...

        def __getitem__(self, key: bytes) -> Any: ...  # noqa: D105


else:
    FileDict = dict[bytes, Any]
    InfoDict = dict[bytes, Any]
    MetainfoDict = dict[bytes, Any]

    FileSpecV2 = dict[bytes, Any]
    InfoDictV2 = dict[bytes, Any]
    FileV2 = dict[bytes, Any]
    DirectoryV2 = dict[bytes, Any]
    MetainfoV2Dict = dict[bytes, Any]


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
        if self.torrent_info:
            return self.torrent_info.info_hash().to_bytes()
        return self.atp.info_hash.to_bytes()

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

    @staticmethod
    def load_from_dict(metainfo: MetainfoDict | MetainfoV2Dict) -> TorrentDef:
        """
        Load a metainfo dictionary into a TorrentDef object.

        :param metainfo: The metainfo dictionary
        """
        try:
            return TorrentDef.load_from_memory(lt.bencode(metainfo))
        except RuntimeError as e:
            raise ValueError from e

    def get_metainfo(self) -> MetainfoDict | MetainfoV2Dict | None:
        """
        Returns the metainfo of the torrent. Might be None if no metainfo is provided.
        """
        if self.atp.ti is None:
            return None
        return MetainfoDict({
            b"announce": self.atp.trackers[0].encode() if self.atp.trackers else b"",
            b"announce-list": [[tracker.encode()] for tracker in self.atp.trackers],
            b"comment": self.atp.ti.comment().encode(),
            b"created by": self.atp.ti.creator().encode(),
            b"creation date": self.atp.ti.creation_date(),
            b"encoding": "UTF-8",
            b"httpseeds": [web_seed["url"].encode() for web_seed in self.atp.ti.web_seeds()
                           if web_seed["type"] == 1],  # type: ignore[typeddict-item]  # missing in lt .pyi
            b"nodes": [(entry[0].encode(), entry[1]) for entry in self.atp.ti.nodes()],
            b"urllist": [web_seed["url"].encode() for web_seed in self.atp.ti.web_seeds()
                         if web_seed["type"] == 0],  # type: ignore[typeddict-item]  # missing in lt .pyi
            b"info": lt.bdecode(self.atp.ti.info_section())
        })

    def get_file_indices(self) -> list[int]:
        """
        Get the actual torrent file indices of our files.
        """
        if self.torrent_info is None:
            return []
        storage = self.torrent_info.files()
        return [i for i in range(storage.num_files()) if storage.file_flags(i) == 0]
