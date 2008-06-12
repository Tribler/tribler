# Written by Arno Bakker
# see LICENSE.txt for license information
#
# SecureOverlay message handler for a Coordinator
#
import sys

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Utilities.utilities import show_permid_short

DEBUG = False

class CoordinatorMessageHandler:
    def __init__(self,launchmany):
        self.launchmany = launchmany

    #def register(self):

    def handleMessage(self,permid,selversion,message):
        t = message[0]
        #if DEBUG:
        #    print >> sys.stderr,"helpcoord: Got",getMessageName(t)

        if t == RESERVE_PIECES:
            return self.got_reserve_pieces(permid, message, selversion)
        
    def got_reserve_pieces(self, permid, message,selversion):
        try:
            infohash = message[1:21]
            all_or_nothing = message[21]
            pieces = bdecode(message[22:])
        except:
            print >> sys.stderr, "warning: bad data in RESERVE_PIECES"
            return False

        network_got_reserve_pieces_lambda = lambda:self.network_got_reserve_pieces(permid,infohash,pieces,all_or_nothing,selversion)
        self.launchmany.rawserver.add_task(network_got_reserve_pieces_lambda,0)
        return True 


    def network_got_reserve_pieces(self,permid,infohash,pieces,all_or_nothing,selversion):
        # Called by network thread
        c = self.launchmany.get_coopdl_role_object(infohash,COOPDL_ROLE_COORDINATOR)
        if c is None:
            return

        ## FIXME: if he's not a helper, but thinks he is, we better send him
        ## a STOP_DOWNLOAD_HELP (again)
        if not c.is_helper_permid(permid):
            if DEBUG:
                print >> sys.stderr,"helpcoord: Ignoring RESERVE_PIECES from non-helper",show_permid_short(permid)
            return

        c.got_reserve_pieces(permid, pieces, all_or_nothing, selversion)
