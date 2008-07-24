# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information
#
# Send free-form queries to all the peers you are connected to.
#
# TODO: make sure we return also items from download history, but need to verify if 
# their status is still checked.
#
#

import sys
from time import time
from sets import Set
from traceback import print_stack, print_exc

from M2Crypto import Rand

from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SIXTH
from Tribler.Core.Utilities.utilities import show_permid_short,show_permid
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.Utilities.unicode import dunno2unicode
from Tribler.Core.Search.SearchManager import SearchManager

MAX_RESULTS = 20
QUERY_ID_SIZE = 20
MAX_QUERY_REPLY_LEN = 100*1024    # 100K
MAX_PEERS_TO_QUERY = 10

DEBUG = False

class FakeUtility:
    
    def __init__(self,config_path):
        self.config_path = config_path
        
    def getConfigPath(self):
        return self.config_path


class RemoteQueryMsgHandler:
    
    __single = None
    
    def __init__(self):
        if RemoteQueryMsgHandler.__single:
            raise RuntimeError, "RemoteQueryMsgHandler is singleton"
        RemoteQueryMsgHandler.__single = self

        
        self.connections = Set()    # only connected remote_search_peers
        self.query_ids2rec = {}    # ARNOCOMMENT: TODO: purge old entries...
        self.overlay_log = None
        self.registered = False

    def getInstance(*args, **kw):
        if RemoteQueryMsgHandler.__single is None:
            RemoteQueryMsgHandler(*args, **kw)
        return RemoteQueryMsgHandler.__single
    getInstance = staticmethod(getInstance)
        

    def register(self,overlay_bridge,launchmany,config,bc_fac,log=''):
        if DEBUG:
            print >> sys.stderr,"rquery: register"
        self.overlay_bridge = overlay_bridge
        self.launchmany= launchmany
        self.search_manager = SearchManager(launchmany.torrent_db)
        self.peer_db = launchmany.peer_db
        self.config = config
        self.bc_fac = bc_fac # May be None
        if log:
            self.overlay_log = OverlayLogger.getInstance(log)
        self.registered = True
        
    #
    # Incoming messages
    # 
    def handleMessage(self,permid,selversion,message):
        if not self.registered:
            return True
        
        t = message[0]
        if t == QUERY:
            if DEBUG:
                print >> sys.stderr,"rquery: Got QUERY",len(message)
            return self.recv_query(permid,message,selversion)
        if t == QUERY_REPLY:
            if DEBUG:
                print >> sys.stderr,"rquery: Got QUERY_REPLY",len(message)
            return self.recv_query_reply(permid,message,selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"rquery: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    #
    # Incoming connections
    #
    def handleConnection(self,exc,permid,selversion,locally_initiated):
        if not self.registered:
            return True
        
        if DEBUG:
            print >> sys.stderr,"rquery: handleConnection",exc,"v",selversion,"local",locally_initiated
        if exc is not None:
            return
        
        if selversion < OLPROTO_VER_SIXTH:
            return True

        if exc is None:
            self.connections.add(permid)
        else:
            self.connections.remove(permid)

        return True

    #
    # Send query
    # 
    def send_query(self,query,usercallback,max_peers_to_query=MAX_PEERS_TO_QUERY):
        """ Called by GUI Thread """
        if max_peers_to_query is None:
            max_peers_to_query = MAX_PEERS_TO_QUERY
        if DEBUG:
            print >>sys.stderr,"rquery: send_query",query
        if max_peers_to_query > 0:
            send_query_func = lambda:self.network_send_query_callback(query,usercallback,max_peers_to_query)
            self.overlay_bridge.add_task(send_query_func,0)


    def network_send_query_callback(self,query,usercallback,max_peers_to_query):
        """ Called by overlay thread """
        p = self.create_query(query,usercallback)
        m = QUERY+p
        query_conn_callback_lambda = lambda exc,dns,permid,selversion:self.conn_callback(exc,dns,permid,selversion,m)

        if DEBUG:
            print >>sys.stderr,"rquery: send_query: Connected",len(self.connections),"peers"
        
        #print "******** send query net cb:", query, len(self.connections), self.connections
        
        peers_to_query = 0
        for permid in self.connections:
            self.overlay_bridge.connect(permid,query_conn_callback_lambda)
            peers_to_query += 1
        
        if peers_to_query < max_peers_to_query and self.bc_fac and self.bc_fac.buddycast_core:
            query_cand = self.bc_fac.buddycast_core.getRemoteSearchPeers(MAX_PEERS_TO_QUERY-peers_to_query)
            for permid in query_cand:
                if permid not in self.connections:    # don't call twice
                    self.overlay_bridge.connect(permid,query_conn_callback_lambda)
                    peers_to_query += 1
        
        if DEBUG:
            print >>sys.stderr,"rquery: send_query: Sent to",peers_to_query,"peers"
        
    def create_query(self,query,usercallback):
        d = {}
        d['q'] = 'SIMPLE '+query
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
        #print "******* queury was sent to", show_permid_short(permid), exc
        pass
    
    
    #
    # Receive query
    # 
    
    def recv_query(self,permid,message,selversion):
        if selversion < OLPROTO_VER_SIXTH:
            return False

        # Unpack
        try:
            d = bdecode(message[1:])
        except:
            if DEBUG:
                print >>sys.stderr,"rquery: Cannot bdecode QUERY message"
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


    
    
    #
    # Send query reply
    #
    def process_query(self, permid, d, selversion):
        q = d['q'][len('SIMPLE '):]
        q = dunno2unicode(q)
        # Format: 'SIMPLE '+string of space separated keywords
        # In the future we could support full SQL queries:
        # SELECT infohash,torrent_name FROM torrent_db WHERE status = ALIVE
        kws = q.split()
        hits = self.search_manager.search(kws, maxhits=MAX_RESULTS)
        
        p = self.create_query_reply(d['id'],hits)
        m = QUERY_REPLY+p

        if self.overlay_log:
            nqueries = self.get_peer_nqueries(permid)
            # RECV_MSG PERMID OVERSION NUM_QUERIES MSG
            self.overlay_log('RECV_QRY', show_permid(permid), selversion, nqueries, repr(d))

            # RPLY_QRY PERMID NUM_HITS MSG
            self.overlay_log('RPLY_QRY', show_permid(permid), len(hits), repr(p))

        self.overlay_bridge.send(permid, m, self.send_callback)
        
        self.inc_peer_nqueries(permid)
        
        
    def create_query_reply(self,id,hits):
        d = {}
        d['id'] = id
        d2 = {}
        for torrent in hits:
            r = {}
            # NEWDBSTANDARD. Do not rename r's fields: they are part of the 
            # rquery protocol spec.
            r['content_name'] = torrent['name'] 
            r['length'] = torrent['length']
            r['leecher'] = torrent['num_leechers']
            r['seeder'] = torrent['num_seeders']
            # Arno: TODO: sending category doesn't make sense as that's user-defined
            # leaving it now because of time constraints
            r['category'] = torrent['category']
            d2[torrent['infohash']] = r
        d['a'] = d2
        return bencode(d)


    #
    # Receive query reply
    #

    def recv_query_reply(self,permid,message,selversion):
        
        #print "****** recv query reply", len(message)
        
        if selversion < OLPROTO_VER_SIXTH:
            return False
        
        if len(message) > MAX_QUERY_REPLY_LEN:
            return True    # don't close

        # Unpack
        try:
            d = bdecode(message[1:])
        except:
            if DEBUG:
                print >>sys.stderr,"rquery: Cannot bdecode QUERY_REPLY message"
            return False
        
        if not isValidQueryReply(d,selversion):
            if DEBUG:
                print >>sys.stderr,"rquery: not valid QUERY_REPLY message"
            return False

        # Check auth
        queryrec = self.is_registered_query_id(d['id'])
        if not queryrec:
            if DEBUG:
                print >>sys.stderr,"rquery: QUERY_REPLY has unknown query ID"
            return False

        # Process
        self.process_query_reply(permid,queryrec['query'],queryrec['usercallback'],d)
        return True


    def process_query_reply(self,permid,query,usercallback,d):
        
        if DEBUG:
            print >>sys.stderr,"rquery: process_query_reply:",show_permid_short(permid),query,d
        
        if len(d['a']) > 0:
            remote_query_usercallback_lambda = lambda:usercallback(permid,query,d['a'])
            self.launchmany.session.uch.perform_usercallback(remote_query_usercallback_lambda)
        elif DEBUG:
            print >>sys.stderr,"rquery: QUERY_REPLY: no results found"


    def test_send_query(self,query):
        """ Called by GUI Thread """
        add_remote_hits_func = lambda:self.add_remote_query_hits(query)
        self.overlay_bridge.add_task(add_remote_hits_func,3)
        
    def add_remote_query_hits(self,query):
        torrent = {}
        torrent['content_name'] = 'Hallo 1'
        torrent['length'] = 100000000
        torrent['leecher'] = 200
        torrent['seeder'] = 400
        torrent['category'] = 'Video'
        
        torrent2 = {}
        torrent2['content_name'] = 'Hallo 2'
        torrent2['length'] = 7777777
        torrent2['leecher'] = 678
        torrent2['seeder'] = 123
        torrent2['category'] = 'Audio'
        
        d = {}
        ih = 'a'*20
        ih2 = 'b'*20
        d[ih] = torrent
        d[ih2] = torrent2
        kws = query.split()
        permid = None
        self.notify_of_remote_hits(permid,kws,d)

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
    if len(d) > 2: # no other keys
        return False
    return True

def isValidQueryReply(d,selversion):
    if not isinstance(d,dict):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: not dict"
        return False
    if not ('a' in d and 'id' in d):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a or id key missing"
        return False
    if not (isinstance(d['a'],dict) and isinstance(d['id'],str)):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a or id key not dict/str"
        return False
    if not isValidHits(d['a']):
        return False
    if len(d) > 2: # no other keys
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: too many keys, got",d.keys()
        return False
    return True

def isValidHits(d):
    if not isinstance(d,dict):
        return False
    for key in d.keys():
#        if len(key) != 20:
#            return False
        val = d[key]
        if not isValidVal(val):
            return False
    return True

def isValidVal(d):
    if not isinstance(d,dict):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a: value not dict"
        return False
    if not ('content_name' in d and 'length' in d and 'leecher' in d and 'seeder' in d and 'category' in d):
        if DEBUG:
            print >>sys.stderr,"rqmh: reply: a: key missing, got",d.keys()
        return False
#    if not (isinstance(d['content_name'],str) and isinstance(d['length'],int) and isinstance(d['leecher'],int) and isinstance(d['seeder'],int)):
#        return False
#    if len(d) > 4: # no other keys
#        return False
    return True

        