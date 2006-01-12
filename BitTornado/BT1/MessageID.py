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

DOWNLOAD_HELP = chr(246)
# 2fastbt_
RESERVE_PIECES = chr(242)
PIECES_RESERVED = chr(241)
IGNORE_PIECES = chr(240)
# _2fastbt

HelpMessages = [DOWNLOAD_HELP,RESERVE_PIECES,PIECES_RESERVED,IGNORE_PIECES]

ONLINE_EXCHANGE = chr(244)
FRIENDS_EXCHANGE = chr(243)

OverlaySwarmMessages= PermIDMessages + BuddyCastMessages + MetadataMessages + HelpMessages

def printMessageID(t,message):
    if t == CHOKE:
        print "GOT CHOKE",len(message)
    elif t == UNCHOKE:
        print "GOT UNCHOKE",len(message)
    elif t == INTERESTED:
        print "GOT INTEREST",len(message)
    elif t == NOT_INTERESTED:
        print "GOT NOT_INTEREST",len(message)
    elif t == HAVE:
        print "GOT HAVE",len(message)
    elif t == BITFIELD:
        print "GOT BITFIELD",len(message)
    elif t == REQUEST:
        print "GOT REQUEST",len(message)
    elif t == CANCEL:
        print "GOT CANCEL",len(message)
    elif t == PIECE:
        print "GOT PIECE",len(message)
    elif t == CHALLENGE:
        print "GOT CHALLENGE",len(message)            
    elif t == RESPONSE1:
        print "GOT RESPONSE1",len(message)
    elif t == RESPONSE2:
        print "GOT RESPONSE2",len(message)
    elif t == DOWNLOAD_HELP:
        print "GOT DOWNLOAD_HELP", len(message)
    elif t == HASHPIECE:
        print "GOT HASHPIECE", len(message)
    elif t == PREFERENCE_EXCHANGE:
        print "GOT PREFERENCE_EXCHANGE", len(message)
    elif t == GET_METADATA:
        print "GOT GET_METADATA", len(message)
    elif t == METADATA:
        print "GOT SEND_METADATA", len(message)
    elif t == RESERVE_PIECES:
        print "GOT RESERVE_PIECES", len(message)
    elif t == PIECES_RESERVED:
        print "GOT PIECES_RESERVED", len(message)
    elif t == IGNORE_PIECES:
        print "GOT IGNORE_PIECES", len(message)
    else:
        print "GOT unknown!",`t`,"length",len(message)
        
