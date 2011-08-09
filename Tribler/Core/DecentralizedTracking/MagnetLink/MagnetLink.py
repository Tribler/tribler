# Written by Boudewijn Schoon
# see LICENSE.txt for license information
"""
The MagnetLink module handles the retrieval of the 'info' part of a
.torrent file given a magnet link.

Ideally we should use the regular BitTorrent connection classes to
make connection to peers, but all these classes assume that the
.torrent information is already available.

Hence, this module will make BitTorrent connection for the sole
purpose of retrieving the .torrent info part.  After retrieval has
finished all connections are closed and a regular download will begin.
"""
import sys
from binascii import unhexlify
from urlparse import urlsplit
from traceback import print_exc
from threading import Lock

try:
    # parse_sql requires python 2.6 or higher
    from urlparse import parse_qsl
except ImportError:
    from urllib import unquote_plus
    def parse_qsl(query):
        """
        'foo=bar&moo=milk' --> [('foo', 'bar'), ('moo', 'milk')]
        """
        query = unquote_plus(query)
        for part in query.split("&"):
            if "=" in part:
                yield part.split("=", 1)

from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id, IdError
from Tribler.Core.DecentralizedTracking.MagnetLink.MiniBitTorrent import MiniSwarm, MiniTracker
import Tribler.Core.DecentralizedTracking.mainlineDHT as mainlineDHT

DEBUG = False

class Singleton:
    _singleton_lock = Lock()

    @classmethod
    def get_instance(cls, *args, **kargs):
        if hasattr(cls, "_singleton_instance"):
            return getattr(cls, "_singleton_instance")

        else:
            cls._singleton_lock.acquire()
            try:
                if not hasattr(cls, "_singleton_instance"):
                    setattr(cls, "_singleton_instance", cls(*args, **kargs))
                return getattr(cls, "_singleton_instance")
                
            finally:
                cls._singleton_lock.release()

class MagnetHandler(Singleton):
    def __init__(self, raw_server):
        self._raw_server = raw_server
        self._magnets = []

    def get_raw_server(self):
        return self._raw_server

    def add_magnet(self, magnet_link, timeout):
        self._magnets.append(magnet_link)
        self._raw_server.add_task(magnet_link.close, timeout)

    def remove_magnet(self, magnet_link):
        if magnet_link in self._magnets:
            self._magnets.remove(magnet_link)

    def get_magnets(self):
        return self._magnets

class MagnetLink:
    def __init__(self, url, callback, timeout):
        """
        If the URL conforms to a magnet link, the .torrent info is
        downloaded and returned to CALLBACK.
        """
        # _callback is called when the metadata is retrieved.
        self._callback = callback

        dn, xt, trs = self.parse_url(url)

        # _name is the unicode name suggested for the swarm.
        assert dn is None or isinstance(dn, unicode), "DN has invalid type: %s" % type(dn)
        self._name = dn

        # _info_hash is the 20 byte binary info hash that identifies
        # the swarm.
        assert isinstance(xt, str), "XT has invalid type: %s" % type(xt)
        assert len(xt) == 20, "XT has invalid length: %d" % len(xt)
        self._info_hash = xt

        # _tracker is an optional tracker address.
        self._trackers = trs

        # _swarm is a MiniBitTorrent.MiniSwarm instance that connects
        # to peers to retrieve the metadata.
        magnet_handler = MagnetHandler.get_instance()
        magnet_handler.add_magnet(self, timeout)
        self._swarm = MiniSwarm(self._info_hash, magnet_handler.get_raw_server(), self.metainfo_retrieved)

    def get_infohash(self):
        return self._info_hash

    def get_name(self):
        return self._name

    def retrieve(self):
        """
        Start retrieving the metainfo
        
        Returns True when attempting to obtain the metainfo, in this
        case CALLBACK will always be called.  Otherwise False is
        returned, in this case CALLBACK will not be called.
        """
        if self._info_hash:
            # todo: catch the result from get_peers and call its stop
            # method.  note that this object does not yet contain a
            # stop method...
            dht = mainlineDHT.dht
            dht.get_peers(self._info_hash, Id(self._info_hash), self.potential_peers_from_dht, 0)

            try:
                if self._trackers:
                    MiniTracker(self._swarm, self._trackers)
            except:
                print_exc()

            return True
        else:
            print >> sys.stderr, "No Infohash"
            return False

    def potential_peers_from_dht(self, lookup_id, peers):
        if peers:
            self._swarm.add_potential_peers(peers)

    def metainfo_retrieved(self, metainfo, peers=[]):
        """
        Called when info part for metadata is retrieved.  If we have
        more metadata, we will add it at this point.

        PEERS optionally contains a list of valid BitTorrent peers,
        found during metadata download, to help bootstrap the
        download.
        """
        assert isinstance(metainfo, dict)
        assert isinstance(peers, list)
        if __debug__:
            for address in peers:
                assert isinstance(address, tuple)
                assert len(address) == 2
                assert isinstance(address[0], str)
                assert isinstance(address[1], int)

        # create metadata
        metadata = {"info":metainfo}
        if self._trackers:
            if len(self._trackers) > 1:
                metadata["announce-list"] = [self._trackers]
            metadata["announce"] = self._trackers[0]
        else:
            metadata["nodes"] = []
        if peers:
            metadata["initial peers"] = peers

        self._callback(metadata)
        self.close()

    def close(self):
        magnet_handler = MagnetHandler.get_instance()
        magnet_handler.remove_magnet(self)

        if DEBUG:
            print >> sys.stderr, "Magnet.close()"

        # close all MiniBitTorrent activities
        self._swarm.close()

    @staticmethod
    def parse_url(url):
        # url must be a magnet link
        dn = None
        xt = None
        trs = []

        if DEBUG: print >> sys.stderr, "Magnet.parse_url()", url

        schema, netloc, path, query, fragment = urlsplit(url)
        if schema == "magnet":
            # magnet url's do not conform to regular url syntax (they
            # do not have a netloc.)  This causes path to contain the
            # query part.
            if "?" in path:
                pre, post = path.split("?", 1)
                if query:
                    query = "&".join((post, query))
                else:
                    query = post

            for key, value in parse_qsl(query):
                if key == "dn":
                    # convert to unicode
                    dn = value.decode()

                elif key == "xt" and value.startswith("urn:btih:"):
                    xt = unhexlify(value[9:49])

                elif key == "tr":
                    if not value.startswith('udp:'): #Niels: ignoring udp trackers                    
                        trs.append(value)

            if DEBUG: print >> sys.stderr, "Magnet.parse_url() NAME:", dn
            if DEBUG: print >> sys.stderr, "Magnet.parse_url() HASH:", xt
            if DEBUG: print >> sys.stderr, "Magnet.parse_url() TRACS:", trs

        return (dn, xt, trs)
