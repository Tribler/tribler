# Written by Arno Bakker
# see LICENSE.txt for license information
""" SecureOverlay message handler for a Coordinator """

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *
from Tribler.Overlay.permid import show_permid

DEBUG = False

class CoordinatorMessageHandler:
    def __init__(self,launchmany):
        self.launchmany = launchmany

    #def register(self):
    

    def handleMessage(self,permid,message):
        t = message[0]
        if DEBUG:
            print "helpcoord: Got",getMessageName(t)
#            get_logger().log(3, "connection: got RESERVE_PIECES")

        if t == RESERVE_PIECES:
            return self.got_reserve_pieces(permid, message)
        
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

        ## FIXME: if he's not a helper, but thinks he is, we better send him
        ## a STOP_DOWNLOAD_HELP (again)
        if not c.is_helper_permid(permid):
            if DEBUG:
                print "helpcoord: Ignoring RESERVE_PIECES from non-helper",show_permid(permid)
            return False

        c.got_reserve_pieces(permid, pieces, all_or_nothing)
        return True
