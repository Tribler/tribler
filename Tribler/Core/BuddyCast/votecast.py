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
from Tribler.Core.CacheDB.SqliteCacheDBHandler import PeerDBHandler

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
        
        self.peerdb = PeerDBHandler.getInstance()
        self.votecastdb = VoteCastDBHandler.getInstance()
        
        self.my_permid = self.votecastdb.my_permid
        self.session = session
        self.max_length = SINGLE_VOTECAST_LENGTH * (session.get_votecast_random_votes() + session.get_votecast_recent_votes())       

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
    def createVoteCastMessage(self):
        """ Create a VOTECAST message """
        #TODO: REPLACE WITH DISPERSY
        """
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
        """
    
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
        return True

    def handleVoteCastMsg(self, sender_permid, data):
        """ Handles VoteCast message """
        if DEBUG: 
            print >> sys.stderr, "votecast: Processing VOTECAST msg from: ", show_permid_short(sender_permid), "; data: ", repr(data)
        
        modified_channels = set()
        
        votes = []
        voter_id = self.peerdb.getPeerID(sender_permid)
        for key, value in data.items():
            #TODO: seems incorrect
            channel_id = self.peerdb.getPeerID(key)
            vote = value['vote']
            time_stamp = value['time_stamp']
            
            votes.append((channel_id, voter_id, vote, time_stamp))
            modified_channels.add(channel_id)
        
        self.votecastdb.addVotes(votes)
        for channel_id in modified_channels:
            try:
                self.notifier.notify(NTFY_VOTECAST, NTFY_UPDATE, channel_id)
            except:
                print_exc()
        if DEBUG:
            print >> sys.stderr,"votecast: Processing VOTECAST msg from: ", show_permid_short(sender_permid), "DONE; data:"