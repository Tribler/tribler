# Written by Arno Bakker
# see LICENSE.txt for license information
""" Definition of a torrent, that is, a collection of files or a live stream. """
import sys
import os
import copy
import math
from traceback import print_exc, print_stack
from types import StringType, ListType, IntType, LongType
from binascii import hexlify

import Tribler
from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import *
from Tribler.Core.exceptions import *
from Tribler.Core.Base import *
from Tribler.Core.Utilities.bencode import bencode, bdecode
import Tribler.Core.APIImplementation.maketorrent as maketorrent
import Tribler.Core.APIImplementation.makeurl as makeurl
from Tribler.Core.APIImplementation.miscutils import *

from Tribler.Core.Utilities.utilities import validTorrentFile, isValidURL
from Tribler.Core.Utilities.unicode import dunno2unicode
from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout
from Tribler.Core.osutils import *
from Tribler.Core.Utilities.Crypto import sha

from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr


class TorrentDef(ContentDefinition, Serializable, Copyable):

    """
    Definition of a torrent, that is, all params required for a torrent file,
    plus optional params such as thumbnail, playtime, etc.

    Note: to add fields to the torrent definition which are not supported
    by its API, first create the torrent def, finalize it, then add the
    fields to the metainfo, and create a new torrent def from that
    upgraded metainfo using TorrentDef.load_from_dict()

    This class can also be used to create P2P URLs, by calling set_url_compat()
    before finalizing. In that case only name, piece length, tracker, bitrate
    and source-authentication parameters (for live) are configurable.

    cf. libtorrent torrent_info
    """
    def __init__(self, input=None, metainfo=None, infohash=None):
        """ Normal constructor for TorrentDef (The input, metainfo and infohash
        parameters are used internally to make this a copy constructor) """
        assert infohash is None or isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert infohash is None or len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        self.readonly = False
        if input is not None:  # copy constructor
            self.input = input
            # self.metainfo_valid set in copy()
            self.metainfo = metainfo
            self.infohash = infohash
            return

        self.input = {}  # fields added by user, waiting to be turned into torrent file
        # Define the built-in default here
        self.input.update(tdefdefaults)
        try:
            self.input['encoding'] = sys.getfilesystemencoding()
        except:
            self.input['encoding'] = sys.getdefaultencoding()

        self.input['files'] = []

        self.metainfo_valid = False
        self.metainfo = None  # copy of loaded or last saved torrent dict
        self.infohash = None  # only valid if metainfo_valid

        # We cannot set a built-in default for a tracker here, as it depends on
        # a Session. Alternatively, the tracker will be set to the internal
        # tracker by default when Session::start_download() is called, if the
        # 'announce' field is the empty string.
    #
    # Class methods for creating a TorrentDef from a .torrent file
    #
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
    load = staticmethod(load)

    def _read(stream):
        """ Internal class method that reads a torrent file from stream,
        checks it for correctness and sets self.input and self.metainfo
        accordingly. """
        bdata = stream.read()
        stream.close()
        data = bdecode(bdata)
        # print >>sys.stderr,data
        return TorrentDef._create(data)
    _read = staticmethod(_read)

    def _create(metainfo):  # TODO: replace with constructor
        # raises ValueErrors if not good
        validTorrentFile(metainfo)

        t = TorrentDef()
        t.metainfo = metainfo
        t.metainfo_valid = True
        # copy stuff into self.input
        maketorrent.copy_metainfo_to_input(t.metainfo, t.input)

        # For testing EXISTING LIVE, or EXISTING MERKLE: DISABLE, i.e. keep true infohash
        if t.get_url_compat():
            t.infohash = makeurl.metainfo2swarmid(t.metainfo)
        else:
            # Two places where infohash calculated, here and in maketorrent.py
            # Elsewhere: must use TorrentDef.get_infohash() to allow P2PURLs.
            t.infohash = sha(bencode(metainfo['info'])).digest()

        assert isinstance(t.infohash, str), "INFOHASH has invalid type: %s" % type(t.infohash)
        assert len(t.infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(t.infohash)

        # print >>sys.stderr,"INFOHASH",`t.infohash`

        return t

    _create = staticmethod(_create)

    @staticmethod
    def retrieve_from_magnet(url, callback, timeout=30.0, max_connections=30.0):
        """
        If the URL conforms to a magnet link, the .torrent info is
        downloaded and converted into a TorrentDef.  The resulting
        TorrentDef is provided through CALLBACK.

        Returns True when attempting to obtain the TorrentDef, in this
        case CALLBACK will always be called.  Otherwise False is
        returned, in this case CALLBACK will not be called.

        The thread making the callback should be used very briefly.
        """
        assert isinstance(url, str), "URL has invalid type: %s" % type(url)
        assert callable(callback), "CALLBACK must be callable"

        def metainfo_retrieved(metadata):
            tdef = TorrentDef.load_from_dict(metadata)
            callback(tdef)
        LibtorrentMgr.getInstance().get_metainfo(url, metainfo_retrieved, timeout)
        return True

    @staticmethod
    def retrieve_from_magnet_infohash(infohash, callback, timeout=30.0, max_connections=30.0):
        magnetlink = "magnet:?xt=urn:btih:" + hexlify(infohash)
        return TorrentDef.retrieve_from_magnet(magnetlink, callback, timeout, max_connections)

    @staticmethod
    def load_from_url(url):
        """
        If the URL starts with 'http:' load a BT .torrent or Tribler .tstream
        file from the URL and convert it into a TorrentDef. If the URL starts
        with our URL scheme, we convert the URL to a URL-compatible TorrentDef.

        @param url URL
        @return TorrentDef.
        """
        # Class method, no locking required
        if url.startswith(P2PURL_SCHEME):
            (metainfo, swarmid) = makeurl.p2purl2metainfo(url)

            # Metainfo created from URL, so create URL compatible TorrentDef.
            metainfo['info']['url-compat'] = 1

            # For testing EXISTING LIVE: ENABLE, for old EXISTING MERKLE: DISABLE
            # metainfo['info']['name.utf-8'] = metainfo['info']['name']

            t = TorrentDef._create(metainfo)

            return t
        else:
            f = urlOpenTimeout(url)
            return TorrentDef._read(f)

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
    # ContentDefinition interface
    #
    def get_def_type(self):
        """ Returns the type of this Definition
        @return string
        """
        return "torrent"

    def get_id(self):
        """ Returns a identifier for this Definition
        @return string
        """
        return self.get_infohash()

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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        s = os.stat(inpath)
        d = {'inpath': inpath, 'outpath': outpath, 'playtime': playtime, 'length': s.st_size}
        self.input['files'].append(d)

        self.metainfo_valid = False

    def remove_content(self, inpath):
        """ Remove a file or directory from this torrent definition

        @param inpath Absolute name of file or directory on local filesystem,
        as Unicode string.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        for d in self.input['files']:
            if d['inpath'] == inpath:
                self.input['files'].remove(d)
                break

    def create_live(self, name, bitrate, playtime="1:00:00", authconfig=None):
        """ Create a live streaming multimedia torrent with a specific bitrate.

        The authconfig is a subclass LiveSourceAuthConfig with the key
        information required to allow authentication of packets from the source,
        or None. In the latter case there is no source authentication. The other
        two legal values are:
        <pre>
        * An instance of ECDSALiveSourceAuthConfig.
        * An Instance of RSALiveSourceAuthConfig.
        </pre>
        When using the ECDSA method, a sequence number, real-time timestamp and
        an ECDSA signature of 64 bytes is put in each piece. As a result, the
        content in each packet is get_piece_length()-81, so that this into
        account when selecting the bitrate.

        When using the RSA method, a sequence number, real-time timestamp and
        a RSA signature of keysize/8 bytes is put in each piece.

        The info from the authconfig is stored in the 'info' part of the
        torrent file when finalized, so changing the authentication info changes
        the identity (infohash) of the torrent.

        @param name The name of the stream.
        @param bitrate The desired bitrate in bytes per second.
        @param playtime The virtual playtime of the stream as a string in
        [hh:]mm:ss format.
        @param authconfig Parameters for the authentication of the source
        """
        self.input['bps'] = bitrate
        self.input['playtime'] = playtime  # size of virtual content

        # For source auth
        authparams = {}
        if authconfig is None:
            authparams['authmethod'] = LIVE_AUTHMETHOD_NONE
        else:
            authparams['authmethod'] = authconfig.get_method()
            authparams['pubkey'] = authconfig.get_pubkey()

        self.input['live'] = authparams

        d = {'inpath': name, 'outpath': None, 'playtime': None, 'length': None}
        self.input['files'].append(d)

    #
    # Torrent attributes
    #
    def set_encoding(self, enc):
        """ Set the character encoding for e.g. the 'name' field """
        self.input['encoding'] = enc
        self.metainfo_valid = False

    def get_encoding(self):
        return self.input['encoding']

    def set_thumbnail(self, thumbfilename):
        """
        Reads image from file and turns it into a torrent thumbnail
        The file should contain an image in JPEG format, preferably 171x96.

        @param thumbfilename Absolute name of image file, as Unicode string.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        f = open(thumbfilename, "rb")
        data = f.read()
        f.close()
        self.input['thumb'] = data
        self.metainfo_valid = False

    def get_thumbnail(self):
        """ Returns (MIME type,thumbnail data) if present or (None,None)
        @return A tuple. """
        if 'thumb' not in self.input or self.input['thumb'] is None:
            return (None, None)
        else:
            thumb = self.input['thumb']  # buffer/string immutable
            return ('image/jpeg', thumb)

    def set_tracker(self, url):
        """ Sets the tracker (i.e. the torrent file's 'announce' field).
        @param url The announce URL.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        if not isValidURL(url):
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
        at http://www.bittornado.com/docs/multitracker-spec.txt
        @param hier A hierarchy of trackers as a list of lists.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        # TODO: check input, in particular remove / at end
        newhier = []
        if not isinstance(hier, ListType):
            raise ValueError("hierarchy is not a list")
        for tier in hier:
            if not isinstance(tier, ListType):
                raise ValueError("tier is not a list")
            newtier = []
            for url in tier:
                if not isValidURL(url):
                    raise ValueError("Invalid URL: " + repr(url))

                if url.endswith('/'):
                    # Some tracker code can't deal with / at end
                    url = url[:-1]
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

    def has_trackers(self):
        return len(self.get_trackers_as_single_tuple()) > 0

    def set_dht_nodes(self, nodes):
        """ Sets the DHT nodes required by the mainline DHT support,
        See http://www.bittorrent.org/beps/bep_0005.html
        @param nodes A list of [hostname,port] lists.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        for url in value:
            if not isValidURL(url):
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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        for url in value:
            if not isValidURL(url):
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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

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

    def set_add_md5hash(self, value):
        """ Whether to add an end-to-end MD5 checksum to the def.
        @param value Boolean.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['makehash_md5'] = value
        self.metainfo_valid = False

    def get_add_md5hash(self):
        """ Returns whether to add an MD5 checksum. """
        return self.input['makehash_md5']

    def set_add_crc32(self, value):
        """ Whether to add an end-to-end CRC32 checksum to the def.
        @param value Boolean.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['makehash_crc32'] = value
        self.metainfo_valid = False

    def get_add_crc32(self):
        """ Returns whether to add an end-to-end CRC32 checksum to the def.
        @return Boolean. """
        return self.input['makehash_crc32']

    def set_add_sha1hash(self, value):
        """ Whether to add end-to-end SHA1 checksum to the def.
        @param value Boolean.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['makehash_sha1'] = value
        self.metainfo_valid = False

    def get_add_sha1hash(self):
        """ Returns whether to add an end-to-end SHA1 checksum to the def.
        @return Boolean."""
        return self.input['makehash_sha1']

    def set_create_merkle_torrent(self, value):
        """ Create a Merkle torrent instead of a regular BT torrent. A Merkle
        torrent uses a hash tree for checking the integrity of the content
        received. As such it creates much smaller torrent files than the
        regular method. Tribler-specific feature."""
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['createmerkletorrent'] = value
        self.metainfo_valid = False

    def get_create_merkle_torrent(self):
        """ Returns whether to create a Merkle torrent.
        @return Boolean. """
        return self.input['createmerkletorrent']

    def set_signature_keypair_filename(self, value):
        """ Set absolute filename of keypair to be used for signature.
        When set, a signature will be added.
        @param value A filename containing an Elliptic Curve keypair.
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        self.input['torrentsigkeypairfilename'] = value
        self.metainfo_valid = False

    def get_signature_keypair_filename(self):
        """ Returns the filename containing the signing keypair or None.
        @return Unicode String or None. """
        return self.input['torrentsigkeypairfilename']

    def get_live(self):
        """ Returns whether this definition is for a live torrent.
        @return Boolean. """
        return bool('live' in self.input and self.input['live'])

    def get_live_authmethod(self):
        """ Returns the method for authenticating the source.
        <pre>
        LIVE_AUTHMETHOD_ECDSA
        </pre>
        @return String
        """
        return 'live' in self.input and self.input['live']['authmethod']

    def get_live_pubkey(self):
        """ Returns the public key used for authenticating packets from
        the source.
        @return A public key in DER.
        """
        if 'live' in self.input and 'pubkey' in self.input['live']:
            return self.input['live']['pubkey']
        else:
            return None

    def set_url_compat(self, value):
        """ Set the URL compatible value for this definition. Only possible
        for Merkle torrents and live torrents.
        @param value Integer."""

        self.input['url-compat'] = value

    def get_url_compat(self):
        """ Returns whether this definition is URL compatible.
        @return Boolean. """
        return 'url-compat' in self.input and self.input['url-compat']

    #
    # For P2P-transported Ogg streams
    #
    def set_live_ogg_headers(self, value):
        if self.get_url_compat():
            raise ValueError("Cannot use P2PURLs for Ogg streams")
        self.input['ogg-headers'] = value

    def get_live_ogg_headers(self):
        if 'ogg-headers' in self.input:
            return self.input['ogg-headers']
        else:
            return None

    def set_metadata(self, value):
        """ Set the P2P-Next metadata
        @param value binary string """

        self.input['ns-metadata'] = value

    def get_metadata(self):
        """ Returns the stored P2P-Next metadata or None.
        @return binary string. """
        if 'ns-metadata' in self.input:
            return self.input['ns-metadata']
        else:
            return None

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
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

        if self.metainfo_valid:
            return

        if 'live' in self.input:
            # Make sure the duration is an integral number of pieces, for
            # security (live source auth).
            secs = parse_playtime_to_secs(self.input['playtime'])
            pl = float(self.get_piece_length())
            length = float(self.input['bps'] * secs)

            if DEBUG:
                print >> sys.stderr, "TorrentDef: finalize: length", length, "piecelen", pl
            diff = length % pl
            add = (pl - diff) % pl
            newlen = int(length + add)

            # print >>sys.stderr,"CHECK INFO LENGTH",secs,newlen
            d = self.input['files'][0]
            d['length'] = newlen

        # Note: reading of all files and calc of hashes is done by calling
        # thread.
        (infohash, metainfo) = maketorrent.make_torrent_file(self.input, userabortflag=userabortflag, userprogresscallback=userprogresscallback)
        if infohash is not None:

            if self.get_url_compat():
                url = makeurl.metainfo2p2purl(metainfo)
                # Make sure metainfo is preserved, in particular, the url-compat field.
                swarmid = makeurl.metainfo2swarmid(metainfo)
                self.infohash = swarmid
            else:
                self.infohash = infohash
            self.metainfo = metainfo

            self.input['name'] = metainfo['info']['name']
            # May have been 0, meaning auto.
            self.input['piece length'] = metainfo['info']['piece length']
            self.metainfo_valid = True

        assert self.infohash is None or isinstance(self.infohash, str), "INFOHASH has invalid type: %s" % type(self.infohash)
        assert self.infohash is None or len(self.infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(self.infohash)

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
            if self.is_merkle_torrent():
                return self.metainfo['info']['root hash']
            else:
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

    def set_name(self, name):
        """ Set the name of this torrent
        @param name name of torrent as String
        """
        if self.readonly:
            raise OperationNotPossibleAtRuntimeException()

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
                            if DEBUG:
                                print >> sys.stderr, "Bad character filter", ord(char), "isalnum?", char.isalnum()
                            return u"?"
                    return u"".join([filter_character(char) for char in name])
                return unicode(filter_characters(self.metainfo["info"]["name"]))
            except UnicodeError:
                pass

        # We failed.  Returning an empty string
        return u""

    def verify_torrent_signature(self):
        """ Verify the signature on the finalized torrent definition. Returns
        whether the signature was valid.
        @return Boolean.
        """
        if self.metainfo_valid:
            return Tribler.Core.Overlay.permid.verify_torrent_signature(self.metainfo)
        else:
            raise TorrentDefNotFinalizedException()

    def save(self, filename):
        """
        Finalizes the torrent def and writes a torrent file i.e., bencoded dict
        following BT spec) to the specified filename. Note this may take a
        long time when the torrent def is not yet finalized.

        @param filename An absolute Unicode path name.
        """
        if not self.readonly:
            self.finalize()

        # Boudewijn, 10/09/10: do not save the 'initial peers'.  (1)
        # they should not be saved, as they are unlikely to be there
        # the next time, and (2) bencode does not understand tuples
        # and converts the (addres,port) tuple into a list.
        if 'initial peers' in self.metainfo:
            del self.metainfo['initial peers']

        bdata = bencode(self.metainfo)
        f = open(filename, "wb")
        f.write(bdata)
        f.close()

    def get_bitrate(self, file=None):
        """ Returns the bitrate of the specified file. If no file is specified,
        we assume this is a single-file torrent.

        @param file (Optional) the file in the torrent to retrieve the bitrate of.
        @return The bitrate in bytes per second or None.
        """
        if not self.metainfo_valid:
            raise NotYetImplementedException()  # must save first

        return maketorrent.get_bitrate_from_metainfo(file, self.metainfo)

    def get_files_with_length(self, exts=None):
        """ The list of files in the finalized torrent def.
        @param exts (Optional) list of filename extensions (without leading .)
        to search for.
        @return A list of filenames.
        """
        return maketorrent.get_files(self.metainfo, exts)

    def get_files(self, exts=None):
        """ The list of files in the finalized torrent def.
        @param exts (Optional) list of filename extensions (without leading .)
        to search for.
        @return A list of filenames.
        """
        return [filename for filename, _ in maketorrent.get_files(self.metainfo, exts)]

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
                                    if DEBUG:
                                        print >> sys.stderr, "Bad character filter", ord(char), "isalnum?", char.isalnum()
                                    return u"?"
                            return u"".join([filter_character(char) for char in name])
                        yield join(*[unicode(filter_characters(element)) for element in file_dict["path"]]), file_dict["length"]
                        continue
                    except UnicodeError:
                        pass

        else:
            # Single-file torrent
            yield self.get_name_as_unicode(), self.metainfo["info"]["length"]

    def get_files_as_unicode_with_length(self, exts=None):
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

    def get_files_as_unicode(self, exts=None):
        return [filename for filename, _ in self.get_files_as_unicode_with_length(exts)]

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

    def is_merkle_torrent(self):
        """ Returns whether this TorrentDef is a Merkle torrent. Use
        get_create_merkle_torrent() to determine this before finalization.
        @return Boolean """
        if self.metainfo_valid:
            return 'root hash' in self.metainfo['info']
        else:
            raise TorrentDefNotFinalizedException()

    def is_private(self):
        """ Returns whether this TorrentDef is a private torrent. 
        @return Boolean """
        if not self.metainfo_valid:
            raise NotYetImplementedException()

        return int(self.metainfo['info'].get('private', 0)) == 1

    def get_url(self):
        """ Returns the URL representation of this TorrentDef. The TorrentDef
        must be a Merkle or live torrent and must be set to URL-compatible
        before finalizing."""

        if self.metainfo_valid:
            return makeurl.metainfo2p2purl(self.metainfo)
        else:
            raise TorrentDefNotFinalizedException()

    #
    # Internal methods
    #
    def get_index_of_file_in_files(self, file):
        if not self.metainfo_valid:
            raise NotYetImplementedException()  # must save first

        info = self.metainfo['info']

        if file is not None and 'files' in info:
            for i in range(len(info['files'])):
                x = info['files'][i]

                intorrentpath = maketorrent.pathlist2filename(x['path'])
                if intorrentpath == file:
                    return i
            return ValueError("File not found in torrent")
        else:
            raise ValueError("File not found in single-file torrent")

    #
    # Copyable interface
    #
    def copy(self):
        input = copy.copy(self.input)
        metainfo = copy.copy(self.metainfo)
        infohash = self.infohash
        t = TorrentDef(input, metainfo, infohash)
        t.metainfo_valid = self.metainfo_valid
        t.set_cs_keys(self.get_cs_keys_as_ders())
        return t


class TorrentDefNoMetainfo(ContentDefinition, Serializable, Copyable):

    def __init__(self, infohash, name, url=None):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        self.infohash = infohash
        self.name = name
        self.url = url

    def get_name(self):
        return self.name

    def get_def_type(self):
        return "torrent"

    def get_id(self):
        return self.get_infohash()

    def get_infohash(self):
        return self.infohash

    def get_live(self):
        return False

    def get_length(self, selectedfiles=None):
        return 0

    def get_metainfo(self):
        return {'infohash': self.get_infohash(), 'name': self.get_name_as_unicode()}

    def get_url(self):
        return self.url

    def is_multifile_torrent(self):
        return False

    def get_name_as_unicode(self):
        return unicode(self.name)

    def get_files(self, exts=None):
        return []

    def has_trackers(self):
        return False

    def copy(self):
        return TorrentDefNoMetainfo(self.infohash, self.name)
