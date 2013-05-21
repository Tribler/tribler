# Written by Jie Yang, Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information
#
# All message IDs in BitTorrent Protocol and our extensions
#
#    Arno: please don't define stuff until the spec is ready
#

protocol_name = 'BitTorrent protocol'
# Enable Tribler extensions:
# Left-most bit = Azureus Enhanced Messaging Protocol (AEMP)
# Left+42 bit = Tribler Simple Merkle Hashes extension v0. Outdated, but still sent for compatibility.
# Left+43 bit = Tribler Overlay swarm extension
#               AND uTorrent extended protocol, conflicting. See EXTEND message
# Right-most bit = BitTorrent DHT extension
# option_pattern = chr(0)*8
option_pattern = '\x00\x00\x00\x00\x00\x30\x00\x00'


CHOKE = chr(0)
UNCHOKE = chr(1)
INTERESTED = chr(2)
NOT_INTERESTED = chr(3)

# index
HAVE = chr(4)
# index, bitfield
BITFIELD = chr(5)
# index, begin, length
REQUEST = chr(6)
# index, begin, piece
PIECE = chr(7)
# index, begin, piece
CANCEL = chr(8)
# 2-byte port
PORT = chr(9)

# uTorrent and Bram's BitTorrent now support an extended protocol
EXTEND = chr(20)


#
# Tribler specific message IDs
#

# IDs 255 and 254 are reserved. Tribler extensions number downwards

# PermID /Overlay Swarm Extension
# ctxt
CHALLENGE = chr(253)
# rdata1
RESPONSE1 = chr(252)
# rdata2
RESPONSE2 = chr(251)

# Merkle Hash Extension
# Merkle: PIECE message with hashes
HASHPIECE = chr(250)

# Buddycast Extension
# payload is beencoded dict
BUDDYCAST = chr(249)

# bencoded torrent_hash (Arno,2007-08-14: shouldn't be bencoded, but is)
GET_METADATA = chr(248)
# {'torrent_hash', 'metadata', ... }
METADATA = chr(247)

# ProxyService extension, reused from Cooperative Download (2fast)
# For connectability test
DIALBACK_REQUEST = chr(244)
DIALBACK_REPLY = chr(243)

# Doe sent messages
RELAY_REQUEST = chr(246)  # payload = infohash
STOP_RELAYING = chr(245)  # payload = infohash
DOWNLOAD_PIECE = chr(242)  # payload = infohash + bencode(piece_number)
CANCEL_DOWNLOADING_PIECE = chr(241)  # payload = infohash + bencode(piece_number)
UPLOAD_PIECE = chr(219)  # payload = infohash + bencode(piece_number) + bencode(piece_data)
CANCEL_UPLOADING_PIECE = chr(218)  # payload = infohash + bencode(piece_number)

# Proxy sent messages
RELAY_ACCEPTED = chr(224)  # payload = infohash
RELAY_DROPPED = chr(223)  # payload = infohash
DROPPED_PIECE = chr(222)  # payload = infohash + bencode(piece_number)
PROXY_HAVE = chr(221)  # payload = infohash + bencode(haves_bitstring)
PROXY_UNHAVE = chr(220)  # payload = infohash + bencode(haves_bitstring)
PIECE_DATA = chr(217)  # payload = infohash + bencode(piece_number) + bencode(piece_data)

# SecureOverlay empty payload
KEEP_ALIVE = chr(240)

# Social-Network feature
SOCIAL_OVERLAP = chr(239)

# Remote query extension
QUERY = chr(238)
QUERY_REPLY = chr(237)

# Bartercast, payload is bencoded dict
BARTERCAST = chr(236)

# g2g info (uplink statistics, etc)
G2G_PIECE_XFER = chr(235)

# Friendship messages
FRIENDSHIP = chr(234)

# Generic Crawler messages
CRAWLER_REQUEST = chr(232)
CRAWLER_REPLY = chr(231)

VOTECAST = chr(226)
CHANNELCAST = chr(225)

GET_SUBS = chr(230)
SUBS = chr(229)

# FREE ID = 227/228 + < 217


#
# EXTEND_MSG_CS sub-messages
#
# Closed swarms
# CS  : removed, unused. Using CS_CHALLENGE_A message ID in extend handshake
CS_CHALLENGE_A = chr(227)
CS_CHALLENGE_B = chr(228)
CS_POA_EXCHANGE_A = chr(229)
CS_POA_EXCHANGE_B = chr(230)

#
# Crawler sub-messages
#
CRAWLER_DATABASE_QUERY = chr(1)
CRAWLER_SEEDINGSTATS_QUERY = chr(2)
CRAWLER_NATCHECK = chr(3)
CRAWLER_FRIENDSHIP_STATS = chr(4)
CRAWLER_NATTRAVERSAL = chr(5)
CRAWLER_VIDEOPLAYBACK_INFO_QUERY = chr(6)
CRAWLER_VIDEOPLAYBACK_EVENT_QUERY = chr(7)
CRAWLER_REPEX_QUERY = chr(8)  # RePEX: query a peer's SwarmCache history
CRAWLER_PUNCTURE_QUERY = chr(9)
CRAWLER_CHANNEL_QUERY = chr(10)
CRAWLER_USEREVENTLOG_QUERY = chr(11)


#
# Summaries
#

PermIDMessages = [CHALLENGE, RESPONSE1, RESPONSE2]
BuddyCastMessages = [CHANNELCAST, VOTECAST, BARTERCAST, BUDDYCAST, KEEP_ALIVE]
MetadataMessages = [GET_METADATA, METADATA]
DialbackMessages = [DIALBACK_REQUEST, DIALBACK_REPLY]
DoeMessages = [RELAY_REQUEST, STOP_RELAYING, DOWNLOAD_PIECE, CANCEL_DOWNLOADING_PIECE, UPLOAD_PIECE, CANCEL_UPLOADING_PIECE]
ProxyMessages = [RELAY_ACCEPTED, RELAY_DROPPED, DROPPED_PIECE, PROXY_HAVE, PROXY_UNHAVE, PIECE_DATA]
SocialNetworkMessages = [SOCIAL_OVERLAP]
RemoteQueryMessages = [QUERY, QUERY_REPLY]
VoDMessages = [G2G_PIECE_XFER]
FriendshipMessages = [FRIENDSHIP]
CrawlerMessages = [CRAWLER_REQUEST, CRAWLER_REPLY]
SubtitleMessages = [GET_SUBS, SUBS]

# All overlay-swarm messages
OverlaySwarmMessages = PermIDMessages + BuddyCastMessages + MetadataMessages + DoeMessages + ProxyMessages + SocialNetworkMessages + RemoteQueryMessages + CrawlerMessages


#
# Printing
#

message_map = {
    CHOKE: "CHOKE",
    UNCHOKE: "UNCHOKE",
    INTERESTED: "INTEREST",
    NOT_INTERESTED: "NOT_INTEREST",
    HAVE: "HAVE",
    BITFIELD: "BITFIELD",
    REQUEST: "REQUEST",
    CANCEL: "CANCEL",
    PIECE: "PIECE",
    PORT: "PORT",
    EXTEND: "EXTEND",

    CHALLENGE: "CHALLENGE",
    RESPONSE1: "RESPONSE1",
    RESPONSE2: "RESPONSE2",
    HASHPIECE: "HASHPIECE",
    BUDDYCAST: "BUDDYCAST",
    GET_METADATA: "GET_METADATA",
    METADATA: "METADATA",

    RELAY_REQUEST: "RELAY_REQUEST",
    STOP_RELAYING: "STOP_RELAYING",
    DOWNLOAD_PIECE: "DOWNLOAD_PIECE",
    CANCEL_DOWNLOADING_PIECE: "CANCEL_DOWNLOADING_PIECE",
    UPLOAD_PIECE: "UPLOAD_PIECE",
    CANCEL_UPLOADING_PIECE: "CANCEL_UPLOADING_PIECE",
    RELAY_ACCEPTED: "RELAY_ACCEPTED",
    RELAY_DROPPED: "RELAY_DROPPED",
    DROPPED_PIECE: "DROPPED_PIECE",
    PROXY_HAVE: "PROXY_HAVE",
    PROXY_UNHAVE: "PROXY_UNHAVE",
    PIECE_DATA: "PIECE_DATA",
    DIALBACK_REQUEST: "DIALBACK_REQUEST",
    DIALBACK_REPLY: "DIALBACK_REPLY",

    KEEP_ALIVE: "KEEP_ALIVE",
    SOCIAL_OVERLAP: "SOCIAL_OVERLAP",
    QUERY: "QUERY",
    QUERY_REPLY: "QUERY_REPLY",
    VOTECAST: "VOTECAST",
    BARTERCAST: "BARTERCAST",
    G2G_PIECE_XFER: "G2G_PIECE_XFER",
    FRIENDSHIP: "FRIENDSHIP",
    VOTECAST: "VOTECAST",
    CHANNELCAST: "CHANNELCAST",

    CRAWLER_REQUEST: "CRAWLER_REQUEST",
    CRAWLER_REQUEST + CRAWLER_DATABASE_QUERY: "CRAWLER_DATABASE_QUERY_REQUEST",
    CRAWLER_REQUEST + CRAWLER_SEEDINGSTATS_QUERY: "CRAWLER_SEEDINGSTATS_QUERY_REQUEST",
    CRAWLER_REQUEST + CRAWLER_NATCHECK: "CRAWLER_NATCHECK_QUERY_REQUEST",
    CRAWLER_REQUEST + CRAWLER_NATTRAVERSAL: "CRAWLER_NATTRAVERSAL_QUERY_REQUEST",
    CRAWLER_REQUEST + CRAWLER_FRIENDSHIP_STATS: "CRAWLER_FRIENDSHIP_STATS_REQUEST",
    CRAWLER_REQUEST + CRAWLER_VIDEOPLAYBACK_INFO_QUERY: "CRAWLER_VIDEOPLAYBACK_INFO_QUERY_REQUEST",
    CRAWLER_REQUEST + CRAWLER_VIDEOPLAYBACK_EVENT_QUERY: "CRAWLER_VIDEOPLAYBACK_EVENT_QUERY_REQUEST",
    CRAWLER_REQUEST + CRAWLER_REPEX_QUERY: "CRAWLER_REPEX_QUERY_REQUEST",  # RePEX: query a peer's SwarmCache history
    CRAWLER_REQUEST + CRAWLER_PUNCTURE_QUERY: "CRAWLER_PUNCTURE_QUERY_REQUEST",
    CRAWLER_REQUEST + CRAWLER_CHANNEL_QUERY: "CRAWLER_CHANNEL_QUERY_REQUEST",

    CRAWLER_REPLY: "CRAWLER_REPLY",
    CRAWLER_REPLY + CRAWLER_DATABASE_QUERY: "CRAWLER_DATABASE_QUERY_REPLY",
    CRAWLER_REPLY + CRAWLER_SEEDINGSTATS_QUERY: "CRAWLER_SEEDINGSTATS_QUERY_REPLY",
    CRAWLER_REPLY + CRAWLER_NATCHECK: "CRAWLER_NATCHECK_QUERY_REPLY",
    CRAWLER_REPLY + CRAWLER_NATTRAVERSAL: "CRAWLER_NATTRAVERSAL_QUERY_REPLY",
    CRAWLER_REPLY + CRAWLER_FRIENDSHIP_STATS: "CRAWLER_FRIENDSHIP_STATS",
    CRAWLER_REPLY + CRAWLER_FRIENDSHIP_STATS: "CRAWLER_FRIENDSHIP_STATS_REPLY",
    CRAWLER_REPLY + CRAWLER_VIDEOPLAYBACK_INFO_QUERY: "CRAWLER_VIDEOPLAYBACK_INFO_QUERY_REPLY",
    CRAWLER_REPLY + CRAWLER_VIDEOPLAYBACK_EVENT_QUERY: "CRAWLER_VIDEOPLAYBACK_EVENT_QUERY_REPLY",
    CRAWLER_REPLY + CRAWLER_REPEX_QUERY: "CRAWLER_REPEX_QUERY_REPLY",  # RePEX: query a peer's SwarmCache history
    CRAWLER_REPLY + CRAWLER_PUNCTURE_QUERY: "CRAWLER_PUNCTURE_QUERY_REPLY",
    CRAWLER_REPLY + CRAWLER_CHANNEL_QUERY: "CRAWLER_CHANNEL_QUERY_REPLY"
}


def getMessageName(s):
    """
    Return the message name for message id s. This may be either a one
    or a two byte sting
    """
    if s in message_map:
        return message_map[s]
    else:
        return "Unknown_MessageID_" + "_".join([str(ord(c)) for c in s])
