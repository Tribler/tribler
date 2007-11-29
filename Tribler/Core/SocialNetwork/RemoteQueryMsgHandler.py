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


MAX_RESULTS = 20
QUERY_ID_SIZE = 20
MAX_QUERY_REPLY_LEN = 100*1024    # 100K
MAX_NQUERIES = 10

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
        self.query_ids2query = {}
        self.overlay_log = None
        self.registered = False

    def getInstance(*args, **kw):
        if RemoteQueryMsgHandler.__single is None:
            RemoteQueryMsgHandler(*args, **kw)
        return RemoteQueryMsgHandler.__single
    getInstance = staticmethod(getInstance)
        

    def register(self,secure_overlay,launchmany,rawserver,config,bc_fac,log=''):
        if DEBUG:
            print >> sys.stderr,"rquery: register"
        self.secure_overlay = secure_overlay
        self.launchmany= launchmany
        self.torrent_db = launchmany.torrent_db
        self.friend_db = launchmany.friend_db
        self.peer_db = launchmany.peer_db
        self.rawserver = rawserver
        self.config = config
        self.bc_fac = bc_fac # May be None
        self.data_manager = None
        if log:
            self.overlay_log = OverlayLogger.getInstance(log)
        self.registered = True
        
    def register2(self,data_manager):
        self.data_manager = data_manager

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

    def sendQuery(self,query, max_nqueries=MAX_NQUERIES):
        """ Called by GUI Thread """
        if DEBUG:
            print >>sys.stderr,"rquery: sendQuery",query
        if max_nqueries > 0:
            send_query_func = lambda:self.sendQueryNetworkCallback(query,max_nqueries)
            self.rawserver.add_task(send_query_func,0)


    def sendQueryNetworkCallback(self,query,max_nqueries):
        """ Called by network thread """
        p = self.create_query(query)
        m = QUERY+p
        func = lambda exc,dns,permid,selversion:self.conn_callback(exc,dns,permid,selversion,m)

        if DEBUG:
            print >>sys.stderr,"rquery: sendQuery: Connected",len(self.connections),"peers"
        
        #print "******** send query net cb:", query, len(self.connections), self.connections
        
        nqueries = 0
        for permid in self.connections:
            self.secure_overlay.connect(permid,func)
            nqueries += 1
        
        if nqueries < max_nqueries and self.bc_fac and self.bc_fac.buddycast_core:
            query_cand = self.bc_fac.buddycast_core.getRemoteSearchPeers(MAX_NQUERIES-nqueries)
            for permid in query_cand:
                if permid not in self.connections:    # don't call twice
                    self.secure_overlay.connect(permid,func)
                    nqueries += 1
        
        if DEBUG:
            print >>sys.stderr,"rquery: sendQuery: Sent to",nqueries,"peers"
        
    def create_query(self,query):
        d = {}
        d['q'] = 'SIMPLE '+query
        d['id'] = self.create_and_register_query_id(query)
        return bencode(d)
        
    def create_and_register_query_id(self,query):
        id = Rand.rand_bytes(QUERY_ID_SIZE)
        self.query_ids2query[id] = query
        return id
        
    def is_registered_query_id(self,id):
        if id in self.query_ids2query:
            return self.query_ids2query[id]
        else:
            return None
        
    def conn_callback(self,exc,dns,permid,selversion,message):
        if exc is None and selversion >= OLPROTO_VER_SIXTH:
            self.secure_overlay.send(permid,message,self.send_callback)
            
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
        if self.data_manager is None:    # running on text terminate
            self.create_data_manager()
        hits = self.data_manager.remoteSearch(kws, maxhits=MAX_RESULTS)
        
        p = self.create_query_reply(d['id'],hits)
        m = QUERY_REPLY+p

        if self.overlay_log:
            nqueries = self.get_peer_nqueries(permid)
            # RECV_MSG PERMID OVERSION NUM_QUERIES MSG
            self.overlay_log('RECV_QRY', show_permid(permid), selversion, nqueries, repr(d))

            # RPLY_QRY PERMID NUM_HITS MSG
            self.overlay_log('RPLY_QRY', show_permid(permid), len(hits), repr(p))

        self.secure_overlay.send(permid, m, self.send_callback)
        
        self.inc_peer_nqueries(permid)
        
    def create_data_manager(self):
        config_path = '.Tribler'
        #print "*** create fake data manager", config_path
        utility = FakeUtility(config_path)
        
        # TODO FIXME: let GUI be updated via Notifier structure
        #from Tribler.vwxGUI.torrentManager import TorrentDataManager
        #self.data_manager = TorrentDataManager.getInstance(utility)
        #self.data_manager.loadData()
        
        
    def create_query_reply(self,id,hits):
        d = {}
        d['id'] = id
        d2 = {}
        for torrent in hits:
            r = {}
            r['content_name'] = torrent['content_name']
            r['length'] = torrent['length']
            r['leecher'] = torrent['leecher']
            r['seeder'] = torrent['seeder']
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
        query = self.is_registered_query_id(d['id'])
        if not query:
            if DEBUG:
                print >>sys.stderr,"rquery: QUERY_REPLY has unknown query ID"
            return False

        # Process
        self.process_query_reply(permid,query,d)
        return True


    def process_query_reply(self,permid,query,d):
        
        #print "****** recv query reply:", query, d
        
        if len(d['a']) > 0:
            #TODO: report to standardOverview instead
            kws = query.split()
            self.notify_of_remote_hits(permid,kws,d['a'])
        elif DEBUG:
            print >>sys.stderr,"rquery: QUERY_REPLY: no results found"

    def notify_of_remote_hits(self,permid,kws,answers):
        guiutil = self.launchmany.get_gui_util()
        if guiutil is None:
            if DEBUG:
                print >>sys.stderr,"rquery: QUERY_REPLY: cannot pass remote hits to GUI layer"
            return
        
        so = guiutil.standardOverview
        so.invokeLater(self.notify_hits_guicallback,[so,permid,kws,answers])


    def notify_hits_guicallback(self,standardOverview,permid,kws,answers):
        """ Called by GUI thread """
        standardOverview.gotRemoteHits(permid,kws,answers)


    def test_sendQuery(self,query):
        """ Called by GUI Thread """
        add_remote_hits_func = lambda:self.add_remote_query_hits(query)
        self.rawserver.add_task(add_remote_hits_func,3)
        
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

def inc_peer_nqueries(self, permid):
        peer = self.peer_db.getPeer(permid)
        nqueries = peer['nqueries']
        self.peer_db.updatePeer(permid, 'nqueries', nqueries+1)