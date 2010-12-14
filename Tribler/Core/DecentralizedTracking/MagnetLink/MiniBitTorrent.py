# Written by Boudewijn Schoon
# see LICENSE.txt for license information

"""
The MiniBitTorrent module sets up connections to BitTorrent peers with
the sole purpose of obtaining the .Torrent metadata.

The peers are obtained though either the tracker, PEX, or the DHT
provided in the MagnetLink.  All connections will be closed once the
metadata is obtained.
"""

from cStringIO import StringIO
from random import getrandbits 
from threading import Lock, Event, Thread
from time import time
from traceback import print_exc
from urllib import urlopen, urlencode
import sys

from Tribler.Core.BitTornado.BT1.MessageID import protocol_name, EXTEND
from Tribler.Core.BitTornado.BT1.convert import toint, tobinary
from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.BitTornado.SocketHandler import SocketHandler
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Utilities.Crypto import sha

UT_EXTEND_HANDSHAKE = chr(0)
UT_PEX_ID = chr(1)
UT_METADATA_ID = chr(2)
METADATA_PIECE_SIZE = 16 * 1024
MAX_CONNECTIONS = 30
MAX_TIME_INACTIVE = 10 #Current default timeout is 30s, setting inactive time to 10

DEBUG = False

# todo: extend testcases
# todo: add tracker support
# todo: stop the dht

class Connection:
    """
    A single BitTorrent connection.
    """
    def __init__(self, swarm, raw_server, address):
        self._swarm = swarm
        self._closed = False
        self._in_buffer = StringIO()
        self._next_len = 1
        self._next_func = self.read_header_len
        self._address = address
        self._last_activity = time()

        self._her_ut_metadata_id = chr(0)

        # outstanding requests for pieces in piece-id:piece-length pairs
        self._metadata_requests = {}

        if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent: New connection"
        self._socket = raw_server.start_connection(address, self)
        self.write_handshake()

    @property
    def address(self):
        return self._address

    def write_handshake(self):
        # if DEBUG: print >> sys.stderr, "MiniBitTorrent.write_handshake()"
        self._socket.write("".join((chr(len(protocol_name)), protocol_name,
                                    "\x00\x00\x00\x00\x00\x30\x00\x00",
                                    self._swarm.get_info_hash(),
                                    self._swarm.get_peer_id())))

    def write_extend_message(self, metadata_message_id, payload):
        assert isinstance(payload, dict), "PAYLOAD has invalid type: %s" % type(payload)
        assert isinstance(metadata_message_id, str), "METADATA_MESSAGE_ID has invalid type: %s" % type(metadata_message_id)
        assert len(metadata_message_id) == 1, "METADATA_MESSAGE_ID has invalid length: %d" % len(metadata_message_id)
        if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.write_extend_message()"
        payload = bencode(payload)
        self._socket.write("".join((tobinary(2 + len(payload)), # msg len
                                    EXTEND,                     # msg id
                                    metadata_message_id,        # extend msg id
                                    payload)))                  # bencoded msg

    def read_header_len(self, s):
        if ord(s) != len(protocol_name):
            return None
        return len(protocol_name), self.read_header

    def read_header(self, s):
        if s != protocol_name:
            return None
        return 8, self.read_reserved

    def read_reserved(self, s):
        if ord(s[5]) & 16:
            # extend module is enabled
            if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.read_reserved() extend module is supported"
            self.write_extend_message(UT_EXTEND_HANDSHAKE, {"m":{"ut_pex":ord(UT_PEX_ID), "ut_metadata":ord(UT_METADATA_ID), "metadata_size":self._swarm.get_metadata_size()}})
            return 20, self.read_download_id
        else:
            if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.read_reserved() extend module not supported"
            return None

    def read_download_id(self, s):
        if s != self._swarm.get_info_hash():
            if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.read_download_id() invalid info hash"
            return None
        return 20, self.read_peer_id

    def read_peer_id(self, s):
        self._swarm.add_good_peer(self._address)
        return 4, self.read_len

    def read_len(self, s):
        l = toint(s)
        # if l > self.Encoder.max_len:
        #     return None
        # if DEBUG: print >> sys.stderr, "waiting for", l, "bytes"
        return l, self.read_message

    def read_message(self, s):
        if s != '':
            if not self.got_message(s):
                return None
        return 4, self.read_len

    def got_message(self, data):
        if data[0] == EXTEND and len(data) > 2:

            # we only care about EXTEND messages.  So all other
            # messages will NOT reset the _last_activity timestamp.
            self._last_activity = time()

            return self.got_extend_message(data)

        # ignore all other messages, but stay connected
        return True

    def _request_some_metadata_piece(self):
        if not self._closed:
            piece, length = self._swarm.reserve_metadata_piece()
            if isinstance(piece, (int, long)):
                if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Requesting metadata piece", piece
                self._metadata_requests[piece] = length
                self.write_extend_message(self._her_ut_metadata_id, {"msg_type":0, "piece":piece})

            else:
                self._swarm._raw_server.add_task(self._request_some_metadata_piece, 1)

    def got_extend_message(self, data):
        try:
            message = bdecode(data[2:], sloppy=True)
            if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message()", len(message), "bytes as payload"
            # if DEBUG: print >> sys.stderr, message
        except:
            if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Received invalid UT_METADATA message"
            return False

        if data[1] == UT_EXTEND_HANDSHAKE: # extend handshake
            if "metadata_size" in message and isinstance(message["metadata_size"], int) and message["metadata_size"] > 0:
                self._swarm.add_metadata_size_opinion(message["metadata_size"])

            if "m" in message and isinstance(message["m"], dict) and "ut_metadata" in message["m"] and isinstance(message["m"]["ut_metadata"], int):
                self._her_ut_metadata_id = chr(message["m"]["ut_metadata"])
                self._request_some_metadata_piece()

            else:
                # other peer does not support ut_metadata.  Try to get
                # some PEX peers, otherwise close connection
                if not ("m" in message and isinstance(message["m"], dict) and "ut_pex" in message["m"]):
                    return False

        elif data[1] == UT_PEX_ID: # our ut_pex id
            if "added" in message and isinstance(message["added"], str) and len(message["added"]) % 6 == 0:
                added = message["added"]
                addresses = []
                for offset in xrange(0, len(added), 6):
                    address = ("%s.%s.%s.%s" % (ord(added[offset]), ord(added[offset+1]), ord(added[offset+2]), ord(added[offset+3])), ord(added[offset+4]) << 8 | ord(added[offset+5]))
                    addresses.append(address)
                if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message()", len(addresses), "peers from PEX"
                self._swarm.add_potential_peers(addresses)

                # when this peer does not support ut_metadata we can
                # close the connection after receiving a PEX message
                if self._her_ut_metadata_id == chr(0):
                    return False

        elif data[1] == UT_METADATA_ID: # our ut_metadata id
            if "msg_type" in message:
                if message["msg_type"] == 0 and "piece" in message and isinstance(message["piece"], int):
                    # She send us a request.  However, since
                    # MiniBitTorrent disconnects after obtaining the
                    # metadata, we can not provide any pieces
                    # whatsoever.
                    # So... send reject
                    if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Rejecting request for piece", message["piece"]
                    self.write_extend_message(self._her_ut_metadata_id, {"msg_type":2, "piece":message["piece"]})

                elif message["msg_type"] == 1:
                    if not ("piece" in message and isinstance(message["piece"], (int, long)) and message["piece"] in self._metadata_requests):
                        if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() No or invalid piece number", message.get("piece", -1), "?", message.get("piece", -1) in self._metadata_requests
                        return False

                    if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Received metadata piece", message["piece"]
                    length = self._metadata_requests[message["piece"]]
                    self._swarm.add_metadata_piece(message["piece"], data[-length:])
                    del self._metadata_requests[message["piece"]]
                    self._request_some_metadata_piece()

                elif message["msg_type"] == 2 and "piece" in message and isinstance(message["piece"], int) and message["piece"] in self._metadata_requests:
                    # Received a reject
                    if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Our request for", message["piece"], "was rejected"
                    del self._metadata_requests[message["piece"]]
                    self._swarm.unreserve_metadata_piece(message["piece"])

                    # Register a task to run in 'some time' to start
                    # requesting again (reject is usually caused by
                    # flood protection)
                    self._swarm._raw_server.add_task(self._request_some_metadata_piece, 5)

                else:
                    if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Received unknown message"
                    return False

            else:
                if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Received invalid extend message (no msg_type)"
                return False

        else:
            if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.got_extend_message() Received unknown extend message"
            return False
                    
        return True

    def data_came_in(self, socket, data):
        while not self._closed:
            left = self._next_len - self._in_buffer.tell()
            # if DEBUG: print >> sys.stderr, self._in_buffer.tell() + len(data), "/", self._next_len
            if left > len(data):
                self._in_buffer.write(data)
                return
            self._in_buffer.write(data[:left])
            data = data[left:]
            message = self._in_buffer.getvalue()
            self._in_buffer.reset()
            self._in_buffer.truncate()
            next_ = self._next_func(message)
            if next_ is None:
                self.close()
                return
            self._next_len, self._next_func = next_

    def connection_lost(self, socket):
        if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.connection_lost()"
        if not self._closed:
            self._closed = True
            self._swarm.connection_lost(self)

    def connection_flushed(self, socket):
        pass

    def check_for_timeout(self, deadline):
        """
        Close when no activity since DEADLINE
        """
        if self._last_activity < deadline:
            if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.check_for_timeout() Timeout!"
            self.close()

    def close(self):
        if DEBUG: print >> sys.stderr, self._address, "MiniBitTorrent.close()"
        if not self._closed:
            self.connection_lost(self._socket)
            self._socket.close()
        
    def __str__(self):
        return 'MiniBitTorrentCON'+str(self._closed)+str(self._socket.connected)+str(self._swarm._info_hash)
    
class MiniSwarm:
    """
    A MiniSwarm instance maintains an overview of what is going on in
    a single BitTorrent swarm.
    """
    def __init__(self, info_hash, raw_server, callback):
        # _info_hash is the 20 byte binary info hash that identifies
        # the swarm.
        assert isinstance(info_hash, str), str
        assert len(info_hash) == 20
        self._info_hash = info_hash

        # _raw_server provides threading support.  All socket events
        # will run in this thread.
        self._raw_server = raw_server

        # _callback is called with the raw metadata string when it is
        # retrieved
        self._callback = callback

        # _peer_id contains 20 semi random bytes
        self._peer_id = "-ST0100-" + "".join([chr(getrandbits(8)) for _ in range(12)])
        assert isinstance(self._peer_id, str)
        assert len(self._peer_id) == 20, len(self._peer_id)

        # _lock protects several member variables that are accessed
        # from our RawServer and other threads.
        self._lock = Lock()

        # _connections contains all open socket connections.  This
        # variable is protected by _lock.
        self._connections = []

        # _metadata_blocks contains the blocks that form the metadata
        # that we want to download.  This variable is protected by
        # _lock.
        self._metadata_blocks = [] # [requested, piece, data]

        # _metadata_size contains the size in bytes of the metadata.
        # This value is based on the opinions of other peers which is
        # accumulated in _metadata_size_opinions.
        self._metadata_size = 0
        self._metadata_size_opinions = {} # size:number-of-votes

        # _potential_peers contains a dictionary of address::timestamp
        # pairs where potential BitTorrent peers can be found
        self._potential_peers = {}

        # _good_peers contains a dictionary of address:timestamp pairs
        # where valid BitTorrent peers can be found
        self._good_peers = {}

        # _closed indicates that we no longer need this swarm instance
        self._closed = False

        # scan for old connections
        self._raw_server.add_task(self._timeout_connections, 5)

    def add_good_peer(self, address):
        assert isinstance(address, tuple)
        assert len(address) == 2
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        self._good_peers[address] = time()

    def get_info_hash(self):
        return self._info_hash

    def get_peer_id(self):
        return self._peer_id

    def get_metadata_size(self):
        return self._metadata_size

    def add_metadata_size_opinion(self, metadata_size):
        """
        A peer told us the metadata size.  Assume it is correct,
        however, keep track of potential differences.
        """
        if metadata_size in self._metadata_size_opinions:
            self._metadata_size_opinions[metadata_size] += 1
        else:
            self._metadata_size_opinions[metadata_size] = 1

        # what do we believe the metadata size is
        if len(self._metadata_size_opinions) == 1:
            metadata_size = self._metadata_size_opinions.keys()[0]
            if DEBUG: print >> sys.stderr, "MiniBitTorrent.add_metadata_size_opinion() Metadata size is:", metadata_size, "(%d unanimous vote)" % sum(self._metadata_size_opinions.values())

        else:
            options = [(weight, metadata_size) for metadata_size, weight in self._metadata_size_opinions.iteritems()]
            options.sort(reverse=True)
            if DEBUG: print >> sys.stderr, "MiniBitTorrent.add_metadata_size_opinion() Choosing metadata size from multiple options:", options
            metadata_size = options[0][1]

        if self._metadata_size != metadata_size:
            self._metadata_size = metadata_size

            pieces = metadata_size / METADATA_PIECE_SIZE
            if metadata_size % METADATA_PIECE_SIZE != 0:
                pieces += 1

            # we were led to believe that there are more blocks than
            # there actually are, remove some
            if len(self._metadata_blocks) > pieces:
                if DEBUG: print >> sys.stderr, "MiniBitTorrent.add_metadata_size_opinion() removing some blocks..."
                self._metadata_blocks = [block_tuple for block_tuple in self._metadata_blocks if block_tuple[1] < pieces]

            # we were led to believe that there are fewer blocks than
            # there actually are, add some
            elif len(self._metadata_blocks) < pieces:
                blocks = [[0, piece, None] for piece in xrange(len(self._metadata_blocks), pieces)]
                if DEBUG: print >> sys.stderr, "MiniBitTorrent.add_metadata_size_opinion() adding", len(blocks), "blocks..."
                self._metadata_blocks.extend(blocks)

    def reserve_metadata_piece(self):
        """
        A metadata piece request can be made.  Find the most usefull
        piece to request.
        """
        for block_tuple in self._metadata_blocks:
            if block_tuple[2] is None:
                block_tuple[0] += 1
                self._metadata_blocks.sort()

                if block_tuple[1] < len(self._metadata_blocks) - 1:
                    length = METADATA_PIECE_SIZE
                else:
                    length = self._metadata_size % METADATA_PIECE_SIZE

                return block_tuple[1], length
        return None, None

    def unreserve_metadata_piece(self, piece):
        """
        A metadata piece request is refused or cancelled.  Update the
        priorities.
        """
        for index, block_tuple in zip(xrange(len(self._metadata_blocks)), self._metadata_blocks):
            if block_tuple[1] == piece:
                block_tuple[0] = max(0, block_tuple[0] - 1)
                self._metadata_blocks.sort()
                break

    def add_metadata_piece(self, piece, data):
        """
        A metadata piece was received
        """
        if not self._closed:

            for index, block_tuple in zip(xrange(len(self._metadata_blocks)), self._metadata_blocks):
                if block_tuple[1] == piece:
                    block_tuple[0] = max(0, block_tuple[0] - 1)
                    block_tuple[2] = data
                    self._metadata_blocks.sort()
                    break

            # def p(s):
            #     if s is None: return 0
            #     return len(s)
            # if DEBUG: print >> sys.stderr, "Progress:", [p(t[2]) for t in self._metadata_blocks]

            # see if we are done
            for requested, piece, data in self._metadata_blocks:
                if data is None:
                    break

            else:
                # _metadata_blocks is sorted by requested count.  we need to sort it by piece-id
                metadata_blocks = [(piece, data) for _, piece, data in self._metadata_blocks]
                metadata_blocks.sort()

                metadata = "".join([data for _, data in metadata_blocks])
                info_hash = sha(metadata).digest()

                if info_hash == self._info_hash:
                    if DEBUG: print >> sys.stderr, "MiniBitTorrent.add_metadata_piece() Done!"

                    # get nice list with recent BitTorrent peers, sorted
                    # by most recently connected
                    peers = [(timestamp, address) for address, timestamp in self._good_peers.iteritems()]
                    peers.sort(reverse=True)
                    peers = [address for _, address in peers]

                    self._callback(bdecode(metadata), peers)

                else:
                    # for piece, data in metadata_blocks:
                    #     open("failed-hash-{0}.data".format(piece), "w+").write(data)

                    # todo: hash failed... now what?
                    # quick solution... remove everything and try again
                    if DEBUG: print >> sys.stderr, "MiniBitTorrent.add_metadata_piece() Failed hashcheck! Restarting all over again :("
                    self._metadata_blocks = [[requested, piece, None] for requested, piece, data in self._metadata_blocks]
 
    def add_potential_peers(self, addresses):
        if not self._closed:
            self._lock.acquire()
            try:
                for address in addresses:
                    if not address in self._potential_peers:
                        self._potential_peers[address] = 0
            finally:
                self._lock.release()

            if len(self._connections) < MAX_CONNECTIONS:
                self._create_connections()

    def _create_connections(self):
        now = time()

        # order by last connection attempt
        self._lock.acquire()
        try:
            addresses = [(timestamp, address) for address, timestamp in self._potential_peers.iteritems() if timestamp + 60 < now]
            if DEBUG:
                print >> sys.stderr, len(self._connections), "/", len(self._potential_peers), "->", len(addresses)
        finally:
            self._lock.release()
        addresses.sort()

        for timestamp, address in addresses:
            if len(self._connections) >= MAX_CONNECTIONS:
                break

            already_on_this_address = False
            for connection in self._connections:
                if connection.address == address:
                    already_on_this_address = True
                    break
            if already_on_this_address:
                continue

            try:
                connection = Connection(self, self._raw_server, address)

            except:
                connection = None
                if DEBUG: print >> sys.stderr, "MiniBitTorrent.add_potential_peers() ERROR"
                print_exc()

            self._lock.acquire()
            try:
                self._potential_peers[address] = now
                if connection:
                    self._connections.append(connection)
            finally:
                self._lock.release()

    def _timeout_connections(self):
        deadline = time() - MAX_TIME_INACTIVE
        for connection in self._connections:
            connection.check_for_timeout(deadline)

        if not self._closed:
            self._raw_server.add_task(self._timeout_connections, 1)

    def connection_lost(self, connection):
        try:
            self._connections.remove(connection)
        except:
            # it is possible that a connection timout occurs followed
            # by another connection close from the socket handler when
            # the connection can not be established.
            pass
        if not self._closed:
            self._create_connections()

    def close(self):
        if not self._closed:
            self._closed = True
            for connection in self._connections:
                connection.close()

class MiniTracker(Thread):
    """
    A MiniTracker instance makes a single connection to a tracker to
    attempt to obtain peer addresses.
    """
    def __init__(self, swarm, tracker):
        Thread.__init__(self)
        self._swarm = swarm
        self._tracker = tracker
        self.start()

    def run(self):
        announce = self._tracker + "?" + urlencode({"info_hash":self._swarm.get_info_hash(),
                                                    "peer_id":self._swarm.get_peer_id(),
                                                    "port":"12345",
                                                    "compact":"1",
                                                    "uploaded":"0",
                                                    "downloaded":"0",
                                                    "left":"-1",
                                                    "event":"started"})
        handle = urlopen(announce)
        if handle:
            body = handle.read()
            if body:
                try:
                    body = bdecode(body)

                except:
                    pass
                
                else:
                    # using low-bandwidth binary format
                    peers = []
                    peer_data = body["peers"]
                    for x in range(0, len(peer_data), 6):
                        key = peer_data[x:x+6]
                        ip = ".".join([str(ord(i)) for i in peer_data[x:x+4]])
                        port = (ord(peer_data[x+4]) << 8) | ord(peer_data[x+5])
                        peers.append((ip, port))

                    if DEBUG: print >> sys.stderr, "MiniTracker.run() received", len(peers), "peer addresses from tracker"
                    self._swarm.add_potential_peers(peers)
