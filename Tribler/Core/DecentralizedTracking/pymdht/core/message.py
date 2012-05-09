# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""
The message module contains all the data structures needed to create, encode,
and decode valid MDHT messages.

Outgoing messages are built from a few parameters. They are immutable and can
oly be stamped once.

Incoming messages are built from bencoded data. They are automatically
sanitized.

"""

import sys

import logging

import ptime as time
import bencode
from identifier import Id, ID_SIZE_BYTES, IdError
from node import Node
import message_tools as mt

logger = logging.getLogger('dht')


#NEXTSHARE_VERSION = 'NS\8\3' # 11.8.3

# High level keys
TYPE = 'y'     # Message's type
ARGS = 'a'     # Query's arguments in a dictionary
RESPONSE = 'r' # Reply dictionary
ERROR = 'e'    # Error message string
TID = 't'      # Transaction ID
QUERY = 'q'    # Query command (only for queries)
VERSION = 'v'  # Client's version

# Valid values for key TYPE
QUERY = 'q'    # Query
RESPONSE = 'r' # Response
ERROR = 'e'    # Error

# Valid values for key QUERY
PING = 'ping'
FIND_NODE = 'find_node'
GET_PEERS = 'get_peers'
ANNOUNCE_PEER = 'announce_peer'

# Valid keys for ARGS
ID = 'id'         # Node's nodeID (all queries)
TARGET = 'target' # Target's nodeID (find_node)
INFO_HASH = 'info_hash' # Torrent's info_hash (get_peers and announce)
PORT = 'port'     # BitTorrent port (announce)
TOKEN = 'token'   # Token (announce)

# Valid keys for RESPONSE
ID = 'id'         # Node's nodeID (all replies)
NODES = 'nodes'   # String of nodes in compact format (find_nodes and get_peers)
NODES2 = 'nodes2' # Same as previous (with IPv6 support)
TOKEN = 'token'   # Token (get_peers)
PEERS = VALUES = 'values' # List of peers in compact format (get_peers)

# Valid values for ERROR
GENERIC_E = [201, 'Generic Error']
SERVER_E = [202, 'Server Error']
PROTOCOL_E = [203, 'Protocol Error']
UNKNOWN_E = [204, 'Method Unknown']

# Valid BT ports (for announcements)
MIN_BT_PORT = 1 #TODO: lower it to 1024? Let tracker decide.
MAX_BT_PORT = 2**16


def version_repr(v):
    if v:
        return v[:2] + ''.join(['%02x' % (ord(n)) for n in v[2:]])
    else:
        return 'None'


class MsgError(Exception):
    """Raised anytime something goes wrong (specially when
    decoding/sanitizing).

    """

class MsgFactory(object):

    def __init__(self, version_label, src_id, private_dht_name=None):
        self.version_label = version_label
        self.src_id = src_id
        self.private_dht_name = private_dht_name

    def outgoing_ping_query(self, dst_node, experimental_obj=None):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_query(self.src_id, experimental_obj)
        msg.ping_query()
        return msg
    
    def outgoing_find_node_query(self, dst_node, target,
                                 lookup_obj=None, experimental_obj=None):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_query(self.src_id, experimental_obj, lookup_obj)
        msg.find_node_query(target)
        return msg
    
    def outgoing_get_peers_query(self, dst_node, info_hash, lookup_obj=None,
                                experimental_obj=None):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_query(self.src_id, experimental_obj, lookup_obj)
        msg.get_peers_query(info_hash)
        return msg
    
    def outgoing_announce_peer_query(self, dst_node, info_hash, port, token,
                                     experimental_obj=None):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_query(self.src_id, experimental_obj)
        msg.announce_peer_query(info_hash, port, token)
        return msg
    
    def outgoing_ping_response(self, dst_node):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_response(self.src_id)
        msg.ping_response()
        return msg
    
    def outgoing_find_node_response(self, dst_node, nodes):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_response(self.src_id)
        msg.find_node_response(nodes)
        return msg
    
    def outgoing_get_peers_response(self, dst_node, token=None,
                                    nodes=None, peers=None):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_response(self.src_id)
        msg.get_peers_response(token, nodes, peers)
        return msg
    
    def outgoing_announce_peer_response(self, dst_node):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.make_response(self.src_id)
        msg.announce_peer_response()
        return msg

    def outgoing_error(self, dst_node, error):
        msg = OutgoingMsg(self.version_label, dst_node,
                          self.private_dht_name)
        msg.outgoing_error(error)
        return msg
    
    def incoming_msg(self, datagram):
        msg = IncomingMsg(self.private_dht_name, datagram)
        return msg

class OutgoingMsg(object):
    """
    """

    def __init__(self, version_label, dst_node, private_dht_name):
        self.dst_node = dst_node
        self._dict = {VERSION: version_label}
        if private_dht_name:
            self._dict['d'] = private_dht_name
        self._already_encoded = False
    
    def __str__(self):
        return str(self._dict)

    def __repr__(self):
        return str(self.__class__) + str(self)

    def stamp(self, tid):
        """
        Return a Datagram object ready to be sent over the network. The
        message's state is changed internally to reflect that this message has
        been stamped. This call will raise MsgError if the message has already
        been stamped.
        
        """
        
        if TID in self._dict:
            raise MsgError, 'Message has already been stamped'
        self._dict[TID] = tid
        self.sending_ts = time.time()
        return bencode.encode(self._dict)
      
        
    @property
    def query(self):
        return self._dict[QUERY]

    @property
    def tid(self):
        return self._dict[TID]

    def match_response(self, response_msg):
      """
      Return a boolean indicating whether 'response\_msg' matches this
      outgoing query. If so, as a side effect, the round trip time is
      calculated and stored in 'self.rtt'. 'self.got\_response' is set to
      True.
      
      """
      matched = self._dict[TID][0] == response_msg.tid[0]
      if matched:
          self.rtt = time.time() - self.sending_ts
          self.got_response = True            
          if response_msg.type == RESPONSE and not self.dst_node.id:
              self.dst_node.id = response_msg.src_node.id
      return matched

    def make_query(self, src_id, experimental_obj=None,
                   lookup_obj=None):
        self._dict[TYPE] = QUERY
        self._dict[ARGS] = {ID: src_id.bin_id}
        self.lookup_obj = lookup_obj
        self.experimental_obj = experimental_obj
        self.got_response = False

    def ping_query(self):
        self._dict[QUERY] = PING

    def find_node_query(self, target):
        self._dict[QUERY] = FIND_NODE
        self._dict[ARGS][TARGET] = str(target)
        self.target = target

    def get_peers_query(self, info_hash):
        self._dict[QUERY] = GET_PEERS
        self._dict[ARGS][INFO_HASH] = str(info_hash)

    def announce_peer_query(self, info_hash, port, token):
        self._dict[QUERY] = ANNOUNCE_PEER
        self._dict[ARGS][INFO_HASH] = str(info_hash)
        self._dict[ARGS][PORT] = port
        self._dict[ARGS][TOKEN] = token

####################

    def make_response(self, src_id):
        self._dict[TYPE] = RESPONSE
        self._dict[RESPONSE] = {ID: str(src_id)}
        
    def ping_response(self):
        pass

    def find_node_response(self, nodes):
        self._dict[RESPONSE][NODES] = mt.compact_nodes(nodes)

    def get_peers_response(self, token, nodes, peers):
        assert nodes or peers
        if token:
            self._dict[RESPONSE][TOKEN] = token
        if nodes:
            self._dict[RESPONSE][NODES] = mt.compact_nodes(nodes)
        if peers:
            self._dict[RESPONSE][VALUES] = mt.compact_peers(peers)

    def announce_peer_response(self):
        pass

###################################

    def outgoing_error(self, error):
        self._dict[TYPE] = ERROR
        self._dict[ERROR] = error

############################################

class IncomingMsg(object):
    """
    Create an object by decoding the given Datagram object. Raise 'MsgError'
    whenever the decoder fails to decode the datagram's data (e.g., invalid
    bencode).

    ?TODO: List attributes.
    """
    def __init__(self, private_dht_name, datagram):
        self.private_dht_name = private_dht_name
        bencoded_msg = datagram.data
        src_addr = datagram.addr
        self.src_addr = src_addr
        # COMMON
        self.tid = None
        self.type = None
        self.version = None
        self.ns_node = None # never used
        self.src_id = None
        self.src_node = None
        # QUERY
        self.query = None
        self.target = None # find_node
        self.info_hash = None # announce_peer
        self.bt_port = None # announce_peer
        self.token = None # announce_peer
        # RESPONSE
        self.nodes = None
        self.nodes2 = None
        self.all_nodes = None
        self.token = None
        self.peers = None
        # ERROR
        self.error = None
        try:
            # bencode.decode may raise bencode.DecodeError
            self._msg_dict = bencode.decode(bencoded_msg)
            self._sanitize_common()
            if self.type == QUERY:
                self._sanitize_query()
            elif self.type == RESPONSE:
                self._sanitize_response()
            elif self.type == ERROR:
                self._sanitize_error()
            else:
                raise MsgError, 'Unknown TYPE value'
        except (MsgError):
            raise
        except:
            logger.warning(
                'This bencoded message is broken:\n%s' % repr(bencoded_msg))
            raise MsgError, 'Invalid message'

    def __repr__(self):
        return repr(self._msg_dict)

    #
    # Sanitize functions
    #
    
    def _get_value(self, k, kk=None, optional=False):
        try:
            v = self._msg_dict[k]
            if kk:
                v = v[kk]
            return v
        except (KeyError):
            if optional:
                return None
            else:
                raise MsgError, 'Non-optional key (%s:%s) not found' % (k, kk)
        except (TypeError):
            raise MsgError, 'Probably k (%r) is not a dictionary' % (k)
    
    def _get_str(self, k, kk=None, optional=False):
        v = self._get_value(k, kk, optional)
        if v is None:
            return None
        if not isinstance(v, str):
            raise MsgError, 'Value (%s:%s,%s) must be a string' % (k, kk, v)
        return v

    def _get_id(self, k, kk=None):
        v = self._get_str(k, kk)
        try:
            return Id(v)
        except (IdError):
            raise MsgError, 'Value (%s:%s,%s) must be a valid Id' % (k, kk, v)

    def _get_int(self, k, kk=None):
        v = self._get_value(k, kk)
        try:
            return int(v)
        except (TypeError, ValueError):
            raise MsgError, 'Value (%s:%s,%s) must be an int' % (k, kk, v)
    
    def _sanitize_common(self):
        # Make sure the decoded data is a dict and has a TID key
        try:
            self.tid = self._msg_dict[TID]
        except (TypeError):
            raise MsgError, 'decoded data is not a dictionary'
        except (KeyError): 
            raise MsgError, 'key TID not found'
        # Sanitize TID
        if not (isinstance(self.tid, str) and self.tid):
            raise MsgError, 'TID must be a non-empty binary string'

        # Sanitize TYPE
        try:
            self.type = self._msg_dict[TYPE]
        except (KeyError):
            raise MsgError, 'key TYPE not found'
        # private dht name
        if self.private_dht_name:
            try:
                if self._msg_dict['d'] != self.private_dht_name:
                    raise MsgError, 'invalid private DHT name %r!=%r' % (
                        self._msg_dict['d'], self.private_dht_name)
            except (KeyError, TypeError):
                raise MsgError, 'invalid private DHT name'
        # version (optional)
        self.version = self._get_str(VERSION, optional=True)
        self.ns_node = self.version \
            and self.version.startswith('NS')
    
    def _sanitize_query(self):
        # src_id
        self.src_id = self._get_id(ARGS, ID)
        self.src_node = Node(self.src_addr, self.src_id, self.version)
        # query
        self.query = self._get_str(QUERY)
        if self.query in [GET_PEERS, ANNOUNCE_PEER]:
            # info_hash
            self.info_hash = self._get_id(ARGS, INFO_HASH)
            if self.query == ANNOUNCE_PEER:
                self.bt_port = self._get_int(ARGS, PORT)
                if not MIN_BT_PORT <= self.bt_port <= MAX_BT_PORT:
                    raise MsgError, 'announcing to %d. Out of range' % (
                        self.bt_port)
                self.token = self._get_str(ARGS, TOKEN)
        elif self.query == FIND_NODE:
            # target
            self.target = self._get_id(ARGS, TARGET)
        return
        
    def _sanitize_response(self):
        # src_id
        self.src_id = self._get_id(RESPONSE, ID)
        self.src_node = Node(self.src_addr, self.src_id, self.version)
        # all nodes
        self.all_nodes = []
        # nodes
        c_nodes = self._get_str(RESPONSE, NODES, optional=True)
        if c_nodes:
            self.nodes = mt.uncompact_nodes(c_nodes)
            self.all_nodes = self.nodes
        # nodes2
        try:
            c_nodes2 = self._msg_dict[RESPONSE][NODES2]
        except (KeyError):
            self.nodes2 = None
        else:
            self.nodes2 = mt.uncompact_nodes2(c_nodes2)
            for n in self.nodes2:
                if n not in self.all_nodes:
                    self.all_nodes.append(n)
        # token
        self.token = self._get_str(RESPONSE, TOKEN, optional=True)
        # peers
        self.peers = None
        c_peers = self._get_value(RESPONSE, PEERS, optional=True)
        if c_peers:
            self.peers = mt.uncompact_peers(c_peers)

    def _sanitize_error(self):
        self.src_id = None
        self.src_node = Node(self.src_addr)
        try:
            self.error = [int(self._msg_dict[ERROR][0]),
                          str(self._msg_dict[ERROR][1])]
        except:
            raise MsgError, 'Invalid error message'


class Datagram(object):

    def __init__(self, data, addr):
        self.data = data
        self.addr = addr

    def __eq__(self, other):
        return (self.data == other.data and 
                self.addr == other.addr)
