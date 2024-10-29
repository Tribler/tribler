"""
Author(s): Arno Bakker.
"""
from __future__ import annotations

import itertools
import logging
from asyncio import get_running_loop
from contextlib import suppress
from functools import cached_property
from hashlib import sha1
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Iterable, Literal, cast, overload

import aiohttp
import libtorrent as lt

from tribler.core.libtorrent.torrent_file_tree import TorrentFileTree
from tribler.core.libtorrent.trackers import is_valid_url

if TYPE_CHECKING:
    from os import PathLike


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


    class TorrentParameters(dict):  # noqa: D101

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
        def __getitem__(self, key: Literal[b"httpseeds"]) -> list[bytes] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"name"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"name.utf-8"]) -> bytes | None: ...

        @overload
        def __getitem__(self, key: Literal[b"nodes"]) -> list[bytes] | None: ...

        @overload
        def __getitem__(self, key: Literal[b"urllist"]) -> list[bytes] | None: ...

        def __getitem__(self, key: bytes) -> Any: ...  # noqa: D105

else:
    FileDict = dict
    InfoDict = dict
    MetainfoDict = dict[bytes, Any]
    TorrentParameters = dict


def escape_as_utf8(string: bytes, encoding: str = "utf8") -> str:
    """
    Make a string UTF-8 compliant, destroying characters if necessary.

    :param string: the string to convert
    :param encoding: the string encoding to use
    :return: the utf-8 string derivative
    """
    try:
        # Check if the delivered encoding is correct and we can convert to utf8 without any issues.
        return string.decode(encoding).encode('utf8').decode('utf8')
    except (LookupError, TypeError, ValueError):
        try:
            # The delivered encoding is incorrect, cast it to  latin1 and hope for the best (minor corruption).
            return string.decode('latin1').encode('utf8', 'ignore').decode('utf8')
        except (TypeError, ValueError):
            # This is a very nasty string (e.g. '\u266b'), remove the illegal entries.
            return string.decode('utf8', 'ignore')


def pathlist2filename(pathlist: Iterable[bytes]) -> Path:
    """
    Convert a multi-file torrent file 'path' entry to a filename.
    """
    return Path(*(x.decode() for x in pathlist))


def get_length_from_metainfo(metainfo: MetainfoDict, selectedfiles: set[Path] | None) -> int:
    """
    Loop through all files in a torrent and calculate the total size.
    """
    if b"files" not in metainfo[b"info"]:
        # single-file torrent
        return metainfo[b"info"][b"length"]
    # multi-file torrent
    files = metainfo[b"info"][b"files"]

    total = 0
    for i in range(len(files)):
        path = files[i][b"path"]
        length = files[i][b"length"]
        if length > 0 and (not selectedfiles or pathlist2filename(path) in selectedfiles):
            total += length
    return total


class TorrentDef:
    """
    This object acts as a wrapper around some libtorrent metadata.
    It can be used to create new torrents, or analyze existing ones.
    """

    def __init__(self, metainfo: MetainfoDict | None = None,
                 torrent_parameters: TorrentParameters | None = None,
                 ignore_validation: bool = True) -> None:
        """
        Create a new TorrentDef object, possibly based on existing data.

        :param metainfo: A dictionary with metainfo, i.e. from a .torrent file.
        :param torrent_parameters: User-defined parameters for the new TorrentDef.
        :param ignore_validation: Whether we ignore the libtorrent validation.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.torrent_parameters: TorrentParameters = cast(TorrentParameters, {})
        self.metainfo: MetainfoDict | None = metainfo
        self.infohash: bytes | None = None
        self._torrent_info: lt.torrent_info | None = None

        if self.metainfo is not None:
            # First, make sure the passed metainfo is valid
            if not ignore_validation:
                try:
                    self._torrent_info = lt.torrent_info(self.metainfo)
                    raw_infohash = self._torrent_info.info_hash()  # LT1.X: bytes, LT2.X: sha1_hash
                    self.infohash = raw_infohash if isinstance(raw_infohash, bytes) else raw_infohash.to_bytes()
                except RuntimeError as exc:
                    raise ValueError from exc
            else:
                try:
                    if not self.metainfo[b'info']:
                        msg = "Empty metainfo!"
                        raise ValueError(msg)
                    self.infohash = sha1(lt.bencode(self.metainfo[b'info'])).digest()
                except (KeyError, RuntimeError) as exc:
                    raise ValueError from exc
            self.copy_metainfo_to_torrent_parameters()

        elif torrent_parameters is not None:
            self.torrent_parameters.update(torrent_parameters)

    def copy_metainfo_to_torrent_parameters(self) -> None:  # noqa: C901
        """
        Populate the torrent_parameters dictionary with information from the metainfo.
        """
        if self.metainfo is not None:
            if b"comment" in self.metainfo:
                self.torrent_parameters[b"comment"] = self.metainfo[b"comment"]
            if b"created by" in self.metainfo:
                self.torrent_parameters[b"created by"] = self.metainfo[b"created by"]
            if b"creation date" in self.metainfo:
                self.torrent_parameters[b"creation date"] = self.metainfo[b"creation date"]
            if b"announce" in self.metainfo:
                self.torrent_parameters[b"announce"] = self.metainfo[b"announce"]
            if b"announce-list" in self.metainfo:
                self.torrent_parameters[b"announce-list"] = self.metainfo[b"announce-list"]
            if b"nodes" in self.metainfo:
                self.torrent_parameters[b"nodes"] = self.metainfo[b"nodes"]
            if b"httpseeds" in self.metainfo:
                self.torrent_parameters[b"httpseeds"] = self.metainfo[b"httpseeds"]
            if b"urllist" in self.metainfo:
                self.torrent_parameters[b"urllist"] = self.metainfo[b"urllist"]
            if b"name" in self.metainfo[b"info"]:
                self.torrent_parameters[b"name"] = self.metainfo[b"info"][b"name"]
            if b"piece length" in self.metainfo[b"info"]:
                self.torrent_parameters[b"piece length"] = self.metainfo[b"info"][b"piece length"]

    @property
    def torrent_info(self) -> lt.torrent_info | None:
        """
        Get the libtorrent torrent info instance or load it from our metainfo.
        """
        self.load_torrent_info()
        return self._torrent_info

    def invalidate_torrent_info(self) -> None:
        """
        Invalidate the torrent info.
        """
        self._torrent_info = None

    def load_torrent_info(self) -> None:
        """
        Load the torrent info into memory from our metainfo if it does not exist.
        """
        if self._torrent_info is None:
            self._torrent_info = lt.torrent_info(cast(dict[bytes, Any], self.metainfo))

    def torrent_info_loaded(self) -> bool:
        """
        Check if the libtorrent torrent info is loaded.
        """
        return self._torrent_info is not None

    @cached_property
    def torrent_file_tree(self) -> TorrentFileTree:
        """
        Construct a file tree from this torrent definition.
        """
        return TorrentFileTree.from_lt_file_storage(self.torrent_info.files())  # type: ignore[union-attr]

    @staticmethod
    def _threaded_load_job(filepath: str | bytes | PathLike) -> TorrentDef:
        """
        Perform the actual loading of the torrent.

        Called from a thread: don't call this directly!
        """
        with open(filepath, "rb") as torrent_file:
            file_content = torrent_file.read()
        return TorrentDef.load_from_memory(file_content)

    @staticmethod
    async def load(filepath: str | bytes | PathLike) -> TorrentDef:
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
        metainfo = lt.bdecode(bencoded_data)
        # Some versions of libtorrent will not raise an exception when providing invalid data.
        # This issue is present in 1.0.8 (included with Tribler 7.3.0), but has been fixed since at least 1.2.1.
        if metainfo is None:
            msg = "Data is not a bencoded string"
            raise ValueError(msg)
        return TorrentDef.load_from_dict(cast(MetainfoDict, metainfo))

    @staticmethod
    def load_from_dict(metainfo: MetainfoDict) -> TorrentDef:
        """
        Load a metainfo dictionary into a TorrentDef object.

        :param metainfo: The metainfo dictionary
        """
        return TorrentDef(metainfo=metainfo)

    @staticmethod
    async def load_from_url(url: str) -> TorrentDef:
        """
        Create a TorrentDef with information from a remote source.

        :param url: The HTTP/HTTPS url where to fetch the torrent info from.
        """
        session = aiohttp.ClientSession(raise_for_status=True)

        response = await session.get(url)
        body = await response.read()

        return TorrentDef.load_from_memory(body)

    def _filter_characters(self, name: bytes) -> str:
        """
        Sanitize the names in path to unicode by replacing out all
        characters that may -even remotely- cause problems with the '?'
        character.

        :param name: the name to sanitize
        :return: the sanitized string
        """

        def filter_character(char: int) -> str:
            if 0 < char < 128:
                return chr(char)
            self._logger.debug("Bad character 0x%X", char)
            return "?"

        return "".join(map(filter_character, name))

    def set_encoding(self, enc: bytes) -> None:
        """
        Set the character encoding for e.g. the 'name' field.

        :param enc: The new encoding of the file.
        """
        self.torrent_parameters[b"encoding"] = enc

    def get_encoding(self) -> str:
        """
        Returns the used encoding of the TorrentDef.
        """
        return self.torrent_parameters.get(b"encoding", b"utf-8").decode()

    def set_tracker(self, url: str) -> None:
        """
        Set the tracker of this torrent, according to a given URL.
        :param url: The tracker url.
        """
        if not is_valid_url(url):
            msg = "Invalid URL"
            raise ValueError(msg)

        if url.endswith("/"):  # Some tracker code can't deal with / at end
            url = url[:-1]
        self.torrent_parameters[b"announce"] = url

    def get_tracker(self) -> bytes | None:
        """
        Returns the torrent announce URL.
        """
        return self.torrent_parameters.get(b"announce", None)

    def get_tracker_hierarchy(self) -> list[list[bytes]]:
        """
        Returns the hierarchy of trackers.
        """
        return self.torrent_parameters.get(b"announce-list", [])

    def get_trackers(self) -> set[bytes]:
        """
        Returns a flat set of all known trackers.

        :return: all known trackers
        """
        if self.get_tracker_hierarchy():
            trackers = itertools.chain.from_iterable(self.get_tracker_hierarchy())
            return set(filter(None, trackers))
        tracker = self.get_tracker()
        if tracker:
            return {tracker}
        return set()

    def set_piece_length(self, piece_length: int) -> None:
        """
        Set the size of the pieces in which the content is traded.
        The piece size must be a multiple of the chunk size, the unit in which
        it is transmitted, which is 16K by default. The default is automatic (value 0).

        :param piece_length: The piece length.
        """
        if not isinstance(piece_length, int):
            msg = "Piece length not an int/long"
            raise ValueError(msg)  # noqa: TRY004

        self.torrent_parameters[b"piece length"] = piece_length

    def get_piece_length(self) -> int:
        """
        Returns the piece size.
        """
        return self.torrent_parameters.get(b"piece length", 0)

    def get_nr_pieces(self) -> int:
        """
        Returns the number of pieces.
        """
        if not self.metainfo:
            return 0
        return len(self.metainfo[b"info"][b"pieces"]) // 20

    def get_infohash(self) -> bytes | None:
        """
        Returns the infohash of the torrent, if metainfo is provided. Might be None if no metainfo is provided.
        """
        return self.infohash

    def get_metainfo(self) -> MetainfoDict | None:
        """
        Returns the metainfo of the torrent. Might be None if no metainfo is provided.
        """
        return self.metainfo

    def get_name(self) -> bytes | None:
        """
        Returns the name as raw string of bytes.
        """
        return self.torrent_parameters[b"name"]

    def get_name_utf8(self) -> str:
        """
        Not all names are utf-8, attempt to construct it as utf-8 anyway.
        """
        return escape_as_utf8(self.get_name() or b"", self.get_encoding())

    def set_name(self, name: bytes) -> None:
        """
        Set the name of this torrent.

        :param name: The new name of the torrent
        """
        self.torrent_parameters[b"name"] = name

    def get_name_as_unicode(self) -> str:
        """
        Returns the info['name'] field as Unicode string.

        If there is an utf-8 encoded name, we assume that it is correctly encoded and use it normally.
        Otherwise, if there is an encoding[1], we attempt to decode the (bytes) name.
        Otherwise, we attempt to decode the (bytes) name as UTF-8.
        Otherwise, we attempt to replace non-UTF-8 characters from the (bytes) name with "?".
        If all of the above fails, this returns an empty string.

        [1] Some encodings are not supported by python. For instance, the MBCS codec which is used by Windows is not
        supported (Jan 2010).
        """
        if self.metainfo is not None:
            if b"name.utf-8" in self.metainfo[b"info"]:
                with suppress(UnicodeError):
                    return self.metainfo[b"info"][b"name.utf-8"].decode()

            if (name := self.metainfo[b"info"].get(b"name")) is not None:
                if (encoding := self.metainfo.get(b"encoding")) is not None:
                    with suppress(UnicodeError), suppress(LookupError):
                        return name.decode(encoding.decode())
                with suppress(UnicodeError):
                    return name.decode()
                with suppress(UnicodeError):
                    return self._filter_characters(name)

        return ""

    def _get_all_files_as_unicode_with_length(self) -> Generator[tuple[Path, int], None, None]:  # noqa: C901
        """
        Get a generator for files in the torrent def. No filtering is possible and all tricks are allowed to obtain
        a unicode list of filenames.

        :return: A unicode filename generator.
        """
        if self.metainfo and b"files" in self.metainfo[b"info"]:
            # Multi-file torrent
            files = cast(FileDict, self.metainfo[b"info"][b"files"])

            for file_dict in files:
                if b"path.utf-8" in file_dict:
                    # This file has an utf-8 encoded list of elements.
                    # We assume that it is correctly encoded and use it normally.
                    try:
                        yield (Path(*(element.decode() for element in file_dict[b"path.utf-8"])),
                               file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

                if b"path" in file_dict:
                    # Try to use the 'encoding' field. If it exists, it should contain something like 'utf-8'.
                    if (encoding := self.metainfo.get(b"encoding")) is not None:
                        try:
                            yield (Path(*(element.decode(encoding.decode()) for element in file_dict[b"path"])),
                                   file_dict[b"length"])
                            continue
                        except UnicodeError:
                            pass
                        except LookupError:
                            # Some encodings are not supported by Python.  For instance, the MBCS codec which is used
                            # by Windows is not supported (Jan 2010).
                            pass

                    # Try to convert the names in path to unicode, assuming that it was encoded as utf-8.
                    try:
                        yield (Path(*(element.decode() for element in file_dict[b"path"])),
                               file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

                    # Convert the names in path to unicode by replacing out all characters that may - even remotely -
                    # cause problems with the '?' character.
                    try:
                        yield Path(*map(self._filter_characters, file_dict[b"path"])), file_dict[b"length"]
                        continue
                    except UnicodeError:
                        pass

        elif self.metainfo:
            # Single-file torrent
            yield Path(self.get_name_as_unicode()), self.metainfo[b"info"][b"length"]

    def get_files_with_length(self, exts: set[str] | None = None) -> list[tuple[Path, int]]:
        """
        The list of files in the torrent def.

        :param exts: (Optional) list of filename extensions (without leading .) to search for.
        :return: A list of filenames.
        """
        videofiles = []
        for filename, length in self._get_all_files_as_unicode_with_length():
            ext = Path(filename).suffix
            if ext != "" and ext[0] == ".":
                ext = ext[1:]
            if exts is None or ext.lower() in exts:
                videofiles.append((filename, length))
        return videofiles

    def get_files(self, exts: set[str] | None = None) -> list[Path]:
        """
        Return the list of file paths in this torrent.
        """
        return [filename for filename, _ in self.get_files_with_length(exts)]

    def get_length(self, selectedfiles: set[Path] | None = None) -> int:
        """
        Returns the total size of the content in the torrent. If the optional selectedfiles argument is specified, the
        method returns the total size of only those files.

        :return: A length (long)
        """
        if self.metainfo:
            return get_length_from_metainfo(self.metainfo, selectedfiles)
        return 0

    def get_creation_date(self) -> int:
        """
        Returns the creation date of the torrent.
        """
        return self.metainfo.get(b"creation date", 0) if self.metainfo else 0

    def is_multifile_torrent(self) -> bool:
        """
        Returns whether this TorrentDef is a multi-file torrent.
        """
        if self.metainfo:
            return b"files" in self.metainfo[b"info"]
        return False

    def is_private(self) -> bool:
        """
        Returns whether this TorrentDef is a private torrent (and is not announced in the DHT).
        """
        try:
            private = int(self.metainfo[b"info"].get(b"private", 0)) if self.metainfo else 0
        except (ValueError, KeyError) as e:
            self._logger.warning("%s: %s", e.__class__.__name__, str(e))
            private = 0
        return private == 1

    def get_index_of_file_in_files(self, file: str | None) -> int:
        """
        Get the index of the given file path in the torrent.

        Raises a ValueError if the path is not found.
        """
        if not self.metainfo:
            msg = "TorrentDef does not have metainfo"
            raise ValueError(msg)
        info = self.metainfo[b"info"]

        if file is not None and b"files" in info:
            for i in range(len(info[b"files"])):
                file_dict = info[b"files"][i]

                intorrentpath = pathlist2filename(file_dict.get(b"path.utf-8", file_dict[b"path"]))

                if intorrentpath == Path(file):
                    return i
            msg = "File not found in torrent"
            raise ValueError(msg)

        msg = "File not found in single-file torrent"
        raise ValueError(msg)


class TorrentDefNoMetainfo(TorrentDef):
    """
    Instances of this class are used when working with a torrent def that contains no metainfo (yet), for instance,
    when starting a download with only an infohash. Other methods that are using this class do not distinguish between
    a TorrentDef with and without data and may still expect this class to have various methods in TorrentDef
    implemented.
    """

    def __init__(self, infohash: bytes, name: bytes, url: bytes | str | None = None) -> None:
        """
        Create a new valid torrent def without metainfo.
        """
        torrent_parameters: TorrentParameters = cast(TorrentParameters, {b"name": name})
        if url is not None:
            torrent_parameters[b"urllist"] = [url if isinstance(url, bytes) else url.encode()]
        super().__init__(torrent_parameters=torrent_parameters)
        self.infohash = infohash

    def get_url(self) -> bytes | str | None:
        """
        Get the URL belonging to this torrent.
        """
        if urllist := self.torrent_parameters.get(b"urllist"):
            return urllist[0]
        return None

    @property
    def torrent_info(self) -> lt.torrent_info | None:
        """
        A torrent def without metinfo has no libtorrent torrent_info.
        """
        return None

    def load_torrent_info(self) -> None:
        """
        If there cannot be torrent info, we don't need to try and load it.
        """

    def get_name_as_unicode(self) ->  str:
        """
        Get the name of this torrent.
        """
        return self.get_name_utf8()
