#Written By Rameez Rahman
#from BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.bencode import bencode, bdecode
#from Tribler.Statistics.Logger import OverlayLogger
from Tribler.Core.Statistics.Logger import OverlayLogger
#from BitTornado.BT1.MessageID import MODERATIONCAST_HAVE, MODERATIONCAST_REQUEST, MODERATIONCAST_REPLY
from Tribler.Core.BitTornado.BT1.MessageID import VOTECAST
#from Tribler.Core.CacheDB.SynDBHandler import SynTorrentDBHandler

#from Tribler.Core.CacheDB.CacheDBHandler import MyDBHandler
from Tribler.Core.CacheDB.CacheDBHandler import VoteCastDBHandler
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Overlay.permid import permid_for_user

from traceback import print_exc, print_stack
from types import StringType, ListType, DictType

from Tribler.Core.Overlay.permid import sign_data
#from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SEVEN
#MIN_VERSION = OLPROTO_VER_SEVEN

from time import time, ctime
from zlib import compress, decompress
from base64 import decodestring
from binascii import hexlify

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.BuddyCast.moderationcast_util import *

DEBUG_UI = False
DEBUG = False    #Default debug
debug = False    #For send-errors and other low-level stuff

AUTO_MODERATE = False    #Automatically moderate content, with bogus moderations
AUTO_MODERATE_INTERVAL = 1    #Number of seconds between creation of moderations

NO_RANDOM_VOTES = 12
NO_RECENT_VOTES = 13

from random import randint, sample, seed, random

class VoteCastCore:
    """ VoteCastCore is responsible for sending and receiving VOTECAST-messages """

    ################################
    def __init__(self, data_handler, secure_overlay, session, buddycast_interval_function, log = '', dnsindb = None):
        """ Returns an instance of this class
        """
        #Keep reference to interval-function of BuddycastFactory
        self.interval = buddycast_interval_function
        self.data_handler = data_handler
        self.dnsindb = dnsindb
        self.log = log
        self.secure_overlay = secure_overlay
        self.votecastdb = VoteCastDBHandler.getInstance()
        self.my_permid = self.votecastdb.my_permid
        self.max_have_length = SINGLE_HAVE_LENGTH * session.get_moderationcast_moderations_per_have()

        self.network_delay = 30
        #Reference to buddycast-core, set by the buddycast-core (as it is created by the
        #buddycast-factory after calling this constructor).
        self.buddycast_core = None
        self.send_block_list = {}
        self.recv_block_list = {}
        self.block_interval = 1*60*60   # block interval for a peer to vote   cast
        #Blocklist (to keep track of sent HAVE-messages)
        #self.blockHave = BlockList(BLOCK_HAVE_TIME)
        
        #BandwidthLimiters (to limit the used upload- and download-bandwith)
        self.uploadLimiter = SustainableBandwidthLimiter(session.get_moderationcast_upload_bandwidth_limit())
        self.downloadLimiter = SustainableBandwidthLimiter(session.get_moderationcast_download_bandwidth_limit())

        #Debug-interface
        if DEBUG_UI:
            from moderationcast_test import ModerationCastTest
            ModerationCastTest(self)

        #Extend logging with ModerationCAST-messages and status
        if self.log:
            self.overlay_log = OverlayLogger.getInstance(self.log)
            self.dnsindb = self.data_handler.get_dns_from_peerdb
            
        if AUTO_MODERATE:
            assert AUTO_MODERATE_INTERVAL > 0
            from moderationcast_experiment import BogusAutoModerator
            self.auto_moderator = BogusAutoModerator(AUTO_MODERATE_INTERVAL)

    def initialized(self):
        return self.buddycast_core is not None

    ################################
    def createAndSendVoteCastMessage(self, target_permid, selversion):
        votecast_data = self.createVoteCastMessage(target_permid)
        
        #print >> sys.stderr, "And this is vote message"
        
        votecast_msg = bencode(votecast_data)
        
        #self.blockHave.add(target_permid)
         
        if self.log:
            dns = self.dnsindb(target_permid)
            if dns:
                ip,port = dns
                MSG_ID = "VOTECAST"
                msg = voteCastReplyMsgToString(votecast_data)
                self.overlay_log('SEND_MSG', ip, port, show_permid(target_permid), selversion, MSG_ID, msg)
        
        
        if DEBUG: print >> sys.stderr, "Sending votecastmsg",voteCastMsgToString(votecast_data)
        data = VOTECAST+votecast_msg
        self.blockPeer(target_permid, self.send_block_list, self.block_interval)
        self.secure_overlay.send(target_permid, data, self.voteCastSendCallback)        
        

    ################################
    def createVoteCastMessage(self, target_permid):
        """ Create a VOTECAST message """

        #Select latest own moderations
        if DEBUG: print >> sys.stderr, "Creating votecastmsg..."
        records = self.votecastdb.recentVotes(NO_RECENT_VOTES)
        
        #Add random own moderations
        size = NO_RANDOM_VOTES+NO_RECENT_VOTES
        random_own = self.votecastdb.randomVotes(size)
        #print >> sys.stderr, "random own >>>>>>>>>>> ", random_own
        
        for vote in random_own:
            if len(records) == size:
                break
            #print >> sys.stderr, "votes information", vote
            if vote not in records:
                records.append(vote)
        data = []        
        for record in records:            
            mod_id = record[0]
            vote = record[1]
            data.append((mod_id, vote))
        return data

    
    ################################
    def voteCastSendCallback(self, exc, target_permid, other=0):
        if DEBUG:
            if exc is None:
                print >> sys.stderr,"votecast: *** msg was sent successfully to peer", permid_for_user(target_permid)
            else:
                print >> sys.stderr, "votecast: *** warning - error in sending msg to", permid_for_user(target_permid), exc

    ################################
    def gotVoteCastMessage(self, recv_msg, sender_permid, selversion):
        if DEBUG:
            print >> sys.stderr,'votecast: Received a msg from ', permid_for_user(sender_permid)

        if not sender_permid or sender_permid == self.my_permid:
            if DEBUG:

                print >> sys.stderr, "votecast: error - got votecastMsg from a None peer", \
                        permid_for_user(sender_permid), recv_msg
            return False

        if self.max_have_length > 0 and len(recv_msg) > self.max_have_length:
            if DEBUG:

                print >> sys.stderr, "votecast: warning - got large voteCastHaveMsg", len(t)
            return False

        #active = self.blockHave.blocked(sender_permid)

        votecast_data = {}

        try:
            votecast_data = bdecode(recv_msg)
        except:
            print >> sys.stderr, "votecast: warning, invalid bencoded data"
            return False

        # check message-structure
        if not validVoteCastMsg(votecast_data):
            print >> sys.stderr, "votecast: invalid votecast_message"
            return False
        
        st = time()
        self.handleVoteCastMsg(sender_permid, votecast_data)
        et = time()
        diff = et - st
        if DEBUG:
            print >>sys.stderr,"votecast: HANDLE took %.4f" % diff            

        #Log RECV_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(sender_permid)
            if dns:
                ip,port = dns
                MSG_ID = "VOTECAST"
                msg = voteCastMsgToString(votecast_data)
                self.overlay_log('RECV_MSG', ip, port, show_permid(sender_permid), selversion, MSG_ID, msg)
        #Send have-message, if we have not done so
        #print >> sys.stderr, "should be twice right"
        if not self.isBlocked(sender_permid, self.send_block_list):
            self.replyVoteCast(sender_permid, selversion)
        
        return True

    ################################
        ################################
    def handleVoteCastMsg(self, sender_permid, data):
        
        print >> sys.stderr, "Processing VOTECAST msg from: ", permid_for_user(sender_permid), "; data: ", repr(data)
    
        for value in data:
            vote = {}
            #print >> sys.stderr,"intention>>>>", value
            vote['mod_id'] = value[0]
            vote['voter_id'] = self.votecastdb.getPeerID(sender_permid)
            #print >> sys.stderr,"this is the peer id so it should be clear", vote['voter_id']
            vote['vote'] = value[1] 
            self.votecastdb.addVote(vote)
            
        if DEBUG:
            print >> sys.stderr,"Processing VOTECAST msg from: ", permid_for_user(sender_permid), "DONE; data:"
            
    ################################
    def replyVoteCast(self, target_permid, selversion):
        """ Reply a VoteCast message """

        self.createAndSendVoteCastMessage(target_permid, selversion)

    ################################
    def isBlocked(self, peer_permid, block_list):
        if peer_permid not in block_list:
            return False
        unblock_time = block_list[peer_permid]
        if now() >= unblock_time - self.network_delay:    # 30 seconds for network delay
            block_list.pop(peer_permid)
            return False
        return True
    
    def blockPeer(self, peer_permid, block_list, block_interval=None):
        """ Add a peer to a block list """

        if block_interval is None:
            block_interval = self.block_interval
        unblock_time = now() + block_interval
        block_list[peer_permid] = unblock_time
        
        if DEBUG:
            print >>sys.stderr,'votecast: %s Blocked peer %s'% (ctime(now()), permid_for_user(peer_permid))
            
    def showAllVotes(self):
        """ Currently this function is only for testing, to show all votes """
        if DEBUG:
            records = self.votecastdb.getAll()
            print >>sys.stderr, "Existing votes..."
            for record in records:
                print >>sys.stderr, "    mod_id:",record[0],"; voter_id:", record[1], "; votes:",record[2],"; timestamp:", record[3]
            print >>sys.stderr, "End of votes..."        

    


    ################################
