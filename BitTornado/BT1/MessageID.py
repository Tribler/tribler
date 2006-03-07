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
{'preferences':[[infohash]],
 'permid': my permid, 
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

BuddyCastMessages = [BUDDYCAST]

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

ONLINE_EXCHANGE = chr(244)
FRIENDS_EXCHANGE = chr(243)

# torrent_hash + 1-byte all_or_nothing + bencode([piece num,...])
RESERVE_PIECES = chr(242)
# torrent_hash + bencode([piece num,...])
PIECES_RESERVED = chr(241)

HelpCoordinatorMessages = [DOWNLOAD_HELP,STOP_DOWNLOAD_HELP,PIECES_RESERVED]
HelpHelperMessages = [RESERVE_PIECES]
# _2fastbt

OverlaySwarmMessages= PermIDMessages + BuddyCastMessages + MetadataMessages + HelpCoordinatorMessages + HelpHelperMessages


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
    ONLINE_EXCHANGE:"ONLINE_EXCHANGE",
    FRIENDS_EXCHANGE:"FRIENDS_EXCHANGE",
}


def getMessageName(t):
    if t in message_map:
        return message_map[t]
    else:
        return "Unknown_MessageID_"+str(ord(t))
        
