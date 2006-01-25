from Tribler.toofastbt.intencode import toint, tobinary
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *

DEBUG = True



class CoordinatorMessageHandler:
    def __init__(self,launchmany):
        self.launchmany = launchmany

    #def register(self):
    

    def handleMessage(self,permid,message):
        t = message[0]
        
        if t == RESERVE_PIECES:
            if DEBUG:
                print "helpcoord: Got RESERVE_PIECES"
#            get_logger().log(3, "connection: got RESERVE_PIECES")
            return self.got_reserve_pieces(permid, message)
        else:
            print "helpcoord: UNKNOWN OVERLAY MESSAGE", ord(t)
        
    def got_reserve_pieces(self, permid, message):
        try:
            torrent_hash = message[1:21]
            reqid = toint(message[21:25])
            all_or_nothing = message[25]
            pieces = bdecode(message[26:])
        except:
            errorfunc("warning: bad data in RESERVE_PIECES")
            return False

# TODO: add concurrency control

        c = self.launchmany.get_coordinator(torrent_hash)
        if c is None:
            return False

        if not c.is_helper(permid): 
            return False

        c.got_reserve_pieces(permid, reqid, pieces, all_or_nothing)
        return True
