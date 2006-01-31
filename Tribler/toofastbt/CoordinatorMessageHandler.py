# Written by Arno Bakker
# see LICENSE.txt for license information
""" SecureOverlay message handler for a Coordinator """

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
            if DEBUG:
                print "helpcoord: UNKNOWN OVERLAY MESSAGE", ord(t)
        
    def got_reserve_pieces(self, permid, message):
        try:
            torrent_hash = message[1:21]
            all_or_nothing = message[21]
            pieces = bdecode(message[22:])
        except:
            errorfunc("warning: bad data in RESERVE_PIECES")
            return False

# TODO: add smarter concurrency control, see SecureOverlay. Currently has 1 big lock

        c = self.launchmany.get_coordinator(torrent_hash)
        if c is None:
            return False

        if not c.is_helper_permid(permid): 
            return False

        c.got_reserve_pieces(permid, pieces, all_or_nothing)
        return True
