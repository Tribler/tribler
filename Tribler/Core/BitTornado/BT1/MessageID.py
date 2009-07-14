# Written by Jie Yang, Arno Bakker
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
#option_pattern = chr(0)*8
option_pattern = '\x00\x00\x00\x00\x00\x30\x00\x00'
disabled_overlay_option_pattern = '\x00\x00\x00\x00\x00\x20\x00\x00'


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


## IDs 255 and 254 are reserved. Tribler extensions number downwards

## PermID /Overlay Swarm Extension
# ctxt
CHALLENGE = chr(253)
# rdata1
RESPONSE1 = chr(252)
# rdata2
RESPONSE2 = chr(251)

PermIDMessages = [CHALLENGE, RESPONSE1, RESPONSE2]

## Merkle Hash Extension
# Merkle: PIECE message with hashes
HASHPIECE = chr(250)

## Buddycast Extension
"""
{'preferences':[[infohash]],
 #'permid': my permid,     # not used since 3.3.2
 'connectable': self connectability, # used since version > 3.5
 'name': my name,
 'ip':current ip,
 'port':current listening port,
 'taste_buddies':[{'preferences':[[infohash]],
                   'permid':Permanent ID,
                   'ip':the last known IP,
                   'port':the last known listen port,
                   'age':the age of this preference list in integer seconds
                  }],
 'random_peers':[{'permid':Permanent ID,
                  'ip':the last known IP,
                  'port':the last known listen port,
                  'age':the age of this preference list in integer seconds
                 }]
 'npeers': Number of peers known to peer
 'nfiles': Number of files known to peer
 'ndls': Number of downloads by peer
}
"""      
# payload is beencoded dict
BUDDYCAST = chr(249)
# empty payload
KEEP_ALIVE = chr(240)
# Bartercast, payload is bencoded dict
BARTERCAST = chr(236)

VOTECAST = chr(226)
MODERATIONCAST_HAVE = chr(227)
MODERATIONCAST_REQUEST = chr(228)
MODERATIONCAST_REPLY = chr(229)

#BuddyCastMessages = [BARTERCAST, BUDDYCAST, KEEP_ALIVE]
BuddyCastMessages = [MODERATIONCAST_HAVE, MODERATIONCAST_REQUEST, MODERATIONCAST_REPLY, VOTECAST, BARTERCAST, BUDDYCAST, KEEP_ALIVE]

# bencoded torrent_hash (Arno,2007-08-14: shouldn't be bencoded, but is)
GET_METADATA = chr(248)
# {'torrent_hash', 'metadata', ... }
METADATA = chr(247)

MetadataMessages = [GET_METADATA, METADATA]

# 2fastbt_
## Cooperative Download Extension
# torrent_hash
DOWNLOAD_HELP = chr(246)
# torrent_hash
STOP_DOWNLOAD_HELP = chr(245)

# For connectability test
DIALBACK_REQUEST = chr(244)
DIALBACK_REPLY = chr(243)

DialbackMessages = [DIALBACK_REQUEST,DIALBACK_REPLY]

# torrent_hash + 1-byte all_or_nothing + bencode([piece num,...])
RESERVE_PIECES = chr(242)
# torrent_hash + bencode([piece num,...])
PIECES_RESERVED = chr(241)

HelpCoordinatorMessages = [DOWNLOAD_HELP,STOP_DOWNLOAD_HELP,PIECES_RESERVED]
HelpHelperMessages = [RESERVE_PIECES]
# _2fastbt

# Note: SecureOverlay's KEEP_ALIVE is 240
## Social-Network feature 
SOCIAL_OVERLAP = chr(239)

SocialNetworkMessages = [SOCIAL_OVERLAP]

# Remote query extension
QUERY = chr(238)
QUERY_REPLY = chr(237)

RemoteQueryMessages = [QUERY,QUERY_REPLY]

# g2g info (uplink statistics, etc)
G2G_PIECE_XFER = chr(235)

VoDMessages = [G2G_PIECE_XFER]

# Friendship messages
FRIENDSHIP = chr(234)

FriendshipMessages = [FRIENDSHIP]

####### FREE ID = 233

# Generic Crawler messages
CRAWLER_REQUEST = chr(232)
CRAWLER_REPLY = chr(231)

CrawlerMessages = [CRAWLER_REQUEST, CRAWLER_REPLY]

# All overlay-swarm messages
OverlaySwarmMessages = PermIDMessages + BuddyCastMessages + MetadataMessages + HelpCoordinatorMessages + HelpHelperMessages + SocialNetworkMessages + RemoteQueryMessages + CrawlerMessages

# Crawler sub-messages
CRAWLER_DATABASE_QUERY = chr(1)
CRAWLER_SEEDINGSTATS_QUERY = chr(2)
CRAWLER_NATCHECK = chr(3)
CRAWLER_FRIENDSHIP_STATS = chr(4)
CRAWLER_NATTRAVERSAL = chr(5)
CRAWLER_VIDEOPLAYBACK_INFO_QUERY = chr(6)
CRAWLER_VIDEOPLAYBACK_EVENT_QUERY = chr(7)

message_map = {
    CHOKE:"CHOKE",
    UNCHOKE:"UNCHOKE",
    INTERESTED:"INTEREST",
    NOT_INTERESTED:"NOT_INTEREST",
    HAVE:"HAVE",
    BITFIELD:"BITFIELD",
    REQUEST:"REQUEST",
    CANCEL:"CANCEL",
    PIECE:"PIECE",
    PORT:"PORT",
    EXTEND:"EXTEND",
    
    CHALLENGE:"CHALLENGE",
    RESPONSE1:"RESPONSE1",
    RESPONSE2:"RESPONSE2",
    HASHPIECE:"HASHPIECE",
    BUDDYCAST:"BUDDYCAST",
    GET_METADATA:"GET_METADATA",
    METADATA:"METADATA",
    DOWNLOAD_HELP:"DOWNLOAD_HELP",
    STOP_DOWNLOAD_HELP:"STOP_DOWNLOAD_HELP",
    PIECES_RESERVED:"PIECES_RESERVED",
    RESERVE_PIECES:"RESERVE_PIECES",
    DIALBACK_REQUEST:"DIALBACK_REQUEST",
    DIALBACK_REPLY:"DIALBACK_REPLY",
    KEEP_ALIVE:"KEEP_ALIVE",
    SOCIAL_OVERLAP:"SOCIAL_OVERLAP",
    QUERY:"QUERY",
    QUERY_REPLY:"QUERY_REPLY",
    MODERATIONCAST_HAVE:"MODERATIONCAST_HAVE",
    MODERATIONCAST_REQUEST:"MODERATIONCAST_REQUEST",
    MODERATIONCAST_REPLY:"MODERATIONCAST_REPLY",
    VOTECAST:"VOTECAST",
    BARTERCAST:"BARTERCAST",
    G2G_PIECE_XFER: "G2G_PIECE_XFER",
    FRIENDSHIP:"FRIENDSHIP",

    CRAWLER_REQUEST:"CRAWLER_REQUEST",
    CRAWLER_REQUEST+CRAWLER_DATABASE_QUERY:"CRAWLER_DATABASE_QUERY_REQUEST",
    CRAWLER_REQUEST+CRAWLER_SEEDINGSTATS_QUERY:"CRAWLER_SEEDINGSTATS_QUERY_REQUEST",
    CRAWLER_REQUEST+CRAWLER_NATCHECK:"CRAWLER_NATCHECK_QUERY_REQUEST",
    CRAWLER_REQUEST+CRAWLER_NATTRAVERSAL:"CRAWLER_NATTRAVERSAL_QUERY_REQUEST",
    CRAWLER_REQUEST+CRAWLER_FRIENDSHIP_STATS:"CRAWLER_FRIENDSHIP_STATS_REQUEST",
    CRAWLER_REQUEST+CRAWLER_VIDEOPLAYBACK_INFO_QUERY:"CRAWLER_VIDEOPLAYBACK_INFO_QUERY_REQUEST",
    CRAWLER_REQUEST+CRAWLER_VIDEOPLAYBACK_EVENT_QUERY:"CRAWLER_VIDEOPLAYBACK_EVENT_QUERY_REQUEST",

    CRAWLER_REPLY:"CRAWLER_REPLY",
    CRAWLER_REPLY+CRAWLER_DATABASE_QUERY:"CRAWLER_DATABASE_QUERY_REPLY",
    CRAWLER_REPLY+CRAWLER_SEEDINGSTATS_QUERY:"CRAWLER_SEEDINGSTATS_QUERY_REPLY",
    CRAWLER_REPLY+CRAWLER_NATCHECK:"CRAWLER_NATCHECK_QUERY_REPLY",
    CRAWLER_REPLY+CRAWLER_NATTRAVERSAL:"CRAWLER_NATTRAVERSAL_QUERY_REPLY",
    CRAWLER_REPLY+CRAWLER_FRIENDSHIP_STATS:"CRAWLER_FRIENDSHIP_STATS",
    CRAWLER_REPLY+CRAWLER_FRIENDSHIP_STATS:"CRAWLER_FRIENDSHIP_STATS_REPLY",
    CRAWLER_REPLY+CRAWLER_VIDEOPLAYBACK_INFO_QUERY:"CRAWLER_VIDEOPLAYBACK_INFO_QUERY_REPLY",
    CRAWLER_REPLY+CRAWLER_VIDEOPLAYBACK_EVENT_QUERY:"CRAWLER_VIDEOPLAYBACK_EVENT_QUERY_REPLY"
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
