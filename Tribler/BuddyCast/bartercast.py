from BitTornado.bencode import bencode, bdecode
from Tribler.Statistics.Logger import OverlayLogger
from BitTornado.BT1.MessageID import BARTERCAST #, KEEP_ALIVE
from Tribler.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.utilities import *
from Tribler.Overlay.permid import permid_for_user
from traceback import print_exc, print_stack
from types import StringType, ListType, DictType

from Tribler.Overlay.SecureOverlay import OLPROTO_VER_FIFTH


MAX_BARTERCAST_LENGTH = 10 * 1024 * 1024 # TODO: give this length a reasonable value
NO_PEERS_IN_MSG = 10

debug = True

class BarterCastCore:

    ################################
    def __init__(self, data_handler, secure_overlay, log = ''):
    
        self.data_handler = data_handler
        self.dnsindb = self.data_handler.get_dns_from_peerdb
        self.log = log
        self.secure_overlay = secure_overlay
        self.bartercastdb = BarterCastDBHandler()
        self.buddycast_core = None

        if self.log:
            self.overlay_log = OverlayLogger(self.log)


    ################################
    def createAndSendBarterCastMessage(self, target_permid, selversion):

        # for older versions of Tribler (non-BarterCast): do nothing
        if selversion <= OLPROTO_VER_FIFTH:
            return

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
            

    ################################
    def createBarterCastMessage(self, target_permid):
        """ Create a bartercast message """

        my_permid = self.bartercastdb.my_permid
        top_peers = map(lambda (permid, value): permid, self.bartercastdb.getTopNPeers(NO_PEERS_IN_MSG))
        data = {}
        
        for permid in top_peers:
            
            item = self.bartercastdb.getItem((my_permid, permid))
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
            if debug:
                print "bartercast: *** msg was sent successfully to peer", self.bartercastdb.getName(target_permid)
        else:
            if debug:
                print "bartercast: *** warning - error in sending msg to", self.bartercastdb.getName(target_permid), exc



    ################################
    def gotBarterCastMessage(self, recv_msg, sender_permid, selversion):
        """ Received a bartercast message and handle it. Reply if needed """
        
        if debug:
            print 'Received a BarterCast message from ', permid_for_user(sender_permid)
            
        if not sender_permid or sender_permid == self.bartercastdb.my_permid:
            print >> sys.stderr, "bartercast: error - got BarterCastMsg from a None peer", \
                        sender_permid, recv_msg
            return False
        
        if self.buddycast_core.isBlocked(sender_permid, self.buddycast_core.recv_block_list):
            if DEBUG:
                print >> sys.stderr, "bc: warning - got BuddyCastMsg from a recv blocked peer", \
                        show_permid(sender_permid), "Round", self.round
            return True     # allow the connection to be kept. That peer may have restarted in 4 hours
        
        if MAX_BARTERCAST_LENGTH > 0 and len(recv_msg) > MAX_BARTERCAST_LENGTH:
            print >> sys.stderr, "bartercast: warning - got large BarterCastMsg", len(t)
            return False

        active = self.buddycast_core.isBlocked(sender_permid, self.buddycast_core.send_block_list)

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
       
#        self.blockPeer(sender_permid, self.recv_block_list)
        
        if not active:
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
        
        # process bartercast data in database
        for permid in data.keys():

            data_to = data[permid]['u']
            data_from = data[permid]['d']

            # update database sender->permid and permid->sender
            self.bartercastdb.updateItem((sender_permid, permid), 'uploaded', data_to)
            self.bartercastdb.updateItem((sender_permid, permid), 'downloaded', data_from)
            

    ################################
    def replyBarterCast(self, target_permid, selversion):
        """ Reply a bartercast message """

        if not self.buddycast_core.isConnected(target_permid):
            print >> sys.stderr, 'bartercast: lost connection while replying buddycast', \
                "Round", self.buddycast_core.round
            return

        self.createAndSendBarterCastMessage(target_permid, selversion)

#        self.blockPeer(target_permid, self.send_block_list, self.short_block_interval)
#        self.removeConnCandidate(target_permid)
#        self.next_initiate += 1        # Be idel in next round
