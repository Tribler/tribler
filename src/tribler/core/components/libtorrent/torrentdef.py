"""
Author(s): Arno Bakker
"""
from __future__ import annotations

import itertools
import logging
from asyncio import get_running_loop
from contextlib import suppress
from functools import cached_property
from hashlib import sha1
from os import PathLike
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union

import aiohttp

from tribler.core.components.libtorrent.torrent_file_tree import TorrentFileTree
from tribler.core.components.libtorrent.utils import torrent_utils
from tribler.core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler.core.utilities import maketorrent, path_util
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.unicode import ensure_unicode, hexlify
from tribler.core.utilities.utilities import bdecode_compat, is_valid_url


def escape_as_utf8(string, encoding='utf8') -> str:
    """
    Make a string UTF-8 compliant, destroying characters if necessary.

    :param string: the string to convert
    :type string: str
    :return: the utf-8 string derivative
    :rtype: str
    """
    try:
        # Try seeing if the delivered encoding is correct and we
        # can convert to utf8 without any issues.
        return string.decode(encoding).encode('utf8').decode('utf8')
    except (LookupError, TypeError, ValueError):
        try:
            # The delivered encoding is incorrect, cast it to
            # latin1 and hope for the best (minor corruption).
            return string.decode('latin1').encode('utf8', 'ignore').decode('utf8')
        except (TypeError, ValueError):
            # This is a very nasty string (e.g. '\u266b'), remove the illegal entries.
            return string.encode('utf8', 'ignore').decode('utf8')


class TorrentDef:
    """
    This object acts as a wrapper around some libtorrent metadata.
    It can be used to create new torrents, or analyze existing ones.
    """

    def __init__(self, metainfo: Optional[Dict] = None, torrent_parameters: Optional[Dict] = None,
                 ignore_validation: bool = True):
        """
        Create a new TorrentDef object, possibly based on existing data.
        :param metainfo: A dictionary with metainfo, i.e. from a .torrent file.
        :param torrent_parameters: User-defined parameters for the new TorrentDef.
        :param ignore_validation: Whether we ignore the libtorrent validation.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.torrent_parameters = {}
        self.metainfo = metainfo
        self.files_list = []
        self.infohash: Optional[bytes] = None
        self._infohash_hex: Optional[str] = None
        self._torrent_info = None

        if metainfo is not None:
            # First, make sure the passed metainfo is valid
            if not ignore_validation:
                try:
                    self._torrent_info = lt.torrent_info(metainfo)
                    self.infohash = self._torrent_info.info_hash()
                except RuntimeError as exc:
                    raise ValueError from exc
            else:
                try:
                    if not self.metainfo[b'info']:
                        raise ValueError("Empty metainfo!")
                    self.infohash = sha1(lt.bencode(self.metainfo[b'info'])).digest()
                except (KeyError, RuntimeError) as exc:
                    raise ValueError from exc
            self.copy_metainfo_to_torrent_parameters()
        elif torrent_parameters:
            self.torrent_parameters.update(torrent_parameters)

    def copy_metainfo_to_torrent_parameters(self) -> None:
        """
        Populate the torrent_parameters dictionary with information from the metainfo.
        """
        for key in [
            b"comment",
            b"created by",
            b"creation date",
            b"announce",
            b"announce-list",
            b"nodes",
            b"httpseeds",
            b"urllist",
        ]:
            if self.metainfo and key in self.metainfo:
                self.torrent_parameters[key] = self.metainfo[key]

        infokeys = [b'name', b'piece length']
        for key in infokeys:
            if self.metainfo and key in self.metainfo[b'info']:
                self.torrent_parameters[key] = self.metainfo[b'info'][key]

    @property
    def torrent_info(self) -> lt.torrent_info:
        """
        Get the libtorrent torrent info instance or load it from our metainfo.
        """
        self.load_torrent_info()
        return self._torrent_info

    def load_torrent_info(self) -> None:
        """
        Load the torrent info into memory from our metainfo if it does not exist.
        """
        if self._torrent_info is None:
            self._torrent_info = lt.torrent_info(self.metainfo)

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
        return TorrentFileTree.from_lt_file_storage(self.torrent_info.files())

    @staticmethod
    def _threaded_load_job(filepath: Union[str, bytes, PathLike]) -> TorrentDef:
        """
        Perform the actual loading of the torrent.

        Called from a thread: don't call this directly!
        """
        with open(filepath, "rb") as torrent_file:
            file_content = torrent_file.read()
        return TorrentDef.load_from_memory(file_content)

    @staticmethod
    async def load(filepath: Union[str, bytes, PathLike]) -> TorrentDef:
        """
        Create a TorrentDef object from a .torrent file
        :param filepath: The path to the .torrent file
        """
        return await get_running_loop().run_in_executor(None, TorrentDef._threaded_load_job, filepath)

    @staticmethod
    def load_from_memory(bencoded_data: bytes) -> TorrentDef:
        """
        Load some bencoded data into a TorrentDef.
        :param bencoded_data: The bencoded data to decode and use as metainfo
        """
        metainfo = bdecode_compat(bencoded_data)
        # Some versions of libtorrent will not raise an exception when providing invalid data.
        # This issue is present in 1.0.8 (included with Tribler 7.3.0), but has been fixed since at least 1.2.1.
        if metainfo is None:
            raise ValueError("Data is not a bencoded string")
        return TorrentDef.load_from_dict(metainfo)

    @staticmethod
    def load_from_dict(metainfo: Dict) -> TorrentDef:
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
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            response = await session.get(url)
            body = await response.read()
        return TorrentDef.load_from_memory(body)

    def _filter_characters(self, name: bytes) -> str:
        """
        Sanitize the names in path to unicode by replacing out all
        characters that may -even remotely- cause problems with the '?'
        character.

        :param name: the name to sanitize
        :type name: bytes
        :return: the sanitized string
        :rtype: str
        """

        def filter_character(char: int) -> str:
            if 0 < char < 128:
                return chr(char)
            self._logger.debug("Bad character 0x%X", char)
            return "?"

        return "".join(map(filter_character, name))

    def add_content(self, file_path: str) -> None:
        """
        Add some content to the torrent file.
        :param file_path: The (absolute) path of the file to add.
        """
        self.files_list.append(Path(file_path).absolute())

    def set_encoding(self, enc: bytes) -> None:
        """
        Set the character encoding for e.g. the 'name' field
        :param enc: The new encoding of the file.
        """
        self.torrent_parameters[b'encoding'] = enc

    def get_encoding(self) -> str:
        """
        Returns the used encoding of the TorrentDef.
        """
        return ensure_unicode(self.torrent_parameters.get(b'encoding', b'utf-8'), 'utf-8')

    def set_tracker(self, url: str) -> None:
        """
        Set the tracker of this torrent, according to a given URL.
        :param url: The tracker url.
        """
        if not is_valid_url(url):
            raise ValueError("Invalid URL")

        if url.endswith('/'):  # Some tracker code can't deal with / at end
            url = url[:-1]
        self.torrent_parameters[b'announce'] = url

    def get_tracker(self) -> Optional[str]:
        """
        Returns the torrent announce URL.
        """
        return self.torrent_parameters.get(b'announce', None)

    def get_tracker_hierarchy(self) -> List[List[str]]:
        """
        Returns the hierarchy of trackers.
        """
        return self.torrent_parameters.get(b'announce-list', [])

    def get_trackers(self) -> Set[str]:
        """
        Returns a flat set of all known trackers.

        :return: all known trackers
        :rtype: set
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
            raise ValueError("Piece length not an int/long")

        self.torrent_parameters[b'piece length'] = piece_length

    def get_piece_length(self) -> None:
        """
        Returns the piece size.
        """
        return self.torrent_parameters.get(b'piece length', 0)

    def get_nr_pieces(self) -> int:
        """
        Returns the number of pieces.
        """
        if not self.metainfo:
            return 0
        return len(self.metainfo[b'info'][b'pieces']) // 20

    def get_pieces(self) -> List:
        """
        Returns the pieces.
        """
        if not self.metainfo:
            return []
        return self.metainfo[b'info'][b'pieces'][:]

    def get_infohash(self) -> Optional[bytes]:
        """
        Returns the infohash of the torrent, if metainfo is provided. Might be None if no metainfo is provided.
        """
        return self.infohash

    def get_infohash_hex(self) -> Optional[str]:
        if not self._infohash_hex and self.infohash:
            self._infohash_hex = hexlify(self.infohash)

        return self._infohash_hex

    def get_metainfo(self) -> Dict:
        """
        Returns the metainfo of the torrent. Might be None if no metainfo is provided.
        """
        return self.metainfo

    def get_name(self) -> bytes:
        """
        Returns the name as raw string of bytes.
        """
        return self.torrent_parameters[b'name']

    def get_name_utf8(self) -> str:
        """
        Not all names are utf-8, attempt to construct it as utf-8 anyway.
        """
        return escape_as_utf8(self.get_name(), self.get_encoding())

    def set_name(self, name: bytes) -> None:
        """
        Set the name of this torrent.
        :param name: The new name of the torrent
        """
        self.torrent_parameters[b'name'] = name

    def get_name_as_unicode(self) -> str:
        """ Returns the info['name'] field as Unicode string.
        @return Unicode string. """
        if self.metainfo and b"name.utf-8" in self.metainfo[b"info"]:
            # There is an utf-8 encoded name.  We assume that it is
            # correctly encoded and use it normally
            try:
                return ensure_unicode(self.metainfo[b"info"][b"name.utf-8"], "UTF-8")
            except UnicodeError:
                pass

        if self.metainfo and b"name" in self.metainfo[b"info"]:
            # Try to use the 'encoding' field.  If it exists, it
            # should contain something like 'utf-8'
            if "encoding" in self.metainfo:
                try:
                    return ensure_unicode(self.metainfo[b"info"][b"name"], self.metainfo[b"encoding"])
                except UnicodeError:
                    pass
                except LookupError:
                    # Some encodings are not supported by python.  For
                    # instance, the MBCS codec which is used by
                    # Windows is not supported (Jan 2010)
                    pass

            # Try to convert the names in path to unicode, assuming
            # that it was encoded as utf-8
            try:
                return ensure_unicode(self.metainfo[b"info"][b"name"], "UTF-8")
            except UnicodeError:
                pass

            # Convert the names in path to unicode by replacing out
            # all characters that may -even remotely- cause problems
            # with the '?' character
            try:
                return self._filter_characters(self.metainfo[b"info"][b"name"])
            except UnicodeError:
                pass

        # We failed.  Returning an empty string
        return ""

    def save(self, torrent_filepath: Optional[str] = None) -> None:
        """
        Generate the metainfo and save the torrent file.
        :param torrent_filepath: An optional absolute path to where to save the generated .torrent file.
        """
        torrent_dict = torrent_utils.create_torrent_file(self.files_list, self.torrent_parameters,
                                                         torrent_filepath=torrent_filepath)
        self._torrent_info = None
        with suppress(AttributeError):
            del self.torrent_file_tree  # Remove the cache without retrieving it or checking if it exists (Error)
        self.metainfo = bdecode_compat(torrent_dict['metainfo'])
        self.copy_metainfo_to_torrent_parameters()
        self.infohash = torrent_dict['infohash']

    def _get_all_files_as_unicode_with_length(self) -> Iterator[Path, int]:
        """ Get a generator for files in the torrent def. No filtering
        is possible and all tricks are allowed to obtain a unicode
        list of filenames.
        @return A unicode filename generator.
        """
        if self.metainfo and b"files" in self.metainfo[b"info"]:
            # Multi-file torrent
            files = self.metainfo[b"info"][b"files"]

            for file_dict in files:
                if b"path.utf-8" in file_dict:
                    # This file has an utf-8 encoded list of elements.
                    # We assume that it is correctly encoded and use
                    # it normally
                    try:
                        yield (Path(*(ensure_unicode(element, "UTF-8") for element in file_dict[b"path.utf-8"])),
                               file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

                if b"path" in file_dict:
                    # Try to use the 'encoding' field.  If it exists,
                    # it should contain something like 'utf-8'
                    if b"encoding" in self.metainfo:
                        encoding = ensure_unicode(self.metainfo[b"encoding"], "utf8")
                        try:
                            yield (Path(*(ensure_unicode(element, encoding) for element in file_dict[b"path"])),
                                   file_dict[b"length"])
                            continue
                        except UnicodeError:
                            pass
                        except LookupError:
                            # Some encodings are not supported by
                            # python.  For instance, the MBCS codec
                            # which is used by Windows is not
                            # supported (Jan 2010)
                            pass

                    # Try to convert the names in path to unicode,
                    # assuming that it was encoded as utf-8
                    try:
                        yield (Path(*(ensure_unicode(element, "UTF-8") for element in file_dict[b"path"])),
                               file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

                    # Convert the names in path to unicode by
                    # replacing out all characters that may -even
                    # remotely- cause problems with the '?' character
                    try:
                        yield (Path(*map(self._filter_characters, file_dict[b"path"])), file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

        elif self.metainfo:
            # Single-file torrent
            yield self.get_name_as_unicode(), self.metainfo[b"info"][b"length"]

    def get_files_with_length(self, exts: Optional[str] = None) -> List[Tuple[Path, int]]:
        """ The list of files in the torrent def.
        @param exts (Optional) list of filename extensions (without leading .)
        to search for.
        @return A list of filenames.
        """
        videofiles = []
        for filename, length in self._get_all_files_as_unicode_with_length():
            ext = path_util.Path(filename).suffix
            if ext != "" and ext[0] == ".":
                ext = ext[1:]
            if exts is None or ext.lower() in exts:
                videofiles.append((filename, length))
        return videofiles

    def get_files(self, exts: Optional[Set[str]] = None) -> List[Path]:
        return [filename for filename, _ in self.get_files_with_length(exts)]

    def get_length(self, selectedfiles: Optional[Set[Path]] = None) -> int:
        """ Returns the total size of the content in the torrent. If the
        optional selectedfiles argument is specified, the method returns
        the total size of only those files.
        @return A length (long)
        """
        if self.metainfo:
            return maketorrent.get_length_from_metainfo(self.metainfo, selectedfiles)
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
            return b'files' in self.metainfo[b'info']
        return False

    def is_private(self) -> bool:
        """
        Returns whether this TorrentDef is a private torrent (and is not announced in the DHT).
        """
        try:
            private = int(self.metainfo[b'info'].get(b'private', 0)) if self.metainfo else 0
        except (ValueError, KeyError) as e:
            self._logger.warning(f'{e.__class__.__name__}: {e}')
            private = 0
        return private == 1

    def get_index_of_file_in_files(self, file: Optional[str]) -> int:
        if not self.metainfo:
            raise ValueError("TorrentDef does not have metainfo")
        info = self.metainfo[b'info']

        if file is not None and b'files' in info:
            for i in range(len(info[b'files'])):
                file_dict = info[b'files'][i]

                if b'path.utf-8' in file_dict:
                    intorrentpath = maketorrent.pathlist2filename(file_dict[b'path.utf-8'])
                else:
                    intorrentpath = maketorrent.pathlist2filename(file_dict[b'path'])

                if intorrentpath == path_util.Path(ensure_unicode(file, 'utf8')):
                    return i
            raise ValueError("File not found in torrent")
        else:
            raise ValueError("File not found in single-file torrent")


class TorrentDefNoMetainfo(TorrentDef):
    """
    Instances of this class are used when working with a torrent def that contains no metainfo (yet), for instance,
    when starting a download with only an infohash. Other methods that are using this class do not distinguish between
    a TorrentDef with and without data and may still expect this class to have various methods in TorrentDef
    implemented.
    """

    def __init__(self, infohash: bytes, name: bytes, url: bytes | str | None = None):
        torrent_parameters = {
            b'name': name
        }
        if url is not None:
            torrent_parameters[b'urllist'] = [url]
        super().__init__(torrent_parameters=torrent_parameters)
        self.infohash = infohash

    def get_url(self) -> bytes | str | None:
        if urllist := self.torrent_parameters.get(b'urllist'):
            return urllist[0]
        return None

    @property
    def torrent_info(self) -> lt.torrent_info | None:
        return None

    def load_torrent_info(self) -> None:
        pass

    def get_name_as_unicode(self) -> str:
        return self.get_name_utf8()
