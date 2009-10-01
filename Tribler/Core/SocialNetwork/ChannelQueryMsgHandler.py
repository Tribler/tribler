import sys
from time import time, sleep
from sets import Set
from traceback import print_stack, print_exc
import datetime
import time as T

from M2Crypto import Rand

from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Core.CacheDB.CacheDBHandler import ChannelCastDBHandler,PeerDBHandler
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BuddyCast.moderationcast_util import *
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SIXTH, OLPROTO_VER_ELEVENTH
from Tribler.Core.Utilities.utilities import show_permid_short,show_permid
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.Utilities.unicode import dunno2unicode
from Tribler.Core.Search.SearchManager import SearchManager

MAX_RESULTS = 20
QUERY_ID_SIZE = 20
MAX_QUERY_REPLY_LEN = 100*1024    # 100K
MAX_PEERS_TO_QUERY = 20

DEBUG = False

class ChannelQueryMsgHandler:
    __single = None
    
    def __init__(self):
        if ChannelQueryMsgHandler.__single:
            raise RuntimeError, "ChannelQueryMsgHandler is singleton"
        ChannelQueryMsgHandler.__single = self
        
        self.connections = Set()    # only connected remote_search_peers
        self.query_ids2rec = {}    # ARNOCOMMENT: TODO: purge old entries...
        self.overlay_log = None
        self.registered = False
        self.logfile = None 
                
    def getInstance(*args, **kw):
        if ChannelQueryMsgHandler.__single is None:
            ChannelQueryMsgHandler(*args, **kw)
        return ChannelQueryMsgHandler.__single
    getInstance = staticmethod(getInstance)
    
    def register(self,overlay_bridge,launchmany,config,bc_fac):
        if DEBUG:
            print >> sys.stderr,"cquery: register"
        self.overlay_bridge = overlay_bridge
        self.launchmany= launchmany
        self.peer_db = launchmany.peer_db
        self.channelcast_db = launchmany.channelcast_db
        self.config = config
        self.bc_fac = bc_fac # May be None
        self.registered = True

    def handleMessage(self,permid,selversion,message):
        """ Handles Incoming messages """

        if not self.registered:
            return True
       
        t = message[0]
        if t == CHANNEL_QUERY:
            if DEBUG:
                print >> sys.stderr,"cquery: Got CHANNEL_QUERY",len(message)
            return self.recv_query(permid,message,selversion)
        if t == CHANNEL_QUERY_REPLY:
            if DEBUG:
                print >> sys.stderr,"cquery: Got CHANNEL_QUERY_REPLY",len(message)
            return self.recv_query_reply(permid,message,selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"cquery: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False
    
    def handleConnection(self,exc,permid,selversion,locally_initiated):
        """  Handles connections """
        if not self.registered:
            return True
        
        if DEBUG:
            print >> sys.stderr,"cquery: handleConnection",exc,"v",selversion,"local",locally_initiated
        
        if selversion < OLPROTO_VER_ELEVENTH:
            return True

        if exc is None:
            self.connections.add(permid)

        elif permid in self.connections:
            self.connections.remove(permid)

        return True
    
    def create_query(self,query,usercallback):
        d = {}
        d['q'] = query
        d['id'] = self.create_and_register_query_id(query,usercallback)
        return bencode(d)
    
    def create_and_register_query_id(self,query,usercallback):
        id = Rand.rand_bytes(QUERY_ID_SIZE)
        queryrec = {'query':query,'usercallback':usercallback}
        self.query_ids2rec[id] = queryrec
        return id    
    
    def is_registered_query_id(self,id):
        if id in self.query_ids2rec:
            return self.query_ids2rec[id]
        else:
            return None    
    
    def conn_callback(self,exc,dns,permid,selversion,message):
        if exc is None and selversion >= OLPROTO_VER_SIXTH:
            self.overlay_bridge.send(permid,message,self.send_callback)

    
    def send_callback(self,exc,permid):
        pass    
    
    def send_query(self,query,usercallback,max_peers_to_query=MAX_PEERS_TO_QUERY):
        """ Called by GUI Thread """
        if max_peers_to_query is None:
            max_peers_to_query = MAX_PEERS_TO_QUERY
        if DEBUG:
            print >>sys.stderr,"cquery: send_query",query
        if max_peers_to_query > 0:
            send_query_func = lambda:self.network_send_query_callback(query,usercallback,max_peers_to_query)
            self.overlay_bridge.add_task(send_query_func,0)

    def network_send_query_callback(self,query,usercallback,max_peers_to_query):
        """ Called by overlay thread """
        p = self.create_query(query,usercallback)
        m = CHANNEL_QUERY+p
        query_conn_callback_lambda = lambda exc,dns,permid,selversion:self.conn_callback(exc,dns,permid,selversion,m)

        peers_to_query = 0
        for permid in self.connections:
            self.overlay_bridge.connect(permid,query_conn_callback_lambda)
            peers_to_query += 1

        
        if peers_to_query < max_peers_to_query and self.bc_fac and self.bc_fac.buddycast_core:
            query_cand = self.bc_fac.buddycast_core.getRemoteSearchPeers(MAX_PEERS_TO_QUERY-peers_to_query)
            for permid in query_cand:
                print >> sys.stderr , "ch: peers_to_query" , bin2str(permid)
                if permid not in self.connections:    # don't call twice
                    self.overlay_bridge.connect(permid,query_conn_callback_lambda)
                    peers_to_query += 1
                    
        print >>sys.stderr,"Sent channel query to %d peers" % peers_to_query
         
    def recv_query(self,permid,message,selversion):
        if selversion < OLPROTO_VER_SIXTH:
            return False

        # Unpack
        try:
            d = bdecode(message[1:])
        except:
            if DEBUG:
                print >>sys.stderr,"cquery: Cannot bdecode QUERY message"
            #print_exc()
            return False
        
        if not isValidQuery(d,selversion):
            return False

        # ACCESS CONTROL, INCLUDING CHECKING IF PEER HAS NOT EXCEEDED
        # QUERY QUOTUM IS DONE in Tribler/Core/RequestPolicy.py
        #

        # Process
        self.process_query(permid, d, selversion)
        
        return True
    
    def process_query(self, permid, d, selversion):
        q = dunno2unicode(d['q'])
        hits = self.channelcast_db.searchChannels(q)
        p = self.create_query_reply(d['id'],hits)
        m = CHANNEL_QUERY_REPLY+p
        print >> sys.stderr, "ChQ_reply:", repr(m)
        self.overlay_bridge.send(permid, m, self.send_callback)
        self.inc_peer_nqueries(permid)        
    
    def create_query_reply(self,id,hits):
        d = {}
        d['id'] = id
        d['a'] = hits
        return bencode(d)
    
    def recv_query_reply(self,permid,message,selversion):
        # Unpack
        try:
            d = bdecode(message[1:])
        except:
            if DEBUG:
                print >>sys.stderr,"cquery: Cannot bdecode CHANNEL_QUERY_REPLY message"
            return False

        if not isValidQueryReply(d,selversion):
            if DEBUG:
                print >>sys.stderr,"cquery: not valid QUERY_REPLY message"
            return False
        
        # Check auth
        queryrec = self.is_registered_query_id(d['id'])
        if not queryrec:
            if DEBUG:
                print >>sys.stderr,"cquery: CHANNEL_QUERY_REPLY has unknown query ID"
            return False        
        
        # process the reply
        self.process_query_reply(permid,queryrec['query'],queryrec['usercallback'],d)
        
        return True
    
    def process_query_reply(self,permid,query,usercallback,d):
        if DEBUG:
            print >> sys.stderr, "Processing reply:", permid, query, repr(d)
        
        # TODO: usercallback needs to call an appropriate GUI function
        if len(d['a']) > 0:
            remote_query_usercallback_lambda = lambda:usercallback(permid,query,d['a'])
            self.launchmany.session.uch.perform_usercallback(remote_query_usercallback_lambda)
        elif DEBUG:
            print >>sys.stderr,"chquery: CHANNEL_QUERY_REPLY: no results found"    
    
    def inc_peer_nqueries(self, permid):
        peer = self.peer_db.getPeer(permid)
        try:
            if peer is not None:
                nqueries = peer['num_queries']
                if nqueries is None:
                    nqueries = 0
                self.peer_db.updatePeer(permid, num_queries=nqueries+1)
        except:
            print_exc()    
    
def isValidQuery(d,selversion):
    if not isinstance(d,dict):
        return False
    if not ('q' in d and 'id' in d):
        return False
    if not (isinstance(d['q'],str) and isinstance(d['id'],str)):
        return False
    if len(d['q']) == 0:
        return False
    if not d['q'].isalnum():
        return False    
    if len(d) > 2: # no other keys
        return False
    return True

def isValidQueryReply(d,selversion):
    if not isinstance(d,dict):
        if DEBUG:
            print >>sys.stderr,"ch_reply: not dict"
        return False
    if not ('a' in d and 'id' in d):
        if DEBUG:
            print >>sys.stderr,"ch_reply: a or id key missing"
        return False
    if not validChannelCastMsg(d['a']):
        if DEBUG:
            print >> sys.stderr, "ch_reply: is not valid list of ChannelCast records"
        return False
    return True
