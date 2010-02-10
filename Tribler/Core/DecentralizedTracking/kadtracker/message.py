# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""
This module provides message classes.

Outgoing messages are built from a few parameters. They are immutable and can be
reused (TID is not part of the message).

Incoming messages are built from bencoded data. They are immutable and must be
sanitized before attempting to use message's attributes.

"""

import sys

import logging

import bencode
from identifier import Id, ID_SIZE_BYTES, IdError
from node import Node


logger = logging.getLogger('dht')


NEXTSHARE = 'NS\0\0\0'

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
VALUES = 'values' # List of peers in compact format (get_peers)

# Valid values for ERROR
GENERIC_E = [201, 'Generic Error']
SERVER_E = [202, 'Server Error']
PROTOCOL_E = [203, 'Protocol Error']
UNKNOWN_E = [201, 'Method Unknown']

BLANK = 'BLANK'
BENCODED_BLANK = bencode.encode(BLANK)

# Valid values for TID and VERSION
#  binary string



IP4_SIZE = 4 #bytes
IP6_SIZE = 16 #bytes
ADDR4_SIZE = IP4_SIZE + 2 # IPv4 address plus port
ADDR6_SIZE = IP6_SIZE + 2 # IPv6 address plus port
C_NODE_SIZE = ID_SIZE_BYTES + ADDR4_SIZE
C_NODE2_SIZE = ID_SIZE_BYTES + ADDR6_SIZE

IP6_PADDING = '\0' * 10 + '\xff\xff'


class AddrError(Exception):
    pass

#class IP6Addr(AddrError):
#    pass
# TODO2: deal with IPv6 address (we ignore them now)

def bin_to_int(bin_str):
    return ord(bin_str[0]) * 256 + ord(bin_str[1])

def int_to_bin(i):
    return chr(i/256) + chr(i%256)

def bin_to_ip(bin_str):
    if len(bin_str) == IP4_SIZE:
        return '.'.join([str(ord(b)) for b in bin_str])
    if len(bin_str) != IP6_SIZE:
        raise MsgError, 'compact_ip: invalid size (%d)' % len(bin_str)
    if not bin_str.startswith(IP6_PADDING):
        raise AddrError, 'IPv4 and v6 should not be mixed!'
    c_ip = bin_str[len(IP6_PADDING):]
    return '.'.join([`ord(byte)` for byte in c_ip])

def ip_to_bin(ip_str):
    return ''.join([chr(int(b)) for b in ip_str.split('.')])

def compact_addr(addr):
    return ''.join((ip_to_bin(addr[0]), int_to_bin(addr[1])))

def uncompact_addr(c_addr):
    if c_addr[-2:] == '\0\0':
        logger.warning('c_addr: %r > port is ZERO' % c_addr)
        raise AddrError
    return (bin_to_ip(c_addr[:-2]), bin_to_int(c_addr[-2:]))

def _compact_peers(peers):
    return [compact_addr(peer) for peer in peers]

def _uncompact_peers(c_peers):
    peers = []
    for c_peer in c_peers:
        try:
            peers.append(uncompact_addr(c_peer))
        except (AddrError):
            pass
    return peers

def _compact_nodes(nodes):
    return ''.join([node.id.bin_id + compact_addr(node.addr) \
                    for node in nodes])
    
def _uncompact_nodes(c_nodes):
    if len(c_nodes) % C_NODE_SIZE != 0: 
        raise MsgError, 'invalid size (%d) %s' % (len(c_nodes),
                                                  c_nodes)
    nodes = []
    for begin in xrange(0, len(c_nodes), C_NODE_SIZE):
        node_id = Id(c_nodes[begin:begin + ID_SIZE_BYTES])
        try:
            node_addr = uncompact_addr(
                c_nodes[begin+ID_SIZE_BYTES:begin+C_NODE_SIZE])
        except AddrError:
            pass
        else:
            node = Node(node_addr, node_id)
            nodes.append(node)
    return nodes

def _compact_nodes2(nodes):
    return [node.id.bin_id + IP6_PADDING + compact_addr(node.addr) \
            for node in nodes]
    
def _uncompact_nodes2(c_nodes):
    nodes = []
    for c_node in c_nodes:
        node_id = Id(c_node[:ID_SIZE_BYTES])
        try:
            node_addr = uncompact_addr(c_node[ID_SIZE_BYTES:]) 
        except (AddrError):
            logger.warning('IPv6 addr in nodes2: %s' % c_node)
        else:
            node = Node(node_addr, node_id)
            nodes.append(node)
    return nodes
        

def matching_tid(query_tid, response_tid):
    return query_tid[0] == response_tid[0]



MSG_DICTS = {}

MSG_DICTS['og_ping_q'] = {VERSION: NEXTSHARE,
                            TID: BLANK,
                            TYPE: QUERY,
                            QUERY: PING,
                            ARGS: {ID: BLANK}
                            }
MSG_DICTS['og_find_node_q'] = {VERSION: NEXTSHARE,
                                 TID: BLANK,
                                 TYPE: QUERY,
                                 QUERY: FIND_NODE,
                                 ARGS: {ID: BLANK, TARGET: BLANK}
                                 }
MSG_DICTS['og_get_peers_q'] = {VERSION: NEXTSHARE,
                                  TID: BLANK,
                                  TYPE: QUERY,
                                  QUERY: GET_PEERS,
                                  ARGS: {ID: BLANK, INFO_HASH: BLANK}
                                  }
MSG_DICTS['og_announce_peer_q'] = {VERSION: NEXTSHARE,
                                   TID: BLANK,
                                   TYPE: QUERY,
                                   QUERY: ANNOUNCE_PEER,
                                   ARGS: {ID: BLANK, INFO_HASH: BLANK,
                                          PORT: BLANK, TOKEN: BLANK}
                                   }

MSG_DICTS['og_ping_r'] = {VERSION: NEXTSHARE,
                               TID: BLANK,
                               TYPE: RESPONSE,
                               RESPONSE: {ID: BLANK}
                               }
MSG_DICTS['og_find_node_r'] = {VERSION: NEXTSHARE,
                               TID: BLANK,
                               TYPE: RESPONSE,
                               RESPONSE: {ID: BLANK, NODES2: BLANK}
                                   }
MSG_DICTS['og_get_peers_r_nodes'] = {VERSION: NEXTSHARE,
                                      TID: BLANK,
                                     TYPE: RESPONSE,
                                     RESPONSE: {ID: BLANK, NODES2: BLANK,
                                                TOKEN: BLANK}
                                    }
MSG_DICTS['og_get_peers_r_values'] = {VERSION: NEXTSHARE,
                                      TID: BLANK,
                                     TYPE: RESPONSE,
                                     RESPONSE: {ID: BLANK, VALUES: BLANK,
                                                TOKEN: BLANK}
                                    }
MSG_DICTS['og_announce_peer_r'] = {VERSION: NEXTSHARE,
                                  TID: BLANK,
                                  TYPE: RESPONSE,
                                  RESPONSE: {ID: BLANK}
                                  }
MSG_DICTS['og_error'] = {VERSION: NEXTSHARE,
                         TID: BLANK,
                         TYPE: ERROR,
                         ERROR: BLANK
                         }
BENCODED_MSG_TEMPLATES = {}
for msg_type, msg_dict in MSG_DICTS.iteritems():
    bencoded_msg = bencode.encode(msg_dict)
    BENCODED_MSG_TEMPLATES[msg_type] = bencoded_msg.split(BENCODED_BLANK)


class MsgError(Exception):
    """Raised anytime something goes wrong (specially when decoding/sanitizing).

    """


class OutgoingMsgBase(object):
    """Base class for outgoing messages. You shouldn't have instances of it.

    """
    
    def __str__(self):
        return str(self._bencoded_msg) + str(self._values)

    def __repr__(self):
        return str(self.__class__) + str(self)

    def encode(self, tid):
        self._values[-1] = tid
        num_blank_slots  = len(self._bencoded_msg) -1
        # Reserve space for prebencoded chunks and blank slots.
        splitted_msg = [None] * (len(self._bencoded_msg) + num_blank_slots)
        # Let's fill in every blank slot.
        for i in range(num_blank_slots):
            splitted_msg[2*i] = self._bencoded_msg[i] # prebencoded chunk
            splitted_msg[2*i+1] = bencode.encode(self._values[i]) # value
        splitted_msg[-1] = self._bencoded_msg[-1] # last prebencoded chunk
        return ''.join(splitted_msg) # put all bencode in a single string
      

class OutgoingPingQuery(OutgoingMsgBase):
    
    def __init__(self, sender_id):
        self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_ping_q']
        self._values = [sender_id.bin_id,
                        ''] #TID
        self.query = PING

        
class OutgoingFindNodeQuery(OutgoingMsgBase):

    def __init__(self, sender_id, target_id):
        self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_find_node_q']
        self._values = [sender_id.bin_id,
                        target_id.bin_id,
                        ''] #TID
        self.query = FIND_NODE


class OutgoingGetPeersQuery(OutgoingMsgBase):

    def __init__(self, sender_id, info_hash):
        self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_get_peers_q']
        self._values = [sender_id.bin_id,
                        info_hash.bin_id,
                        ''] #TID
        self.query = GET_PEERS


class OutgoingAnnouncePeerQuery(OutgoingMsgBase):
    
    def __init__(self, sender_id, info_hash, port, token):
        self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_announce_peer_q']
        self._values = [sender_id.bin_id,
                        info_hash.bin_id,
                        port,
                        token,
                        ''] #TID
        self.query = ANNOUNCE_PEER


class OutgoingPingResponse(OutgoingMsgBase):

    def __init__(self, sender_id):
        self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_ping_r']
        self._values = [sender_id.bin_id,
                        ''] #TID


class OutgoingFindNodeResponse(OutgoingMsgBase):

    def __init__(self, sender_id, nodes2=None, nodes=None):
        if nodes is not None:
            raise MsgError, 'not implemented'
        if nodes2 is not None:
            self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_find_node_r']
            self._values = [sender_id.bin_id,
                            _compact_nodes2(nodes2),
                            ''] #TID
        else:
            raise MsgError, 'must have nodes OR nodes2'
                          
class OutgoingGetPeersResponse(OutgoingMsgBase):

    def __init__(self, sender_id, token,
                 nodes2=None, peers=None):
        if peers:
            self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_get_peers_r_values']
            self._values = [sender_id.bin_id,
                            token,
                            _compact_peers(peers),
                            ''] #TID
            
        elif nodes2:
            self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_get_peers_r_nodes']
            self._values = [sender_id.bin_id,
                            _compact_nodes2(nodes2),
                            token,
                            ''] #TID
        else:
            raise MsgError, 'must have nodes OR peers'

class OutgoingAnnouncePeerResponse(OutgoingMsgBase):
    
    def __init__(self, sender_id):
        self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_announce_peer_r']
        self._values = [sender_id.bin_id,
                        ''] #TID

class OutgoingErrorMsg(OutgoingMsgBase):

    def __init__(self, error):
        self._bencoded_msg = BENCODED_MSG_TEMPLATES['og_error']
        self._values = [error,
                        ''] #TID
        return

    
class IncomingMsg(object):

    def __init__(self, bencoded_msg):
        try:
            self._msg_dict = bencode.decode(bencoded_msg)
        except (bencode.DecodeError):
            logger.exception('invalid bencode')
            raise MsgError, 'invalid bencode'
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

        if not self.type in (QUERY, RESPONSE, ERROR):
            raise MsgError, 'Unknown TYPE value'
        if self.type == QUERY:
            self._sanitize_query()
        elif self.type == ERROR:
            self._sanitize_error()
        return

    def __repr__(self):
        return repr(self._msg_dict)


    def _get_value(self, k, kk=None, optional=False):
        try:
            v = self._msg_dict[k]
            if kk:
                v = v[kk]
        except (KeyError):
            if optional:
                return None
            else:
                raise MsgError, 'Non-optional key (%s:%s) not found' % (k, kk)
        except (TypeError):
            raise MsgError, 'Probably k (%r) is not a dictionary' % (k)
        return v
    
    def _get_str(self, k, kk=None, optional=False):
        v = self._get_value(k, kk, optional)
        if v is None:
            return None
        if not isinstance(v, str):
            raise MsgError, 'Value (%s:%s,%s) must be a string' % (k, kk, v)
        return v

    def _get_id(self, k, kk=None):
        try:
            v = self._get_value(k, kk)
            v = Id(v)
        except (IdError):
            raise MsgError, 'Value (%s:%s,%s) must be a valid Id' % (k, kk, v)
        return v

    def _get_int(self, k, kk=None):
        v = self._get_value(k, kk)
        try:
            v= int(v)
        except (TypeError, ValueError):
            raise MsgError, 'Value (%s:%s,%s) must be an int' % (k, kk, v)
        return v
    
    def _sanitize_common(self):
        # version (optional)
        self.version = self._get_str(VERSION, optional=True)
        self.ns_node = self.version \
            and self.version.startswith(NEXTSHARE[:2])
    
    def _sanitize_query(self):
        self._sanitize_common()
        # sender_id
        self.sender_id = self._get_id(ARGS, ID)
        # query
        self.query = self._get_str(QUERY)
        if self.query in [GET_PEERS, ANNOUNCE_PEER]:
            # info_hash
            self.info_hash = self._get_id(ARGS, INFO_HASH)
            if self.query == ANNOUNCE_PEER:
                self.port = self._get_int(ARGS, PORT)
                self.token = self._get_str(ARGS, TOKEN)
        elif self.query == FIND_NODE:
            # target
            self.target = self._get_id(ARGS, TARGET)
        return
        
    def sanitize_response(self, query):
        self._sanitize_common()
        # sender_id
        self.sender_id = self._get_id(RESPONSE, ID)
        if query in [FIND_NODE, GET_PEERS]:
            # nodes
            nodes_found = False
            c_nodes = self._get_str(RESPONSE, NODES, optional=True)
            if c_nodes:
                self.nodes = _uncompact_nodes(c_nodes)
                nodes_found = True
            # nodes2
            try:
                self.nodes2 = _uncompact_nodes2(
                    self._msg_dict[RESPONSE][NODES2])
                if nodes_found:
                    logger.info('Both nodes and nodes2 found')
                nodes_found = True
            except (KeyError):
                pass
        if query == FIND_NODE:
            if not nodes_found:
                logger.warning('No nodes in find_node response')
                raise MsgError, 'No nodes in find_node response'
        elif query == GET_PEERS:
            # peers
            try:
                self.peers = _uncompact_peers(
                    self._msg_dict[RESPONSE][VALUES])
                if nodes_found:
                    logger.debug(
                        'Nodes and peers found in get_peers response')
            except (KeyError):
                if not nodes_found:
                    logger.warning(
                        'No nodes or peers found in get_peers response')
                    raise (MsgError,
                           'No nodes or peers found in get_peers response')
            # token
            self.token = self._get_str(RESPONSE, TOKEN)
            
    def _sanitize_error(self):
        self._sanitize_common()
        try:
            self.error = [int(self._msg_dict[ERROR][0]),
                          str(self._msg_dict[ERROR][1])]
        except (KeyError, IndexError, ValueError, TypeError):
            raise MsgError, 'Invalid error message'
        if self.error not in [GENERIC_E, SERVER_E, PROTOCOL_E, UNKNOWN_E]:
            logger.info('Unknown error: %s', self.error)
            
