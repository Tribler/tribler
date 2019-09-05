"""
Author(s): Arno Bakker
"""
from __future__ import absolute_import, division

import logging
import os
from hashlib import sha1

import libtorrent as lt
from libtorrent import bdecode, bencode

from six import binary_type, ensure_binary, integer_types, text_type

from Tribler.Core.Utilities import maketorrent
from Tribler.Core.Utilities.torrent_utils import create_torrent_file
from Tribler.Core.Utilities.unicode import ensure_unicode
from Tribler.Core.Utilities.utilities import http_get, is_valid_url, parse_magnetlink
from Tribler.Core.simpledefs import INFOHASH_LENGTH


def escape_as_utf8(string, encoding='utf8'):
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
            # This is a very nasty string (e.g. u'\u266b'), remove the illegal entries.
            return string.encode('utf8', 'ignore').decode('utf8')


def convert_dict_unicode_to_bytes(orig_dict):
    result = {}
    for k, v in orig_dict.items():
        k = k.encode('utf-8') if isinstance(k, text_type) else k
        if isinstance(v, dict):
            result[k] = convert_dict_unicode_to_bytes(v)
        else:
            result[k] = v.encode('utf-8') if isinstance(v, text_type) else v
    return result


class TorrentDef(object):
    """
    This object acts as a wrapper around some libtorrent metadata.
    It can be used to create new torrents, or analyze existing ones.
    """

    def __init__(self, metainfo=None, torrent_parameters=None):
        """
        Create a new TorrentDef object, possibly based on existing data.
        :param metainfo: A dictionary with metainfo, i.e. from a .torrent file.
        :param torrent_parameters: User-defined parameters for the new TorrentDef.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.torrent_parameters = {}
        self.metainfo = None
        self.files_list = []
        self.infohash = None

        if metainfo is not None:
            # First, make sure the passed metainfo is valid
            try:
                lt.torrent_info(metainfo)
            except RuntimeError as exc:
                raise ValueError(str(exc))
            self.metainfo = metainfo
            self.infohash = sha1(bencode(self.metainfo[b'info'])).digest()
            self.copy_metainfo_to_torrent_parameters()

        elif torrent_parameters:
            self.torrent_parameters.update(torrent_parameters)

    def copy_metainfo_to_torrent_parameters(self):
        """
        Populate the torrent_parameters dictionary with information from the metainfo.
        """
        for key in [b"comment", b"created by", b"creation date", b"announce", b"announce-list", b"nodes",
                    b"httpseeds", b"urllist"]:
            if self.metainfo and key in self.metainfo:
                self.torrent_parameters[key] = self.metainfo[key]

        infokeys = [b'name', b'piece length']
        for key in infokeys:
            if self.metainfo and key in self.metainfo[b'info']:
                self.torrent_parameters[key] = self.metainfo[b'info'][key]

    @staticmethod
    def load(filepath):
        """
        Create a TorrentDef object from a .torrent file
        :param filepath: The path to the .torrent file
        """
        with open(filepath, "rb") as torrent_file:
            file_content = torrent_file.read()
        return TorrentDef.load_from_memory(file_content)

    @staticmethod
    def load_from_memory(bencoded_data):
        """
        Load some bencoded data into a TorrentDef.
        :param bencoded_data: The bencoded data to decode and use as metainfo
        """
        metainfo = bdecode(bencoded_data)
        return TorrentDef.load_from_dict(metainfo)

    @staticmethod
    def load_from_dict(metainfo):
        """
        Load a metainfo dictionary into a TorrentDef object.
        :param metainfo: The metainfo dictionary
        """
        return TorrentDef(metainfo=metainfo)

    @staticmethod
    def load_from_url(url):
        """
        Create a TorrentDef with information from a remote source.
        :param url: The HTTP/HTTPS url where to fetch the torrent info from.
        """
        # Class method, no locking required
        def _on_response(data):
            return TorrentDef.load_from_memory(data)

        deferred = http_get(url)
        deferred.addCallback(_on_response)
        return deferred

    def add_content(self, file_path):
        """
        Add some content to the torrent file.
        :param file_path: The (absolute) path of the file to add.
        """
        self.files_list.append(os.path.abspath(file_path))

    def set_encoding(self, enc):
        """
        Set the character encoding for e.g. the 'name' field
        :param enc: The new encoding of the file.
        """
        self.torrent_parameters[b'encoding'] = enc

    def get_encoding(self):
        """
        Returns the used encoding of the TorrentDef.
        """
        return self.torrent_parameters.get(b'encoding', b'utf-8')

    def set_tracker(self, url):
        """
        Set the tracker of this torrent, according to a given URL.
        :param url: The tracker url.
        """
        if not is_valid_url(url):
            raise ValueError("Invalid URL")

        if url.endswith('/'):  # Some tracker code can't deal with / at end
            url = url[:-1]
        self.torrent_parameters[b'announce'] = url

    def get_tracker(self):
        """
        Returns the torrent announce URL.
        """
        return self.torrent_parameters.get(b'announce', None)

    def get_tracker_hierarchy(self):
        """
        Returns the hierarchy of trackers.
        """
        return self.torrent_parameters.get(b'announce-list', [])

    def get_trackers_as_single_tuple(self):
        """
        Returns a flat tuple of all known trackers.
        """
        if self.get_tracker_hierarchy():
            trackers = []
            for level in self.get_tracker_hierarchy():
                for tracker in level:
                    if tracker and tracker not in trackers:
                        trackers.append(tracker)
            return tuple(trackers)
        tracker = self.get_tracker()
        if tracker:
            return tracker,
        return ()

    def set_piece_length(self, piece_length):
        """
        Set the size of the pieces in which the content is traded.
        The piece size must be a multiple of the chunk size, the unit in which
        it is transmitted, which is 16K by default. The default is automatic (value 0).
        :param piece_length: The piece length.
        """
        if not isinstance(piece_length, integer_types):
            raise ValueError("Piece length not an int/long")

        self.torrent_parameters[b'piece length'] = piece_length

    def get_piece_length(self):
        """
        Returns the piece size.
        """
        return self.torrent_parameters.get(b'piece length', 0)

    def get_nr_pieces(self):
        """
        Returns the number of pieces.
        """
        if not self.metainfo:
            return 0
        return len(self.metainfo[b'info'][b'pieces']) // 20

    def get_pieces(self):
        """
        Returns the pieces.
        """
        if not self.metainfo:
            return []
        return self.metainfo[b'info'][b'pieces'][:]

    def get_infohash(self):
        """
        Returns the infohash of the torrent, if metainfo is provided. Might be None if no metainfo is provided.
        """
        return self.infohash

    def get_metainfo(self):
        """
        Returns the metainfo of the torrent. Might be None if no metainfo is provided.
        """
        return self.metainfo

    def get_name(self):
        """
        Returns the name as raw string of bytes.
        """
        return self.torrent_parameters[b'name']

    def get_name_utf8(self):
        """
        Not all names are utf-8, attempt to construct it as utf-8 anyway.
        """
        return escape_as_utf8(self.get_name(), self.get_encoding())

    def set_name(self, name):
        """
        Set the name of this torrent.
        :param name: The new name of the torrent
        """
        self.torrent_parameters[b'name'] = name

    def get_name_as_unicode(self):
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
                def filter_characters(name):
                    def filter_character(char):
                        if 0 < ord(char) < 128:
                            return char
                        else:
                            self._logger.debug("Bad character filter %s, isalnum? %s", ord(char), char.isalnum())
                            return u"?"
                    return u"".join([filter_character(char) for char in name])
                return text_type(filter_characters(self.metainfo[b"info"][b"name"]))
            except UnicodeError:
                pass

        # We failed.  Returning an empty string
        return u""

    def save(self, torrent_filepath=None):
        """
        Generate the metainfo and save the torrent file.
        :param torrent_filepath: An optional absolute path to where to save the generated .torrent file.
        """
        torrent_dict = create_torrent_file(self.files_list, self.torrent_parameters, torrent_filepath=torrent_filepath)
        self.metainfo = bdecode(torrent_dict['metainfo'])
        self.copy_metainfo_to_torrent_parameters()
        self.infohash = torrent_dict['infohash']

    def _get_all_files_as_unicode_with_length(self):
        """ Get a generator for files in the torrent def. No filtering
        is possible and all tricks are allowed to obtain a unicode
        list of filenames.
        @return A unicode filename generator.
        """
        if self.metainfo and b"files" in self.metainfo[b"info"]:
            # Multi-file torrent
            join = os.path.join
            files = self.metainfo[b"info"][b"files"]

            for file_dict in files:
                if b"path.utf-8" in file_dict:
                    # This file has an utf-8 encoded list of elements.
                    # We assume that it is correctly encoded and use
                    # it normally
                    try:
                        yield (join(*[ensure_unicode(element, "UTF-8") for element in file_dict[b"path.utf-8"]]),
                               file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

                if b"path" in file_dict:
                    # Try to use the 'encoding' field.  If it exists,
                    # it should contain something like 'utf-8'
                    if b"encoding" in self.metainfo:
                        encoding = self.metainfo[b"encoding"]
                        try:
                            yield (join(*[ensure_unicode(element, encoding) for element in file_dict[b"path"]]),
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
                    # without specifying the encoding
                    try:
                        yield join(*[text_type(element) for element in file_dict[b"path"]]), file_dict[b"length"]
                        continue
                    except UnicodeError:
                        pass

                    # Try to convert the names in path to unicode,
                    # assuming that it was encoded as utf-8
                    try:
                        yield (join(*[ensure_unicode(element, "UTF-8") for element in file_dict[b"path"]]),
                               file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

                    # Convert the names in path to unicode by
                    # replacing out all characters that may -even
                    # remotely- cause problems with the '?' character
                    try:
                        def filter_characters(name):
                            def filter_character(char):
                                if 0 < ord(char) < 128:
                                    return char
                                else:
                                    self._logger.debug(
                                        "Bad character filter %s, isalnum? %s", ord(char), char.isalnum())
                                    return u"?"
                            return u"".join([filter_character(char) for char in name])
                        yield (join(*[text_type(filter_characters(element)) for element in file_dict[b"path"]]),
                               file_dict[b"length"])
                        continue
                    except UnicodeError:
                        pass

        elif self.metainfo:
            # Single-file torrent
            yield self.get_name_as_unicode(), self.metainfo[b"info"][b"length"]

    def get_files_with_length(self, exts=None):
        """ The list of files in the torrent def.
        @param exts (Optional) list of filename extensions (without leading .)
        to search for.
        @return A list of filenames.
        """
        videofiles = []
        for filename, length in self._get_all_files_as_unicode_with_length():
            prefix, ext = os.path.splitext(filename)
            if ext != "" and ext[0] == ".":
                ext = ext[1:]
            if exts is None or ext.lower() in exts:
                videofiles.append((filename, length))
        return videofiles

    def get_files(self, exts=None):
        return [filename for filename, _ in self.get_files_with_length(exts)]

    def get_length(self, selectedfiles=None):
        """ Returns the total size of the content in the torrent. If the
        optional selectedfiles argument is specified, the method returns
        the total size of only those files.
        @return A length (long)
        """
        if self.metainfo:
            return maketorrent.get_length_from_metainfo(self.metainfo, selectedfiles)
        return 0

    def get_creation_date(self):
        """
        Returns the creation date of the torrent.
        """
        return self.metainfo.get(b"creation date", 0) if self.metainfo else 0

    def is_multifile_torrent(self):
        """
        Returns whether this TorrentDef is a multi-file torrent.
        """
        if self.metainfo:
            return b'files' in self.metainfo[b'info']
        return False

    def is_private(self):
        """
        Returns whether this TorrentDef is a private torrent (and is not announced in the DHT).
        """
        return (int(self.metainfo[b'info'].get(b'private', 0)) == 1) if self.metainfo else False

    def get_index_of_file_in_files(self, file):
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

                if intorrentpath == file:
                    return i
            raise ValueError("File not found in torrent")
        else:
            raise ValueError("File not found in single-file torrent")


class TorrentDefNoMetainfo(object):
    """
    Instances of this class are used when working with a torrent def that contains no metainfo (yet), for instance,
    when starting a download with only an infohash. Other methods that are using this class do not distinguish between
    a TorrentDef with and without data and may still expect this class to have various methods in TorrentDef
    implemented.
    """

    def __init__(self, infohash, name, url=None):
        assert isinstance(infohash, binary_type), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        self.infohash = infohash
        self.name = name
        self.url = url

    def get_name(self):
        return self.name

    def get_infohash(self):
        return self.infohash

    def get_length(self, selectedfiles=None):
        return 0

    def get_metainfo(self):
        return None

    def get_url(self):
        return self.url

    def is_multifile_torrent(self):
        return False

    def get_name_utf8(self):
        """
        Not all names are utf-8, attempt to construct it as utf-8 anyway.
        """
        return escape_as_utf8(ensure_binary(self.get_name()))

    def get_name_as_unicode(self):
        return ensure_unicode(self.name, 'utf-8')

    def get_files(self, exts=None):
        return []

    def get_files_with_length(self, exts=None):
        return []

    def get_trackers_as_single_tuple(self):
        if self.url and self.url.startswith('magnet:'):
            _, _, trs = parse_magnetlink(self.url)
            return tuple(trs)
        return ()

    def is_private(self):
        return False

    def get_nr_pieces(self):
        return 0
