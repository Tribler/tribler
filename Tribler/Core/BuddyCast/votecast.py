# Written by Rameez Rahman
# see LICENSE.txt for license information
#

import sys
from time import time
from sets import Set

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.BitTornado.BT1.MessageID import VOTECAST
from Tribler.Core.CacheDB.CacheDBHandler import VoteCastDBHandler
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Overlay.permid import permid_for_user
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Core.BuddyCast.moderationcast_util import *
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_THIRTEENTH
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_VOTECAST, NTFY_UPDATE

DEBUG_UI = False
DEBUG = False    #Default debug
debug = False    #For send-errors and other low-level stuff


SINGLE_VOTECAST_LENGTH = 130

class VoteCastCore:
    """ VoteCastCore is responsible for sending and receiving VOTECAST-messages """

    TESTASSERVER = False # for unit testing
    
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
        self.session = session
        self.max_length = SINGLE_VOTECAST_LENGTH * (session.get_votecast_random_votes() + session.get_votecast_recent_votes())       

        self.network_delay = 30
        #Reference to buddycast-core, set by the buddycast-core (as it is created by the
        #buddycast-factory after calling this constructor).
        self.buddycast_core = None
        
        
        self.notifier = Notifier.getInstance()
        
        #Extend logging with VoteCast-messages and status
        if self.log:
            self.overlay_log = OverlayLogger.getInstance(self.log)

    def initialized(self):
        return self.buddycast_core is not None

    ################################
    def createAndSendVoteCastMessage(self, target_permid, selversion):
        """ Creates and sends a VOTECAST message """
        # Arno, 2010-02-05: v12 uses a different on-the-wire format, ignore those.
        if selversion < OLPROTO_VER_THIRTEENTH:
            if DEBUG:
                print >> sys.stderr, "votecast: Do not send to lower version peer:", selversion
            return
                
        votecast_data = self.createVoteCastMessage()
        if len(votecast_data) == 0:
            if DEBUG:
                print >>sys.stderr, "votecast: No votes there.. hence we do not send"            
            return
        
        votecast_msg = bencode(votecast_data)
         
        if self.log:
            dns = self.dnsindb(target_permid)
            if dns:
                ip,port = dns
                MSG_ID = "VOTECAST"
                # msg = voteCastReplyMsgToString(votecast_data)
                self.overlay_log('SEND_MSG', ip, port, show_permid(target_permid), selversion, MSG_ID)
        
        if DEBUG: print >> sys.stderr, "votecast: Sending votecastmsg",voteCastMsgToString(votecast_data)
#        data = VOTECAST + votecast_msg
#        self.secure_overlay.send(target_permid, data, self.voteCastSendCallback)
        self.secure_overlay.send(target_permid, VOTECAST + votecast_msg, self.voteCastSendCallback)           
        

    ################################
    def createVoteCastMessage(self):
        """ Create a VOTECAST message """

        if DEBUG: print >> sys.stderr, "votecast: Creating votecastmsg..."        
        
        NO_RANDOM_VOTES = self.session.get_votecast_random_votes()
        NO_RECENT_VOTES = self.session.get_votecast_recent_votes()
        records = self.votecastdb.getRecentAndRandomVotes()

        data = {}
        for record in records:
            # record is of the format: (publisher_id, vote, time_stamp)
            if DEBUG:
                print >>sys.stderr,"votecast: publisher id",`record[0]`,type(record[0]) 
            publisher_id = record[0]
            data[publisher_id] = {'vote':record[1], 'time_stamp':record[2]}
        if DEBUG: print >>sys.stderr, "votecast to be sent:", repr(data)
        return data

    
    ################################
    def voteCastSendCallback(self, exc, target_permid, other=0):
        if DEBUG:
            if exc is None:
                print >> sys.stderr,"votecast: *** msg was sent successfully to peer", show_permid_short(target_permid)
            else:
                print >> sys.stderr, "votecast: *** warning - error in sending msg to", show_permid_short(target_permid), exc

    ################################
    def gotVoteCastMessage(self, recv_msg, sender_permid, selversion):
        """ Receives VoteCast message and handles it. """
        # VoteCast feature is renewed in eleventh version; hence, do not receive from lower version peers
        # Arno, 2010-02-05: v12 uses a different on-the-wire format, ignore those.
        if selversion < OLPROTO_VER_THIRTEENTH:
            if DEBUG:
                print >> sys.stderr, "votecast: Do not receive from lower version peer:", selversion
            return True
                
        if DEBUG:
            print >> sys.stderr,'votecast: Received a msg from ', show_permid_short(sender_permid)

        if not sender_permid or sender_permid == self.my_permid:
            if DEBUG:

                print >> sys.stderr, "votecast: error - got votecastMsg from a None peer", \
                        show_permid_short(sender_permid), recv_msg
            return False

        if self.max_length > 0 and len(recv_msg) > self.max_length:
            if DEBUG:
                print >> sys.stderr, "votecast: warning - got large voteCastHaveMsg; msg_size:", len(recv_msg)
            return False

        votecast_data = {}

        try:
            votecast_data = bdecode(recv_msg)
        except:
            print >> sys.stderr, "votecast: warning, invalid bencoded data"
            return False

        # check message-structure
        if not validVoteCastMsg(votecast_data):
            print >> sys.stderr, "votecast: warning, invalid votecast_message"
            return False
        
        self.handleVoteCastMsg(sender_permid, votecast_data)

        #Log RECV_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(sender_permid)
            if dns:
                ip,port = dns
                MSG_ID = "VOTECAST"
                msg = voteCastMsgToString(votecast_data)
                self.overlay_log('RECV_MSG', ip, port, show_permid(sender_permid), selversion, MSG_ID, msg)
 
        if self.TESTASSERVER:
            self.createAndSendVoteCastMessage(sender_permid, selversion)
        return True

    ################################
        ################################
    def handleVoteCastMsg(self, sender_permid, data):
        """ Handles VoteCast message """
        if DEBUG: 
            print >> sys.stderr, "votecast: Processing VOTECAST msg from: ", show_permid_short(sender_permid), "; data: ", repr(data)

        mod_ids = Set()
        for key, value in data.items():
            vote = {}
            vote['mod_id'] = bin2str(key)
            vote['voter_id'] = permid_for_user(sender_permid)
            vote['vote'] = value['vote']
            vote['time_stamp'] = value['time_stamp'] 
            self.votecastdb.addVote(vote)
            
            mod_ids.add(vote['mod_id'])

        # Arno, 2010-02-24: Generate event
        for mod_id in mod_ids:
            try:
                self.notifier.notify(NTFY_VOTECAST, NTFY_UPDATE, mod_id)
            except:
                print_exc()
            
        if DEBUG:
            print >> sys.stderr,"votecast: Processing VOTECAST msg from: ", show_permid_short(sender_permid), "DONE; data:"
            
    def showAllVotes(self):
        """ Currently this function is only for testing, to show all votes """
        if DEBUG:
            records = self.votecastdb.getAll()
            print >>sys.stderr, "Existing votes..."
            for record in records:
                print >>sys.stderr, "    mod_id:",record[0],"; voter_id:", record[1], "; votes:",record[2],"; timestamp:", record[3]
            print >>sys.stderr, "End of votes..."        

    


    ################################
