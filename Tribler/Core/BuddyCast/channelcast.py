# Written by Nitin Chiluka
# see LICENSE.txt for license information

import sys
from time import time, ctime, sleep
from zlib import compress, decompress
from base64 import decodestring, encodestring
from binascii import hexlify
from traceback import print_exc, print_stack
from types import StringType, ListType, DictType
from random import randint, sample, seed, random
from sha import sha

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.BitTornado.BT1.MessageID import CHANNELCAST, BUDDYCAST
from Tribler.Core.CacheDB.CacheDBHandler import ChannelCastDBHandler
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Overlay.permid import permid_for_user,sign_data,verify_data
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.BuddyCast.moderationcast_util import *
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_ELEVENTH

DEBUG = False

NUM_OWN_RECENT_TORRENTS = 15
NUM_OWN_RANDOM_TORRENTS = 10
NUM_OTHERS_RECENT_TORRENTS = 15
NUM_OTHERS_RECENT_TORRENTS = 10

RELOAD_FREQUENCY = 2*60*60

class ChannelCastCore:
    __single = None

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
        self.hits = []
        self.hit = {}

    
    def initialized(self):
        return self.buddycast_core is not None
 


    def getInstance(*args, **kw):
        if ChannelCastCore.__single is None:
            ChannelCastCore(*args, **kw)
        return ChannelCastCore.__single
    getInstance = staticmethod(getInstance)

   
    def createAndSendChannelCastMessage(self, target_permid, selversion):
        """ Create and send a ChannelCast Message """
        # ChannelCast feature starts from eleventh version; hence, do not send to lower version peers
        if selversion < OLPROTO_VER_ELEVENTH:
            if DEBUG:
                print >> sys.stderr, "Do not send to lower version peer:", selversion
            return
        
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
        
        data = CHANNELCAST + channelcast_msg
        self.secure_overlay.send(target_permid, data, self.channelCastSendCallback)        
        if DEBUG: print >> sys.stderr, "Sent channelcastmsg",repr(channelcast_msg)
    
    def createChannelCastMessage(self):
        """ Create a ChannelCast Message """
        
        if DEBUG: 
            print >> sys.stderr, "Creating channelcastmsg..."
        
        hits = self.channelcastdb.getRecentAndRandomTorrents(NUM_OWN_RECENT_TORRENTS,NUM_OWN_RANDOM_TORRENTS,NUM_OTHERS_RECENT_TORRENTS,NUM_OTHERS_RECENT_TORRENTS)
        # hits is of the form: [(mod_id, mod_name, infohash, torrenthash, torrent_name, time_stamp, signature)]
        d = {}
        for hit in hits:
            r = {}
            r['publisher_id'] = hit[0]
            r['publisher_name'] = hit[1]
            r['infohash'] = hit[2]
            r['torrenthash'] = hit[3]
            r['torrentname'] = hit[4]
            r['time_stamp'] = int(hit[5])
            # hit[6]: signature, which is unique for any torrent published by a user
            signature = hit[6].encode('ascii','ignore')
            d[signature] = r
        #assert validChannelCastMsg(d)
        return d
    
    def channelCastSendCallback(self, exc, target_permid, other=0):
        if DEBUG:
            if exc is None:
                print >> sys.stderr,"channelcast: *** msg was sent successfully to peer", permid_for_user(target_permid)
            else:
                print >> sys.stderr, "channelcast: *** warning - error in sending msg to", permid_for_user(target_permid), exc
 
    def gotChannelCastMessage(self, recv_msg, sender_permid, selversion):
        """ Receive and handle a ChannelCast message """
        # ChannelCast feature starts from eleventh version; hence, do not receive from lower version peers
        if selversion < OLPROTO_VER_ELEVENTH:
            if DEBUG:
                print >> sys.stderr, "Do not receive from lower version peer:", selversion
            return
                
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
        self.updateChannel(sender_permid, None, data)

    def updateChannel(self,query_permid, query, hits):
        """
        This function is called when there is a reply from remote peer regarding updating of a channel
        @param query_permid: the peer who returned the results
        @param query: the query string
        @param hits: details of all matching results related to the query  
        """
        #print >> sys.stderr , "RECEIVED HITS : " , hits
        records = []
        for k,v in hits.items():
            records.append((v['publisher_id'],v['publisher_name'],v['infohash'],v['torrenthash'],v['torrentname'],v['time_stamp'],k))
        for hit in records:
            print >> sys.stderr, "-----------------------------------------------------"
            print >> sys.stderr, hit
            if self.channelcastdb.existsTorrent(hit[2]):
                if self.channelcastdb.addTorrent(hit):
                    self.hits.append(hit)
            else:
#                def usercallback(infohash,metadata,filename):
#                    print >> sys.stderr , "USERCALLBACK", infohash, hit 
#                    if self.channelcastdb.addTorrent(hit):
#                        self.hits.append(hit)
                self.hit[hit[2]] = hit
                self.rtorrent_handler.download_torrent(query_permid,str2bin(hit[2]),self.usercallback)

    def usercallback(self, infohash,metadata,filename):
        hit=self.hit[bin2str(infohash)]
        print >> sys.stderr , "USERCALLBACK", infohash, hit 
        if self.channelcastdb.addTorrent(hit):
            self.hits.append(hit)

        del self.hit[bin2str(infohash)]



    def updateMySubscribedChannels(self):
        subscribed_channels = self.channelcastdb.getMySubscribedChannels(from_channelcast=True)
        for permid, channel_name, num_subscriptions, notused in subscribed_channels:
            # query the remote peers, based on permid, to update the channel content
            q = "CHANNEL p:"+permid
            self.session.query_connected_peers(q,usercallback=self.updateChannel)
        
        self.secure_overlay.add_task(self.updateMySubscribedChannels, RELOAD_FREQUENCY)        
