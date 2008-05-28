from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.BitTornado.BT1.MessageID import BARTERCAST #, KEEP_ALIVE
from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.Core.Utilities.utilities import *
from traceback import print_exc, print_stack
from types import StringType, ListType, DictType
from time import time, gmtime, strftime, ctime

from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FIFTH


MAX_BARTERCAST_LENGTH = 10 * 1024 * 1024 # TODO: give this length a reasonable value
NO_PEERS_IN_MSG = 10

DEBUG = False

def now():
    return int(time())
    
class BarterCastCore:

    ################################
    def __init__(self, data_handler, secure_overlay, log = '', dnsindb = None):
    
        if DEBUG:
            print >> sys.stderr, "=================Initializing bartercast core"
    
        self.data_handler = data_handler
        self.dnsindb = dnsindb
        self.log = log
        self.secure_overlay = secure_overlay
        self.bartercastdb = BarterCastDBHandler.getInstance()
        
        self.network_delay = 30
        self.send_block_list = {}
        self.recv_block_list = {}
        self.block_interval = 1*60*60   # block interval for a peer to barter   cast
        
        if self.log:
            self.overlay_log = OverlayLogger(self.log)


    ################################
    def createAndSendBarterCastMessage(self, target_permid, selversion, active = False):


        # for older versions of Tribler (non-BarterCast): do nothing
        if selversion <= OLPROTO_VER_FIFTH:
            return

        if DEBUG:
            print >> sys.stderr, "===========bartercast: Sending BarterCast msg to ", self.bartercastdb.getName(target_permid)

        # create a new bartercast message
        bartercast_data = self.createBarterCastMessage(target_permid)

        try:
            bartercast_msg = bencode(bartercast_data)
        except:
            print_exc()
            print >> sys.stderr, "error bartercast_data:", bartercast_data
            return
            
        # send the message    
        self.secure_overlay.send(target_permid, BARTERCAST+bartercast_msg, self.bartercastSendCallback)

        self.blockPeer(target_permid, self.send_block_list, self.block_interval)
            

    ################################
    def createBarterCastMessage(self, target_permid):
        """ Create a bartercast message """

        my_permid = self.bartercastdb.my_permid
        local_top = self.bartercastdb.getTopNPeers(NO_PEERS_IN_MSG, local_only = True)['top']
        top_peers = map(lambda (permid, up, down): permid, local_top)
        data = {}
        
        for permid in top_peers:
            
            item = self.bartercastdb.getItem((my_permid, permid))
            
            if item is not None:
                # retrieve what i have uploaded to permid
                data_to = item['uploaded']
                # retrieve what i have downloaded from permid
                data_from = item['downloaded']

                data[permid] = {'u': data_to, 'd': data_from}
        
        bartercast_data = {'data': data}
        
        return bartercast_data


    ################################
    def bartercastSendCallback(self, exc, target_permid, other=0):
        if exc is None:
            if DEBUG:
                print "bartercast: %s *** msg was sent successfully to peer %s" % (ctime(now()), self.bartercastdb.getName(target_permid))
        else:
            if DEBUG:
                print "bartercast: %s *** warning - error in sending msg to %s" % (ctime(now()), self.bartercastdb.getName(target_permid))


    ################################
    def gotBarterCastMessage(self, recv_msg, sender_permid, selversion):
        """ Received a bartercast message and handle it. Reply if needed """
        
        if DEBUG:
            print >>sys.stderr,'bartercast: %s Received a BarterCast msg from %s'% (ctime(now()), self.bartercastdb.getName(sender_permid))
            
        if not sender_permid or sender_permid == self.bartercastdb.my_permid:
            print >> sys.stderr, "bartercast: error - got BarterCastMsg from a None peer", \
                        sender_permid, recv_msg
            return False
        
        if MAX_BARTERCAST_LENGTH > 0 and len(recv_msg) > MAX_BARTERCAST_LENGTH:
            print >> sys.stderr, "bartercast: warning - got large BarterCastMsg", len(t)
            return False

        bartercast_data = {}

        try:
            bartercast_data = bdecode(recv_msg)
        except:
            print >> sys.stderr, "bartercast: warning, invalid bencoded data"
            return False
            
        try:    # check bartercast message
            self.validBarterCastMsg(bartercast_data)
        except RuntimeError, msg:
            print >> sys.stderr, msg
            return False
       
        data = bartercast_data['data']

        self.handleBarterCastMsg(sender_permid, data)
       
        if not self.isBlocked(sender_permid, self.send_block_list):
            self.replyBarterCast(sender_permid, selversion)    
        
        return True



    ################################
    def validBarterCastMsg(self, bartercast_data):

        if not type(bartercast_data) == DictType:
            raise RuntimeError, "bartercast: received data is not a dictionary"
            return False
            
        if not bartercast_data.has_key('data'):
            raise RuntimeError, "bartercast: 'data' key doesn't exist"
            return False

        if not type(bartercast_data['data']) == DictType:
            raise RuntimeError, "bartercast: 'data' value is not dictionary"
            return False
        
        for permid in bartercast_data['data'].keys():
                        
            if not bartercast_data['data'][permid].has_key('u') or \
               not bartercast_data['data'][permid].has_key('d'):
                raise RuntimeError, "bartercast: datafield doesn't contain 'u' or 'd' keys"
                return False
        
        return True
       
    ################################
    def handleBarterCastMsg(self, sender_permid, data):
        
        if DEBUG:
            print >> sys.stderr, "bartercast: Processing bartercast msg from: ", self.bartercastdb.getName(sender_permid)
        
        # process bartercast data in database
        for permid in data.keys():
            
            data_to = data[permid]['u']
            data_from = data[permid]['d']
            
            if DEBUG:
                print >> sys.stderr, "bartercast: data: (%s, %s) up = %d down = %d" % (self.bartercastdb.getName(sender_permid), self.bartercastdb.getName(permid),\
                                                                        data_to, data_from)

            # update database sender->permid and permid->sender
            self.bartercastdb.updateItem((sender_permid, permid), 'uploaded', data_to)
            self.bartercastdb.updateItem((sender_permid, permid), 'downloaded', data_from)
            

    ################################
    def replyBarterCast(self, target_permid, selversion):
        """ Reply a bartercast message """

        self.createAndSendBarterCastMessage(target_permid, selversion)




    # Blocking functions (similar to BuddyCast):
    
    ################################
    def isBlocked(self, peer_permid, block_list):
        if peer_permid not in block_list:
            return False
        unblock_time = block_list[peer_permid]
        if now() >= unblock_time - self.network_delay:    # 30 seconds for network delay
            block_list.pop(peer_permid)
            return False
        return True



    ################################
    def blockPeer(self, peer_permid, block_list, block_interval=None):
        """ Add a peer to a block list """

        if block_interval is None:
            block_interval = self.block_interval
        unblock_time = now() + block_interval
        block_list[peer_permid] = unblock_time
        
        if DEBUG:
            print >>sys.stderr,'bartercast: %s Blocked peer %s'% (ctime(now()), self.bartercastdb.getName(peer_permid))
