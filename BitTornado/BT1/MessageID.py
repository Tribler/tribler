# Written by Jie Yang
# see LICENSE.txt for license information
""" All message IDs in BitTorrent Protocol and BT+ Protocol """

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

## PermID Extension
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

## Overlay Swarm Extension
"""
{'my_preferences':[[infohash]],
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
PREFERENCE_EXCHANGE = chr(249)

BuddyCastMessages = [PREFERENCE_EXCHANGE]

# torrent_hash
GET_METADATA = chr(248)
# {'torrent_hash', 'metadata', 'md5sum'}    # index starts from 1 and ends by total.
METADATA = chr(247)

MetadataMessages = [GET_METADATA, METADATA]

# 2fastbt_
# torrent_hash
DOWNLOAD_HELP = chr(246)
# torrent_hash
STOP_DOWNLOAD_HELP = chr(245)
# torrent_hash + 4-byte requestID + 1-byte all_or_nothing + bencode([piece num,...])
RESERVE_PIECES = chr(242)
# torrent_hash + + 4-byte requestID + bencode([piece num,...])
PIECES_RESERVED = chr(241)

HelpCoordinatorMessages = [DOWNLOAD_HELP,STOP_DOWNLOAD_HELP,PIECES_RESERVED]
HelpHelperMessages = [RESERVE_PIECES]
# _2fastbt

ONLINE_EXCHANGE = chr(244)
FRIENDS_EXCHANGE = chr(243)

OverlaySwarmMessages= PermIDMessages + BuddyCastMessages + MetadataMessages + HelpCoordinatorMessages + HelpHelperMessages

def getMessageName(t):
    if t == CHOKE:
        return "CHOKE"
    elif t == UNCHOKE:
        return "UNCHOKE"
    elif t == INTERESTED:
        return "INTEREST"
    elif t == NOT_INTERESTED:
        return "NOT_INTEREST"
    elif t == HAVE:
        return "HAVE"
    elif t == BITFIELD:
        return "BITFIELD"
    elif t == REQUEST:
        return "REQUEST"
    elif t == CANCEL:
        return "CANCEL"
    elif t == PIECE:
        return "PIECE"
    elif t == CHALLENGE:
        return "CHALLENGE"            
    elif t == RESPONSE1:
        return "RESPONSE1"
    elif t == RESPONSE2:
        return "RESPONSE2"
    elif t == DOWNLOAD_HELP:
        return "DOWNLOAD_HELP"
    elif t == STOP_DOWNLOAD_HELP:
        return "STOP_DOWNLOAD_HELP"
    elif t == HASHPIECE:
        return "HASHPIECE"
    elif t == PREFERENCE_EXCHANGE:
        return "PREFERENCE_EXCHANGE"
    elif t == GET_METADATA:
        return "GET_METADATA"
    elif t == METADATA:
        return "METADATA"
    elif t == RESERVE_PIECES:
        return "RESERVE_PIECES"
    elif t == PIECES_RESERVED:
        return "PIECES_RESERVED"
    else:
        return "unknown!"+str(ord(t))
        
