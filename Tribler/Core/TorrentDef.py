"""
Definition of a torrent, that is, a collection of files or a live stream

Author(s): Arno Bakker
"""
import logging
import os
import sys
from hashlib import sha1
from types import StringType, ListType, IntType, LongType

from libtorrent import bencode, bdecode

from Tribler.Core.Utilities import maketorrent
from Tribler.Core.Utilities.utilities import create_valid_metainfo, is_valid_url
from Tribler.Core.Utilities.unicode import dunno2unicode
from Tribler.Core.Utilities.utilities import parse_magnetlink, http_get
from Tribler.Core.defaults import TDEF_DEFAULTS
from Tribler.Core.exceptions import TorrentDefNotFinalizedException, NotYetImplementedException
from Tribler.Core.simpledefs import INFOHASH_LENGTH
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TorrentDef(object):

    """
    Definition of a torrent, that is, all params required for a torrent file,
    plus optional params such as thumbnail, playtime, etc.

    Note: to add fields to the torrent definition which are not supported
    by its API, first create the torrent def, finalize it, then add the
    fields to the metainfo, and create a new torrent def from that
    upgraded metainfo using TorrentDef.load_from_dict()

    cf. libtorrent torrent_info
    """

    def __init__(self, input=None, metainfo=None, infohash=None):
        """ Normal constructor for TorrentDef (The input, metainfo and infohash
        parameters are used internally to make this a copy constructor) """
        assert infohash is None or isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert infohash is None or len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)

        self._logger = logging.getLogger(self.__class__.__name__)

        if input is not None:  # copy constructor
            self.input = input
            # self.metainfo_valid set in copy()
            self.metainfo = metainfo
            self.infohash = infohash
            return

        self.input = {}  # fields added by user, waiting to be turned into torrent file
        # Define the built-in default here
        self.input.update(TDEF_DEFAULTS)
        self.input['encoding'] = sys.getfilesystemencoding()

        self.input['files'] = []

        self.metainfo_valid = False
        self.metainfo = None  # copy of loaded or last saved torrent dict
        self.infohash = None  # only valid if metainfo_valid

        # We cannot set a built-in default for a tracker here, as it depends on
        # a Session. Alternatively, the tracker will be set to the internal
        # tracker by default when Session::start_download() is called, if the
        # 'announce' field is the empty string.

    def __eq__(self, other):
        return (isinstance(other, TorrentDef) and
                self.metainfo_valid == other.metainfo_valid and
                self.input == other.input and
                self.infohash == other.infohash and
                self.metainfo == other.metainfo)

    def __str__(self):
        return str({
            "metainfo_valid": self.metainfo_valid,
            "input": self.input,
            "infohash": self.infohash,
            "metainfo": self.metainfo
        })

    #
    # Class methods for creating a TorrentDef from a .torrent file
    #
    @staticmethod
    def load(filename):
        """
        Load a BT .torrent or Tribler .tribe file from disk and convert
        it into a finalized TorrentDef.

        @param filename  An absolute Unicode filename
        @return TorrentDef
        """
        # Class method, no locking required
        f = open(filename, "rb")
        return TorrentDef._read(f)

    @staticmethod
    def load_from_memory(data):
        """ Loads a torrent file that is already in memory.
        :param data: The torrent file data.
        :return: A TorrentDef object.
        """
        data = bdecode(data)
        return TorrentDef._create(data)

    def _read(stream):
        """ Internal class method that reads a torrent file from stream,
        checks it for correctness and sets self.input and self.metainfo
        accordingly. """
        bdata = stream.read()
        stream.close()
        data = bdecode(bdata)
        return TorrentDef._create(data)
    _read = staticmethod(_read)

    def _create(metainfo):  # TODO: replace with constructor
        # raises ValueErrors if not good
        metainfo_fixed = create_valid_metainfo(metainfo)

        t = TorrentDef()
        t.metainfo = metainfo_fixed
        t.metainfo_valid = True
        # copy stuff into self.input
        maketorrent.copy_metainfo_to_input(t.metainfo, t.input)

        # Two places where infohash calculated, here and in maketorrent.py
        # Elsewhere: must use TorrentDef.get_infohash() to allow P2PURLs.
        t.infohash = sha1(bencode(metainfo['info'])).digest()

        assert isinstance(t.infohash, str), "INFOHASH has invalid type: %s" % type(t.infohash)
        assert len(t.infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(t.infohash)

        return t

    _create = staticmethod(_create)

    @staticmethod
    @blocking_call_on_reactor_thread
    def load_from_url(url):
        """
        Load a BT .torrent or Tribler .tstream file from the URL and
        convert it into a TorrentDef.

        @param url URL
        @return Deferred
        """
        # Class method, no locking required
        def _on_response(data):
            return TorrentDef.load_from_memory(data)

        deferred = http_get(url)
        deferred.addCallback(_on_response)
        return deferred

    @staticmethod
    def load_from_dict(metainfo):
        """
        Load a BT .torrent or Tribler .tribe file from the metainfo dictionary
        it into a TorrentDef

        @param metainfo A dictionary following the BT torrent file spec.
        @return TorrentDef.
        """
        # Class method, no locking required
        return TorrentDef._create(metainfo)

    #
    # Convenience instance methods for publishing new content
    #
    def add_content(self, inpath, outpath=None, playtime=None):
        """
        Add a file or directory to this torrent definition. When adding a
        directory, all files in that directory will be added to the torrent.

        One can add multiple files and directories to a torrent definition.
        In that case the "outpath" parameter must be used to indicate how
        the files/dirs should be named in the torrent. The outpaths used must
        start with a common prefix which will become the "name" field of the
        torrent.

        To seed the torrent via the core (as opposed to e.g. HTTP) you will
        need to start the download with the dest_dir set to the top-level
        directory containing the files and directories to seed. For example,
        a file "c:\Videos\file.avi" is seeded as follows:
        <pre>
            tdef = TorrentDef()
            tdef.add_content("c:\Videos\file.avi",playtime="1:59:20")
            tdef.set_tracker(s.get_internal_tracker_url())
            tdef.finalize()
            dscfg = DownloadStartupConfig()
            dscfg.set_dest_dir("c:\Video")
            s.start_download(tdef,dscfg)
        </pre>
        @param inpath Absolute name of file or directory on local filesystem,
        as Unicode string.
        @param outpath (optional) Name of the content to use in the torrent def
        as Unicode string.
        @param playtime (optional) String representing the duration of the
        multimedia file when played, in [hh:]mm:ss format.
        """
        s = os.stat(inpath)
        d = {'inpath': inpath, 'outpath': outpath, 'playtime': playtime, 'length': s.st_size}
        self.input['files'].append(d)

        self.metainfo_valid = False

    def remove_content(self, inpath):
        """ Remove a file or directory from this torrent definition

        @param inpath Absolute name of file or directory on local filesystem,
        as Unicode string.
        """
        for d in self.input['files']:
            if d['inpath'] == inpath:
                self.input['files'].remove(d)
                break

    #
    # Torrent attributes
    #
    def set_encoding(self, enc):
        """ Set the character encoding for e.g. the 'name' field """
        self.input['encoding'] = enc
        self.metainfo_valid = False

    def get_encoding(self):
        return self.input['encoding']

    def set_tracker(self, url):
        """ Sets the tracker (i.e. the torrent file's 'announce' field).
        @param url The announce URL.
        """
        if not is_valid_url(url):
            raise ValueError("Invalid URL")

        if url.endswith('/'):
            # Some tracker code can't deal with / at end
            url = url[:-1]
        self.input['announce'] = url
        self.metainfo_valid = False

    def get_tracker(self):
        """ Returns the announce URL.
        @return URL """
        return self.input['announce']

    def set_tracker_hierarchy(self, hier):
        """ Set hierarchy of trackers (announce-list) following the spec
        at http://www.bittorrent.org/beps/bep_0012.html
        @param hier A hierarchy of trackers as a list of lists.
        """
        # TODO: check input, in particular remove / at end
        newhier = []
        if not isinstance(hier, ListType):
            raise ValueError("hierarchy is not a list")
        for tier in hier:
            if not isinstance(tier, ListType):
                raise ValueError("tier is not a list")
            newtier = []
            for url in tier:
                if not is_valid_url(url):
                    self._logger.error("Invalid tracker URL: %s", repr(url))
                    continue

                if url.endswith('/'):
                    # Some tracker code can't deal with / at end
                    url = url[:-1]

                if self.get_tracker() is None:
                    # Backwards compatibility Multitracker Metadata Extension
                    self.set_tracker(url)
                newtier.append(url)
            newhier.append(newtier)

        self.input['announce-list'] = newhier
        self.metainfo_valid = False

    def get_tracker_hierarchy(self):
        """ Returns the hierarchy of trackers.
        @return A list of lists. """
        return self.input['announce-list']

    def get_trackers_as_single_tuple(self):
        """ Returns a flat tuple of all known trackers
        @return A tuple containing trackers
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
            return (tracker,)
        return ()

    def set_dht_nodes(self, nodes):
        """ Sets the DHT nodes required by the mainline DHT support,
        See http://www.bittorrent.org/beps/bep_0005.html
        @param nodes A list of [hostname,port] lists.
        """
        # Check input
        if not isinstance(nodes, ListType):
            raise ValueError("nodes not a list")
        else:
            for node in nodes:
                if not isinstance(node, ListType) or len(node) != 2:
                    raise ValueError("node in nodes not a 2-item list: " + repr(node))
                if not isinstance(node[0], StringType):
                    raise ValueError("host in node is not string:" + repr(node))
                if not isinstance(node[1], IntType):
                    raise ValueError("port in node is not int:" + repr(node))

        self.input['nodes'] = nodes
        self.metainfo_valid = False

    def get_dht_nodes(self):
        """ Returns the DHT nodes set.
        @return A list of [hostname,port] lists. """
        return self.input['nodes']

    def set_comment(self, value):
        """ Set comment field.
        @param value A Unicode string.
         """
        self.input['comment'] = value
        self.metainfo_valid = False

    def get_comment(self):
        """ Returns the comment field of the def.
        @return A Unicode string. """
        return self.input['comment']

    def get_comment_as_unicode(self):
        """ Returns the comment field of the def as a unicode string.
        @return A Unicode string. """
        return dunno2unicode(self.input['comment'])

    def set_created_by(self, value):
        """ Set 'created by' field.
        @param value A Unicode string.
        """
        self.input['created by'] = value
        self.metainfo_valid = False

    def get_created_by(self):
        """ Returns the 'created by' field.
        @return Unicode string. """
        return self.input['created by']

    def set_urllist(self, value):
        """ Set list of HTTP seeds following the BEP 19 spec (GetRight style):
        http://www.bittorrent.org/beps/bep_0019.html
        @param value A list of URLs.
        """
        for url in value:
            if not is_valid_url(url):
                raise ValueError("Invalid URL: " + repr(url))

        self.input['url-list'] = value
        self.metainfo_valid = False

    def get_urllist(self):
        """ Returns the list of HTTP seeds.
        @return A list of URLs. """
        return self.input['url-list']

    def set_httpseeds(self, value):
        """ Set list of HTTP seeds following the BEP 17 spec (John Hoffman style):
        http://www.bittorrent.org/beps/bep_0017.html
        @param value A list of URLs.
        """
        for url in value:
            if not is_valid_url(url):
                raise ValueError("Invalid URL: " + repr(url))

        self.input['httpseeds'] = value
        self.metainfo_valid = False

    def get_httpseeds(self):
        """ Returns the list of HTTP seeds.
        @return A list of URLs. """
        return self.input['httpseeds']

    def set_piece_length(self, value):
        """ Set the size of the pieces in which the content is traded.
        The piece size must be a multiple of the chunk size, the unit in which
        it is transmitted, which is 16K by default (see
        DownloadConfig.set_download_slice_size()). The default is automatic
        (value 0).
        @param value A number of bytes as per the text.
        """
        if not (isinstance(value, IntType) or isinstance(value, LongType)):
            raise ValueError("Piece length not an int/long")

        self.input['piece length'] = value
        self.metainfo_valid = False

    def get_piece_length(self):
        """ Returns the piece size.
        @return A number of bytes. """
        return self.input['piece length']

    def get_nr_pieces(self):
        """ Returns the number of pieces.
        @return A number of pieces. """
        return len(self.metainfo['info']['pieces']) / 20

    def get_pieces(self):
        """ Returns the pieces"""
        return self.metainfo['info']['pieces'][:]

    def set_initial_peers(self, value):
        """ Set the initial peers to connect to.
        @param value List of (IP,port) tuples """
        self.input['initial peers'] = value

    def get_initial_peers(self):
        """ Returns the list of initial peers.
        @return List of (IP,port) tuples. """
        if 'initial peers' in self.input:
            return self.input['initial peers']
        else:
            return []

    def finalize(self, userabortflag=None, userprogresscallback=None):
        """ Create BT torrent file by reading the files added with
        add_content() and calculate the torrent file's infohash.

        Creating the torrent file can take a long time and will be carried out
        by the calling thread. The process can be made interruptable by passing
        a threading.Event() object via the userabortflag and setting it when
        the process should be aborted. The also optional userprogresscallback
        will be called by the calling thread periodically, with a progress
        percentage as argument.

        The userprogresscallback function will be called by the calling thread.

        @param userabortflag threading.Event() object
        @param userprogresscallback Function accepting a fraction as first
        argument.
        """
        if self.metainfo_valid:
            return

        # Note: reading of all files and calc of hashes is done by calling
        # thread.
        (infohash, metainfo) = maketorrent.make_torrent_file(self.input,
                                                             userabortflag=userabortflag, userprogresscallback=userprogresscallback)
        if infohash is not None:
            self.infohash = infohash
            self.metainfo = metainfo

            self.input['name'] = metainfo['info']['name']
            # May have been 0, meaning auto.
            self.input['piece length'] = metainfo['info']['piece length']
            self.metainfo_valid = True

        assert self.infohash is None or isinstance(
            self.infohash, str), "INFOHASH has invalid type: %s" % type(self.infohash)
        assert self.infohash is None or len(
            self.infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(self.infohash)

    def is_finalized(self):
        """ Returns whether the TorrentDef is finalized or not.
        @return Boolean. """
        return self.metainfo_valid

    #
    # Operations on finalized TorrentDefs
    #
    def get_infohash(self):
        """ Returns the infohash of the torrent, for non-URL compatible
        torrents. Otherwise it returns the swarm identifier (either the root hash
        (Merkle torrents) or hash of the live-source authentication key.
        @return A string of length 20. """
        if self.metainfo_valid:
            return self.infohash
        else:
            raise TorrentDefNotFinalizedException()

    def get_metainfo(self):
        """ Returns the torrent definition as a dictionary that follows the BT
        spec for torrent files.
        @return dict
        """
        if self.metainfo_valid:
            return self.metainfo
        else:
            raise TorrentDefNotFinalizedException()

    def get_name(self):
        """ Returns the info['name'] field as raw string of bytes.
        @return String """
        if self.metainfo_valid:
            return self.input['name']  # string immutable
        else:
            raise TorrentDefNotFinalizedException()

    def get_name_utf8(self):
        """
        Not all names are utf-8, attempt to construct it as utf-8 anyway.
        """
        out = self.get_name()
        try:
            # Try seeing if the delivered encoding is correct and we
            # can convert to utf8 without any issues.
            return out.decode(self.get_encoding()).encode('utf8').decode('utf8')
        except (LookupError, TypeError, ValueError):
            try:
                # The delivered encoding is incorrect, cast it to
                # latin1 and hope for the best (minor corruption).
                return out.decode('latin1').encode('utf8', 'ignore').decode('utf8')
            except (TypeError, ValueError):
                # This is a very nasty string (e.g. u'\u266b'), remove the illegal entries.
                return out.encode('utf8', 'ignore').decode('utf8')

    def set_name(self, name):
        """ Set the name of this torrent
        @param name name of torrent as String
        """
        self.input['name'] = name
        self.metainfo_valid = False

    def get_name_as_unicode(self):
        """ Returns the info['name'] field as Unicode string.
        @return Unicode string. """
        if not self.metainfo_valid:
            raise TorrentDefNotFinalizedException()

        if "name.utf-8" in self.metainfo["info"]:
            # There is an utf-8 encoded name.  We assume that it is
            # correctly encoded and use it normally
            try:
                return unicode(self.metainfo["info"]["name.utf-8"], "UTF-8")
            except UnicodeError:
                pass

        if "name" in self.metainfo["info"]:
            # Try to use the 'encoding' field.  If it exists, it
            # should contain something like 'utf-8'
            if "encoding" in self.metainfo:
                try:
                    return unicode(self.metainfo["info"]["name"], self.metainfo["encoding"])
                except UnicodeError:
                    pass
                except LookupError:
                    # Some encodings are not supported by python.  For
                    # instance, the MBCS codec which is used by
                    # Windows is not supported (Jan 2010)
                    pass

            # Try to convert the names in path to unicode, without
            # specifying the encoding
            try:
                return unicode(self.metainfo["info"]["name"])
            except UnicodeError:
                pass

            # Try to convert the names in path to unicode, assuming
            # that it was encoded as utf-8
            try:
                return unicode(self.metainfo["info"]["name"], "UTF-8")
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
                return unicode(filter_characters(self.metainfo["info"]["name"]))
            except UnicodeError:
                pass

        # We failed.  Returning an empty string
        return u""

    def save(self, filename):
        """
        Finalizes the torrent def and writes a torrent file i.e., bencoded dict
        following BT spec) to the specified filename. Note this may take a
        long time when the torrent def is not yet finalized.

        @param filename An absolute Unicode path name.
        """
        with open(filename, "wb") as f:
            f.write(self.encode())

    def get_torrent_size(self):
        """
        Finalizes the torrent def and converts the metainfo to string, returns the
        number of bytes the string would take on disk.
        """
        return len(self.encode())

    def encode(self):
        self.finalize()

        # Boudewijn, 10/09/10: do not save the 'initial peers'.  (1)
        # they should not be saved, as they are unlikely to be there
        # the next time, and (2) bencode does not understand tuples
        # and converts the (addres,port) tuple into a list.
        if 'initial peers' in self.metainfo:
            del self.metainfo['initial peers']

        return bencode(self.metainfo)

    def _get_all_files_as_unicode_with_length(self):
        """ Get a generator for files in the torrent def. No filtering
        is possible and all tricks are allowed to obtain a unicode
        list of filenames.
        @return A unicode filename generator.
        """
        assert self.metainfo_valid, "TorrentDef is not finalized"
        if "files" in self.metainfo["info"]:
            # Multi-file torrent
            join = os.path.join
            files = self.metainfo["info"]["files"]

            for file_dict in files:
                if "path.utf-8" in file_dict:
                    # This file has an utf-8 encoded list of elements.
                    # We assume that it is correctly encoded and use
                    # it normally
                    try:
                        yield join(*[unicode(element, "UTF-8") for element in file_dict["path.utf-8"]]), file_dict["length"]
                        continue
                    except UnicodeError:
                        pass

                if "path" in file_dict:
                    # Try to use the 'encoding' field.  If it exists,
                    # it should contain something like 'utf-8'
                    if "encoding" in self.metainfo:
                        encoding = self.metainfo["encoding"]
                        try:
                            yield join(*[unicode(element, encoding) for element in file_dict["path"]]), file_dict["length"]
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
                        yield join(*[unicode(element) for element in file_dict["path"]]), file_dict["length"]
                        continue
                    except UnicodeError:
                        pass

                    # Try to convert the names in path to unicode,
                    # assuming that it was encoded as utf-8
                    try:
                        yield join(*[unicode(element, "UTF-8") for element in file_dict["path"]]), file_dict["length"]
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
                        yield join(*[unicode(filter_characters(element)) for element in file_dict["path"]]), file_dict["length"]
                        continue
                    except UnicodeError:
                        pass

        else:
            # Single-file torrent
            yield self.get_name_as_unicode(), self.metainfo["info"]["length"]

    def get_files_with_length(self, exts=None):
        """ The list of files in the finalized torrent def.
        @param exts (Optional) list of filename extensions (without leading .)
        to search for.
        @return A list of filenames.
        """
        if not self.metainfo_valid:
            raise NotYetImplementedException()  # must save first

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
        if not self.metainfo_valid:
            raise NotYetImplementedException()  # must save first

        return maketorrent.get_length_from_metainfo(self.metainfo, selectedfiles)

    def get_creation_date(self, default=0):
        if not self.metainfo_valid:
            raise NotYetImplementedException()  # must save first

        return self.metainfo.get("creation date", default)

    def is_multifile_torrent(self):
        """ Returns whether this TorrentDef is a multi-file torrent.
        @return Boolean
        """
        if not self.metainfo_valid:
            raise NotYetImplementedException()  # must save first

        return 'files' in self.metainfo['info']

    def is_private(self):
        """ Returns whether this TorrentDef is a private torrent.
        @return Boolean """
        if not self.metainfo_valid:
            raise NotYetImplementedException()

        return int(self.metainfo['info'].get('private', 0)) == 1

    def set_private(self, private=True):
        self.input['private'] = 1 if private else 0

    #
    # Internal methods
    #
    def get_index_of_file_in_files(self, file):
        if not self.metainfo_valid:
            raise NotYetImplementedException()  # must save first

        info = self.metainfo['info']

        if file is not None and 'files' in info:
            for i in range(len(info['files'])):
                file_dict = info['files'][i]

                if 'path.utf-8' in file_dict:
                    intorrentpath = maketorrent.pathlist2filename(file_dict['path.utf-8'])
                else:
                    intorrentpath = maketorrent.pathlist2filename(file_dict['path'])

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
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
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

    def get_name_as_unicode(self):
        return unicode(self.name) if self.name else u''

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
