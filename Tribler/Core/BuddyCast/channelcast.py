# Written by Nitin Chiluka
# see LICENSE.txt for license information

import sys
import threading
from time import time, ctime, sleep
from zlib import compress, decompress
from binascii import hexlify
from traceback import print_exc, print_stack
from types import StringType, ListType, DictType
from random import randint, sample, seed, random, shuffle
from sha import sha
from sets import Set

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.BitTornado.BT1.MessageID import CHANNELCAST, BUDDYCAST
from Tribler.Core.CacheDB.CacheDBHandler import ChannelCastDBHandler, VoteCastDBHandler
from Tribler.Core.Utilities.unicode import str2unicode
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Overlay.permid import permid_for_user,sign_data,verify_data
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.SocialNetwork.RemoteQueryMsgHandler import RemoteQueryMsgHandler
from Tribler.Core.BuddyCast.moderationcast_util import *
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_THIRTEENTH,\
    OLPROTO_VER_FOURTEENTH
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_UPDATE
from Tribler.Core.Subtitles.RichMetadataInterceptor import RichMetadataInterceptor
from Tribler.Core.CacheDB.MetadataDBHandler import MetadataDBHandler
from Tribler.Core.Subtitles.PeerHaveManager import PeersHaveManager
from Tribler.Core.Subtitles.SubtitlesSupport import SubtitlesSupport

DEBUG = False

NUM_OWN_RECENT_TORRENTS = 15
NUM_OWN_RANDOM_TORRENTS = 10
NUM_OTHERS_RECENT_TORRENTS = 15
NUM_OTHERS_RECENT_TORRENTS = 10

RELOAD_FREQUENCY = 2*60*60

class ChannelCastCore:
    __single = None
    TESTASSERVER = False # for unit testing

    def __init__(self, data_handler, overlay_bridge, session, buddycast_interval_function, log = '', dnsindb = None):
        """ Returns an instance of this class """
        #Keep reference to interval-function of BuddycastFactory
        self.interval = buddycast_interval_function
        self.data_handler = data_handler
        self.dnsindb = dnsindb
        self.log = log
        self.overlay_bridge = overlay_bridge
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.votecastdb = VoteCastDBHandler.getInstance()
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

        self.notifier = Notifier.getInstance()

        self.metadataDbHandler = MetadataDBHandler.getInstance()
        
        #subtitlesHandler = SubtitlesHandler.getInstance()
        subtitleSupport = SubtitlesSupport.getInstance()
        # better if an instance of RMDInterceptor was provided from the
        # outside
        self.peersHaveManger = PeersHaveManager.getInstance()
        if not self.peersHaveManger.isRegistered():
                self.peersHaveManger.register(self.metadataDbHandler, self.overlay_bridge)
        self.richMetadataInterceptor = RichMetadataInterceptor(self.metadataDbHandler,self.votecastdb,
                                                               self.my_permid, subtitleSupport, self.peersHaveManger,
                                                               self.notifier)
        
        

    
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
        # Arno, 2010-02-05: v12 uses a different on-the-wire format, ignore those.
        
        # Andrea, 2010-04-08: sending the "old-style" channelcast message to older
        # peers, and enriched channelcast messages to new versions, for full backward
        # compatibility
        if selversion < OLPROTO_VER_THIRTEENTH:
            if DEBUG:
                print >> sys.stderr, "channelcast: Do not send to lower version peer:", selversion
            return
        
        # 3/5/2010 Andrea: adding the destination parameters to createChannelCastMessage for
        # logging reasons only. When logging will be disabled, that parameter will
        # become useless
        channelcast_data = self.createChannelCastMessage(selversion, target_permid)
        if channelcast_data is None or len(channelcast_data)==0:
            if DEBUG:
                print >>sys.stderr, "channelcast: No channels there.. hence we do not send"
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
        self.overlay_bridge.send(target_permid, data, self.channelCastSendCallback)        
        #if DEBUG: print >> sys.stderr, "channelcast: Sent channelcastmsg",repr(channelcast_data)
    
    def createChannelCastMessage(self, selversion, dest_permid=None):
        """ 
        Create a ChannelCast Message 
        
        @param selversion: the protocol version of the destination
        @param dest_permid: the destination of the message. Actually this parameter is not really needed. If 
                            not none, it is used for logging purposes only
                            
        @return a channelcast message, possibly enrich with rich metadata content in the
                case selversion is sufficiently high
        """
        # 09-04-2010 Andrea: I addedd the selversion param, to intercept and modify
        # the ChannelCast message contents if the protocol version allows rich metadata
        # enrichment
        
        if DEBUG: 
            print >> sys.stderr, "channelcast: Creating channelcastmsg..."
        
        hits = self.channelcastdb.getRecentAndRandomTorrents(NUM_OWN_RECENT_TORRENTS,NUM_OWN_RANDOM_TORRENTS,NUM_OTHERS_RECENT_TORRENTS,NUM_OTHERS_RECENT_TORRENTS)
        # 3/5/2010 Andrea:  
        # hits is of the form: [(mod_id, mod_name, infohash, torrenthash, torrent_name, time_stamp, signature)]
        # adding the destination parameter to buildChannelcastMessageFrom Hits for
        # logging reasons only. When logging will be disabled, that parameter will
        # become useless
        d = self.buildChannelcastMessageFromHits(hits, selversion, dest_permid)
#        #assert validChannelCastMsg(d)
        return d
    
    def channelCastSendCallback(self, exc, target_permid, other=0):
        if DEBUG:
            if exc is None:
                print >> sys.stderr,"channelcast: *** msg was sent successfully to peer", show_permid_short(target_permid)
            else:
                print >> sys.stderr, "channelcast: *** warning - error in sending msg to", show_permid_short(target_permid), exc
 
    def gotChannelCastMessage(self, recv_msg, sender_permid, selversion):
        """ Receive and handle a ChannelCast message """
        # ChannelCast feature starts from eleventh version; hence, do not receive from lower version peers
        # Arno, 2010-02-05: v12 uses a different on-the-wire format, ignore those.
        
        # Andrea: 2010-04-08: v14 can still receive v13 channelcast messages
        if selversion < OLPROTO_VER_THIRTEENTH:
            if DEBUG:
                print >> sys.stderr, "channelcast: Do not receive from lower version peer:", selversion
            return True
                
        if DEBUG:
            print >> sys.stderr,'channelcast: Received a msg from ', show_permid_short(sender_permid)
            print >> sys.stderr,"channelcast: my_permid=", show_permid_short(self.my_permid)

        """
        We want to receive our own channelcast messages, to fix our illegal timeframes
        if not sender_permid or sender_permid == self.my_permid:
            if DEBUG:
                print >> sys.stderr, "channelcast: warning - got channelcastMsg from a None/Self peer", \
                        show_permid_short(sender_permid), recv_msg
            return False
        """
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

        # 19/02/10 Boudewijn: validChannelCastMsg passes when
        # PUBLISHER_NAME and TORRENTNAME are either string or
        # unicode-string.  However, all further code requires that
        # these are unicode!
        for ch in channelcast_data.values():
            if isinstance(ch["publisher_name"], str):
                ch["publisher_name"] = str2unicode(ch["publisher_name"])
            if isinstance(ch["torrentname"], str):
                ch["torrentname"] = str2unicode(ch["torrentname"])

        self.handleChannelCastMsg(sender_permid, channelcast_data)
        
        #Log RECV_MSG of uncompressed message
        if self.log:
            dns = self.dnsindb(sender_permid)
            if dns:
                ip,port = dns
                MSG_ID = "CHANNELCAST"
                # 08/04/10 Andrea: representing the whole channelcast  + metadata message
                msg = repr(channelcast_data)
                self.overlay_log('RECV_MSG', ip, port, show_permid(sender_permid), selversion, MSG_ID, msg)
 
        if self.TESTASSERVER:
            self.createAndSendChannelCastMessage(sender_permid, selversion)
            
        return True       

    def handleChannelCastMsg(self, sender_permid, data):
        self._updateChannelInternal(sender_permid, None, data)

    def updateChannel(self,query_permid, query, hits):
        """
        This function is called when there is a reply from remote peer regarding updating of a channel
        @param query_permid: the peer who returned the results
        @param query: the query string (None if this is not the results of a query) 
        @param hits: details of all matching results related to the query
        """
        if DEBUG:
            print >> sys.stderr, "channelcast: sending message to", bin2str(query_permid), query, len(hits)
        return self._updateChannelInternal(query_permid, query, hits)
        
    def _updateChannelInternal(self, query_permid, query, hits):
        listOfAdditions = list()
        
        # a single read from the db is more efficient
        all_spam_channels = self.votecastdb.getPublishersWithNegVote(bin2str(self.session.get_permid()))
        for k,v in hits.items():
            #check if the record belongs to a channel who we have "reported spam" (negative vote)
            if bin2str(v['publisher_id']) in all_spam_channels:
                # if so, ignore the incoming record
                continue
            
            #Nitin: Check if the record belongs to my channel 
            if bin2str(v['publisher_id']) == bin2str(self.session.get_permid()):
                # if so, ignore the incoming record
                continue
            
            # make everything into "string" format, if "binary"
            hit = (bin2str(v['publisher_id']),v['publisher_name'],bin2str(v['infohash']),bin2str(v['torrenthash']),v['torrentname'],v['time_stamp'],bin2str(k))
            
            listOfAdditions.append(hit)
        
        # Arno, 2010-06-11: We're on the OverlayThread
        self._updateChannelcastDB(query_permid, query, hits, listOfAdditions)
        return listOfAdditions
    
    def _updateChannelcastDB(self, query_permid, query, hits, listOfAdditions):
        publisher_ids = Set()
        infohashes = Set()
        for hit in listOfAdditions:
            publisher_ids.add(hit[0])
            infohashes.add(str2bin(hit[2]))
            
        if query and query.startswith('CHANNEL p') and len(publisher_ids) == 1:
            publisher_id = publisher_ids.pop()
            publisher_ids.add(publisher_id)
            
            nr_torrents = self.channelcastdb.getNrTorrentsInChannel(publisher_id)
            if len(infohashes) > nr_torrents:
                if len(infohashes) > 50 and len(infohashes) > nr_torrents +1: #peer not behaving according to spec, ignoring
                    #print >> sys.stderr, "channelcast: peer not behaving according to spec, ignoring",len(infohashes), show_permid(query_permid)
                    return
                self.channelcastdb.deleteTorrentsFromPublisherId(str2bin(publisher_id))
            #print >> sys.stderr, 'Received channelcast message with %d hashes'%len(infohashes), show_permid(query_permid)
        else:
            #ignore all my favorites, randomness will cause problems with timeframe
            my_favorites = self.votecastdb.getPublishersWithPosVote(bin2str(self.session.get_permid()))
            listOfAdditions = [hit for hit in listOfAdditions if hit[0] not in my_favorites]
        
        #08/04/10: Andrea: processing rich metadata part.
        self.richMetadataInterceptor.handleRMetadata(query_permid, hits, fromQuery = query is not None)
        
        self.channelcastdb.addTorrents(listOfAdditions)
        missing_infohashes = {}
        for publisher_id in publisher_ids:
            for infohash in self.channelcastdb.selectTorrentsToCollect(publisher_id):
                missing_infohashes[str2bin(infohash[0])] = publisher_id
                
        def notify(publisher_id):
            self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, publisher_id)

        for infohash in infohashes:
            if infohash in missing_infohashes:
                self.rtorrent_handler.download_torrent(query_permid, infohash, lambda infohash, metadata, filename: notify(missing_infohashes[infohash]) ,2)
        
        for infohash, publisher_id in missing_infohashes.iteritems():
            if infohash not in infohashes:
                self.rtorrent_handler.download_torrent(query_permid, infohash, lambda infohash, metadata, filename: notify(publisher_id) ,3)
    
    def updateMySubscribedChannels(self):
        subscribed_channels = self.channelcastdb.getMySubscribedChannels()
        for permid, channel_name, _, num_subscriptions, _ in subscribed_channels:
            self.updateAChannel(permid)
        
        self.overlay_bridge.add_task(self.updateMySubscribedChannels, RELOAD_FREQUENCY)    
    
    def updateAChannel(self, publisher_id, peers = None):
        if peers == None:
            peers = RemoteQueryMsgHandler.getInstance().get_connected_peers(OLPROTO_VER_FOURTEENTH)
        else:
            #use the specified peers list, small problem we dont have the selversion
            #use oversion 14, eventually RemoteQueryMsgHandler will convert the query for oversion13 peers
            peers = [(permid, OLPROTO_VER_FOURTEENTH) for permid in peers]
            
        shuffle(peers)
        # Create separate thread which does all the requesting
        self.overlay_bridge.add_task(lambda: self._sequentialQueryPeers(publisher_id, peers))
    
    def _sequentialQueryPeers(self, publisher_id, peers):
        def seqtimeout(permid):
            if peers and permid == peers[0][0]:
                peers.pop(0)
                dorequest()
                
        def seqcallback(query_permid, query, hits):
            self.updateChannel(query_permid, query, hits)
            
            if peers and query_permid == peers[0][0]:
                peers.pop(0)
                dorequest()
            
        def dorequest():
            if peers:
                permid, selversion = peers[0]
                
                q = "CHANNEL p "+publisher_id
                record = self.channelcastdb.getTimeframeForChannel(publisher_id)
                if record:
                    q+= " "+" ".join(map(str,record))
                self.session.query_peers(q,[permid],usercallback = seqcallback)
                self.overlay_bridge.add_task(lambda: seqtimeout(permid), 30)
        
        peers = peers[:]
        dorequest()

    def buildChannelcastMessageFromHits(self, hits, selversion, dest_permid=None, fromQuery=False):
        '''
        Creates a channelcast message from database hits.
        
        This method is used to create channel results both when a channelcast message
        is created in the "normal" buddycast epidemic protocol, and when a remote
        query for channels arrives and is processed. It substitutes a lot of duplicated
        code in the old versions.
        
        @param hits: a tuple (publisher_id, publisher_name, infohash, 
                     torrenthash, torrentname, time_stamp, signature) representing
                     a channelcast entry in the db
        @param selversion: the protocol version of the destination
        @param dest_permid: the permid of the destination of the message. Actually this parameter
                            is used for logging purposes only, when not None. If None, nothing
                            bad happens.
        '''
        # 09-04-2010 Andrea : I introduced this separate method because this code was 
        # duplicated in RemoteQueryMessageHandler
        enrichWithMetadata = False
        
        if selversion >= OLPROTO_VER_FOURTEENTH:
            enrichWithMetadata = True
            if DEBUG:
                print >> sys.stderr, "channelcast: creating enriched messages"\
                    "since peer has version: ", selversion
        d = {}
        for hit in hits:
            # ARNOUNICODE: temp fixes until data is sent not Base64-encoded
             
            # 08/04/10 Andrea: I substituted the keys with constnats, otherwise a change here
            # would break my code in the RichMetadataInterceptor
            r = {}
            r['publisher_id'] = str(hit[0]) # ARNOUNICODE: must be str
            r['publisher_name'] = hit[1].encode("UTF-8")  # ARNOUNICODE: must be explicitly UTF-8 encoded
            r['infohash'] = str(hit[2])     # ARNOUNICODE: must be str
            r['torrenthash'] = str(hit[3])  # ARNOUNICODE: must be str
            r['torrentname'] = hit[4].encode("UTF-8") # ARNOUNICODE: must be explicitly UTF-8 encoded
            r['time_stamp'] = int(hit[5])
            # hit[6]: signature, which is unique for any torrent published by a user
            signature = hit[6]
            d[signature] = r
            

        # 08/04/10 Andrea: intercepting a channelcast message and enriching it with
        # subtitles information
        # 3/5/2010 Andrea: adding the destination parameter to addRichMetadataContent for
        # logging reasons only. When logging will be disabled, that parameter will
        # become useless
        if enrichWithMetadata:
            d = self.richMetadataInterceptor.addRichMetadataContent(d, dest_permid, fromQuery)
    
        return d
    
        
