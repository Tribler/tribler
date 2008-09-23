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
# Left+42 bit = Tribler Simple Merkle Hashes extension
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
# payload is beencoded dict
BUDDYCAST = chr(249)
# empty payload
KEEP_ALIVE = chr(240)
# Bartercast, payload is bencoded dict
BARTERCAST = chr(236)

BuddyCastMessages = [BARTERCAST, BUDDYCAST, KEEP_ALIVE]

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

# Do NAT check and report
DO_NAT_CHECK = chr(234)
NAT_CHECK_REPLY = chr(233)

NatCheckMessages = [DO_NAT_CHECK, NAT_CHECK_REPLY]

OverlaySwarmMessages = PermIDMessages + BuddyCastMessages + MetadataMessages + HelpCoordinatorMessages + HelpHelperMessages + SocialNetworkMessages + RemoteQueryMessages

# g2g info (uplink statistics, etc)
G2G_PIECE_XFER = chr(235)

VoDMessages = [G2G_PIECE_XFER]

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
    BARTERCAST:"BARTERCAST",
    DO_NAT_CHECK:"DO_NAT_CHECK",
    NAT_CHECK_REPLY:"NAT_CHECK_REPLY",
    G2G_PIECE_XFER: "G2G_PIECE_XFER"
}


def getMessageName(t):
    if t in message_map:
        return message_map[t]
    else:
        return "Unknown_MessageID_"+str(ord(t))
        
