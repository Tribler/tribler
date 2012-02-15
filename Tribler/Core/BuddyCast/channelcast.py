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
        if ChannelCastCore.__single:
            raise RuntimeError, "ChannelCastCore is singleton"
        ChannelCastCore.__single = self
        
        #Keep reference to interval-function of BuddycastFactory
        self.interval = buddycast_interval_function
        self.data_handler = data_handler
        self.dnsindb = dnsindb
        self.log = log
        self.overlay_bridge = overlay_bridge
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.votecastdb = VoteCastDBHandler.getInstance()
        self.rtorrent_handler = RemoteTorrentHandler.getInstance()
        
        self.session = session
        self.database_thread = session.lm.database_thread
        
        self.my_permid = session.get_permid()
        
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
        #self.richMetadataInterceptor = RichMetadataInterceptor(self.metadataDbHandler,self.votecastdb,
        #                                                       self.my_permid, subtitleSupport, self.peersHaveManger,
        #                                                       self.notifier)
    
    def initialized(self):
        return self.buddycast_core is not None

    def getInstance(*args, **kw):
        if ChannelCastCore.__single is None:
            ChannelCastCore(*args, **kw)
        return ChannelCastCore.__single
    getInstance = staticmethod(getInstance)
    
    def gotChannelCastMessage(self, recv_msg, sender_permid, selversion):
        """ Receive and handle a ChannelCast message """
        # ChannelCast feature starts from eleventh version; hence, do not receive from lower version peers
        # Arno, 2010-02-05: v12 uses a different on-the-wire format, ignore those.
        # Andrea: 2010-04-08: v14 can still receive v13 channelcast messages
        # Niels: 2011-02-02: Channelcast is now using dispersy, but we can still receive old messages
        
        if selversion < OLPROTO_VER_THIRTEENTH:
            if DEBUG:
                print >> sys.stderr, "channelcast: Do not receive from lower version peer:", selversion
            return True
                
        if DEBUG:
            print >> sys.stderr,'channelcast: Received a msg from ', show_permid_short(sender_permid)
            print >> sys.stderr,"channelcast: my_permid=", show_permid_short(self.my_permid)
        
        if not sender_permid or sender_permid == self.my_permid:
            if DEBUG:
                print >> sys.stderr, "channelcast: warning - got channelcastMsg from a None/Self peer", \
                        show_permid_short(sender_permid), recv_msg
            return False
       
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

        self.updateChannel(sender_permid, None, channelcast_data)
        
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

    def updateChannel(self, query_permid, query, hits, callback = None):
        """
        This function is called when there is a reply from remote peer regarding updating of a channel
        @param query_permid: the peer who returned the results
        @param query: the query string (None if this is not the results of a query) 
        @param hits: details of all matching results related to the query
        @param callback: callback function which will receive dictOfAdditions, query_permid and query
        """
        self.database_thread.register(self._updateChannelInternal, args = (query_permid, query, hits), callback_args = (query_permid, query))
        
    def _updateChannelInternal(self, query_permid, query, hits):
        dictOfAdditions = dict()

        if len(hits) > 0:
            # a single read from the db is more efficient
            all_spam_channels = self.votecastdb.getChannelsWithNegVote(None)
            permid_channel_id = self.channelcastdb.getPermChannelIdDict(binary = True)

            for k,v in hits.items():
                #create new channel if not found
                if v['publisher_id'] not in permid_channel_id:
                    permid_channel_id[v['publisher_id']] = self.channelcastdb.on_channel_from_channelcast(v['publisher_id'], v['publisher_name'])

                #add local channel_id to all messages
                v['channel_id'] = permid_channel_id[v['publisher_id']]

                #check if the record belongs to a channel who we have "reported spam" (negative vote)
                if bin2str(v['publisher_id']) in all_spam_channels:
                    # if so, ignore the incoming record
                    continue

                # make everything into "string" format, if "binary"
                hit = (v['channel_id'],v['publisher_name'],v['infohash'],v['torrentname'],v['time_stamp'])
                dictOfAdditions[k] = hit

            self._updateChannelcastDB(query_permid, query, hits, dictOfAdditions.values())

        return dictOfAdditions
    
    def _updateChannelcastDB(self, query_permid, query, hits, listOfAdditions):
        if DEBUG:
            print >> sys.stderr, "channelcast: updating channelcastdb", query, len(hits)

        channel_ids = Set()
        infohashes = Set()
        for hit in listOfAdditions:
            channel_ids.add(hit[0])
            infohashes.add(hit[2])
            
        my_favorites = self.votecastdb.getChannelsWithPosVote(None)
        if query and query.startswith('CHANNEL p') and len(channel_ids) == 1:
            channel_id = channel_ids.pop()
            channel_ids.add(channel_id)
            
            nr_torrents = self.channelcastdb.getNrTorrentsInChannel(channel_id)
            if len(infohashes) > nr_torrents:
                if len(infohashes) > 50 and len(infohashes) > nr_torrents +1: #peer not behaving according to spec, ignoring
                    if DEBUG:
                        print >> sys.stderr, "channelcast: peer not behaving according to spec, ignoring",len(infohashes), show_permid(query_permid)
                    return
                
                self.channelcastdb.deleteTorrentFromChannel(channel_id)
            if DEBUG:
                print >> sys.stderr, 'Received channelcast message with %d hashes'%len(infohashes), show_permid(query_permid)
                
            request_updates = False
        else:
            #filter listOfAdditions
            listOfAdditions = [hit for hit in listOfAdditions if hit[0] not in my_favorites]
            
            request_updates = True

        #08/04/10: Andrea: processing rich metadata part.
        #self.richMetadataInterceptor.handleRMetadata(query_permid, hits, fromQuery = query is not None)
           
        self.channelcastdb.on_torrents_from_channelcast(listOfAdditions)
        
        if request_updates:
            #request channeltimeframes for subscribed channels
            for channel_id in my_favorites:
                if channel_id in channel_ids:
                    self.updateAChannel(channel_id, [query_permid])
                    channel_ids.remove(channel_id) #filter publisher_ids
        
        missing_infohashes = {}
        for channel_id in channel_ids:
            for infohash in self.channelcastdb.selectTorrentsToCollect(channel_id):
                missing_infohashes[infohash] = channel_id
                
        def notify(channel_id):
            self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)

        for infohash, channel_id in missing_infohashes.iteritems():
            if infohash in infohashes:
                self.rtorrent_handler.download_torrent(query_permid, infohash, lambda infohash, metadata, filename: notify(channel_id) ,2)
            else:
                self.rtorrent_handler.download_torrent(query_permid, infohash, lambda infohash, metadata, filename: notify(channel_id) ,3)
    
    def updateMySubscribedChannels(self):
        def update(channel_ids, perm_ids):
            channel_id = channel_ids.pop()
            perm_id = perm_ids.pop()
            self.updateAChannel(channel_id, perm_id)
            
            if len(channel_ids) > 0:
                self.overlay_bridge.add_task(lambda: update(channel_ids, perm_ids), 20)
        
        self.overlay_bridge.add_task(self.updateMySubscribedChannels, RELOAD_FREQUENCY)
        
        def db_call():
            subscribed_channels = self.channelcastdb.getMySubscribedChannels()
            channel_ids = [values[0] for values in subscribed_channels if values[2] == -1]
            if len(channel_ids) > 0:
                perm_ids = self.channelcastdb.getPermidForChannels(channel_ids)
                update(channel_ids, perm_ids)
                
        self.database_thread.register(db_call)
    
    def updateAChannel(self, channel_id, publisher_id, peers = None, timeframe = None):
        if peers == None:
            peers = RemoteQueryMsgHandler.getInstance().get_connected_peers(OLPROTO_VER_THIRTEENTH)
        else:
            peers = list(peers)
            
        shuffle(peers)
        
        # Create separate task which does all the requesting
        self.overlay_bridge.add_task(lambda: self._sequentialQueryPeers(channel_id, publisher_id, peers, timeframe))
    
    def _sequentialQueryPeers(self, channel_id, publisher_id, peers, timeframe = None):
        def nextPeer(result, query_permid, query):
            if peers:
                dorequest()
        
        def seqtimeout(permid):
            #actual timeout, or did response arrive
            if peers and permid == peers[0][0]:
                peers.pop(0)
                dorequest()
                
        def seqcallback(query_permid, query, hits):
            #did timeout already occur?
            if peers and query_permid == peers[0][0]:
                peers.pop(0)
                self.updateChannel(query_permid, query, hits, nextPeer)
            else:
                self.updateChannel(query_permid, query, hits)      
            
        def dorequest():
            if peers:
                if len(peers[0]) == 2:
                    permid, selversion = peers[0]
                else:
                    permid = peers[0]
                    selversion = OLPROTO_VER_THIRTEENTH
                
                q = "CHANNEL p "+publisher_id
                
                if timeframe or not channel_id:
                    record = timeframe
                else:
                    record = self.channelcastdb.getTimeframeForChannel(channel_id)
                
                if record:
                    q+= " "+" ".join(map(str,record))

                self.session.query_peers(q,[permid],usercallback = seqcallback)
                self.overlay_bridge.add_task(lambda: seqtimeout(permid), 30)
        
        peers = peers[:]
        dorequest()
