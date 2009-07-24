import sys
from time import time, ctime, sleep
from zlib import compress, decompress
from base64 import decodestring
from binascii import hexlify
from traceback import print_exc, print_stack
from types import StringType, ListType, DictType
from random import randint, sample, seed, random
from sha import sha

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.BitTornado.BT1.MessageID import CHANNELCAST
from Tribler.Core.CacheDB.CacheDBHandler import ChannelCastDBHandler
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Overlay.permid import permid_for_user,sign_data,verify_data
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.SocialNetwork.ChannelQueryMsgHandler import ChannelQueryMsgHandler
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
#from Tribler.Core.BuddyCast.moderationcast_util import *

DEBUG = True

NUM_OWN_RECENT_TORRENTS = 15
NUM_OWN_RANDOM_TORRENTS = 10
NUM_OTHERS_RECENT_TORRENTS = 15
NUM_OTHERS_RECENT_TORRENTS = 10

class ChannelCastCore:
    def __init__(self, data_handler, secure_overlay, session, buddycast_interval_function, log = '', dnsindb = None):
        """ Returns an instance of this class """
        #Keep reference to interval-function of BuddycastFactory
        self.interval = buddycast_interval_function
        self.data_handler = data_handler
        self.dnsindb = dnsindb
        self.log = log
        self.secure_overlay = secure_overlay
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.rtorrent_handler = RemoteTorrentHandler.getInstance()
        self.my_permid = self.channelcastdb.my_permid
        self.session = session
        
        self.network_delay = 30
        #Reference to buddycast-core, set by the buddycast-core (as it is created by the
        #buddycast-factory after calling this constructor).
        self.buddycast_core = None
        
        #Extend logging with ChannelCast-messages and status
        if self.log:
            self.overlay_log = OverlayLogger.getInstance(self.log)
            self.dnsindb = self.data_handler.get_dns_from_peerdb
    
    def initialized(self):
        return self.buddycast_core is not None
    
    def createAndSendChannelCastMessage(self, target_permid, selversion):
        """ Create and send a ChannelCast Message """
        channelcast_data = self.createChannelCastMessage()
        if channelcast_data is None or len(channelcast_data)==0:
            if DEBUG:
                print >>sys.stderr, "No channels there.. hence we do not send"
            #self.session.chquery_connected_peers('k:MFIwEAYHKoZIzj0CAQYFK4EEABoDPgAEAf3BkHsZ6UdIpuIX441wjU5Ybe0HPjTDvS+iacFZABH20It9N9uwkwtpkS3uEvVvfcTX50jcFNXOSCwq')            
            return
        
        channelcast_msg = bencode(channelcast_data)
        
        if self.log:
            dns = self.dnsindb(target_permid)
            if dns:
                ip,port = dns
                MSG_ID = "CHANNELCAST"
                msg = repr(channelcast_data)
                self.overlay_log('SEND_MSG', ip, port, show_permid(target_permid), selversion, MSG_ID, msg)
        
        
        if DEBUG: print >> sys.stderr, "Sending channelcastmsg",repr(channelcast_data) 
        data = CHANNELCAST+channelcast_msg
        self.secure_overlay.send(target_permid, data, self.channelCastSendCallback)        
        
    
    def createChannelCastMessage(self):
        """ Create a ChannelCast Message """
        
        if DEBUG: 
            print >> sys.stderr, "Creating channelcastmsg..."
        
        records = self.channelcastdb.getRecentAndRandomTorrents(NUM_OWN_RECENT_TORRENTS,NUM_OWN_RANDOM_TORRENTS,NUM_OTHERS_RECENT_TORRENTS,NUM_OTHERS_RECENT_TORRENTS)
        # records is of the form: [(mod_id, mod_name, infohash, torrenthash, torrent_name, time_stamp, signature)]
        return records
    
    def channelCastSendCallback(self, exc, target_permid, other=0):
        if DEBUG:
            if exc is None:
                print >> sys.stderr,"channelcast: *** msg was sent successfully to peer", permid_for_user(target_permid)
            else:
                print >> sys.stderr, "channelcast: *** warning - error in sending msg to", permid_for_user(target_permid), exc
 
    def gotChannelCastMessage(self, recv_msg, sender_permid, selversion):
        """ Receive and handle a ChannelCast message """
        if DEBUG:
            print >> sys.stderr,'channelcast: Received a msg from ', permid_for_user(sender_permid)
            print >> sys.stderr," my_permid=", permid_for_user(self.my_permid)

        if not sender_permid or sender_permid == self.my_permid:
            if DEBUG:
                print >> sys.stderr, "channelcast: warning - got channelcastMsg from a None/Self peer", \
                        permid_for_user(sender_permid), recv_msg
            return False

        #if len(recv_msg) > self.max_length:
        #    if DEBUG:
        #        print >> sys.stderr, "channelcast: warning - got large channelCastHaveMsg", len(recv_msg)
        #    return False

        channelcast_data = {}

        try:
            channelcast_data = bdecode(recv_msg)
        except:
            print >> sys.stderr, "channelcast: warning, invalid bencoded data"
            return False

        # check message-structure
        if not validChannelCastMsg(channelcast_data):
            print >> sys.stderr, "channelcast: invalid channelcast_message"
            return False
        
        self.handleChannelCastMsg(sender_permid, channelcast_data)
        
        #Log RECV_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(sender_permid)
            if dns:
                ip,port = dns
                MSG_ID = "CHANNELCAST"
                msg = repr(channelcast_data)
                self.overlay_log('RECV_MSG', ip, port, show_permid(sender_permid), selversion, MSG_ID, msg)
 
        return True       

    def handleChannelCastMsg(self, sender_permid, data):
        if DEBUG:
            print >> sys.stderr, "Processing CHANNELCAST msg from: ", permid_for_user(sender_permid)
            print >> sys.stderr, "data: ", repr(data)
            
        for record in data:
            l = (record[0],record[2], record[3], record[5])
            result = verify_data(bencode(l),str2bin(record[0]),str2bin(record[6]))
            if result:
                if self.channelcastdb.addTorrent(record):
                    print >>sys.stderr, "torrent record is successfully added into ChannelCastDB"
                    if not self.channelcastdb.existsTorrent(record[2]):
                        print >>sys.stderr, "Downloading the torrent"
                        self.rtorrent_handler.download_torrent(sender_permid,str2bin(record[2]),usercallback)
                else:
                    print >>sys.stderr, "Torrent already exists.. so need not download it"

        if DEBUG:
            print >> sys.stderr, "Processed CHANNELCAST msg from: ", permid_for_user(sender_permid)

def usercallback(infohash,metadata,filename):
    pass


def validChannelCastMsg(channelcast_data):
    if not isinstance(channelcast_data,list):
        return False
    for ch in channelcast_data:
        if len(ch) != 7:
            return False
    return True