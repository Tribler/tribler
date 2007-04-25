# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information

""" All message IDs in BitTorrent Protocol and our extensions 
 
    Arno: please don't define stuff until the spec is ready
"""

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

# uTorrent and Bram's BitTorrent now support an extended protocol
EXTEND = chr(20)

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
}
"""                   
BUDDYCAST = chr(249)
KEEP_ALIVE = chr(240)

BuddyCastMessages = [BUDDYCAST, KEEP_ALIVE]

# torrent_hash
GET_METADATA = chr(248)
# {'torrent_hash', 'metadata', 'md5sum'}    # index starts from 1 and ends by total.
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


## Social-Network feature 
SOCIAL_OVERLAP = chr(239)

SocialNetworkMessages = [SOCIAL_OVERLAP]

OverlaySwarmMessages= PermIDMessages + BuddyCastMessages + MetadataMessages + HelpCoordinatorMessages + HelpHelperMessages + SocialNetworkMessages

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
    SOCIAL_OVERLAP:"SOCIAL_OVERLAP"
}


def getMessageName(t):
    if t in message_map:
        return message_map[t]
    else:
        return "Unknown_MessageID_"+str(ord(t))
        
