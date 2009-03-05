#Written By Vincent Heinink and Rameez Rahman

from Tribler.Core.BitTornado.BT1.MessageID import MODERATIONCAST_HAVE, MODERATIONCAST_REQUEST, MODERATIONCAST_REPLY
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BuddyCast.moderationcast_util import *
from Tribler.Core.CacheDB.CacheDBHandler import ModerationCastDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.Overlay.permid import permid_for_user
from Tribler.Core.Overlay.permid import sign_data
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.Utilities.utilities import *

from base64 import decodestring
from binascii import hexlify
from time import time
from traceback import print_exc, print_stack
from types import StringType, ListType, DictType
from zlib import compress, decompress

DEBUG_UI = False
DEBUG = False    #Default debug
debug = False   #For send-errors and other low-level stuff

AUTO_MODERATE = False    #Automatically moderate content, with bogus moderations
AUTO_MODERATE_INTERVAL = 1    #Number of seconds between creation of moderations

from random import randint, sample, seed, random

class ModerationCastCore:
    """ ModerationCastCore is responsible for sending and receiving:
        MODERATIONCAST_HAVE, MODERATIONCAST_REQUEST, and MODERATIONCAST_REPLY-messages
    """

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
        self.moderationcastdb = ModerationCastDBHandler.getInstance()
        self.my_permid = self.moderationcastdb.my_permid
        self.session = session

        self.max_have_length = SINGLE_HAVE_LENGTH * session.get_moderationcast_moderations_per_have()
        self.max_request_length = SINGLE_REQUEST_LENGTH * session.get_moderationcast_moderations_per_have()
            
        #Reference to buddycast-core, set by the buddycast-core (as it is created by the
        #buddycast-factory after calling this constructor).
        self.buddycast_core = None
        
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
    def createAndSendModerationCastHaveMessage(self, target_permid, selversion):
        
        moderationcast_data = self.createModerationCastHaveMessage(target_permid)
        # ARNO50: TODO: don't send empty msgs. Need to change the arch for this.
        if len(moderationcast_data) == 0:
            if DEBUG:
                print >>sys.stderr, "There are no moderations.. hence we do not send"
            return
        moderationcast_msg = bencode(moderationcast_data)
         
        if self.log:
            dns = self.dnsindb(target_permid)
            if dns:
                ip,port = dns
                MSG_ID = "MODERATIONCAST_HAVE"
                msg = moderationCastHaveMsgToString(moderationcast_data)
                self.overlay_log('SEND_MSG', ip, port, show_permid(target_permid), selversion, MSG_ID, msg)
        
        data = MODERATIONCAST_HAVE+moderationcast_msg
        print >>sys.stderr, "Sending Moderationcast Have Msg", moderationCastHaveMsgToString(moderationcast_data)
        self.secure_overlay.send(target_permid, data, self.moderationcastSendCallback)
        
    ################################
    def createModerationCastHaveMessage(self, target_permid):
        """ Create a MODERATIONCAST_HAVE message """

        #Select latest own moderations
        size = self.session.get_moderationcast_recent_own_moderations_per_have()
        info = self.moderationcastdb.recentOwnModerations(size)
        
        #Add random own moderations
        size += self.session.get_moderationcast_random_own_moderations_per_have()
        random_own = self.moderationcastdb.randomOwnModerations(size)
        #print >> sys.stderr, "random own >>>>>>>>>>> ", random_own
        
        for infohash in random_own:
            if len(info) == size:
                break
             
            if infohash not in info:
                info.append(infohash)

        
        #Add latest moderations to forward
        size += self.session.get_moderationcast_recent_forward_moderations_per_have()
        recent_forward = self.moderationcastdb.recentModerations(size)
        #print >> sys.stderr, "recent forward >>>>>>>>>>> ", recent_forward
        for infohash in recent_forward:
            if len(info) == size:
                break
            if infohash not in info:
                info.append(infohash)
        
        #Add random moderations to forward
        size += self.session.get_moderationcast_random_forward_moderations_per_have()
        random_forward = self.moderationcastdb.randomModerations(size)
        #print >> sys.stderr, "random forward >>>>>>>>>>> ", random_forward
        for infohash in random_forward:
            if len(info) == size:
                break
            if infohash not in info:
                info.append(infohash)
        
        data = []
        #Gather timestamp and size
        for infohash in info:
            #print >> sys.stderr, "what exactly do we send",infohash
            hash = infohash[2]
            time = infohash[3]
            data.append((hash, time))

        if DEBUG:
            print >>sys.stderr, "moderationcast: Prepared", len(data), "moderations"

        return data

    ################################
    def createAndSendModerationCastRequestMessage(self, target_permid, have_message, selversion):
        # for older versions of Tribler (non-ModerationCast): do nothing
        #if selversion < MIN_VERSION:
            #return

        # create a new MODERATIONCAST_REQUEST message
        moderationcast_data = self.createModerationCastRequestMessage(target_permid, have_message)

        try:
            moderationcast_msg = bencode(moderationcast_data)
        except:
            if DEBUG:

                print_exc()
                print >> sys.stderr, "error moderationcast_data:", moderationcast_data
            return
        
        #Log SEND_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(target_permid)
            if dns:
                ip,port = dns
                MSG_ID = "MODERATIONCAST_REQUEST"
                msg = moderationCastRequestMsgToString(moderationcast_data)
                self.overlay_log('SEND_MSG', ip, port, show_permid(target_permid), selversion, MSG_ID, msg)
        
        #if REQUEST_COMPRESSION:
            #Compress this message
            #moderationcast_msg = compress(moderationcast_msg)
            
        print >>sys.stderr, "Sending Moderationcast Request Msg", moderationCastRequestMsgToString(moderationcast_data)
        # send the message
        data = MODERATIONCAST_REQUEST+moderationcast_msg
        #print >>sys.stderr,"the moderation cast request is", data
        #print >>sys.stderr,"the moderation cast request decoded is", bdecode(data)
        #self.uploadLimiter.use(len(data))            #Log upload-bandwidth usage
        #return
        self.secure_overlay.send(target_permid, data, self.moderationcastSendCallback)

    ################################
    def createModerationCastRequestMessage(self, target_permid, have_message):
        """ Create a MODERATIONCAST_REQUEST message """

        #Select request set, such that it will not exceed download-bandwidth-limit and
        #only select moderations for which we have the torrent and not have a newer moderation
        #limit_bytes = self.downloadLimiter.getAvailableSize()
        
        requests = []
        requests_size = 0
        for (infohash, timestamp) in have_message:
            if self.moderationcastdb.hasModeration(infohash): 
                moderation = self.moderationcastdb.getModeration(infohash)
                if moderation[3] < timestamp:
                    requests.append(infohash)
            else:
                requests.append(infohash)
            
            
                
        return requests

    ################################
    def createAndSendModerationCastReplyMessage(self, target_permid, request_message, selversion):
        # for older versions of Tribler (non-ModerationCast): do nothing
        #if selversion < MIN_VERSION:
            #return


        # create a new MODERATIONCAST_REQUEST message
        moderationcast_data = self.createModerationCastReplyMessage(target_permid, request_message)

        try:
            moderationcast_msg = bencode(moderationcast_data)
        except:
            if DEBUG:

                print_exc()
                print >> sys.stderr, "error moderationcast_data:", moderationcast_data
            return
        
        #Log SEND_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(target_permid)
            if dns:
                ip,port = dns
                MSG_ID = "MODERATIONCAST_REPLY"
                msg = moderationCastReplyMsgToString(moderationcast_data)
                self.overlay_log('SEND_MSG', ip, port, show_permid(target_permid), selversion, MSG_ID, msg)
        
        #if REPLY_COMPRESSION:
            #Compress this message
            #moderationcast_msg = compress(moderationcast_msg)
        print >>sys.stderr, "Sending Moderationcast Reply Msg", moderationCastReplyMsgToString(moderationcast_data)
        # send the message
        data = MODERATIONCAST_REPLY+moderationcast_msg
        self.secure_overlay.send(target_permid, data, self.moderationcastSendCallback)

    ################################
    def createModerationCastReplyMessage(self, target_permid, request_message):
        """ Create a MODERATIONCAST_REPLY message """

        #Select reply set, such that it will not exceed upload-bandwidth-limit:
        #limit_bytes = self.uploadLimiter.getAvailableSize()
        reply = []
        reply_size = 0
        
        for infohash in request_message:
            mod = self.moderationcastdb.getModeration(infohash)
            moderation = {}
            moderation['mod_id'] = mod[0]
            moderation['mod_name'] = mod[1] 
            moderation['infohash'] = mod[2]
            moderation['time_stamp'] = mod[3]
            moderation['signature'] = mod[7]
            
            reply.append(moderation)

        return reply

    ################################
    def moderationcastSendCallback(self, exc, target_permid, other=0):
        if exc is None:
            if DEBUG:

                print >> sys.stderr,"moderationcast: *** msg was sent successfully to peer", permid_for_user(target_permid)
        else:
            if DEBUG:

                print >> sys.stderr, "moderationcast: *** warning - error in sending msg to", permid_for_user(target_permid), exc

    ################################
    def gotModerationCastHaveMessage(self, recv_msg, sender_permid, selversion):

        if DEBUG:
            print >>sys.stderr,'moderationcast: Received a HAVE msg from ', permid_for_user(sender_permid)

        if not sender_permid or sender_permid == self.my_permid:
            return False

        if self.max_have_length > 0 and len(recv_msg) > self.max_have_length:
            return False
        
        #check if this moderator is a fraud
        mod = self.moderationcastdb.getModerator(permid_for_user(sender_permid))
        if mod is not None and len(mod)>0:
            if mod[1]==-1:
                print >>sys.stderr, "Sorry this moderator is a fraud one:", permid_for_user(sender_permid)
                return False
            else:
                print >>sys.stderr, "This moderator is not a fraud one:", permid_for_user(sender_permid)
        else:
            print >>sys.stderr, "Never seen this moderator :", permid_for_user(sender_permid)

        moderationcast_data = {}

        try:
            moderationcast_data = bdecode(recv_msg)
        except:
            if DEBUG:
                print >> sys.stderr, "moderationcast: warning, invalid bencoded data"
            return False

        #print >> sys.stderr, "received this thing from the test", moderationcast_data
        # check message-structure
        if not validModerationCastHaveMsg(moderationcast_data):
            if DEBUG:
                print >> sys.stderr, "moderationcast: invalid MODERATIONCAST_HAVE-message"
            return False

        if DEBUG:
            print "Received MODERATIONCAST_HAVE", moderationCastHaveMsgToString(moderationcast_data)

        #Log RECV_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(sender_permid)
            if dns:
                ip,port = dns
                MSG_ID = "MODERATIONCAST_HAVE"
                msg = moderationCastHaveMsgToString(moderationcast_data)
                self.overlay_log('RECV_MSG', ip, port, show_permid(sender_permid), selversion, MSG_ID, msg)
  
        #Reply have-message, with request message
        self.createAndSendModerationCastRequestMessage(sender_permid, moderationcast_data, selversion)
        
        return True

    ################################
    def gotModerationCastRequestMessage(self, recv_msg, sender_permid, selversion):
        """ Received a MODERATIONCAST_REQUEST message and handle it. Reply if needed """
        if DEBUG:
            print >>sys.stderr,'moderationcast: Received a REQUEST msg from ', permid_for_user(sender_permid)

        #Log download-bandwidth-usage
        #self.downloadLimiter.use(len(recv_msg))

        #if REQUEST_COMPRESSION:
            #Decompress this message, before handling further
            #recv_msg = decompress(recv_msg)
            
        if not sender_permid or sender_permid == self.my_permid:
            return False

        if self.max_request_length > 0 and len(recv_msg) > self.max_request_length:
            return False

        moderationcast_data = {}

        try:
            moderationcast_data = bdecode(recv_msg)
        except:
            if DEBUG:
                print >> sys.stderr, "moderationcast: warning, invalid bencoded data"
            return False

        # check message-structure
        if not validModerationCastRequestMsg(moderationcast_data):
            if DEBUG:
                print >> sys.stderr, "moderationcast: invalid MODERATIONCAST_REQUEST-message"
            return False

        if DEBUG:
            print "Received MODERATIONCAST_REQUEST", moderationCastRequestMsgToString(moderationcast_data)

        #Log RECV_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(sender_permid)
            if dns:
                ip,port = dns
                MSG_ID = "MODERATIONCAST_REQUEST"
                msg = moderationCastRequestMsgToString(moderationcast_data)
                self.overlay_log('RECV_MSG', ip, port, show_permid(sender_permid), selversion, MSG_ID, msg)

        self.createAndSendModerationCastReplyMessage(sender_permid, moderationcast_data, selversion)    
        
        return True

    ################################
    def gotModerationCastReplyMessage(self, recv_msg, sender_permid, selversion):
        """ Received a MODERATIONCAST_REPLY message and handle it."""

        #Log download-bandwidth-usage
        #self.downloadLimiter.use(len(recv_msg))
        if not sender_permid or sender_permid == self.my_permid:
            return False

        if MAX_REPLY_LENGTH > 0 and len(recv_msg) > MAX_REPLY_LENGTH:
            return False

        moderationcast_data = {}

        try:
            moderationcast_data = bdecode(recv_msg)
        except:
            return False

        # check message-structure
        if not validModerationCastReplyMsg(moderationcast_data):
            print >>sys.stderr, "Received Invalid Moderationcast Reply Message"
            return False

        if DEBUG:
            print >>sys.stderr, "Received MODERATIONCAST_REPLY", moderationCastReplyMsgToString(moderationcast_data)

        #Log RECV_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(sender_permid)
            if dns:
                ip,port = dns
                MSG_ID = "MODERATIONCAST_REPLY"
                msg = moderationCastReplyMsgToString(moderationcast_data)
                self.overlay_log('RECV_MSG', ip, port, show_permid(sender_permid), selversion, MSG_ID, msg)

        #Handle moderationcast-have-message:
        self.handleModerationCastReplyMsg(sender_permid, moderationcast_data)
        
        return True
    
    ################################
    def handleModerationCastReplyMsg(self, sender_permid, data):
        
        if DEBUG:
            print "Processing MODERATIONCAST_REPLY msg from: ", permid_for_user(sender_permid)
        
        for moderation in data:
            #print >> sys.stderr,"intention>>>>", moderation
            self.moderationcastdb.updateModeration(moderation)
            
        if DEBUG:
            print "Processing MODERATIONCAST_REPLY msg from: ", permid_for_user(sender_permid), "DONE"
            
    ################################
    def replyModerationCast(self, target_permid, selversion):
        """ Reply a moderationcast-have message """

        #if not self.buddycast_core.isConnected(target_permid):
            #print >> sys.stderr, 'moderationcast: lost connection while replying moderationcast', \
                #"Round", self.buddycast_core.round
            #return
        #return 
        self.createAndSendModerationCastHaveMessage(target_permid, selversion)

    ################################
    
    def showAllModerations(self):
        """ Currently this function is only for testing, to show all moderations """
        if DEBUG:
            records = self.moderationcastdb.getAll()
            print >>sys.stderr, "Existing moderations..."
            for record in records:
                print >>sys.stderr, "    modid:",record[0],"; modname:", record[1], "; infohash:",record[2],"; signature:", record[7]
            print >>sys.stderr, "End of moderations..."
            
            records = self.moderationcastdb.getAllModerators()
            print >>sys.stderr, "Existing moderators..."
            for record in records:
                print >>sys.stderr, "    modid:",record[0],"; status:", record[1], "; timestamp:",record[2]
            print >>sys.stderr, "End of moderators..."
            
